# Quy tắc cho AI agent

File này áp dụng cho mọi AI coding agent (Claude Code, Codex, Cursor, Copilot...) làm việc trong repository. `CLAUDE.md` chỉ import file này; sửa quy tắc tại đây.

## 1. Bắt buộc đọc tài liệu trước khi làm feature mới

Trước khi viết hoặc sửa code cho **feature mới, endpoint mới, module mới hoặc thay đổi hành vi**, agent PHẢI dùng tool đọc (Read/cat) các file quy tắc bên dưới trong phiên hiện tại. Không được dựa vào trí nhớ, phiên trước hoặc suy đoán từ tên file.

### 1.1. Luôn đọc (mọi feature)

1. `docs/prd/README.md` — mục lục PRD, kèm tài liệu PRD theo phạm vi ở mục 1.2. Mỗi feature phải gắn được vào ít nhất một mã FR/NFR trong `docs/prd/requirements.md`; không có mã tương ứng thì hỏi người dùng trước, không tự mở rộng phạm vi sản phẩm.
2. `src/ARCHITECTURE.md` — cấu trúc repo, quy tắc phụ thuộc, quy ước thêm module.
3. `src/shared/contracts/MVP.md` — bộ trường tối thiểu hiện hành (1.2.0).
4. `docs/spec/contract-baseline-v1.1.md` — quyết định đã chốt và phần còn chờ xác nhận.
5. `README.md` của workstream sẽ sửa (`src/<workstream>/README.md`).
6. Lịch sử thay đổi trong `history/` (xem mục 5): `history/README.md`, 10 entry mới nhất, mọi entry từng chạm vào đường dẫn/workstream sắp sửa và mọi entry có `Trạng thái: dang dở` thuộc phạm vi đó.

### 1.2. Đọc thêm theo phạm vi

| Phạm vi thay đổi | File phải đọc |
|---|---|
| API / request / response bất kỳ | `src/shared/contracts/README.md`, `src/shared/contracts/openapi.yaml`, file `paths/<domain>.yaml` và `schemas/<domain>.yaml` liên quan, `schemas/common.yaml`, `docs/prd/api-contract.md` (chuẩn Error Envelope, phân trang, quy tắc versioning — **ví dụ endpoint trong đó chỉ để minh hoạ, xem cảnh báo ở mục 2**) |
| Backend (`src/backend`) | `src/backend/README.md`, `docs/spec/hop-dong-tich-hop-backend.md` (các mục của domain liên quan), `docs/prd/architecture.md` §2 (phân lớp + quy tắc phụ thuộc) |
| Frontend (`src/frontend`) | `src/frontend/README.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/product.md`, `docs/prd/user-flow.md` (route table, wireframe, luồng cốt lõi) |
| Auth: đăng nhập, phiên, cookie, JWT, mật khẩu, 2FA, OAuth | `docs/spec/hop-dong-tich-hop-auth.md` (bắt buộc đọc §3 Logic mapping), `src/shared/contracts/paths/auth.yaml`, `src/shared/contracts/schemas/auth.yaml`, `docs/prd/requirements.md` §1.6 (FR-USR) |
| Itinerary Agent (`src/backend/app/agents`, use case itinerary) | `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/README.md` và các file nó liên kết, `src/shared/mocks/itinerary-agent/README.md`, `docs/prd/architecture.md` §3 (StateGraph + chuẩn grounding), `docs/prd/requirements.md` §1.4 (FR-AGT) |
| Search / Recommendation | `docs/spec/hop-dong-tich-hop-search-recommendation.md` (hợp đồng chi tiết cho cả hai engine), `docs/spec/hop-dong-tich-hop-backend.md` (mục Search, Recommendation), `docs/spec/recsys-internship-handbook-v3-vi.md`, `docs/prd/requirements.md` §1.2–1.3 (FR-SRC, FR-REC) |
| CDP clone, `CdpClient`, ghi hành vi người dùng | mục 6 bên dưới, `docs/spec/hop-dong-tich-hop-cdp.md`, `src/cdp_clone/README.md`, `src/shared/contracts/cdp-clone.openapi.yaml`, `docs/prd/requirements.md` §1.7 (FR-CDP) |
| Mock / fixture (`src/shared/mocks`) | `src/shared/README.md`, `src/shared/mocks/index.json`, schema response tương ứng |
| Data collection (`src/data_collection`) | `src/data_collection/README.md`, `src/data_collection/docs/SCHEMA.md`, `docs/prd/data-model.md` §3 (quy chuẩn `attributes`) |
| Database: schema, DDL, loader, seed, `db/` | mục 6 bên dưới, `docs/spec/DATABASE_SCHEMA.md`, `docs/spec/PRODUCT_SCHEMA.md`, `db/vota_schema.sql`, `db/insider_schema.sql`, `db/migrations/README.md`, `docs/prd/data-model.md` (ERD, ranh giới quyền, vòng đời thực thể) |
| Mock data tuần 1 (`src/data_collection/seed`) | mục 6 bên dưới, `docs/spec/MOCK_DATA_SPEC.md`, `src/data_collection/docs/SCHEMA.md`, `db/verify.sql`, `db/verify_insider.sql` |
| Evaluation (`src/evaluation`) | `src/evaluation/README.md` (chưa tồn tại — hỏi người dùng trước khi giả định nội dung), `docs/spec/recsys-internship-handbook-v3-vi.md`, `docs/prd/test-plan.md` §2.4–2.5 (chỉ số grounding và RecSys offline) |
| Insider clone (`src/insider_clone`) | `src/insider_clone/README.md`, `docs/spec/hop-dong-tich-hop-insider.md`, `docs/spec/recsys-internship-handbook-v3-vi.md` (phần Insider), `docs/prd/requirements.md` §1.8 (FR-ENG) |
| Tính năng sản phẩm / luồng người dùng mới | `docs/spec/product.md`, `docs/prd/project-brief.md` (§4 phạm vi in/out), `docs/prd/requirements.md`, `docs/prd/user-flow.md` |
| Môi trường, biến môi trường, migration, Docker, CI/CD | `docs/prd/deployment-plan.md`, `docs/prd/test-plan.md` §4, `db/migrations/README.md`, mục 6.3 bên dưới |
| Lập kế hoạch, chia giai đoạn, định nghĩa hoàn thành | `docs/prd/implementation-plan.md` (lộ trình 6 giai đoạn, ownership theo workstream, DoD §4) |

