# Shared Weaviate for every app VM. Vectors are derived data: if this VM or its disk is lost the
# index job rebuilds them from catalog (Postgres) and Cohere, so the target is fast rebuild + daily
# snapshots, not a 3-node Raft cluster. While it is down or empty the backends report NOT READY
# (READY_REQUIRES_RECSYS=true) and the load balancer sends no search traffic to them.
resource "google_compute_address" "weaviate" {
  count        = var.create_weaviate ? 1 : 0
  name         = "${var.name_prefix}-weaviate-ip"
  address_type = "INTERNAL"
  subnetwork   = var.subnetwork
  region       = var.region
}

resource "google_compute_disk" "weaviate_data" {
  count = var.create_weaviate ? 1 : 0
  name  = "${var.name_prefix}-weaviate-data"
  type  = "pd-balanced"
  zone  = var.weaviate_zone
  size  = var.weaviate_disk_gb

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_compute_resource_policy" "weaviate_snapshots" {
  count  = var.create_weaviate ? 1 : 0
  name   = "${var.name_prefix}-weaviate-daily"
  region = var.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "19:00" # UTC = 02:00 ICT
      }
    }
    retention_policy {
      max_retention_days    = 7
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }
  }
}

resource "google_compute_disk_resource_policy_attachment" "weaviate" {
  count = var.create_weaviate ? 1 : 0
  name  = google_compute_resource_policy.weaviate_snapshots[0].name
  disk  = google_compute_disk.weaviate_data[0].name
  zone  = var.weaviate_zone
}

resource "google_compute_instance" "weaviate" {
  count        = var.create_weaviate ? 1 : 0
  name         = "${var.name_prefix}-weaviate"
  machine_type = var.weaviate_machine_type
  zone         = var.weaviate_zone
  tags         = ["${var.name_prefix}-weaviate"]
  # Không gắn lịch tắt/bật: staging-ha chạy 24/7 (xác nhận 2026-10-12). Policy ở scheduler.tf giữ lại nhưng không gắn vào VM.

  boot_disk {
    initialize_params {
      image = var.boot_image
      size  = 20
    }
  }

  attached_disk {
    source      = google_compute_disk.weaviate_data[0].self_link
    device_name = "weaviate-data"
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    network_ip = google_compute_address.weaviate[0].address
  }

  service_account {
    email  = var.app_service_account_email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  allow_stopping_for_update = true

  depends_on = [
    google_secret_manager_secret_iam_member.weaviate_key_reader,
    google_compute_router_nat.egress,
    data.google_secret_manager_secret_version.weaviate_api_key,
  ]

  metadata = {
    startup-script = <<-SCRIPT
      #!/bin/bash
      set -euo pipefail
      DEV=/dev/disk/by-id/google-weaviate-data
      mkdir -p /mnt/weaviate
      blkid "$DEV" >/dev/null 2>&1 || mkfs.ext4 -F "$DEV"   # chỉ định dạng đĩa trống
      mountpoint -q /mnt/weaviate || mount "$DEV" /mnt/weaviate
      KEY=$(gcloud secrets versions access latest --secret='${var.weaviate_api_key_secret}')
      docker rm -f vota-weaviate 2>/dev/null || true
      docker run -d --name vota-weaviate --restart unless-stopped --memory 3g \
        -p 8080:8080 -p 50051:50051 -v /mnt/weaviate:/var/lib/weaviate \
        -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
        -e DEFAULT_VECTORIZER_MODULE=none -e ENABLE_MODULES= \
        -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=false \
        -e AUTHENTICATION_APIKEY_ENABLED=true \
        -e AUTHENTICATION_APIKEY_ALLOWED_KEYS="$KEY" -e AUTHENTICATION_APIKEY_USERS=vota-backend \
        cr.weaviate.io/semitechnologies/weaviate:1.27.0 --host 0.0.0.0 --port 8080 --scheme http
    SCRIPT
  }
}

# Only the app group reaches Weaviate (REST 8080 and gRPC 50051); no public address.
resource "google_compute_firewall" "app_to_weaviate" {
  count       = var.create_weaviate ? 1 : 0
  name        = "${var.name_prefix}-app-to-weaviate"
  network     = var.network
  direction   = "INGRESS"
  source_tags = ["${var.name_prefix}-app"]
  target_tags = ["${var.name_prefix}-weaviate"]

  allow {
    protocol = "tcp"
    ports    = ["8080", "50051"]
  }
}
