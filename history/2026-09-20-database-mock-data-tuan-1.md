# Database tuần 1: schema `vota` + `insider`, gộp bundle, và package mock data

- Ngày: 2026-09-20
- Tác giả: Nguyễn Hải Sơn / Claude Code
- Nhánh: data_contract
- Trạng thái: dang dở
- Phạm vi: data, cdp, insider, docs
- Thay thế: `2026-09-17-thiet-ke-schema-3-service.md` (phần "ba service, mỗi service một database" và "CDP clone là service HTTP")

## Mục tiêu

Người yêu cầu đã giải nén `vota-schema-bundle.zip` vào gốc repo và yêu cầu làm theo `CLAUDE.database.md`:
gộp phần hạ tầng vào repo, dựng Postgres, rồi viết `src/data_collection/seed/` sinh mock data tất định
để `db/verify.sql` và `db/verify_insider.sql` chạy được.

Chia làm ba phần, mỗi phần một commit. **Entry này viết ở phần A và được bổ sung ở phần B, C.**

- Phần A (commit này): gộp bundle, sửa tài liệu cho khớp, dựng database, kiểm tra 15 bảng + 3 view.
- Phần B: package `src/data_collection/seed/` (gen_products → seed_insider).
- Phần C: unit test, báo cáo seed, chốt trạng thái.

## File thay đổi

Phần A — đối chiếu `git status` ngày 20/09:

- `docker-compose.yml` — thêm: service `postgres` (pgvector/pgvector:pg16, db `vota`, mount `db/init`), đổi tên từ `docker-compose.db.yml` của bundle. Thêm healthcheck `pg_isready` để `up -d --wait` dùng được.
- `docker-compose.db.yml` — xóa: đã đổi tên thành `docker-compose.yml`. Repo trước đó **không có** `docker-compose.yml` ở gốc nên không có gì để "gộp vào" như README.database.md mô tả.
- `AGENTS.md` — sửa: thêm mục 6 "Database" (nội dung `CLAUDE.database.md`), thêm 2 dòng bảng §1.2 (Database, Mock data tuần 1), sửa dòng CDP clone trỏ sang mục 6, mở rộng §5 để `db/` cũng phải có entry lịch sử.
- `CLAUDE.database.md` — xóa: đã gộp vào `AGENTS.md`.
- `db/` — thêm (từ bundle): `init/00_create_insider.sql`, `init/01_vota.sql`, `init/02_insider.sql`, `init/03_roles_dev.sql`, `vota_schema.sql`, `insider_schema.sql`, `verify.sql`, `verify_insider.sql`.
- `docs/DATABASE_SCHEMA.md`, `docs/PRODUCT_SCHEMA.md` — thêm (từ bundle).
- `docs/MOCK_DATA_SPEC.md` — thêm (từ bundle) và sửa §0: connection seed/verify là `SEED_DATABASE_URL`, báo cáo ghi vào khối đánh dấu trong `src/data_collection/README.md`, và ghi rõ hai dòng verify FAIL theo thiết kế với catalog tổng hợp.
- `docs/spec/Mock-data.md` — xóa: trùng byte-for-byte với `docs/MOCK_DATA_SPEC.md` (chỉ khác CRLF), mà mọi tài liệu đều trỏ tới bản trong `docs/`.
- `docs/research/recsys-data-cleaning-embedding-strategy.md` — thêm (từ bundle).
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: banner đầu file nêu phần nào chưa áp dụng ở tuần 1; §1.5 gạch quy tắc "seed qua API"; §11 chốt nơi lưu `products`/`users`/`bookings`/`product_vectors`; §13 thêm 2 dòng quyết định 20/09.
- `src/ARCHITECTURE.md` — sửa: §3 vẽ lại sơ đồ theo hai connection và nêu `db/` + compose ở gốc; §4 chú thích lại `data_collection` và `cdp_clone`, thêm câu về thư mục hạ tầng ngoài `src/`; §7 sửa dòng CDP clone; §9 viết lại 3 gạch đầu dòng (CDP clone là schema, ngoại lệ loader/seed, nơi lưu các bảng).
- `src/cdp_clone/README.md` — sửa: banner "tuần 1 CDP clone là database" ở trên, **khôi phục toàn bộ tài liệu service** mà bundle đã xóa, đặt dưới mục "Service HTTP — tạm gác". Thêm cảnh báo bảng trong `app/infrastructure/tables.py` chưa khớp `db/init/01_vota.sql`.
- `.env.example` — sửa: giữ 7 biến database của bundle, **khôi phục** phần crawl politeness (`RATE_LIMIT_RPS`, `MAX_CONCURRENCY`, `USER_AGENT`), Amadeus và `PYTHONUTF8=1` mà bundle đã xóa; thêm ghi chú DSN thuần cho psycopg v3.
- `src/data_collection/seed/README.md` — thêm (placeholder từ bundle; phần B thay bằng bản viết tay).
- `history/2026-09-17-thiet-ke-schema-3-service.md` — sửa: thêm đúng một dòng `Bị thay thế bởi:` (mức sửa duy nhất `history/README.md` cho phép với entry cũ).

