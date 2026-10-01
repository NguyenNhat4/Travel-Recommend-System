data "google_compute_instance" "app" {
  project = var.project_id
  name    = var.app_vm_name
  zone    = var.zone
}

data "google_compute_instance" "db" {
  project = var.project_id
  name    = var.db_vm_name
  zone    = var.zone
}

data "google_compute_instance" "db_replica" {
  count   = var.db_replica_vm_name == "" ? 0 : 1
  project = var.project_id
  name    = var.db_replica_vm_name
  zone    = var.zone
}