Với file dài (> 500 dòng), được phép đọc mục lục (`grep -n "^#"`) rồi đọc đầy đủ các mục liên quan, nhưng phải đọc hết mục đó, không chỉ vài dòng đầu.

### 1.3. Xác nhận trước khi code

Trước lần sửa code đầu tiên, agent phải ghi ngắn cho người dùng:

- Danh sách file đã đọc, gồm các entry `history/` đã đọc.
- Mã FR/NFR trong `docs/prd/requirements.md` mà feature này phục vụ, và tiêu chí nghiệm thu (AC) tương ứng ở §3 của tài liệu đó nếu có.
- Các quy tắc/ràng buộc từ tài liệu áp dụng cho feature này.
- Quyết định hoặc việc dang dở từ lịch sử liên quan tới feature này.
- Điểm mâu thuẫn hoặc chưa rõ (nếu có).

Nếu chưa đọc đủ file theo mục 1.1 và 1.2, **không được bắt đầu code**.

## 2. Khi tài liệu mâu thuẫn hoặc thiếu

PRD (`docs/prd/`) trả lời **làm gì và vì sao** — phạm vi, FR/NFR, tiêu chí nghiệm thu. Contract và DDL trả lời **giao diện và cấu trúc cụ thể**. Hai nhóm không thay thế nhau; tra đúng nhóm theo loại câu hỏi, và chính PRD cũng tự trỏ về contract/DDL cho phần kỹ thuật (`api-contract.md` dòng 3, `data-model.md` §5.1) và về file này cho quy tắc lịch sử (`docs/prd/README.md`, mục "Nguyên Tắc Vận Hành & Quản Trị Tài Liệu").

**Giao diện kỹ thuật (API, schema, DDL)** — ưu tiên cao xuống thấp:

1. `src/shared/contracts/openapi.yaml` và các file `paths/`, `schemas/` — nguồn sự thật cho API.
2. `src/shared/contracts/MVP.md` — thay thế danh sách required/optional của baseline 1.1.
3. `docs/spec/contract-baseline-v1.1.md`.
4. `db/vota_schema.sql`, `db/insider_schema.sql`, `db/migrations/` — nguồn sự thật cho DDL.
5. `src/ARCHITECTURE.md`.
6. `docs/spec/hop-dong-tich-hop-*.md`, `docs/spec/product.md`, handbook.

