# Cảnh báo cho NHÓM VM HA. Các alert trong infra/monitoring chỉ nhắm đúng một app VM staging
# (data.google_compute_instance.app) nên không nhìn thấy nhóm này. Tên metric: request_count/https_lb_rule/
# response_code_class và backend_latencies theo tài liệu Cloud Load Balancing; cpu/utilization đã dùng ở infra/monitoring.
locals {
  vm_name_prefix        = "${var.name_prefix}-app"
  alert_channels        = concat([for c in google_monitoring_notification_channel.email : c.id], var.notification_channel_ids)
  lb_rule_filter_prefix = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/request_count\""
  group_vm_filter       = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" metric.labels.instance_name=starts_with(\"${local.vm_name_prefix}\")"
  # Số VM của MIG theo metric của Google (không đếm theo tiền tố tên). Tên MIG = ${var.name_prefix}-app.
  group_size_filter = "resource.type=\"instance_group\" metric.type=\"compute.googleapis.com/instance_group/size\" resource.labels.instance_group_name=\"${local.vm_name_prefix}\""
  # Metric của Ops Agent (memory, disk) không có nhãn tên VM: lọc theo nhãn instance của template (group = ${var.name_prefix}-app).
  group_memory_filter = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/memory/percent_used\" metric.labels.state=\"used\" metadata.user_labels.\"group\"=\"${local.vm_name_prefix}\""
  group_disk_filter   = "resource.type=\"gce_instance\" metric.type=\"agent.googleapis.com/disk/percent_used\" metric.labels.state=\"used\" metadata.user_labels.\"group\"=\"${local.vm_name_prefix}\""
}

resource "google_monitoring_notification_channel" "email" {
  for_each     = toset(var.alert_emails)
  display_name = "${var.name_prefix} HA ${each.value}"
  type         = "email"

  labels = {
    email_address = each.value
  }

  lifecycle {
    # Kênh này bị tắt/bật theo khung mute ban đêm (alert_mute.tf). Terraform không đưa enabled về true khi plan.
    ignore_changes = [enabled]
  }
}

# 1. Nhóm có ít VM đang chạy hơn mức tối thiểu (mất VM mà autohealing chưa bù kịp, hoặc template không khởi động được).
resource "google_monitoring_alert_policy" "group_below_min" {
  display_name          = "${var.name_prefix} HA: số VM dưới mức tối thiểu"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Số VM của nhóm nhỏ hơn mức tối thiểu (min_replicas) trong 5 phút"
    condition_threshold {
      filter          = local.group_size_filter
      comparison      = "COMPARISON_LT"
      threshold_value = var.min_replicas
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
      }
    }
  }

  # Metric số VM của MIG biến mất (nhóm bị xoá hẳn) thì ngưỡng "nhỏ hơn" không bao giờ kích hoạt: dùng điều kiện vắng mặt.
  conditions {
    display_name = "Không có dữ liệu số VM của nhóm trong 5 phút"
    condition_absent {
      filter   = local.group_size_filter
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
    content   = "Nhóm ${local.vm_name_prefix} có dưới ${var.min_replicas} VM chạy. Kiểm MIG, startup script, secret và Cloud NAT (docs/plan/2026-10-05-ha-load-balancing.md)."
    mime_type = "text/markdown"
  }
}

# 2. Autoscaler chạm trần VÀ tải vẫn cao: đủ hai điều kiện cùng lúc trong 15 phút (combiner AND).
#    Chỉ đếm VM thì báo cả khi 2 VM đang nhàn rỗi, vì scale-in chậm (600 s). CPU trung bình nhóm vượt cpu_target
#    nghĩa là autoscaler đã muốn scale-out nhưng không còn chỗ.
resource "google_monitoring_alert_policy" "group_at_max" {
  display_name          = "${var.name_prefix} HA: autoscaler đã đạt tối đa và CPU vẫn cao"
  combiner              = "AND"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Số VM của nhóm đã đạt tối đa (max_replicas) trong 15 phút"
    condition_threshold {
      filter = local.group_size_filter
      # Cloud Monitoring chỉ nhận COMPARISON_GT / COMPARISON_LT. Số VM là số nguyên nên "> max-0,5" tương đương ">= max".
      comparison      = "COMPARISON_GT"
      threshold_value = var.max_replicas - 0.5
      duration        = "900s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
      }
    }
  }

  conditions {
    display_name = "CPU trung bình nhóm vượt mục tiêu autoscaler (cpu_target) trong 15 phút"
    condition_threshold {
      filter          = local.group_vm_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.cpu_target
      duration        = "900s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Nhóm đã ở trần ${var.max_replicas} VM và CPU trung bình vẫn trên ${var.cpu_target} trong 15 phút: autoscaler hết chỗ co giãn. Xem dashboard `vota-ha HA: tổng quan nhóm app` (ô CPU từng VM) và `vota-ha HA: độ trễ API` (p95), cân nhắc nâng max_replicas hoặc machine_type (xem ngưỡng p95 và 5xx trước khi quyết)."
    mime_type = "text/markdown"
  }
}

