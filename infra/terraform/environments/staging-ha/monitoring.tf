# Cảnh báo cho NHÓM VM HA. Các alert trong infra/monitoring chỉ nhắm đúng một app VM staging
# (data.google_compute_instance.app) nên không nhìn thấy nhóm này. Tên metric: request_count/https_lb_rule/
# response_code_class và backend_latencies theo tài liệu Cloud Load Balancing; cpu/utilization đã dùng ở infra/monitoring.
locals {
  vm_name_prefix        = "${var.name_prefix}-app"
  alert_channels        = concat([for c in google_monitoring_notification_channel.email : c.id], var.notification_channel_ids)
  lb_rule_filter_prefix = "resource.type=\"https_lb_rule\" metric.type=\"loadbalancing.googleapis.com/https/request_count\""
  group_vm_filter       = "resource.type=\"gce_instance\" metric.type=\"compute.googleapis.com/instance/cpu/utilization\" metric.labels.instance_name=starts_with(\"${local.vm_name_prefix}\")"
}

resource "google_monitoring_notification_channel" "email" {
  for_each     = toset(var.alert_emails)
  display_name = "${var.name_prefix} HA ${each.value}"
  type         = "email"

  labels = {
    email_address = each.value
  }
}

# 1. Nhóm có ít VM đang chạy hơn mức tối thiểu (mất VM mà autohealing chưa bù kịp, hoặc template không khởi động được).
resource "google_monitoring_alert_policy" "group_below_min" {
  display_name          = "${var.name_prefix} HA: số VM dưới mức tối thiểu"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "VM đang báo CPU < min_replicas trong 5 phút"
    condition_threshold {
      filter          = local.group_vm_filter
      comparison      = "COMPARISON_LT"
      threshold_value = var.min_replicas
      duration        = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_COUNT"
      }
    }
  }

  # Không còn VM nào báo metric (nhóm bị xoá sạch) thì ngưỡng "nhỏ hơn" không bao giờ kích hoạt: dùng điều kiện vắng mặt.
  conditions {
    display_name = "Không VM nào báo metric trong 5 phút"
    condition_absent {
      filter   = local.group_vm_filter
      duration = "300s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_COUNT"
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

# 2. Autoscaler chạm trần: không còn chỗ co giãn thêm trong khi tải vẫn cao.
resource "google_monitoring_alert_policy" "group_at_max" {
  display_name          = "${var.name_prefix} HA: autoscaler chạm max_replicas"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "Số VM bằng max_replicas trong 15 phút"
    condition_threshold {
      filter          = local.group_vm_filter
      comparison      = "COMPARISON_GE"
      threshold_value = var.max_replicas
      duration        = "900s"

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_COUNT"
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    content   = "Nhóm đã ở trần ${var.max_replicas} VM liên tục 15 phút. Xem p95 và CPU; cân nhắc nâng max_replicas hoặc machine_type."
    mime_type = "text/markdown"
  }
}

# 3. Tỷ lệ 5xx của load balancer.
resource "google_monitoring_alert_policy" "lb_5xx_ratio" {
  display_name          = "${var.name_prefix} HA: tỷ lệ 5xx của load balancer"
  combiner              = "OR"
  notification_channels = local.alert_channels

  conditions {
    display_name = "5xx / tổng request > ngưỡng trong 5 phút"
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
    display_name = "p95 backend_latencies > ngưỡng trong 10 phút"
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
  display_name = "${var.name_prefix} HA readiness qua LB"
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
