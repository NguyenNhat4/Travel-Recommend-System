# Bấm "Xác nhận" ở form gợi ý thì gửi luôn

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Áp dụng đề xuất đã chốt `docs/prd/update-archive/2026-10-05-xac-nhan-form-goi-y-gui-luon.md` (chốt bởi Nguyễn Minh Nhật, 2026-10-05). Thay thế hành vi "đặt câu vào ô nhập, không tự gửi" của đề xuất 2026-09-29. Thay thế: `2026-10-05-de-xuat-xac-nhan-form-goi-y-gui-luon.md` (entry đề xuất, dang dở).

## File thay đổi

- `docs/prd/user-flow.md`, `docs/prd/requirements.md` (AC-AGT-01), `docs/prd/architecture.md` §3 — sửa: xác nhận gửi ngay.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/agent/field-review.md` — sửa: đồng bộ hành vi mới.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: `handleConfirmTripDetails` gọi `handleSendMessage(prompt)`; đang xử lý thì bỏ qua như mọi lần gửi.
- `docs/prd/update-archive/2026-10-05-xac-nhan-form-goi-y-gui-luon.md` — chuyển từ `docs/prd/update/`, trạng thái đã áp dụng.

## Quyết định

- PRD sửa trước, rồi spec, rồi code (AGENTS.md mục 8). Không đổi contract/backend.

## Kiểm tra

- Xem kết quả `tsc --noEmit` ở báo cáo cuối; chưa thử bằng tay trên trình duyệt.

## Còn lại / rủi ro

- Form vẫn có `disabled={isRunning}` nên không gửi chồng lượt.
