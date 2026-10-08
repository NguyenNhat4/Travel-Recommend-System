# Nạp lại catalog chỉ khi mã băm phía Postgres đổi

- Ngày: 2026-10-07
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl (dựng trên `origin/release-mvp-v2` 737ede4)
- Trạng thái: hoàn thành
- Phạm vi: backend, docs
- Thay thế: phần "nạp đầy đủ mỗi 15 phút" trong mục Quyết định của `2026-09-24-luong-cao-index-backend-sau-audit.md`

## Mục tiêu

Team agent chạy backend local trỏ DB staging qua SSH tunnel. Mỗi lần khởi động mất khoảng 3 phút, và cứ 15 phút
`RecsysRefresher` lại kéo toàn bộ `cdp.products` thêm một lần: 16.740 dòng, khoảng 51 MB, đo được 127 s qua tunnel.
Catalog chỉ đổi khoảng một lần mỗi ngày khi job cào ghi DB, nên gần như mọi lần kéo đều ra dữ liệu cũ. Người dùng
chốt: không nạp lại toàn bộ catalog mỗi 15 phút. Giữ chu kỳ 900 giây và độ trễ dữ liệu tối đa 15 phút như spec §2.4.
Phục vụ NFR-PERF-01 và FR-SRC-01/FR-REC-01: dữ liệu search/recsys theo kịp catalog.

## File thay đổi

- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: thêm `_FINGERPRINT_QUERY`, là mã băm md5 tính phía
  DB của đúng `_QUERY` và `_COMBO_QUERY`, trả một dòng. `PostgresCatalogReader.load()` hỏi mã trước; nếu trùng lần
  trước thì trả lại `CatalogUnits` đang giữ, nếu khác thì kéo đầy đủ (`_load_full`, chính là thân `load` cũ). Hỏi mã
  lỗi thì kéo đầy đủ và không lưu cache.
- `src/backend/tests/unit/infrastructure/test_postgres_catalog_reader.py` — thêm: 6 test cho các trường hợp mã trùng
  thì dùng lại, mã đổi thì kéo lại, hỏi mã lỗi thì kéo đầy đủ, kéo lỗi thì giữ cache cũ, lỗi kết nối bị nuốt kèm log,
  câu băm chứa đúng hai câu SELECT.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.4 — sửa: thêm câu mô tả việc so mã băm.
- `src/backend/README.md` — sửa: câu chu kỳ nạp lại.

## Quyết định

- Lấy mã băm **trước** khi kéo. Nếu catalog đổi giữa hai bước thì lần sau mã khác và sẽ kéo lại, không bỏ sót.
- Băm trên chính câu SELECT mà backend dùng, không dùng `pg_stat_user_tables` hay cột `updated_at` (`cdp.products`
  không có cột này). Như vậy mọi thay đổi backend có thể nhìn thấy đều làm đổi mã, kể cả thay đổi ở view
  `catalog.product_meta`.
- Chỉ cache phần catalog. Phần kiểm vector Weaviate (`missing`/`staleText`) và `BuildPopularity` từ `cdp.events` vẫn
  chạy mỗi chu kỳ, vì chúng đổi độc lập với catalog (job index, lượt mua mới).
- Không đổi `CATALOG_REFRESH_SECONDS` (900), API, contract hay PRD. Khác với phương án "query chữ ký 60 giây" bị bỏ
  ngày 24/09: lần này không tăng tần suất, chỉ bỏ những lần kéo vô ích.
- Không làm trong lần này: thời gian **khởi động** lần đầu vẫn kéo đầy đủ (~2–3 phút qua tunnel). Các hướng đã nêu
  với người dùng: dev bằng Postgres local, tunnel `ssh -C`, cache catalog ra đĩa theo mã băm.

## Kiểm tra

Chạy trên `origin/release-mvp-v2` (737ede4) cộng với thay đổi này, conda `vsf2` (Python 3.11.16, cùng bản với CI):

- Các bước của job `CI checks` trong `backend-ci-cd.yml`:
  - `validate_contract.py`: PASS (117 schemas, 93 fixtures).
  - `compileall src/backend src/data_collection`: ok.
  - `bash -n` script deploy và `test-backend-vm-cd-sync.sh`: passed.
  - `pytest src/backend/tests`: **1818 passed, 35 skipped**, 0 failed.
- `RUN_POSTGRES_INTEGRATION=1` với Postgres local, Weaviate trỏ local:
  - 19 lỗi (auth/booking/role) do DB local chưa migrate tới schema mvp2 và seed lệch (2.005 profile).
  - Chạy y hệt trên `release-mvp-v2` gốc cho **đúng 19 lỗi đó**, nên các lỗi này không thuộc thay đổi này.
  - `test_catalog_postgres.py` và `test_postgres_search_logs.py`: pass.
- Đầu-cuối với `RecsysRefresher` và `build_recsys` thật, Postgres local (11.708 dòng → 3.183 search unit), Weaviate giả
  trả metadata đúng model, 3 lần reload:
  - Lần 1 kéo đầy đủ, 9,33 s.
  - Lần 2 và 3 log `recsys.catalog.unchanged`, mất 1,32 s và 1,41 s, dùng lại đúng danh sách unit.
  - Popularity và engine vẫn được dựng mới mỗi lần.
- Phát hiện thay đổi:
  - Tăng `unit_price` một search unit thêm 1 (bằng `SEED_DATABASE_URL`) → reload kéo lại và thấy giá mới.
  - Trả giá về như cũ → kéo lại lần nữa.
  - Không đổi gì → dùng lại. DB local đã được trả về nguyên trạng.
- Staging qua tunnel, chỉ đọc, chạy trên nhánh `bench_search_recomSys` trước khi dựng lại trên mvp2:
  - Câu mã băm mất 1,62 s, hai lần liên tiếp ra cùng mã.
  - Lần 1 kéo 16.740 dòng trong 287,1 s; lần 2 log `unchanged` và mất 3,0 s.

## Còn lại / rủi ro

- Khởi động lần đầu qua tunnel vẫn mất vài phút, vì phải kéo đầy đủ.
- Mỗi chu kỳ, DB tốn khoảng 1–1,5 s để băm catalog.
