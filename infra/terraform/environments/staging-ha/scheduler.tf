# Lịch bật/tắt ban đêm của staging-ha (múi giờ Asia/Ho_Chi_Minh). Chốt bởi người vận hành ngày 2026-10-10, đã vô hiệu
# ngày 2026-10-12 (xem history/2026-10-12-tat-lich-vm-va-bo-chan-cd.md):
# - Các VM đã được gỡ khỏi resource policy lịch (patroni.tf, bastion.tf, weaviate.tf, crawler.tf). VM chạy 24/7.
# - Cloud Scheduler job tắt/bật app (MIG) và khung cào thêm đã bị xoá khỏi file này.
# - Ba resource policy bên dưới chưa được xoá: đang không gắn VM nào. Xoá ở PR sau, khi đã đảm bảo VM không còn tham chiếu.
#   Xoá cùng lúc với bước gỡ attachment từng gây lỗi resourceInUseByAnotherResource (10/10).
# - Runner `vota-ci-runner` nằm ngoài Terraform; lịch của nó đã gỡ bằng gcloud.
# - Cloud NAT, Load Balancer không phải VM: giữ 24/7.
#
# File này còn lại: ba resource policy (chờ xoá), service account và quyền Cloud Scheduler cho lịch mute cảnh báo
# (alert_mute.tf).

variable "ops_schedule_timezone" {
  description = "Múi giờ áp dụng cho mọi lịch bật/tắt staging-ha trong file này."
  type        = string
  default     = "Asia/Ho_Chi_Minh"
}

variable "vm_night_stop_schedule" {
  description = "Lúc tắt các VM staging-ha có instance schedule: Patroni, weaviate, bastion. Crawler dùng crawler_stop_schedule."
  type        = string
  default     = "59 23 * * *"
}

variable "vm_night_start_schedule" {
  description = "Lúc bật các VM staging-ha có instance schedule: Patroni, weaviate, bastion. Crawler dùng crawler_start_schedule."
  type        = string
  default     = "30 8 * * *"
}

# --- Lịch VM (instance schedule) đã gỡ khỏi VM, chờ xoá ở PR sau ---
# Mỗi VM đã bỏ resource_policies trong patroni.tf, weaviate.tf, bastion.tf, crawler.tf.

resource "google_compute_resource_policy" "patroni_schedule" {
  count  = local.patroni_enabled ? 1 : 0
  name   = "${var.name_prefix}-patroni-schedule"
  region = var.region

  instance_schedule_policy {
    vm_start_schedule {
      schedule = var.vm_night_start_schedule
    }
    vm_stop_schedule {
      schedule = var.vm_night_stop_schedule
    }
    time_zone = var.ops_schedule_timezone
  }
}

resource "google_compute_resource_policy" "weaviate_schedule" {
  count  = var.create_weaviate ? 1 : 0
  name   = "${var.name_prefix}-weaviate-schedule"
  region = var.region

  instance_schedule_policy {
    vm_start_schedule {
      schedule = var.vm_night_start_schedule
    }
    vm_stop_schedule {
      schedule = var.vm_night_stop_schedule
    }
    time_zone = var.ops_schedule_timezone
  }
}

resource "google_compute_resource_policy" "bastion_schedule" {
  count  = local.bastion_enabled ? 1 : 0
  name   = "${var.name_prefix}-bastion-schedule"
  region = var.region

  instance_schedule_policy {
    vm_start_schedule {
      schedule = var.vm_night_start_schedule
    }
    vm_stop_schedule {
      schedule = var.vm_night_stop_schedule
    }
    time_zone = var.ops_schedule_timezone
  }
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
