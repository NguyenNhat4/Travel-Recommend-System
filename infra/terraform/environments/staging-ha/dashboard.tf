# Dashboard nhóm HA (MIG vota-ha-app), bố cục 12 cột, đọc từ trên xuống:
#   Tiêu đề, readiness và số VM, link log -> request và độ trễ LB -> độ trễ API theo VM và theo route -> CPU/RAM -> log
#   -> CPU của node DB và máy cào, đĩa theo từng VM (xem cuối file).
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
              content = "## Nhóm HA `${local.vm_name_prefix}`\nNgưỡng: autoscaler CPU ${var.cpu_target} (vàng), RAM ${var.memory_target_percent}% (vàng), p95 search 250 ms NFR-PERF-01 (vàng), ngưỡng alert p95 LB ${var.alert_p95_latency_ms} ms (đỏ). Độ trễ LB gồm cả SSE; độ trễ API theo VM và route không tính SSE và /health. Đối chiếu VM ↔ MIG: `gcloud compute instance-groups managed list-instances ${local.vm_name_prefix} --region=${var.region}`. Mã instance (ô RAM và đĩa) đối chiếu với tên VM bằng `gcloud compute instances list --project=${var.project_id} --format='table(name,id,zone)'`."
            }
          }
        },
        {
          xPos = 0, yPos = 3, width = 3, height = 3
          widget = {
            title = "Sẵn sàng qua LB (tỷ lệ đạt)"
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
            title = "p95 API theo VM (ms, bỏ SSE và health)"
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
            title = "p99 API theo VM (ms, bỏ SSE và health)"
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
            title = "RAM đã dùng từng VM (mã instance, %)"
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
            title = "Lỗi backend (mức ERROR), mọi VM"
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
            title = "Container dừng đột ngột / OOM (watcher, không tính helper)"
            logsPanel = {
              filter        = local.log_filter_container
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        {
          xPos = 6, yPos = 31, width = 6, height = 5
          widget = {
            title = "Lượt cào (job cào), từ mức cảnh báo trở lên"
            logsPanel = {
              filter        = local.log_filter_crawler
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        # RAM tách theo state của từng VM (used, cached, buffered...). Đường theo cặp (VM, state), không xếp chồng
        # các VM lên nhau; VM đã xoá thì đường của nó dừng lại. Dùng instance_id vì metric Ops Agent không có instance_name.
        {
          xPos = 0, yPos = 36, width = 12, height = 5
          widget = {
            title = "RAM theo trạng thái từng VM (mã instance, %)"
            xyChart = {
              dataSets = [{
                plotType       = "LINE"
                legendTemplate = "$${resource.labels.instance_id} · $${metric.labels.state}"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state!=\"free\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["resource.labels.instance_id", "metric.labels.state"] }
                  }
                }
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        # Hàng cuối: CPU của node DB và máy cào tách theo tên VM (CPU đo từ hypervisor, có cả pg-w), và đĩa của mọi VM có
        # Ops Agent tách theo mã instance và thiết bị. Ngưỡng vẽ theo đúng alert: DB 70%, máy cào 95% kéo dài, đĩa 80%.
        {
          xPos = 0, yPos = 41, width = 6, height = 4
          widget = {
            title = "CPU từng node DB và máy cào (tên VM, 1 = 100%)"
            xyChart = {
              dataSets = [
                {
                  plotType = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.db_cpu_filter
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.instance_name"] }
                    }
                  }
                },
                {
                  plotType = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.crawler_cpu_filter
                      aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.instance_name"] }
                    }
                  }
                },
              ]
              thresholds = [
                { label = "ngưỡng CPU node DB (${var.alert_db_cpu_percent}%)", value = var.alert_db_cpu_percent / 100, targetAxis = "Y1" },
                { label = "ngưỡng CPU máy cào (${var.alert_crawler_cpu_percent}%, kéo dài)", value = var.alert_crawler_cpu_percent / 100, targetAxis = "Y1" },
              ]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 41, width = 6, height = 4
          widget = {
            title = "Đĩa đã dùng từng VM (mã instance · thiết bị, %)"
            xyChart = {
              dataSets = [{
                plotType       = "LINE"
                legendTemplate = "$${resource.labels.instance_id} · $${metric.labels.device}"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\""
                    aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["resource.labels.instance_id", "metric.labels.device"] }
                  }
                }
              }]
              thresholds = [{ label = "ngưỡng đĩa node DB và máy cào (${var.alert_db_disk_percent}%)", value = var.alert_db_disk_percent, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
      ]
    }
  })
}
