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

# --- Tài nguyên VM job cào: RAM, đĩa, CPU ----------------------------------------------------------------------------
# Lọc theo mã instance của chính VM (tham chiếu Terraform), nên không cần thêm nhãn vào VM. Các cảnh báo này không phụ
# thuộc crawler_alerts_enabled, chỉ phụ thuộc VM có được tạo hay không (create_crawler_vm).
# try(): khi create_crawler_vm = false thì VM không tồn tại; policy cũng không được tạo (count = 0).
locals {
  crawler_instance_id   = try(google_compute_instance.crawler[0].instance_id, "")
  crawler_memory_filter = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${local.crawler_instance_id}\""
  crawler_disk_filter   = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${local.crawler_instance_id}\""
  crawler_cpu_filter    = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" metric.labels.instance_name=\"${local.crawler_name}\""
}

resource "google_monitoring_alert_policy" "crawler_memory_high" {
  count                 = local.crawler_enabled ? 1 : 0
  display_name          = "${var.name_prefix} Job cào: RAM máy cào cao"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "RAM đã dùng trên máy cào > ${var.alert_crawler_memory_percent}% trong 10 phút"
    condition_threshold {
      filter          = local.crawler_memory_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_crawler_memory_percent
      duration        = "600s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metadata.system_labels.name"]
      }
    }
  }

  conditions {
    display_name = "Không có dữ liệu RAM của máy cào trong 10 phút"
    condition_absent {
      filter   = local.crawler_memory_filter
      duration = "600s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "VM job cào dùng quá ${var.alert_crawler_memory_percent}% RAM trong 10 phút. Kiểm docker stats trên VM vota-ha-crawler và log lượt cào (docs/guide/van-hanh-crawler-db-noi-bo.md §2). Nếu cảnh báo kêu vắng dữ liệu: Ops Agent trên máy cào dừng hoặc VM tắt, kiểm bằng gcloud compute instances describe."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "crawler_disk_high" {
  count                 = local.crawler_enabled ? 1 : 0
  display_name          = "${var.name_prefix} Job cào: đĩa máy cào đầy"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Đĩa đã dùng trên một thiết bị của máy cào > ${var.alert_crawler_disk_percent}% trong 5 phút"
    condition_threshold {
      filter          = local.crawler_disk_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_crawler_disk_percent
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metadata.system_labels.name", "metric.label.device"]
      }
    }
  }

  conditions {
    display_name = "Không có dữ liệu đĩa của máy cào trong 5 phút"
    condition_absent {
      filter   = local.crawler_disk_filter
      duration = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Đĩa boot 15 GB của VM job cào quá ${var.alert_crawler_disk_percent}%. Mỗi image crawler khoảng 3 GB; khi đĩa đầy, lượt cào sau không pull được image. Kiểm docker system df và thư mục /srv/vota/fresh-catalog-logs trên VM. Không xoá volume đang dùng. Nếu đỉnh chạm mức này mỗi ngày, cần tăng đĩa: đổi kích thước đĩa boot buộc thay VM (xem history/2026-10-09-crawler-disk-15gb.md)."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "crawler_cpu_sustained" {
  count                 = local.crawler_enabled ? 1 : 0
  display_name          = "${var.name_prefix} Job cào: CPU máy cào cao kéo dài"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "CPU máy cào > ${var.alert_crawler_cpu_percent}% liên tục ${var.alert_crawler_cpu_minutes} phút"
    condition_threshold {
      filter          = local.crawler_cpu_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_crawler_cpu_percent / 100
      duration        = "${var.alert_crawler_cpu_minutes * 60}s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metric.label.instance_name"]
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "VM job cào ở trên ${var.alert_crawler_cpu_percent}% CPU liên tục ${var.alert_crawler_cpu_minutes} phút. Lượt cào bình thường chạm đỉnh gần 100% khoảng 1 giờ mỗi ngày (quanh 09:00 giờ Việt Nam), nên alert này là lượt bị treo hoặc chạy quá lâu. Kiểm tiến trình trên VM và log lượt cào (docs/guide/van-hanh-crawler-db-noi-bo.md §2)."
    mime_type = "text/markdown"
  }
}
