# Năm dashboard HA, tách theo việc cần làm để mỗi trang tải ít truy vấn (trước đây một trang có 21 ô, 4 khung log và 4 biểu
# đồ phân vị, tải cùng lúc):
#   - tổng quan nhóm app: sẵn sàng LB, số VM, request, CPU từng VM app
#   - độ trễ API: p95/p99 theo VM và theo route, LB
#   - tài nguyên VM app: RAM, đĩa, CPU và RAM container theo VM
#   - DB và máy cào: CPU, RAM, đĩa của pg-a, pg-b, pg-w và máy cào
#   - nhật ký: bốn khung log (chỉ dashboard này có khung log)
# Tên VM lấy từ metadata.system_labels.name của Ops Agent và cAdvisor-style collector (metric container), nên mọi ô hiển thị
# tên VM, không còn mã instance. Metric CPU của Compute Engine có sẵn nhãn instance_name.

locals {
  # Bộ lọc log dùng chung cho khung log và link Logs Explorer. Phải khớp với bộ lọc của metric độ trễ bên dưới.
  log_filter_backend   = "resource.type=\"gce_instance\" AND jsonPayload.service=\"backend\""
  log_filter_errors    = "${local.log_filter_backend} AND severity>=ERROR"
  log_filter_slow      = "${local.log_filter_backend} AND jsonPayload.event=\"http.request\" AND jsonPayload.duration_ms>1000 AND NOT jsonPayload.route:\"/stream\" AND NOT jsonPayload.route:\"/health/\""
  log_filter_container = "logName:\"docker_events\" AND NOT jsonPayload.event=\"heartbeat\" AND NOT jsonPayload.container_class=\"helper\""
  log_filter_crawler   = "jsonPayload.service=\"crawler\" AND severity>=WARNING"
  logs_url_base        = "https://console.cloud.google.com/logs/query;query="

  # Nhóm theo tên VM (metadata của Ops Agent và collector). Metric per-VM dùng 300 giây để ít điểm hơn; metric LB và
  # scorecard giữ 60 giây.
  group_by_vm      = ["metadata.system_labels.name"]
  align_per_vm     = "300s"
  align_lb         = "60s"
  dashboard_prefix = "${var.name_prefix} HA"
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

# 1. Tổng quan nhóm app: trang mở đầu, chỉ có ô nhẹ.
resource "google_monitoring_dashboard" "ha" {
  dashboard_json = jsonencode({
    displayName = "${local.dashboard_prefix}: tổng quan nhóm app"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 12, height = 3
          widget = {
            text = {
              format  = "MARKDOWN"
              style   = {}
              content = "## Nhóm HA `${local.vm_name_prefix}`\nTrang tổng quan. Chi tiết: **độ trễ API**, **tài nguyên VM app**, **DB và máy cào**, **nhật ký** (các dashboard `${local.dashboard_prefix}: …`).\nNgưỡng: autoscaler CPU ${var.cpu_target} (vàng); alert p95 LB ${var.alert_p95_latency_ms} ms (đỏ). Đối chiếu VM ↔ MIG: `gcloud compute instance-groups managed list-instances ${local.vm_name_prefix} --region=${var.region}`."
            }
          }
        },
        {
          yPos = 3, width = 3, height = 3
          widget = {
            title = "Sẵn sàng qua LB (tỷ lệ đạt)"
            scorecard = {
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter      = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" resource.type=\"uptime_url\" metric.labels.check_id=\"${google_monitoring_uptime_check_config.lb_ready.uptime_check_id}\""
                  aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_FRACTION_TRUE", crossSeriesReducer = "REDUCE_MEAN" }
                }
              }
              gaugeView  = { upperBound = 1 }
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
              style   = {}
              content = "**Log (mở trong Logs Explorer; khung log nằm ở dashboard `${local.dashboard_prefix}: nhật ký`):**\n- [Backend, mọi VM](${local.logs_url_base}${replace(urlencode(local.log_filter_backend), "+", "%20")}?project=${var.project_id}) — cột `labels.\"compute.googleapis.com/resource_name\"` là tên VM\n- [Lỗi backend (ERROR)](${local.logs_url_base}${replace(urlencode(local.log_filter_errors), "+", "%20")}?project=${var.project_id})"
            }
          }
        },
        {
          yPos = 6, width = 6, height = 4
          widget = {
            title = "Request theo mã trạng thái (LB, mỗi phút)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/request_count\""
                    aggregation = { alignmentPeriod = local.align_lb, perSeriesAligner = "ALIGN_RATE", crossSeriesReducer = "REDUCE_SUM", groupByFields = ["metric.labels.response_code_class"] }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 6, width = 6, height = 4
          widget = {
            title = "CPU từng VM app (tên VM, 1 = 100%)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = local.group_vm_filter
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.instance_name"] }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              thresholds = [{ label = "cpu_target (autoscaler)", value = var.cpu_target, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
      ]
    }
  })
}

