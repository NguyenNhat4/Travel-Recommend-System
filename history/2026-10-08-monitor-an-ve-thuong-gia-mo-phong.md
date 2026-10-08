# Monitor không hiện bước con "vé thương gia mô phỏng"

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: fix/full-refresh-stable → đẩy lên `test/newcrawl`
- Trạng thái: hoàn thành (chưa deploy)
- Phạm vi: data

## Mục tiêu

Người dùng muốn monitor chỉ hiện các bước xử lý; phần dữ liệu demo (vé thương gia mô phỏng) không hiện thành tiến trình.
Sửa tiếp `history/2026-10-08-monitor-tien-do-va-buoc-con.md` (entry đó ghi Bảo trì DB 7 và Nạp DB 8 bước con). Không lệch PRD:
vé mô phỏng vẫn sinh như FR-CAT-03 / `data-model.md` §3, chỉ đổi cách hiện trên monitor.

## File thay đổi

- `src/data_collection/fresh_catalog_db.py` — sửa: `maintain_catalog`, `load_into_db` vẫn gọi `simulated_business.sync` (số đếm
  vẫn vào kết quả bước) nhưng không ghi bước con / dòng log `catalog.substep` cho việc này.
- `src/data_collection/monitor.py` — sửa: `EXPECTED_SUBSTEPS` maintain 7 → 6, db 8 → 7.
- `src/data_collection/tests/test_simulated_business.py` — sửa: test nạp DB thật kiểm vé mô phỏng vẫn được ghi nhưng không có
  bước con / dòng log nào về nó.

## Kiểm tra

- `pytest -q tests` (`src/data_collection`, vsf2): 582 passed, 27 skipped.
- `SIMULATED_TEST_DATABASE_URL` (DB tạm trên Postgres sandbox): 9 passed, 1 failed — test đỏ có sẵn trên code gốc
  (`test_fresh_maintenance_follows_the_env_switch`); test vừa sửa xanh.
- `maintain_catalog` trên DB sandbox `vota_crawl_refresh`: bước con = đọc catalog, danh sách làm mới, hết hạn giá Trip, cuộn cửa
  sổ 30 ngày, ghi DB, parse thành phần combo; `simulatedBusiness` = 190 (vẫn đồng bộ).

## Còn lại / rủi ro

- Số đếm vé mô phỏng vẫn có trong `detail` của bước (tab "Chi tiết bước" dạng JSON); không hiện trên sơ đồ.
