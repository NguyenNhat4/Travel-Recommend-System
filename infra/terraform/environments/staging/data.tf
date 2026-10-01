data "google_compute_instance" "db_primary" {
  project = var.project_id
  name    = var.db_primary_vm_name
  zone    = var.zone
}
