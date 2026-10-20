# HTTPS origin cho praxis.io.vn bằng chứng chỉ Cloudflare Origin CA

- Ngày: 2026-10-09
- Tác giả: Khoa15 / Claude (agent)
- Trạng thái: đã hoàn thành (GCP); SSL mode Cloudflare cần xác nhận là Full (strict)
- Phạm vi: `infra/terraform/environments/staging-ha` (secrets.tf, variables.tf, main.tf, staging-ha.tfvars gitignored), Secret Manager

## Nguyên nhân

`praxis.io.vn` được Cloudflare proxy và trả 525: LB `vota-ha-fr` chỉ có listener HTTP :80, không có 443 để Cloudflare bắt tay TLS.

## Thay đổi

1. Secret Manager: `praxis-origin-cert` và `praxis-origin-key` (Cloudflare Origin CA, hết hạn 2041). Đã kiểm khớp khoá công khai giữa cert và key trước khi upload. File PEM local đã xoá.
2. Terraform (thêm mới, không sửa tài nguyên hiện có):
   - `data.google_secret_manager_secret_version.origin_cert` / `origin_key` (bật bằng `origin_tls_enabled`)
   - `google_compute_ssl_certificate.origin`
   - `google_compute_target_https_proxy.origin` (cùng URL map `vota-ha-app`)
   - `google_compute_global_forwarding_rule.origin_https` (:443 trên IP `34.111.252.145`)
   - `origin_tls_enabled = true` trong `staging-ha.tfvars`.
   Plan: 3 add, 0 change, 0 destroy. Apply thành công.

## Kiểm chứng

- Forwarding rule `vota-ha-origin-fr` mất khoảng 4 phút để phục vụ (lúc đầu 000/502/404).
- Origin HTTPS (`--resolve praxis.io.vn:443:34.111.252.145`): `/health/ready` 200.
- Qua Cloudflare: `https://praxis.io.vn/health/ready` 200; `/api/v1/search` 200.

## Còn lại

- Cloudflare → SSL/TLS → Overview: đặt **Full (strict)**. Chứng chỉ Origin CA được Cloudflare tin cậy cho chế độ này.
- Tương lai: đặt `domain` trong Terraform không cần, vì đang dùng chứng chỉ tự quản.
