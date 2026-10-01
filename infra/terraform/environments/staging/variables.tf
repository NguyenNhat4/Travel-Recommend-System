variable "project_id" {
  description = "GCP project containing the staging VMs."
  type        = string
  nullable    = false
}

variable "region" {
  description = "GCP region used by the provider."
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  description = "Zone of the existing DB VM. The replica is created in the same zone."
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

variable "db_primary_vm_name" {
  description = "Existing (hand-made) DB VM running the primary PostgreSQL. Read-only here: Terraform never changes it."
  type        = string
  nullable    = false
}

variable "db_replica_vm_name" {
  description = "Name of the new replica VM."
  type        = string
  default     = "vota-staging-db-replica"

  validation {
    condition     = can(regex("^[a-z]([-a-z0-9]{0,60}[a-z0-9])?$", var.db_replica_vm_name))
    error_message = "db_replica_vm_name must be a valid GCE instance name."
  }
}

variable "machine_type" {
  description = "Replica machine type. e2-small is 2 vCPU (shared) and 2 GB RAM, matching the other VMs."
  type        = string
  default     = "e2-small"
}

variable "disk_size_gb" {
  description = "Replica boot/data disk size. The primary disk is 50 GB; keep the replica at least as large."
  type        = number
  default     = 50

  validation {
    condition     = var.disk_size_gb >= 20
    error_message = "disk_size_gb must be at least 20."
  }
}

variable "disk_type" {
  description = "Boot disk type."
  type        = string
  default     = "pd-balanced"
}

variable "image" {
  description = "Boot image. The bootstrap scripts support Debian/Ubuntu only."
  type        = string
  default     = "debian-cloud/debian-12"
}

variable "assign_external_ip" {
  description = "Give the replica an ephemeral external IP for apt, Docker and Artifact Registry egress. Set false only if the subnet has Cloud NAT. Inbound access is governed by the existing VPC firewall rules (default-allow-ssh is open to the Internet, as for the other VMs)."
  type        = bool
  default     = true
}
