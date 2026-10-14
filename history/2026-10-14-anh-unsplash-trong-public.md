# Đưa ảnh Unsplash hard-code vào public/ (14 ảnh)

- Ngày: 2026-10-14
- Tác giả: Khoa15 / Claude Code
- Nhánh: khoa/unsplash-images-public (tách từ `origin/release-mvp-v2`)
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Ảnh hard-code từ `images.unsplash.com` (hero và panorama trang chủ, hero các trang danh mục, ảnh bìa điểm đến) được tải về và lưu trong `public/images/unsplash/`, phục vụ qua bộ tối ưu của Next và cache dưới domain của mình. Trình duyệt không còn kết nối tới host bên thứ ba cho các ảnh này.

## File thay đổi

- `src/frontend/public/images/unsplash/<mã ảnh>.webp` — thêm: 14 file WebP, bản gốc 1920 px, tổng ~7,4 MB. 12 file thay cho hotlink cũ; 2 file (Hà Nội, Huế) bổ sung ảnh bìa điểm đến còn thiếu.
- `src/frontend/src/lib/unsplash.ts` — viết lại: `unsplashPath(id)` thay `unsplashUrl`, `unsplashSrcSet` và `UNSPLASH_DEFAULT_WIDTH`.
- `src/frontend/src/components/home/HomeView.tsx` — hero (`priority`) và panorama (lazy) dùng `next/image` với `fill`.
- `src/frontend/src/features/catalog/landing/LandingHero.tsx` — hero danh mục dùng `next/image` (`priority`).
- `src/frontend/src/features/catalog/landing/DestinationTiles.tsx` — ảnh bìa điểm đến dùng `next/image` (`fill`, `sizes="176px"`).
- `src/frontend/src/features/catalog/landing/destinationCovers.ts` — đường dẫn local; thêm ảnh bìa cho `Hà Nội` và `Huế`.
- `src/frontend/src/features/catalog/landing/verticals.ts` — chỉnh chú thích `heroPhoto`.
- `src/frontend/src/app/globals.css` — xoá `.hero-resort-layer`: không có phần tử nào dùng, chứa URL Unsplash.
- `src/frontend/next.config.ts` — `images.minimumCacheTTL: 604800` (7 ngày).
- `src/frontend/tests/unit/unsplashImage.test.ts` — viết lại: đường dẫn và file tồn tại trong `public/`, gồm cả hai điểm đến mới.
- `src/frontend/tests/unit/verticals.test.ts` — kỳ vọng đường dẫn local.

## Quyết định

- Hà Nội và Huế là hai điểm đến top trên trang chủ (362 và 268 sản phẩm) nhưng trước đó không có ảnh bìa trong `COVERS`, nên ô chỉ hiện gradient. Ảnh mới: cầu Thê Húc trên hồ Hoàn Kiếm (Hà Nội, `1753380226922-06a65b17ddf2`) và cổng Ngọ Môn Kinh thành Huế (`1765034841805-8330b54bfdb7`). Đã kiểm tra nội dung ảnh trước khi dùng.
- Lưu bản gốc 1920 px theo lựa chọn của người dùng. Next tự sinh các cỡ `srcSet` từ một file gốc.
- Tải với `Accept: image/webp`. Không có header này Unsplash trả JPEG dù URL có `auto=format`.
- Giấy phép Unsplash cho phép tải và dùng miễn phí, không bắt buộc ghi công. Không bán nguyên bản và không tổng hợp ảnh để làm dịch vụ cạnh tranh.
- `minimumCacheTTL` 7 ngày, vì Next mặc định chỉ 60 giây. Next không có cơ chế xoá cache tối ưu, nên đổi nội dung một file cần đổi tên file.

## Kiểm tra

- `tsc --noEmit`: pass.
- `eslint` trên các file đã sửa: pass.
- `vitest run tests/unit`: 80 file pass, 1 file todo; 873 test pass, 1 todo.
- `npm run build:web`: pass.
- Trang chủ và `/hotels` trả HTML không còn `images.unsplash.com`. Hero có thẻ preload.
- `/images/unsplash/1582719508461-905c673771fd.webp`: HTTP 200, `image/webp`, 552 KB.
- Dung lượng hero qua bộ tối ưu cục bộ: 42 KB (w=640), 61 KB (w=828), 90 KB (w=1080), 217 KB (w=1920). Bản hotlink cũ ở w=1280 là 277 KB.

## Còn lại / rủi ro

- Phản hồi của `/_next/image` có `max-age=604800` (7 ngày), dưới ngưỡng ~97 ngày của Lighthouse. Vì vậy `uses-long-cache-ttl` có thể vẫn cảnh báo cho các ảnh này. Muốn đóng cảnh báo thì nâng `minimumCacheTTL` lên khoảng 110 ngày và chấp nhận đổi tên file khi đổi ảnh.
- Lần tải đầu của mỗi cỡ mất khoảng 1 giây (sharp), các lần sau lấy từ cache.
- Repo tăng khoảng 6 MB file nhị phân.
- Chưa đo Lighthouse trên staging vì chưa deploy.
