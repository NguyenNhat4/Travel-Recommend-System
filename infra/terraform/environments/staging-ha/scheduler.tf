# Lịch bật/tắt ban đêm của staging-ha (múi giờ Asia/Ho_Chi_Minh). Chốt bởi người vận hành:
# - App (MIG) và runner: tắt sau 23:57, bật lại trước 08:30.
# - Crawler: thêm khung 01:45–04:00 để cào; khung 08:30–23:59 do resource policy trong crawler.tf đảm nhiệm.
# - Patroni (DB), Redis, Cloud NAT, Load Balancer: giữ 24/7. Crawler cần DB để ghi cdp.products trong khung cào đêm.
#
# Cơ chế:
# - VM đơn (crawler): instance schedule (resource policy). Mỗi VM chỉ gắn được một policy.
# - MIG app: instance schedule không áp dụng được. Autoscaler dùng CPU không scale về 0, nên Cloud Scheduler
#   tắt autoscaler (mode OFF) rồi resize MIG về 0; buổi sáng bật lại autoscaler (mode ON) để MIG lên min_replicas.
# - Crawler, khung thêm 01:45–04:00: Cloud Scheduler gọi Compute API start/stop.
#
# Lưu ý: runner `vota-ci-runner` không nằm trong Terraform. Lịch của nó được gắn bằng gcloud (xem history).

variable "ops_schedule_timezone" {
  description = "Múi giờ áp dụng cho mọi lịch bật/tắt staging-ha trong file này."
  type        = string
  default     = "Asia/Ho_Chi_Minh"
}

variable "app_autoscaler_off_schedule" {
  description = "Lúc tắt autoscaler MIG app (trước khi resize về 0)."
  type        = string
  default     = "57 23 * * *"
}

variable "app_resize_zero_schedule" {
  description = "Lúc resize MIG app về 0 VM."
  type        = string
  default     = "59 23 * * *"
}

variable "app_autoscaler_on_schedule" {
  description = "Lúc bật lại autoscaler MIG app, để MIG lên min_replicas trước 08:30."
  type        = string
  default     = "20 8 * * *"
}

variable "crawler_extra_start_schedule" {
  description = "Lúc bật VM crawler cho khung cào thêm."
  type        = string
  default     = "45 1 * * *"
}

variable "crawler_extra_stop_schedule" {
  description = "Lúc tắt VM crawler sau khung cào thêm."
  type        = string
  default     = "0 4 * * *"
}

locals {
  scheduler_compute_base = "https://compute.googleapis.com/compute/v1/projects/${var.project_id}"
  app_autoscaler_name    = "${var.name_prefix}-app"
  app_mig_name           = "${var.name_prefix}-app"

  # Body đầy đủ của autoscaler, lấy từ cùng giá trị với main.tf. Chỉ khác ở mode, để không phụ thuộc
  # vào việc PATCH có merge từng phần hay không.
  app_autoscaler_policy = merge(
    {
      minNumReplicas    = var.min_replicas
      maxNumReplicas    = var.max_replicas
      coolDownPeriodSec = var.boot_to_ready_seconds
      cpuUtilization    = { utilizationTarget = var.cpu_target }
      scaleInControl = {
        timeWindowSec       = 600
        maxScaledInReplicas = { fixed = 1 }
      }
    },
    var.memory_target_percent > 0 ? {
      customMetricUtilizations = [{
        metric                = "agent.googleapis.com/memory/percent_used"
        filter                = "metric.labels.state = \"used\""
        utilizationTarget     = var.memory_target_percent
        utilizationTargetType = "GAUGE"
      }]
    } : {}
  )

  app_autoscaler_body = {
    ON = jsonencode({
      name              = local.app_autoscaler_name
      target            = "projects/${var.project_id}/regions/${var.region}/instanceGroupManagers/${local.app_mig_name}"
      autoscalingPolicy = merge(local.app_autoscaler_policy, { mode = "ON" })
    })
    OFF = jsonencode({
      name              = local.app_autoscaler_name
      target            = "projects/${var.project_id}/regions/${var.region}/instanceGroupManagers/${local.app_mig_name}"
      autoscalingPolicy = merge(local.app_autoscaler_policy, { mode = "OFF" })
    })
  }
}

# --- Cloud Scheduler: API và service account chỉ có quyền bật/tắt đúng tài nguyên staging-ha ---

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

# --- Cloud Scheduler jobs ---

# MIG app: tắt autoscaler, resize về 0, rồi bật lại autoscaler buổi sáng.
resource "google_cloud_scheduler_job" "app_autoscaler_off" {
  name      = "${var.name_prefix}-app-autoscaler-off"
  region    = var.region
  schedule  = var.app_autoscaler_off_schedule
  time_zone = var.ops_schedule_timezone

  http_target {
    http_method = "PATCH"
    uri         = "${local.scheduler_compute_base}/regions/${var.region}/autoscalers?autoscaler=${local.app_autoscaler_name}"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(local.app_autoscaler_body["OFF"])
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.cloudscheduler, google_project_iam_member.scheduler_ops, google_service_account_iam_member.scheduler_token_creator]
}

resource "google_cloud_scheduler_job" "app_resize_zero" {
  name      = "${var.name_prefix}-app-resize-zero"
  region    = var.region
  schedule  = var.app_resize_zero_schedule
  time_zone = var.ops_schedule_timezone

  http_target {
    http_method = "POST"
    uri         = "${local.scheduler_compute_base}/regions/${var.region}/instanceGroupManagers/${local.app_mig_name}/resize?size=0"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.cloudscheduler, google_project_iam_member.scheduler_ops, google_service_account_iam_member.scheduler_token_creator]
}

resource "google_cloud_scheduler_job" "app_autoscaler_on" {
  name      = "${var.name_prefix}-app-autoscaler-on"
  region    = var.region
  schedule  = var.app_autoscaler_on_schedule
  time_zone = var.ops_schedule_timezone

  http_target {
    http_method = "PATCH"
    uri         = "${local.scheduler_compute_base}/regions/${var.region}/autoscalers?autoscaler=${local.app_autoscaler_name}"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(local.app_autoscaler_body["ON"])
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.cloudscheduler, google_project_iam_member.scheduler_ops, google_service_account_iam_member.scheduler_token_creator]
}

# Crawler: khung cào thêm 01:45–04:00. Khung 08:30–23:59 do resource policy trong crawler.tf.
resource "google_cloud_scheduler_job" "crawler_extra_start" {
  count     = local.crawler_enabled ? 1 : 0
  name      = "${var.name_prefix}-crawler-extra-start"
  region    = var.region
  schedule  = var.crawler_extra_start_schedule
  time_zone = var.ops_schedule_timezone

  http_target {
    http_method = "POST"
    uri         = "${local.scheduler_compute_base}/zones/${var.crawler_zone}/instances/${local.crawler_name}/start"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.cloudscheduler, google_project_iam_member.scheduler_ops, google_service_account_iam_member.scheduler_token_creator]
}

resource "google_cloud_scheduler_job" "crawler_extra_stop" {
  count     = local.crawler_enabled ? 1 : 0
  name      = "${var.name_prefix}-crawler-extra-stop"
  region    = var.region
  schedule  = var.crawler_extra_stop_schedule
  time_zone = var.ops_schedule_timezone

  http_target {
    http_method = "POST"
    uri         = "${local.scheduler_compute_base}/zones/${var.crawler_zone}/instances/${local.crawler_name}/stop"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.cloudscheduler, google_project_iam_member.scheduler_ops, google_service_account_iam_member.scheduler_token_creator]
}
