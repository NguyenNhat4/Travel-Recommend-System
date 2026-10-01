# Reserve the addresses the VMs already hold so they can never change. Reserving an
# in-use ephemeral address keeps it attached; nothing restarts. These addresses are
# load-bearing: the app VM reaches the primary through an SSH tunnel to
# 10.148.0.2, PRIMARY pg_hba allows the replica by its IP, and DuckDNS points at the
# app's external IP.
locals {
  subnetwork = "projects/${var.project_id}/regions/${var.region}/subnetworks/default"

  ips = {
    db_primary = "10.148.0.2"
    app        = "10.148.0.3"
    db_replica = "10.148.0.4"
    app_public = "34.142.132.251"
  }
}

resource "google_compute_address" "db_primary_internal" {
  name         = "${var.db_primary_vm_name}-internal"
  region       = var.region
  address_type = "INTERNAL"
  address      = local.ips.db_primary
  subnetwork   = local.subnetwork
}

resource "google_compute_address" "app_internal" {
  name         = "${var.app_vm_name}-internal"
  region       = var.region
  address_type = "INTERNAL"
  address      = local.ips.app
  subnetwork   = local.subnetwork
}

resource "google_compute_address" "db_replica_internal" {
  name         = "${var.db_replica_vm_name}-internal"
  region       = var.region
  address_type = "INTERNAL"
  address      = local.ips.db_replica
  subnetwork   = local.subnetwork
}

resource "google_compute_address" "app_public" {
  name         = "${var.app_vm_name}-public"
  region       = var.region
  address_type = "EXTERNAL"
  address      = local.ips.app_public
  network_tier = "PREMIUM"
}
