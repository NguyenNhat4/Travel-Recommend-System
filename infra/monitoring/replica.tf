# Monitoring for the PostgreSQL read replica. Everything here is skipped while
# var.db_replica_vm_name is empty, so merging this file before the replica exists is safe.
locals {
  replica_enabled     = var.db_replica_vm_name != ""
  replica_instance_id = local.replica_enabled ? data.google_compute_instance.db_replica[0].instance_id : ""

  replica_vm_alerts = local.replica_enabled ? {
    memory = {
      title  = "memory above 90 percent"
      metric = "agent.googleapis.com/memory/percent_used"
      state  = true
    }
    disk = {
      title  = "disk above 90 percent"
      metric = "agent.googleapis.com/disk/percent_used"
      state  = true
    }
  } : {}
}

# One line per minute from ops/db-replica-lag-probe.sh; status is ok | lagging | broken.
resource "google_logging_metric" "replica_probe_heartbeat" {
  count       = local.replica_enabled ? 1 : 0
  name        = "${var.name_prefix}_db_replica_probe_heartbeat"
  description = "Replication probe heartbeat from the DB replica VM."
  filter      = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${local.replica_instance_id}\" AND jsonPayload.event=\"pg_replica\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "replica_unhealthy" {
  count       = local.replica_enabled ? 1 : 0
  name        = "${var.name_prefix}_db_replica_unhealthy"
  description = "Replica probe reported lagging or broken replication."
  filter      = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${local.replica_instance_id}\" AND jsonPayload.event=\"pg_replica\" AND jsonPayload.status!=\"ok\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "replica_uptime" {
  count                 = local.replica_enabled ? 1 : 0
  display_name          = "${var.name_prefix} DB replica VM unavailable"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "DB replica VM uptime metric absent"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/uptime\" resource.labels.instance_id=\"${local.replica_instance_id}\""
      duration = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }

  documentation {
    content   = "No VM uptime metric from DB replica ${var.db_replica_vm_name} for five minutes. Check VM state and Ops Agent. Reads through the replica tunnel will fail; the primary is not affected."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "replica_vm" {
  for_each              = local.replica_vm_alerts
  display_name          = "${var.name_prefix} DB replica ${each.value.title}"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "DB replica ${each.value.title}"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"${each.value.metric}\" metric.labels.state=\"used\" resource.labels.instance_id=\"${local.replica_instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 90
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }

  documentation {
    content   = "DB replica ${var.db_replica_vm_name}: ${each.value.title} for five minutes."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "replica_replication" {
  count                 = local.replica_enabled ? 1 : 0
  display_name          = "${var.name_prefix} DB replica replication unhealthy"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Replica lagging or not streaming"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.replica_unhealthy[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "180s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }

  documentation {
    content   = "The replica reports status lagging (replay behind more than 60 seconds) or broken (not streaming / not in recovery). See docs/guide/van-hanh-db-replica.md."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "replica_probe_absent" {
  count                 = local.replica_enabled ? 1 : 0
  display_name          = "${var.name_prefix} DB replica probe silent"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Replica probe heartbeat absent"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.replica_probe_heartbeat[0].name}\""
      duration = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }

  documentation {
    content   = "No replication probe line for five minutes. Check the cron entry, the Docker container and Ops Agent on the replica VM."
    mime_type = "text/markdown"
  }
}