# 2b. Bộ nhớ của một VM app cao. Autoscaler co giãn theo memory ở memory_target_percent (60), nên ngưỡng này cao hơn nhiều:
#     báo khi co giãn không kịp hoặc tiến trình rò rỉ bộ nhớ. REDUCE_MAX trên mọi VM: một VM vượt ngưỡng là đủ báo.
#     Điều kiện vắng mặt: không VM nào gửi memory trong 5 phút (Ops Agent dừng trên cả nhóm).
resource "google_monitoring_alert_policy" "group_memory_high" {
  display_name          = "${var.name_prefix} HA: bộ nhớ một VM app cao"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Bộ nhớ đã dùng trên một VM > ${var.alert_memory_percent}% trong 5 phút"
    condition_threshold {
      filter          = local.group_memory_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_memory_percent
      duration        = "300s"

      # Nhóm theo tên VM để incident nêu đúng VM (metadata.system_labels.name của Ops Agent).
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metadata.system_labels.name"]
      }
    }
  }

  conditions {
    display_name = "Không VM nào gửi dữ liệu bộ nhớ trong 5 phút"
    condition_absent {
      filter   = local.group_memory_filter
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
    content   = "Một VM của ${local.vm_name_prefix} dùng quá ${var.alert_memory_percent}% bộ nhớ trong 5 phút. Autoscaler co giãn theo memory ở ${var.memory_target_percent}%, nên mức này là co giãn không kịp hoặc rò rỉ bộ nhớ. Xem ô RAM từng VM trên dashboard `vota-ha HA: tài nguyên VM app`; kiểm container nào tăng (docker stats, log container_oom)."
    mime_type = "text/markdown"
  }
}

# 2c. Đĩa của một VM app đầy (từng thiết bị). Docker image, log container và volume nằm trên đĩa boot: đĩa đầy làm
#     container ghi lỗi trước khi có alert khác. Không lọc theo thiết bị: mọi thiết bị của mọi VM đều được xét.
resource "google_monitoring_alert_policy" "group_disk_high" {
  display_name          = "${var.name_prefix} HA: đĩa một VM app đầy"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Đĩa đã dùng trên một thiết bị > ${var.alert_disk_percent}% trong 5 phút"
    condition_threshold {
      filter          = local.group_disk_filter
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_disk_percent
      duration        = "300s"

      # Nhóm theo tên VM và thiết bị: incident nêu đúng VM và đĩa.
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["metadata.system_labels.name", "metric.label.device"]
      }
    }
  }

  conditions {
    display_name = "Không VM nào gửi dữ liệu đĩa trong 5 phút"
    condition_absent {
      filter   = local.group_disk_filter
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
    content   = "Một thiết bị đĩa của VM ${local.vm_name_prefix} dùng quá ${var.alert_disk_percent}% trong 5 phút. Kiểm docker system df và log container trên VM đó (vota-container-disk.jsonl), rồi mới dọn; không xoá volume của container đang chạy."
    mime_type = "text/markdown"
  }
}

