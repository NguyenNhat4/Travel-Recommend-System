# Mute cảnh báo HA trong khung 23:55–08:35 (múi giờ Asia/Ho_Chi_Minh).
# Cơ chế: Cloud Scheduler tắt kênh email HA (enabled = false) lúc 23:55 và bật lại lúc 08:35.
# Khi kênh tắt, các alert của staging-ha không gửi email trong khung này. Incident vẫn được ghi nhận trong Monitoring.
# Kênh `vota-staging` (stack cũ, ngoài staging-ha) không đổi.
#
# Replica Patroni (pg-b) tắt theo lịch 00:00–08:12. Primary (pg-a) và witness (pg-w) giữ 24/7.
# Patroni đang dùng synchronous_mode_strict: false nên primary vẫn nhận ghi khi replica tắt.

variable "alert_mute_start_schedule" {
  description = "Lúc tắt kênh cảnh báo HA (mute bắt đầu)."
  type        = string
  default     = "55 23 * * *"
}

variable "alert_mute_end_schedule" {
  description = "Lúc bật lại kênh cảnh báo HA (mute kết thúc)."
  type        = string
  default     = "35 8 * * *"
}

locals {
  # Kênh email HA duy nhất (alert_emails). Nếu có nhiều email, chỉnh tại đây.
  ha_alert_channel_name = values(google_monitoring_notification_channel.email)[0].name
}

resource "google_cloud_scheduler_job" "alert_mute_on" {
  name      = "${var.name_prefix}-alert-mute-on"
  region    = var.region
  schedule  = var.alert_mute_start_schedule
  time_zone = var.ops_schedule_timezone

  http_target {
    http_method = "PATCH"
    uri         = "https://monitoring.googleapis.com/v3/${local.ha_alert_channel_name}?updateMask=enabled"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(jsonencode({ name = local.ha_alert_channel_name, enabled = false }))
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.cloudscheduler, google_project_iam_member.scheduler_ops, google_service_account_iam_member.scheduler_token_creator]
}

resource "google_cloud_scheduler_job" "alert_mute_off" {
  name      = "${var.name_prefix}-alert-mute-off"
  region    = var.region
  schedule  = var.alert_mute_end_schedule
  time_zone = var.ops_schedule_timezone

  http_target {
    http_method = "PATCH"
    uri         = "https://monitoring.googleapis.com/v3/${local.ha_alert_channel_name}?updateMask=enabled"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode(jsonencode({ name = local.ha_alert_channel_name, enabled = true }))
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_project_service.cloudscheduler, google_project_iam_member.scheduler_ops, google_service_account_iam_member.scheduler_token_creator]
}

# Replica Patroni (pg-b, sync standby): tắt 00:00, bật 08:12. Primary (pg-a) và witness (pg-w) không có lịch.
resource "google_compute_resource_policy" "patroni_replica_schedule" {
  count  = local.patroni_enabled ? 1 : 0
  name   = "${var.name_prefix}-pg-b-schedule"
  region = var.region

  instance_schedule_policy {
    vm_start_schedule {
      schedule = "12 8 * * *"
    }
    vm_stop_schedule {
      schedule = "0 0 * * *"
    }
    time_zone = var.ops_schedule_timezone
  }
}
