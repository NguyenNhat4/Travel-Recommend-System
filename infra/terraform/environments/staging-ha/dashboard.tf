# Dashboard nhóm HA (MIG vota-ha-app), bố cục 12 cột, đọc từ trên xuống:
#   Tiêu đề, readiness và số VM, link log -> request và độ trễ LB -> độ trễ API theo VM và theo route -> CPU/RAM -> log.
# Độ trễ theo VM và theo route lấy từ log http.request của backend (phân phối, nên p95/p99 đúng). LB không biết VM nào
# phục vụ, nên độ trễ LB chỉ cho toàn nhóm. Chart CPU tách theo instance_name (tên VM); chart RAM chỉ có instance_id vì
# metric memory của Ops Agent không mang nhãn tên VM. Đối chiếu instance_id với tên VM bằng lệnh trong ô ghi chú.

locals {
  # Bộ lọc log dùng chung cho khung log và link Logs Explorer. Phải khớp với bộ lọc của metric độ trễ bên dưới.
  log_filter_backend   = "resource.type=\"gce_instance\" AND jsonPayload.service=\"backend\""
  log_filter_errors    = "${local.log_filter_backend} AND severity>=ERROR"
  log_filter_slow      = "${local.log_filter_backend} AND jsonPayload.event=\"http.request\" AND jsonPayload.duration_ms>1000 AND NOT jsonPayload.route:\"/stream\" AND NOT jsonPayload.route:\"/health/\""
  log_filter_container = "logName:\"docker_events\" AND NOT jsonPayload.event=\"heartbeat\" AND NOT jsonPayload.container_class=\"helper\""
  log_filter_crawler   = "jsonPayload.service=\"crawler\" AND severity>=WARNING"
  logs_url_base        = "https://console.cloud.google.com/logs/query;query="
}

# Độ trễ API của backend, mỗi dòng log http.request là một mẫu. Loại /health/* (probe) và /stream (SSE kéo dài theo LLM;
# NFR-PERF-02 đo bằng token đầu tiên, không phải tổng thời gian). Nhãn route là route mẫu (có {tham_số}), số lượng bị chặn.
resource "google_logging_metric" "ha_api_latency" {
  name   = "${var.name_prefix}_api_latency_ms"
  filter = "${local.log_filter_backend} AND jsonPayload.event=\"http.request\" AND NOT jsonPayload.route:\"/stream\" AND NOT jsonPayload.route:\"/health/\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "ms"

    labels {
      key         = "route"
      value_type  = "STRING"
      description = "Route mẫu của backend, ví dụ /api/v1/products/{product_id}"
    }
  }

  label_extractors = {
    route = "EXTRACT(jsonPayload.route)"
  }

  value_extractor = "EXTRACT(jsonPayload.duration_ms)"

  bucket_options {
    exponential_buckets {
      growth_factor      = 1.5
      num_finite_buckets = 30
      scale              = 1
    }
  }
}

