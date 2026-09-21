# Tổng hợp thay đổi HomeView và ảnh WebP ngày 21-09-2026

- Ngày: 2026-09-21
- Tác giả: người dùng / Codex / agent
- Nhánh: data_contract, release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Gộp hai entry frontend trong ngày: tạm ẩn các nút Xem thêm chưa có luồng đích và tạo ảnh WebP đã resize để giảm payload ảnh đang render.

## File thay đổi

- `src/frontend/src/components/home/HomeView.tsx` — comment bốn nút Xem thêm; thay ba đường dẫn Trust Badge sang WebP.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — thay hai tham chiếu mascot sang WebP.
- `src/frontend/public/mascot_welcome.webp` (192×187), `src/frontend/public/mascot_hello.webp` (80×80), `src/frontend/public/trust_badge_booking.webp` (80×80), `src/frontend/public/trust_badge_ai_assistant.webp` (80×80), `src/frontend/public/trust_badge_ecosystem.webp` (80×73) — thêm ảnh WebP có alpha; giữ PNG nguồn.

## Quyết định

- Dùng cwebp 1.6.0, quality 85, alpha quality 100; resize theo khoảng 2× kích thước CSS và giữ tỷ lệ. mascot_hello được tạo ở 80×80 theo kích thước Trust Badge.
- Giữ các nút Xem thêm dưới dạng JSX comment và giữ import ArrowRight để có thể bật lại khi route/popup danh mục hoàn thiện.

## Kiểm tra

- Các kiểm tra ghi nhận metadata/alpha và kiểm tra trực quan cho đủ năm WebP; typecheck, web build và kiểm tra không còn component nào tham chiếu PNG cho ảnh đang render đều pass.
- Entry nút Xem thêm ghi nhận typecheck, lint và routeGeometry tests 17/17 pass; lint có warning tồn tại từ trước.
- git diff --check từng báo trailing whitespace trong AiFloatingWidget.tsx từ thay đổi dirty ngoài phạm vi.
- Không chạy lại build/test trong lần gộp tài liệu này.

## Còn lại / rủi ro

- PNG gốc vẫn được giữ trong public; component dùng WebP.
- Có thể bỏ comment các nút Xem thêm khi các route hoặc popup tương ứng sẵn sàng.
