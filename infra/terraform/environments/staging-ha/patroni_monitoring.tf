# Cảnh báo cụm DB Patroni. Nguồn: dòng JSON mỗi phút từ ops/patroni/cluster_probe.py trên từng node DB (Ops Agent →
# Cloud Logging, jsonPayload.event = patroni_cluster). Dùng chung kênh thông báo với monitoring.tf (local.alert_channels).
# Chưa kiểm trên GCP: tên trường jsonPayload sau parse_json của Ops Agent; chỉ apply thật mới xác nhận.
resource "google_logging_metric" "patroni_probe_heartbeat" {
  count       = var.create_patroni ? 1 : 0
  name        = "${var.name_prefix}_patroni_probe_heartbeat"
  description = "Dòng probe cụm Patroni (mỗi node, mỗi phút)."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"patroni_cluster\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "patroni_no_replica" {
  count       = var.create_patroni ? 1 : 0
  name        = "${var.name_prefix}_patroni_no_replica"
  description = "Cụm có node chính (leader) nhưng không còn replica đang đồng bộ (streaming): hệ thống là một DB đơn lẻ."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"patroni_cluster\" AND jsonPayload.status=\"no_replica\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "patroni_no_leader" {
  count       = var.create_patroni ? 1 : 0
  name        = "${var.name_prefix}_patroni_no_leader"
  description = "Cụm không có node chính (leader), hoặc node không hỏi được Patroni."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"patroni_cluster\" AND (jsonPayload.status=\"no_leader\" OR jsonPayload.status=\"broken\")"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# Không còn replica: sau failover (hoặc khi replica chết) thêm một sự cố nữa là mất dữ liệu. 5 phút để Patroni tự
# vào lại node cũ (pg_rewind) trước khi kêu; quá 5 phút là cần người dựng node thay thế.
resource "google_monitoring_alert_policy" "patroni_no_replica" {
  count                 = var.create_patroni ? 1 : 0
  display_name          = "${var.name_prefix} DB: KHÔNG CÒN REPLICA"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Cụm Patroni chỉ còn node chính (leader) trong 5 phút"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.patroni_no_replica[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Cụm DB chỉ còn một node ghi được, không có replica nào: mất tiếp node này là mất dữ liệu đã thanh toán. Làm theo docs/guide/van-hanh-db-patroni.md §5 (dựng lại replica): thay VM node lỗi, đĩa dữ liệu mới, Patroni tự sao chép (basebackup) từ node chính."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "patroni_no_leader" {
  count                 = var.create_patroni ? 1 : 0
  display_name          = "${var.name_prefix} DB: KHÔNG CÓ NODE CHÍNH"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Cụm Patroni không có node chính (leader) trong 2 phút"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.patroni_no_leader[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "120s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Không có node chính (leader) Postgres hơn 2 phút (bình thường failover mất dưới 1 phút). Kiểm etcd (cần 2/3 thành viên), docker logs vota-patroni trên cả hai node, docs/guide/van-hanh-db-patroni.md §6."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "patroni_probe_absent" {
  count                 = var.create_patroni ? 1 : 0
  display_name          = "${var.name_prefix} DB: probe Patroni không gửi dữ liệu"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Không có dòng probe trong 5 phút"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.patroni_probe_heartbeat[0].name}\""
      duration = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Cả hai node DB không gửi dòng probe: kiểm cron, Ops Agent và VM. Các cảnh báo 'không còn replica' và 'không có node chính' sẽ KHÔNG kêu khi probe không gửi dữ liệu."
    mime_type = "text/markdown"
  }
}
