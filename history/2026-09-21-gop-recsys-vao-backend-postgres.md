# Gộp nhánh: giữ engine RecSys, chạy nó trên PostgreSQL đã seed

- Ngày: 2026-09-21
- Tác giả: Quang anh / Claude Code
- Nhánh: mockdata
- Trạng thái: hoàn thành
- Phạm vi: backend, data, cdp, docs
- Thay thế: phần catalog tổng hợp của `2026-09-20-database-mock-data-tuan-1.md` (nay dùng snapshot crawl thật 10.320 dòng)

## Mục tiêu

Merge `origin/mockdata` (`77fb099`, nối Backend với PostgreSQL + seed catalog thật) vào nhánh local đang có `898e294 add recsys simple engine`. 14 file xung đột. Người yêu cầu chốt: **giữ code RecSys**, và lấy bản seed của remote.

## Quyết định

- **`src/data_collection/seed/` (11 file) + `README.md`: lấy bản remote.** Bản remote dùng snapshot crawl **thật 10.320 sản phẩm** (nén, có checksum trong `manifest.json`), thêm `snapshot.py`/`catalog_meta.py`/`database.py`, `Makefile` và đã chỉnh `db/verify.sql` thành `products = 10320`. Catalog tổng hợp 433 dòng của entry 20/09 vốn chỉ là giải pháp tạm "cho tới khi có crawl" — crawl đã về nên nó hết vai trò. Hệ quả tốt: **hai dòng verify trước đây FAIL theo thiết kế nay PASS thật.**
- **`tests/test_seed.py` (60 test của bản cũ): xoá.** Test API không còn tồn tại (`config.ZIPF_S`…). Remote có 5 file test thay thế, 40 test, chạy từ `src/`.
- **`main.py`: lấy composition root của remote rồi wire RecSys vào**, thay vì chọn một phía. Giữ nguyên recsys `main.py` sẽ mất toàn bộ phần nối Postgres và làm hỏng 2 test mới của remote; lấy bản remote không thì RecSys không được wire. Hai đường CDP **bổ sung nhau chứ không trùng**: `clients/local_cdp_client.py` là chiều **ghi** (async: purchase, huỷ bù trừ, browse event), `cdp/postgres_cdp_reader.py` là chiều **đọc** (sync: lịch sử khách, bảng phổ biến).
- **RecSys đọc PostgreSQL thay vì file.** Thêm `PostgresVectorStore` (thay `InMemoryVectorStore` đọc `products.jsonl`) và `PostgresCdpReader` (thay `LocalCdpClient` đọc JSONL). Bám đúng ranh giới role: catalog qua `DATABASE_URL` (`vota_app` được SELECT `cdp.products`), lịch sử qua `CDP_DATABASE_URL` (`vota_app` **không** đọc được `cdp.events`). `is_search_unit`/`is_recommendable` lấy từ view `catalog.product_meta` chứ không tính lại trong Python — PRODUCT_SCHEMA §4 quy định view là nơi duy nhất định nghĩa vai trò.
- **Thống nhất import về `src.backend.app.*`** (5 file recsys + conftest). Đây là convention của 22 file remote, của `Makefile` (`uvicorn src.backend.app.main:app`) và của test; recsys chỉ dùng `app.*` ở 6 file.
- **`application/ports.py` → `application/ports/recsys.py`.** Merge tạo ra đồng thời module `ports.py` (recsys) và package `ports/` (remote); Python ưu tiên package nên `ports.py` bị che hoàn toàn, `CdpClientPort` không import được. Gộp vào package và re-export ở `__init__.py`. Không trùng tên: remote export `CdpClient`, recsys export `CdpClientPort`.
- **Route recsys mount thẳng vào `app`,** không qua `api_router`: hai router đã tự mang prefix `/api/v1`, đưa vào `api_router` sẽ thành `/api/v1/api/v1/search`.
- **`requirements.txt`: hợp hai phía** (thêm `numpy`, `sentence-transformers` vào bộ của remote).
- **`.embcache/` vào `.gitignore`**: 9 MB cache embedding sinh lúc chạy, dựng lại được từ catalog.

