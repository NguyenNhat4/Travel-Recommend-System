# CDP clone

Service giả lập CDP, là **system of record** cho `events` và `profiles` (handbook §3, §6). Service nội bộ: chỉ Backend (qua `CdpClient`), seed và job gọi, bằng `X-Service-Token`. Web không bao giờ gọi trực tiếp.

- Nghiệp vụ, luồng dữ liệu, bù trừ `purchase`, rủi ro và phần chờ xác nhận: [`docs/spec/hop-dong-tich-hop-cdp.md`](../../docs/spec/hop-dong-tich-hop-cdp.md)
- Contract: [`src/shared/contracts/cdp-clone.openapi.yaml`](../shared/contracts/cdp-clone.openapi.yaml)
- Fixture: [`src/shared/mocks/cdp-clone`](../shared/mocks/cdp-clone/README.md)

> Bề mặt API là **tạm**, chưa có tài liệu API CDP thật của V-OTA (spec §11).

## Endpoint

| Endpoint | Mục đích |
|---|---|
| `POST /cdp/v1/events` | Ghi 1–100 event; một event sai thì không ghi event nào |
| `GET /cdp/v1/users/{cdpUserId}/events` | Lịch sử mới nhất trước; mặc định bỏ event đã huỷ |
| `PUT /cdp/v1/users/{cdpUserId}/events/{eventId}/cancellation` | Đánh dấu huỷ (bù trừ booking lỗi) |
| `GET` / `PUT /cdp/v1/profiles/{cdpUserId}` | Đọc / thay toàn bộ hồ sơ |

## Chạy

Từ repo root, Python ≥ 3.12:

```bash
pip install -r src/cdp_clone/requirements.txt
docker compose -f src/cdp_clone/docker-compose.yml up -d        # Postgres ở 127.0.0.1:5433
cp src/cdp_clone/.env.example .env                              # điền CDP_SERVICE_TOKEN (≥ 32 ký tự)
alembic -c src/cdp_clone/alembic.ini upgrade head
uvicorn src.cdp_clone.app.main:app --host 127.0.0.1 --port 8100
```

`CDP_SERVICE_TOKEN` phải trùng giá trị cấu hình ở Backend. Thiếu token thì service không khởi động. Không mở cổng 8100 ra ngoài mạng nội bộ.

Test (SQLite in-memory, không cần Postgres):

```bash
python -m pytest src/cdp_clone/tests
```

Đổi bảng thì sửa `app/infrastructure/tables.py` **và** thêm revision trong `migrations/versions/`; `tests/integration/test_migrations.py` bắt lệch giữa hai nơi.

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `app/domain` | Quy tắc trường bắt buộc theo `eventName`, chống trùng trong lô; không import FastAPI/DB |
| `app/api` | Route, wire model, kiểm tra service token, envelope lỗi và `X-Request-ID` |
| `app/infrastructure` | Bảng SQLAlchemy và repository (Postgres; SQLite cho test) |
| `migrations` | Alembic |
| `tests/unit`, `tests/integration`, `tests/contract` | Quy tắc domain; API + DB + migration; response khớp OpenAPI |
