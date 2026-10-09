# VM job cào (crawler) của staging-ha. Một VM đơn, không thuộc MIG: job chạy bằng cron (scripts/install-vota-cron.sh),
# được CD cài qua IAP SSH (.github/workflows/staging-ha-cd.yml). Chỉ một VM được phép ghi catalog, nên không có
# bản sao thứ hai trong root này.
# Tag `vota-crawler` là tag mà patroni.tf đã cho phép tới cổng 5432 của Postgres; đừng đổi tên mà không sửa patroni.tf.
# Không có IP public: job cào gọi ra ngoài qua Cloud NAT (variables.tf create_nat).

variable "create_crawler_vm" {
  description = "Tạo VM job cào staging-ha. Bật sau khi chuyển crawler từ VM staging cũ (xem history/2026-10-09-staging-ha-cd-tu-dong.md)."
  type        = bool
  default     = false
}

variable "crawler_zone" {
  description = "Zone của VM job cào."
  type        = string
  default     = "asia-southeast1-a"
}

variable "crawler_machine_type" {
  description = "Máy của VM job cào: e2-medium như VM staging cũ. Quota là CPUS_ALL_REGIONS (toàn project), không phải theo region."
  type        = string
  default     = "e2-medium"
}

variable "crawler_stop_schedule" {
  description = "Lịch tắt VM job cào (cron, theo crawler_schedule_timezone). Mặc định 23:59 hằng ngày."
  type        = string
  default     = "59 23 * * *"
}

variable "crawler_start_schedule" {
  description = "Lịch bật VM job cào (cron, theo crawler_schedule_timezone). Mặc định 08:30 hằng ngày."
  type        = string
  default     = "30 8 * * *"
}

variable "crawler_schedule_timezone" {
  description = "Múi giờ áp dụng cho crawler_stop_schedule và crawler_start_schedule."
  type        = string
  default     = "Asia/Ho_Chi_Minh"
}

locals {
  crawler_enabled = var.create_crawler_vm
  crawler_name    = "${var.name_prefix}-crawler"
  crawler_tag     = "vota-crawler"
}

# Lịch bật/tắt riêng cho VM job cào. Chỉ áp dụng cho VM đơn này, không dùng cho MIG app.
resource "google_compute_resource_policy" "crawler_schedule" {
  count  = local.crawler_enabled ? 1 : 0
  name   = "${var.name_prefix}-crawler-schedule"
  region = var.region

  instance_schedule_policy {
    vm_start_schedule {
      schedule = var.crawler_start_schedule
    }
    vm_stop_schedule {
      schedule = var.crawler_stop_schedule
    }
    time_zone = var.crawler_schedule_timezone
  }
}

resource "google_compute_instance" "crawler" {
  count                     = local.crawler_enabled ? 1 : 0
  name                      = local.crawler_name
  zone                      = var.crawler_zone
  machine_type              = var.crawler_machine_type
  tags                      = [local.crawler_tag]
  allow_stopping_for_update = true
  resource_policies         = [google_compute_resource_policy.crawler_schedule[0].self_link]

  boot_disk {
    initialize_params {
      image = var.boot_image
      size  = 30
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    # Không có access_config: không có IP public.
  }

  service_account {
    email  = var.app_service_account_email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    startup-script         = file("${path.module}/crawler-startup.sh")
    google-logging-enabled = "true"
  }

  depends_on = [google_compute_router_nat.egress]

  # Key SSH của runner CD được thêm vào metadata ngoài Terraform (cài cron qua IAP SSH). Không để plan xóa nó.
  lifecycle {
    ignore_changes = [metadata["ssh-keys"]]
  }
}

output "crawler_instance_name" {
  description = "Tên VM job cào; CD cài cron lên VM này qua IAP SSH."
  value       = try(google_compute_instance.crawler[0].name, null)
}
