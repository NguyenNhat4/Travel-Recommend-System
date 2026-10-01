locals {
  labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "database"
    role        = "replica"
  }

  replica_tag = "vota-db-replica"

  primary_nic     = data.google_compute_instance.db_primary.network_interface[0]
  primary_sa      = data.google_compute_instance.db_primary.service_account[0]
  app_private_ip  = data.google_compute_instance.app.network_interface[0].network_ip
  replica_private = google_compute_instance.db_replica.network_interface[0].network_ip
}

# The replica reuses the primary's network, service account and scopes, so it
# can pull vota-db:pg16 from Artifact Registry exactly like the primary does.
resource "google_compute_instance" "db_replica" {
  name         = var.db_replica_vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [local.replica_tag]
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

# Primary accepts replication connections only from the replica.
# Targeted by service account because the hand-made primary carries no network tag.
resource "google_compute_firewall" "replica_to_primary_postgres" {
  name        = "${var.db_replica_vm_name}-to-primary-5432"
  network     = local.primary_nic.network
  description = "PostgreSQL streaming replication: replica to primary."

  direction               = "INGRESS"
  source_ranges           = ["${local.replica_private}/32"]
  target_service_accounts = [local.primary_sa.email]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

# SSH to the replica only from IAP (CI/operators) and from the app VM (read tunnel).
resource "google_compute_firewall" "ssh_to_replica" {
  name        = "${var.db_replica_vm_name}-ssh"
  network     = local.primary_nic.network
  description = "SSH to the DB replica from IAP and the app VM only."

  direction     = "INGRESS"
  source_ranges = [var.iap_ssh_source_range, "${local.app_private_ip}/32"]
  target_tags   = [local.replica_tag]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