**Yêu cầu sản phẩm (phạm vi, hành vi, tiêu chí nghiệm thu)** — ưu tiên cao xuống thấp:

1. `docs/prd/requirements.md` — FR, NFR và ma trận AC.
2. `docs/prd/project-brief.md` (§4 phạm vi in/out), `docs/prd/user-flow.md`, `docs/prd/data-model.md`, `docs/prd/architecture.md`.
3. `docs/spec/*` và handbook.

**Cảnh báo: `docs/prd/api-contract.md` là tài liệu minh hoạ, không phải nguồn sự thật.** Phần nguyên tắc (Error Envelope, phân trang, quy tắc tương thích ngược, lệnh `validate_contract.py`) vẫn áp dụng, nhưng một số ví dụ endpoint trong đó đã lệch với `openapi.yaml` — luôn đối chiếu contract trước khi code, không copy path/field từ PRD. Lệch đã biết tại thời điểm 2026-09-22: PRD ghi `POST /assistant/chat` và `POST /assistant/conversations` (contract dùng `/assistant/itineraries`, `/assistant/itineraries/stream`, `/assistant/status`; route `/chat` đã **bị gỡ có chủ đích**, xem `history/2026-09-21-lock-assistant-api-to-contract.md`), `POST /auth/logout` và `/auth/persona-switch` (contract dùng `/auth/session/revoke`, `/auth/demo-accounts`), `GET /products/{id}/availability` (không có trong contract), `bookingCode` (contract dùng `referenceCode`); contract còn có `/cart*`, `/auth/register`, `/auth/password`, `/destinations` mà PRD không nhắc.

Không tự chọn phương án cho các mục đang "chờ xác nhận" trong baseline hoặc mục 6.4; áp dụng quy tắc tạm thời đã ghi và báo người dùng. Nếu tài liệu không đề cập, hỏi người dùng thay vì tự đặt quy ước mới.

## 3. Quy tắc khi triển khai

- Thay đổi giao diện giữa các team: cập nhật OpenAPI (`paths/`, `schemas/`) **trước**, rồi mới code backend/frontend. Không sửa bản bundle sinh tự động.
- Không xóa/đổi tên field hoặc đổi semantics trong v1; thay đổi phá vỡ tương thích phải lên v2.
- Tuân thủ quy tắc phụ thuộc backend và quy tắc frontend trong `src/ARCHITECTURE.md` (mục 5, 6, 12).
- Code mới đặt theo cấu trúc trong `src/ARCHITECTURE.md` (`src/backend`, `src/frontend`...). Các thư mục cũ ở gốc `src/` (`src/agents`, `src/api`, `src/models`, `src/services`, `src/main.py`, `src/config.py`) không được mở rộng nếu chưa hỏi người dùng.
- Grounding: mọi sản phẩm, giá, `productId` phải đến từ Search/Recommendation/Catalog; không để LLM tạo dữ liệu sản phẩm. Tỷ lệ grounding bắt buộc 100% (`docs/prd/requirements.md` NFR-REL-01).
- Không tự làm các hạng mục PRD đã ghi **ngoài phạm vi** (`docs/prd/project-brief.md` §4.2): cổng thanh toán ngân hàng thật, tồn kho thời gian thực nối hãng bay/khách sạn ngoài, app di động native. Người dùng yêu cầu thì xác nhận lại rằng đây là mở rộng phạm vi trước khi code.
- Không commit hoặc log secret, API key, JWT. Biến bí mật theo bảng ở `docs/prd/deployment-plan.md` §2.

## 4. Trước khi báo hoàn thành

Chuẩn đầy đủ: Definition of Done ở `docs/prd/implementation-plan.md` §4 và tháp kiểm thử ở `docs/prd/test-plan.md`. Tối thiểu:

