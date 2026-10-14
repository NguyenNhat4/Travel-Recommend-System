# Khắc phục 5 vấn đề Lighthouse trên staging (praxis.io.vn)

- Ngày: 2026-10-14
- Tác giả: Khoa15 / Claude Code
- Nhánh: khoa/lighthouse-staging-fixes (tách từ `origin/release-mvp-v2`)
- Trạng thái: dang dở
- Phạm vi: frontend

## Mục tiêu

Lighthouse 12.8.2 mobile và desktop trên `https://praxis.io.vn/` (14/10) cho Performance 69/70, Accessibility 93/96, Best Practices 75/74, SEO 100. Năm vấn đề được ghi nhận:

1. JS mobile nặng: chunk `3794` tốn 11,9 s CPU.
2. Ảnh hero LCP quá lớn (`w=2000`).
3. Accessibility: tương phản thấp, vùng chạm tab bar, `aria-label` logo không khớp.
4. Best Practices: 404 `/favicon.ico`, cookie bên thứ ba.
5. Cache: file `public/` có `max-age` 4 giờ.

Yêu cầu bổ sung trong phiên: xóa nút DEBUG.

## File thay đổi

- `src/frontend/src/components/common/DebugPanel.tsx` — sửa: bỏ nút "DEBUG (Shift+D)" theo yêu cầu, bỏ import `Bug` không còn dùng. Phím Shift+D (`TravelContext`) vẫn bật/tắt panel.
- `src/frontend/src/components/common/Header.tsx` — sửa: `aria-label` logo thành `Sota Resorts & Hotels, về trang chủ` để chứa đủ chữ hiển thị.
- `src/frontend/src/components/common/ProductCard.tsx` — sửa: số đánh giá `text-slate-400` → `text-slate-500` (ba chỗ). Tương phản `#90a1b9`/`#f8fafc` = 2,51; `#62748e`/`#f8fafc` = 4,55.
- `src/frontend/src/components/common/PriceTag.tsx` — sửa: `Intl.NumberFormat('vi-VN')` dựng một lần ở module thay vì mỗi lần render.
- `src/frontend/src/features/search/tripContext.ts` — sửa: `Intl.DateTimeFormat` của `todayVN` dựng một lần.
- `src/frontend/src/features/flights/results/flightHref.ts` — sửa: `Intl.DateTimeFormat` của ngày bay dựng một lần.
- `src/frontend/src/features/itinerary/widget/WidgetLauncher.tsx` — sửa: trên mobile nâng widget nổi lên trên tab bar (`bottom-[calc(3.5rem+env(safe-area-inset-bottom)+0.75rem)]`, `md:bottom-5`). Vẫn ở góc dưới phải theo `user-flow.md` §3.
- `src/frontend/src/app/icon.svg` — mới: favicon SVG nền `#2563EB`, chữ "S" trắng. Next tự thêm `<link rel="icon">`.
- `history/2026-10-14-lighthouse-staging-fixes.md` — mới: entry này.

Commit `40a80048` (ảnh hero srcset và lazy panorama) là bản cherry-pick của `bf8c1765` trên `khoa/perf-lcp-mobile`. Nội dung giống hệt PR #207 đã merge vào `release-mvp-v2` (`535df6bc`).

## Quyết định

- **Vấn đề 1:** CPU profile trên lab cho thấy chunk `7323` (`PriceTag`, `ProductCard`, helper ngày) tốn 1916 ms, trong đó hàm `PriceTag` và helper ngày chiếm phần lớn vì tạo `Intl.*Format` mỗi lần gọi. Hoist ra module-level, không đổi kết quả hiển thị. Phần còn lại (`4bd1` React, `3794` router Next) không sửa trong entry này.
- **Vấn đề 3:** Hai nguyên nhân của `target-size` là nút DEBUG và widget nổi đè lên tab bar dưới. Xóa nút DEBUG và nâng widget trên mobile, không ẩn widget vì `user-flow.md` §3 yêu cầu widget ở mọi trang trừ `/checkout`.
- **Vấn đề 4:** Favicon là quyết định tạm thời. Đề xuất `docs/prd/update/2026-10-12-doi-logo-du-sota.md` (câu hỏi 3, favicon) còn chờ chốt; nếu đổi logo thì cập nhật lại `icon.svg`. Cookie `__cf_bm` và `_cfuvid` do Cloudflare set qua ảnh từ `booking-static.vinpearl.com`, không sửa được trong repo.
- **Vấn đề 5:** `Cache-Control` 4 giờ của file `public/` do cache rule Cloudflare đặt (xem `history/2026-10-13-cloudflare-cache-rule-catalog.md`), nằm ngoài repo. Lighthouse chỉ đạt khi thời gian cache khoảng 110 ngày trở lên; đây là quyết định chính sách cache, chưa sửa.

## Kiểm tra

- `npx tsc --noEmit`: pass.
- `npx eslint` trên các file TS/TSX đã sửa: pass (cảnh báo về `icon.svg` là bình thường).
- `npx vitest run tests/unit`: 81 file, 874 test pass.
- `npm run build:web`: pass.
- Lighthouse 12 mobile trên lab local (build production, API proxy tới staging, cùng cấu hình trước và sau):

| Chỉ số | Trước | Sau |
|---|---|---|
| Performance | 61 | 63 |
| Accessibility | 93 | 100 |
| Best Practices | 75 | 79 |
| TBT | 400 ms | 240 ms |
| LCP | 5,0 s | 5,1 s |
| Chunk `7323` (CPU) | 1916 ms | 889 ms |

Số trước đã gồm PR #207 (commit `40a80048`), nên LCP không đổi ở đây là đúng. Lab không tương đương staging: staging đo Performance 69 và LCP 4,0 s, nên không so trực tiếp với số trên.

- Kiểm tra trên staging ở viewport 375×812: nút DEBUG đè "Trang chủ"; widget nổi đè "Trợ lý", "Giỏ hàng", "Tài khoản". Sau thay đổi, cần deploy để kiểm lại.

## Còn lại / rủi ro

- Vấn đề 1: còn chunk React (`4bd1`) và router Next (`3794`); chưa có giải pháp trong entry này.
- Vấn đề 2: LCP là ảnh hero Unsplash, chọn cỡ 960 px trên mobile. Ảnh sản phẩm từ `ak-d.tripcdn.com` và `booking-static.vinpearl.com` chưa resize (bên thứ ba).
- Vấn đề 4: cookie bên thứ ba và `inspector-issues` còn lỗi; cần quyết định với chủ host ảnh `booking-static` hoặc chấp nhận.
- Vấn đề 5: cần người vận hành quyết định TTL cache Cloudflare cho file `public/` (kèm đánh đổi ảnh cũ trong thời gian dài).
- Favicon và chỉnh `aria-label` logo cần đối chiếu với đề xuất logo "Dự Sota" đang chờ chốt.
- Chưa deploy staging; số Lighthouse trên staging sau thay đổi chưa đo.
