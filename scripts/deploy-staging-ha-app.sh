#!/usr/bin/env bash
# Đưa image backend và frontend (digest bất biến) vào MIG vota-ha-app qua Terraform root staging-ha.
# Dùng bởi .github/workflows/staging-ha-cd.yml (triển khai và rollback). Không chạy migration DB ở đây.
#
# Biến môi trường (bắt buộc):
#   BACKEND_REF   image@sha256:...   (ví dụ europe-.../vota-backend@sha256:...)
#   FRONTEND_REF  image@sha256:...
#   TF_STATE_BUCKET   bucket GCS chứa state (prefix infra/staging-ha)
#   TFVARS_FILE   đường dẫn staging-ha.tfvars (ghi từ secret STAGING_HA_TFVARS, không commit)
#   TF_ROOT       thư mục Terraform root (mặc định infra/terraform/environments/staging-ha)
#
# Chỉ chấp nhận plan đổi đúng: template app (thay thế), MIG app (update version), VM crawler (tạo lần đầu).
# Mọi thay đổi khác làm script dừng TRƯỚC khi apply.
set -euo pipefail

die() {
  printf 'deploy-staging-ha-app.sh: %s\n' "$*" >&2
  exit 1
}

: "${BACKEND_REF:?BACKEND_REF là bắt buộc}"
: "${FRONTEND_REF:?FRONTEND_REF là bắt buộc}"
: "${TF_STATE_BUCKET:?TF_STATE_BUCKET là bắt buộc}"
: "${TFVARS_FILE:?TFVARS_FILE là bắt buộc}"
TF_ROOT="${TF_ROOT:-infra/terraform/environments/staging-ha}"
# Preflight quota (chỉ khi plan có rolling update của MIG app). Rollout tạo max_surge VM mới trước khi xoá VM cũ,
# nên cần thêm APP_SURGE × vCPU của một VM app. Giữ APP_SURGE đồng bộ với max_surge_fixed trong main.tf (0 từ 2026-10-09: thay VM không surge, chấp nhận downtime, không cần thêm quota).
GCP_PROJECT_ID="${GCP_PROJECT_ID:-}"
APP_SURGE="${APP_SURGE:-0}"
APP_VM_VCPUS="${APP_VM_VCPUS:-2}"   # e2-standard-2

[[ "$BACKEND_REF" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'BACKEND_REF phải là image@sha256:<64 hex>'
[[ "$FRONTEND_REF" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'FRONTEND_REF phải là image@sha256:<64 hex>'
[ -s "$TFVARS_FILE" ] || die "không có tfvars: $TFVARS_FILE"

plan_file="$(mktemp -d)/staging-ha.tfplan"
cd "$TF_ROOT"

terraform init -input=false -reconfigure \
  -backend-config="bucket=$TF_STATE_BUCKET" \
  -backend-config='prefix=infra/staging-ha' >/dev/null

terraform plan -input=false -no-color -lock-timeout=10m \
  -var-file="$TFVARS_FILE" \
  -var "backend_image=$BACKEND_REF" \
  -var "frontend_image=$FRONTEND_REF" \
  -out="$plan_file" >/dev/null

# Cổng an toàn: chỉ các địa chỉ dưới đây được phép đổi trong lần apply CD.
allowed_changes='
google_compute_instance_template.app|create,delete
google_compute_instance_template.app|delete,create
google_compute_region_instance_group_manager.app|update
google_compute_region_autoscaler.app|update
google_compute_instance.crawler[0]|create
'
unexpected="$(terraform show -json "$plan_file" | jq -r '
  .resource_changes[]
  | select(.change.actions != ["no-op"] and .change.actions != ["read"])
  | "\(.address)|\(.change.actions | join(","))"')"

while IFS= read -r change; do
  [ -n "$change" ] || continue
  if ! grep -Fxq "$change" <<< "$allowed_changes"; then
    printf 'Plan có thay đổi ngoài phạm vi cho phép:\n%s\n' "$change" >&2
    die 'dừng trước khi apply'
  fi
done <<< "$unexpected"

if [ -z "$unexpected" ]; then
  echo 'Plan không có thay đổi: image đã đúng.'
fi

# Preflight quota: nếu MIG app sẽ rolling update thì kiểm trước khi apply. Thiếu quota thì MIG treo ở
# QUOTA_EXCEEDED, verify timeout và rollback cũng cần surge nên cũng treo. Dừng sớm ở đây.
if grep -q '^google_compute_region_instance_group_manager\.app|' <<< "$unexpected"; then
  [ -n "$GCP_PROJECT_ID" ] || die 'GCP_PROJECT_ID là bắt buộc khi có rolling update (kiểm quota)'
  quota_json="$(gcloud compute project-info describe --project "$GCP_PROJECT_ID" --format=json)"
  limit="$(jq -er '.quotas[] | select(.metric == "CPUS_ALL_REGIONS") | .limit' <<< "$quota_json")"
  usage="$(jq -er '.quotas[] | select(.metric == "CPUS_ALL_REGIONS") | .usage' <<< "$quota_json")"
  needed=$(( APP_SURGE * APP_VM_VCPUS ))
  printf 'Quota CPUS_ALL_REGIONS: usage=%s limit=%s, rollout cần thêm %s vCPU\n' "$usage" "$limit" "$needed"
  awk -v u="$usage" -v n="$needed" -v l="$limit" 'BEGIN { exit !(u + n <= l) }' \
    || die "thiếu quota: usage $usage + cần $needed > limit $limit. Tăng quota hoặc giảm VM khác trước khi rollout."
fi

terraform apply -input=false -no-color -lock-timeout=10m "$plan_file"
