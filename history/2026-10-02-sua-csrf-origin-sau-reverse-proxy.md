# Sửa CSRF_FAILED do so Origin với request.url sau reverse proxy

- Ngày: 2026-10-02
- Tác giả: Khoa15 / Claude Code
- Nhánh: khoa/fix-monitoring-xy-threshold
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Request ghi từ frontend tới BFF (ví dụ `POST /api/auth/register` trên https://v-ota.duckdns.org) bị `403 CSRF_FAILED`. Spec: `docs/spec/hop-dong-tich-hop-auth.md` §7 (lớp 3: `Origin` phải thuộc allowlist).

## File thay đổi

- `src/frontend/src/services/server/bffSession.ts` — sửa: `allowedOrigins()` khi `ALLOWED_ORIGINS` trống suy allowlist từ `X-Forwarded-Host`/`Host` + `X-Forwarded-Proto` (cộng `request.url.origin`) thay vì chỉ `request.url`.
- `src/frontend/tests/api/bff-auth.test.ts` — sửa: thêm test hồi quy Origin khớp Host khác `request.url`; Origin lạ vẫn 403.
- `ops/docker-compose.backend-vm.yml` — sửa: frontend nhận `ALLOWED_ORIGINS: ${ALLOWED_ORIGINS:-}`.
- `scripts/deploy-frontend-vm.sh` — sửa: thêm `read_backend_optional_value`, đọc `ALLOWED_ORIGINS` từ `/etc/vota/backend.env` (khoá tuỳ chọn, thiếu thì rỗng, không dừng deploy) và export cho compose.
- `scripts/tests/test-backend-vm-cd-sync.sh` — sửa: kiểm compose và deploy script có truyền `ALLOWED_ORIGINS`.

## Quyết định

- Nguyên nhân: `csrfFailure` so `Origin` với `new URL(request.url).origin`. Next chuẩn hoá `request.url` về hostname lúc khởi động (`localhost` ở dev, `0.0.0.0` trong container với `HOSTNAME=0.0.0.0`), nên truy cập qua domain thật, 127.0.0.1 hay cổng khác đều lệch → `reason: origin`. `ops/docker-compose.backend-vm.yml` (production) không đặt `ALLOWED_ORIGINS`, nên production dính lỗi này.
- Tái hiện trên production bằng curl: `GET /api/auth/session` rồi `POST /api/auth/register` với đúng token và `Origin: https://v-ota.duckdns.org` → 403.
- Trình duyệt không giả được `Host`, nên allowlist suy từ Host vẫn giữ nguyên ý nghĩa lớp kiểm Origin. Khi `ALLOWED_ORIGINS` được đặt thì dùng đúng danh sách đó như cũ.
- Không lệch PRD: hiện thực đúng §7.

## Kiểm tra

- Dev local: Origin 127.0.0.1 + Host 127.0.0.1 trước sửa → 403 `reason: origin`.
- `bash scripts/tests/test-backend-vm-cd-sync.sh`: pass; `bash -n scripts/deploy-frontend-vm.sh`: ok; thử hàm đọc khoá tuỳ chọn với file mẫu: có khoá trả giá trị, thiếu khoá trả rỗng, rc=0.
- `vitest run tests/api`: 22/22 pass. Chưa redeploy production nên chưa xác nhận lại trên https://v-ota.duckdns.org.
- `tsc --noEmit` có lỗi sẵn có không liên quan (`WidgetProgress` lệch hoa/thường tên file).

## Còn lại / rủi ro

- Cần deploy frontend rồi thử lại `/register`. Cần Caddy chuyển `Host`/`X-Forwarded-Proto` (mặc định có).
- Frontend container trước đây không nhận `ALLOWED_ORIGINS` từ `backend.env` (compose không có `env_file`, deploy script chỉ đọc 2 khoá). Đã sửa; cần secret `GCE_BACKEND_ENV_SECRET` có `ALLOWED_ORIGINS=https://v-ota.duckdns.org` (phân tách bằng dấu phẩy nếu nhiều origin) — đặt sai/thiếu thì BFF vẫn dùng nhánh suy từ Host.
- `docker-compose.yml` (local) cố định ALLOWED_ORIGINS là localhost; chưa đổi.
