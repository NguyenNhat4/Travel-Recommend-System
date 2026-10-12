# Đề xuất: sở thích là vài lựa chọn cố định và một ô tự nhập, bỏ AI

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: `history/2026-10-12-so-thich-chip-co-dinh.md`

## Mục tiêu

Người dùng muốn bỏ ô "Mong muốn cho chuyến đi" và nút Viết bằng AI; thay bằng vài lựa chọn cố định để bấm và một ô tự nhập thêm.

## File thay đổi

- `docs/prd/update/2026-10-12-so-thich-chip-co-dinh-va-o-tu-nhap.md` — thêm: đề xuất thay phần sở thích của AC-AGT-01, chờ chốt.

## Quyết định

- Lệch AC-AGT-01 hiện hành nên qua đề xuất (AGENTS.md §8); chưa sửa source.
- Đề xuất 5 lựa chọn gốc (Hồ bơi, Phù hợp trẻ nhỏ, View biển, Có bữa sáng, Spa) và ô tự nhập tối đa 150 ký tự; bỏ endpoint `/assistant/preferences`.

## Kiểm tra

- Không chạy test: chỉ thêm tài liệu đề xuất.

## Còn lại / rủi ro

- Chờ người dùng chốt danh sách lựa chọn và giới hạn ô tự nhập.
