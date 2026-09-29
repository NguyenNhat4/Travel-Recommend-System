output "dashboard_id" {
  description = "Cloud Monitoring dashboard resource name."
  value       = google_monitoring_dashboard.staging.id
}

output "uptime_check_id" {
  description = "Cloud Monitoring uptime check resource name."
  value       = google_monitoring_uptime_check_config.staging_health.id
}

output "alert_policy_ids" {
  description = "Staging alert policy resource names."
  value = {
    public_uptime = google_monitoring_alert_policy.staging_uptime.id
    app_cpu       = google_monitoring_alert_policy.staging_vm_cpu.id
    app_memory    = google_monitoring_alert_policy.staging_memory.id
    app_disk      = google_monitoring_alert_policy.staging_disk.id
    db_uptime     = google_monitoring_alert_policy.staging_db_uptime.id
    db_cpu        = google_monitoring_alert_policy.staging_db_cpu.id
    db_memory     = google_monitoring_alert_policy.staging_db_memory.id
    db_disk       = google_monitoring_alert_policy.staging_db_disk.id
    error_logs    = google_monitoring_alert_policy.staging_error_logs.id
  }
}
