# Webhook Stripe đi thẳng từ nginx tới backend

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/stripe-webhook-frontend-to-backend
- Trạng thái: hoàn thành (code và nginx đã kiểm cục bộ; chưa deploy lên VM staging-ha, chưa đặt endpoint trong Stripe Dashboard)
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-09-24-trien-khai-booking-thanh-toan-stripe.md` (plan `docs/plan/2026-09-24-booking-thanh-toan-stripe.md`, rủi ro 1), `2026-10-13-slot-ghi-de-url-backend-theo-port.md`, `2026-10-12-sua-reload-proxy-slot.md` (dang dở, cùng sửa `slot-deploy.sh`)

## Mục tiêu

Stripe gọi `https://praxis.io.vn/api/v1/payments/stripe/webhook`. Backend đã xử lý webhook, nên chỉ cần đường tới đó. Đường qua Next.js (BFF) không dùng được: `proxyToBackend` kiểm CSRF cho mọi POST, còn Stripe không gửi `Origin`, `Referer` hay `X-CSRF-Token`, nên `csrfFailure` (`src/frontend/src/services/server/bffSession.ts`) trả `403 CSRF_FAILED` trước khi tới backend. Kết luận này đọc từ code, chưa chạy trên staging.

Người dùng chọn phương án C: nginx đưa thẳng request tới backend của slot đang hoạt động, không qua Next.js. Đây là đường mà `docs/prd/architecture.md` §5 điểm 6 đã ghi ("không qua BFF"), nên không cần sửa PRD.

## File thay đổi

- `infra/terraform/environments/staging-ha/slot-deploy.sh` — sửa:
  - Header: thêm dòng bố cục cho đường webhook.
  - Hằng `BACKEND_UPSTREAM="$PROXY_DIR/backend-upstream.conf"`.
  - Template nginx: `upstream vota_backend` (include `backend-upstream.conf`) và `location = /api/v1/payments/stripe/webhook` với `limit_except POST { deny all; }`, `proxy_pass http://vota_backend`, đặt `Host` và `X-Request-ID`. Không tắt chuyển body hay header.
  - `write_upstream` nhận thêm `$2` = cổng backend, ghi cả `upstream.conf` lẫn `backend-upstream.conf`. Sáu chỗ gọi đều truyền `"$BACKEND_PORT"` sau `slot_ports`.
  - Hàm mới `seed_backend_upstream`, gọi ở cuối `write_files`: nếu file chưa có thì ghi cổng backend theo slot đang phục vụ (8001/8002), hoặc 8000 với VM kiểu cũ.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — thêm: `StripeWebhookRoute` (5 test cấu trúc) và `BackendUpstreamFiles` (3 test chạy thật `write_upstream` và `seed_backend_upstream` trên thư mục tạm).
- `docs/guide/van-hanh-cd-staging-ha.md` — sửa: mục "Trên VM" có một gạch đầu dòng về đường webhook; lệnh kiểm tra và "Trạng thái đúng" có `backend-upstream.conf`.
- `docs/plan/2026-09-24-booking-thanh-toan-stripe.md` — sửa: rủi ro 1 ghi kết quả đã chốt.
- `history/2026-10-13-stripe-webhook-nginx-truc-tiep.md` — thêm: entry này.

Không đổi: backend, frontend, contract OpenAPI, PRD, DDL, secret `STRIPE_WEBHOOK_SECRET`.

## Quyết định

