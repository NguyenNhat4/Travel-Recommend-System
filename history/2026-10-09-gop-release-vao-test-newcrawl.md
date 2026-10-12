# Gộp `release-mvp-v2` mới nhất vào `test/newcrawl` trước khi mở PR dữ liệu mô phỏng

- Ngày: 2026-10-09
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `test/newcrawl`
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

`release-mvp-v2` đã đi tiếp (PR #124, #131, #133, #135–#137: agent, search-production, CD cụm HA) sau khi nhánh dữ liệu mô phỏng
(`f1f3b9e7`, entry `2026-10-09-mock-thanh-phan-combo-ve-phu-ngay-va-phong.md`) được push. Gộp để PR `test/newcrawl` → `release-mvp-v2` không
xung đột. FR-CAT-03, FR-CAT-04.

## File thay đổi

- `src/data_collection/normalise.py` — sửa (giải xung đột): `departDate` / `returnDate` của combo Trip dùng
  `collectors/textutil.trip_combo_dates` của `release-mvp-v2` (commit 4ebd6420); bỏ hàm trùng `_trip_combo_day` của nhánh mock.
- `src/data_collection/tests/test_trip_combos.py` — sửa: bỏ `ComboDatesTests` (test hàm đã bỏ; `release-mvp-v2` có test riêng cho
  `trip_combo_dates`, `test_fresh_catalog_job`, `test_seed_load_products`).
- `src/data_collection/tests/fixtures/normalise_sample/expected_products.jsonl` — lấy bản của `release-mvp-v2`.
- `history/2026-10-09-gop-release-vao-test-newcrawl.md` — thêm: entry này.
- Các file còn lại do merge mang vào từ `release-mvp-v2`, không sửa tay.

## Quyết định

- Giữ bản sửa ngày combo của đồng đội (4ebd6420) thay cho bản của nhánh mock: cùng mục đích, nhưng áp cả seed lẫn `apply_window` nên job
  tự chuyển các dòng combo cũ trong DB sang ISO — script sửa dữ liệu một lần không còn cần phần ngày combo.
- Phần chuẩn hoá thành phố tuyến bay (Điện Biên) và alias Tuyên Quang của nhánh mock giữ nguyên.

## Kiểm tra

- `pytest src/data_collection/tests` (vsf2, `PYTHONPATH=src`): **630 passed, 27 skipped**.
- `db/vota_schema.sql` và `db/init/01_vota.sql` vẫn byte-identical.

## Còn lại / rủi ro

- Staging-HA Backend CD dừng khi commit có đổi `db/migrations` (CD cụm HA chưa chạy migration): migration 0010 phải áp tay vào DB mới
  trước / ngay khi merge PR.
- `askpass.cmd` (từ `release-mvp-v2`, commit b80acb62) nằm ở gốc repo — không thuộc thay đổi này; đã báo người dùng.
