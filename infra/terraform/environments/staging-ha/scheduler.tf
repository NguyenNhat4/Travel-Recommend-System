# Cloud Scheduler của staging-ha. Lịch tắt/bật VM ban đêm đã bị vô hiệu (2026-10-12, thay thế lịch chốt 2026-10-10;
# xem history/2026-10-12-tat-lich-vm-va-bo-chan-cd.md): toàn bộ VM staging-ha chạy 24/7, gồm app (MIG), crawler,
# Patroni (pg-a, pg-b, pg-w), weaviate, bastion. Runner `vota-ci-runner` nằm ngoài Terraform; lịch của nó đã gỡ bằng gcloud.
# Cloud NAT, Load Balancer không phải VM: giữ 24/7.
#
# File này chỉ còn service account và quyền Cloud Scheduler cho lịch mute cảnh báo (alert_mute.tf).

variable "ops_schedule_timezone" {
  description = "Múi giờ cho lịch mute cảnh báo staging-ha (alert_mute.tf)."
  type        = string
  default     = "Asia/Ho_Chi_Minh"
}

# --- Cloud Scheduler: API và service account cho lịch mute cảnh báo ---

resource "google_project_service" "cloudscheduler" {
  project            = var.project_id
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "scheduler" {
  account_id   = "${var.name_prefix}-scheduler"
  display_name = "Lịch bật/tắt staging-ha"
}

resource "google_project_iam_custom_role" "ops_scheduler" {
  role_id     = "votaHaOpsScheduler"
  title       = "VOTA HA ops scheduler"
  description = "Bật/tắt VM và điều chỉnh autoscaler/MIG của staging-ha. Không có quyền tạo hoặc xoá tài nguyên."
  permissions = [
    "compute.instances.get",
    "compute.instances.start",
    "compute.instances.stop",
    "compute.autoscalers.get",
    "compute.autoscalers.update",
    "compute.instanceGroupManagers.get",
    "compute.instanceGroupManagers.update",
    "compute.instanceGroupManagers.use",
    "monitoring.notificationChannels.update",
  ]
}

resource "google_project_iam_member" "scheduler_ops" {
  project = var.project_id
  role    = google_project_iam_custom_role.ops_scheduler.id
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

data "google_project" "this" {
  project_id = var.project_id
}

# Service agent của Cloud Scheduler cần tạo token cho service account trên.
resource "google_service_account_iam_member" "scheduler_token_creator" {
  service_account_id = google_service_account.scheduler.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
  depends_on         = [google_project_service.cloudscheduler]
}
