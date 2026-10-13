# Ảnh hero theo kích thước màn hình và tải lười ảnh panorama trang chủ

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/perf-lcp-mobile (worktree `.claude/worktrees/perf-lcp-mobile`, tách từ `release-mvp-v2` ở `b25647c2`)
- Trạng thái: hoàn thành (mã và kiểm tra cục bộ). Chưa deploy staging, chưa đo lại trên staging.
- Phạm vi: frontend

## Mục tiêu

Lighthouse mobile trên `https://praxis.io.vn/` (13/10, lần 2) cho LCP 8,6 s. Phần tử LCP là ảnh hero (`photo-1582719508461`, `w=2000`, `fetchpriority="high"`). Ảnh này nặng 311 KB ở AVIF. Cùng lúc, ảnh panorama dưới trang (`photo-1506929562872`, 1,1 MB) không có `loading="lazy"` nên tải song song và tranh băng thông với ảnh hero.

Không thực hiện đề xuất Cloudflare (Rocket Loader, Polish, Argo, Zaraz) theo quyết định của người yêu cầu. Chỉ sửa trong mã frontend.

Không có FR/NFR nào trong `docs/prd/requirements.md` mô tả LCP frontend. NFR-PERF-01 chỉ nói về độ trễ API, nên thay đổi này không lệch PRD và không cần đề xuất `docs/prd/update/`.

## File thay đổi

- `src/frontend/src/lib/unsplash.ts` — thêm: `unsplashUrl(photoId, width)`, `unsplashSrcSet(photoId)` và `UNSPLASH_DEFAULT_WIDTH = 1280`. Cỡ srcSet: 640, 960, 1280, 1920.
- `src/frontend/src/components/home/HomeView.tsx` — ảnh hero: `src` 1280 px, `srcSet` đầy đủ, `sizes="100vw"`; `fetchPriority` và `loading="eager"` giữ nguyên. Ảnh panorama: `srcSet`, `sizes="100vw"`, thêm `loading="lazy"` và `decoding="async"`.
- `src/frontend/src/features/catalog/landing/verticals.ts` — `VerticalConfig.heroImage: string` đổi thành `heroPhoto: string` (mã ảnh Unsplash). Bỏ hàm `heroUrl` cứng `w=2000`.
- `src/frontend/src/features/catalog/landing/LandingHero.tsx` — dựng `src` và `srcSet` từ `heroPhoto` bằng helper mới, giữ thuộc tính LCP.
- `src/frontend/tests/unit/unsplashImage.test.ts` — test mới: URL theo width, srcSet có đủ cỡ, không còn `w=2000`, `src` nằm trong `srcSet`.

## Quyết định

- Dùng `<img srcSet>` thuần, không dùng `next/image`. Lý do: Unsplash tự resize theo tham số `w`. `next/image` với ảnh từ xa cần `remotePatterns` và bộ tối ưu chạy trên server, nên sẽ tốn CPU và đổi cả pipeline ảnh. Phần còn lại của code cũng dùng `<img>`.
- Không đổi `q` (vẫn 80) và `auto=format`. Mục tiêu chỉ là giảm kích thước theo màn hình, không giảm chất lượng.
- Ảnh panorama dùng `loading="lazy"` vì nằm sâu dưới trang, không phải LCP.

## Kiểm tra

Kích thước ảnh hero đo bằng `curl`, header `Accept: image/avif,image/webp,*/*` (định dạng AVIF do Unsplash trả):

| w | Kích thước |
|---|---|
| 640 | 57.235 B |
| 960 | 106.421 B |
| 1280 | 157.356 B |
| 1920 | 291.492 B |
| 2000 (trước) | 310.999 B |

Mobile ~412 px × DPR ~2,6 cần khoảng 1080 px, nên trình duyệt sẽ chọn 1280 (157 KB), giảm ~50% so với 2000 (311 KB).

Lệnh đã chạy trong worktree (`src/frontend`):

- `npx tsc --noEmit` — pass (exit 0)
- `npx eslint` trên 5 file đã sửa — pass (exit 0)
- `npx vitest run tests/unit/unsplashImage.test.ts tests/unit/catalogService.test.ts` — 12 test pass
- `npx vitest run tests/unit` — pass: 81 file, 875 test
- `npm run build:web` — pass (exit 0), compile thành công, route trang chủ và trang vertical build bình thường

## Còn lại / rủi ro

- **Chưa xử lý JS trên mobile.** Lighthouse mobile lần 2 cho thấy chunk `3794-*.js` tốn 5,3 s thời gian chạy (lần 1: 12,4 s), TBT 2.040 ms. Phần này chưa điều tra. Cần profile (trace) để biết đoạn nào tốn thời gian trước khi sửa.
- **Ảnh sản phẩm từ CDN bên thứ ba chưa xử lý.** Ảnh `ak-d.tripcdn.com` nặng ~1,4 MB ở bản gốc. Đo thử, CDN này trả ~88 KB với hậu tố `_W_640_400_R5_Q80`. Đây là quy tắc riêng của từng nhà cung cấp và ảnh hưởng toàn bộ thẻ sản phẩm, nên cần quyết định trước khi làm.
- Google Fonts vẫn tải qua `<link>` trong `app/layout.tsx`. Lighthouse không báo đây là tài nguyên chặn render đáng kể, nên chưa đổi.
- Chưa deploy và chưa đo lại trên staging. Số liệu sau thay đổi cần đo bằng Lighthouse trên staging sau khi deploy.
