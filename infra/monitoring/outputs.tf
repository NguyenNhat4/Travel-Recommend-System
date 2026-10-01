output "dashboard_id" {
  description = "Cloud Monitoring dashboard resource name."
  value       = google_monitoring_dashboard.staging.id
}

output "uptime_check_id" {
  description = "Cloud Monitoring uptime check resource name."
  value       = google_monitoring_uptime_check_config.staging_health.id
}

output "slo_ids" {
  description = "Staging Service Monitoring SLO resource names."
  value = {
    availability = google_monitoring_slo.staging_availability.id
    error_rate   = google_monitoring_slo.staging_error_rate.id
    latency      = google_monitoring_slo.staging_latency.id
  }
}

output "alert_policy_ids" {
  description = "Staging alert policy resource names."
  value = {
    public_uptime   = google_monitoring_alert_policy.staging_uptime.id
    app_cpu         = google_monitoring_alert_policy.staging_vm_cpu.id
    app_memory      = google_monitoring_alert_policy.staging_memory.id
    app_disk        = google_monitoring_alert_policy.staging_disk.id
    db_uptime       = google_monitoring_alert_policy.staging_db_uptime.id
    db_cpu          = google_monitoring_alert_policy.staging_db_cpu.id
    db_memory       = google_monitoring_alert_policy.staging_db_memory.id
    db_disk         = google_monitoring_alert_policy.staging_db_disk.id
    error_logs      = google_monitoring_alert_policy.staging_error_logs.id
    crawler_warning = google_monitoring_alert_policy.staging_crawler_warning.id
    crawler_failure = google_monitoring_alert_policy.staging_crawler_failure.id
    container_stop  = google_monitoring_alert_policy.staging_container_stop.id
    container_oom   = google_monitoring_alert_policy.staging_container_oom.id
    watcher_absent  = google_monitoring_alert_policy.staging_docker_watcher_absent.id
  }
}

output "db_replica_alert_policy_ids" {
  description = "DB replica alert policy resource names; empty until db_replica_vm_name is set."
  value = local.replica_enabled ? {
    uptime      = google_monitoring_alert_policy.replica_uptime[0].id
    replication = google_monitoring_alert_policy.replica_replication[0].id
    probe       = google_monitoring_alert_policy.replica_probe_absent[0].id
    vm          = { for k, v in google_monitoring_alert_policy.replica_vm : k => v.id }
  } : {}
}