- Có thay đổi contract hoặc mock: chạy `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` từ repo root và báo kết quả.
- Thêm test theo mục 10 của `src/ARCHITECTURE.md` và tháp 5 tầng của `docs/prd/test-plan.md` — unit, contract, integration/DB, grounding của agent, đánh giá RecSys offline — chỉ các tầng thuộc phạm vi thay đổi. DoD đặt mức bao phủ ≥ 80% cho `domain` và `application`.
- Có thay đổi schema hoặc seed: `db/verify.sql` (và `db/verify_insider.sql` nếu chạm Insider) PASS, trừ hai dòng FAIL dự kiến ghi ở mục 6.5.
- Nếu feature làm thay đổi quy ước, cập nhật tài liệu liên quan trong cùng thay đổi — gồm tài liệu PRD tương ứng khi thay đổi chạm tới FR/NFR, mô hình dữ liệu hoặc luồng người dùng.
- Có thay đổi trong `src/`, `docs/` hoặc `db/`: đã tạo entry trong `history/` theo mục 5.

## 5. Bắt buộc ghi lịch sử thay đổi

Mọi thay đổi (thêm, sửa, xóa, đổi tên file) trong `src/`, `docs/` hoặc `db/` PHẢI có một entry trong `history/`, kể cả sửa nhỏ, refactor, fix bug hay chỉ sửa tài liệu.

- Đọc `history/README.md` và làm đúng định dạng, tên file, mẫu tại đó.
- Mỗi task một file mới `history/YYYY-MM-DD-<slug>.md`; không gộp vào entry của người khác.
- Liệt kê **đầy đủ** file đã đổi (đối chiếu `git status` trước khi viết), lý do, quyết định, lệnh kiểm tra đã chạy và kết quả thật, việc còn lại.
- Tạo entry trước khi báo hoàn thành và trước khi commit; entry nằm trong cùng commit với thay đổi.
- Dừng giữa chừng hoặc bị chặn: vẫn tạo entry với `Trạng thái: dang dở` và ghi rõ đang dừng ở đâu.
- Không sửa nội dung entry cũ; quyết định mới thay thế quyết định cũ thì tạo entry mới theo `history/README.md`.

Thiếu entry lịch sử thì thay đổi được coi là **chưa hoàn thành**.

## 6. Database — quy tắc cho mọi thay đổi (đọc trước khi chạm vào schema, loader, CdpClient)

Nguồn sự thật: `docs/spec/DATABASE_SCHEMA.md` (toàn hệ thống + DDL), `docs/spec/PRODUCT_SCHEMA.md` (catalog sản phẩm), `docs/spec/MOCK_DATA_SPEC.md` (cách tạo bảng + mock data tuần 1). `docs/prd/data-model.md` là bản mô tả cấp PRD (ERD, ranh giới quyền, vòng đời thực thể) — đọc để hiểu ý đồ, nhưng khi lệch thì file `.sql` và ba tài liệu `docs/spec/` trên thắng (chính PRD §5.1 cũng chỉ về `db/*.sql`); lệch đã biết ghi ở mục 6.4.
DDL chạy được: `db/vota_schema.sql`, `db/insider_schema.sql`; bản initdb cho docker-compose ở `db/init/`; migration cho database đã có dữ liệu ở `db/migrations/` (đọc `db/migrations/README.md`).
Sửa schema = sửa file .sql, **thêm migration idempotent tương ứng** và cập nhật doc — cả ba trong cùng commit. Thiếu file .sql thì máy mới thiếu bảng; thiếu migration thì máy đang chạy thiếu bảng.

### 6.1. Ranh giới

