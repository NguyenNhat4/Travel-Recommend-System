# Bỏ mọi liên kết "Xem thêm" ở các khối carousel

- Ngày: 2026-10-02
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Các khối carousel (trang chủ và trang danh mục) không cần liên kết "Xem thêm".

## File thay đổi

- `src/frontend/src/components/home/HomeView.tsx` — sửa: bỏ `popularMoreHref`, prop `moreHref` và import `buildSearchHref` không còn dùng.
- `src/frontend/src/features/catalog/landing/ProductShelf.tsx` — sửa: bỏ prop `moreHref`, liên kết và icon `ArrowRight`.
- `src/frontend/src/features/catalog/landing/VerticalLanding.tsx` — sửa: bỏ `allHref` và hai `moreHref`.
- `src/frontend/tests/unit/verticalLanding.test.tsx` — sửa: test nay khẳng định không có liên kết "Xem thêm".
- `history/2026-10-02-bo-xem-them-o-khoi-pho-bien-trang-chu.md` — thêm.

## Quyết định

- Bỏ hẳn `moreHref` khỏi `ProductShelf`. Nút "Xem thêm (n/total)" tải trang kế trong `GroupResults` là phân trang, giữ nguyên.

## Kiểm tra

- `tsc --noEmit` (src/frontend): sạch.
- `eslint` (catalog, home): sạch.
- `vitest run tests/unit/verticalLanding.test.tsx tests/unit/homeView.test.tsx`: 12 test pass.

## Còn lại / rủi ro

- Chưa kiểm tay trên trình duyệt.
