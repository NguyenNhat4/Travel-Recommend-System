# Chỉ tạo "vỏ" secret và quyền đọc; GIÁ TRỊ nạp tay (không bao giờ nằm trong Terraform hay state):
#   gcloud secrets versions add vota-ha-backend-env --data-file=backend.env
#   printf '%s' "$KEY" | gcloud secrets versions add vota-ha-weaviate-api-key --data-file=-
resource "google_secret_manager_secret" "backend_env" {
  secret_id = var.backend_env_secret

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "weaviate_api_key" {
  count     = var.create_weaviate ? 1 : 0
  secret_id = var.weaviate_api_key_secret

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "backend_env_reader" {
  secret_id = google_secret_manager_secret.backend_env.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.app_service_account_email}"
}

resource "google_secret_manager_secret_iam_member" "weaviate_key_reader" {
  count     = var.create_weaviate ? 1 : 0
  secret_id = google_secret_manager_secret.weaviate_api_key[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.app_service_account_email}"
}

# Instance template chỉ được tạo khi secret đã có phiên bản; thiếu thì plan dừng ngay, thay vì để VM boot rồi
# startup script thất bại và autohealing thay VM mãi. Lần apply đầu đặt require_secret_versions = false.
data "google_secret_manager_secret_version" "backend_env" {
  count  = var.require_secret_versions ? 1 : 0
  secret = google_secret_manager_secret.backend_env.id
}

data "google_secret_manager_secret_version" "weaviate_api_key" {
  count  = var.require_secret_versions && var.create_weaviate ? 1 : 0
  secret = google_secret_manager_secret.weaviate_api_key[0].id
}

# Cloudflare Origin CA certificate cho HTTPS origin (Cloudflare SSL mode Full (strict)). Nạp tay vào Secret Manager,
# không nằm trong Terraform. Bật bằng origin_tls_enabled = true.
data "google_secret_manager_secret_version" "origin_cert" {
  count  = var.origin_tls_enabled ? 1 : 0
  secret = var.origin_cert_secret
}

data "google_secret_manager_secret_version" "origin_key" {
  count  = var.origin_tls_enabled ? 1 : 0
  secret = var.origin_key_secret
}
