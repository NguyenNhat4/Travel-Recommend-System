# Travel Recommendation Product

V-OTA là nền tảng đặt tour du lịch, gồm tìm kiếm ngữ nghĩa, gợi ý cá nhân hoá và trợ lý lịch trình AI.

- Yêu cầu sản phẩm: [docs/prd/README.md](docs/prd/README.md)
- Quy tắc làm việc trong repo (cho cả người và AI agent): [AGENTS.md](AGENTS.md)
- Cách đọc code backend: [docs/guide/doc-code-backend.md](docs/guide/doc-code-backend.md)

**File này là hướng dẫn setup duy nhất.** README trong `src/*` chỉ mô tả cấu trúc và chi tiết riêng của từng
workstream.

## 1. Cần cài sẵn

| Công cụ | Phiên bản | Kiểm tra |
|---|---|---|
| Docker + Docker Compose | bản mới | `docker compose version` |
| Python | 3.11+ | `python3 --version` |
| Node.js + npm | 20+ | `node -v` |
| make, openssl | bất kỳ | `make -v` |

Windows: chạy trong WSL2.

## 2. Setup lần đầu (khoảng 10 phút)

Chạy lần lượt từ thư mục gốc của repo.

```bash
# 1. Tạo venv Python ở gốc repo rồi cài dependency Python và frontend
python3 -m venv .venv
source .venv/bin/activate
make update

# 2. Tạo file cấu hình
cp .env.example .env
cp src/frontend/.env.example src/frontend/.env.local

# 3. Sinh token nội bộ dùng chung cho backend và BFF, rồi ghi vào cả hai file
TOKEN=$(openssl rand -hex 32)
sed -i "s/^AUTH_SERVICE_TOKEN=.*/AUTH_SERVICE_TOKEN=$TOKEN/" .env
sed -i "s/^AUTH_SERVICE_TOKEN=.*/AUTH_SERVICE_TOKEN=\"$TOKEN\"/" src/frontend/.env.local

# 4. Sinh khoá ký JWT (ghi vào secrets/, đã gitignore)
make jwt-keys

# 5. Dựng database: Postgres + Redis + seed catalog 11.387 sản phẩm + verify
docker compose up -d --wait redis
make demo-db
```

Sau đó mở `.env` và điền API key (xem mục 3). Có key rồi thì chạy thêm:

```bash
# 6. Embed catalog bằng Cohere rồi ghi lên Weaviate (cần COHERE_API_KEY, chạy vài phút)
make index-vectors
```

Nếu thấy `make demo-db` báo đúng hai dòng FAIL `products >= 11387` và `is_recommendable properties >= 300`,
nghĩa là bạn đang dùng catalog tổng hợp. Hai dòng này FAIL theo thiết kế (xem `AGENTS.md` §6.5). Mọi dòng FAIL
khác đều là lỗi thật.

## 3. Biến môi trường cần điền

Chỉ cần sửa vài dòng trong `.env`; các dòng còn lại đã có giá trị mặc định chạy được ở local.

| Biến | Bắt buộc khi | Lấy ở đâu |
|---|---|---|
| `COHERE_API_KEY` | Dùng search / recommendation | dashboard.cohere.com |
| `GEMINI_API_KEY` hoặc `OPENAI_API_KEY` hoặc `ANTHROPIC_API_KEY` | Dùng trợ lý lịch trình (chỉ cần một key) | Trang của provider tương ứng |
| `AUTH_SERVICE_TOKEN` | Đăng nhập trên web | Đã sinh ở bước 3 |

- Không có key LLM: đặt `ITINERARY_USE_LLM=false`. App vẫn chạy; riêng trợ lý trả 503 `LLM_UNAVAILABLE`.
- Không commit `.env`, `src/frontend/.env.local` và `secrets/`.

## 4. Chạy ứng dụng

Luôn `source .venv/bin/activate` trước khi chạy các lệnh dưới.

