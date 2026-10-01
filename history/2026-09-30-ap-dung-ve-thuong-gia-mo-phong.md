# Áp dụng đề xuất vé Thương gia mô phỏng (cả DB VM)

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu chốt đề xuất `docs/prd/update-archive/2026-09-30-ve-thuong-gia-mo-phong-cho-demo.md` ("đã chốt"), bản sửa cho
cả DB VM; dặn "nhớ test đầy đủ". Phục vụ FR-CAT-03 (ngoại lệ vé mô phỏng), FR-CAT-01; liên quan NFR-REL-01. Nối tiếp
`2026-09-30-khu-hoi-3-5-7-va-thuong-gia-nhieu-ngay.md` (nơi đề xuất được sửa, trạng thái lúc đó `chờ chốt`).

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-CAT-03 thêm ngoại lệ vé Thương gia mô phỏng. Đề xuất ghi FR-CAT-01, nhưng câu "không
  suy hạng hoặc tự tạo giá" nằm ở FR-CAT-03; áp đúng chỗ câu đó và ghi chú trong đề xuất.
- `docs/prd/data-model.md` — sửa: §3 thêm mục "Vé Thương gia mô phỏng (demo)" đúng nội dung đã chốt.
- `docs/prd/update/2026-09-30-ve-thuong-gia-mo-phong-cho-demo.md` → `docs/prd/update-archive/` (`git mv`) — sửa: trạng thái
  `đã áp dụng`, chốt bởi Đăng Khôi 2026-09-30.
- `src/data_collection/seed/simulated_business.py` — thêm: `plan` (thuần) và `sync` (ghi `demo:business:*` trong transaction
  của nơi gọi, chỉ dòng đổi), CLI chạy một lần (`--enable`/`--disable`, khoá ghi catalog `7791024`).
- `src/data_collection/seed/database.py` — sửa: seed đầy đủ gọi `sync(conn, True)`; `upsert_catalog` (`--catalog-only`,
  `daily.py`) gọi `sync(conn)` theo `SIMULATED_BUSINESS_FARES`, sau bước `retire_missing`.
- `src/data_collection/fresh_catalog_db.py` — sửa: `load_into_db` và `maintain_catalog` gọi `sync(conn)` sau upsert/cửa sổ,
  cùng transaction.
- `src/data_collection/.env.example` — sửa: thêm `SIMULATED_BUSINESS_FARES`.
- `src/data_collection/tests/test_simulated_business.py` — thêm: 7 test thuần + 3 test PostgreSQL (chạy khi có
  `SIMULATED_TEST_DATABASE_URL` trỏ database `vota_simbiz_test_*`).
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: `maintain_catalog` patch `sync` và kiểm được gọi trên đúng
  kết nối (kết nối giả không có `row_factory`).
- `docs/spec/MOCK_DATA_SPEC.md` (§2 bước 1 mục 5), `docs/spec/data-collection/schema.md` (khoá `simulated`),
  `src/data_collection/snapshots/README.md`, `docs/guide/hien-thi-hang-ve-may-bay.md` (FE hiện nhãn "giá minh hoạ"),
  `docs/guide/ve-thuong-gia-va-index-cho.md` (bật trên VM, lệnh chạy một lần) — sửa.
- `src/data_collection/README.md` — sửa: khối seed-report do seed ghi lại (11.718 → 12.515 sản phẩm = + 797 vé mô phỏng).
- `history/2026-09-30-ap-dung-ve-thuong-gia-mo-phong.md` — thêm: entry này.

## Quyết định

- Một module dùng chung, chạy trên các dòng đã nạp trong DB (sau cửa sổ 30 ngày), nên seed demo, `daily.py` và job fresh cho
  cùng kết quả. Không thêm cột/bảng; `simulated` nằm trong `attributes`.
- Vé Thương gia thật "thắng" khi cùng (loại vé, sân bay đi/đến, số hiệu, ngày đi theo `available_from`, chuyến về, ngày về) và
  đang `available`.
- `productId` = uuid5 cùng namespace với `normalise.product_id` (có test đối chiếu).
- Chưa bật trên VM: cần người có quyền VM đặt `SIMULATED_BUSINESS_FARES=1` trong `/etc/vota/fresh-catalog.env`. Không chạy
  CLI lên DB VM trong task này (chờ người yêu cầu).

## Kiểm tra

- Database nháp `vota_simbiz_test_20260930` + `insider_simbiz_test_20260930` (template0, DDL `db/init/*.sql`, migration runner
  4/4), seed đầy đủ snapshot `2026-09-30`, `--as-of 2026-09-30 --seed 42`: 11.718 sản phẩm + **797 vé mô phỏng** (290 khứ hồi,
  507 một chiều / vé cũ), tất cả `available` và `is_bookable`.
- `db/verify.sql`: 18/18 PASS; `db/verify_insider.sql`: 6 PASS, 0 FAIL.
- CLI `--enable` hai lần: lần 1 ghi 797, lần 2 ghi 0 (idempotent).
- Backend `fare_classes_by_product` trên dữ liệu DB nháp: cùng hành trình trả `ECO` 1.113.000 + `BUS` "Thương gia" 2.949.000.
- `SIMULATED_TEST_DATABASE_URL=… pytest src/data_collection/tests`: 459 passed, 6 skipped (gồm 3 test DB: sync idempotent /
  theo giá / tắt thì khoá; `maintain_catalog` theo biến; `load_into_db` ghi vé mô phỏng và vé thật thắng).
- `src/backend` `pytest tests`: 699 passed, 19 skipped.
- Kiểm test bắt lỗi (phá rồi khôi phục, `cmp` sạch): bỏ luật vé thật thắng / đổi tỉ lệ / bỏ bước khoá → mỗi lần 1 test fail.
  Bỏ điều kiện "không sinh từ vé mô phỏng" không làm test fail vì vé mô phỏng đã bị loại ở điều kiện hạng `BUSINESS`.
- Database nháp đã xoá.

## Còn lại / rủi ro

- Bật trên VM (env) hoặc chạy CLI một lần qua tunnel; chưa làm.
- FE cần hiện nhãn "giá minh hoạ" (hậu tố tên / `attributes.simulated`); contract không đổi.
- Vé mô phỏng đặt được trên VM (Stripe test); AI Assistant có thể đề xuất chúng.
- Chưa commit.
