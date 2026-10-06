# The primary PostgreSQL VM, adopted from the hand-made instance. It is the most
# valuable resource in the stack (the data lives on its boot disk), so Terraform
# may only touch it in ways that do not stop or recreate it:
#   - prevent_destroy / deletion_protection block any delete or replace;
#   - allow_stopping_for_update is left unset, so any change that needs a stop fails
#     at apply instead of rebooting the database;
#   - metadata is ignored: it holds ssh-keys that people and CI add at run time and
#     the app tunnel depends on SSH access to this VM staying as is;
#   - the boot disk (and its default-schedule-1 daily snapshot policy) is managed
#     outside Terraform.
resource "google_compute_instance" "db_primary" {
  name         = var.db_primary_vm_name
  machine_type = "e2-small"
  zone         = var.zone

  deletion_protection = true

  # Matches the live value; omitting it would force a replacement.
  key_revocation_action_type = "NONE"

  boot_disk {
    auto_delete = true
    device_name = var.db_primary_vm_name
    source      = "projects/${var.project_id}/zones/${var.zone}/disks/${var.db_primary_vm_name}"
  }

  network_interface {
    network    = "default"
    subnetwork = local.subnetwork
    network_ip = google_compute_address.db_primary_internal.address

    access_config {
      network_tier = "PREMIUM"
    }
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    provisioning_model  = "STANDARD"
  }

  service_account {
    email  = "${var.db_primary_vm_name}@${var.project_id}.iam.gserviceaccount.com"
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
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
      network_interface[0].access_config[0].nat_ip,
    ]
  }
}
