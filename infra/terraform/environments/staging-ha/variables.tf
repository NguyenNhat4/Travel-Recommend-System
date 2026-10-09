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
  description = "Số VM tối thiểu. 3 (một VM mỗi zone) để mất 1 VM chỉ đẩy phần còn lại lên N/(N-1) = 150% tải thay vì 200%."
  type        = number
  default     = 3

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
  description = "Autoscaler target CPU utilization (0-1). Để sống sót khi mất 1 trong N VM, mức dùng ở trạng thái ổn định phải <= (N-1)/N: N=3 -> 0.667, N=2 -> 0.5."
  type        = number
  default     = 0.55

  validation {
    condition     = var.cpu_target <= (var.min_replicas - 1) / var.min_replicas
    error_message = "cpu_target phải <= (min_replicas-1)/min_replicas, nếu không mất 1 VM làm các VM còn lại quá tải (docs/plan/2026-10-07-ha-vung-crawler-rolling.md §5.2)."
  }
}

variable "memory_target_percent" {
  description = "Autoscaler target memory percent_used (needs Ops Agent on the VM). 0 disables the memory signal. Cùng công thức (N-1)/N với CPU."
  type        = number
  default     = 60

  validation {
    condition     = var.memory_target_percent == 0 || var.memory_target_percent <= 100 * (var.min_replicas - 1) / var.min_replicas
    error_message = "memory_target_percent phải <= 100*(min_replicas-1)/min_replicas (hoặc 0 để tắt)."
  }
}

variable "boot_to_ready_seconds" {
  description = "Thời gian từ lúc VM tạo đến lúc /health/ready = 200 (kéo image, nạp RecSys). Dùng cho min_ready_sec của rolling update, cooldown autoscaler và initial_delay autohealing. CHƯA đo trên GCP: đo lại sau lần apply đầu (log startup.recsys.ready so với thời điểm tạo VM) rồi chỉnh."
  type        = number
  default     = 360

  validation {
    condition     = var.boot_to_ready_seconds >= 360
    error_message = "boot_to_ready_seconds < 360 thấp hơn thời gian boot-to-ready ước tính (4-6 phút)."
  }
}

variable "sse_max_seconds" {
  description = "Thời lượng tối đa của một stream SSE trợ lý (ITINERARY_REQUEST_TIMEOUT_SECONDS)."
  type        = number
  default     = 90
}

variable "lb_connection_draining_seconds" {
  description = "Connection draining của backend service. Chuỗi bắt buộc: sse_max_seconds <= draining <= stop_grace (draining + 10) để stream đang chạy không bị cắt khi scale-in hoặc rolling update."
  type        = number
  default     = 100

  validation {
    condition     = var.lb_connection_draining_seconds >= var.sse_max_seconds
    error_message = "lb_connection_draining_seconds phải >= sse_max_seconds, nếu không stream trợ lý dài hơn bị cắt khi rút VM."
  }
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

variable "create_weaviate" {
  description = "Create the shared Weaviate VM. Set false when using Weaviate Cloud (then put its URL in the env secret)."
  type        = bool
  default     = true
}

variable "weaviate_zone" {
  type    = string
  default = "asia-southeast1-a"
}

variable "weaviate_machine_type" {
  description = "Vectors for ~11k search units are tens of MB; memory is for HNSW + BM25, not data size."
  type        = string
  default     = "e2-medium"
}

variable "weaviate_disk_gb" {
  type    = number
  default = 50
}

variable "weaviate_api_key_secret" {
  description = "Secret Manager secret id holding the Weaviate API key (same value as WEAVIATE_API_KEY in the backend env secret)."
  type        = string
  default     = "vota-ha-weaviate-api-key"
}

variable "db_primary_ip" {
  description = "Private IP of the Postgres primary (staging root output db_primary_private_ip / addresses.tf)."
  type        = string
  nullable    = false
}

variable "db_replica_ip" {
  description = "Private IP of the Postgres replica; empty = no db-replica record."
  type        = string
  default     = ""
}

variable "internal_zone_dns_name" {
  type    = string
  default = "vota.internal."
}

variable "create_nat" {
  description = "Create Cloud NAT for the region. Set false if the VPC already has one."
  type        = bool
  default     = true
}

variable "require_secret_versions" {
  description = "Fail the plan unless the env secrets already have a version. First apply: false; after loading values: true."
  type        = bool
  default     = false
}

variable "alert_emails" {
  description = "Emails that receive HA alerts. Empty = alert policies exist but notify nobody (see notification_channel_ids)."
  type        = list(string)
  default     = []
}

variable "notification_channel_ids" {
  description = "Existing Cloud Monitoring notification channel ids to attach in addition to alert_emails."
  type        = list(string)
  default     = []
}

variable "alert_p95_latency_ms" {
  type    = number
  default = 800
}

variable "alert_5xx_ratio" {
  description = "Fraction of LB requests answered 5xx (over 5 minutes) that raises an alert."
  type        = number
  default     = 0.02
}

# --- Tầng DB tự failover (Patroni) -------------------------------------------------------------------------------
variable "create_patroni" {
  description = "Tạo cụm DB Patroni 2 node ở 2 zone + witness etcd ở zone thứ ba + load balancer nội bộ. Mặc định tắt: bật khi đã có image Patroni và secret."
  type        = bool
  default     = false
}

variable "patroni_zones" {
  description = "Hai zone chứa hai node DB (cùng region). Phải khác nhau: replica cùng zone với primary không bảo hiểm được mất zone."
  type        = list(string)
  default     = ["asia-southeast1-a", "asia-southeast1-b"]

  validation {
    condition     = length(var.patroni_zones) == 2 && length(toset(var.patroni_zones)) == 2
    error_message = "patroni_zones cần đúng 2 zone KHÁC NHAU."
  }
}

variable "patroni_witness_zone" {
  description = "Zone của VM witness etcd (thành viên đa số thứ ba). Phải khác cả hai zone DB."
  type        = string
  default     = "asia-southeast1-c"

  validation {
    condition     = !contains(var.patroni_zones, var.patroni_witness_zone)
    error_message = "patroni_witness_zone phải khác các zone DB, nếu không mất một zone là mất cả đa số etcd."
  }
}

variable "patroni_machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "patroni_witness_machine_type" {
  type    = string
  default = "e2-small"
}