- Database `vota`, ba schema: `cdp` (mirror CDP thật) · `catalog` (dựng lại được từ `cdp.products`) · `app` (trạng thái BE/FE/agent).
- Database `insider` riêng — chỉ service Insider clone (`src/insider_clone`) chạm vào; V-OTA đi qua HTTP (`InsiderClient`).
- `cdp.*` chỉ được đọc/ghi qua port `CdpClient` (`application/ports/cdp_client.py`). Adapter hiện tại `LocalCdpClient` (`infrastructure/cdp/`) dùng connection **riêng** `CDP_DATABASE_URL` (role `cdp_writer`, không có USAGE trên `catalog`/`app`); adapter sau `HttpCdpClient` gọi CDP thật. Code ngoài adapter không được `import` gì từ `cdp` — không SQL, không JOIN sang `cdp.events`/`cdp.profiles`. Role `vota_app` (`DATABASE_URL`) chỉ SELECT được `cdp.products` để `catalog.*` dựng từ nó.
- **Ngoại lệ duy nhất:** loader/seed (`src/data_collection/seed`) ghi thẳng SQL vào `cdp.*` bằng `SEED_DATABASE_URL` (superuser). Đây là job nạp dữ liệu, không phải code app; khi lên CDP thật nó được thay bằng job sync qua `CdpClient`.
- Insider: port `InsiderClient` + adapter `HttpInsiderClient` (httpx → `INSIDER_BASE_URL`, header `X-PARTNER-NAME`/`X-REQUEST-TOKEN`). Backend không có connection nào tới database `insider`.
- Không tạo service HTTP cho CDP clone ở tuần 1 — handbook §6: CDP clone là database, Insider clone mới là service. Code FastAPI trong `src/cdp_clone/` là của tuần trước, **tạm gác**, giữ lại làm nền cho `HttpCdpClient` (xem `src/cdp_clone/README.md`); tuần 1 không chạy nó.
- `cdp.products` giữ **đúng 13 trường** handbook §6. Không thêm cột; mọi thuộc tính theo loại vào `attributes` JSONB (khoá theo `SCHEMA.md`).
- Không FK từ `app` tới `cdp.events.event_id` (id nội bộ của clone). Đơn nối sang event bằng `event_group_id` + `product_id` + `using_date`.
- Không có bảng nhật ký job; job ghi kết quả ra file/report.

### 6.2. Quy tắc dữ liệu

- `available_from/to` = cửa sổ đặt chỗ 30 ngày từ `as_of` (ngày nạp), cắt với khoảng của nguồn; chuyến bay `from = to = ngày bay`. Loader nhận `--as-of`; mọi thứ có ngày (cửa sổ, `attributes.availability`, event seed, chuyến của persona) sinh tương đối theo `as_of`. Chạy lại loader trước demo.
- Lịch kín/trống ở `attributes.availability {from, days, calendar "1/0"}` — đọc-only, không có bảng tồn kho.
- Vai trò sản phẩm chỉ định nghĩa ở view `catalog.product_meta`: `variant`, `is_bookable` (property/route/điểm công cộng = false), `is_search_unit` (room/flight = false), `is_recommendable`. Chỉ đặt ở cấp `hotel_room`; property không có phòng con chỉ hiển thị.
- Combo: một dòng `cdp.products`; thành phần ở `catalog.combo_items`, parse từ `description` (job `parse_combos`, ghi `source`/`confidence`/`evidence`). `attributes.priceBasis` mặc định `per_package`, `per_person` khi text nói giá theo khách.
- Booking: CDP không có bảng booking. Checkout: `CdpClient.record_purchase(events, event_group_id)` trước → commit `app.bookings` + `booking_items` (transaction của `DATABASE_URL`) → commit lỗi thì `CdpClient.cancel_purchase(event_group_id)` bù trừ. Không gói hai connection vào một transaction.
- Vector **không** nằm trong Postgres. Collection `Product` của Weaviate giữ vector cho `is_search_unit = true`; `catalog.product_vectors` và extension `pgvector` đã gỡ (`db/migrations/0002_drop_product_vectors.sql`, chốt 22/09/2026). Model: Cohere `embed-multilingual-v3.0`, 1024 chiều. Backend tự gọi Cohere rồi tự ghi vector (`vectorizer: none`) — nạp dùng `input_type=search_document`, truy vấn dùng `search_query`; dùng sai làm giảm chất lượng xếp hạng mà không báo lỗi. Chi tiết: `docs/prd/architecture.md` §5, `docs/prd/data-model.md` §1.

### 6.3. Môi trường database

- Dev: mỗi người một Postgres local qua `make demo-db` (hoặc compose + seed thủ công) → ai cũng dùng snapshot catalog có checksum và không ai giẫm lên ai. Không dùng chung một DB để dev; `make demo-db-reset` chỉ dùng khi chủ động xoá state demo local.
- Một Postgres cloud làm **staging** chung (không cần pgvector nữa; Weaviate là service riêng, xem `docs/prd/deployment-plan.md` §1): FE/agent/demo trỏ vào; chỉ job seed (CI hoặc một người) được `--reset` nó; tạo schema lần đầu bằng `psql -f db/init/*.sql` vì cloud không chạy initdb, và mọi thay đổi schema **sau đó** bằng `python db/migrations/run.py --database-url <dsn staging>` — không chạy lại `db/init/` trên database đã có dữ liệu.

