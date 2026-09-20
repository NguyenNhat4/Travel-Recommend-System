# Hoàn thành seed catalog thật theo DDL chính thức

- Ngày: 2026-09-21
- Tác giả: Đặng Khôi / Codex
- Nhánh: mockdata-work
- Trạng thái: hoàn thành
- Phạm vi: data, cdp, insider, evaluation, docs
- Tiếp nối: `2026-09-20-database-mock-data-tuan-1.md` (hoàn thành phần B/C còn dang dở)

## Mục tiêu

Đưa snapshot catalog thật 10.320 dòng vào quy trình seed của repository Travel theo DDL chính thức, không tạo lịch sử Git từ repository crawl, không commit catalog runtime, không tạo embedding ở tuần 1, và tạo đủ dữ liệu CDP/app/Insider để demo RecSys. Hoàn thiện package, test, report và kiểm tra database mà entry ngày 20/09 còn để dang dở.

## File thay đổi

- `AGENTS.md` — sửa: cập nhật ngưỡng verify và đường dẫn runtime catalog hiện hành.
- `db/verify.sql` — sửa: dùng đúng tên `SEED_DATABASE_URL` trong hướng dẫn và kiểm tra đúng 10.320 sản phẩm.
- `docs/MOCK_DATA_SPEC.md` — sửa: đường dẫn catalog ignored, ngưỡng snapshot 10.320 và Zipf 0.8 đã hiệu chỉnh.
- `src/data_collection/README.md` — sửa: thêm lệnh seed/verify và khối báo cáo snapshot thực tế.
- `src/data_collection/requirements.txt` — sửa: thêm `psycopg[binary]` cho loader PostgreSQL.
- `src/data_collection/seed/README.md` — sửa: thay placeholder bằng hướng dẫn package thật.
- `src/data_collection/seed/__init__.py` — thêm: khai báo package seed.
- `src/data_collection/seed/__main__.py` — thêm: CLI điều phối parse → load → history/app → Insider → report.
- `src/data_collection/seed/catalog_meta.py` — thêm: quy tắc variant, search/bookable/recommendable và lịch khả dụng dùng chung.
- `src/data_collection/seed/config.py` — thêm: đường dẫn, connection, quy mô và tham số phân bố tập trung.
- `src/data_collection/seed/database.py` — thêm: COPY theo transaction và reset an toàn cho hai database local.
- `src/data_collection/seed/gen_products.py` — thêm: catalog fallback deterministic khi chưa có dữ liệu crawl.
- `src/data_collection/seed/load_products.py` — thêm: đổi 13 trường catalog sang `cdp.products`, cắt cửa sổ ngày và gắn combo attributes.
- `src/data_collection/seed/parse_combos.py` — thêm: parse/map combo theo enum DDL, giữ mapping manual.
- `src/data_collection/seed/report.py` — thêm: đọc số đếm DB và chỉ cập nhật khối `seed-report`.
- `src/data_collection/seed/seed_app.py` — thêm: biên dữ liệu app users/bookings từ history seed.
- `src/data_collection/seed/seed_histories.py` — thêm: 2.000 profile, event theo chuyến, persona và edge case deterministic.
- `src/data_collection/seed/seed_insider.py` — thêm: partners/profiles/identifiers/events/channel events có TTL và opt-out.
- `src/data_collection/tests/test_seed_load_products.py` — thêm: unit test meta, cửa sổ, calendar, flight và loader.
- `src/data_collection/tests/test_seed_parse_combos.py` — thêm: unit test parser, mapping, confidence, unit và manual rows.
- `src/data_collection/tests/test_seed_histories.py` — thêm: unit/smoke test history, lifecycle, persona, booking, noisy edges và catalog thật.
- `src/data_collection/tests/test_seed_insider.py` — thêm: unit test TTL, identity history, GDPR, funnel và tính deterministic.
- `history/2026-09-21-hoan-thanh-seed-catalog.md` — thêm: entry này.

