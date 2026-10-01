output "replica_vm_name" {
  description = "Replica VM name; use it for GCE_DB_REPLICA_INSTANCE in infra/monitoring."
  value       = google_compute_instance.db_replica.name
}

output "replica_private_ip" {
  description = "Private IP of the replica; PRIMARY pg_hba and the app-side read tunnel use it."
  value       = google_compute_instance.db_replica.network_interface[0].network_ip
}

output "primary_private_ip" {
  description = "Private IP of the existing primary; pass it as PRIMARY_HOST to ops/bootstrap-db-replica.sh."
  value       = data.google_compute_instance.db_primary.network_interface[0].network_ip
}
