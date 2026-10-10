# Bastion cho đội đọc/ghi DB: một VM không có IP public, chỉ nhận SSH qua IAP, và là đường duy nhất
# (ngoài app/crawler) được mở tới cổng 5432 của cụm Patroni. Tắt mặc định (create_bastion = false).
# Quyền truy cập DB của từng người là role Postgres riêng, không phải quyền trên VM này.
# Phạm vi và điều kiện: docs/prd/update/2026-10-09-team-db-access.md (chờ chốt). Chưa apply.

variable "create_bastion" {
  description = "Tạo bastion cho đội DB. Chỉ bật sau khi đề xuất docs/prd/update/2026-10-09-team-db-access.md đã chốt."
  type        = bool
  default     = false
}

variable "bastion_zone" {
  description = "Zone của bastion. Nên khác zone chứa leader để không phụ thuộc một zone."
  type        = string
  default     = "asia-southeast1-c"
}

variable "bastion_machine_type" {
  description = "Máy của bastion. Chỉ là điểm đi qua TCP, không chạy workload."
  type        = string
  default     = "e2-micro"
}

locals {
  bastion_enabled = var.create_bastion
  bastion_tag     = "${var.name_prefix}-bastion"
}

resource "google_compute_instance" "bastion" {
  count        = local.bastion_enabled ? 1 : 0
  name         = "${var.name_prefix}-bastion"
  zone         = var.bastion_zone
  machine_type = var.bastion_machine_type
  tags         = [local.bastion_tag]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    # Không có access_config: không có IP public.
  }

  # Không gắn service account: bastion không cần quyền GCP nào để chuyển tiếp TCP.
  metadata = {
    enable-oslogin = "TRUE"
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
}

# SSH vào bastion chỉ từ dải IAP TCP forwarding.
resource "google_compute_firewall" "bastion_iap_ssh" {
  count         = local.bastion_enabled ? 1 : 0
  name          = "${var.name_prefix}-bastion-iap-ssh"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]
  target_tags   = [local.bastion_tag]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# Bastion tới cụm Patroni (ILB 10.148.0.34 chuyển tới leader). Đây là quy tắc bổ sung, không sửa
# quy tắc patroni_clients hiện có.
resource "google_compute_firewall" "bastion_to_pg" {
  count       = local.bastion_enabled && local.patroni_enabled ? 1 : 0
  name        = "${var.name_prefix}-bastion-to-pg"
  network     = var.network
  direction   = "INGRESS"
  source_tags = [local.bastion_tag]
  target_tags = [local.patroni_tag]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

output "bastion_name" {
  description = "Tên bastion (nếu create_bastion = true). Dùng với gcloud compute ssh --tunnel-through-iap."
  value       = local.bastion_enabled ? google_compute_instance.bastion[0].name : null
}
