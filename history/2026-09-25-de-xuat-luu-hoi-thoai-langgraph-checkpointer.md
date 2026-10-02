# Đề xuất lưu hội thoại trợ lý bằng LangGraph checkpointer

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Hội thoại của trợ lý đang nằm trong RAM của process, nên mất khi backend khởi động lại và lỗi ngẫu nhiên nếu chạy nhiều worker (xem `2026-09-25-chu-hoi-thoai-theo-user.md`). Người dùng chọn lưu bằng checkpointer Postgres có sẵn của LangGraph.

## File thay đổi

- `docs/prd/update/2026-09-25-luu-hoi-thoai-bang-langgraph-checkpointer.md` — thêm: đề xuất trạng thái `chờ chốt`.

## Quyết định

- Việc này lệch PRD (`architecture.md` §3 chỉ nói lưu intent; `data-model.md` không có bảng checkpointer), nên theo AGENTS.md mục 8 phải viết đề xuất và dừng, chưa sửa source.
- Đề xuất chép DDL của checkpointer vào `db/` thay vì gọi `setup()`, để giữ quy tắc "bảng chỉ tạo từ DDL viết tay".

## Kiểm tra

- Chỉ viết tài liệu; không chạy test.

## Còn lại / rủi ro

- Đang chờ người dùng chốt đề xuất. Chốt xong mới cập nhật PRD rồi mới code, theo mục "Thay đổi source sau khi chốt" trong đề xuất.
