# Tên ổn định cho DB: backend dùng db.vota.internal thay vì IP hay tunnel SSH. Failover chỉ đổi bản ghi này
# (ops/promote-db-replica.sh), không phải sửa env hay thay VM. TTL ngắn để client nhận IP mới trong ~30 giây.
resource "google_dns_managed_zone" "internal" {
  name        = "${var.name_prefix}-internal"
  dns_name    = var.internal_zone_dns_name
  description = "Private names for V-OTA data services"
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = "projects/${var.project_id}/global/networks/${var.network}"
    }
  }
}

resource "google_dns_record_set" "db" {
  managed_zone = google_dns_managed_zone.internal.name
  name         = "db.${var.internal_zone_dns_name}"
  type         = "A"
  ttl          = 30
  rrdatas      = [var.db_primary_ip]

  # promote-db-replica.sh đổi rrdatas ngoài Terraform khi failover; không để apply kế tiếp trả về primary cũ.
  lifecycle {
    ignore_changes = [rrdatas]
  }
}

resource "google_dns_record_set" "db_replica" {
  count        = var.db_replica_ip == "" ? 0 : 1
  managed_zone = google_dns_managed_zone.internal.name
  name         = "db-replica.${var.internal_zone_dns_name}"
  type         = "A"
  ttl          = 30
  rrdatas      = [var.db_replica_ip]

  lifecycle {
    ignore_changes = [rrdatas]
  }
}