resource "google_monitoring_dashboard" "ha" {
  dashboard_json = jsonencode({
    displayName = "${var.name_prefix} HA: nhóm app"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos = 0, yPos = 0, width = 12, height = 3
          widget = {
            text = {
              format  = "MARKDOWN"
              content = "## Nhóm HA `${local.vm_name_prefix}`\nNgưỡng: autoscaler CPU ${var.cpu_target} (vàng), RAM ${var.memory_target_percent}% (vàng), p95 search 250 ms NFR-PERF-01 (vàng), ngưỡng alert p95 LB ${var.alert_p95_latency_ms} ms (đỏ). Độ trễ LB gồm cả SSE; độ trễ API theo VM và route không tính SSE và /health. Đối chiếu VM ↔ MIG: `gcloud compute instance-groups managed list-instances ${local.vm_name_prefix} --region=${var.region}`."
            }
          }
        },
        {
          xPos = 0, yPos = 3, width = 3, height = 3
          widget = {
            title = "Readiness qua LB (tỷ lệ pass)"
            scorecard = {
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter      = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\" metric.labels.check_id=\"${google_monitoring_uptime_check_config.lb_ready.uptime_check_id}\""
                  aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_FRACTION_TRUE", crossSeriesReducer = "REDUCE_MEAN" }
                }
              }
              gaugeView  = { lowerBound = 0, upperBound = 1 }
              thresholds = [{ value = 0.99, color = "RED", direction = "BELOW" }]
            }
          }
        },
        {
          xPos = 3, yPos = 3, width = 3, height = 3
          widget = {
            title = "Số VM của MIG"
            scorecard = {
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter      = local.group_size_filter
                  aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MAX" }
                }
              }
              sparkChartView = { sparkChartType = "SPARK_LINE" }
            }
          }
        },
        {
          xPos = 6, yPos = 3, width = 6, height = 3
          widget = {
            text = {
              format  = "MARKDOWN"
              content = "**Log (khung ở cuối trang, hoặc mở đầy đủ trong Logs Explorer):**\n- [Backend, mọi VM](${local.logs_url_base}${replace(urlencode(local.log_filter_backend), "+", "%20")}?project=${var.project_id}) — cột `labels.\"compute.googleapis.com/resource_name\"` là tên VM\n- [Lỗi backend (ERROR)](${local.logs_url_base}${replace(urlencode(local.log_filter_errors), "+", "%20")}?project=${var.project_id})\n- [Request chậm > 1 s](${local.logs_url_base}${replace(urlencode(local.log_filter_slow), "+", "%20")}?project=${var.project_id})"
            }
          }
        },
        {
          xPos = 0, yPos = 6, width = 6, height = 4
          widget = {
            title = "Request theo mã trạng thái (LB, mỗi phút)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/request_count\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.labels.response_code_class"] }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 6, width = 6, height = 4
          widget = {
            title = "Độ trễ LB (ms): p95 và p99, cả nhóm, gồm SSE"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/backend_latencies\""
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MAX" }
                    }
                  }
                  plotType       = "LINE"
                  legendTemplate = "p95"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/backend_latencies\""
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_99", crossSeriesReducer = "REDUCE_MAX" }
                    }
                  }
                  plotType       = "LINE"
                  legendTemplate = "p99"
                },
              ]
              thresholds = [
                { label = "NFR-PERF-01: 250 ms", value = 250, targetAxis = "Y1" },
                { label = "ngưỡng alert p95", value = var.alert_p95_latency_ms, targetAxis = "Y1" },
              ]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 0, yPos = 10, width = 6, height = 4
          widget = {
            title = "p95 API theo VM (ms, không SSE, không health)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ha_api_latency.name}\" resource.type=\"gce_instance\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["resource.labels.instance_id"] }
                  }
                }
                plotType = "LINE"
              }]
              thresholds = [{ label = "NFR search p95 250 ms", value = 250, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR", label = "ms" }
            }
          }
        },
        {
          xPos = 6, yPos = 10, width = 6, height = 4
          widget = {
            title = "p99 API theo VM (ms, không SSE, không health)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ha_api_latency.name}\" resource.type=\"gce_instance\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_99", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["resource.labels.instance_id"] }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR", label = "ms" }
            }
          }
        },
        {
          xPos = 0, yPos = 14, width = 6, height = 4
          widget = {
            title = "p95 API theo route (ms): search cần ≤ 250, chi tiết sản phẩm ≤ 100"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ha_api_latency.name}\" resource.type=\"gce_instance\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.route"] }
                  }
                }
                plotType = "LINE"
              }]
              thresholds = [{ label = "NFR search 250 ms", value = 250, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR", label = "ms" }
            }
          }
        },
        {
          xPos = 6, yPos = 14, width = 6, height = 4
          widget = {
            title = "CPU từng VM của nhóm (tên VM)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = local.group_vm_filter
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.instance_name"] }
                  }
                }
                plotType = "LINE"
              }]
              thresholds = [{ label = "cpu_target (autoscaler)", value = var.cpu_target, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 0, yPos = 18, width = 6, height = 4
          widget = {
            title = "RAM đã dùng từng VM (instance_id, %)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["resource.labels.instance_id"] }
                  }
                }
                plotType = "LINE"
              }]
              thresholds = [{ label = "memory_target (autoscaler)", value = var.memory_target_percent, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        # Container: collector của VM (vota-container-stats-collector) gắn nhãn container_name và instance_id.
        {
          xPos = 6, yPos = 18, width = 6, height = 4
          widget = {
            title = "CPU từng container (100 = một vCPU)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"custom.googleapis.com/vota/container/cpu_percent\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.container_name", "resource.labels.instance_id"] }
                  }
                }
                plotType = "LINE"
              }]
              thresholds = [{ label = "ngưỡng container (190 = 95% của 2 vCPU)", value = 190, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 0, yPos = 22, width = 6, height = 4
          widget = {
            title = "RAM từng container (bytes)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"custom.googleapis.com/vota/container/memory_bytes\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.container_name", "resource.labels.instance_id"] }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { label = "bytes", scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 22, width = 6, height = 4
          widget = {
            text = {
              format  = "MARKDOWN"
              content = "**Cách đọc độ trễ**\n- *LB*: đo tại load balancer, gồm cả SSE của trợ lý.\n- *API theo VM / theo route*: đo trong backend (`duration_ms` của log `http.request`), không tính `/health/*` và `/stream`.\n- Số mẫu thấp thì p99 dao động mạnh; đọc cùng ô request.\n- Ngưỡng: search p95 ≤ 250 ms, chi tiết sản phẩm ≤ 100 ms (NFR-PERF-01)."
            }
          }
        },
        {
          xPos = 0, yPos = 26, width = 6, height = 5
          widget = {
            title = "Lỗi backend (ERROR), mọi VM"
            logsPanel = {
              filter        = local.log_filter_errors
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        {
          xPos = 6, yPos = 26, width = 6, height = 5
          widget = {
            title = "Request chậm > 1 s (backend, mọi VM)"
            logsPanel = {
              filter        = local.log_filter_slow
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        {
          xPos = 0, yPos = 31, width = 6, height = 5
          widget = {
            title = "Container die/OOM (watcher, không tính helper)"
            logsPanel = {
              filter        = local.log_filter_container
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        {
          xPos = 6, yPos = 31, width = 6, height = 5
          widget = {
            title = "Lượt cào (crawler), cảnh báo trở lên"
            logsPanel = {
              filter        = local.log_filter_crawler
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
      ]
    }
  })
}
