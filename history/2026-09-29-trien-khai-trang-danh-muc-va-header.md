# Triển khai trang danh mục dịch vụ, header nhóm dịch vụ và Home tải lười

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (chờ nghiệm thu bằng mắt; xem Còn lại)
- Phạm vi: frontend, docs

## Mục tiêu

Làm hết P0–P6 của `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md`: xây UI theo bố cục trang khách sạn của VP-OTA, sửa việc Home gọi mọi dữ liệu cùng lúc và các nút header "Di chuyển / Tour và trải nghiệm…" chưa có nội dung. Phục vụ FR-CAT-01, FR-SRC-01, FR-SRC-03, FR-REC-01, FR-AGT-01; giữ AC-REC-01/02.

## File thay đổi

Mới (`src/frontend/`):
- `src/app/(storefront)/{hotels,flights,experiences,combos}/page.tsx` — trang danh mục, đọc `destination`/`type` ở server.
- `src/features/catalog/landing/{verticals,destinationCovers,searchHref,useDestinations}.ts`, `{VerticalLanding,LandingHero,LandingSearchSheet,DateRangePicker,GuestsPopover,ProductShelf,DestinationTiles,PromoBanner}.tsx` — template trang danh mục.
- `src/features/search/tripContext.ts` — ngày/số khách qua URL.
- `src/components/layout/nav/{navConfig.ts,NavMenu.tsx,MenuShell.tsx,NavIcon.tsx,VerticalChips.tsx}` — điều hướng nhóm.
- `src/hooks/{useInView,useLazySection}.ts` — tải lười và bộ đệm.
- `tests/unit/{navConfig,navMenu,tripContext,searchHref,verticals,useInView,useLazySection,landingSearchSheet,verticalLanding,homeView,tripPrefill}.test.ts(x)`, `tests/e2e/navigation.spec.ts`.

Sửa:
- `src/components/common/Header.tsx` — viết lại: overlay/solid, bốn nhóm có menu, nút lưới, Trợ lý AI; bỏ chuông và V-Points, bỏ dòng "Ưu đãi V-OTA Silver".
- `src/components/home/HomeView.tsx` — 1382 → ~390 dòng: bốn ô danh mục, ① giữ nguyên + timeout 3 giây, ④ một carousel có tab, điểm đến từ API; bỏ dữ liệu cứng và form khách sạn.
- `src/components/common/ProductCard.tsx` — thêm `variant="tile"` và `tripQuery`.
- `src/components/common/Footer.tsx` — cột "Dịch vụ" trỏ route thật.
- `src/components/search/SearchView.tsx` — chip ngữ cảnh chuyến đi, giữ ngữ cảnh khi đổi tab/tìm lại, tiêu đề theo danh mục khi `q` là câu mặc định.
- `src/components/detail/ProductDetailView.tsx` — điền sẵn hộp đặt từ URL khi hợp lệ.
- `src/services/search.ts` — `DEFAULT_QUERY` theo danh mục (trước đây `q` rỗng luôn tìm "khách sạn").
- `src/context/TravelContext.tsx` — gọi `clearSectionCache()` khi đổi tài khoản.
- `src/app/globals.css` — `.glass-pill`, `.glass-sheet`, `.glass-panel`, `.skeleton-wave`, `.snap-row`, `prefers-reduced-motion`.
- `tests/unit/searchService.test.ts`, `tests/e2e/widget-opening.spec.ts` — thêm ca query rỗng; đặt lại bộ đếm `/destinations` sau khi Home tải xong (Home nay tự tải điểm đến khi cuộn tới, điều cần kiểm là việc mở widget không tải thêm).
- `src/frontend/README.md`, `docs/spec/hop-dong-tich-hop-frontend.md` (§3, §4.1, §4.1a mới), `docs/spec/product.md` (§3.1, §3.3, §4.2.1, §7.2), `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md` (tiến độ, kết quả).

## Quyết định

- Chi tiết các điểm khác plan nằm ở mục "Kết quả triển khai" của plan (không hủy request khi unmount, `price_asc` không cần lọc null, `DEFAULT_QUERY` ở services, trang đọc query ở server, header mobile gọn, P3 gộp P5).
- Không đổi contract, DB, backend, mock nên không chạy `validate_contract.py`.
- Chỉ lấy bố cục và hành vi từ mẫu VP-OTA; logo, ảnh, câu chữ, thông tin pháp nhân, script theo dõi không dùng. Ảnh hero chọn và xem bằng mắt (ảnh piano đầu tiên bị loại).

## Kiểm tra

- `./node_modules/.bin/tsc --noEmit`: sạch.
- `./node_modules/.bin/eslint .`: 0 lỗi, 3 cảnh báo có sẵn (`ItineraryMap`, `ShareItineraryModal`).
- `./node_modules/.bin/vitest run`: 43 file, 378 test pass (baseline trước khi sửa 27 file, 257 test). Lần chạy song song đầu có một test `productDetailView` chập chờn, chạy lại đều pass.
- Playwright trỏ vào dev server đang chạy (không dùng `npm run test:e2e`: môi trường không có `npm`, và `build:web` sẽ ghi đè `.next` của dev server): `navigation.spec.ts` 8/8 (sau khi sửa tràn ngang header ở 375 px), `routes.spec.ts` và `widget-opening.spec.ts` 8/8 (lần chạy đầu 1 ca stream chập chờn do dev server tải nặng, chạy lại pass).
- Đếm request Home (khách, 1440 px): trước 2 request danh mục khi tải (4 ở dev StrictMode) → sau 1; `/destinations` chỉ khi cuộn. Xem ảnh chụp `/`, `/hotels` ở 1440 px và `/hotels` ở 375 px bằng mắt.

## Còn lại / rủi ro

- Chưa chạy với Backend và seed thật: AC-REC-01/02 (gợi ý cá nhân hóa, "vé máy bay sau khi đặt phòng") chỉ được kiểm ở mức mã ① giữ nguyên; cần người dùng xem bằng `make web`.
- Chưa chạy `npm run test:e2e` chuẩn và chưa kiểm tương phản chữ trắng trên hero bằng công cụ (chỉ xem bằng mắt).
- Ảnh hero/điểm đến là URL Unsplash; ảnh "Nha Trang" cũ nhìn không đúng địa điểm. Liên kết pháp lý ở Footer vẫn trỏ `/`.
- `/destinations` gộp mọi danh mục nên chip ở `/flights?destination=X` có thể ra rỗng (đã có thông báo và liên kết ra).
