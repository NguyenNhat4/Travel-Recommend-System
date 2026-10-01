# Đề xuất gộp giao diện trợ lý về widget, xóa trang `/assistant`

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (đề xuất đang chờ chốt)
- Phạm vi: docs (prd)

## Mục tiêu

Người dùng yêu cầu xóa trang `/assistant` (giao diện trợ lý cũ) để hệ thống chỉ có một giao diện trợ lý. Route này nằm trong PRD (`user-flow.md` §2, §3.2, §4.2) nên cần đề xuất được chốt trước khi sửa source (`AGENTS.md` §8). Phục vụ FR-AGT-01.

## File thay đổi

- `docs/prd/update/2026-09-29-gop-giao-dien-tro-ly-ve-widget.md` — thêm: đề xuất, trạng thái `chờ chốt`.

## Quyết định

- Chưa xóa code. Việc xóa kéo theo nhiều nơi (tab bar mobile, giỏ, tìm kiếm, xác nhận đơn, liên kết chia sẻ) nên để sau khi chốt.

## Kiểm tra

- Không có code. Đã liệt kê tham chiếu tới `/assistant` trong `src/frontend` và PRD.

## Còn lại / rủi ro

- Chờ chốt; cần quyết định đích thay cho liên kết chia sẻ `/assistant?share=`.
