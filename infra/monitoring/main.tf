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

resource "google_logging_metric" "staging_http_requests_total" {
  name        = "${var.name_prefix}_http_requests_total"
  description = "Backend HTTP access requests observed in Uvicorn access logs."
  filter      = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND jsonPayload.log=~\"HTTP/1.1.* [0-9][0-9][0-9]\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "staging_http_requests_5xx" {
  name        = "${var.name_prefix}_http_requests_5xx"
  description = "Backend HTTP 5xx responses observed in Uvicorn access logs."
  filter      = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND jsonPayload.log=~\"HTTP/1.1.* 5[0-9][0-9]\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "staging_crawler_warning" {
  name        = "${var.name_prefix}_crawler_warning"
  description = "Crawler runs that completed with the known partial-result exit code 3."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.message:\"fresh-catalog.exit=3\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "staging_crawler_failure" {
  name        = "${var.name_prefix}_crawler_failure"
  description = "Crawler container lifecycle failures, including non-zero exit and OOM."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.container_class=\"crawler\" AND (jsonPayload.event=\"die\" OR jsonPayload.event=\"oom\") AND jsonPayload.exit_code!=0"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "staging_container_stop" {
  name        = "${var.name_prefix}_container_stop_by_name"
  description = "Unexpected lifecycle stop events for service containers."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.container_class=\"service\" AND jsonPayload.event=\"die\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"

    labels {
      key         = "container_name"
      value_type  = "STRING"
      description = "Docker container name that emitted the lifecycle event."
    }
  }

  label_extractors = {
    container_name = "EXTRACT(jsonPayload.container_name)"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_logging_metric" "staging_container_oom" {
  name        = "${var.name_prefix}_container_oom"
  description = "Docker containers killed by the kernel OOM killer."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"oom\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "staging_container_disk_bytes" {
  name        = "${var.name_prefix}_container_disk_bytes"
  description = "Disk used per container: writable layer + json logs + named volumes, sampled by vota-container-disk-collector."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"container_disk\""
  # Distribution buckets are 10% wide, so percentile readings are accurate to about +/-5%. Exact bytes stay in the log entries.
  value_extractor = "EXTRACT(jsonPayload.total_bytes)"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "By"

    labels {
      key         = "container_name"
      value_type  = "STRING"
      description = "Docker container name."
    }
  }

  label_extractors = {
    container_name = "EXTRACT(jsonPayload.container_name)"
  }

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 200
      growth_factor      = 1.1
      scale              = 1048576
    }
  }
}

resource "google_logging_metric" "staging_docker_watcher_heartbeat" {
  name        = "${var.name_prefix}_docker_watcher_heartbeat"
  description = "Heartbeat emitted by the Docker lifecycle event watcher."
  filter      = "resource.type=\"gce_instance\" AND jsonPayload.event=\"heartbeat\" AND jsonPayload.watcher=\"docker-events\""

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

resource "google_monitoring_custom_service" "staging_api" {
  service_id   = "vota-staging-api"
  display_name = "${var.name_prefix} API"
  user_labels  = local.common_labels
}

resource "google_monitoring_slo" "staging_availability" {
  service             = google_monitoring_custom_service.staging_api.service_id
  slo_id              = "vota-staging-availability"
  display_name        = "${var.name_prefix} availability"
  goal                = 0.995
  rolling_period_days = 30
  user_labels         = local.common_labels

  windows_based_sli {
    window_period          = "60s"
    good_bad_metric_filter = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.labels.check_id=\"${google_monitoring_uptime_check_config.staging_health.uptime_check_id}\""
  }
}

resource "google_monitoring_slo" "staging_error_rate" {
  service             = google_monitoring_custom_service.staging_api.service_id
  slo_id              = "vota-staging-error-rate"
  display_name        = "${var.name_prefix} error rate"
  goal                = 0.995
  rolling_period_days = 30
  user_labels         = local.common_labels

  request_based_sli {
    good_total_ratio {
      total_service_filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_http_requests_total.name}\" AND resource.type=\"gce_instance\""
      bad_service_filter   = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_http_requests_5xx.name}\" AND resource.type=\"gce_instance\""
    }
  }
}

