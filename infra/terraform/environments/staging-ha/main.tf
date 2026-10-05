locals {
  registry_host = split("/", var.backend_image)[0]
  # The host-network compose used by the single staging VM, plus resource limits for the HA tier.
  compose = file("${path.module}/compose.ha.yml")
  startup = templatefile("${path.module}/startup.sh.tftpl", {
    backend_env_secret = var.backend_env_secret
    registry_host      = local.registry_host
    backend_image      = var.backend_image
    frontend_image     = var.frontend_image
    uvicorn_workers    = var.uvicorn_workers
    compose            = local.compose
  })
}

resource "google_compute_instance_template" "app" {
  name_prefix  = "${var.name_prefix}-app-"
  machine_type = var.machine_type
  tags         = ["${var.name_prefix}-app"]

  disk {
    source_image = var.boot_image
    auto_delete  = true
    boot         = true
    disk_size_gb = 30
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    # No external IP: traffic enters through the load balancer only. Needs Cloud NAT for image pulls.
  }

  service_account {
    email  = var.app_service_account_email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    startup-script         = local.startup
    google-logging-enabled = "true"
  }

  depends_on = [
    google_secret_manager_secret_iam_member.backend_env_reader,
    google_compute_router_nat.egress,
    data.google_secret_manager_secret_version.backend_env,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# Hai health check có vai trò khác nhau, KHÔNG dùng chung:
# - ready (load balancer): frontend /health/ready proxy backend /health/ready, gồm cả RecSys đã nạp. Chưa sẵn sàng thì
#   chỉ bị loại khỏi rotation, VM vẫn sống và tự hồi phục khi Weaviate/DB quay lại.
# - live (autohealing): frontend /health/live proxy backend /health, chỉ nói "tiến trình còn trả lời". Chỉ khi VM thật sự
#   treo mới bị thay. Dùng readiness cho autohealing thì Weaviate/DB gián đoạn làm MIG xoá và tạo lại VM liên tục
#   mà không sửa được gì (docs/plan/2026-10-05-ha-load-balancing.md §3b, use case 3).
resource "google_compute_health_check" "ready" {
  name                = "${var.name_prefix}-app-ready"
  check_interval_sec  = 10
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3

  http_health_check {
    port_specification = "USE_FIXED_PORT"
    port               = 3000
    request_path       = "/health/ready"
  }
}

resource "google_compute_health_check" "live" {
  name                = "${var.name_prefix}-app-live"
  check_interval_sec  = 15
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 4 # 60 giây liên tục không trả lời mới thay VM

  http_health_check {
    port_specification = "USE_FIXED_PORT"
    port               = 3000
    request_path       = "/health/live"
  }
}

resource "google_compute_region_instance_group_manager" "app" {
  name                      = "${var.name_prefix}-app"
  base_instance_name        = "${var.name_prefix}-app"
  region                    = var.region
  distribution_policy_zones = null

  version {
    instance_template = google_compute_instance_template.app.self_link_unique
  }

  named_port {
    name = "http-web"
    port = 3000
  }

  auto_healing_policies {
    health_check      = google_compute_health_check.live.id
    initial_delay_sec = 300
  }

  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 3
    max_unavailable_fixed = 0
  }

  lifecycle {
    ignore_changes = [target_size]
  }
}

resource "google_compute_region_autoscaler" "app" {
  name   = "${var.name_prefix}-app"
  region = var.region
  target = google_compute_region_instance_group_manager.app.id

  autoscaling_policy {
    min_replicas    = var.min_replicas
    max_replicas    = var.max_replicas
    cooldown_period = 180

    cpu_utilization {
      target = var.cpu_target
    }

    dynamic "metric" {
      for_each = var.memory_target_percent > 0 ? [1] : []
      content {
        name   = "agent.googleapis.com/memory/percent_used"
        filter = "metric.labels.state = \"used\""
        target = var.memory_target_percent
        type   = "GAUGE"
      }
    }

    scale_in_control {
      time_window_sec = 600
      max_scaled_in_replicas {
        fixed = 1
      }
    }
  }
}

# Google front ends and health checkers reach port 3000 (traffic + probe) only.
resource "google_compute_firewall" "lb_to_app" {
  name          = "${var.name_prefix}-lb-to-app"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["${var.name_prefix}-app"]

  allow {
    protocol = "tcp"
    ports    = ["3000"]
  }
}

resource "google_compute_global_address" "lb" {
  name = "${var.name_prefix}-lb-ip"
}

resource "google_compute_backend_service" "app" {
  name                            = "${var.name_prefix}-app"
  protocol                        = "HTTP"
  port_name                       = "http-web"
  load_balancing_scheme           = "EXTERNAL_MANAGED"
  timeout_sec                     = var.lb_timeout_seconds
  health_checks                   = [google_compute_health_check.ready.id]
  session_affinity                = "NONE" # sessions live in Redis; any VM can serve any request
  connection_draining_timeout_sec = 60

  backend {
    group           = google_compute_region_instance_group_manager.app.instance_group
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
    capacity_scaler = 1.0
  }

  log_config {
    enable      = true
    sample_rate = 0.5
  }
}

resource "google_compute_url_map" "app" {
  name            = "${var.name_prefix}-app"
  default_service = google_compute_backend_service.app.id
}

resource "google_compute_managed_ssl_certificate" "app" {
  count = var.domain == "" ? 0 : 1
  name  = "${var.name_prefix}-cert"

  managed {
    domains = [var.domain]
  }
}

resource "google_compute_target_https_proxy" "app" {
  count            = var.domain == "" ? 0 : 1
  name             = "${var.name_prefix}-https"
  url_map          = google_compute_url_map.app.id
  ssl_certificates = [google_compute_managed_ssl_certificate.app[0].id]
}

resource "google_compute_target_http_proxy" "app" {
  count   = var.domain == "" ? 1 : 0
  name    = "${var.name_prefix}-http"
  url_map = google_compute_url_map.app.id
}

resource "google_compute_global_forwarding_rule" "app" {
  name                  = "${var.name_prefix}-fr"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb.id
  port_range            = var.domain == "" ? "80" : "443"
  target                = var.domain == "" ? google_compute_target_http_proxy.app[0].id : google_compute_target_https_proxy.app[0].id
}

# Shared session/rate-limit/working-memory store. noeviction matches deployment-plan.md §1.
resource "google_redis_instance" "shared" {
  count                   = var.create_redis ? 1 : 0
  name                    = "${var.name_prefix}-redis"
  tier                    = "STANDARD_HA"
  memory_size_gb          = var.redis_memory_gb
  region                  = var.region
  authorized_network      = var.network
  auth_enabled            = true
  transit_encryption_mode = "DISABLED"
  redis_version           = "REDIS_7_0"

  redis_configs = {
    maxmemory-policy = "noeviction"
  }
}