# 2. Độ trễ API: các biểu đồ phân vị (p95, p99) nằm riêng để không kéo chậm trang tổng quan.
resource "google_monitoring_dashboard" "ha_latency" {
  dashboard_json = jsonencode({
    displayName = "${local.dashboard_prefix}: độ trễ API"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 12, height = 3
          widget = {
            text = {
              format  = "MARKDOWN"
              style   = {}
              content = "**Cách đọc độ trễ**\n- *API theo VM / theo route*: đo trong backend (`duration_ms` của log `http.request`), không tính `/health/*` và `/stream`. Tên VM là nhóm của biểu đồ.\n- *LB*: đo tại load balancer, gồm cả SSE của trợ lý; LB không biết VM nào phục vụ nên chỉ có cho cả nhóm.\n- Số mẫu thấp thì p99 dao động mạnh; đọc cùng ô request ở tổng quan.\n- Ngưỡng: search p95 ≤ 250 ms, chi tiết sản phẩm ≤ 100 ms (NFR-PERF-01)."
            }
          }
        },
        {
          yPos = 3, width = 6, height = 4
          widget = {
            title = "p95 API theo VM (ms, bỏ SSE và health)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ha_api_latency.name}\" resource.type=\"gce_instance\""
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MEAN", groupByFields = local.group_by_vm }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              thresholds = [{ label = "NFR search p95 250 ms", value = 250, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR", label = "ms" }
            }
          }
        },
        {
          xPos = 6, yPos = 3, width = 6, height = 4
          widget = {
            title = "p99 API theo VM (ms, bỏ SSE và health)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ha_api_latency.name}\" resource.type=\"gce_instance\""
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_PERCENTILE_99", crossSeriesReducer = "REDUCE_MEAN", groupByFields = local.group_by_vm }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              yAxis = { scale = "LINEAR", label = "ms" }
            }
          }
        },
        {
          yPos = 7, width = 6, height = 4
          widget = {
            title = "p95 API theo route (ms): search cần ≤ 250, chi tiết sản phẩm ≤ 100"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.ha_api_latency.name}\" resource.type=\"gce_instance\""
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.route"] }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              thresholds = [{ label = "NFR search 250 ms", value = 250, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR", label = "ms" }
            }
          }
        },
        {
          xPos = 6, yPos = 7, width = 6, height = 4
          widget = {
            title = "Độ trễ LB (ms): p95 và p99, cả nhóm, gồm SSE"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/backend_latencies\""
                      aggregation = { alignmentPeriod = local.align_lb, perSeriesAligner = "ALIGN_PERCENTILE_95", crossSeriesReducer = "REDUCE_MAX" }
                    }
                  }
                  targetAxis     = "Y1"
                  plotType       = "LINE"
                  legendTemplate = "p95"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/backend_latencies\""
                      aggregation = { alignmentPeriod = local.align_lb, perSeriesAligner = "ALIGN_PERCENTILE_99", crossSeriesReducer = "REDUCE_MAX" }
                    }
                  }
                  targetAxis     = "Y1"
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
      ]
    }
  })
}

