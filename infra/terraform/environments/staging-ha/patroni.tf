# Tầng DB tự failover: 2 node Patroni/Postgres ở 2 zone + 1 witness etcd ở zone thứ ba + load balancer nội bộ.
# Use case và số liệu: docs/plan/2026-10-07-ha-vung-crawler-rolling.md §2. Tắt mặc định (create_patroni = false).
#
#   zone a: vota-ha-pg-a  (etcd + Patroni + Postgres)  -- đĩa dữ liệu riêng, snapshot hằng ngày
#   zone b: vota-ha-pg-b  (etcd + Patroni + Postgres)  -- replica đồng bộ ở zone KHÁC primary
#   zone c: vota-ha-pg-w  (etcd)                       -- đa số thứ ba: mất 1 zone vẫn còn 2/3 etcd
#
# ILB nội bộ chỉ gửi kết nối tới node trả 200 ở :8008/primary (leader). Failover của Patroni đổi leader, health check
# phát hiện, ILB chuyển hướng: không ai phải chạy lệnh nào, không đổi DNS (db.vota.internal trỏ ILB, xem dns.tf).
locals {
  patroni_enabled = var.create_patroni
  patroni_nodes = local.patroni_enabled ? {
    a = { zone = var.patroni_zones[0], role = "db" }
    b = { zone = var.patroni_zones[1], role = "db" }
    w = { zone = var.patroni_witness_zone, role = "witness" }
  } : {}
  patroni_tag          = "${var.name_prefix}-pg"
  patroni_ips          = { for k, a in google_compute_address.patroni : k => a.address }
  etcd_initial_cluster = join(",", [for k in sort(keys(local.patroni_ips)) : "${var.name_prefix}-pg-${k}=http://${local.patroni_ips[k]}:2380"])
  etcd_client_hosts    = join(",", [for k in sort(keys(local.patroni_ips)) : "${local.patroni_ips[k]}:2379"])
}

resource "google_compute_address" "patroni" {
  for_each     = local.patroni_nodes
  name         = "${var.name_prefix}-pg-${each.key}-ip"
  address_type = "INTERNAL"
  subnetwork   = var.subnetwork
  region       = var.region
}

resource "google_compute_disk" "patroni_data" {
  for_each = { for k, n in local.patroni_nodes : k => n if n.role == "db" }
  name     = "${var.name_prefix}-pg-${each.key}-data"
  type     = "pd-balanced"
  zone     = each.value.zone
  size     = var.patroni_disk_gb

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_compute_resource_policy" "patroni_snapshots" {
  count  = local.patroni_enabled ? 1 : 0
  name   = "${var.name_prefix}-pg-daily-snapshot"
  region = var.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "20:00" # 03:00 giờ Việt Nam
      }
    }
    retention_policy {
      max_retention_days    = 7
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }
  }
}

resource "google_compute_disk_resource_policy_attachment" "patroni_snapshots" {
  for_each = google_compute_disk.patroni_data
  name     = google_compute_resource_policy.patroni_snapshots[0].name
  disk     = each.value.name
  zone     = each.value.zone
}

