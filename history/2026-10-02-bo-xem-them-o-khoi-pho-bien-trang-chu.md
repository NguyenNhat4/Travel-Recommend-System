# Bỏ liên kết "Xem thêm" ở khối Phổ biến trang chủ

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Khối "Phổ biến tại các điểm đến Việt Nam" ở trang chủ không cần liên kết "Xem thêm".

## File thay đổi

- `src/frontend/src/components/home/HomeView.tsx` — sửa: bỏ `popularMoreHref`, prop `moreHref` và import `buildSearchHref` không còn dùng.
- `history/2026-10-02-bo-xem-them-o-khoi-pho-bien-trang-chu.md` — thêm.

## Quyết định

- Chỉ bỏ ở trang chủ; `ProductShelf` vẫn hỗ trợ `moreHref` cho các trang danh mục (`VerticalLanding`).

## Kiểm tra

- `tsc --noEmit` (src/frontend): sạch.
- `vitest run tests/unit/homeView.test.tsx`: 5 test pass.

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt.
