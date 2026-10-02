# Staging dashboard on a 12-column mosaic grid, top to bottom:
#   Overview (SLOs) -> Backend API -> one block per VM -> Containers (App VM) -> Events -> Logs
# Every VM and every container has its own series; nothing is averaged across machines.
locals {
  dash_app_id = data.google_compute_instance.app.instance_id

  dash_vms = [for vm in [
    {
      key     = "app"
      title   = "App VM"
      name    = var.app_vm_name
      id      = data.google_compute_instance.app.instance_id
      role    = "Docker host: backend, frontend, redis, weaviate, crawler"
      enabled = true
    },
    {
      key     = "db"
      title   = "DB VM"
      name    = var.db_vm_name
      id      = data.google_compute_instance.db.instance_id
      role    = "PostgreSQL primary"
      enabled = true
    },
    {
      key     = "replica"
      title   = "DB replica VM"
      name    = var.db_replica_vm_name
      id      = local.replica_instance_id
      role    = "PostgreSQL read replica"
      enabled = local.replica_enabled
    },
  ] : vm if vm.enabled]

  dash_gce = "resource.type=\"gce_instance\""

  # Row offsets (grid units). Each VM block is 10 high, the container block 12, events 6.
  dash_vm_base         = 13
  dash_containers_base = local.dash_vm_base + 10 * length(local.dash_vms)
  dash_events_base     = local.dash_containers_base + 12
  dash_logs_base       = local.dash_events_base + 6

  dash_container_filter = "${local.dash_gce} resource.labels.instance_id=\"${local.dash_app_id}\""

  dash_header_tiles = [
    {
      xPos   = 0, yPos = 0, width = 12, height = 2
      widget = { text = { format = "MARKDOWN", content = "## Overview\nReadiness and 30-day SLOs. Gauges turn red below the SLO goal." } }
    },
    {
      xPos = 0, yPos = 2, width = 3, height = 3
      widget = {
        title = "Readiness check (pass ratio)"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = {
            filter      = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\""
            aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_FRACTION_TRUE", crossSeriesReducer = "REDUCE_MEAN" }
          } }
          gaugeView  = { lowerBound = 0, upperBound = 1 }
          thresholds = [{ value = 0.99, color = "RED", direction = "BELOW" }]
        }
      }
    },
    {
      xPos = 3, yPos = 2, width = 3, height = 3
      widget = {
        title = "Availability SLO (goal 99.5%)"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = { filter = "select_slo_compliance(\"${google_monitoring_slo.staging_availability.name}\")" } }
          gaugeView       = { lowerBound = 0, upperBound = 1 }
          thresholds      = [{ value = 0.995, color = "RED", direction = "BELOW" }]
        }
      }
    },
    {
      xPos = 6, yPos = 2, width = 3, height = 3
      widget = {
        title = "Error-rate SLO (goal 99.5%)"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = { filter = "select_slo_compliance(\"${google_monitoring_slo.staging_error_rate.name}\")" } }
          gaugeView       = { lowerBound = 0, upperBound = 1 }
          thresholds      = [{ value = 0.995, color = "RED", direction = "BELOW" }]
        }
      }
    },
    {
      xPos = 9, yPos = 2, width = 3, height = 3
      widget = {
        title = "Latency SLO (goal 95% under 1s)"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = { filter = "select_slo_compliance(\"${google_monitoring_slo.staging_latency.name}\")" } }
          gaugeView       = { lowerBound = 0, upperBound = 1 }
          thresholds      = [{ value = 0.95, color = "RED", direction = "BELOW" }]
        }
      }
    },
    {
      xPos = 0, yPos = 5, width = 3, height = 2
      widget = {
        title = "Availability error budget left"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = { filter = "select_slo_budget(\"${google_monitoring_slo.staging_availability.name}\")" } }
          thresholds      = [{ value = 0.2, color = "RED", direction = "BELOW" }]
        }
      }
    },
    {
      xPos = 3, yPos = 5, width = 3, height = 2
      widget = {
        title = "Error-rate error budget left"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = { filter = "select_slo_budget(\"${google_monitoring_slo.staging_error_rate.name}\")" } }
          thresholds      = [{ value = 0.2, color = "RED", direction = "BELOW" }]
        }
      }
    },
    {
      xPos = 6, yPos = 5, width = 3, height = 2
      widget = {
        title = "Latency error budget left"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = { filter = "select_slo_budget(\"${google_monitoring_slo.staging_latency.name}\")" } }
          thresholds      = [{ value = 0.2, color = "RED", direction = "BELOW" }]
        }
      }
    },
    {
      xPos = 9, yPos = 5, width = 3, height = 2
      widget = {
        title = "Error-level logs (last hour)"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = {
            filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_error_logs.name}\""
            aggregation = { alignmentPeriod = "3600s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM" }
          } }
          sparkChartView = { sparkChartType = "SPARK_BAR" }
          thresholds     = [{ value = 0, color = "YELLOW", direction = "ABOVE" }]
        }
      }
    },
  ]

  dash_api_tiles = [
    {
      xPos   = 0, yPos = 7, width = 12, height = 2
      widget = { text = { format = "MARKDOWN", content = "## Backend API\nTraffic from Uvicorn access logs and public probe latency per region." } }
    },
    {
      xPos = 0, yPos = 9, width = 6, height = 4
      widget = {
        title = "HTTP requests/s and 5xx/s"
        xyChart = {
          dataSets = [
            {
              plotType = "STACKED_AREA", targetAxis = "Y1", legendTemplate = "All requests/s"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_http_requests_total.name}\""
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM" }
              } }
            },
            {
              plotType = "LINE", targetAxis = "Y2", legendTemplate = "5xx/s (right axis)"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_http_requests_5xx.name}\""
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM" }
              } }
            },
          ]
          yAxis  = { scale = "LINEAR" }
          y2Axis = { scale = "LINEAR" }
        }
      }
    },
    {
      xPos = 6, yPos = 9, width = 6, height = 4
      widget = {
        title = "Readiness latency by probe region (ms)"
        xyChart = {
          dataSets = [{
            plotType = "LINE", targetAxis = "Y1", legendTemplate = "$${metric.labels.checker_location}"
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "metric.type=\"monitoring.googleapis.com/uptime_check/request_latency\" resource.type=\"uptime_url\""
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.label.checker_location"] }
            } }
          }]
          yAxis      = { scale = "LINEAR" }
          thresholds = [{ value = 1000, targetAxis = "Y1", label = "SLO 1s" }]
        }
      }
    },
  ]

  # Per VM: header, three "right now" scorecards, then CPU / memory / disk / network history.
  dash_vm_tiles = flatten([
    for i, vm in local.dash_vms : [
      {
        xPos   = 0, yPos = local.dash_vm_base + 10 * i, width = 12, height = 2
        widget = { text = { format = "MARKDOWN", content = "## ${vm.title} · ${vm.name}\n${vm.role}" } }
      },
      {
        xPos = 0, yPos = local.dash_vm_base + 10 * i + 2, width = 4, height = 3
        widget = {
          title = "${vm.title}: CPU now"
          scorecard = {
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "${local.dash_gce} metric.type=\"compute.googleapis.com/instance/cpu/utilization\" resource.labels.instance_id=\"${vm.id}\""
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN" }
            } }
            sparkChartView = { sparkChartType = "SPARK_LINE" }
            thresholds = [
              { value = 0.7, color = "YELLOW", direction = "ABOVE" },
              { value = 0.9, color = "RED", direction = "ABOVE" },
            ]
          }
        }
      },
      {
        xPos = 4, yPos = local.dash_vm_base + 10 * i + 2, width = 4, height = 3
        widget = {
          title = "${vm.title}: memory now"
          scorecard = {
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "${local.dash_gce} metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\" resource.labels.instance_id=\"${vm.id}\""
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN" }
            } }
            sparkChartView = { sparkChartType = "SPARK_LINE" }
            thresholds = [
              { value = 70, color = "YELLOW", direction = "ABOVE" },
              { value = 90, color = "RED", direction = "ABOVE" },
            ]
          }
        }
      },
      {
        xPos = 8, yPos = local.dash_vm_base + 10 * i + 2, width = 4, height = 3
        widget = {
          title = "${vm.title}: fullest disk now"
          scorecard = {
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "${local.dash_gce} metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" metric.labels.device=starts_with(\"/dev/\") resource.labels.instance_id=\"${vm.id}\""
              aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MAX" }
            } }
            sparkChartView = { sparkChartType = "SPARK_LINE" }
            thresholds = [
              { value = 80, color = "YELLOW", direction = "ABOVE" },
              { value = 90, color = "RED", direction = "ABOVE" },
            ]
          }
        }
      },
      {
        xPos = 0, yPos = local.dash_vm_base + 10 * i + 5, width = 3, height = 5
        widget = {
          title = "${vm.title}: CPU utilization"
          xyChart = {
            dataSets = [{
              plotType = "LINE", targetAxis = "Y1", legendTemplate = "CPU"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"compute.googleapis.com/instance/cpu/utilization\" resource.labels.instance_id=\"${vm.id}\""
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN" }
              } }
            }]
            yAxis = { scale = "LINEAR" }
            thresholds = [
              { value = 0.7, targetAxis = "Y1", label = "warn" },
              { value = 0.9, targetAxis = "Y1", label = "alert" },
            ]
          }
        }
      },
      {
        xPos = 3, yPos = local.dash_vm_base + 10 * i + 5, width = 3, height = 5
        widget = {
          title = "${vm.title}: memory by state"
          xyChart = {
            dataSets = [{
              plotType = "STACKED_AREA", targetAxis = "Y1", legendTemplate = "$${metric.labels.state}"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"agent.googleapis.com/memory/bytes_used\" metric.labels.state!=\"free\" resource.labels.instance_id=\"${vm.id}\""
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.label.state"] }
              } }
            }]
            yAxis = { scale = "LINEAR" }
          }
        }
      },
      {
        xPos = 6, yPos = local.dash_vm_base + 10 * i + 5, width = 3, height = 5
        widget = {
          title = "${vm.title}: disk used by device (%)"
          xyChart = {
            dataSets = [{
              plotType = "LINE", targetAxis = "Y1", legendTemplate = "$${metric.labels.device}"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" metric.labels.device=starts_with(\"/dev/\") resource.labels.instance_id=\"${vm.id}\""
                aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MAX", groupByFields = ["metric.label.device"] }
              } }
            }]
            yAxis = { scale = "LINEAR" }
            thresholds = [
              { value = 80, targetAxis = "Y1", label = "warn" },
              { value = 90, targetAxis = "Y1", label = "alert" },
            ]
          }
        }
      },
      {
        xPos = 9, yPos = local.dash_vm_base + 10 * i + 5, width = 3, height = 5
        widget = {
          title = "${vm.title}: network in / out"
          xyChart = {
            dataSets = [
              {
                plotType = "STACKED_AREA", targetAxis = "Y1", legendTemplate = "in"
                timeSeriesQuery = { timeSeriesFilter = {
                  filter      = "${local.dash_gce} metric.type=\"compute.googleapis.com/instance/network/received_bytes_count\" resource.labels.instance_id=\"${vm.id}\""
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM" }
                } }
              },
              {
                plotType = "STACKED_AREA", targetAxis = "Y1", legendTemplate = "out"
                timeSeriesQuery = { timeSeriesFilter = {
                  filter      = "${local.dash_gce} metric.type=\"compute.googleapis.com/instance/network/sent_bytes_count\" resource.labels.instance_id=\"${vm.id}\""
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM" }
                } }
              },
            ]
            yAxis = { scale = "LINEAR" }
          }
        }
      },
    ]
  ])

  # Per container on the App VM, from vota-container-stats-collector (CPU/RAM) and the disk collector.
  dash_container_tiles = [
    {
      xPos   = 0, yPos = local.dash_containers_base, width = 12, height = 2
      widget = { text = { format = "MARKDOWN", content = "## Containers on ${var.app_vm_name}\nPer-service CPU and RAM (CPU: 100% = one vCPU). Disk = writable layer + json logs + named volumes." } }
    },
    {
      xPos = 0, yPos = local.dash_containers_base + 2, width = 12, height = 5
      widget = {
        title = "Containers right now"
        timeSeriesTable = {
          metricVisualization = "NUMBER"
          dataSets = [
            {
              tableTemplate = "CPU (100% = 1 vCPU)", minAlignmentPeriod = "60s"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "metric.type=\"${google_monitoring_metric_descriptor.container["cpu_percent"].type}\" ${local.dash_container_filter}"
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.label.container_name"] }
              } }
            },
            {
              tableTemplate = "RAM used", minAlignmentPeriod = "60s"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "metric.type=\"${google_monitoring_metric_descriptor.container["memory_bytes"].type}\" ${local.dash_container_filter}"
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.label.container_name"] }
              } }
            },
            {
              tableTemplate = "RAM % of limit", minAlignmentPeriod = "60s"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "metric.type=\"${google_monitoring_metric_descriptor.container["memory_percent"].type}\" ${local.dash_container_filter}"
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.label.container_name"] }
              } }
            },
          ]
        }
      }
    },
    {
      xPos = 0, yPos = local.dash_containers_base + 7, width = 4, height = 5
      widget = {
        title = "CPU by container (100% = 1 vCPU)"
        xyChart = {
          dataSets = [{
            plotType = "STACKED_AREA", targetAxis = "Y1", legendTemplate = "$${metric.labels.container_name}"
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "metric.type=\"${google_monitoring_metric_descriptor.container["cpu_percent"].type}\" ${local.dash_container_filter}"
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.label.container_name"] }
            } }
          }]
          yAxis      = { scale = "LINEAR" }
          thresholds = [{ value = var.container_cpu_alert_percent, targetAxis = "Y1", label = "alert" }]
        }
      }
    },
    {
      xPos = 4, yPos = local.dash_containers_base + 7, width = 4, height = 5
      widget = {
        title = "RAM by container"
        xyChart = {
          dataSets = [{
            plotType = "STACKED_AREA", targetAxis = "Y1", legendTemplate = "$${metric.labels.container_name}"
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "metric.type=\"${google_monitoring_metric_descriptor.container["memory_bytes"].type}\" ${local.dash_container_filter}"
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.label.container_name"] }
            } }
          }]
          yAxis = { scale = "LINEAR" }
        }
      }
    },
    {
      xPos = 8, yPos = local.dash_containers_base + 7, width = 4, height = 5
      widget = {
        title = "Container disk usage (writable + logs + volumes)"
        xyChart = {
          dataSets = [{
            plotType = "LINE", targetAxis = "Y1", legendTemplate = "$${metric.labels.container_name}"
            timeSeriesQuery = {
              unitOverride = "By"
              timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_disk_bytes.name}\""
                aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_PERCENTILE_99", crossSeriesReducer = "REDUCE_MAX", groupByFields = ["metric.label.container_name"] }
              }
            }
          }]
          yAxis      = { scale = "LINEAR" }
          thresholds = [{ value = var.container_disk_alert_gib * 1073741824, targetAxis = "Y1", label = "alert" }]
        }
      }
    },
  ]

  dash_event_tiles = [
    {
      xPos   = 0, yPos = local.dash_events_base, width = 12, height = 2
      widget = { text = { format = "MARKDOWN", content = "## Container and crawler events\nBars are event counts per minute; an empty chart is the healthy state." } }
    },
    {
      xPos = 0, yPos = local.dash_events_base + 2, width = 4, height = 4
      widget = {
        title = "Service container stops (by container)"
        xyChart = {
          dataSets = [{
            plotType = "STACKED_BAR", targetAxis = "Y1", legendTemplate = "$${metric.labels.container_name}"
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_stop.name}\""
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.label.container_name"] }
            } }
          }]
          yAxis = { scale = "LINEAR" }
        }
      }
    },
    {
      xPos = 4, yPos = local.dash_events_base + 2, width = 3, height = 4
      widget = {
        title = "Container OOM kills"
        xyChart = {
          dataSets = [{
            plotType = "STACKED_BAR", targetAxis = "Y1", legendTemplate = "OOM"
            timeSeriesQuery = { timeSeriesFilter = {
              filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_container_oom.name}\""
              aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM" }
            } }
          }]
          yAxis = { scale = "LINEAR" }
        }
      }
    },
    {
      xPos = 7, yPos = local.dash_events_base + 2, width = 3, height = 4
      widget = {
        title = "Crawler warnings and failures"
        xyChart = {
          dataSets = [
            {
              plotType = "STACKED_BAR", targetAxis = "Y1", legendTemplate = "partial run (exit 3)"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_crawler_warning.name}\""
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM" }
              } }
            },
            {
              plotType = "STACKED_BAR", targetAxis = "Y1", legendTemplate = "failed / OOM"
              timeSeriesQuery = { timeSeriesFilter = {
                filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_crawler_failure.name}\""
                aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM" }
              } }
            },
          ]
          yAxis = { scale = "LINEAR" }
        }
      }
    },
    {
      xPos = 10, yPos = local.dash_events_base + 2, width = 2, height = 4
      widget = {
        title = "Docker watcher heartbeat (per 5 min)"
        scorecard = {
          timeSeriesQuery = { timeSeriesFilter = {
            filter      = "${local.dash_gce} metric.type=\"logging.googleapis.com/user/${google_logging_metric.staging_docker_watcher_heartbeat.name}\""
            aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_SUM", crossSeriesReducer = "REDUCE_SUM" }
          } }
          sparkChartView = { sparkChartType = "SPARK_BAR" }
          thresholds     = [{ value = 1, color = "RED", direction = "BELOW" }]
        }
      }
    },
  ]

  dash_log_panels = [
    {
      title  = "Backend container logs"
      filter = "${local.dash_container_filter} AND jsonPayload.container_name=\"vota-backend\""
    },
    {
      title  = "Frontend container logs"
      filter = "${local.dash_container_filter} AND jsonPayload.container_name=\"vota-frontend\""
    },
    {
      title  = "Crawler container logs"
      filter = "${local.dash_container_filter} AND (jsonPayload.container_name=\"vota-fresh-catalog\" OR jsonPayload.message:\"fresh-catalog.\")"
    },
    {
      title  = "Redis container logs"
      filter = "${local.dash_container_filter} AND jsonPayload.container_name=\"vota-redis\""
    },
    {
      title  = "Weaviate container logs"
      filter = "${local.dash_container_filter} AND jsonPayload.container_name=\"vota-weaviate\""
    },
    {
      title  = "Container disk usage (exact samples)"
      filter = "${local.dash_container_filter} AND jsonPayload.event=\"container_disk\""
    },
  ]

  dash_log_tiles = concat(
    [{
      xPos   = 0, yPos = local.dash_logs_base, width = 12, height = 2
      widget = { text = { format = "MARKDOWN", content = "## Logs\nNamed panels need `jsonPayload.container_name` on the log entry; verify in Logs Explorer before treating an empty panel as an ingestion failure." } }
    }],
    [for i, panel in local.dash_log_panels : {
      xPos   = 4 * (i % 3)
      yPos   = local.dash_logs_base + 2 + 5 * floor(i / 3)
      width  = 4
      height = 5
      widget = {
        title     = panel.title
        logsPanel = { filter = panel.filter, resourceNames = ["projects/${var.project_id}"] }
      }
    }],
  )
}

resource "google_monitoring_dashboard" "staging_overview" {
  dashboard_json = jsonencode({
    displayName = "${var.name_prefix} infrastructure"
    labels      = local.common_labels
    mosaicLayout = {
      columns = 12
      tiles = concat(
        local.dash_header_tiles,
        local.dash_api_tiles,
        local.dash_vm_tiles,
        local.dash_container_tiles,
        local.dash_event_tiles,
        local.dash_log_tiles,
      )
    }
  })
}
