#!/usr/bin/env bash
# Apply Terraform root staging-ha. Từ 2026-10-13 chỉ staging-ha-infra-cd.yml gọi: deploy ứng dụng không chạy Terraform
# (image mong muốn nằm ở all-instances config của MIG). BACKEND_REF/FRONTEND_REF lấy từ last-good và chỉ là image dự
# phòng của template. Không chạy migration DB ở đây.
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
# Ngưỡng autoscaler lên 90% CPU/RAM (2026-10-13): alert "CPU trung bình > cpu_target" lấy threshold = var.cpu_target nên đổi theo.
google_monitoring_alert_policy.group_at_max|update
google_compute_instance.crawler[0]|create
google_compute_firewall.patroni_clients[0]|update
# Cảnh báo crawler (crawler_alerts_enabled = true, 2026-10-12): metric và policy đã có trong state.
google_logging_metric.crawler_freshness_heartbeat[0]|update
google_logging_metric.crawler_catalog_late[0]|create
google_monitoring_alert_policy.crawler_catalog_late[0]|create
google_monitoring_alert_policy.crawler_run_failed[0]|update
google_monitoring_alert_policy.crawler_silent[0]|update
# Cảnh báo bộ nhớ và đĩa của từng VM app (2026-10-13): policy mới, không thay đổi policy nào khác.
google_monitoring_alert_policy.group_memory_high|create
google_monitoring_alert_policy.group_disk_high|create
# Đổi tên hiển thị sang tiếng Việt (2026-10-13): chỉ đổi display_name, title, description, content; filter, ngưỡng và metric không đổi.
google_monitoring_alert_policy.mute_job_failed|update
google_monitoring_alert_policy.group_below_min|update
google_monitoring_alert_policy.group_at_max|update
google_monitoring_alert_policy.lb_5xx_ratio|update
google_monitoring_alert_policy.lb_latency|update
# Cảnh báo container, log và job cào (2026-10-14), thay cho 7 policy vota-staging đã xoá: 6 log-metric và 7 policy mới.
google_logging_metric.container_oom|create
google_logging_metric.container_dung|create
google_logging_metric.container_disk|create
google_logging_metric.docker_watcher|create
google_logging_metric.crawler_container_fail|create
google_logging_metric.error_logs|create
google_monitoring_alert_policy.container_oom|create
google_monitoring_alert_policy.container_dung|create
google_monitoring_alert_policy.container_disk|create
google_monitoring_alert_policy.docker_watcher|create
google_monitoring_alert_policy.error_logs|create
google_monitoring_alert_policy.crawler_container_fail|create
google_monitoring_alert_policy.log_spike|create
google_monitoring_uptime_check_config.lb_ready|update
google_monitoring_alert_policy.patroni_no_replica[0]|update
google_monitoring_alert_policy.patroni_no_leader[0]|update
google_monitoring_alert_policy.patroni_probe_absent[0]|update
google_logging_metric.patroni_no_replica[0]|update
google_logging_metric.patroni_no_leader[0]|update
# Patroni và dashboard (2026-10-12): startup-script có metrics_filter (f664124c), pg-a/pg-b đã ghi trực tiếp qua SSH.
# Plan đã kiểm: chỉ metadata và dashboard_json đổi, không đổi machine_type/scheduling/status (không dừng VM DB).
google_compute_instance.patroni["a"]|update
google_compute_instance.patroni["b"]|update
google_compute_instance.patroni["w"]|update
google_monitoring_dashboard.ha|update
# Đổi tên hiển thị dashboard sang SOTA (2026-10-14): chỉ displayName/title, không đổi metric hay log filter.
google_monitoring_dashboard.ha_db_crawler|update
# VM bastion và crawler: chỉ bỏ resource_policies (gỡ lịch tắt/bật, 2026-10-12, PR #180). Không đổi gì khác.
google_compute_instance.bastion[0]|update
google_compute_instance.crawler[0]|update
# Xoá job Cloud Scheduler tắt/bật app và khung cào thêm (PR #180, 2026-10-12). Không có VM nào tham chiếu, nên không có
# ràng buộc thứ tự với bước gỡ resource_policies. Ba resource policy lịch chưa nằm trong danh sách: xoá ở PR sau.
google_cloud_scheduler_job.app_autoscaler_off|delete
google_cloud_scheduler_job.app_autoscaler_on|delete
google_cloud_scheduler_job.app_resize_zero|delete
google_cloud_scheduler_job.crawler_extra_start[0]|delete
google_cloud_scheduler_job.crawler_extra_stop[0]|delete
# Alert runner CI không chạy (2026-10-13).
google_monitoring_alert_policy.ci_runner_down|create
# Chữ hiển thị tiếng Việt (c8e52d98) đổi display_name của alert runner sau khi alert đã được tạo.
google_monitoring_alert_policy.ci_runner_down|update
# cpu_target 0.55 -> 0.9 (commit 10aa9488): alert group_at_max dùng var.cpu_target làm ngưỡng nên chỉ đổi threshold.
google_monitoring_alert_policy.group_at_max|update
# Cảnh báo RAM, đĩa, CPU của cụm DB và job cào (2026-10-14): sáu policy mới, không đổi policy nào khác. Dashboard đã có ở trên.
google_monitoring_alert_policy.db_memory_high[0]|create
google_monitoring_alert_policy.db_disk_high[0]|create
google_monitoring_alert_policy.db_cpu_high[0]|create
google_monitoring_alert_policy.crawler_memory_high[0]|create
google_monitoring_alert_policy.crawler_disk_high[0]|create
google_monitoring_alert_policy.crawler_cpu_sustained[0]|create
# Tách dashboard HA thành năm trang theo chủ đề, thêm dashboard cảnh báo, và nhóm alert theo tên VM (2026-10-14).
# Dashboard tổng quan giữ địa chỉ cũ (update); bốn trang mới và trang cảnh báo là create. Policy chỉ đổi aggregation (group_by).
google_monitoring_dashboard.ha_latency|create
google_monitoring_dashboard.ha_vm_app|create
google_monitoring_dashboard.ha_db_crawler|create
google_monitoring_dashboard.ha_logs|create
google_monitoring_dashboard.ha_alerts|create
# Sửa dashboard cảnh báo (2026-10-14): cấu hình khớp dạng API lưu lại và tiêu đề 5xx "2%" (trước là 1.9999…). Thay đổi thật một lần.
google_monitoring_dashboard.ha_alerts|update
# Trang nhật ký (2026-10-14): log theo từng service (mọi mức) thay vì bốn khung lọc sẵn. Thay đổi thật một lần.
google_monitoring_dashboard.ha_logs|update
google_monitoring_alert_policy.group_memory_high|update
google_monitoring_alert_policy.group_disk_high|update
google_monitoring_alert_policy.db_memory_high[0]|update
google_monitoring_alert_policy.db_disk_high[0]|update
google_monitoring_alert_policy.db_cpu_high[0]|update
google_monitoring_alert_policy.crawler_memory_high[0]|update
google_monitoring_alert_policy.crawler_disk_high[0]|update
google_monitoring_alert_policy.crawler_cpu_sustained[0]|update
'
unexpected="$(terraform show -json "$plan_file" | jq -r '
  .resource_changes[]
  | select(.change.actions != ["no-op"] and .change.actions != ["read"])
  | "\(.address)|\(.change.actions | join(","))"')"

while IFS= read -r change; do
  [ -n "$change" ] || continue
  if ! grep -Fxq "$change" <<< "$allowed_changes"; then
    printf 'Plan có thay đổi ngoài phạm vi cho phép:\n%s\n' "$change" >&2
    die 'dừng trước khi apply (drift giữa mã và state? xem docs/guide/van-hanh-cd-staging-ha.md, mục "Cổng plan")'
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
