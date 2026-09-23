# Migrate data collection vào monorepo

- Ngày: 2026-09-23
- Tác giả: Đăng Khôi / Codex
- Nhánh: `feat/catalog-sync-cohere`
- Trạng thái: hoàn thành
- Phạm vi: data, database, backend integration test, docs

## Mục tiêu

Chuyển phần cần thiết của repository standalone `/home/dangkhoi/code/vsf/data-collection` vào
`src/data_collection` mà không mang Git history, raw cache, browser profile, crawl state, backup, log,
temp/staging hay secret. Sau thay đổi này monorepo là source chính duy nhất cho crawl → normalize →
catalog → DB; catalog chuẩn 11.387 sản phẩm được giữ làm baseline có checksum.

## File thay đổi

- `AGENTS.md` — sửa: cập nhật ngưỡng snapshot hiện hành từ 10.320 lên 11.387.
- `Makefile` — sửa: trỏ `CATALOG_SNAPSHOT` mặc định tới snapshot 2026-09-23.
- `README.md` — sửa: cập nhật quy mô snapshot demo.
- `db/verify.sql` — sửa: kiểm tra chính xác 11.387 sản phẩm.
- `docs/MOCK_DATA_SPEC.md` — sửa: cập nhật snapshot, số đo seed 42 và quy tắc ưu tiên lịch phòng thật khi dữ liệu đủ dày.
- `docs/PRODUCT_SCHEMA.md` — sửa: mô tả lịch thật/fallback của loader.
- `src/backend/tests/integration/test_local_postgres_adapters.py` — sửa: cập nhật kỳ vọng số sản phẩm của snapshot mới.
- `src/data_collection/.env.example` — thêm: mẫu biến token, không chứa secret, dùng mật khẩu Postgres local của compose.
- `src/data_collection/README.md` — sửa: xác lập source of truth, lệnh automation, snapshot mới và ranh giới 13 trường catalog/14 trường API.
- `src/data_collection/api_sources.py` — thêm: nhận, phân loại và đổi dạng dữ liệu từ API.
- `src/data_collection/apify_source.py` — thêm: client Apify có giới hạn chi phí và che token.
- `src/data_collection/batch.py` — thêm: điều phối job thu thập theo batch/thành phố.
- `src/data_collection/catalog.py` — thêm: split/merge catalog và kiểm tra xung đột.
- `src/data_collection/crawl.py` — sửa: tích hợp nguồn/chế độ crawl mới.
- `src/data_collection/normalise.py` — sửa: mang logic chuẩn hoá mới nhất, vẫn xuất đúng 13 trường CDP.
- `src/data_collection/deepen_jobs.py` — thêm: mở rộng job Booking đã hoàn tất mà không cào lại trang cũ.
- `src/data_collection/retry_unpriced.py` — thêm: retry có kiểm soát các bản ghi chưa có giá.
- `src/data_collection/pipeline_demo.py` — thêm: pipeline tự động ingest → normalize → loader → PostgreSQL local `vota_demo*`.
- `src/data_collection/monitor.py` — thêm: HTTP monitor local và API điều khiển pipeline.
- `src/data_collection/monitor_ui/index.html` — thêm: giao diện theo dõi crawler.
- `src/data_collection/monitor_ui/pipeline.html` — thêm: giao diện theo dõi pipeline và guardrail DB.
- `src/data_collection/parse_combos.py` — thêm: CLI tương thích gọi parser canonical trong `seed/`.
- `src/data_collection/load_catalog.py` — thêm: CLI tương thích gọi loader canonical trong `seed/`.
- `src/data_collection/make_docs.py` — thêm: sinh tài liệu bàn giao từ catalog.
- `src/data_collection/make_handover.py` — thêm: đóng gói bàn giao local, dùng `seed.catalog_meta` hiện hành.
- `src/data_collection/make_sample.py` — sửa: projection sample API thêm `priceUnit=UNKNOWN`, không suy từ taxonomy và không đổi catalog 13 trường.
- `src/data_collection/finalize_catalog.sh` — thêm: finalize catalog sau crawl.
- `src/data_collection/cron_run.sh` — thêm: job định kỳ nguồn live/API, dùng compose ở repository root.
- `src/data_collection/cron_hotels_daily.sh` — thêm: job khách sạn hằng ngày và staging riêng.
- `src/data_collection/run_extra_queue.sh` — thêm: hàng đợi crawl bổ sung có resume.
- `src/data_collection/stop_crawl.sh` — thêm: dừng êm các tiến trình crawl.
- `src/data_collection/collectors/booking_attractions.py` — sửa: logic collector mới nhất.
- `src/data_collection/collectors/booking_base.py` — sửa: logic dùng chung Booking mới nhất.
- `src/data_collection/collectors/booking_hotels.py` — sửa: logic khách sạn Booking mới nhất.
- `src/data_collection/collectors/common.py` — sửa: hạ tầng cache/state/rate-limit mới nhất.
- `src/data_collection/collectors/geo.py` — sửa: mapping và kiểm tra vị trí mới nhất.
- `src/data_collection/collectors/plan.py` — sửa: kế hoạch điểm đến và budget mới nhất.
- `src/data_collection/collectors/trip.py` — sửa: logic Trip.com mới nhất.
- `src/data_collection/collectors/vinpearl.py` — sửa: lưu bằng chứng ngày đã hỏi giá.
- `src/data_collection/collectors/booking_flights.py` — thêm: collector chuyến bay Booking.
- `src/data_collection/collectors/trip_combos.py` — thêm: collector combo bay + ở Trip.com.
- `src/data_collection/collectors/trip_hotels.py` — thêm: collector khách sạn Trip.com.
- `src/data_collection/docs/BANGIAO.md` — sửa: tài liệu bàn giao catalog 11.387 sản phẩm.
- `src/data_collection/docs/SCHEMA.md` — sửa: schema/độ phủ sinh từ catalog 11.387 sản phẩm.
- `src/data_collection/docs/CATALOG_STATS.md` — thêm: thống kê catalog hiện hành.
- `src/data_collection/docs/RUN_BY_CITY.md` — thêm: hướng dẫn chạy theo thành phố trong monorepo.
- `src/data_collection/docs/template.json` — thêm: mapping schema máy đọc được.
- `src/data_collection/docs/EXPAND_CATALOG.md` — sửa: bỏ đường dẫn tuyệt đối sang repository cũ.
- `src/data_collection/docs/bao-cao-ban-giao.md` — sửa: cập nhật đường dẫn source chính.
- `src/data_collection/seed/README.md` — sửa: snapshot mặc định 2026-09-23.
- `src/data_collection/seed/config.py` — sửa: snapshot mặc định 2026-09-23.
- `src/data_collection/seed/load_products.py` — sửa: merge có kiểm soát lịch phòng thật từ pipeline mới, giữ toàn bộ loader/DDL hiện hành.
- `src/data_collection/snapshots/README.md` — sửa: mô tả snapshot mới và giữ snapshot cũ để tái lập phép đo.
- `src/data_collection/snapshots/2026-09-23/products.jsonl.gz` — thêm: catalog 11.387 dòng nén tất định.
- `src/data_collection/snapshots/2026-09-23/combo_items_manual.jsonl` — thêm: 64 mapping combo duyệt tay.
- `src/data_collection/snapshots/2026-09-23/manifest.json` — thêm: số dòng và checksum catalog/mapping.
- `src/data_collection/tests/fixtures/booking-flight-detail.html` — thêm: fixture DOM offline.
- `src/data_collection/tests/test_api_sources.py` — thêm: test API intake/adapters/token/monitor.
- `src/data_collection/tests/test_batch.py` — thêm: test batch và catalog roundtrip.
- `src/data_collection/tests/test_booking_attractions.py` — thêm: test parser giá/scroll.
- `src/data_collection/tests/test_booking_flights.py` — thêm: test collector chuyến bay Booking.
- `src/data_collection/tests/test_booking_search.py` — thêm: test trạng thái hoàn tất trang tìm kiếm.
- `src/data_collection/tests/test_deepen_jobs.py` — thêm: test mở rộng job có resume.
- `src/data_collection/tests/test_make_sample.py` — thêm: test projection 13 trường catalog → ProductSummary có `priceUnit=UNKNOWN`.
- `src/data_collection/tests/test_pipeline_demo.py` — thêm: test guardrail, pipeline, monitor và Apify giả.
- `src/data_collection/tests/test_plan.py` — thêm: test cấu hình điểm đến.
- `src/data_collection/tests/test_retry_unpriced.py` — thêm: test retry giá.
- `src/data_collection/tests/test_trip_combos.py` — thêm: test parser combo Trip.com.
- `src/data_collection/tests/test_trip_hotels.py` — thêm: test parser khách sạn Trip.com.
- `src/data_collection/tests/test_trip_routes.py` — thêm: test discovery tuyến bay.
- `src/data_collection/tests/test_quality.py` — sửa: mang test chất lượng/normalise mới nhất.
- `src/data_collection/tests/test_seed_load_products.py` — sửa: test integration lịch thật ≥ 85% và fallback dữ liệu thưa.
- `src/data_collection/data/products.jsonl` — thay local, Git-ignored: bản runtime nguyên byte 11.387 sản phẩm từ nguồn cũ.
- `src/data_collection/data/combo_items_manual.jsonl` — thay local, Git-ignored: mapping runtime trùng checksum snapshot.

