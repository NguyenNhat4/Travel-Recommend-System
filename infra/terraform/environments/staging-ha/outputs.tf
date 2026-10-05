output "lb_ip" {
  description = "Public IP of the load balancer. Point DNS here."
  value       = google_compute_global_address.lb.address
}

output "redis_host" {
  description = "Memorystore host; put it in AUTH_REDIS_URL / SESSION_REDIS_URL / ITINERARY_REDIS_URL in the env secret."
  value       = try(google_redis_instance.shared[0].host, null)
}

output "instance_group" {
  value = google_compute_region_instance_group_manager.app.instance_group
}

output "weaviate_url" {
  description = "Put in WEAVIATE_URL of the env secret (gRPC port stays 50051). Run the index job against it before the group takes traffic."
  value       = try("http://${google_compute_address.weaviate[0].address}:8080", null)
}
