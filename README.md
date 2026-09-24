# Travel Recommendation Product

V-OTA: nền tảng đặt tour du lịch có tìm kiếm ngữ nghĩa, gợi ý cá nhân hoá và trợ lý lịch trình AI. Tài liệu gốc là PRD ở [docs/prd/README.md](docs/prd/README.md); quy tắc cho người và AI agent làm việc trong repo ở [AGENTS.md](AGENTS.md).

## Chuẩn bị

Cần Docker Compose và Python 3.11+.

```bash
cp .env.example .env    # điền COHERE_API_KEY, API key LLM...; không commit .env
python3 -m venv src/backend/.venv
src/backend/.venv/bin/python -m pip install -r src/backend/requirements.txt -r src/data_collection/requirements.txt
```

`src/backend/.venv` đã nằm trong `.gitignore`. Các target `make` tự dùng venv này cho migration và job embed; seed dùng `$(PYTHON)` và chạy từ `src/`, nên kích hoạt venv trước (`source src/backend/.venv/bin/activate`) hoặc truyền đường dẫn **tuyệt đối** `PYTHON="$PWD/src/backend/.venv/bin/python"`.

## Dữ liệu quan hệ: PostgreSQL local

```bash
make demo-db
```

`make demo-db` thực hiện ba việc: chạy PostgreSQL 16 bằng Docker, kiểm tra/bung snapshot catalog 11.387 sản phẩm và seed hai database `vota`/`insider`, sau đó chạy các câu verify chính thức. Vector nằm trong Weaviate riêng, không dùng pgvector. Mỗi thành viên có Docker volume riêng trên máy; không chia sẻ hoặc commit volume.

1. Chạy PostgreSQL 16 bằng Docker.
2. Áp các migration còn thiếu.
3. Kiểm tra checksum, bung snapshot catalog 10.320 sản phẩm (`src/data_collection/snapshots/`), rồi seed hai database `vota` và `insider`.
4. Chạy các câu verify chính thức.

Mỗi thành viên có Docker volume riêng; không chia sẻ hoặc commit volume.

Khi database local đã có dữ liệu và cần dựng lại từ đầu:

```bash
make demo-db-reset
```

Lệnh `demo-db-reset` xóa state demo hiện có trong hai database local trước khi nạp lại. Target này cố định URL vào PostgreSQL Docker `localhost:5432`, không đọc URL staging từ shell. Có thể cố định ngày cửa sổ dữ liệu bằng `make demo-db AS_OF=2026-09-23`.

Sau khi seed catalog, đặt `COHERE_API_KEY` trong `.env` rồi chạy `make index-vectors`. Job khởi động Weaviate, chỉ embed search unit mới/đã đổi bằng `embed-multilingual-v3.0` và giữ vector trong volume riêng; `make demo-db-reset` không xóa volume này.

Nếu máy đã có Postgres khác giữ cổng 5432, truyền cổng khác cho **mọi** target và sửa cả bốn DSN `localhost:5432` trong `.env` cho khớp:

```bash
make demo-db POSTGRES_HOST_PORT=5433
make db-migrate POSTGRES_HOST_PORT=5433
```

### Đổi schema database

`db/init/*.sql` chỉ chạy **một lần**, lúc Docker khởi tạo volume rỗng. Database đã có dữ liệu sẽ không thấy bảng mới nếu chỉ sửa `db/init/`. Dùng migration:

```bash
make db-migrate-status     # đã áp gì, còn gì
make db-migrate            # áp phần còn thiếu, không xoá dữ liệu
```

`make demo-db` và `make demo-db-reset` đã tự gọi `db-migrate`. Quy tắc viết migration: [db/migrations/README.md](db/migrations/README.md).

## Vector: Cohere + Weaviate (Sẽ thay đổi trong tương lai)

Vector sản phẩm không nằm trong Postgres. Job `index-vectors` (`src/backend/jobs/embed_products.py`) đọc các search unit (`is_search_unit = true`) từ database đã seed, gọi Cohere `embed-multilingual-v3.0` (1024 chiều, `input_type=search_document`), rồi ghi vào collection `Product` trên Weaviate kèm `productId`, `modelVersion`, `textHash` (`docs/prd/architecture.md` §5).

```bash
make index-vectors     # embed phần mới/đã đổi bằng Cohere rồi ghi lên Weaviate
```

- Cần `COHERE_API_KEY` và `WEAVIATE_URL` trong `.env`. `WEAVIATE_API_KEY` chỉ cần khi dùng Weaviate Cloud.
- Weaviate local: `docker compose up -d --wait weaviate`, rồi đặt `WEAVIATE_URL=http://localhost:8080`.
- Weaviate Cloud: đặt `WEAVIATE_URL` (hostname hoặc `https://…` của cluster) và `WEAVIATE_API_KEY`.
- Vector có vòng đời riêng với Postgres: `make demo-db` không xoá vector. Chạy lại job chỉ embed những sản phẩm có text hoặc model đổi, và xoá vector của sản phẩm không còn trong catalog.

## Chạy Backend

```bash
make backend
```

`make backend` build và chạy Backend trong Docker Compose; Compose cũng khởi động PostgreSQL nếu service đó chưa chạy. Chạy `make demo-db` trước, nếu không thì search/recommendation tự tắt, chỉ các route khác chạy. Kiểm tra `http://localhost:8000/health` sau khi server khởi động. Xem log hoặc dừng riêng Backend bằng `make backend-logs` hoặc `make backend-stop`; dữ liệu PostgreSQL vẫn được giữ.

Chạy Backend trực tiếp trên máy, có reload khi sửa code:

```bash
make backend-local PYTHON=src/backend/.venv/bin/python
```

Chạy local, Backend đọc `.env` ở gốc repo và kết nối PostgreSQL Docker tại `localhost:5432` bằng hai role giới hạn (`DATABASE_URL`, `CDP_DATABASE_URL`).
Chỉ cần phần auth/contract mà không cần recsys thì có thể cài tập con:
`pip install fastapi uvicorn pydantic pydantic-settings psycopg[binary] argon2-cffi bcrypt 'PyJWT[crypto]' redis pytest`.

> Search/recommendation của Backend lúc chạy **chưa** đọc vector từ Weaviate. Hiện nó vẫn tự embed bằng `sentence-transformers` (`intfloat/multilingual-e5-base`) và cache ở `.embcache/`, nên lần cài `requirements.txt` đầu tiên sẽ kéo `torch` (khoảng 550 MB). Phần chuyển đường truy vấn sang Weaviate là việc tiếp theo.

## Test

```bash
src/backend/.venv/bin/python -m pytest -q src/backend/tests
PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py
```

Snapshot catalog có version nằm tại `src/data_collection/snapshots/`. JSONL đã bung, artifact seed và volume database đều là dữ liệu runtime local, không nằm trong Git.