## Quyết định

- Không dùng subtree/submodule/merge history; file được đưa vào như source mới nên không kéo commit hay `.git` của repository cũ.
- Không copy `.env`, raw response, browser profile, cache, backup, log, crawl state, staging, temp, `__pycache__` hoặc output sinh không cần thiết.
- Giữ `src/data_collection/seed` và DDL root làm canonical. Hai CLI wrapper chỉ duy trì tương thích với script mới; không tạo loader/parser thứ hai.
- Catalog canonical và `cdp.products` giữ đúng 13 trường. `priceUnit` thuộc API `ProductSummary`; sample projection dùng `UNKNOWN` theo contract baseline thay vì suy từ taxonomy.
- Khi Vinpearl đã hỏi ≥ 26/30 ngày, loader dùng lịch thật; dưới ngưỡng này vẫn dùng lịch mô phỏng để không biến “chưa hỏi” thành “hết phòng”.
- Pipeline DB chỉ cho host loopback và database tên `vota_demo*`; dùng PostgreSQL/DDL hiện hành của monorepo, không chạm `vota`/`insider`.
- Catalog runtime SHA-256 `518a9aa7820c9ded4a02a2c9148af2ffa4103272071c84b6e0235f4ee251d862`; gzip SHA-256 `1b11d9054ff20429c884aa9df8f5a84cce731037c24b1d8e1d7f261b772d50a9`.