| Muốn làm gì | Lệnh | Mở ở đâu |
|---|---|---|
| Chạy web đầy đủ (FastAPI + Next.js) | `make web` | http://localhost:3000 |
| Build frontend image bằng Docker Compose | `docker compose build frontend` | image `travel-recommendation-product-frontend` |
| Chạy Backend + Frontend trong Docker | `docker compose up -d --build backend frontend` | http://localhost:3000 |
| Thử trợ lý lịch trình bằng UI Streamlit | `make chat` | http://127.0.0.1:8502 |
| Chỉ chạy backend, tự reload khi sửa code | `make backend-local` | http://127.0.0.1:8000/docs |
| Chạy backend trong Docker | `make backend` (log: `make backend-logs`, dừng: `make backend-stop`) | http://localhost:8000/health |

Nhấn Ctrl+C để dừng `make web` hoặc `make chat` (dừng cả hai process).

Tài khoản đăng nhập có sẵn sau khi seed: `test01@vota.demo` … `test50@vota.demo`, mật khẩu `Demo@2026`.

Kiểm tra backend đang ở trạng thái nào:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/assistant/status    # llmMode: live | disabled | unavailable
```

## 5. Việc thường ngày

| Tình huống | Lệnh |
|---|---|
| Vừa `git pull`, có đổi `requirements.txt` hoặc `package.json` | `make update` |
| Vừa `git pull`, có migration mới trong `db/migrations/` | `make db-migrate` |
| Xem database đã áp migration nào | `make db-migrate-status` |
| Dựng lại database demo từ đầu (xoá dữ liệu demo local) | `make demo-db-reset` |
| Cố định ngày của dữ liệu demo | `make demo-db AS_OF=2026-09-23` |
| Catalog đổi, cần embed lại (chỉ embed phần mới/đổi) | `make index-vectors` |
| Chạy test backend (không cần Postgres) | `python -m pytest -q src/backend/tests` |
| Kiểm contract OpenAPI và mock | `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` |
| Chạy test frontend | `npm --prefix src/frontend test` |

Đổi schema database: sửa `db/*.sql` và thêm migration trong cùng commit. Không chạy lại `db/init/` trên database
đã có dữ liệu, vì file đó chỉ chạy một lần lúc Docker tạo volume rỗng. Quy tắc chi tiết:
[db/migrations/README.md](db/migrations/README.md).

## 6. Gặp lỗi

| Triệu chứng | Cách xử lý |
|---|---|
| `make web` / `make chat` báo "Không tìm thấy .venv" | Venv phải nằm ở `.venv` ngay gốc repo (bước 1) |
| `ModuleNotFoundError` khi chạy `make demo-db` | Chưa `source .venv/bin/activate` |
| Cổng 5432 đã bị Postgres khác chiếm | Thêm `POSTGRES_HOST_PORT=5433` vào **mọi** lệnh `make` và đổi `localhost:5432` → `localhost:5433` trong `.env` |
| Search trả mảng rỗng | Chưa chạy `make index-vectors` hoặc thiếu `COHERE_API_KEY`; khởi động lại backend sau khi embed |
| `make index-vectors` báo 429 | Hết quota Cohere; chờ rồi chạy lại, job sẽ tiếp tục phần còn thiếu |
| Web không đăng nhập được (401) | `AUTH_SERVICE_TOKEN` ở `.env` và `src/frontend/.env.local` không giống nhau |
| Token hết hiệu lực mỗi lần khởi động lại backend | Chưa chạy `make jwt-keys` |
| Trợ lý trả 503 `LLM_UNAVAILABLE` | Thiếu key LLM, hoặc đang đặt `ITINERARY_USE_LLM=false` |

## 7. Sơ đồ service local

| Service | Cổng | Khởi động bằng |
|---|---|---|
| PostgreSQL 16 (database `vota`, `insider`) | 5432 | `make demo-db` |
| Redis (session, rate limit) | 6379 | `docker compose up -d redis` |
| Weaviate (vector sản phẩm) | 8080, 50051 | `make index-vectors` |
| FastAPI backend | 8000 | `make web` / `make chat` / `make backend-local` |
| Next.js web + BFF | 3000 | `make web` |
| Next.js web + BFF trong Docker | 3000 | `docker compose up -d frontend` |
| Streamlit (demo trợ lý) | 8502 | `make chat` |

Dữ liệu Postgres và Weaviate nằm trong Docker volume riêng trên máy của từng người. Không chia sẻ hay commit các
volume này. `make demo-db-reset` không xoá vector trong Weaviate.
