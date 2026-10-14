# Cảnh báo container, log và job cào của VM staging-ha (app, máy cào). Thay thế 7 policy `vota-staging` của staging cũ đã xoá
# ngày 2026-10-14 (xem history/2026-10-14-xoa-7-alert-vota-staging.md).
# Nguồn: log do Ops Agent đẩy lên (ops-agent-staging.yaml, ops-agent-crawler.yaml) và collector trên VM (docker_events,
# container_disk). Nhãn `vm` lấy từ tên VM trong log (compute.googleapis.com/resource_name): email nêu đúng VM.
# Mọi alert dùng local.alert_channels, nên chịu lịch mute 23:55–08:35 như các alert HA khác (quyết định 2026-10-12).

# --- Log-based metric ----------------------------------------------------------------------------------------------

resource "google_logging_metric" "container_oom" {
  name        = "${var.name_prefix}_container_oom"
  description = "Container Docker bị kernel tiêu diệt do hết bộ nhớ (OOM). Mỗi dòng là một lần."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"oom\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "vm"
      value_type  = "STRING"
      description = "Tên VM phát sinh sự kiện."
    }
  }

  label_extractors = {
    vm = "EXTRACT(labels.\"compute.googleapis.com/resource_name\")"
  }
}

resource "google_logging_metric" "container_dung" {
  name        = "${var.name_prefix}_container_dung"
  description = "Container dịch vụ (không phải job cào) vừa dừng: sự kiện die của Docker."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.container_class=\"service\" AND jsonPayload.event=\"die\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "vm"
      value_type  = "STRING"
      description = "Tên VM phát sinh sự kiện."
    }
    labels {
      key         = "container_name"
      value_type  = "STRING"
      description = "Tên container vừa dừng."
    }
  }

  label_extractors = {
    vm             = "EXTRACT(labels.\"compute.googleapis.com/resource_name\")"
    container_name = "EXTRACT(jsonPayload.container_name)"
  }
}

resource "google_logging_metric" "container_disk" {
  name        = "${var.name_prefix}_container_disk"
  description = "Dung lượng đĩa mỗi container: lớp ghi + log json + volume. Lấy mẫu 5 phút bởi vota-container-disk-collector."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"container_disk\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "By"
    labels {
      key         = "vm"
      value_type  = "STRING"
      description = "Tên VM."
    }
    labels {
      key         = "container_name"
      value_type  = "STRING"
      description = "Tên container."
    }
  }

  value_extractor = "EXTRACT(jsonPayload.total_bytes)"

  label_extractors = {
    vm             = "EXTRACT(labels.\"compute.googleapis.com/resource_name\")"
    container_name = "EXTRACT(jsonPayload.container_name)"
  }

  bucket_options {
    exponential_buckets {
      growth_factor      = 1.1
      num_finite_buckets = 200
      scale              = 1048576
    }
  }
}

resource "google_logging_metric" "docker_watcher" {
  name        = "${var.name_prefix}_docker_watcher"
  description = "Nhịp (heartbeat) của trình theo dõi sự kiện Docker. Mất nhịp nghĩa là không ghi nhận được OOM và container dừng."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"heartbeat\" AND jsonPayload.watcher=\"docker-events\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "crawler_container_fail" {
  name        = "${var.name_prefix}_crawler_container_fail"
  description = "Container job cào thoát với mã khác 0 hoặc bị OOM-kill."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.container_class=\"crawler\" AND (jsonPayload.event=\"die\" OR jsonPayload.event=\"oom\") AND jsonPayload.exit_code!=0"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "vm"
      value_type  = "STRING"
      description = "Tên VM chạy job cào."
    }
  }

  label_extractors = {
    vm = "EXTRACT(labels.\"compute.googleapis.com/resource_name\")"
  }
}

resource "google_logging_metric" "error_logs" {
  name        = "${var.name_prefix}_error_logs"
  description = "Dòng log mức ERROR trở lên của mọi VM, trừ log của Ops Agent."
  filter      = "resource.type=\"gce_instance\" AND severity>=ERROR AND NOT logName:\"ops-agent\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "vm"
      value_type  = "STRING"
      description = "Tên VM phát sinh log lỗi."
    }
  }

  label_extractors = {
    vm = "EXTRACT(labels.\"compute.googleapis.com/resource_name\")"
  }
}

# --- Alert policy (tên và mô tả tiếng Việt) ----------------------------------------------------------------------

