# Đề xuất: điểm đến nằm sẵn trong system prompt, bỏ tool Destinations của orc

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Người dùng muốn đưa thẳng danh sách điểm đến vào system prompt và không cần tool cho việc này, vì catalog có ít điểm đến.
Danh sách đã được đưa vào prompt (`history/2026-10-13-orc-v2-ten-diem-den-catalog-trong-prompt.md`); bỏ tool
`list_destinations` khỏi orc là lệch PRD (architecture §3 ghi "Tám tool… Destinations", FR-AGT-02).

## File thay đổi

- `docs/prd/update/2026-10-13-diem-den-trong-system-prompt-bo-tool-destinations.md` — thêm: đề xuất, trạng thái chờ chốt.

## Quyết định

- Theo AGENTS.md §8: tạo đề xuất và dừng phần bỏ tool cho tới khi người dùng chốt. Danh sách vẫn đọc từ catalog lúc
  chạy, không viết cứng.

## Kiểm tra

- Không có (chỉ tài liệu).

## Còn lại / rủi ro

- Chờ chốt; sau khi chốt: cập nhật PRD rồi sửa source theo mục "Thay đổi source sau khi chốt" của đề xuất.
