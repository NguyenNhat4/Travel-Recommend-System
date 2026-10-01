# Plan normalize ổn định: bỏ golden test ở bước đầu

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng hỏi có thật sự cần golden test ở CP0 không, rồi đồng ý bỏ dạng test tự động, bắt đầu từ CP1. Cập nhật plan
`docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` cho khớp. Phục vụ FR-CAT-01..04.
Thay thế một phần quyết định trong: `history/2026-09-28-plan-normalize-on-dinh.md` (CP0 golden test).

## File thay đổi

- `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` — sửa: CP0 thành phép so `sha256` của `products.jsonl` trước/sau (cùng ngày, cùng interim) ở CP2/CP4/CP5; golden test + tuỳ chọn `--today` chỉ viết khi CP4 kéo dài hoặc cần CI; các tiêu chí "golden pass" đổi theo.
- `history/2026-09-28-plan-normalize-bo-golden-test.md` — thêm: entry này.

## Quyết định

- CP1 và CP3 không đổi output nên không cần so; CP2/CP4/CP5 so `sha256` trước/sau.
- `normalise.py` dùng `date.today()` (~dòng 2705) và `datetime.now()` (~dòng 1413) nên chỉ so trong cùng ngày.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy test.

## Còn lại / rủi ro

- Bắt đầu CP1 (đo từng bước normalize).
- Chưa commit.
