locals {
  labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "database"
    role        = "replica"
  }

  primary_nic = data.google_compute_instance.db_primary.network_interface[0]
  primary_sa  = data.google_compute_instance.db_primary.service_account[0]
}

# The replica reuses the primary's network, service account and scopes, so it
# is reachable and can pull images exactly like the primary does. In the default
# network, default-allow-internal already lets it reach the primary on 5432 and
# default-allow-ssh covers SSH (IAP included), so no firewall resources are needed.
resource "google_compute_instance" "db_replica" {
  name         = var.db_replica_vm_name
  machine_type = var.machine_type
  zone         = var.zone
  labels       = local.labels

  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      image = var.image
      size  = var.disk_size_gb
      type  = var.disk_type
    }
  }

  network_interface {
    network    = local.primary_nic.network
    subnetwork = local.primary_nic.subnetwork

    dynamic "access_config" {
      for_each = var.assign_external_ip ? [1] : []
      content {}
    }
  }

  service_account {
    email  = local.primary_sa.email
    scopes = tolist(local.primary_sa.scopes)
  }
}
