# Bastion cho đội DB: VM có IP public tĩnh, SSH bằng username + mật khẩu, chỉ được chuyển tiếp TCP tới
# ILB Patroni 10.148.0.34:5432. Không dùng IAP, không cần gcloud phía người dùng. Tắt mặc định (create_bastion = false).
# Quyền DB của từng người là role Postgres riêng, không phải quyền trên VM này.

variable "create_bastion" {
  description = "Tạo bastion cho đội DB."
  type        = bool
  default     = false
}

variable "bastion_zone" {
  description = "Zone của bastion."
  type        = string
  default     = "asia-southeast1-c"
}

variable "bastion_machine_type" {
  description = "Máy của bastion. Chỉ là điểm đi qua TCP, không chạy workload."
  type        = string
  default     = "e2-micro"
}

variable "bastion_public_ip" {
  description = "IP public tĩnh của bastion (đã đặt trước: 34.142.132.251)."
  type        = string
  default     = "34.142.132.251"
}

variable "bastion_ssh_source_ranges" {
  description = "IP/CIDR được phép SSH vào bastion (đặt trong tfvars, gitignored)."
  type        = list(string)
  default     = []
}

variable "bastion_password_hash" {
  description = "Hash SHA-512 (openssl passwd -6) của mật khẩu user bastion. Truyền qua TF_VAR_bastion_password_hash, không ghi vào tfvars. Mật khẩu gốc không đi vào Terraform."
  type        = string
  default     = ""
  sensitive   = true
}

locals {
  bastion_enabled = var.create_bastion
  bastion_tag     = "${var.name_prefix}-bastion"
  bastion_startup = <<-EOT
    #!/bin/bash
    set -euo pipefail
    MD=http://metadata.google.internal/computeMetadata/v1/instance/attributes
    H=$(curl -fs -H "Metadata-Flavor: Google" "$MD/bastion-password-hash")
    id bastion >/dev/null 2>&1 || useradd -m -s /bin/bash bastion
    echo "bastion:$H" | chpasswd -e
    cat > /etc/ssh/sshd_config.d/10-bastion.conf <<'CONF'
    PasswordAuthentication yes
    KbdInteractiveAuthentication no
    PermitRootLogin no
    MaxAuthTries 3
    LoginGraceTime 30
    Match User bastion
        PermitTTY no
        X11Forwarding no
        AllowAgentForwarding no
        AllowTcpForwarding local
        PermitOpen 10.148.0.34:5432
    CONF
    systemctl restart ssh
    apt-get update -qq
    apt-get install -y -qq fail2ban
    systemctl enable --now fail2ban
  EOT
}

resource "google_compute_instance" "bastion" {
  count        = local.bastion_enabled ? 1 : 0
  name         = "${var.name_prefix}-bastion"
  zone         = var.bastion_zone
  machine_type = var.bastion_machine_type
  tags         = [local.bastion_tag]
  # Lịch tắt 23:59 / bật 08:30 chung với các VM khác (scheduler.tf). IP tĩnh giữ nguyên qua các lần tắt bật.
  resource_policies = [google_compute_resource_policy.bastion_schedule[0].self_link]

  lifecycle {
    precondition {
      condition     = length(var.bastion_ssh_source_ranges) > 0 && var.bastion_password_hash != ""
      error_message = "Cần bastion_ssh_source_ranges và TF_VAR_bastion_password_hash."
    }
  }

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    access_config {
      nat_ip = var.bastion_public_ip
    }
  }

  # Không gắn service account: bastion không cần quyền GCP nào để chuyển tiếp TCP.
  # OS Login tắt trên bastion để đăng nhập bằng username + mật khẩu Linux (các VM khác vẫn bật OS Login).
  metadata = {
    enable-oslogin        = "FALSE"
    bastion-password-hash = var.bastion_password_hash
    startup-script        = local.bastion_startup
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
}

# SSH vào bastion từ các IP cho phép.
resource "google_compute_firewall" "bastion_ssh" {
  count         = local.bastion_enabled ? 1 : 0
  name          = "${var.name_prefix}-bastion-ssh"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = var.bastion_ssh_source_ranges
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
  description = "Tên bastion (nếu create_bastion = true)."
  value       = local.bastion_enabled ? google_compute_instance.bastion[0].name : null
}

output "bastion_ip" {
  description = "IP public của bastion (nếu create_bastion = true)."
  value       = local.bastion_enabled ? var.bastion_public_ip : null
}
