# Thêm thư mục `docs/guide/` cho hướng dẫn phát triển

- Ngày: 2026-09-24
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §6.1
- Mã FR/NFR: không gắn FR — tài liệu nội bộ cho người phát triển

## Lý do

Người mới vào repo cần một hướng dẫn "đọc code theo thứ tự nào". Nội dung này không phải PRD, không phải spec
(không đặc tả một phần hệ thống) và không phải plan (không có bước triển khai), nên không vừa thư mục nào hiện có.
Bản đầu tiên đã có ở `docs/guide/doc-code-backend.md` theo yêu cầu trực tiếp của người dùng.

## Nội dung đề xuất

`docs/prd/architecture.md` §6.1, dòng "Ngoài `src/`":

- Hiện tại: `docs/` (`prd/`, `spec/`, `plan/` — xem `AGENTS.md` §7)
- Thay bằng: `docs/` (`prd/`, `spec/`, `plan/`, `guide/` — xem `AGENTS.md` §7)

`guide/` chứa hướng dẫn cho người phát triển (cách đọc code, cách chạy, quy trình). Guide không tạo quy tắc mới;
khi lệch PRD, contract hoặc `AGENTS.md` thì các nguồn đó thắng.

## Thay đổi source sau khi chốt

- `docs/prd/architecture.md` §6.1 — sửa dòng trên.
- `AGENTS.md` §7 — thêm hàng `Guide | docs/guide/ | Hướng dẫn cho người phát triển; không chứa quy tắc hay spec`.