## Kiểm tra

- `python -m unittest discover -s data_collection/tests -t data_collection -v` với conda `vsf` và đúng `PYTHONPATH` → **260 test PASS, 2 skip**; test HTTP giả chạy trên loopback, không gọi dịch vụ thật.
- Sau khi merge lịch thật/sample projection: 15 test mục tiêu (`test_make_sample`, `test_seed_load_products`, `RealCatalogSmoke`) → **PASS**; test `ResourceWarning` riêng → **PASS**.
- `python -m data_collection.seed --products .../2026-09-23/products.jsonl.gz --as-of 2026-09-23 --seed 42 --generate-only` → **PASS**: 11.387 products, 307 combo items, 2.000 profiles, 7.145 events; PostgreSQL không đổi.
- Kiểm tra catalog → **11.387 dòng, đúng 13 field mỗi dòng, 0 productId trùng, 0 sourceRef trùng**; runtime và nguồn cũ cùng SHA-256.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → **PASS**: 70 schemas, 50 grounded products và CDP clone fixtures.
- `bash -n` trên sáu shell script data collection → **PASS**.
- Parse AST toàn bộ 68 file Python data collection → **PASS**.
- Hai CLI wrapper `parse_combos.py --help` và `load_catalog.py --help` → **PASS**.
- Backend PostgreSQL integration file → **2 skip** vì `RUN_POSTGRES_INTEGRATION`/database không được bật; không có ghi DB trong task này.
- `git diff --check` → **PASS**; repository standalone nguồn vẫn clean sau migration.

## Còn lại / rủi ro

- DDL và tài liệu DB hiện vẫn là `vector(768)`, trong khi model đã được chốt là Cohere `embed-multilingual-v3.0`; chưa đổi dimension/reindex trong task migration này. Phải chốt và migrate đồng bộ schema, code và docs trước khi ghi Cohere vector vào `catalog.product_vectors`.
- Generate-only cho thấy lịch hạng phòng baseline có tỷ lệ ngày đóng trung bình 95% sau khi cắt theo cửa sổ nguồn. Đây là dữ liệu ngày crawl đã cũ/hẹp, không phải lỗi checksum; automation cần crawl lại đủ 30 ngày trước demo để lịch thật/fresh thay thế baseline.
- Chưa chạy `db/verify.sql` trên PostgreSQL thật trong task này; chạy `make demo-db-reset AS_OF=2026-09-23` khi muốn nạp/reset database local.
- 67 thành phần combo vẫn nằm trong hàng đợi soát tay; 64 mapping duyệt tay đã được giữ nguyên.