### 6.4. Còn chờ chốt

- Tên cột opt-in trong `cdp.profiles` (chờ reviewer CDP) · mọi route có ≥ 1 chuyến? (Data kiểm tra trên `products.jsonl`).
- **Bộ persona lệch giữa PRD và bản đã triển khai — không tự đồng bộ.** DDL và `docs/spec/DATABASE_SCHEMA.md` dùng cột `app.users.persona` với 4 giá trị trạng thái cold-start: `P1_frequent`, `P2_first_time`, `P3_dormant`, `P4_no_history` (mỗi persona kích hoạt một nhánh khác nhau của recommendation — bảng persona ở `DATABASE_SCHEMA.md` §8 Kế hoạch mock data). PRD lại mô tả 4 persona phong cách du lịch `P1_family`, `P2_biz`, `P3_explorer`, `P4_deal` trên cột `persona_tag` / trường `personaTag` (`docs/prd/project-brief.md` §5, `data-model.md` §2.2, `api-contract.md` §2.1), trong khi contract thật chỉ có `personaLabel` (`schemas/auth.yaml`). Khi code: theo DDL + contract. Việc hợp nhất hai bộ persona cần người dùng quyết định.

### 6.5. Nhiệm vụ tuần 1 — tạo bảng và mock data (spec đầy đủ: `docs/spec/MOCK_DATA_SPEC.md`)

Thứ tự, mỗi bước là một module trong `src/data_collection/seed/`, chạy chung từ `src/` qua `python -m data_collection.seed --as-of YYYY-MM-DD --seed 42 [--reset]`:
1. Tạo bảng: `docker compose up -d --wait postgres` chạy `db/init/*.sql` (vota + insider). Không tạo bảng bằng ORM (SQLAlchemy, Alembic, Prisma...) — DDL viết tay trong `db/` là nguồn duy nhất. Database **đã có dữ liệu** nhận thay đổi schema qua `make db-migrate` (`db/migrations/README.md`), vì `db/init/*.sql` chỉ chạy lúc initdb trên volume rỗng.
2. Ưu tiên `data/products.jsonl` khi Data đang phát triển local; bản clone sạch tự dùng snapshot nén có version trong `src/data_collection/snapshots/`. Snapshot được kiểm checksum, bung vào `data/` ignored và kèm mapping combo đã duyệt. Chỉ sinh `products.synthetic.jsonl` khi cả runtime catalog lẫn snapshot đều không có.
3. `load_products.py` — `products.jsonl` → `cdp.products`; cửa sổ 30 ngày theo `as_of`, `attributes.availability`, combo attrs.
4. `parse_combos.py` — description → `catalog.combo_items` (source/confidence/evidence).
5. `seed_histories.py` — 2.000 `cdp.profiles`, ~7.000 `cdp.events` theo chuyến, power-law, cạnh lộn xộn; profiles suy từ event.
6. `seed_app.py` — 4 persona + 50 user test; `app.bookings` chỉ cho P1.
7. `seed_insider.py` — database `insider`: partners, profiles, identifiers, events (TTL), channel_events.
8. `db/verify.sql` và `db/verify_insider.sql` phải toàn PASS, chạy bằng `SEED_DATABASE_URL` (superuser — `DATABASE_URL` không đọc được `cdp.events`/`profiles`). Kết quả tóm tắt ghi vào khối `<!-- seed-report:start -->`…`<!-- seed-report:end -->` trong `src/data_collection/README.md`, không ghi DB.

Với catalog tổng hợp (`products.synthetic.jsonl`, khoảng 400–450 dòng), hai dòng của `db/verify.sql` FAIL theo thiết kế: `products = 10320` và `is_recommendable properties >= 300` — ngưỡng của snapshot catalog thật hiện hành. Không sửa `db/*.sql` để lách; report ghi rõ hai dòng này là FAIL dự kiến. Có `src/data_collection/data/products.jsonl` thật thì cả hai tự PASS.

Mọi tỷ lệ/phân bố nằm trong `seed/config.py`. Thiếu thông tin thì hỏi, không tự thêm cột hay bảng.
