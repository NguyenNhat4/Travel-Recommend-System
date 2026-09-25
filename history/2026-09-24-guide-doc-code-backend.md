# Hướng dẫn đọc code backend

- Ngày: 2026-09-24
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Viết hướng dẫn cách đọc code khi phát triển, tập trung backend, đặt ở `docs/guide/` theo yêu cầu người dùng.

## File thay đổi

- `docs/guide/doc-code-backend.md` — thêm: thứ tự đọc tài liệu và code, bản đồ lớp, lần theo request `/search`, đọc agent, dùng test/history để đọc code.
- `docs/prd/update/2026-09-24-them-thu-muc-docs-guide.md` — thêm: đề xuất đưa `docs/guide/` vào PRD §6.1 và `AGENTS.md` §7.
- `src/backend/README.md` — sửa: bỏ `GET /popular?k=` (không có route lẫn contract), thêm `GET /destinations` (route có thật trong `routes/catalog.py`); "LangGraph 9 node" → "10 node" theo `agents/graph.py`.

## Quyết định

- Đường dẫn file trong guide đối chiếu với code hiện tại trên `feat/agent`, không chép từ PRD.
- `docs/guide/` chưa có trong `docs/prd/architecture.md` §6.1 và `AGENTS.md` §7 → tạo đề xuất, chưa sửa PRD/AGENTS.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy test. Đã kiểm bằng `ls`/`grep` rằng mọi file, hàm và endpoint nhắc trong guide tồn tại.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất `2026-09-24-them-thu-muc-docs-guide.md`; chốt thì cập nhật PRD §6.1 + `AGENTS.md` §7 và chuyển đề xuất sang `update-archive/`. Từ chối thì chuyển guide sang `docs/spec/`.
