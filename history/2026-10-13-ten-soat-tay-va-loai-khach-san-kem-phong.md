# Tên soát tay (name_overrides.csv), loại khách sạn kèm hạng phòng, loại 6 sản phẩm lỗi trên production

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở — job + test xong; production chưa sửa (cần script xem trước + người dùng đồng ý); mục 2, 4 chưa làm
- Phạm vi: data
- Liên quan: `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md`

## Mục tiêu

Người dùng (13/10): rà dữ liệu production ảnh hưởng tới trợ lý gợi ý/lên lịch, sửa job cào để không làm hỏng dữ liệu đã bổ sung;
chốt "sửa 1, 2, 4 trước", "nhớ test đầy đủ". Mục 1 = sửa lỗi rõ ràng và đưa ref vào job để lượt cào không hoàn tác.
FR-CAT-02, NFR-REL-01. Không lệch PRD (chỉ thêm dữ liệu soát tay theo cơ chế đã có).

## Thay đổi

- `src/data_collection/normalise.py`: `excluded_reason` — ref trong `excluded_products.csv` hoặc hạng phòng có khách sạn cha
  trong đó; `NAME_OVERRIDES_CSV`, `load_name_overrides` (thiếu bằng chứng → bỏ qua, cảnh báo), `apply_name_overrides` (đặt `name`,
  giữ `attributes.originalName`, ghi `nameSource`/`nameEvidence`, sửa đầu mô tả dựng từ tên cũ); pipeline áp tên trên toàn bộ sản
  phẩm (cả tour Booking) rồi mới loại; báo cáo `namesOverridden`.
- `src/data_collection/collectors/name_overrides.csv` (mới): Nguyễn Huệ → "Phố đi bộ Nguyễn Huệ"; "Halong Bay Cruises" →
  "Động Trung Trang" (nameEn "Trung Trang Cave", toạ độ Cát Bà).
- `src/data_collection/collectors/excluded_products.csv`: +6 dòng (PANAMA phòng 111.111.111; tuyến Cà Mau–Hà Nội 0 chuyến;
  Vinpearl VW00469 trùng VW00613; Cubicity bản Trip trùng `booking:hotel:16986224`; 2 khách sạn đảo Hòn Sơn ngoài mọi điểm đến).
- `src/data_collection/tests/test_quality.py`: 3 test (loại khách sạn kèm phòng; đổi tên + mô tả; danh sách 13/10 có trong CSV).
- `src/data_collection/tests/test_normalise_steps.py`: `ReviewedOverridesTests` chạy trọn normalise trên mẫu, kiểm 6 dòng bị loại ở
  bước `excluded` với lý do khách sạn cha, và tên mới áp cho tour Booking.
- `src/data_collection/README.md`, `docs/spec/data-collection/schema.md`: mô tả hai quy tắc trên.
- `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` (mới): bàn giao việc còn lại cho agent khác.

## Quyết định

- Loại khách sạn phải loại cả hạng phòng ngay ở bước soát tay: production bật lại khách sạn còn phòng đặt được (FR-CAT-02).
  `drop_orphans` có sẵn cũng xoá phòng mồ côi, nhưng ghi lý do "lỗi dữ liệu"; quy tắc mới ghi đúng lý do soát tay.
- Job không ghi đè `name`/`description` của dòng đã có trên DB → đổi tên trên production phải sửa trực tiếp (chưa làm).

## Kiểm tra

- `python -m pytest -q -p no:cacheprovider data_collection/tests` (từ `src/`, env vsf2, `DBX_TEST_DATABASE_URL` = DB test local):
  **687 passed, 18 skipped** (skip do thiếu `CATALOG_TEST_DATABASE_URL`, `STREAM_TEST_ADMIN_URL`, `CATALOG_ONLY_TEST_DATABASE_URL`).
- Phá thử: bỏ quy tắc khách sạn cha → `ReviewedOverridesTests` lỗi 1; bỏ `apply_name_overrides` → lỗi 1; bản đúng → 0.
  (Lần phá thử đầu không bắt được vì `drop_orphans` vẫn xoá phòng; đã thêm kiểm bước + lý do trong `dropped.jsonl.gz`.)

## Việc còn lại

Xem `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` §2–§5.
