# Cảnh báo job cào, cho job cào chạy bằng cron trên VM. Hai nguồn khác nhau:
# - Heartbeat "job không chạy": dòng `catalog.due`, mỗi tick cron (15 phút) đều có, kể cả khi đang có lượt chạy
#   (reason "đang có lượt chạy"). Kiểm trên log thật 2026-10-12: đều 15 phút, không phụ thuộc máy rảnh.
# - "Catalog quá hạn": dòng `catalog.freshness state=late`. Bản crawler đang chạy KHÔNG phát dòng này đều mỗi tick
#   (entrypoint thoát ở nhánh due), nên cảnh báo này tắt bằng crawler_late_alert_enabled cho tới khi bản có sửa được deploy.
# X của "catalog quá hạn" là `sla.maxCatalogAgeHours` trong cấu hình job (mặc định 48 giờ).
locals {
  crawler_alerts      = var.crawler_alerts_enabled
  crawler_late_alerts = var.crawler_alerts_enabled && var.crawler_late_alert_enabled
}

resource "google_logging_metric" "crawler_freshness_heartbeat" {
  count       = local.crawler_alerts ? 1 : 0
  name        = "${var.name_prefix}_crawler_freshness_heartbeat"
  description = "Dòng catalog.due của job cào (mỗi tick cron, kể cả khi đang có lượt chạy)."
  filter      = "jsonPayload.service=\"crawler\" AND jsonPayload.event=\"catalog.due\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "crawler_catalog_late" {
  count       = local.crawler_late_alerts ? 1 : 0
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
  display_name          = "${var.name_prefix} Job cào: LƯỢT CÀO THẤT BẠI"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Lượt cào kết thúc với status=failed"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.crawler_run_failed[0].name}\""
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
  display_name          = "${var.name_prefix} Job cào: KHÔNG CHẠY"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Không có dòng catalog.due trong 60 phút (tick 15 phút)"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.crawler_freshness_heartbeat[0].name}\""
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
    content   = "Job cào không có tick nào trong 1 giờ (dòng catalog.due vắng): cron trên VM bị gỡ, VM tắt ngoài lịch, hoặc Ops Agent không đẩy log. Dữ liệu catalog sẽ cũ dần. Xem docs/guide/van-hanh-crawler-db-noi-bo.md §2."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "crawler_catalog_late" {
  count                 = local.crawler_late_alerts ? 1 : 0
  display_name          = "${var.name_prefix} Job cào: CATALOG QUÁ HẠN"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Tick báo catalog quá hạn trong 15 phút"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.crawler_catalog_late[0].name}\""
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