# 3. Tỷ lệ 5xx của load balancer.
resource "google_monitoring_alert_policy" "lb_5xx_ratio" {
  display_name          = "${var.name_prefix} HA: tỷ lệ 5xx của load balancer"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Tỷ lệ 5xx / tổng request vượt ngưỡng trong 5 phút"
    condition_threshold {
      filter             = "${local.lb_rule_filter_prefix} metric.labels.response_code_class=500"
      denominator_filter = local.lb_rule_filter_prefix
      comparison         = "COMPARISON_GT"
      threshold_value    = var.alert_5xx_ratio
      duration           = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }

      denominator_aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Hơn ${var.alert_5xx_ratio * 100}% request qua LB trả 5xx trong 5 phút. Kiểm /health/ready từng VM (RecSys, DB), Redis, Weaviate, pgbouncer."
    mime_type = "text/markdown"
  }
}

# 4. Độ trễ backend p95.
resource "google_monitoring_alert_policy" "lb_latency" {
  display_name          = "${var.name_prefix} HA: p95 độ trễ backend cao"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "p95 độ trễ backend vượt ngưỡng trong 10 phút"
    condition_threshold {
      filter          = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/backend_latencies\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.alert_p95_latency_ms
      duration        = "600s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_95"
        cross_series_reducer = "REDUCE_MAX"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "p95 độ trễ backend vượt ${var.alert_p95_latency_ms} ms trong 10 phút (NFR hiệu năng của search)."
    mime_type = "text/markdown"
  }
}

# 5. Probe từ ngoài vào load balancer: không có VM nào sẵn sàng, hoặc cả LB ngừng phục vụ.
resource "google_monitoring_uptime_check_config" "lb_ready" {
  display_name = "${var.name_prefix} HA sẵn sàng qua LB"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/health/ready"
    port         = var.domain == "" ? 80 : 443
    use_ssl      = var.domain != ""
    validate_ssl = var.domain != ""
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.domain == "" ? google_compute_global_address.lb.address : var.domain
    }
  }
}

resource "google_monitoring_alert_policy" "lb_uptime" {
  display_name          = "${var.name_prefix} HA: LB không sẵn sàng"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Probe /health/ready qua LB thất bại"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\" AND metric.labels.check_id=\"${google_monitoring_uptime_check_config.lb_ready.uptime_check_id}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "180s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Nhiều vùng probe không nhận 200 từ /health/ready qua load balancer trong 3 phút: không còn VM sẵn sàng (RecSys, DB) hoặc LB lỗi."
    mime_type = "text/markdown"
  }
}

# 6. Redis đầy: noeviction nên hết bộ nhớ là mọi ghi (phiên, rate limit, working memory) thất bại.
resource "google_monitoring_alert_policy" "redis_memory" {
  count                 = var.create_redis ? 1 : 0
  display_name          = "${var.name_prefix} HA: Redis gần đầy bộ nhớ"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Redis dùng > 80% bộ nhớ trong 10 phút"
    condition_threshold {
      filter          = "resource.type=\"redis_instance\" metric.type=\"redis.googleapis.com/stats/memory/usage_ratio\" resource.labels.instance_id=\"projects/${var.project_id}/locations/${var.region}/instances/${google_redis_instance.shared[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "600s"

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
    content   = "Redis dùng quá 80% bộ nhớ với chính sách noeviction: phiên đăng nhập và rate limit sắp thất bại. Tăng redis_memory_gb."
    mime_type = "text/markdown"
  }
}

# CI/CD chỉ có một VM runner tự host. VM tắt thì mọi run nằm ở hàng đợi mà GitHub không báo gì
# (2026-10-12 17:44 đến 2026-10-13 02:00 UTC: 15 run kẹt `queued`). Metric uptime ngừng khi VM không chạy.
resource "google_monitoring_alert_policy" "ci_runner_down" {
  display_name          = "${var.name_prefix} CI: máy chạy CI tự host không hoạt động"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "VM ${var.ci_runner_instance_name} không gửi dữ liệu uptime trong 10 phút"
    condition_absent {
      filter   = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/uptime\" metric.labels.instance_name=\"${var.ci_runner_instance_name}\""
      duration = "600s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "VM chạy CI (GitHub Actions) không hoạt động: mọi CI/CD đứng ở hàng đợi. Bật lại VM (`gcloud compute instances start ${var.ci_runner_instance_name}`) rồi kiểm `systemctl status 'actions.runner.*'` trên VM."
    mime_type = "text/markdown"
  }
}
