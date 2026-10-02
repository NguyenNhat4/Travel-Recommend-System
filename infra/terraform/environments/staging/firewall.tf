# Existing firewall rules, adopted unchanged. The 8000 and 8765 rules are scoped to
# the app VM's service account, so they do not expose the DB VMs. The default-allow-*
# rules (internal, ssh, icmp) stay outside Terraform; the replica relies on
# default-allow-internal to reach the primary on 5432.
locals {
  network = "projects/${var.project_id}/global/networks/default"
}

resource "google_compute_firewall" "vota_backend_8000" {
  name                    = "vota-backend-8000"
  network                 = local.network
  direction               = "INGRESS"
  priority                = 1000
  source_ranges           = ["0.0.0.0/0"]
  target_service_accounts = [var.app_service_account_email]

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }
}

# Duplicate of vota-backend-8000; kept as is until the duplicate is removed on purpose.
resource "google_compute_firewall" "vota_public_backend_8000" {
  name                    = "vota-public-backend-8000"
  network                 = local.network
  direction               = "INGRESS"
  priority                = 1000
  source_ranges           = ["0.0.0.0/0"]
  target_service_accounts = [var.app_service_account_email]

  allow {
    protocol = "tcp"
    ports    = ["8000"]
  }
}

resource "google_compute_firewall" "vota_monitor_8765" {
  name                    = "vota-monitor-8765"
  network                 = local.network
  direction               = "INGRESS"
  priority                = 1000
  source_ranges           = ["0.0.0.0/0"]
  target_service_accounts = [var.app_service_account_email]

  allow {
    protocol = "tcp"
    ports    = ["8765"]
  }
}

resource "google_compute_firewall" "vota_web_http_https" {
  name          = "vota-web-http-https"
  description   = "Public HTTP/HTTPS for the V-OTA frontend via Caddy"
  network       = local.network
  direction     = "INGRESS"
  priority      = 1000
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["vota-web"]

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }
}
