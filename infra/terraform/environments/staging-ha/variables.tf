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
  default     = "projects/debian-cloud/global/images/family/debian-12"
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
  description = "Số VM tối thiểu của nhóm app. Quy tắc chốt 2026-10-08: 1 VM tối thiểu, tối đa 2 VM. Mất VM duy nhất là mất dịch vụ app (chấp nhận có chủ đích)."
  type        = number
  default     = 1

  validation {
    condition     = var.min_replicas >= 1
    error_message = "min_replicas must be >= 1."
  }
}

variable "max_replicas" {
  description = "Số VM tối đa của nhóm app. 2 theo quy tắc chốt 2026-10-08 (ngân sách kết nối DB: 2 × 2 × 12 + 10 = 58 <= max_connections 100)."
  type        = number
  default     = 2

  validation {
    condition     = var.max_replicas >= var.min_replicas
    error_message = "max_replicas phải >= min_replicas."
  }
}

variable "cpu_target" {
  description = "Autoscaler target CPU utilization (0-1). Với min_replicas = 1 không còn đảm bảo sống sót khi mất VM; ràng buộc (N-1)/N đã gỡ theo quy tắc chốt 2026-10-08."
  type        = number
  default     = 0.9

  validation {
    condition     = var.cpu_target > 0 && var.cpu_target <= 1
    error_message = "cpu_target phải trong khoảng (0, 1]."
  }
}

variable "memory_target_percent" {
  description = "Autoscaler target memory percent_used (needs Ops Agent on the VM). 0 disables the memory signal."
  type        = number
  default     = 90

  validation {
    condition     = var.memory_target_percent >= 0 && var.memory_target_percent <= 100
    error_message = "memory_target_percent phải trong khoảng [0, 100]."
  }
}