## Hai lỗi có sẵn phát hiện khi kiểm tra, đã sửa

1. **`make demo-db` hỏng trên mọi máy Windows.** `core.autocrlf=true` và repo chưa có `.gitattributes` nên Git đổi LF→CRLF của `combo_items_manual.jsonl`, làm sha256 lệch manifest và seed dừng ở `materialize_snapshot` (`checksum mismatch: 2fd7e744…`, mong đợi `8506b183…`). Thêm `.gitattributes` ghim `src/data_collection/snapshots/** -text`; sau khi checkout lại, checksum khớp đúng manifest.
2. **Backend và test hỏng trên Windows.** psycopg async không chạy được trên `ProactorEventLoop` — loop mặc định của Windows và của uvicorn trên Windows — nên mọi truy cập `cdp.*` qua `LocalCdpClient` trả `InterfaceError`. Đặt `WindowsSelectorEventLoopPolicy` ở composition root (cho server) và ở `tests/conftest.py` (test tự gọi `asyncio.run`). Trên Linux/macOS hai dòng này không có tác dụng gì.

## Kiểm tra

- Không còn marker xung đột nào trong repo; 14/14 file đã giải quyết.
- Seed catalog thật: `cdp.products=10320 · combo_items=218 · profiles=2000 · events=7511 · users=54 · bookings=1 · insider: profiles=2000, identifiers=6167, events=4640, channel_events=19587`.
- `db/verify.sql`: **16/16 PASS** (gồm `products = 10320` và `is_recommendable properties >= 300`). `db/verify_insider.sql`: **6/6 PASS**.
- `pytest src/backend/tests` với `RUN_POSTGRES_INTEGRATION=1`: **37 passed**, gồm 2 integration test trên database đã seed và `test_backend_wiring` của remote.
- `unittest` seed của remote (chạy từ `src/`): **40 passed, 1 skipped**.
- Chạy thật bằng `TestClient` trên database đã seed: nạp **2.897 search unit** từ PostgreSQL, `/health` 200, `/api/v1/search` 200 trả đúng khách sạn/combo Nha Trang cho truy vấn tiếng Việt, `/api/v1/recommendations?cdp_user_id=VP0000001` 200 trả attraction + flight + combo (P1 đã đặt khách sạn, chưa có vé bay), `/api/v1/popular` 200. Không có đường dẫn `/api/v1/api/v1/*`.

## Còn lại / rủi ro

- `catalog.product_vectors` vẫn trống đúng kế hoạch; RecSys tự embed lúc khởi động rồi cache ra `.embcache/`. Lần chạy đầu tải model `intfloat/multilingual-e5-base` và embed 2.897 unit nên chậm; lần sau đọc cache. Job `embed_products` dùng pgvector là việc tuần 2, khi đó `PostgresVectorStore` đọc thẳng `catalog.product_vectors` thay vì tự embed.
- `InMemoryVectorStore` và `cdp/local_cdp_client.py` (đọc JSONL) giữ lại cho test offline và cho người chạy không có Postgres; đường chạy thật đã chuyển sang bản Postgres.
- RecSys lấy `cdp_user_id` từ query param — `recommendations.py` còn `TODO` chuyển sang JWT.
- Chưa đo lại chất lượng gợi ý trên catalog thật: `report.py` của remote ghi baseline most-popular Recall@20 = 57,7% (attraction 78%, hotel 24%). Evaluation cần chạy bộ đo riêng (`src/evaluation`) trước khi kết luận.
- `.env` vẫn chưa tạo; backend và seed hiện chạy bằng giá trị mặc định trong code. Cần `cp .env.example .env` khi đổi cấu hình.
