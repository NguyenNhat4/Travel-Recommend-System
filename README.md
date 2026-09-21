# Travel Recommendation Product

## Dựng database demo local

Yêu cầu: Docker Compose, Python 3.10+ và môi trường Python đã cài dependency trong `src/data_collection/requirements.txt`.

```bash
conda activate vsf
python -m pip install -r src/data_collection/requirements.txt
make demo-db
```

`make demo-db` thực hiện ba việc: chạy PostgreSQL 16 + pgvector bằng Docker, kiểm tra/bung snapshot catalog 10.320 sản phẩm và seed hai database `vota`/`insider`, sau đó chạy các câu verify chính thức. Mỗi thành viên có Docker volume riêng trên máy; không chia sẻ hoặc commit volume.

Lần đầu dùng `make demo-db`. Khi database local đã có dữ liệu và cần dựng lại từ đầu:

```bash
make demo-db-reset
```

Lệnh `demo-db-reset` xóa state demo hiện có trong hai database local trước khi nạp lại. Target này cố định URL vào PostgreSQL Docker `localhost:5432`, không đọc URL staging từ shell. Có thể cố định ngày cửa sổ dữ liệu bằng `make demo-db AS_OF=2026-09-21`.

## Đổi schema database

`db/init/*.sql` chỉ chạy **một lần**, lúc Docker khởi tạo volume rỗng. Database đã có dữ liệu sẽ không
bao giờ thấy bảng mới nếu chỉ sửa `db/init/`. Dùng migration:

```bash
make db-migrate-status     # đã áp gì, còn gì
make db-migrate            # áp phần còn thiếu, không xoá dữ liệu
```

`make demo-db` và `make demo-db-reset` đã tự gọi `db-migrate`. Chi tiết và quy tắc viết migration:
[db/migrations/README.md](db/migrations/README.md).

Máy đã có Postgres khác giữ cổng 5432 thì đổi cổng host:

```bash
POSTGRES_HOST_PORT=5433 docker compose up -d --wait postgres
```

## Chạy Backend

Backend dùng virtualenv riêng tại `src/backend/.venv` (đã nằm trong `.gitignore`):

```bash
python3 -m venv src/backend/.venv
src/backend/.venv/bin/python -m pip install -r src/backend/requirements.txt
make backend
```

`requirements.txt` kéo theo `torch` qua `sentence-transformers` (~550 MB), nên lần cài đầu khá lâu.
Chỉ cần phần auth/contract mà không cần recsys thì cài tập con:
`pip install fastapi uvicorn pydantic pydantic-settings psycopg[binary] argon2-cffi bcrypt 'PyJWT[crypto]' redis pytest`.

Backend mặc định kết nối PostgreSQL Docker tại `localhost:5432` bằng hai role giới hạn trong `.env.example`. Kiểm tra `http://localhost:8000/health` sau khi server khởi động.

Snapshot catalog có version nằm tại `src/data_collection/snapshots/`; JSONL đã bung, artifact seed và database volume đều là runtime local, không nằm trong Git.
