variable "project_id" {
  description = "GCP project that hosts the HA app tier."
  type        = string
  nullable    = false
}

variable "region" {
  type    = string
  default = "asia-southeast1"
}

variable "name_prefix" {
  description = "Prefix for every resource created by this root."
  type        = string
  default     = "vota-ha"
}

variable "network" {
  description = "VPC network self link or name. The DB, replica and Weaviate must be reachable from it."
  type        = string
  default     = "default"
}

variable "subnetwork" {
  description = "Subnetwork self link used by instance template and Redis."
  type        = string
  nullable    = false
}

variable "app_service_account_email" {
  description = "Service account of the app VMs (needs Artifact Registry reader and Secret Manager accessor)."
  type        = string
  nullable    = false
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "backend_image" {
  description = "Backend image. Pin a tag or digest; do not use :latest in an autoscaled group."
  type        = string
  nullable    = false
}

variable "frontend_image" {
  type     = string
  nullable = false
}

variable "boot_image" {
  description = "Boot image for the instance template."
  type        = string
  default     = "projects/cos-cloud/global/images/family/cos-stable"
}

variable "backend_env_secret" {
  description = "Secret Manager secret id holding the backend .env (DATABASE_URL, AUTH_REDIS_URL, ITINERARY_REDIS_URL, WEAVIATE_URL ...). Must point at SHARED Redis/Weaviate, never at localhost."
  type        = string
  nullable    = false
}

variable "uvicorn_workers" {
  description = "Backend worker processes per VM. Keep <= vCPU; measure memory first (each worker loads its own catalog cache)."
  type        = number
  default     = 2
}

variable "min_replicas" {
  type    = number
  default = 2

  validation {
    condition     = var.min_replicas >= 2
    error_message = "min_replicas must be >= 2, otherwise the group is not highly available."
  }
}

variable "max_replicas" {
  type    = number
  default = 4
}

variable "cpu_target" {
  description = "Autoscaler target CPU utilization (0-1)."
  type        = number
  default     = 0.6
}

variable "memory_target_percent" {
  description = "Autoscaler target memory percent_used (needs Ops Agent on the VM). 0 disables the memory signal."
  type        = number
  default     = 80
}

variable "domain" {
  description = "Public domain for a Google-managed certificate. Empty = plain HTTP load balancer (staging smoke only)."
  type        = string
  default     = ""
}

variable "lb_timeout_seconds" {
  description = "Backend timeout. Itinerary SSE streams stay open up to ITINERARY_REQUEST_TIMEOUT_SECONDS (90s)."
  type        = number
  default     = 300
}

variable "create_redis" {
  description = "Create a Memorystore STANDARD_HA Redis for session, rate limit and itinerary working memory."
  type        = bool
  default     = true
}

variable "redis_memory_gb" {
  type    = number
  default = 1
}
