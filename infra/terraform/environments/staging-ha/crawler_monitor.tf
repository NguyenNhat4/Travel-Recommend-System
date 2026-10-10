# Dashboard job cào (monitor, cổng 8765 của VM crawler) công khai qua load balancer HTTPS đang có, đủ chức năng (không read-only).
# - Host công khai: var.monitor_host (Cloudflare proxy → LB, cùng cert *.praxis.io.vn với origin).
# - Monitor chạy đủ chức năng (không --read-only): mọi API điều khiển job, cấu hình, xoá lượt đều dùng được.
# - VM crawler không có IP public. Firewall chỉ cho dải health check và LB của Google vào cổng 8765.
# - Không có xác thực: người vận hành chấp nhận dashboard công khai không có xác thực (xem history/2026-10-09-staging-ha-cd-tu-dong.md).
# Bật bằng crawler_monitor_public = true trong staging-ha.tfvars, sau khi bản ghi DNS monitor.<domain> đã trỏ về LB.

variable "crawler_monitor_public" {
  description = "Công khai dashboard job cào qua monitor_host trên LB staging-ha."
  type        = bool
  default     = false
}

variable "monitor_host" {
  description = "Tên miền công khai của dashboard job cào. Phải nằm trong cert origin (*.praxis.io.vn)."
  type        = string
  default     = "monitor.praxis.io.vn"
}

locals {
  monitor_enabled = local.crawler_enabled && var.crawler_monitor_public
  monitor_port    = 8765
}

resource "google_compute_instance_group" "crawler" {
  count     = local.monitor_enabled ? 1 : 0
  name      = "${var.name_prefix}-crawler-ig"
  zone      = var.crawler_zone
  instances = [google_compute_instance.crawler[0].self_link]

  named_port {
    name = "http-monitor"
    port = local.monitor_port
  }
}

# TCP, không HTTP: monitor từ chối Host lạ, nên health check HTTP không có Host hợp lệ sẽ luôn fail.
resource "google_compute_health_check" "monitor" {
  count               = local.monitor_enabled ? 1 : 0
  name                = "${var.name_prefix}-crawler-monitor"
  check_interval_sec  = 30
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3

  tcp_health_check {
    port = local.monitor_port
  }
}

resource "google_compute_backend_service" "monitor" {
  count                 = local.monitor_enabled ? 1 : 0
  name                  = "${var.name_prefix}-crawler-monitor"
  protocol              = "HTTP"
  port_name             = "http-monitor"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 60
  health_checks         = [google_compute_health_check.monitor[0].id]

  backend {
    group           = google_compute_instance_group.crawler[0].self_link
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
    capacity_scaler = 1.0
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

resource "google_compute_firewall" "lb_to_crawler_monitor" {
  count         = local.monitor_enabled ? 1 : 0
  name          = "${var.name_prefix}-lb-to-crawler-monitor"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = [local.crawler_tag]

  allow {
    protocol = "tcp"
    ports    = [tostring(local.monitor_port)]
  }
}
