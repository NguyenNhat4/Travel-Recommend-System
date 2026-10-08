# Chỉnh Tailwind thanh phân cấp và đầu trang chi tiết

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Làm các thành phần đầu trang chi tiết khách sạn đồng nhất theo Tailwind và token `brand` (thanh phân cấp là ví dụ nêu). Chỉ đổi kiểu dáng, không đổi hành vi, không lệch PRD.

## File thay đổi

- `src/frontend/src/components/detail/ProductBreadcrumb.tsx` — sửa: chữ 14px, mục là vùng bấm ≥ 32px bo góc với hover `brand-50`, icon nhà ở "Trang chủ", mục hiện tại là chip `slate-100`, cuộn ngang một dòng trên điện thoại, focus ring `brand-500`.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: điểm đánh giá thành chip có sao (`brand-50`), tiêu đề các khối 16px → 18px.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§4.3) — sửa: ghi kiểu thanh phân cấp.
- `history/2026-10-08-chinh-tailwind-thanh-phan-cap-va-dau-trang.md` — thêm: entry này.

## Kiểm tra

- 680 unit test pass, `tsc` sạch, `eslint` không báo lỗi ở thư mục `detail`. Trình duyệt thật: thanh phân cấp và đầu trang đã xem trên màn hình rộng; chưa xem ở màn hình điện thoại.

## Còn lại / rủi ro

- Chưa chỉnh `AmenityList`, `ProductGallery`, `RoomCard` theo hướng này (đã dùng token `brand`).
