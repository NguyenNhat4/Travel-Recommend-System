# Đề xuất: thiết kế lại bộ tool của orc (8 → 5)

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Người dùng yêu cầu bỏ hoặc sửa các tool không cần thiết sau khi review thiết kế tool của orc v2. Bộ tool nằm trong
PRD (architecture §3 "Tám tool", FR-AGT-02) nên phải qua đề xuất.

## File thay đổi

- `docs/prd/update/2026-10-13-thiet-ke-lai-bo-tool-orc.md` — thêm: đề xuất 5 phần A–E (bỏ Destinations, gộp
  Search + Catalog list, Detail nhiều sản phẩm kèm hạng phòng, gộp Similar vào Recommendation, build_itinerary tự tính
  giờ), chờ chốt.

## Quyết định

- Chia phần để chốt riêng; phần A trùng đề xuất `2026-10-13-diem-den-trong-system-prompt-bo-tool-destinations.md`.
- Gộp ở tầng orc, không đổi API Search/Catalog/Recommendation.

## Kiểm tra

- Không có (chỉ tài liệu).

## Còn lại / rủi ro

- Chờ người dùng chốt từng phần; sau khi chốt cập nhật PRD trước rồi sửa source theo đề xuất.
