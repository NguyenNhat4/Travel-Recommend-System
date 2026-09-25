# Thêm `make update`, gỡ target Makefile không ai dùng

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: Makefile, tài liệu hướng dẫn chạy

## Mục tiêu

`make web` chỉ chạy `npm install` khi chưa có `node_modules`, nên dependency mới (`redis`) không được cài sau `git pull` và frontend lỗi `Can't resolve 'redis'`. Thêm `make update` để cài dependency mới, và rút gọn Makefile theo yêu cầu. Không lệch PRD (công cụ dev, không đổi hành vi sản phẩm).

## File thay đổi

- `Makefile` — sửa: thêm `update` (pip install trong `.venv` hoặc `src/backend/.venv`, rồi `npm install` trong `src/frontend`); gỡ 8 target không có tài liệu nào nhắc: `chat-full`, `web-ui`, `web-logs`, `chat-api`, `chat-ui`, `chat-logs`, `test-llm`, `backend-build`. Từ 22 còn 15 target.
- `README.md` — sửa: nhắc `make update` sau `git pull`.
- `src/frontend/README.md` — sửa: nhắc `make update` ở bước cài dependency.
- `src/backend/README.md` — sửa: nhắc `make update` cạnh `pip install`.

## Quyết định

- Chỉ gỡ target không xuất hiện trong bất kỳ tài liệu hay target khác (grep toàn repo, trừ `history/`). Giữ `chat`, `web`, `demo-db*`, `db-migrate*`, `index-vectors`, `backend*`, `jwt-keys` vì tài liệu đang dùng.
- `make update` chỉ cài đúng theo phiên bản đã ghim, không nâng lên bản mới nhất.

## Kiểm tra

- `make -n web` và `make -n chat` parse được; `make update` chạy xong, cả pip và npm báo đã đủ.
- Chưa chạy các target còn lại sau khi gỡ, chỉ kiểm cú pháp.

## Còn lại / rủi ro

- Ai còn dùng `make chat-api`, `chat-ui`, `web-ui`, `*-logs`, `test-llm` hay `backend-build` sẽ gặp `No rule to make target`; khôi phục từ git nếu cần. `make test-llm` gọi `test_llm.py` ở gốc repo, file này vẫn còn.
