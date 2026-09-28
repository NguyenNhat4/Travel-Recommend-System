# Đề xuất lưu hội thoại trợ lý bằng Redis 24 giờ và Postgres lâu dài

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Thay thế: 2026-09-25-de-xuat-luu-hoi-thoai-langgraph-checkpointer.md

## Mục tiêu

Hội thoại của trợ lý đang nằm trong RAM của process, nên mất khi backend khởi động lại và không có lịch sử lâu dài. Sau khi cân nhắc checkpointer của LangGraph, người dùng chọn kết hợp hai tầng:

- Redis giữ trí nhớ 24 giờ.
- Postgres (`app.conversations`, `app.conversation_messages`) giữ lịch sử của user đã đăng nhập, không giới hạn thời gian.
- Chưa làm màn hình xem lại chat.

Kế hoạch đã duyệt: `~/.claude/plans/oke-ket-hop-di-binary-brooks.md`.

## File thay đổi

- `docs/prd/update/2026-09-25-luu-hoi-thoai-redis-va-postgres.md` — thêm: đề xuất trạng thái `chờ chốt`.
- `docs/prd/update-archive/2026-09-25-luu-hoi-thoai-bang-langgraph-checkpointer.md` — đổi chỗ từ `docs/prd/update/`, trạng thái `từ chối`. File chưa từng được commit nên dùng `mv` thay cho `git mv`.

## Quyết định

- Việc này lệch PRD: Redis mở rộng vai trò, và hội thoại lưu hai tầng thay vì "lưu intent, TTL 24h". Theo AGENTS.md mục 8, tôi viết đề xuất và dừng, chưa sửa source.
- Dùng bảng có sẵn trong DDL, không đổi schema, không đổi contract. Id hội thoại đổi sang UUID cho khớp PK.

## Kiểm tra

- Chỉ viết tài liệu; không chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất. Chốt xong thì làm theo thứ tự: cập nhật PRD, chuyển đề xuất vào `update-archive/`, rồi code theo bước 1–3 của kế hoạch.
