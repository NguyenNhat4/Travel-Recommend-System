# The Docker host for backend, frontend, crawler, Redis and Weaviate, adopted from
# the hand-made instance. Same safety rules as primary.tf. The app reaches the
# primary through vota-db-tunnel.service on this VM (127.0.0.1:15432 ->
# 10.148.0.2:5432), configured by hand for now.
resource "google_compute_instance" "app" {
  name         = var.app_vm_name
  machine_type = "e2-medium"
  zone         = var.zone
  tags         = ["vota-web"]

  deletion_protection = true

  # Matches the live value; omitting it would force a replacement.
  key_revocation_action_type = "NONE"

  boot_disk {
    auto_delete = true
    device_name = var.app_vm_name
    source      = "projects/${var.project_id}/zones/${var.zone}/disks/${var.app_vm_name}"
  }

  network_interface {
    network    = "default"
    subnetwork = local.subnetwork
    network_ip = google_compute_address.app_internal.address

    access_config {
      nat_ip       = google_compute_address.app_public.address
      network_tier = "PREMIUM"
    }
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    provisioning_model  = "STANDARD"
  }

  service_account {
    email = var.app_service_account_email
    scopes = [
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
      "https://www.googleapis.com/auth/service.management.readonly",
      "https://www.googleapis.com/auth/servicecontrol",
      "https://www.googleapis.com/auth/trace.append",
    ]
  }

  shielded_instance_config {
    enable_integrity_monitoring = true
    enable_secure_boot          = false
    enable_vtpm                 = true
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      metadata,
      metadata_startup_script,
      labels,
      boot_disk,
    ]
  }
}
