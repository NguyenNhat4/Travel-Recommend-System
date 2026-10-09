# Vòng đời log trong Cloud Logging: giữ bao lâu, không nạp những dòng vô ích, và cảnh báo khi lượng nạp tăng đột biến.
# Trước đây dùng mặc định của GCP (30 ngày) mà không khai báo; ghi vào code để không ai đổi tay mà Terraform không biết.

# Bucket _Default đã tồn tại: import lần đầu, sau đó Terraform chỉ quản lý retention.
import {
  to = google_logging_project_bucket_config.default
  id = "projects/${var.project_id}/locations/global/buckets/_Default"
}

resource "google_logging_project_bucket_config" "default" {
  project        = var.project_id
  location       = "global"
  bucket_id      = "_Default"
  retention_days = var.log_retention_days
}

# Không lưu: log DEBUG và dòng health check thành công (kiểu text cũ của uvicorn). Lỗi 5xx của health vẫn được lưu.
# Log-based metric vẫn đếm các dòng này vì metric tính trước khi loại; chỉ chi phí lưu trữ giảm.
resource "google_logging_project_exclusion" "debug_and_health_ok" {
  name        = "${var.name_prefix}-debug-and-health-ok"
  description = "DEBUG logs and successful health-check access lines are not stored."
  filter      = "resource.type=\"gce_instance\" AND (severity=DEBUG OR jsonPayload.log=~\"GET /health/[a-z]+ HTTP/1\\.1\\\" 200\")"
}

resource "google_monitoring_alert_policy" "log_ingest_spike" {
  display_name          = "${var.name_prefix} log ingestion spike"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Project ingests more than ${var.log_ingest_alert_gib_per_hour} GiB of logs per hour"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/billing/bytes_ingested\" resource.type=\"global\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.log_ingest_alert_gib_per_hour * 1073741824
      duration        = "0s"

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy { auto_close = "7200s" }

  documentation {
    content   = "Log volume is far above normal. Likely causes: LOG_BODIES on during a load test, an error loop, or DEBUG level. Check `gcloud logging read` by service, set LOG_BODIES=false or raise LOG_LEVEL, and see docs/spec/logging-schema.md."
    mime_type = "text/markdown"
  }
}