resource "google_compute_instance" "patroni" {
  for_each     = local.patroni_nodes
  name         = "${var.name_prefix}-pg-${each.key}"
  machine_type = each.value.role == "db" ? var.patroni_machine_type : var.patroni_witness_machine_type
  zone         = each.value.zone
  tags         = [local.patroni_tag]
  labels       = { component = "database", role = each.value.role == "db" ? "patroni" : "etcd-witness" }

  # Đổi startup script (ví dụ đổi image Patroni) chỉ chạy lại khi VM khởi động lại; làm có chủ đích theo runbook,
  # từng node một, replica trước. Terraform không tự dừng VM để cập nhật.
  allow_stopping_for_update = false

  boot_disk {
    initialize_params {
      image = "projects/debian-cloud/global/images/family/debian-12"
      size  = 20
      type  = "pd-balanced"
    }
  }

  dynamic "attached_disk" {
    for_each = each.value.role == "db" ? [1] : []
    content {
      source      = google_compute_disk.patroni_data[each.key].id
      device_name = "pgdata"
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    network_ip = local.patroni_ips[each.key]
    # Không IP public: kéo image và apt qua Cloud NAT (network.tf).
  }

  service_account {
    email  = var.patroni_service_account_email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    enable-oslogin = "TRUE"
    startup-script = templatefile("${path.module}/patroni-node.sh.tftpl", {
      role                 = each.value.role
      project_id           = var.project_id
      registry_host        = split("/", var.patroni_image)[0]
      patroni_image        = var.patroni_image
      etcd_image           = var.patroni_etcd_image
      etcd_name            = "${var.name_prefix}-pg-${each.key}"
      etcd_initial_cluster = local.etcd_initial_cluster
      etcd_hosts           = local.etcd_client_hosts
      node_name            = "${var.name_prefix}-pg-${each.key}"
      node_ip              = local.patroni_ips[each.key]
      scope                = "${var.name_prefix}-pg"
      env_secret           = var.patroni_env_secret
      clone_from_host      = var.patroni_clone_from_host
      probe_script         = file("${path.module}/../../../../ops/patroni/cluster_probe.py")
      ops_agent_config     = file("${path.module}/patroni_ops_agent.yaml")
    })
  }

  depends_on = [google_compute_router_nat.egress]
}

resource "google_secret_manager_secret" "patroni_env" {
  count     = local.patroni_enabled ? 1 : 0
  secret_id = var.patroni_env_secret

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "patroni_env_reader" {
  count     = local.patroni_enabled ? 1 : 0
  secret_id = google_secret_manager_secret.patroni_env[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.patroni_service_account_email}"
}

# --- Firewall ---------------------------------------------------------------------------------------------------
# Giữa các node: etcd (2379/2380), Patroni REST (8008), Postgres (5432, replication + pg_rewind).
resource "google_compute_firewall" "patroni_peers" {
  count       = local.patroni_enabled ? 1 : 0
  name        = "${var.name_prefix}-pg-peers"
  network     = var.network
  direction   = "INGRESS"
  source_tags = [local.patroni_tag]
  target_tags = [local.patroni_tag]

  allow {
    protocol = "tcp"
    ports    = ["2379", "2380", "8008", "5432"]
  }
}

# Health check của ILB tới Patroni REST.
resource "google_compute_firewall" "patroni_health" {
  count         = local.patroni_enabled ? 1 : 0
  name          = "${var.name_prefix}-pg-health"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = [local.patroni_tag]

  allow {
    protocol = "tcp"
    ports    = ["8008"]
  }
}

# Client (app VM, job cào) tới Postgres. Chỉ cổng 5432, chỉ từ các tag được liệt kê.
resource "google_compute_firewall" "patroni_clients" {
  count       = local.patroni_enabled ? 1 : 0
  name        = "${var.name_prefix}-pg-clients"
  network     = var.network
  direction   = "INGRESS"
  source_tags = concat(["${var.name_prefix}-app", "vota-crawler"], var.db_client_tags)
  target_tags = [local.patroni_tag]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

# --- Load balancer nội bộ: chỉ leader nhận kết nối ---------------------------------------------------------------
resource "google_compute_instance_group" "patroni" {
  for_each  = { for k, n in local.patroni_nodes : k => n if n.role == "db" }
  name      = "${var.name_prefix}-pg-${each.key}"
  zone      = each.value.zone
  instances = [google_compute_instance.patroni[each.key].self_link]
}

resource "google_compute_health_check" "patroni_primary" {
  count               = local.patroni_enabled ? 1 : 0
  name                = "${var.name_prefix}-pg-primary"
  check_interval_sec  = 5
  timeout_sec         = 3
  healthy_threshold   = 2
  unhealthy_threshold = 2

  http_health_check {
    port         = 8008
    request_path = "/primary" # 200 chỉ trên leader; replica trả 503 nên ILB không gửi kết nối ghi tới replica
  }
}

resource "google_compute_region_backend_service" "patroni_primary" {
  provider              = google-beta # connection_tracking_policy chỉ có ở google-beta
  count                 = local.patroni_enabled ? 1 : 0
  name                  = "${var.name_prefix}-pg-primary"
  region                = var.region
  protocol              = "TCP"
  load_balancing_scheme = "INTERNAL"
  health_checks         = [google_compute_health_check.patroni_primary[0].id]

  # Node vừa bị hạ cấp (hoặc cô lập khỏi mạng) không được giữ kết nối cũ: kết nối tới nó phải đứt để client nối lại
  # vào leader mới. Mặc định của TCP là giữ kết nối trên backend unhealthy.
  connection_tracking_policy {
    connection_persistence_on_unhealthy_backends = "NEVER_PERSIST"
  }

  dynamic "backend" {
    for_each = google_compute_instance_group.patroni
    content {
      group          = backend.value.id
      balancing_mode = "CONNECTION"
    }
  }
}

resource "google_compute_address" "patroni_ilb" {
  count        = local.patroni_enabled ? 1 : 0
  name         = "${var.name_prefix}-pg-ilb-ip"
  address_type = "INTERNAL"
  subnetwork   = var.subnetwork
  region       = var.region
}

resource "google_compute_forwarding_rule" "patroni_primary" {
  count                 = local.patroni_enabled ? 1 : 0
  name                  = "${var.name_prefix}-pg-primary"
  region                = var.region
  load_balancing_scheme = "INTERNAL"
  backend_service       = google_compute_region_backend_service.patroni_primary[0].id
  ip_address            = google_compute_address.patroni_ilb[0].address
  ip_protocol           = "TCP"
  ports                 = ["5432"]
  network               = var.network
  subnetwork            = var.subnetwork
}
