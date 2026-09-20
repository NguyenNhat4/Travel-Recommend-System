# Backend

Python/FastAPI service. `app/main.py` là composition root; business rule nằm trong `domain`, use case và interface nằm trong `application`, implementation kỹ thuật nằm trong `infrastructure`.

Các package hiện có của agent đã được đặt trong `app/agents`, còn API hiện tại nằm trong `app/api` để tiếp tục phát triển theo cấu trúc trong `ARCHITECTURE.md`.

## PostgreSQL local

PostgreSQL chạy trong Docker nhưng Backend vẫn kết nối qua hai DSN với hai role tách biệt. Từ repository root:

```bash
docker compose up -d --wait postgres
pip install -r src/backend/requirements.txt
uvicorn src.backend.app.main:app --reload
```

Giá trị dev mặc định (cũng có trong `.env.example`):

```env
DATABASE_URL=postgresql://vota_app_login:vota@localhost:5432/vota
CDP_DATABASE_URL=postgresql://cdp_client_login:cdp@localhost:5432/vota
CDP_ADAPTER=local
```

- `DATABASE_URL`: adapter catalog/app; role này chỉ được đọc `cdp.products`, không được đọc profile/event.
- `CDP_DATABASE_URL`: `LocalCdpClient`; role này chỉ được vào schema `cdp`.
- `CDP_ADAPTER=http`: đường chuyển sang `CdpHttpClient` sau này; lúc đó mới dùng `CDP_BASE_URL` và `CDP_SERVICE_TOKEN`.

Các URL này chỉ là địa chỉ PostgreSQL trên máy local; chúng không tạo database hay dữ liệu mới. Loader/seed dùng `SEED_DATABASE_URL` riêng và Backend không được dùng quyền đó.

Chạy test đọc seed thật (không ghi DB):

```bash
RUN_POSTGRES_INTEGRATION=1 python -m pytest -q src/backend/tests
```
