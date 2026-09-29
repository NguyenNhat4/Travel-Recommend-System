resource "google_monitoring_notification_channel" "staging_email" {
  count        = var.notification_email == "" ? 0 : 1
  display_name = "${var.name_prefix} email alerts"
  type         = "email"
  labels = {
    email_address = var.notification_email
  }
  user_labels = local.common_labels
}

resource "google_logging_metric" "staging_error_logs" {
  name        = "${var.name_prefix}_error_logs"
  description = "Error-level logs emitted by staging Compute Engine workloads."
  filter      = "resource.type=\"gce_instance\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_uptime_check_config" "staging_health" {
  display_name = "${var.name_prefix} readiness"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = var.uptime_path
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.uptime_host
    }
  }

  selected_regions = [
    "USA",
    "EUROPE",
    "ASIA_PACIFIC",
  ]
}

resource "google_monitoring_alert_policy" "staging_uptime" {
  display_name          = "${var.name_prefix} public readiness failed"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Uptime check failed"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "180s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_FRACTION_TRUE"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Staging readiness endpoint has failed from one or more Cloud Monitoring probe regions."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_vm_cpu" {
  display_name          = "${var.name_prefix} App VM CPU high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "App VM CPU above 90 percent"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.9
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "App VM (${var.app_vm_name}) CPU has remained above 90 percent for five minutes."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_memory" {
  display_name          = "${var.name_prefix} App VM memory high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "App VM memory above 90 percent"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 90
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "App VM (${var.app_vm_name}) memory utilization is above 90 percent."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_disk" {
  display_name          = "${var.name_prefix} App VM disk usage high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "App VM disk usage above 90 percent"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 90
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "App VM (${var.app_vm_name}) disk utilization is above 90 percent."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_db_uptime" {
  display_name          = "${var.name_prefix} DB VM unavailable"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "DB VM uptime metric absent"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/uptime\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\""
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
    content   = "No VM uptime metric has been received from DB VM ${var.db_vm_name} for five minutes. Check VM state, Ops Agent and GCE guest connectivity."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_db_cpu" {
  display_name          = "${var.name_prefix} DB VM CPU high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "DB VM CPU above 90 percent"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.9
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "DB VM ${var.db_vm_name} CPU has remained above 90 percent for five minutes. Check PostgreSQL workload and queries."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_db_memory" {
  display_name          = "${var.name_prefix} DB VM memory high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "DB VM memory above 90 percent"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 90
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "DB VM ${var.db_vm_name} memory utilization is above 90 percent. Check PostgreSQL memory pressure and connection count."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_db_disk" {
  display_name          = "${var.name_prefix} DB VM disk usage high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "DB VM disk above 90 percent"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 90
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "DB VM ${var.db_vm_name} disk utilization is above 90 percent. Check PostgreSQL data and WAL volumes before capacity is exhausted."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_error_logs" {
  display_name          = "${var.name_prefix} error logs"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Error-level log volume"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_error_logs.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Staging Compute Engine workloads emitted error-level logs for five minutes. Inspect Cloud Logging before restarting services."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_dashboard" "staging" {
  dashboard_json = jsonencode({
    displayName = "${var.name_prefix} infrastructure"
    labels      = local.common_labels
    gridLayout = {
      columns = "2"
      widgets = [
        {
          title = "App VM CPU utilization"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_MEAN"
                    crossSeriesReducer = "REDUCE_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "App VM memory utilization"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_MEAN"
                    crossSeriesReducer = "REDUCE_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "App VM disk utilization"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_MEAN"
                    crossSeriesReducer = "REDUCE_MAX"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Readiness check"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\""
                aggregation = {
                  alignmentPeriod    = "300s"
                  perSeriesAligner   = "ALIGN_FRACTION_TRUE"
                  crossSeriesReducer = "REDUCE_MEAN"
                }
              }
            }
            gaugeView = {
              upperBound = 1
            }
          }
        },
        {
          title = "DB VM CPU utilization"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_MEAN"
                    crossSeriesReducer = "REDUCE_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "DB VM memory utilization"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\" metric.labels.state=\"used\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_MEAN"
                    crossSeriesReducer = "REDUCE_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "DB VM disk utilization"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_MEAN"
                    crossSeriesReducer = "REDUCE_MEAN"
                  }
                }
              }
            }]
          }
        },
        {
          title = "DB VM uptime heartbeat"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/uptime\" resource.labels.instance_id=\"${data.google_compute_instance.db.instance_id}\""
                aggregation = {
                  alignmentPeriod    = "60s"
                  perSeriesAligner   = "ALIGN_DELTA"
                  crossSeriesReducer = "REDUCE_SUM"
                }
              }
            }
          }
        }
      ]
    }
  })
}