- **Chọn nginx trực tiếp (C), không thêm route Next.js (B).** Khớp PRD `docs/prd/architecture.md` §5 điểm 6 và plan booking Q7 ("Stripe gọi thẳng FastAPI"). Nếu chọn B thì phải sửa PRD trước theo `AGENTS.md` mục 8.
- **Tách `backend-upstream.conf` khỏi `upstream.conf`.** `detect_active` và các kiểm tra cũ vẫn đọc `upstream.conf`, không đổi. Nginx cần hai khối `upstream` với hai `server` khác nhau.
- **Ghi cổng backend cùng lúc với cổng frontend.** Webhook đổi slot trong cùng một lần `nginx -s reload` với frontend, nên không lệch giữa hai đường.
- **Seed `backend-upstream.conf` khi thiếu.** VM đang chạy bản trước chưa có file này, nhưng `nginx.conf` mới đã include nó. `prepare` có thể đợi tới `READY_TIMEOUT` (600 s) giữa lúc ghi `nginx.conf` và lúc `switch`. Nếu VM reboot trong khoảng đó, `ensure_proxy` sẽ khởi động nginx với file thiếu và proxy không lên.
- **`limit_except POST`.** Stripe chỉ gửi POST. Mọi method khác bị nginx từ chối 403, không tới backend.
- **Không xác thực ở nginx.** Backend kiểm `Stripe-Signature` trên body gốc (`StripePaymentGateway.parse_webhook`), nên nginx chỉ chuyển tiếp.
- **Tài liệu `so-do-luong-dat-cho-thanh-toan.md`** đã ghi BFF "không bao giờ" nhận webhook (cột "Không bao giờ làm"), phù hợp với phương án này, nên không sửa.

## Kiểm tra

- `bash -n infra/terraform/environments/staging-ha/slot-deploy.sh`: OK.
- `python3 -m pytest infra/terraform/environments/staging-ha/tests/test_slot_deploy.py`: 54 passed, 2 failed. Hai test lỗi là `RollVisitsEveryVm::test_every_running_vm_is_prepared_switched_and_checked` và `test_failed_prepare_aborts_everywhere_and_switches_nothing`. Lỗi có sẵn trước thay đổi này: `scripts/roll-staging-ha-app-slots.sh:106` dùng `mapfile`, bash 3.2 của macOS không có. Máy này chạy `bash` 3.2. Chưa chạy lại trên Linux/CI.
- nginx thật: render đúng heredoc `NGINXCONF` của script, chạy `nginx:1.27-alpine` với upstream trỏ tới backend/frontend giả (Python, ghi lại body và header). `nginx -t` OK. Kết quả 10/10 PASS:
  - webhook POST tới backend blue; body đúng từng byte (sha256 khớp, có khoảng trắng và xuống dòng); `Stripe-Signature` nguyên vẹn;
  - POST có Cookie, không có `Origin`, vẫn tới backend;
  - GET tới webhook bị 403, không tới backend;
  - `/api/v1/cart` và `/_next/static/...` vẫn về frontend;
  - đổi `backend-upstream.conf` sang green rồi `nginx -t` và `-s reload`: webhook tới backend green.
- Lệnh chạy lại: render heredoc từ script vào thư mục tạm, chạy `docker run nginx:1.27-alpine` với thư mục đó gắn tại `/etc/vota/proxy`, rồi gửi request như trên.

Chưa làm: chưa chạy trên VM staging-ha, chưa gọi webhook thật từ Stripe.

## Còn lại / rủi ro

- **Deploy:** `slot-deploy.sh` đã nằm trong bộ lọc của `staging-ha-app-cd.yml` (`slot_key`), nên lần deploy app kế tiếp sẽ đẩy script mới lên VM qua metadata và roll. Sau deploy, kiểm:
  - `curl -i -X POST https://praxis.io.vn/api/v1/payments/stripe/webhook` không kèm chữ ký phải ra `400 INVALID_WEBHOOK_SIGNATURE` từ backend (không phải `403 CSRF_FAILED`);
  - `/etc/vota/proxy/backend-upstream.conf` trỏ đúng cổng của slot trong `/etc/vota/active-slot`.
- **Việc người làm:** trong Stripe Dashboard (test mode) đặt endpoint `https://praxis.io.vn/api/v1/payments/stripe/webhook`. Signing secret của endpoint đó phải khớp `STRIPE_WEBHOOK_SECRET` trong Secret Manager `vota-ha-backend-env`. Agent không đọc hay đổi giá trị secret.
- **Xung đột:** `khoa/fix-slot-proxy-reload` (`2026-10-12-sua-reload-proxy-slot.md`) và `khoa/cd-zero-downtime-slot` cũng sửa `slot-deploy.sh`, đang dở. Khi merge cần gộp `write_upstream` và template nginx cẩn thận.
- **Bỏ qua BFF:** webhook không còn đi qua `bffSession`, nên không có kiểm tra CSRF, phiên hay log `bff.*` cho đường này. Backend vẫn kiểm chữ ký và ghi `payment.webhook.received`.
- Thay đổi chưa commit.
