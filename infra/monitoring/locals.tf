locals {
  common_labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "monitoring"
  }

  notification_channels = var.notification_email == "" ? [] : [
    google_monitoring_notification_channel.staging_email[0].name
  ]
}
