# Một thang màu thương hiệu chung cho toàn hệ thống

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Yêu cầu "một màu chung cho toàn hệ thống". Trước đó `globals.css` không có token màu: ~630 chỗ `blue-*`, 56 chỗ `indigo-*` rải ở ~90 file, cộng một vài hex lẻ (nền hero), nên không có chỗ nào để đổi màu cả app. Chỉ là hạ tầng giao diện, không đổi hành vi, contract hay backend; không lệch PRD.

## File thay đổi

- `src/frontend/src/app/globals.css` — sửa: thêm `@theme static` với `brand-50…950` và `accent-300/400/950`; `.ota-hero-bg` dùng biến thay hex.
- 82 file `.ts`/`.tsx` trong `src/frontend/src` và `src/frontend/tests` — sửa: `blue-N` và `indigo-N` → `brand-N`; `sky-N` → `brand-N` riêng ở `AssistantResultPanel.tsx` (trang trí). Chỉ đổi tên lớp, không đổi bố cục. (Danh sách đầy đủ: `git diff --stat`.)
- `src/frontend/src/components/detail/HotelTripBar.tsx` — sửa: nút Tìm dùng `accent-*`, chữ `brand-950`.
- `src/frontend/tests/unit/headerStyles.test.ts` — sửa: `bg-blue-600` → `bg-brand-600`.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§6.7) — thêm: quy ước màu.
- `history/2026-10-08-thang-mau-thuong-hieu-chung.md` — thêm: entry này.

## Quyết định

- `brand` mặc định = thang `blue` của Tailwind nên giao diện giữ nguyên; muốn màu khác chỉ sửa 11 giá trị trong `globals.css`. Chưa đổi màu chủ đạo vì chưa có quyết định về tông mới.
- Giữ nguyên màu mang nghĩa riêng: emerald (thành công), amber (cảnh báo), rose/red (lỗi), teal/cyan/violet/purple ở `TaxonomyBadge`, `AirlineBadge`, `BecauseLine`, `ItineraryMap`, `DebugPanel`.
- `@theme static` để biến `--color-brand-*` luôn có mặt, dùng được cả trong CSS thường (`var(--color-brand-700)`).

## Kiểm tra

- `vitest run tests/unit` (từ `src/frontend`): 64 file, 680 test pass. `tsc --noEmit` sạch. `eslint .`: 0 lỗi, 2 cảnh báo cũ ở `ItineraryMap.tsx`.
- Trình duyệt thật: trang chủ và trang chi tiết khách sạn hiển thị như trước; `--color-brand-600` = `#2563eb`. Chưa duyệt từng trang còn lại.

## Còn lại / rủi ro

- Hex lẻ còn trong code: `ItineraryMap.tsx` (màu ghim Leaflet, cần chuỗi hex), một số nền xám xanh ở vài component; chưa đưa vào token.
- Nhánh mới viết `blue-*` trực tiếp sẽ không theo thang; chưa có lint chặn.
