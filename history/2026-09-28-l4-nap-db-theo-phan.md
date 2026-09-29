# L4: nạp DB theo phần trong lúc cào; prepare_rows tra dòng cũ theo mọi ref

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

L4 của `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`: "đủ catalog nào thì nạp cái đó" (người yêu cầu chốt 2026-09-28).

## File thay đổi

- `src/data_collection/fresh_catalog_db.py` — sửa `prepare_rows`:
  - tra dòng cũ bằng `sourceRef` rồi `sameAs` của dòng mới;
  - dòng giữ đổi nguồn: ref mới vào `sameAs`;
  - nhiều dòng cũ cùng khớp: giữ dòng khớp trước; dòng kia `available=false`, `attributes.mergedInto=<dòng giữ>`
    (`counts.mergedAway`);
  - bỏ qua dòng có `mergedInto` khi dựng bảng tra.
- `src/data_collection/stream_feed.py` — thêm `select_ready`, `DbFeeder`, `source_health`, `row_hash`.
- `src/data_collection/fresh_catalog.py` — sửa:
  - `Previewer(run_dir, destinations, db_url, index_config)` tạo `Ticker('db', DbFeeder)` khi `stream.enabled` và `stream.db`;
  - `crawl_and_load`, `execute` truyền `index_config`;
  - thêm `save_run()`.
- `src/data_collection/fresh_settings.py` — sửa: thêm `stream.db` (mặc định tắt), `stream.dbSeconds` (60), `stream.minRecords` (20).
- `src/data_collection/tests/test_stream_feed.py` — thêm: test `prepare_rows` qua nhiều lô, `select_ready`, `DbFeeder`.
- `src/data_collection/tests/test_stream_feed_db.py` — thêm: 2 test với Postgres thật (chỉ chạy khi có `STREAM_TEST_ADMIN_URL`).
- `src/data_collection/tests/test_normalise_stream.py` — sửa: thêm `PreviewerFeedTests`.
- `docs/spec/data-collection/schema.md` — sửa: thêm khoá `mergedInto` vào bảng §3.1.

## Quyết định

- "Đủ" theo mục Đã chốt 1 của plan, cụ thể hoá:
  - qua `validate_catalog([dòng], allow_external_parents=True)`;
  - site (phần đầu `sourceRef`) có ≥ `stream.minRecords` bản ghi, tỉ lệ lỗi ≤ `normalise.maxErrorPercent`, không checkpoint `failed`;
  - dòng con chỉ nạp khi cha đã nạp trong lượt hoặc cùng lô;
  - **khách sạn Trip và combo luôn để bước nạp chính thức** (coverage giá chỉ biết ở cuối; FK `catalog.combo_items`).
- Nạp bằng đúng `load_into_db` của bước chính thức (upsert, advisory lock, không xoá), `coverage=None`. Mỗi lô ghi
  `db_batches/<n>/` và một dòng `db_batches.jsonl`. Lô lỗi được thử lại ở chu kỳ sau, không hỏng lượt.
- Bước nạp chính thức cuối lượt và quality gate giữ nguyên. Quality gate không đạt thì dòng đã nạp theo phần **ở lại**
  (Đã chốt 2). Đích là `DB_TARGET` của lượt (local hoặc cloud) — người yêu cầu xác nhận job đang nạp cả local và cloud.
- Sửa `prepare_rows` cũng sửa một lỗi tiềm ẩn của nạp theo lô: lượt sau gộp hai khách sạn đã nạp riêng thì trước đây lượt
  kế tiếp lỗi "sourceRef/sameAs conflict".
- `mergedInto` là khoá mới trong `attributes`. PRD `data-model.md` §3.1 chỉ nêu ví dụ, không cấm khoá mới, nên đây không phải
  lệch PRD; spec đã cập nhật.

## Kiểm tra

- `pytest tests/test_stream_feed.py` (env `vsf`):
  - agoda về trước, booking thành dòng giữ → một `product_id`, không conflict ở các lần sau;
  - hai dòng nạp riêng rồi gộp → một dòng ẩn `mergedInto`; phòng đổi cha đúng; một lần nạp như trước không đổi;
  - `select_ready` đủ 5 lý do giữ lại; `DbFeeder` chỉ nạp dòng mới/đổi, lỗi thì lần sau nạp lại.
- **Postgres thật** (docker local, superuser từ `.env`): `tests/test_stream_feed_db.py` **2 passed**.
  - Test tạo database tạm `vota_stream_test_<pid>` **từ `template0`**, vì `template1` của Postgres local lệch phiên bản
    collation (2.36 vs 2.41). Không sửa `template1`.
  - Database tạm bị xoá sau test: chỉ còn `vota`, `vota_crawl`, `vota_crawl_demo`.
  - Kịch bản: nạp theo lô 1 (agoda + phòng) → lô 2 (booking giữ, sameAs agoda, phòng booking, phòng agoda đổi cha) → nạp
    chính thức: 3 dòng, `new=0`, `mergedAway=0`, không lỗi.
- `PreviewerFeedTests`: gộp thật → `DbFeeder` nạp (giả lập) không có khách sạn Trip / combo, không nạp lại khi không đổi.

## Còn lại / rủi ro

- Chưa chạy trong lượt cào thật với DB thật, và chưa bao giờ nạp theo phần vào cloud.
- FE/agent đọc DB staging sẽ thấy dòng mới xuất hiện dần (đã chốt).
- `db_load.jsonl` (bảng trước → sau của monitor) chỉ có lần nạp chính thức; mỗi lô có `db_batches/<n>/db_load.jsonl` riêng.
- Chưa commit.