resource "google_monitoring_alert_policy" "container_oom" {
  display_name          = "${var.name_prefix} Container: hết bộ nhớ (OOM)"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Có container bị OOM-kill trong 1 phút"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.container_oom.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.vm"]
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Lỗi: một container Docker trên VM nêu trong incident (nhãn vm) bị kernel tiêu diệt vì hết bộ nhớ (OOM-kill). Container đó đã dừng, hoặc đã được khởi động lại theo restart policy.\nKiểm tra: docker inspect tên container, xem trường State.OOMKilled; xem RAM của VM trên dashboard HA (ô RAM theo từng VM); xem giới hạn bộ nhớ của container trong file compose.\nXử lý: nếu RAM của VM đang cao, giảm tải hoặc tăng máy. Nếu một container dùng RAM bất thường, đọc log container đó trước khi khởi động lại."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "container_dung" {
  display_name          = "${var.name_prefix} Container: dịch vụ bị dừng bất thường"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Có container dịch vụ vừa dừng trong 1 phút"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.container_dung.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.vm", "metric.label.container_name"]
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Lỗi: một container dịch vụ (không phải job cào) trên VM nêu trong incident vừa dừng. Nếu container có restart policy thì có thể đã tự khởi động lại; nếu không, dịch vụ đang ngừng.\nKiểm tra: trên VM đó, chạy docker ps -a và docker inspect tên container để xem exit code và OOMKilled; xem sự kiện dừng trong log docker_events.\nXử lý: nếu container không tự khởi động, chạy lại bằng docker compose up -d tên-service. Nếu dừng lặp lại, đọc log container trước khi khởi động lại lần nữa."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "container_disk" {
  display_name          = "${var.name_prefix} Container: đĩa gần đầy (trên 5 GiB)"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Một container dùng trên ${var.alert_container_disk_bytes} byte đĩa (p99 trong 10 phút)"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.container_disk.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_container_disk_bytes
      duration        = "0s"

      aggregations {
        alignment_period     = "600s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metric.label.vm", "metric.label.container_name"]
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Lỗi: một container trên VM nêu trong incident dùng quá 5 GiB đĩa (lớp ghi, log json và volume), mẫu p99 trong 10 phút.\nKiểm tra: trên VM đó, chạy docker system df -v; xem /var/log/vota/container-disk.jsonl; xem ô đĩa theo container trên dashboard HA.\nXử lý: dọn image cũ và log json quá lớn. Không xoá volume đang dùng. Nếu log json phình, kiểm tra mức log của service đó."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "docker_watcher" {
  display_name          = "${var.name_prefix} Docker: mất tín hiệu trình theo dõi sự kiện"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Không có nhịp của trình theo dõi sự kiện Docker trong 5 phút"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.docker_watcher.name}\""
      duration = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Lỗi: trình theo dõi sự kiện Docker (vota-docker-event-watcher) không gửi nhịp trong 5 phút trên mọi VM. Khi trình này dừng, cảnh báo OOM, container dừng và job cào thất bại không ghi nhận được sự kiện nào.\nKiểm tra: trên VM, chạy systemctl status vota-docker-event-watcher và systemctl status google-cloud-ops-agent. Trong Logs Explorer, lọc jsonPayload.event=heartbeat để xem VM nào còn nhịp.\nXử lý: khởi động lại vota-docker-event-watcher. Nếu Ops Agent lỗi, khởi động lại google-cloud-ops-agent rồi kiểm tra lại nhịp."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "error_logs" {
  display_name          = "${var.name_prefix} Log: lỗi mức ERROR trên VM"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Có dòng log mức ERROR trở lên trong 5 phút"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.error_logs.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.vm"]
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Lỗi: VM nêu trong incident (nhãn vm) có dòng log mức ERROR trở lên trong 5 phút. Ngưỡng là lớn hơn 0, nên một dòng cũng kêu. Ngoại trừ log của Ops Agent.\nKiểm tra: trong Logs Explorer, lọc resource.type=gce_instance, nhãn compute.googleapis.com/resource_name bằng tên VM, và severity>=ERROR. Xem thông điệp lỗi và jsonPayload.service để biết service nào phát sinh.\nVí dụ đã gặp (14/10/2026 lúc 03:29 UTC): 16 lỗi 503 trên GET /api/v1/products trong 2 giây, do quá tải.\nXử lý: nếu lỗi lặp lại hoặc tăng, xử lý theo nguyên nhân trong log. Nếu chỉ vài dòng đơn lẻ, ghi nhận và theo dõi."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "crawler_container_fail" {
  display_name          = "${var.name_prefix} Job cào: container cào thất bại"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Container cào thoát mã khác 0 hoặc bị OOM-kill trong 1 phút"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.crawler_container_fail.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.vm"]
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Lỗi: container job cào trên VM nêu trong incident thoát với mã khác 0 hoặc bị OOM-kill.\nKiểm tra: log của lượt cào gần nhất (jsonPayload.service=crawler, sự kiện run.end) và sự kiện die hoặc oom của container trên VM đó.\nXử lý: đọc docs/guide/van-hanh-crawler-db-noi-bo.md mục 2 trước khi chạy lại lượt cào."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "log_spike" {
  display_name          = "${var.name_prefix} Log: lượng log tăng đột biến (toàn project)"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Log nạp vào Cloud Logging trong 1 giờ vượt ${var.alert_log_spike_bytes_per_hour} byte (toàn project)"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/billing/bytes_ingested\" resource.type=\"global\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_log_spike_bytes_per_hour
      duration        = "0s"

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Lỗi: lượng log nạp vào Cloud Logging trong 1 giờ vượt 0,25 GiB, tính cho cả project (không theo VM).\nKiểm tra: dùng gcloud logging read theo service để tìm nguồn lớn. Các nguyên nhân thường gặp: LOG_BODIES bật trong lúc tải thử, vòng lặp lỗi, hoặc LOG_LEVEL=DEBUG.\nXử lý: tắt LOG_BODIES, đặt LOG_LEVEL cao hơn, hoặc sửa vòng lặp lỗi trước khi chi phí tăng thêm."
    mime_type = "text/markdown"
  }
}
