# Đề xuất gỡ viên "Trợ lý AI" khỏi thanh điều hướng header

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (đề xuất đang chờ chốt; xem Còn lại)
- Phạm vi: docs (prd)

## Mục tiêu

Người dùng yêu cầu bỏ "Trợ lý AI" khỏi header. Wireframe PRD `docs/prd/user-flow.md` §4.1 đang vẽ `[Trợ lý AI]` ở thanh điều hướng, nên việc gỡ là lệch PRD và cần đề xuất được chốt trước khi sửa source (`AGENTS.md` §8). Phục vụ FR-AGT-01.

## File thay đổi

- `docs/prd/update/2026-09-29-bo-nut-tro-ly-ai-tren-header.md` — thêm: đề xuất, trạng thái `chờ chốt`.

## Quyết định

- Chỉ đề xuất, chưa sửa PRD hay source cho phần này. Các phần không lệch PRD của cùng yêu cầu (bỏ cột "Điểm đến phổ biến" khỏi menu, đồng bộ kích thước header, font Cal Sans) làm ở entry riêng.
- Lời yêu cầu trong tin nhắn không được coi là chốt: `AGENTS.md` §8 yêu cầu người dùng chốt trên đề xuất đã viết.

## Kiểm tra

- Không có code. Đã đối chiếu `docs/prd/*.md`: wireframe `user-flow.md` §4.1 là chỗ duy nhất trong PRD nhắc lối vào trợ lý trên header.

## Còn lại / rủi ro

- Chờ người dùng chốt, sửa hoặc từ chối đề xuất. Khi chốt: sửa `user-flow.md` §4.1, rồi source, rồi chuyển đề xuất sang `docs/prd/update-archive/` (`AGENTS.md` §8 bước 3–4).
