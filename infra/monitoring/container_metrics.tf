# Custom metrics written by vota-container-stats-collector on the App VM. Declaring the descriptors
# here means dashboards and alerts can reference them before the collector's first write.
locals {
  container_metric_descriptors = {
    cpu_percent = {
      display_name = "Container CPU (100 = one vCPU)"
      unit         = "%"
    }
    memory_bytes = {
      display_name = "Container memory used"
      unit         = "By"
    }
    memory_percent = {
      display_name = "Container memory used (percent of limit)"
      unit         = "%"
    }
  }
}

resource "google_monitoring_metric_descriptor" "container" {
  for_each     = local.container_metric_descriptors
  type         = "custom.googleapis.com/vota/container/${each.key}"
  display_name = each.value.display_name
  description  = "Sampled from docker stats every 60 seconds by vota-container-stats-collector."
  metric_kind  = "GAUGE"
  value_type   = "DOUBLE"
  unit         = each.value.unit

  labels {
    key         = "container_name"
    value_type  = "STRING"
    description = "Docker container name."
  }
}

resource "google_monitoring_alert_policy" "staging_container_stats_absent" {
  display_name          = "${var.name_prefix} container metrics collector silent"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "No per-container CPU/RAM samples from the App VM"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"${google_monitoring_metric_descriptor.container["cpu_percent"].type}\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
      duration = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }

  documentation {
    content   = "vota-container-stats-collector has not written samples for five minutes, so the per-container CPU/RAM panels are blank. On the App VM: `systemctl status vota-container-stats-collector` and `journalctl -u vota-container-stats-collector -n 50`."
    mime_type = "text/markdown"
  }
}

# The App VM has 2 vCPU and the metric counts 100 = one vCPU, so 190 means one container is using ~95% of the VM.
resource "google_monitoring_alert_policy" "staging_container_cpu" {
  display_name          = "${var.name_prefix} container CPU high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "A container uses more than ${var.container_cpu_alert_percent} percent CPU (100 = one vCPU)"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"${google_monitoring_metric_descriptor.container["cpu_percent"].type}\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.container_cpu_alert_percent
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metric.label.container_name"]
      }
    }
  }

  alert_strategy { auto_close = "1800s" }

  documentation {
    content   = "A container has used more than ${var.container_cpu_alert_percent}% CPU (100% = one vCPU, the App VM has 2) for five minutes. See the 'CPU by container' panel, then `docker stats` on the App VM."
    mime_type = "text/markdown"
  }
}
