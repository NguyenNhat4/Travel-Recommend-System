# Plan: chuyển orc v2 sang function calling, tool lập lịch mới

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu file thiết kế chuyển orc sang function calling, tập trung lập lịch (lịch đang ra danh sách thay vì
theo buổi), chưa sửa code. Phục vụ FR-AGT-02, FR-AGT-03, NFR-REL-01.

## File thay đổi

- `docs/plan/2026-10-13-orc-function-calling-va-tool-lap-lich.md` — thêm: cơ chế gọi tool mới, định nghĩa
  `find_products`, `plan_itinerary` (orc chọn buổi, code tính giờ/đêm/phòng/chi phí/savings), `update_trip`, `respond`,
  luồng lập lịch 2 lượt, bước code, cách đo.

## Quyết định

- Đổi transport (bước 1–4) không lệch PRD (đề xuất đã chốt 13/10 mục 9.1 cho phép); đổi bộ tool và luật lập lịch
  (bước 5–7) chờ chốt phần B, C, E, F, G của `docs/prd/update/2026-10-13-thiet-ke-lai-bo-tool-orc.md`.
- Combo không vào lịch, gợi ý riêng (đúng `docs/prd/user-flow.md`); vé bay qua sân bay gần để sau.

## Kiểm tra

- Không có (chỉ tài liệu).

## Còn lại / rủi ro

- Chờ người dùng duyệt plan và chốt đề xuất; sau đó làm bước 1–4, đo, rồi bước 5–7.