variable "patroni_disk_gb" {
  description = "Đĩa dữ liệu mỗi node DB (tồn tại độc lập với VM, có snapshot hằng ngày). Primary hiện tại: ~156 MB dữ liệu."
  type        = number
  default     = 50
}

variable "patroni_image" {
  description = "Image Patroni (ops/patroni/Dockerfile) trong Artifact Registry. Ghim tag hoặc digest."
  type        = string
  default     = ""

  validation {
    condition     = !var.create_patroni || var.patroni_image != ""
    error_message = "create_patroni = true cần patroni_image."
  }
}

variable "patroni_etcd_image" {
  type    = string
  default = "quay.io/coreos/etcd:v3.5.17"
}

variable "patroni_service_account_email" {
  description = "Service account của node DB: đọc secret Patroni và kéo image. Tách khỏi service account của app VM để app không đọc được mật khẩu replication."
  type        = string
  default     = ""

  validation {
    condition     = !var.create_patroni || var.patroni_service_account_email != ""
    error_message = "create_patroni = true cần patroni_service_account_email."
  }
}

variable "patroni_env_secret" {
  description = "Secret Manager secret id chứa PATRONI_SUPERUSER_PASSWORD và PATRONI_REPLICATION_PASSWORD (dạng KEY=VALUE mỗi dòng). Giá trị nạp tay, không nằm trong Terraform."
  type        = string
  default     = "vota-ha-patroni-env"
}

variable "patroni_clone_from_host" {
  description = "IP private của primary hiện tại, CHỈ dùng lúc di trú lần đầu (node đầu tiên clone bằng pg_basebackup). Xoá sau khi cụm đã chạy."
  type        = string
  default     = ""
}

variable "db_client_tags" {
  description = "Network tag BỔ SUNG được nối tới Postgres qua load balancer nội bộ. App VM của nhóm HA và job cào (tag vota-crawler) luôn được phép."
  type        = list(string)
  default     = []
}

# --- Cảnh báo job cào (chạy bằng cron trên VM) ---
variable "crawler_alerts_enabled" {
  description = "Bật cảnh báo catalog không đổi / job không chạy / lượt thất bại (cron trên VM phát catalog.freshness từ bản crawler mới). Chỉ bật SAU KHI crawler bản có catalog.freshness đã deploy, nếu không cảnh báo vắng mặt kêu giả."
  type        = bool
  default     = false
}
