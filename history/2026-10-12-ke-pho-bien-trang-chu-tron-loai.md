# Kệ "Phổ biến" ở trang chủ: tab "Tất cả" trộn loại có nhãn, tab "Vé tham quan" gồm golf

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành
- Phạm vi: frontend
- Liên quan: `2026-10-12-contract-1-25-0-products-diversify.md`, `2026-10-12-products-tron-theo-nhom-loai.md`; điều chỉnh một phần `2026-10-01-bo-chip-loai-san-pham-tren-the.md` (không sửa entry đó)

## Mục tiêu

Tab "Tất cả" của kệ "Phổ biến tại các điểm đến Việt Nam" chỉ hiện vé máy bay. Trên prod, hạng 1–10 đều là tuyến bay. Người dùng muốn tab này có thêm khách sạn, vé tham quan, combo và golf. Golf không có tab riêng mà gộp vào tab "Vé tham quan". Phục vụ FR-REC-01 và chỉ số Diversity ở `docs/prd/test-plan.md` §2.5.

## File thay đổi

- `src/frontend/src/services/catalog.ts` — sửa:
  - `ListProductsParams.taxonomy` nhận một loại hoặc mảng; thêm `diversify`;
  - `query()` nối mảng bằng dấu phẩy (style form, explode false).
- `src/frontend/src/components/home/HomeView.tsx` — sửa: `POPULAR_TABS` mang `params` và `showTaxonomy`.
  - "Tất cả" gửi `diversify: 'taxonomy'` và bật nhãn loại.
  - "Vé tham quan" gửi `taxonomy: ['attraction', 'golf']`.
  - Vẫn 1 request mỗi tab.
- `src/frontend/src/features/catalog/landing/ProductShelf.tsx` — sửa: prop tuỳ chọn `showTaxonomy` (mặc định `false`) chuyển xuống thẻ tile.
- `src/frontend/src/components/common/ProductCard.tsx` — sửa: thẻ tile nhận `showTaxonomy`, hiện `TaxonomyBadge` (cỡ `sm`) ở góc trên trái ảnh.
- `src/frontend/tests/unit/homeView.test.tsx` — sửa:
  - tham số request của tab "Tất cả";
  - tab "Vé tham quan" gửi `['attraction', 'golf']`;
  - tab "Vé máy bay" không có `diversify`;
  - nhãn loại chỉ có ở tab "Tất cả" (fixture `diversified`).
- `src/frontend/tests/unit/catalogService.test.ts` — sửa: URL chính xác cho mảng taxonomy (`taxonomy=attraction%2Cgolf`) và cho `diversify`.
- `src/frontend/tests/unit/productCard.test.tsx` — thêm:
  - tile mặc định không có nhãn;
  - bật nhãn thì nhãn nằm trong tên truy cập của liên kết;
  - combo tên "Vé máy bay khứ hồi … +" có nhãn "Combo".
- `history/2026-10-12-ke-pho-bien-trang-chu-tron-loai.md` — thêm: entry này.

## Quyết định

- **Trộn ở Backend** bằng `diversify=taxonomy` (người dùng chọn phương án 1), không gọi 5 request ở Web. Lý do: giữ ngân sách 1 request của trang chủ và e2e `navigation.spec.ts` "Home loads one catalog request".
- **Nhãn loại chỉ ở tab "Tất cả"** (người dùng chốt 2026-10-12). Đây là ngoại lệ của quyết định bỏ nhãn ngày 2026-10-01, vì kệ này trộn nhiều loại mà không có tab bao quanh, giống giỏ và checkout. `GroupShelf` (`/search`), các trang danh mục và các tab khác của kệ vẫn không có nhãn.
- **Dùng lại `TaxonomyBadge` có sẵn,** nhãn golf là "Golf". Nhãn không `aria-hidden`, vì người dùng trình đọc màn hình cũng cần biết loại.
- **Khoá bộ đệm `useLazySection`** chỉ dựng từ `params`, nên `showTaxonomy` không làm đổi khoá.
- **Timeout gợi ý cá nhân hoá giữ 10 s** (người dùng chốt); không đổi code.
- **Trang `/experiences` giữ tab golf riêng;** quyết định gộp golf chỉ áp cho trang chủ.

## Kiểm tra

Chạy trong `src/frontend` của worktree, sau `npm ci`:

- `npm run typecheck`: sạch.
- `npm run lint`: 0 lỗi; 3 cảnh báo có sẵn ở `ItineraryMap.tsx` và `useFloatingWidget.ts`, không liên quan.
- `npm run test`: 80 file, 836 test pass.
- e2e `navigation.spec.ts` không chạy ở máy (CI chạy); test này chỉ đếm pathname `/products` nên không bị ảnh hưởng.

## Còn lại / rủi ro

- Chưa xem bằng mắt trên trình duyệt với backend thật.
- Khi merge, nếu frontend mới chạy với backend cũ, tab "Vé tham quan" sẽ trả 400 (backend cũ không nhận `attraction,golf`). Nên deploy backend trước.
- `TaxonomyBadge` lùi về nhãn khách sạn khi gặp taxonomy lạ, trong khi spec ghi "Dịch vụ". Lỗi này có từ trước, ngoài phạm vi.
