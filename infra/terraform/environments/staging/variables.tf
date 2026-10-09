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
  description = "Zone of the existing DB primary VM. The replica goes to a DIFFERENT zone (db_replica_zone)."
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
  description = "Primary PostgreSQL VM, adopted into state from the hand-made instance (see primary.tf for the safety rules)."
  type        = string
  nullable    = false
}

variable "app_vm_name" {
  description = "Docker host VM for backend, frontend, crawler, Redis and Weaviate, adopted into state (see app.tf)."
  type        = string
  nullable    = false
}

variable "app_service_account_email" {
  description = "Service account of the app VM (the project's default Compute Engine account). The 8000 and 8765 firewall rules target it."
  type        = string
  default     = "365721936833-compute@developer.gserviceaccount.com"
}

variable "db_replica_zone" {
  description = "Zone of the replica VM, same region as the primary but a different zone: a replica in the primary's zone is lost together with it, so it is no zone-level insurance. Changing it replaces the replica VM (CI blocks that unless allow_destroy=true); then re-run the replication job to rebuild it from the primary."
  type        = string
  default     = "asia-southeast1-b"

  validation {
    condition     = var.db_replica_zone != var.zone
    error_message = "db_replica_zone must differ from zone (the primary's zone); same-zone replica does not survive a zone outage."
  }
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
  description = "Replica boot/data disk size. The primary holds about 156 MB of data and the slot WAL is capped at 2 GB, so 20 GB leaves ample room (primary: 6.4 GB used of 49 GB)."
  type        = number
  default     = 20

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
