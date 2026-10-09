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

locals {
  crawler_enabled = var.create_crawler_vm
  crawler_name    = "${var.name_prefix}-crawler"
  crawler_tag     = "vota-crawler"
}

resource "google_compute_instance" "crawler" {
  count                     = local.crawler_enabled ? 1 : 0
  name                      = local.crawler_name
  zone                      = var.crawler_zone
  machine_type              = var.crawler_machine_type
  tags                      = [local.crawler_tag]
  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      image = var.boot_image
      # 15 GB: image crawler ~3 GB, dữ liệu lượt giữ 2 lượt ~1 GB; xem history/2026-10-09-crawler-disk-15gb.md
      size = 15
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
}

output "crawler_instance_name" {
  description = "Tên VM job cào; CD cài cron lên VM này qua IAP SSH."
  value       = try(google_compute_instance.crawler[0].name, null)
}
