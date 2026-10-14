# Dashboard cảnh báo: mỗi ô là lịch sử incident của một alert policy (widget alertChart), tiêu đề ghi tên và ngưỡng.
# Ô của policy có count (DB, máy cào, Redis) chỉ hiện khi policy đó tồn tại: try() bỏ qua index khi count = 0.
# Cảnh báo staging cũ (vota-staging:) chưa nằm trong Terraform nên không có ở đây; xem infra/monitoring/README.md.

locals {
  alert_panels = [
    { title = "App: số VM dưới ${var.min_replicas} (5 phút)", name = google_monitoring_alert_policy.group_below_min.name },
    { title = "App: autoscaler tối đa và CPU cao (15 phút)", name = google_monitoring_alert_policy.group_at_max.name },
    { title = "App: RAM một VM > ${var.alert_memory_percent}% (5 phút)", name = google_monitoring_alert_policy.group_memory_high.name },
    { title = "App: đĩa một VM > ${var.alert_disk_percent}% (5 phút)", name = google_monitoring_alert_policy.group_disk_high.name },
    { title = "LB: không sẵn sàng (/health/ready)", name = google_monitoring_alert_policy.lb_uptime.name },
    { title = "LB: tỷ lệ 5xx > ${var.alert_5xx_ratio * 100}% (5 phút)", name = google_monitoring_alert_policy.lb_5xx_ratio.name },
    { title = "LB: p95 độ trễ > ${var.alert_p95_latency_ms} ms (10 phút)", name = google_monitoring_alert_policy.lb_latency.name },
    { title = "Redis: bộ nhớ > 80% (10 phút)", name = try(google_monitoring_alert_policy.redis_memory[0].name, "") },
    { title = "DB: không còn replica (5 phút)", name = try(google_monitoring_alert_policy.patroni_no_replica[0].name, "") },
    { title = "DB: không có node chính (2 phút)", name = try(google_monitoring_alert_policy.patroni_no_leader[0].name, "") },
    { title = "DB: probe Patroni không gửi dữ liệu (5 phút)", name = try(google_monitoring_alert_policy.patroni_probe_absent[0].name, "") },
    { title = "DB: RAM một node > ${var.alert_db_memory_percent}% (10 phút)", name = try(google_monitoring_alert_policy.db_memory_high[0].name, "") },
    { title = "DB: đĩa một node > ${var.alert_db_disk_percent}% (5 phút)", name = try(google_monitoring_alert_policy.db_disk_high[0].name, "") },
    { title = "DB: CPU một node > ${var.alert_db_cpu_percent}% (15 phút)", name = try(google_monitoring_alert_policy.db_cpu_high[0].name, "") },
    { title = "Máy cào: không có dòng catalog.due (60 phút)", name = try(google_monitoring_alert_policy.crawler_silent[0].name, "") },
    { title = "Máy cào: lượt cào thất bại (status=failed)", name = try(google_monitoring_alert_policy.crawler_run_failed[0].name, "") },
    { title = "Máy cào: RAM > ${var.alert_crawler_memory_percent}% (10 phút)", name = try(google_monitoring_alert_policy.crawler_memory_high[0].name, "") },
    { title = "Máy cào: đĩa > ${var.alert_crawler_disk_percent}% (5 phút)", name = try(google_monitoring_alert_policy.crawler_disk_high[0].name, "") },
    { title = "Máy cào: CPU > ${var.alert_crawler_cpu_percent}% liên tục ${var.alert_crawler_cpu_minutes} phút", name = try(google_monitoring_alert_policy.crawler_cpu_sustained[0].name, "") },
    { title = "CI: máy chạy CI không hoạt động (10 phút)", name = google_monitoring_alert_policy.ci_runner_down.name },
    { title = "Mute: job bật/tắt kênh cảnh báo lỗi", name = google_monitoring_alert_policy.mute_job_failed.name },
  ]

  # Chỉ giữ policy thật sự tồn tại (count = 1); xếp hai ô mỗi hàng, cao 3 đơn vị, từ hàng 3.
  alert_panels_shown = [for p in local.alert_panels : p if p.name != ""]
}

resource "google_monitoring_dashboard" "ha_alerts" {
  dashboard_json = jsonencode({
    displayName = "${local.dashboard_prefix}: cảnh báo"
    mosaicLayout = {
      columns = 12
      tiles = concat(
        [
          {
            xPos = 0, yPos = 0, width = 12, height = 3
            widget = {
              text = {
                format  = "MARKDOWN"
                content = "## Cảnh báo nhóm HA `${local.vm_name_prefix}`, DB và máy cào\nMỗi ô là lịch sử incident của một policy; điều kiện, kênh và hướng dẫn xử lý nằm trong policy ([danh sách](https://console.cloud.google.com/monitoring/alerting?project=${var.project_id})).\n**Khung mute 23:55–08:35 (giờ Việt Nam):** alert HA không gửi email; incident vẫn ghi nhận, nên ô vẫn hiện. Alert job mute lỗi luôn gửi email.\nChưa có ở đây: 8 cảnh báo staging cũ `vota-staging:`, vì chưa đưa vào Terraform."
              }
            }
          },
        ],
        [for i, p in local.alert_panels_shown : {
          xPos   = (i % 2) * 6
          yPos   = 3 + floor(i / 2) * 3
          width  = 6
          height = 3
          widget = {
            title      = p.title
            alertChart = { name = p.name }
          }
        }],
      )
    }
  })
}
