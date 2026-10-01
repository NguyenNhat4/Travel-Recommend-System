data "google_compute_instance" "db_primary" {
  project = var.project_id
  name    = var.db_primary_vm_name
  zone    = var.zone
}

data "google_compute_instance" "app" {
  project = var.project_id
  name    = var.app_vm_name
  zone    = var.zone
}
