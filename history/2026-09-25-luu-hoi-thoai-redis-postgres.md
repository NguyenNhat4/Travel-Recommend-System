# Lưu hội thoại trợ lý bằng Redis và Postgres

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / AI Agent
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, frontend, docs, shared

## Mục tiêu
Triển khai lưu trữ hội thoại trợ lý bằng Redis (trí nhớ 24h) và Postgres (lịch sử lâu dài) theo đề xuất đã chốt.

## Quyết định và thay đổi
- Thực hiện lưu trữ 2 tầng: Redis (working memory 24h) và Postgres (long-term cho người dùng đăng nhập).
- Thêm `RedisConversationStore` và adapter `PostgresConversationArchive`.
- Cập nhật backend `nodes.py`, `graph.py`, `deps.py`, `conversation_store.py`.
- Thêm API lấy danh sách và chi tiết lịch sử hội thoại, có phân trang.
- Frontend: Cập nhật `assistantHistory.ts`, `AssistantProvider`, và UI `/assistant` để tải và tiếp tục hội thoại.
- Tài liệu: Di chuyển đề xuất sang `update-archive`, cập nhật PRD, architecture, user flow, OpenAPI.

## Kiểm tra
- Đã chạy test backend và frontend.
