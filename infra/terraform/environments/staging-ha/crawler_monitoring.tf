# Cảnh báo "catalog không đổi quá X giờ" và "job cào không chạy", cho job cào chạy bằng cron trên VM.
# Nguồn: dòng `catalog.freshness` mà mỗi tick của fresh_catalog.py phát ra (15 phút một lần), jsonPayload.service="crawler".
# X là `sla.maxCatalogAgeHours` trong cấu hình của monitor job cào (mặc định 48 giờ; nên hạ theo chu kỳ cào thật).
# Cảnh báo kiểu "vắng mặt" tối đa 23,5 giờ, nên không đặt thẳng "không có lượt thành công quá X giờ" ở đây: ngưỡng X nằm
# trong job, còn Terraform chỉ cảnh báo dòng freshness báo late hoặc vắng mặt. Chưa kiểm trên GCP (cần apply thật).
locals {
  crawler_alerts = var.crawler_alerts_enabled
}

resource "google_logging_metric" "crawler_freshness_heartbeat" {
  count       = local.crawler_alerts ? 1 : 0
  name        = "${var.name_prefix}_crawler_freshness_heartbeat"
  description = "Dòng catalog.freshness của job cào (mỗi tick)."
  filter      = "jsonPayload.service=\"crawler\" AND jsonPayload.event=\"catalog.freshness\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "crawler_catalog_late" {
  count       = local.crawler_alerts ? 1 : 0
  name        = "${var.name_prefix}_crawler_catalog_late"
  description = "Lần nạp DB thành công gần nhất cũ hơn sla.maxCatalogAgeHours."
  filter      = "jsonPayload.service=\"crawler\" AND jsonPayload.event=\"catalog.freshness\" AND jsonPayload.state=\"late\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# Bổ sung cho cảnh báo "crawler failed" của infra/monitoring (chỉ thấy container thoát khác 0): đọc thẳng event run.end của crawler.
resource "google_logging_metric" "crawler_run_failed" {
  count       = local.crawler_alerts ? 1 : 0
  name        = "${var.name_prefix}_crawler_run_failed"
  description = "Lượt cào kết thúc với status=failed (mọi nơi chạy)."
  filter      = "jsonPayload.service=\"crawler\" AND jsonPayload.event=\"run.end\" AND jsonPayload.status=\"failed\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "crawler_run_failed" {
  count                 = local.crawler_alerts ? 1 : 0
  display_name          = "${var.name_prefix} Crawler: LƯỢT CÀO THẤT BẠI"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "run.end status=failed"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.crawler_run_failed[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "3600s"
  }

  documentation {
    content   = "Một lượt cào kết thúc thất bại (lỗi nạp DB, DB failover giữa lượt, gate chặn...). Xem log run.end và job log của lượt; docs/guide/van-hanh-crawler-db-noi-bo.md §2."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "crawler_silent" {
  count                 = local.crawler_alerts ? 1 : 0
  display_name          = "${var.name_prefix} Crawler: JOB CÀO KHÔNG CHẠY"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Không có dòng catalog.freshness trong 60 phút (tick 15 phút)"
    condition_absent {
      filter   = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.crawler_freshness_heartbeat[0].name}\""
      duration = "3600s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  alert_strategy {
    auto_close = "3600s"
  }

  documentation {
    content   = "Job cào không phát tick nào trong 1 giờ: Cloud cron trên VM bị gỡ hoặc VM chết. Dữ liệu catalog sẽ cũ dần. Xem docs/guide/van-hanh-crawler-db-noi-bo.md §2."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "crawler_catalog_late" {
  count                 = local.crawler_alerts ? 1 : 0
  display_name          = "${var.name_prefix} Crawler: CATALOG KHÔNG ĐỔI QUÁ HẠN"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Tick báo catalog late trong 15 phút"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.crawler_catalog_late[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "900s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "3600s"
  }

  documentation {
    content   = "Lần nạp DB thành công gần nhất cũ hơn sla.maxCatalogAgeHours: job vẫn tick nhưng không nạp được (nguồn bị chặn, gate chặn, DB lỗi). Xem monitor job cào và docs/guide/van-hanh-crawler-db-noi-bo.md §2."
    mime_type = "text/markdown"
  }
}