Không commit: `README.database.md`, `PROMPT_claude_code.md` (bundle ghi rõ không cần commit).

## Quyết định

- **CDP clone là schema `cdp` trong database `vota`, không phải service HTTP có PostgreSQL riêng.** Người yêu cầu chọn phương án "theo bundle + sửa tài liệu" ngày 20/09. Căn cứ: handbook §6 "one implementation now, reading locally"; tách database sẽ mất FK và view của `catalog`/`app` sang `cdp.products`, mà `catalog` vẫn phải là bảng local để search p95 < 300 ms. Ranh giới production được mô phỏng bằng **role + connection riêng** và bằng việc mọi truy cập của app đi qua port `CdpClient` — đổi sang `HttpCdpClient` là thay adapter, không sửa use case. Đã kiểm chứng ranh giới chạy thật (xem Kiểm tra).
- **Giữ nguyên code `src/cdp_clone/`.** Bundle viết README thành "Chưa viết gì ở đây" trong khi thư mục có service FastAPI + Alembic + test chạy được. Không xóa code, không xóa tài liệu; chỉ đánh dấu "tạm gác" và nêu rõ nó là nền cho `HttpCdpClient`.
- **Mục Database đặt trong `AGENTS.md`, không phải `CLAUDE.md`.** Bundle bảo gộp vào `CLAUDE.md`, nhưng `AGENTS.md` dòng 3 quy định `CLAUDE.md` chỉ import `AGENTS.md` và mọi quy tắc sửa tại `AGENTS.md`. Quy tắc repo thắng.
- **`docker-compose.db.yml` đổi tên thành `docker-compose.yml`**, không gộp: repo chưa có compose ở gốc. Thêm healthcheck vì các bước sau cần `--wait`.
- **Quy mô catalog: giữ đúng MOCK_DATA_SPEC §1b (~450 dòng, 40 property).** Người yêu cầu chọn phương án này ngày 20/09, chấp nhận hai dòng `db/verify.sql` FAIL theo thiết kế (`products = 2216`, `is_recommendable properties >= 300`) thay vì thổi quy mô tổng hợp lên 2.216 dòng để lách ngưỡng của crawl thật. Không sửa `db/*.sql`.
- **Báo cáo seed ghi vào khối `<!-- seed-report:start/end -->` trong `src/data_collection/README.md`.** Spec ghi `data-collection/README.md` (gạch nối) — thư mục đó không tồn tại trong monorepo; còn cây thư mục §1 lại trỏ vào chính file sổ tay crawler 426 dòng. Dùng khối đánh dấu để vừa đúng ý spec vừa không mất sổ tay.
- **Seed và verify chạy bằng `SEED_DATABASE_URL` (superuser).** Dòng đầu `db/verify*.sql` ghi `$DATABASE_URL` là nhầm: role `vota_app` không SELECT được `cdp.events`/`cdp.profiles` nên sẽ lỗi quyền chứ không ra FAIL. Ghi chú trong `docs/MOCK_DATA_SPEC.md` §0 thay vì sửa file .sql.
- **Khôi phục biến môi trường crawler trong `.env.example`.** `docs/spec/data-collection-spec.md` dòng 499 quy định file này phải có `RATE_LIMIT_RPS`, `MAX_CONCURRENCY`, `USER_AGENT`, `AMADEUS_*`; `PYTHONUTF8=1` là bắt buộc trên Windows để output tiếng Việt không vỡ khi pipe. Bundle ghi đè cả file nên đã mất hết.

