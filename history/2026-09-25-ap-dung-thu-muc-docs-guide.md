# Áp dụng đề xuất thêm thư mục `docs/guide/`

- Ngày: 2026-09-25
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất `2026-09-24-them-thu-muc-docs-guide.md`; áp dụng vào PRD và `AGENTS.md`, lưu trữ đề xuất (AGENTS.md mục 8, bước 3–4).

## File thay đổi

- `docs/prd/architecture.md` — sửa: §6.1 dòng "Ngoài `src/`" thêm `guide/` vào danh sách thư mục `docs/`, kèm mô tả vai trò guide.
- `AGENTS.md` — sửa: §7 thêm hàng `Guide | docs/guide/`.
- `docs/prd/update/2026-09-24-them-thu-muc-docs-guide.md` → `docs/prd/update-archive/2026-09-24-them-thu-muc-docs-guide.md` — đổi tên (`git mv`): trạng thái `đã áp dụng`, chốt bởi mihhquan ngày 2026-09-25.

## Quyết định

- Sửa PRD trước, rồi `AGENTS.md`, đúng nội dung đề xuất; câu "guide không tạo quy tắc mới, lệch thì PRD/contract/AGENTS thắng" đưa vào cả PRD §6.1 lẫn hàng bảng ở AGENTS §7.
- `docs/guide/doc-code-backend.md` giữ nguyên vị trí — nay hợp lệ.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy test. Đã `grep` xác nhận dòng PRD §6.1 và hàng bảng AGENTS §7 được cập nhật.

## Còn lại / rủi ro

- Không có. Việc dang dở trong `2026-09-24-guide-doc-code-backend.md` (chờ chốt đề xuất) được khép lại bởi entry này.
