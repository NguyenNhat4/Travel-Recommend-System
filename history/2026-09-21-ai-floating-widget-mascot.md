# Dùng mascot WebP cho nút mở trợ lý nổi

- Ngày: 2026-09-21
- Tác giả: người dùng / Codex
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Thay biểu tượng trên nút mở `AiFloatingWidget` bằng ảnh `mascot_welcome.webp` theo yêu cầu.

## File thay đổi

- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa: thay icon Sparkles của nút mở trợ lý bằng mascot WebP; giữ nguyên kích thước và vị trí nút.
- `history/2026-09-21-ai-floating-widget-mascot.md` — thêm: ghi nhận thay đổi này.

## Quyết định

- Dùng `next/image` với kích thước 48×47 px để giữ tỷ lệ ảnh 192×187; ảnh trang trí có `alt=""` vì nút đã có `aria-label`.
- Chỉ thay icon nút mở; giữ nguyên các thay đổi có sẵn khác trong `AiFloatingWidget.tsx` và giữ icon Bot ở tiêu đề panel.
- Không đổi API, contract hay hành vi trợ lý.

## Kiểm tra

- Xác nhận asset tồn tại, định dạng WebP và kích thước 192×187; đã xem ảnh trực quan.
- Không chạy test hoặc build cho thay đổi icon này.

## Còn lại / rủi ro

- Không có.