## Kiểm tra

Đã chạy thật, ngày 20/09:

- `docker compose up -d --wait postgres` → container Healthy. Log initdb không có ERROR/FATAL (chỉ warning "trust authentication" mặc định của image).
- `vota`: **15 bảng + 3 view**, đúng kỳ vọng.
  - `cdp.products`, `cdp.profiles`, `cdp.events`
  - `catalog.combo_items`, `catalog.product_vectors`
  - `app.users`, `carts`, `cart_items`, `bookings`, `booking_items`, `conversations`, `conversation_messages`, `itineraries`, `recommendation_logs`, `search_logs`
  - view `catalog.product_meta`, `catalog.product_parents`, `catalog.search_rows`
- `insider`: **5 bảng + view `live_events`** (`partners`, `insider_profiles`, `identifiers`, `insider_events`, `channel_events`).
- Role: `cdp_reader`, `cdp_writer`, `vota_app` (NOLOGIN) + `vota_app_login`, `cdp_client_login`, `cdp_eval_login` (LOGIN). Extension: `vector`, `plpgsql`.
- Ranh giới role kiểm chứng bằng 4 truy vấn thật:
  - `vota_app_login` → `cdp.products`: OK (0 dòng).
  - `vota_app_login` → `cdp.events`: `ERROR: permission denied for table events`.
  - `cdp_client_login` → `catalog.combo_items`: `ERROR: permission denied for schema catalog`.
  - `cdp_client_login` → `cdp.events`: OK (0 dòng).
- `validate_contract.py`: không chạy — phần A không đổi OpenAPI, mock hay fixture.
- `db/verify.sql`: chưa chạy — chưa có dữ liệu, thuộc phần B.

## Còn lại / rủi ro

- **Phần B và C chưa làm:** package `src/data_collection/seed/` và test. Đang dừng ngay sau khi database dựng xong và tài liệu đã khớp.
- `psql` không có trên máy này; mọi lệnh psql chạy qua `docker compose exec -T postgres psql`. `report.py` ở phần B sẽ tự chạy các câu verify bằng psycopg để không phụ thuộc psql.
- **Hai dòng `db/verify.sql` sẽ FAIL theo thiết kế** với catalog tổng hợp: `products = 2216` và `is_recommendable properties >= 300`. Hết FAIL khi có `products.jsonl` thật từ crawler.
- **Code chưa theo kiến trúc mới:** `src/backend/app/infrastructure/clients/cdp_http_client.py` và `cdp_event_dispatcher.py` vẫn là thiết kế service HTTP. Các adapter mà `README.database.md` nhắc tới — `infrastructure/cdp/local_cdp_client.py`, `infrastructure/insider/http_insider_client.py`, `application/ports/insider_client.py` — **chưa tồn tại**. `src/backend/app/core/config.py` còn default `sqlite:///./data/app.db` và `cdp_base_url`. Việc này thuộc Backend, chưa nằm trong phạm vi tuần 1 của Data.
- `src/cdp_clone/app/infrastructure/tables.py` (revision `0001`) chưa khớp `db/init/01_vota.sql`; phải đối chiếu lại trước khi dựng `HttpCdpClient`.
- `src/insider_clone/` vẫn rỗng (chỉ có README + `.gitkeep`); `seed_insider.py` ở phần B ghi thẳng vào database `insider`, chưa qua service.
- Chờ xác nhận, chưa tự quyết: tên cột opt-in trong `cdp.profiles` (chờ reviewer CDP); D và model vector (tuần 2, `product_vectors` để trống); "mọi route có ≥ 1 chuyến?" — catalog tổng hợp cố ý tạo 1 route không có chuyến để câu hỏi này có ví dụ.
