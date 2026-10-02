variable "project_id" {
  description = "GCP project containing the staging VMs and monitoring resources."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid GCP project ID."
  }
}

variable "region" {
  description = "GCP region used by the provider."
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  description = "GCP zone hosting the staging VMs."
  type        = string
  default     = "asia-southeast1-a"
}

variable "environment" {
  description = "Environment label. This root is intentionally staging-only."
  type        = string
  default     = "staging"

  validation {
    condition     = var.environment == "staging"
    error_message = "This Terraform root only accepts environment = staging."
  }
}

variable "name_prefix" {
  description = "Prefix used for monitoring resource display names."
  type        = string
  default     = "vota-staging"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,40}$", var.name_prefix))
    error_message = "name_prefix must contain lowercase letters, digits and hyphens."
  }
}

variable "app_vm_name" {
  description = "Staging application VM name, used in dashboard documentation."
  type        = string
  nullable    = false
}

variable "db_vm_name" {
  description = "Staging database VM name, used in dashboard documentation."
  type        = string
  nullable    = false
}

variable "uptime_host" {
  description = "Staging public hostname checked by Cloud Monitoring Uptime Checks."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9.-]+$", var.uptime_host))
    error_message = "uptime_host must be a hostname without scheme or path."
  }
}

variable "uptime_path" {
  description = "Staging health path checked by Cloud Monitoring Uptime Checks."
  type        = string
  default     = "/health/ready"

  validation {
    condition     = startswith(var.uptime_path, "/") && !strcontains(var.uptime_path, "?")
    error_message = "uptime_path must be an absolute path without a query string."
  }
}

variable "notification_email" {
  description = "Optional staging alert email. Leave empty to create policies without a channel."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition     = var.notification_email == "" || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.notification_email))
    error_message = "notification_email must be empty or a valid email address."
  }
}

variable "db_replica_vm_name" {
  description = "DB replica VM name (infra/terraform/environments/staging output replica_vm_name). Replica monitoring is skipped while this is empty or while no VM with this name exists, and turns on once the VM does."
  type        = string
  default     = ""
}

variable "container_disk_alert_gib" {
  description = "Alert when one container (writable layer + json logs + named volumes) exceeds this many GiB."
  type        = number
  default     = 5

  validation {
    condition     = var.container_disk_alert_gib > 0
    error_message = "container_disk_alert_gib must be greater than zero."
  }
}
