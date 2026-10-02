# Vé Thương gia mô phỏng: mặc định bật

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu hỏi "Tôi tưởng giờ tôi push lên là sẽ tự động deploy lại ?"; CD không sửa env VM và người yêu cầu không vào VM
được. Chọn cách 2 (đổi mặc định sang bật) và chốt: "OK vậy chốt số 2". Thay quyết định "mặc định tắt" trong
`2026-09-30-ap-dung-ve-thuong-gia-mo-phong.md`. FR-CAT-03; liên quan NFR-REL-01.

Cũng kiểm `release-mvp-v2` theo yêu cầu "xem thử nhánh release mvpv2 đã cập nhật gì, merge về đây": remote vẫn ở `04b3e41`
(PR #51), đã nằm trong nhánh này (behind 0, ahead 2) — không có gì để merge.

## File thay đổi

- `docs/prd/update-archive/2026-09-30-ve-thuong-gia-mo-phong-mac-dinh-bat.md` — thêm: đề xuất, trạng thái `đã áp dụng`.
- `docs/prd/requirements.md` — sửa: FR-CAT-03 "mặc định bật, tắt bằng cấu hình".
- `docs/prd/data-model.md` — sửa: §3 dòng bật / tắt vé mô phỏng.
- `src/data_collection/seed/simulated_business.py` — sửa: `enabled()` mặc định `true`; chỉ `0/false/no/off` là tắt; docstring,
  help `--enable`.
- `src/data_collection/seed/database.py` — sửa: comment.
- `src/data_collection/tests/test_simulated_business.py` — sửa: test cờ (trống / không đặt = bật).
- `src/data_collection/.env.example`, `docs/spec/MOCK_DATA_SPEC.md`, `docs/guide/hien-thi-hang-ve-may-bay.md`,
  `docs/guide/ve-thuong-gia-va-index-cho.md`, `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: mặc định bật, deploy là đủ,
  tắt bằng `SIMULATED_BUSINESS_FARES=0`.
- `history/2026-09-30-ve-thuong-gia-mo-phong-mac-dinh-bat.md` — thêm: entry này.

## Quyết định

- Đề xuất ghi thẳng vào `update-archive` với trạng thái `đã áp dụng` vì người yêu cầu chốt ngay trong chat sau khi được giải
  thích nội dung và đánh đổi (trước khi có file).
- Seed demo đầy đủ vẫn luôn bật (không đọc biến), như trước.

## Kiểm tra

- `PYTHONPATH=src:src/data_collection python -m pytest -q src/data_collection/tests` (env vsf2): 456 passed, 9 skipped (3 test
  PostgreSQL bỏ qua vì database nháp đã xoá; chúng truyền bật / tắt tường minh nên không phụ thuộc mặc định).
- `git rev-list --count HEAD..origin/release-mvp-v2` = 0 sau `git fetch`.
- `git diff --check`: sạch.

## Còn lại / rủi ro

- Sau khi merge vào nhánh CD và deploy, DB staging có vé Thương gia mô phỏng từ lượt nạp đầu tiên của job. Tắt cần quyền VM.
- Chưa commit.
