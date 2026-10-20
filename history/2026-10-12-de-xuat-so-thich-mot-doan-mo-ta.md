# Đề xuất: sở thích trong form là một đoạn mô tả ngắn

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: `history/2026-10-12-so-thich-mot-doan-mo-ta.md`

## Mục tiêu

Người dùng thấy form hiện quá nhiều thứ (3 nhóm sở thích, chip kèm số sản phẩm, ô chữ từng nhóm). Mục tiêu mới: bấm nút thì AI viết một đoạn ngắn mô tả mong muốn để Search tốt hơn; người dùng sửa hoặc tự viết.

## File thay đổi

- `docs/prd/update/2026-10-12-so-thich-mot-doan-mo-ta.md` — thêm: đề xuất thay phần sở thích của AC-AGT-01, trạng thái chờ chốt.

## Quyết định

- Lệch AC-AGT-01 vừa chốt sáng 12/10 nên phải qua đề xuất (AGENTS.md §8); chưa sửa source.
- Đoạn văn đi trong câu xác nhận, để LLM ở bước hiểu yêu cầu đọc như mọi tin nhắn, thay cho regex tách theo tiền tố nhóm.

## Kiểm tra

- Không chạy test: chỉ thêm tài liệu đề xuất.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất; chốt xong thì cập nhật PRD trước rồi mới sửa contract, backend, frontend như mục "Thay đổi source" của đề xuất.
