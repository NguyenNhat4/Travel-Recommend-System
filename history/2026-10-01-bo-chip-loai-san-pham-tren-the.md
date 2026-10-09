# Bỏ chip loại sản phẩm trên thẻ sản phẩm và trang chi tiết

- Ngày: 2026-10-01
- Tác giả: người dùng / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Bỏ chip loại (Khách sạn, Vé máy bay, Combo, Golf, Vé tham quan) vì mỗi khu vực đã có danh mục/tab theo loại.

## File thay đổi

- `src/frontend/src/components/common/ProductCard.tsx` — sửa: bỏ `TaxonomyBadge` ở 4 variant và prop `hideTaxonomyBadge`
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: bỏ chip ở breadcrumb và dòng tiêu đề
- `src/frontend/src/features/catalog/landing/ProductShelf.tsx` — sửa: bỏ prop `hideTaxonomyBadge`
- `src/frontend/src/features/catalog/landing/VerticalLanding.tsx` — sửa: bỏ prop truyền xuống
- `docs/spec/product.md` — sửa: cập nhật mô tả `TaxonomyBadge` và thẻ `row`

## Quyết định

- Giữ chip ở giỏ hàng và checkout (CartView, ReviewStep, OrderSummary, ServicesStep): nơi này trộn nhiều loại, không có danh mục bao quanh. Component `TaxonomyBadge` vẫn còn.
- Không lệch PRD: `docs/prd/` không nhắc `TaxonomyBadge`.

## Kiểm tra

- `tsc --noEmit`: sạch. `vitest run`: 48 file, 482 test pass.

## Còn lại / rủi ro

- Chưa kiểm bằng mắt trên trình duyệt. Nếu muốn bỏ cả ở giỏ hàng/checkout thì xoá 4 chỗ dùng còn lại.
