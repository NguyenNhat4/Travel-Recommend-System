output "replica_vm_name" {
  description = "Replica VM name; use it for GCE_DB_REPLICA_INSTANCE in infra/monitoring."
  value       = google_compute_instance.db_replica.name
}

output "replica_private_ip" {
  description = "Private IP of the replica; PRIMARY pg_hba and the app-side read tunnel use it."
  value       = google_compute_address.db_replica_internal.address
}

output "primary_vm_name" {
  description = "Primary DB VM name."
  value       = google_compute_instance.db_primary.name
}

output "primary_private_ip" {
  description = "Private IP of the primary; pass it as PRIMARY_HOST to ops/bootstrap-db-replica.sh."
  value       = google_compute_address.db_primary_internal.address
}

output "app_vm_name" {
  description = "App VM name."
  value       = google_compute_instance.app.name
}

output "app_private_ip" {
  description = "Private IP of the app VM."
  value       = google_compute_address.app_internal.address
}

output "app_public_ip" {
  description = "Static external IP of the app VM (DuckDNS points here)."
  value       = google_compute_address.app_public.address
}
