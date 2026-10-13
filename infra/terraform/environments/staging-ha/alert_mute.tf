# Mute cảnh báo HA trong khung 23:55–08:35 (múi giờ Asia/Ho_Chi_Minh).
# Cơ chế: Cloud Scheduler tắt kênh email HA (enabled = false) lúc 23:55 và bật lại lúc 08:35.
# Khi kênh tắt, các alert của staging-ha không gửi email trong khung này. Incident vẫn được ghi nhận trong Monitoring.
# Kênh `vota-staging` (stack cũ, ngoài staging-ha) không đổi.
#
# Lịch tắt/bật VM ban đêm đã bị vô hiệu (2026-10-12, xem history/2026-10-12-tat-lich-vm-va-bo-chan-cd.md): VM chạy 24/7.
# Khung mute 23:55–08:35 không còn bao quanh lần khởi động VM nào. Giữ hay bỏ là quyết định của người vận hành (còn lại trong entry).

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

  # Thử lại khi PATCH lỗi tạm thời. Lỗi cuối cùng được đếm bởi google_logging_metric.ha_alert_mute_job_failed.
  # Khai báo đúng giá trị mặc định đang có trên job, để plan không đòi xóa retry_config (drift provider, 2026-10-12).
  retry_config {
    retry_count          = 3
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
    max_doublings        = 5
    max_retry_duration   = "0s"
  }

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

  # Thử lại khi PATCH lỗi tạm thời. Nếu lượt bật lại thất bại, kênh HA tắt tới 23:55 hôm sau: đây là lý do cần alert riêng.
  # Khai báo đúng giá trị mặc định đang có trên job, để plan không đòi xóa retry_config (drift provider, 2026-10-12).
  retry_config {
    retry_count          = 3
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
    max_doublings        = 5
    max_retry_duration   = "0s"
  }

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

# Kênh luôn bật cho cảnh báo "job mute lỗi". Không đưa vào kênh bị mute, không có ignore_changes = [enabled].
resource "google_monitoring_notification_channel" "email_always" {
  for_each     = toset(var.alert_emails)
  display_name = "${var.name_prefix} HA ${each.value} (luôn bật)"
  type         = "email"

  labels = {
    email_address = each.value
  }
}

# Đếm lượt chạy lỗi (mức ERROR trở lên) của hai job mute. Log của Cloud Scheduler: resource.type=cloud_scheduler_job.
resource "google_logging_metric" "ha_alert_mute_job_failed" {
  name   = "${var.name_prefix}_alert_mute_job_failed"
  filter = "resource.type=\"cloud_scheduler_job\" AND (resource.labels.job_id=\"${var.name_prefix}-alert-mute-on\" OR resource.labels.job_id=\"${var.name_prefix}-alert-mute-off\") AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "mute_job_failed" {
  display_name          = "${var.name_prefix} HA: job bật/tắt mute cảnh báo lỗi"
  combiner              = "OR"
  notification_channels = concat([for c in google_monitoring_notification_channel.email_always : c.id], var.notification_channel_ids)

  conditions {
    display_name = "Lượt bật/tắt mute lỗi (sau retry)"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ha_alert_mute_job_failed.name}\" resource.type=\"cloud_scheduler_job\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Job Cloud Scheduler bật/tắt kênh cảnh báo HA lỗi. Nếu lượt tắt lúc 08:35 hôm nay thất bại, kênh HA có thể vẫn tắt tới 23:55: bật kênh tay (Monitoring > Notification channels) hoặc chạy lại job."
    mime_type = "text/markdown"
  }
}