resource "google_monitoring_slo" "staging_latency" {
  service             = google_monitoring_custom_service.staging_api.service_id
  slo_id              = "vota-staging-latency"
  display_name        = "${var.name_prefix} latency under 1s"
  goal                = 0.95
  rolling_period_days = 30
  user_labels         = local.common_labels

  windows_based_sli {
    window_period = "60s"
    metric_mean_in_range {
      time_series = "metric.type=\"monitoring.googleapis.com/uptime_check/request_latency\" AND resource.type=\"uptime_url\" AND metric.labels.check_id=\"${google_monitoring_uptime_check_config.staging_health.uptime_check_id}\""
      range {
        max = 1000
      }
    }
  }
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

resource "google_monitoring_alert_policy" "staging_crawler_warning" {
  display_name          = "${var.name_prefix} crawler partial run"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Crawler exit code 3"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_crawler_warning.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }
  documentation {
    content   = "Crawler completed with exit code 3. Inspect the fresh-catalog log for timeouts or partial source failures."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_crawler_failure" {
  display_name          = "${var.name_prefix} crawler failed"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Crawler non-zero exit or OOM"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_crawler_failure.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }
  documentation {
    content   = "The crawler container exited non-zero or was OOM-killed. Inspect the lifecycle event and fresh-catalog log before rerunning."
    mime_type = "text/markdown"
  }
}

# A new log-based metric takes a few minutes to become usable by alert policies (404 otherwise).
resource "terraform_data" "container_disk_metric_ready" {
  triggers_replace = [google_logging_metric.staging_container_disk_bytes.id]

  provisioner "local-exec" {
    command = "sleep 180"
  }
}

resource "google_monitoring_alert_policy" "staging_container_disk" {
  depends_on            = [terraform_data.container_disk_metric_ready]
  display_name          = "${var.name_prefix} container disk usage high"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "A container uses more than ${var.container_disk_alert_gib} GiB of disk"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_disk_bytes.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.container_disk_alert_gib * 1073741824
      duration        = "0s"

      aggregations {
        alignment_period     = "600s"
        per_series_aligner   = "ALIGN_PERCENTILE_99"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metric.label.container_name"]
      }
    }
  }

  alert_strategy { auto_close = "3600s" }
  documentation {
    content   = "A container's writable layer, json logs and named volumes exceed ${var.container_disk_alert_gib} GiB. Open the 'Container disk usage' panels on the dashboard, then check `docker system df -v` and /var/log/vota/container-disk.jsonl on the App VM. A shared named volume is counted in every container that mounts it."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_container_stop" {
  display_name          = "${var.name_prefix} service container stopped"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Service container die event"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_stop.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }
  documentation {
    content   = "A non-crawler Docker service container stopped. Check the container event log and docker inspect state before restarting it."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_container_oom" {
  display_name          = "${var.name_prefix} container OOM"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Docker OOM event"
    condition_threshold {
      filter          = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_oom.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }
  documentation {
    content   = "A Docker container was killed by the OOM killer. Check VM memory pressure and container limits."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "staging_docker_watcher_absent" {
  display_name          = "${var.name_prefix} Docker event watcher absent"
  combiner              = "OR"
  notification_channels = local.notification_channels
  user_labels           = local.common_labels

  conditions {
    display_name = "Docker watcher heartbeat absent"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_docker_watcher_heartbeat.name}\""
      duration = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  alert_strategy { auto_close = "1800s" }
  documentation {
    content   = "The Docker lifecycle watcher has not emitted a heartbeat for five minutes. Check systemd and Ops Agent on the VM."
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
          title = "Backend container logs"
          logsPanel = {
            filter        = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND jsonPayload.container_name=\"vota-backend\""
            resourceNames = ["projects/${var.project_id}"]
          }
        },
        {
          title = "Frontend container logs"
          logsPanel = {
            filter        = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND jsonPayload.container_name=\"vota-frontend\""
            resourceNames = ["projects/${var.project_id}"]
          }
        },
        {
          title = "Crawler container logs"
          logsPanel = {
            filter        = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND (jsonPayload.container_name=\"vota-fresh-catalog\" OR jsonPayload.message:\"fresh-catalog.\")"
            resourceNames = ["projects/${var.project_id}"]
          }
        },
        {
          title = "Redis container logs"
          logsPanel = {
            filter        = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND jsonPayload.container_name=\"vota-redis\""
            resourceNames = ["projects/${var.project_id}"]
          }
        },
        {
          title = "Weaviate container logs"
          logsPanel = {
            filter        = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND jsonPayload.container_name=\"vota-weaviate\""
            resourceNames = ["projects/${var.project_id}"]
          }
        },
        {
          title = "Container disk usage (writable + logs + volumes)"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                unitOverride = "By"
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_disk_bytes.name}\""
                  aggregation = {
                    alignmentPeriod    = "300s"
                    perSeriesAligner   = "ALIGN_PERCENTILE_99"
                    crossSeriesReducer = "REDUCE_MAX"
                    groupByFields      = ["metric.label.container_name"]
                  }
                }
              }
            }]
          }
        },
        {
          title = "Container disk usage (exact samples)"
          logsPanel = {
            filter        = "resource.type=\"gce_instance\" AND resource.labels.instance_id=\"${data.google_compute_instance.app.instance_id}\" AND jsonPayload.event=\"container_disk\""
            resourceNames = ["projects/${var.project_id}"]
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
          title = "Availability SLO compliance"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "select_slo_compliance(\"${google_monitoring_slo.staging_availability.name}\")"
              }
            }
            gaugeView = {
              lowerBound = 0
              upperBound = 1
            }
          }
        },
        {
          title = "Availability SLO error budget"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "select_slo_budget(\"${google_monitoring_slo.staging_availability.name}\")"
              }
            }
            gaugeView = {
              lowerBound = 0
              upperBound = 1
            }
          }
        },
        {
          title = "Error-rate SLO compliance"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "select_slo_compliance(\"${google_monitoring_slo.staging_error_rate.name}\")"
              }
            }
            gaugeView = {
              lowerBound = 0
              upperBound = 1
            }
          }
        },
        {
          title = "Error-rate SLO error budget"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "select_slo_budget(\"${google_monitoring_slo.staging_error_rate.name}\")"
              }
            }
            gaugeView = {
              lowerBound = 0
              upperBound = 1
            }
          }
        },
        {
          title = "Latency SLO compliance"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "select_slo_compliance(\"${google_monitoring_slo.staging_latency.name}\")"
              }
            }
            gaugeView = {
              lowerBound = 0
              upperBound = 1
            }
          }
        },
        {
          title = "Latency SLO error budget"
          scorecard = {
            timeSeriesQuery = {
              timeSeriesFilter = {
                filter = "select_slo_budget(\"${google_monitoring_slo.staging_latency.name}\")"
              }
            }
            gaugeView = {
              lowerBound = 0
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
        },
        {
          title = "Docker watcher heartbeat"
          xyChart = {
            dataSets = [{
              plotType   = "LINE"
              targetAxis = "Y1"
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_docker_watcher_heartbeat.name}\""
                  aggregation = {
                    alignmentPeriod    = "60s"
                    perSeriesAligner   = "ALIGN_RATE"
                    crossSeriesReducer = "REDUCE_SUM"
                  }
                }
              }
            }]
          }
        },
        {
          title = "Crawler warnings and failures"
          xyChart = {
            dataSets = [
              {
                plotType   = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_crawler_warning.name}\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
              },
              {
                plotType   = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_crawler_failure.name}\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
              }
            ]
          }
        },
        {
          title = "Container stops and OOM"
          xyChart = {
            dataSets = [
              {
                plotType   = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_stop.name}\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
              },
              {
                plotType   = "LINE"
                targetAxis = "Y1"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"gce_instance\" metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_oom.name}\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
              }
            ]
          }
        }
      ]
    }
  })
}
