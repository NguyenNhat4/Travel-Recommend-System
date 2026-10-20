# Đổi domain công khai sang praxis.io.vn (cấu hình, một phần)

- Ngày: 2026-10-09
- Tác giả: Khoa15 / Claude (agent)
- Trạng thái: dang dở (chờ DNS/Cloudflare; xem "Còn lại")
- Phạm vi: secret `vota-ha-backend-env` (version 11), `infra/monitoring` (uptime check)

## Thay đổi đã làm

1. Secret `vota-ha-backend-env` version 11: `PUBLIC_WEB_URL`, `CORS_ORIGINS`, `ALLOWED_ORIGINS` = `https://praxis.io.vn` (trước: `https://v-ota.duckdns.org`). Các khóa khác giữ nguyên. Kiểm tra bằng cách chỉ đổi 3 khóa đó.
2. `infra/monitoring/staging.tfvars` (gitignored): `uptime_host = "praxis.io.vn"`. Apply: uptime check `vota-staging readiness` được tạo lại với host mới, SLO và dashboard liên quan được cập nhật.

## Chưa đổi (có chủ đích)

- `infra/terraform/environments/staging-ha` biến `domain` vẫn trống (HTTP LB). Đặt `domain = "praxis.io.vn"` sẽ tạo managed SSL cert và HTTPS proxy, cert chỉ cấp được khi DNS của domain trỏ về LB `34.111.252.145`.
- Trạng thái DNS khi kiểm tra: `praxis.io.vn` trỏ về Cloudflare (104.21.93.220, 172.67.215.83). `https://praxis.io.vn/` trả **525** (Cloudflare không bắt tay TLS được với origin). `v-ota.duckdns.org` không truy cập được (000).

## Lưu ý

- Secret chỉ có hiệu lực khi VM app khởi động (startup script đọc secret lúc boot). Các VM đang chạy vẫn dùng giá trị cũ cho đến khi được thay (rolling update hoặc restart VM).
- Uptime check `praxis.io.vn` sẽ báo lỗi cho đến khi origin của Cloudflare phục vụ được HTTPS.

## Còn lại

- Người có quyền DNS/Cloudflare: trỏ `praxis.io.vn` về origin đúng (LB `34.111.252.145` hoặc cấu hình origin cert trên Cloudflare), rồi xác nhận `https://praxis.io.vn/health/ready` = 200.
- Quyết định có đặt `domain = "praxis.io.vn"` trong Terraform (HTTPS LB + managed cert) sau khi DNS đúng.
- Áp dụng secret mới cho VM app: rolling update MIG `vota-ha-app`.