Runtime artifact dưới `src/data_collection/data/` (catalog, mapping manual, output loader/seed/report) bị `.gitignore` loại bỏ và không thuộc thay đổi Git.

## Quyết định

- Chỉ copy logic thuần dữ liệu đã được kiểm thử từ repository crawl; Travel sở hữu package seed, database loader và test. Không thêm remote/subtree/cherry-pick và không mang lịch sử commit của repository crawl vào Travel.
- `src/data_collection/data/products.jsonl` là runtime artifact duy nhất của catalog thật trong Travel: 10.320 dòng, SHA-256 `89f452e46eec24ae0fe50769037bc84dbb2609dd9c193a49336108f072acbb18`; vẫn bị Git ignore.
- Không sửa DDL, không thêm bảng/cột, không ghi vector. `catalog.product_vectors` để 0; 2.897 dòng `is_search_unit` là cha/search unit cần embed ở tuần 2, không phải số sản phẩm đã được embed.
- Không xoá purchase thiếu `event_group_id`. Seed cố ý bỏ group cho 3% purchase để mô phỏng dữ liệu CDP bẩn; `db/verify.sql` cho phép tối đa 4%.
- Giữ 64 mapping combo đã soát tay dưới thư mục ignored. Kết quả: 93/93 combo có item, 83/111 thành phần có thể map đã map confidence cao, hàng đợi review còn 0.
- Hiệu chỉnh Zipf từ 1.1 xuống 0.8 trên snapshot thật: popular-in-destination Recall@20 giảm từ 65,7% xuống 57,7%, dưới trần 60% của definition of done nhưng vẫn giữ phân bố purchase lệch (top 10% sản phẩm chiếm 40%).
- `--reset` chỉ dành cho PostgreSQL local/dev: truncate state app/CDP/catalog liên quan rồi nạp lại trong transaction; không có đường kết nối production mặc định.

## Kiểm tra

- `PYTHONPATH=.. conda run -n vsf python -m unittest discover -s tests -t . -v` từ `src/data_collection` → **52/52 PASS**, gồm smoke test catalog thật.
- `python -m data_collection.seed --as-of 2026-09-21 --seed 42 --generate-only` → sinh đủ artifact từ 10.320 products.
- `python -m data_collection.seed --as-of 2026-09-21 --seed 42 --reset` với hai URL local → nạp **10.320 products, 2.000 profiles, 7.511 events, 218 combo items, 54 app users, 1 booking; Insider 2.000 profiles, 4.640 events, 19.587 channel events**.
- `db/verify.sql` trên database `vota` → **16/16 PASS**.
- `db/verify_insider.sql` trên database `insider` → **6/6 PASS**.
- Baseline popular-in-destination Recall@20 → **184/319 = 57,7%**, đạt yêu cầu không gần 0 và không vượt 0,60.
- `validate_contract.py` → chưa PASS do lỗi tồn tại sẵn ngoài phạm vi seed: fixture `src/shared/mocks/itinerary-agent/products.json` thiếu required field `priceUnit` (`KeyError: 'priceUnit'`). Đã cài `jsonschema` và `PyYAML` vào conda env `vsf` để loại trừ lỗi dependency; thay đổi task này không sửa OpenAPI/fixture.
- `git diff --check` → PASS trước khi tạo entry; chạy lại ở vòng kiểm tra cuối.

## Còn lại / rủi ro

- Backend chỉ dùng dữ liệu này khi cấu hình các URL local tương ứng và các adapter PostgreSQL/CDP của Backend được hoàn thiện; task này hoàn thành seed/database, không mở rộng code Backend.
- Embedding của 2.897 search unit và model recommendation thuộc tuần 2, chưa làm trong task này theo handbook.
- Contract validator còn lỗi fixture `priceUnit` nói trên; cần một task contract riêng vì sửa fixture/API ngoài phạm vi data seed.
- Chưa commit, chưa push theo yêu cầu. Container local của worktree đang chạy trên cổng 5432 để người dùng có thể kiểm tra/demo.