# 3. Tài nguyên VM app: RAM, đĩa, CPU và RAM container, theo tên VM.
resource "google_monitoring_dashboard" "ha_vm_app" {
  dashboard_json = jsonencode({
    displayName = "${local.dashboard_prefix}: tài nguyên VM app"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 12, height = 2
          widget = {
            text = {
              format  = "MARKDOWN"
              style   = {}
              content = "VM app thuộc MIG `${local.vm_name_prefix}`, nhóm theo tên VM. Ngưỡng vẽ theo alert: RAM ${var.memory_target_percent}% (mục tiêu autoscaler), đĩa ${var.alert_disk_percent}%, container 190 (95% của 2 vCPU). Biểu đồ RAM theo trạng thái nằm cuối trang vì có nhiều đường nhất."
            }
          }
        },
        {
          yPos = 2, width = 6, height = 4
          widget = {
            title = "RAM đã dùng từng VM app (tên VM, %)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = local.group_memory_filter
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = local.group_by_vm }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              thresholds = [{ label = "memory_target (autoscaler)", value = var.memory_target_percent, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 2, width = 6, height = 4
          widget = {
            title = "Đĩa đã dùng từng VM app (tên VM · thiết bị, %)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = local.group_disk_filter
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = concat(local.group_by_vm, ["metric.labels.device"]) }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              thresholds = [{ label = "ngưỡng đĩa VM app (${var.alert_disk_percent}%)", value = var.alert_disk_percent, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos = 6, width = 6, height = 4
          widget = {
            title = "CPU từng container (tên VM · container, 100 = một vCPU)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"custom.googleapis.com/vota/container/cpu_percent\""
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = concat(local.group_by_vm, ["metric.labels.container_name"]) }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              thresholds = [{ label = "ngưỡng container (190 = 95% của 2 vCPU)", value = 190, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 6, width = 6, height = 4
          widget = {
            title = "RAM từng container (tên VM · container, bytes)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"custom.googleapis.com/vota/container/memory_bytes\""
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = concat(local.group_by_vm, ["metric.labels.container_name"]) }
                  }
                }
                targetAxis = "Y1"
                plotType   = "LINE"
              }]
              yAxis = { label = "bytes", scale = "LINEAR" }
            }
          }
        },
        # Chi tiết: RAM theo trạng thái (used, cached, buffered...). Nhiều đường nhất trang, nên đặt cuối.
        {
          yPos = 10, width = 12, height = 5
          widget = {
            title = "RAM theo trạng thái từng VM app (tên VM · trạng thái, %)"
            xyChart = {
              dataSets = [{
                targetAxis = "Y1"
                plotType   = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter      = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state!=\"free\" metadata.user_labels.\"group\"=\"${local.vm_name_prefix}\""
                    aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = concat(local.group_by_vm, ["metric.labels.state"]) }
                  }
                }
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
      ]
    }
  })
}

