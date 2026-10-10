# Sửa lỗi đăng nhập trên praxis.io.vn: Redis URL sai dạng xác thực

- Ngày: 2026-10-09
- Tác giả: Khoa15 / Claude (agent)
- Trạng thái: đã sửa; E2E đăng ký/đăng nhập do người vận hành tự thực hiện (agent không tạo tài khoản trên domain công khai)
- Phạm vi: Secret `vota-ha-backend-env` version 12; VM app (`/etc/vota/frontend.env`, `/etc/vota/backend.env`); container frontend/backend

## Triệu chứng

- Frontend log: `bff.session.store` outcome=error, `WRONGPASS invalid username-password pair`, tăng liên tục.
- `GET /api/auth/session` trên domain trả `000` (không có phản hồi).

## Nguyên nhân

- `AUTH_REDIS_URL`, `ITINERARY_REDIS_URL`, `BOOKING_REDIS_URL` có dạng `redis://<auth-string>@host:6379/…`. Auth string của Memorystore `vota-ha-redis` nằm ở vị trí username, không có password. Đã so sánh bằng hash: auth string khớp đúng.
- Client `redis` (node-redis, frontend) gửi AUTH sai, nên bị từ chối. Client redis-py của backend lại chạy được với dạng này, nên lỗi bị che cho đến khi frontend đi qua được session store.
- Khi frontend đã đi qua được, backend bị `AuthenticationError` ở `POST /api/v1/auth/session` vì chính nó cũng dùng dạng sai. Đây là lỗi thứ hai, cùng nguyên nhân.

## Cách sửa

1. Secret `vota-ha-backend-env` version 12: ba khóa Redis đổi sang dạng `redis://:<auth-string>@host:6379/…`. Các khóa khác giữ nguyên. Version 11 vẫn enabled để rollback.
2. Trên từng VM app: sửa `SESSION_REDIS_URL` trong `/etc/vota/frontend.env` và ba khóa Redis trong `/etc/vota/backend.env` (bản sao `*.pre-redis-fix`). Dùng `docker compose up -d --force-recreate` để container nhận env mới (`docker restart` không nạp lại `env_file`).
3. VM `bh1j` bị MIG autohealing tạo lại trong lúc backend khởi động lại (RECREATING → VERIFYING). VM mới đọc secret version 12 nên dùng dạng đúng ngay.

## Kiểm chứng

- `https://praxis.io.vn/api/auth/session` → 200 `{"state":"anonymous",...}`.
- `https://praxis.io.vn/health/ready` → 200; `/api/v1/search` → 200.
- Trên `vota-ha-app-tpjz` trong 5 phút sau sửa: WRONGPASS = 0, AuthenticationError = 0, 5xx ở `auth/session` = 0.

## Còn lại

- E2E đăng ký và đăng nhập trên `https://praxis.io.vn`: người vận hành tự thực hiện, agent không tạo tài khoản trên domain công khai.
- Xác nhận `bh1j` vào LB HEALTHY sau khi tạo lại (đang VERIFYING lúc ghi entry).
- Dọn các file `*.pre-redis-fix` trên VM sau khi ổn định.
- Cấu hình `frontend.env`/`backend.env` cũ trên VM tpjz vẫn được giữ đến khi VM được thay.
