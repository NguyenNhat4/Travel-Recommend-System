# Vé máy bay ở trang search dẫn về /flights thay vì trang chi tiết

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Bấm một vé máy bay (ví dụ Hà Nội → Phú Quốc) trong kết quả tìm kiếm đang mở `/product/{id}`. Trang đó không hợp với cách chọn chuyến hiện tại (chọn hạng và đặt ngay trên `/flights`). Đổi thành mở `/flights` với điểm đi, điểm đến, ngày điền sẵn.

## File thay đổi

- `src/frontend/src/features/flights/results/flightHref.ts` — sửa: thêm `flightProductHref` (origin/destination từ `attributes.originCity`/`destinationCity`, ngày bay làm `checkIn` khi URL chưa có ngày).
- `src/frontend/src/components/common/ProductCard.tsx` — sửa: sản phẩm `flight` dùng `flightProductHref`, thiếu dữ liệu thì rơi về `/product/{id}`.
- `src/frontend/tests/unit/flightProductHref.test.ts` — thêm: 3 test.
- `history/2026-10-02-ve-may-bay-o-trang-search-ve-flights.md` — thêm.

## Quyết định

- Sửa ở `ProductCard` để mọi nơi dùng thẻ (search, danh mục, Home) nhất quán; không xoá route `/product/{id}` vì trợ lý, giỏ, xác nhận còn dùng.
- Giữ ngày/số khách đang tìm; chỉ khi chưa có ngày mới lấy ngày bay của vé (và chỉ khi chưa qua).
- Không đổi contract, DDL, backend; không lệch PRD (FR-SRC-03, FR-BKG-10).

## Kiểm tra

- `node_modules/.bin/tsc --noEmit` (src/frontend): sạch.
- `node_modules/.bin/vitest run tests/unit`: lần đầu 1 test fail (không phải test của thay đổi này, lúc máy đang tải nặng), chạy lại không còn fail.

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt. Vé không có `originCity` vẫn mở trang chi tiết.
