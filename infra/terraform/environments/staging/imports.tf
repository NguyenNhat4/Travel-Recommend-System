# Adopt the hand-made staging resources into state. Import blocks are idempotent:
# once a resource is in state, the block is a no-op. None of these imports changes
# the real resource; only the resources in addresses.tf and the deletion_protection
# flags are created or updated (see README).
import {
  to = google_compute_instance.db_primary
  id = "projects/${var.project_id}/zones/${var.zone}/instances/${var.db_primary_vm_name}"
}

import {
  to = google_compute_instance.app
  id = "projects/${var.project_id}/zones/${var.zone}/instances/${var.app_vm_name}"
}

import {
  to = google_compute_firewall.vota_backend_8000
  id = "projects/${var.project_id}/global/firewalls/vota-backend-8000"
}

import {
  to = google_compute_firewall.vota_public_backend_8000
  id = "projects/${var.project_id}/global/firewalls/vota-public-backend-8000"
}

import {
  to = google_compute_firewall.vota_monitor_8765
  id = "projects/${var.project_id}/global/firewalls/vota-monitor-8765"
}

import {
  to = google_compute_firewall.vota_web_http_https
  id = "projects/${var.project_id}/global/firewalls/vota-web-http-https"
}
