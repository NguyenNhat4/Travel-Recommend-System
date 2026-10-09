locals {
  labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "database"
    role        = "replica"
  }
}

# The replica reuses the primary's network, service account and scopes, so it
# is reachable and can pull images exactly like the primary does. In the default
# network, default-allow-internal already lets it reach the primary on 5432 and
# default-allow-ssh covers SSH (IAP included).
resource "google_compute_instance" "db_replica" {
  name         = var.db_replica_vm_name
  machine_type = var.machine_type
  zone         = var.db_replica_zone
  labels       = local.labels

  allow_stopping_for_update = true

  # OS Login: CI and people sign in with their IAM identity instead of ssh-keys in metadata.
  metadata = {
    enable-oslogin = "TRUE"
  }

  boot_disk {
    initialize_params {
      image = var.image
      size  = var.disk_size_gb
      type  = var.disk_type
    }
  }

  network_interface {
    network    = "default"
    subnetwork = local.subnetwork
    network_ip = google_compute_address.db_replica_internal.address

    dynamic "access_config" {
      for_each = var.assign_external_ip ? [1] : []
      content {}
    }
  }

  service_account {
    email  = google_compute_instance.db_primary.service_account[0].email
    scopes = tolist(google_compute_instance.db_primary.service_account[0].scopes)
  }

  lifecycle {
    ignore_changes = [metadata["ssh-keys"]]
  }
}
