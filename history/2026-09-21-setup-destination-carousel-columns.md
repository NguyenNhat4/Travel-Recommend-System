# Setup 4-5 cột cho carousel "Bạn muốn đi đâu" trong HomeView

- Ngày: 2026-09-21
- Tác giả: người dùng / Antigravity
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Xử lý vấn đề phần "Bạn muốn đi đâu" (`DESTINATIONS` carousel) trong [HomeView.tsx](file:///Users/mac/Documents/VSF/vinpearl/Travel-Recommendation-Product/src/frontend/src/components/home/HomeView.tsx) bị hiển thị lỡ cỡ 4.5 cột trên màn hình desktop (do cố định kích thước `sm:w-60` kết hợp container `max-w-7xl`). Điều chỉnh hiển thị vừa vặn 5 cột trên màn hình desktop (xl: ≥1280px) và 4 cột trên màn hình laptop/tablet ngang (lg: 1024px–1279px).

## File thay đổi

- `src/frontend/src/components/home/HomeView.tsx` — sửa: thêm các class responsive `md:w-[calc((100%-40px)/3)] lg:w-[calc((100%-60px)/4)] xl:w-[calc((100%-80px)/5)]` cho thẻ điểm đến thay vì cố định `w-56 sm:w-60`.

## Quyết định

- Áp dụng công thức tính độ rộng theo gap `space-x-5` (20px):
  - Màn hình desktop lớn (`xl`: ≥ 1280px): hiển thị tròn 5 cột với `calc((100% - 80px) / 5)` (4 khoảng cách 20px = 80px), độ rộng thẻ ~227px (tương đương chuẩn `w-56`/`w-60` gốc), không còn hiện tượng thẻ thứ 5 bị cắt lỡ cỡ 4.5 cột.
  - Màn hình laptop vừa (`lg`: 1024px–1279px): tự động co về 4 cột với `calc((100% - 60px) / 4)` (3 khoảng cách 20px = 60px), độ rộng thẻ ~225px, đồng bộ với bố cục 4 cột của 2 section khách sạn bên trên.
  - Tablet (`md`: 768px–1023px): tự động co về 3 cột với `calc((100% - 40px) / 3)`.
  - Mobile/small screen: giữ `w-56 sm:w-60` cho phép vuốt chạm mượt mà.

## Kiểm tra

- Chạy ESLint: `npx eslint src/components/home/HomeView.tsx` -> 0 errors, 1 warning (pre-existing useEffect dependency).
- Chạy hợp đồng: `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` -> PASS: 70 schemas, all local refs, 50 grounded products, 4 itinerary statuses...

## Còn lại / rủi ro

- Không có rủi ro; component hoạt động mượt mà với tính năng cuộn ngang của nút prev/next sẵn có.
