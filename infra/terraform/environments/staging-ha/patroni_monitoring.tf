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

# --- Tài nguyên node DB: RAM, đĩa, CPU -------------------------------------------------------------------------------
# Node witness pg-w (etcd) không cài Ops Agent (patroni-node.sh.tftpl: khối cài nằm trong nhánh role=db), nên không có
# RAM và đĩa. Lọc RAM và đĩa theo nhãn role=patroni để chỉ lấy hai node DB. CPU lấy theo tiền tố tên và gồm cả pg-w,
# vì CPU đo từ hypervisor và không cần Ops Agent. Mỗi policy tách theo tên VM để email nêu đúng node.
locals {
  db_memory_filter = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\" metadata.user_labels.\"component\"=\"database\" metadata.user_labels.\"role\"=\"patroni\""
  db_disk_filter   = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" metadata.user_labels.\"component\"=\"database\" metadata.user_labels.\"role\"=\"patroni\""
  db_cpu_filter    = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" metric.labels.instance_name=starts_with(\"${var.name_prefix}-pg-\")"
}

resource "google_monitoring_alert_policy" "db_memory_high" {
  count                 = var.create_patroni ? 1 : 0
  display_name          = "${var.name_prefix} DB: RAM một node DB cao"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "RAM đã dùng trên một node DB > ${var.alert_db_memory_percent}% trong 10 phút"
    condition_threshold {
      filter          = local.db_memory_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_db_memory_percent
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
    display_name = "Không node DB nào gửi dữ liệu RAM trong 10 phút"
    condition_absent {
      filter   = local.db_memory_filter
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
    content   = "Một node DB (pg-a hoặc pg-b) dùng quá ${var.alert_db_memory_percent}% RAM trong 10 phút. RAM cao kéo dài có thể làm Postgres bị OOM-kill; khi đó Patroni failover và cụm mất replica. Xem ô RAM trên dashboard `vota-ha HA: DB và máy cào`, rồi docker logs vota-patroni trên node đó (docs/guide/van-hanh-db-patroni.md §6). Tên VM nằm trong incident. Node pg-w không có Ops Agent nên không xuất hiện ở đây."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "db_disk_high" {
  count                 = var.create_patroni ? 1 : 0
  display_name          = "${var.name_prefix} DB: đĩa một node DB đầy"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Đĩa đã dùng trên một thiết bị của node DB > ${var.alert_db_disk_percent}% trong 5 phút"
    condition_threshold {
      filter          = local.db_disk_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_db_disk_percent
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
    display_name = "Không node DB nào gửi dữ liệu đĩa trong 5 phút"
    condition_absent {
      filter   = local.db_disk_filter
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
    content   = "Một thiết bị đĩa của node DB đầy quá ${var.alert_db_disk_percent}% trong 5 phút. Postgres ngừng ghi khi đĩa dữ liệu đầy. Kiểm thiết bị nào trong alert, rồi du -sh /mnt/disks/pgdata trên node đó và log Postgres. Không xoá dữ liệu của Postgres khi chưa đối chiếu với docs/guide/van-hanh-db-patroni.md. Tên VM nằm trong incident."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "db_cpu_high" {
  count                 = var.create_patroni ? 1 : 0
  display_name          = "${var.name_prefix} DB: CPU một node DB cao"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "CPU trung bình của một node DB > ${var.alert_db_cpu_percent}% trong 15 phút"
    condition_threshold {
      filter          = local.db_cpu_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_db_cpu_percent / 100
      duration        = "900s"

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
    content   = "CPU của một node DB (pg-a, pg-b hoặc witness pg-w) trung bình trên ${var.alert_db_cpu_percent}% trong 15 phút. Đỉnh 7 ngày của hai node DB chỉ khoảng 13%, nên mức này là bất thường. Kiểm truy vấn đang chạy và autovacuum trong Postgres (docs/guide/van-hanh-db-patroni.md §4). Nếu là pg-w, kiểm etcd: CPU cao ở witness không liên quan tới dữ liệu."
    mime_type = "text/markdown"
  }
}