# 4. DB và máy cào: chỉ các VM đó, theo tên. pg-w không có RAM và đĩa (không có Ops Agent), nên chỉ có CPU.
resource "google_monitoring_dashboard" "ha_db_crawler" {
  dashboard_json = jsonencode({
    displayName = "${local.dashboard_prefix}: DB và máy cào"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 12, height = 3
          widget = {
            text = {
              format  = "MARKDOWN"
              style   = {}
              content = "**Cụm DB** (pg-a, pg-b là node dữ liệu; pg-w là witness etcd, chỉ có CPU vì không cài Ops Agent) và **máy cào** (`${local.crawler_name}`). Ngưỡng alert: node DB RAM ${var.alert_db_memory_percent}%, đĩa ${var.alert_db_disk_percent}%, CPU ${var.alert_db_cpu_percent}%; máy cào RAM ${var.alert_crawler_memory_percent}%, đĩa ${var.alert_crawler_disk_percent}%, CPU ${var.alert_crawler_cpu_percent}% liên tục ${var.alert_crawler_cpu_minutes} phút. Lượt cào chạy quanh 09:00 giờ Việt Nam và chạm gần 100% CPU khoảng 1 giờ."
            }
          }
        },
        {
          yPos = 3, width = 6, height = 4
          widget = {
            title = "CPU các node DB và máy cào (tên VM, 1 = 100%)"
            xyChart = {
              dataSets = [
                {
                  targetAxis = "Y1"
                  plotType   = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.db_cpu_filter
                      aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.instance_name"] }
                    }
                  }
                },
                {
                  targetAxis = "Y1"
                  plotType   = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.crawler_cpu_filter
                      aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = ["metric.labels.instance_name"] }
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
          xPos = 6, yPos = 3, width = 6, height = 4
          widget = {
            title = "RAM các node DB và máy cào (tên VM, %)"
            xyChart = {
              dataSets = [
                {
                  targetAxis = "Y1"
                  plotType   = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.db_memory_filter
                      aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = local.group_by_vm }
                    }
                  }
                },
                {
                  targetAxis = "Y1"
                  plotType   = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.crawler_memory_filter
                      aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = local.group_by_vm }
                    }
                  }
                },
              ]
              thresholds = [{ label = "ngưỡng RAM node DB (${var.alert_db_memory_percent}%)", value = var.alert_db_memory_percent, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos = 7, width = 6, height = 4
          widget = {
            title = "Đĩa các node DB và máy cào (tên VM · thiết bị, %)"
            xyChart = {
              dataSets = [
                {
                  targetAxis = "Y1"
                  plotType   = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.db_disk_filter
                      aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = concat(local.group_by_vm, ["metric.labels.device"]) }
                    }
                  }
                },
                {
                  targetAxis = "Y1"
                  plotType   = "LINE"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter      = local.crawler_disk_filter
                      aggregation = { alignmentPeriod = local.align_per_vm, perSeriesAligner = "ALIGN_MEAN", crossSeriesReducer = "REDUCE_MEAN", groupByFields = concat(local.group_by_vm, ["metric.labels.device"]) }
                    }
                  }
                },
              ]
              thresholds = [{ label = "ngưỡng đĩa node DB và máy cào (${var.alert_db_disk_percent}%)", value = var.alert_db_disk_percent, targetAxis = "Y1" }]
              yAxis      = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos = 6, yPos = 7, width = 6, height = 4
          widget = {
            text = {
              format  = "MARKDOWN"
              style   = {}
              content = "**Đọc nhanh**\n- Đĩa máy cào: đỉnh 7 ngày khoảng 78%, sát ngưỡng ${var.alert_crawler_disk_percent}%. Mỗi image crawler khoảng 3 GB trên đĩa 15 GB.\n- RAM và đĩa không có cho pg-w. CPU của pg-w vẫn có.\n- Chi tiết alert và việc cần làm: `docs/guide/van-hanh-db-patroni.md` §8, `docs/guide/van-hanh-crawler-db-noi-bo.md` §2."
            }
          }
        },
      ]
    }
  })
}

# 5. Nhật ký: bốn khung log, tất cả VM. Tách riêng vì khung log truy vấn lại mỗi lần mở trang.
resource "google_monitoring_dashboard" "ha_logs" {
  dashboard_json = jsonencode({
    displayName = "${local.dashboard_prefix}: nhật ký"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width = 12, height = 2
          widget = {
            text = {
              format  = "MARKDOWN"
              style   = {}
              content = "Bốn khung log, mọi VM. Cột `labels.\"compute.googleapis.com/resource_name\"` trong Logs Explorer là tên VM. Các khung đã lọc sẵn giống link trong dashboard tổng quan."
            }
          }
        },
        {
          yPos = 2, width = 6, height = 5
          widget = {
            title = "Lỗi backend (mức ERROR), mọi VM"
            logsPanel = {
              filter        = local.log_filter_errors
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        {
          xPos = 6, yPos = 2, width = 6, height = 5
          widget = {
            title = "Request chậm > 1 s (backend, mọi VM)"
            logsPanel = {
              filter        = local.log_filter_slow
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        {
          yPos = 7, width = 6, height = 5
          widget = {
            title = "Container dừng đột ngột / OOM (watcher, không tính helper)"
            logsPanel = {
              filter        = local.log_filter_container
              resourceNames = ["projects/${var.project_id}"]
            }
          }
        },
        {
          xPos = 6, yPos = 7, width = 6, height = 5
          widget = {
            title = "Lượt cào (job cào), từ mức cảnh báo trở lên"
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
