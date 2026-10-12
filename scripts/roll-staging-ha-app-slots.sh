#!/usr/bin/env bash
# Đổi image app trên từng VM của MIG vota-ha-app mà không làm gián đoạn: đẩy infra/terraform/environments/staging-ha/
# slot-deploy.sh lên VM qua IAP SSH rồi chạy mode `deploy` (bản mới chạy song song bản cũ, đổi proxy khi ready).
# Từng VM một; dừng ngay khi một VM lỗi (VM đó vẫn phục vụ bằng bản cũ, các VM sau chưa bị đụng).
#
# Biến môi trường (bắt buộc): BACKEND_REF, FRONTEND_REF (image@sha256:...), GCP_PROJECT_ID
# Tuỳ chọn: MIG_NAME (vota-ha-app), MIG_REGION (asia-southeast1)
set -euo pipefail

: "${BACKEND_REF:?BACKEND_REF là bắt buộc}"
: "${FRONTEND_REF:?FRONTEND_REF là bắt buộc}"
: "${GCP_PROJECT_ID:?GCP_PROJECT_ID là bắt buộc}"
MIG_NAME="${MIG_NAME:-vota-ha-app}"
MIG_REGION="${MIG_REGION:-asia-southeast1}"
SLOT_SCRIPT="${SLOT_SCRIPT:-$(dirname "$0")/../infra/terraform/environments/staging-ha/slot-deploy.sh}"

die() {
  printf 'roll-staging-ha-app-slots.sh: %s\n' "$*" >&2
  exit 1
}

[[ "$BACKEND_REF" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'BACKEND_REF phải là image@sha256:<64 hex>'
[[ "$FRONTEND_REF" =~ ^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$ ]] || die 'FRONTEND_REF phải là image@sha256:<64 hex>'
[ -s "$SLOT_SCRIPT" ] || die "không có script slot: $SLOT_SCRIPT"
bash -n "$SLOT_SCRIPT" || die "script slot lỗi cú pháp"

# Không ghim khoá host: VM app bị MIG tạo lại (autohealing, thay template) sinh khoá SSH host mới, và known_hosts của runner
# giữ khoá cũ nên `Host key verification failed` làm cả bước roll lỗi. Kênh vẫn qua IAP tới đúng instance, đăng nhập bằng OS Login.
script_b64="$(base64 < "$SLOT_SCRIPT" | tr -d '\n')"

vms="$(gcloud compute instance-groups managed list-instances "$MIG_NAME" --region "$MIG_REGION" --project "$GCP_PROJECT_ID" --format=json \
  | jq -r '.[] | select(.instanceStatus == "RUNNING") | "\(.instance | split("/") | last) \(.instance | split("/") | .[-3])"')"
[ -n "$vms" ] || die "MIG $MIG_NAME không có VM RUNNING"

result_file="$(mktemp)"
trap 'rm -f "$result_file"' EXIT

# `< /dev/null` ở lệnh ssh là bắt buộc: ssh đọc stdin và sẽ nuốt phần còn lại của danh sách VM ($vms), nên chỉ VM đầu được cập nhật.
while read -r name zone; do
  [ -n "$name" ] || continue
  echo "=== $name ($zone) ==="
  remote="echo '$script_b64' | base64 -d | sudo -n tee /usr/local/sbin/vota-slot-deploy.sh >/dev/null && sudo -n chmod 0755 /usr/local/sbin/vota-slot-deploy.sh && sudo -n env BACKEND_IMAGE='$BACKEND_REF' FRONTEND_IMAGE='$FRONTEND_REF' /usr/local/sbin/vota-slot-deploy.sh deploy"
  if ! gcloud compute ssh "$name" --project "$GCP_PROJECT_ID" --zone "$zone" --tunnel-through-iap --quiet --strict-host-key-checking=no --command "$remote" < /dev/null 2>&1 | tee "$result_file"; then
    die "cập nhật $name lỗi; VM này vẫn phục vụ bằng bản cũ, các VM sau chưa bị đụng"
  fi
  line="$(grep -E '^SLOT_RESULT ' "$result_file" | tail -n 1 || true)"
  [ -n "$line" ] || die "$name không trả SLOT_RESULT"
  [[ "$line" == *" backend=$BACKEND_REF "* && "$line" == *" frontend=$FRONTEND_REF" ]] \
    || die "$name chạy image khác image đích: $line"
  echo "OK $name: $line"
done <<< "$vms"