variable "boot_to_ready_seconds" {
  description = "Thời gian từ lúc VM tạo đến lúc /health/ready = 200 (kéo image, nạp RecSys). Dùng cho cooldown autoscaler và initial_delay autohealing (không còn là min_ready_sec của rolling update từ 2026-10-09). Đã đo 2026-10-09 trên Debian 12: tạo VM -> startup.recsys.ready ~230 giây (2 lần, VM thử và VM MIG gsc1). Đặt 300 để có dự phòng ~25%."
  type        = number
  default     = 360

  validation {
    condition     = var.boot_to_ready_seconds >= 240
    error_message = "boot_to_ready_seconds < 240 thấp hơn thời gian boot-to-ready đã đo (~230 giây, Debian 12, 2026-10-09)."
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

variable "ci_runner_instance_name" {
  description = "VM chạy GitHub Actions runner tự host (mọi CI/CD chạy trên nó). Alert khi VM không gửi metric uptime."
  type        = string
  default     = "vota-ci-runner"
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

# Mẫu tối thiểu cho p95: dưới mức này p95 dựa trên quá ít request (đo 2026-10-14: 03:19 UTC chỉ 78–127 request/phút, p95 nhảy tới 3,2 s).
variable "alert_p95_min_requests" {
  description = "Tổng request LB trong 10 phút phải lớn hơn mức này thì mới cảnh báo p95 độ trễ. Đo 72 giờ: trung vị 175 request/10 phút, 5% cửa sổ thấp nhất dưới 46."
  type        = number
  default     = 100
}

variable "alert_5xx_ratio" {
  description = "Fraction of LB requests answered 5xx (over 5 minutes) that raises an alert."
  type        = number
  default     = 0.02
}

variable "alert_memory_percent" {
  description = "Memory used (percent) on any one app VM above this for 5 minutes raises an alert. Must stay above memory_target_percent: the autoscaler keeps memory near that target, so a threshold at or below it would fire during normal scaling."
  type        = number
  default     = 95
}

variable "alert_disk_percent" {
  description = "Disk used (percent, per device) on any one app VM above this for 5 minutes raises an alert."
  type        = number
  default     = 90
}

# Ngưỡng RAM, đĩa, CPU của cụm DB và job cào. Mức đặt trên đỉnh đo được 7 ngày gần nhất (2026-10-14), xem
# history/2026-10-14-canh-bao-tai-nguyen-db-va-crawler.md.
variable "alert_db_memory_percent" {
  description = "RAM đã dùng (%) trên một node DB (pg-a, pg-b) vượt mức này trong 10 phút thì báo. Đỉnh 7 ngày: 66,6%."
  type        = number
  default     = 85
}

variable "alert_db_disk_percent" {
  description = "Đĩa đã dùng (%) trên một thiết bị của một node DB vượt mức này trong 5 phút thì báo. Đỉnh 7 ngày: 19,5%."
  type        = number
  default     = 80
}

variable "alert_db_cpu_percent" {
  description = "CPU (%) của một node DB (pg-a, pg-b, pg-w) trung bình vượt mức này trong 15 phút thì báo. Đỉnh 7 ngày: 12,6%."
  type        = number
  default     = 70
}

variable "alert_crawler_memory_percent" {
  description = "RAM đã dùng (%) của VM job cào vượt mức này trong 10 phút thì báo. Đỉnh 7 ngày: 57,8%."
  type        = number
  default     = 85
}

variable "alert_crawler_disk_percent" {
  description = "Đĩa boot (%) của VM job cào vượt mức này trong 5 phút thì báo. Đĩa 15 GB, một image crawler khoảng 3 GB; đỉnh 7 ngày: 77,7%, nên mức 80% sát đỉnh."
  type        = number
  default     = 80
}

variable "alert_crawler_cpu_percent" {
  description = "CPU (%) của VM job cào vượt mức này liên tục trong alert_crawler_cpu_minutes phút thì báo. Mỗi lượt cào chạy khoảng 1 giờ ở gần 100%, nên ngưỡng thời gian phải dài hơn lượt bình thường."
  type        = number
  default     = 95
}

variable "alert_crawler_cpu_minutes" {
  description = "Số phút CPU của VM job cào phải liên tục trên alert_crawler_cpu_percent thì báo. Đặt 180: lượt cào bình thường chỉ kéo dài khoảng 1 giờ ở đỉnh."
  type        = number
  default     = 180
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
  description = "Network tag BỔ SUNG được nối tới Postgres qua load balancer nội bộ. App VM của nhóm HA và job cào (tag vota-crawler) luôn được phép. ci-runner: runner tự host chạy CD, cần tới Postgres để áp db/migrations (2026-10-12)."
  type        = list(string)
  default     = ["ci-runner"]
}

# --- Cảnh báo job cào (chạy bằng cron trên VM) ---
variable "crawler_alerts_enabled" {
  description = "Bật cảnh báo job không chạy (heartbeat catalog.due, phát ở mỗi tick cron) và lượt cào thất bại (run.end status=failed). Cả hai đã kiểm trên log thật (2026-10-12)."
  type        = bool
  default     = true
}

variable "crawler_late_alert_enabled" {
  description = "Bật cảnh báo catalog quá hạn (catalog.freshness state=late). Chỉ bật SAU KHI bản crawler có sửa freshness trong nhánh due (src/data_collection/fresh_catalog.py) đã build và deploy; bản đang chạy chưa phát dòng này đều mỗi tick."
  type        = bool
  default     = false
}

variable "origin_tls_enabled" {
  description = "Thêm listener HTTPS :443 trên LB bằng chứng chỉ Cloudflare Origin CA (Secret Manager). Dùng khi Cloudflare proxy với SSL mode Full (strict)."
  type        = bool
  default     = false
}

variable "origin_cert_secret" {
  description = "Secret Manager secret id chứa PEM chứng chỉ Origin CA."
  type        = string
  default     = "praxis-origin-cert"
}

variable "origin_key_secret" {
  description = "Secret Manager secret id chứa PEM private key của chứng chỉ Origin CA."
  type        = string
  default     = "praxis-origin-key"
}
