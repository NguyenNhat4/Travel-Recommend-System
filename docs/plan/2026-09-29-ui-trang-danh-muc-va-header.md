# Kế hoạch: Trang danh mục dịch vụ và thanh điều hướng mới (theo bố cục trang `/hotels` của VP-OTA)

- Tệp đầu ra: `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md`
- Ngày: 2026-09-29
- Phục vụ: FR-CAT-01, FR-SRC-01, FR-SRC-03, FR-REC-01 (giữ khối gợi ý ở Home), FR-AGT-01 (lối vào trợ lý); AC-REC-01, AC-REC-02 phải giữ nguyên hành vi; NFR-PERF-01 (gián tiếp: giảm số request đồng thời lúc mở trang) (`docs/prd/requirements.md`)
- Đề xuất PRD: `docs/prd/update/2026-09-29-route-trang-danh-muc-dich-vu.md` — **sẽ tạo ở bước P0, trạng thái chờ chốt** (chỉ chặn P4)
- Spec cập nhật cùng thay đổi: `docs/spec/hop-dong-tich-hop-frontend.md` §3, §4.1; `docs/spec/product.md` §3.1, §3.3, §4.1, §4.2.1, §7.2
- Người làm: mihhquan / Claude Code. Nên tách nhánh riêng (đang ở `feat/booking`) vì chạm Header và Home dùng chung
- Lịch sử: `history/2026-09-29-plan-ui-trang-danh-muc-va-header.md` (khi lưu plan); mỗi bước code có entry riêng

## Bối cảnh

Yêu cầu gốc: xây UI theo bố cục trang khách sạn của VP-OTA (file HTML người dùng cung cấp). Hai vấn đề hiện có:

1. **Home "gọi tất cả".** `src/frontend/src/components/home/HomeView.tsx` (1382 dòng) vừa là trang chủ vừa là trang khách sạn (hero ghi "Khách sạn", có form ngày/phòng). Ngay khi mount nó gửi song song `GET /products?taxonomy=hotel&limit=8`, `GET /products?sort=popular&limit=8` và `GET /recommendations` (nếu đã đăng nhập), kể cả các khối nằm dưới màn hình.
2. **Nút header chưa có nội dung.** `src/frontend/src/components/common/Header.tsx`: bốn nút "Di chuyển / Lưu trú / Tour và trải nghiệm / Tiện ích khác" chỉ là `navigate('/search?type=…')`; không có menu con, không có trang riêng; "Lưu trú" luôn được tô đậm dù đang ở route nào; cả nhóm nút bị ẩn dưới 1024 px (`hidden lg:flex`) và `MobileTabBar` cũng không có lối vào danh mục.

Hiện trạng cần dọn cùng lúc (đọc từ code, không suy đoán):

- `HomeView.tsx` cứng các thứ không đến từ API: 7 điểm đến kèm mô tả và số đếm tự viết (ví dụ "36 Khách sạn & Resort"), 6 khách sạn gợi ý tên bịa ("V-OTA Resort & Spa tại Hạ Long"), ngày mặc định `18/09/2026`, danh sách "tìm kiếm gần đây". Trái quyết định `history/2026-09-25-trang-chi-tiet-san-pham-that-va-chon-hang-phong.md` ("bỏ mọi đường lui về dữ liệu giả ở Web").
- `handleSearch` gửi `rooms`, `guests` nhưng `SearchView` chỉ đọc `q`, `type|taxonomy`, `destination|dest`; ngày không được gửi đi đâu cả. `handleSelectDestination` chỉ điền ô và cuộn trang dù toast báo "đang chuyển đến kết quả".
- Header có chuông thông báo với khuyến mãi bịa ("giảm 15%", "voucher 100k") và "1.250 V-Points" cứng.
- Footer: mọi liên kết là `navigate('/')`.
- Nút "Xem thêm" của các carousel đang để comment, chờ "trang danh mục" (`history/2026-09-17-home-search-assistant.md`, `2026-09-21-home-buttons-webp.md`). Plan này chính là trang đó.

### Lấy gì từ mẫu VP-OTA, không lấy gì

Lấy **bố cục và hành vi**: header kính mờ nổi trên hero, nút nhóm có menu con và nút "tất cả dịch vụ"; hero cao ~500 px có ảnh nền + lớp phủ tối; tấm tìm kiếm kính mờ với các "viên" Địa điểm / Ngày đi–Ngày về / Số lượng; nền trắng bo góc trên đè lên hero 32 px; skeleton đúng khung thẻ; các khối dưới màn hình chỉ tải khi cuộn tới (`data-component-inview`); chân trang nền xanh đậm.

**Không lấy:** logo, ảnh, câu khẩu hiệu, thông tin pháp nhân (số ĐKKD, địa chỉ), màu thương hiệu, font Cal Sans, và các script GTM/Datadog/Insider có trong HTML mẫu. Giữ logo V-OTA, bảng màu hiện tại, font Plus Jakarta Sans + Inter. Phụ đề hero hiện đang chép nguyên câu của mẫu ("Lưu lại các điểm đến trong mơ…"), sẽ viết lại bằng lời của V-OTA. Mẫu chỉ có bản desktop (`min-w-(--breakpoint-desktop)`); bản của ta phải responsive theo `docs/spec/product.md` §7.

## Phạm vi

**Trong phạm vi:** header + menu nhóm dịch vụ; bốn trang danh mục; tấm tìm kiếm có ngày/số khách; viết lại Home mỏng và tải lười; chip danh mục trên mobile; chân trang trỏ đúng route; test và tài liệu.

**Ngoài phạm vi (không đụng):** backend, OpenAPI, DB; giỏ, checkout, trang đơn; widget trợ lý; đăng nhập. Không thêm thư viện (không TanStack Query, không nuqs). Không nhận lọc ngày phía server: backend chưa xử lý `travelContext`/`CHECK_DATE_RANGE` (không có trong `src/backend`), nên không gửi các trường đó.

## Giả định cần xác nhận

Plan làm theo cột "Mặc định"; sai ý thì đổi ở bước duyệt, chi phí đổi rất thấp vì cấu hình nằm một chỗ (`navConfig.ts`, `verticals.ts`).

| # | Câu hỏi | Mặc định của plan |
|---|---|---|
| A1 | Nhóm header ↔ danh mục dữ liệu ↔ route | Di chuyển → `flight` → `/flights`. Lưu trú → `hotel` → `/hotels`. Tour và trải nghiệm → `attraction` + `golf` → `/experiences` (tab Vé tham quan / Sân golf). Tiện ích khác → `combo` → `/combos`, kèm mục "Trợ lý lịch trình AI" → `/assistant` |
| A2 | Home là gì | Trang tổng quan (tìm kiếm AI, lối vào bốn danh mục, gợi ý cá nhân hóa, phổ biến theo tab, điểm đến). Không còn là trang khách sạn; form ngày/phòng chuyển sang `/hotels` |
| A3 | Có thêm nút "Trợ lý AI" vào header | Có, dạng viên riêng bên phải (PRD `user-flow.md` §4.1 vẽ "Trợ lý AI" trên thanh điều hướng) |
| A4 | Chuông thông báo và V-Points cứng | Bỏ (mẫu cũng không có; nội dung là bịa) |
| A5 | Ngày, số khách trên tấm tìm kiếm | Là ngữ cảnh chuyến đi: đi qua URL tới `/search` rồi tới hộp đặt ở trang chi tiết để điền sẵn. Không phải bộ lọc phòng trống; giao diện ghi rõ "Ngày còn chỗ được kiểm khi chọn phòng" |
| A6 | Banner cuối trang danh mục | CTA sang trợ lý AI (tính năng thật của ta), không có khuyến mãi giả |

## Thiết kế

### 1. Điều hướng và route

`src/frontend/src/components/layout/nav/navConfig.ts` là nguồn duy nhất cho header, menu "tất cả dịch vụ", chip mobile, chân trang và trạng thái "đang ở đâu".

| Nhóm header | Mục trong menu | `href` (sau P4) | `href` tạm (P2–P3) |
|---|---|---|---|
| Di chuyển | Vé máy bay | `/flights` | `/search?type=flight` |
| Lưu trú | Khách sạn & resort | `/hotels` | `/search?type=hotel` |
| Tour và trải nghiệm | Vé tham quan & vui chơi; Sân golf | `/experiences`; `/experiences?type=golf` | `/search?type=attraction`; `/search?type=golf` |
| Tiện ích khác | Combo du lịch; Trợ lý lịch trình AI | `/combos`; `/assistant` | `/search?type=combo`; `/assistant` |

Hành vi menu (mẫu disclosure, không dùng `role="menu"` vì bên trong là liên kết): bấm hoặc rê chuột (chỉ khi `(hover:hover)`, trễ 120 ms) mở panel; Enter/Space bật tắt; Esc đóng và trả focus về nút; Tab đi qua các liên kết; bấm ra ngoài đóng; `aria-expanded` đúng trạng thái; mục hiện tại có `aria-current="page"`. Các mục dùng `next/link` (thay `<button onClick={navigate}>`) để chuột giữa và crawler hoạt động.

Panel gồm cột trái (icon + tên + một dòng mô tả tĩnh, không nêu số liệu) và cột phải "Điểm đến phổ biến": tối đa 6 chip lấy từ `GET /destinations` (sắp theo `productCount` giảm dần), mỗi chip là `{route}?destination={tên}`. `/destinations` chỉ gọi khi mở menu lần đầu và dùng chung cache với trang danh mục.

Nhóm được tô đậm theo route hiện tại: `pathname` khớp `href` của mục, hoặc `/search` có `type` thuộc nhóm. Ở `/` không nhóm nào được tô.

### 2. Header

`Header.tsx` sửa tại chỗ, thêm biến thể:

- **Overlay** trên `/`, `/hotels`, `/flights`, `/experiences`, `/combos`: `fixed`, viên kính bo `rounded-[38px]` nổi trên hero, chữ trắng. Khi cuộn qua hero (IntersectionObserver trên một phần tử mốc, như `<div class="sticky top-0 h-0">` của mẫu) chuyển sang nền trắng mờ chữ tối, có viền dưới.
- **Solid** như hiện tại ở mọi route khác; `isCheckout` giữ nguyên.
- Bên phải: viên "Trợ lý AI" (icon Sparkles) → ngôn ngữ → "Đặt chỗ của tôi" (giữ dropdown và huy hiệu giỏ) → tài khoản / Đăng nhập. Bỏ chuông và V-Points (A4).
- Dưới 1024 px: chỉ logo + ngôn ngữ + tài khoản (đúng `product.md` §7.2). `MobileTabBar` giữ 5 tab; lối vào danh mục là hàng chip cuộn ngang `VerticalChips` ở đầu Home và trang danh mục.

`AppShell.tsx` quyết định biến thể theo `currentRoute` và không thêm padding trên cùng cho `<main>` ở route overlay (hero tự chừa chỗ cho header).

### 3. Trang danh mục `VerticalLanding`

Một template, bốn cấu hình trong `verticals.ts` (taxonomy, route, tiêu đề, phụ đề, ảnh hero, `defaultQuery`, trường của tấm tìm kiếm, tên các khối).

```
Header (overlay)
Hero ~500 px: ảnh nền + lớp phủ 36%, H1, phụ đề, tấm tìm kiếm kính mờ (bo 38 px, blur 36 px)
─ nền trắng bo góc trên, đè hero 32 px ─
Khối 1  "<Danh mục> phổ biến"          tải ngay      GET /products (popular)
Khối 2  "Giá tốt nhất"                 tải khi vào vùng nhìn   GET /products (price_asc)
Khối 3  "Điểm đến phổ biến"            tải khi vào vùng nhìn   GET /destinations (cache chung)
Khối 4  Banner CTA sang trợ lý         tĩnh
Footer
```

| Danh mục | Route | H1 | Tab | `taxonomy` của khối 1–2 |
|---|---|---|---|---|
| Lưu trú | `/hotels` | Khách sạn & resort | — | `hotel` |
| Di chuyển | `/flights` | Vé máy bay | — | `flight` |
| Tour và trải nghiệm | `/experiences` | Tour và trải nghiệm | Vé tham quan · Sân golf (`?type=`) | `attraction` hoặc `golf` |
| Tiện ích khác | `/combos` | Combo du lịch | — | `combo` |

Mọi lời gọi khối 1–2 dùng `listProducts({ taxonomy, sort, availableOnly: true, limit: 8 })` có sẵn ở `services/catalog.ts`. Có `?destination=` thì thêm vào tham số và đổi tiêu đề thành "… tại {điểm đến}"; rỗng → EmptyState "Chưa có … tại {điểm đến}" + liên kết `/search?type=…`. Khối nào lỗi chỉ hiện "Chưa tải được · Thử lại" tại chỗ (frontend §8 quy tắc 2). Bật lại nút "Xem thêm" → `/search?type=…&destination=…`.

Thẻ sản phẩm: thêm `variant="tile"` vào `ProductCard.tsx` (ảnh vuông `aspect-square rounded-3xl`, tên, điểm đến, `PriceTag`), thay `ShelfCards` cục bộ của HomeView. Ảnh `loading="lazy" decoding="async"` và có tỉ lệ cố định để không nhảy layout; giữ `<img>` thường vì `next.config.ts` không khai `images.remotePatterns`. Không sao chép tên/giá/số liệu vào code; ảnh điểm đến trong `verticals.ts` là bản đồ tĩnh theo nhãn điểm đến, nhãn lạ dùng nền gradient.

**Tấm tìm kiếm** (`LandingSearchSheet`), trường theo cấu hình:

| Danh mục | Trường | Đích khi gửi |
|---|---|---|
| Lưu trú | Địa điểm (gợi ý từ `/destinations`, gõ tự do được) · Ngày đi – Ngày về · Phòng, người lớn, trẻ em | `/search?type=hotel&destination=&q=&checkIn=&checkOut=&rooms=&adults=&children=` |
| Di chuyển | Điểm đi (gõ tự do) · Điểm đến (gợi ý) · Ngày đi (+ Ngày về nếu chọn khứ hồi) · Hành khách | `/search?type=flight&…` |
| Tour và trải nghiệm | Điểm đến · Ngày sử dụng · Số khách | `/search?type=attraction|golf&…` |
| Tiện ích khác | Điểm đến · Ngày bắt đầu · Số khách | `/search?type=combo&…` |

Chọn gợi ý → `destination` chính xác; chỉ gõ tự do → vào `q`. `q` rỗng thì dùng `defaultQuery` của danh mục ("khách sạn", "vé máy bay", …) vì `search.ts` đang mặc định `'khách sạn'` cho mọi danh mục. Ngày mặc định là ngày mai theo giờ `Asia/Ho_Chi_Minh` (cùng cách `TravelContext.defaultUsingDate`), ngày quá khứ bị khóa; không cứng năm/tháng. Trên < 640 px các trường xếp dọc, popover ngày/khách thành bottom sheet.

Lịch chọn ngày hiện nằm rải trong HomeView (`parseDateStr`, `formatDateStr`, lưới tháng ~130 dòng); tách thành `DateRangePicker` dùng lại.

### 4. Home mới

`HomeView.tsx` viết lại còn khoảng 300 dòng, giữ nguyên hành vi K1/K2:

1. Hero: ô tìm kiếm AI (giữ, có tôn trọng `prefers-reduced-motion` cho hiệu ứng gõ chữ), chip gợi ý câu hỏi.
2. Bốn ô lối vào danh mục (icon + tên → `navConfig`); dưới 1024 px là `VerticalChips`.
3. ① Gợi ý cá nhân hóa (đã đăng nhập): giữ nguyên `fetchRecommendations`, `WhyPopover`, `because`, phụ thuộc `[currentPersona, activeEvents, recsRetry]`, để AC-REC-01/02 không đổi. Thêm timeout 3 giây theo `RECOMMENDATION_TIMEOUT_MS` (frontend §6.4).
4. ④ Một carousel "Phổ biến" có tab Tất cả · Khách sạn · Vé máy bay · Vé tham quan · Combo (đúng `product.md` §4.1.2), **chỉ tải tab đang chọn**, thay hai carousel hiện tại.
5. "Bạn muốn đi đâu?": từ `/destinations`, bấm → `/hotels?destination=…` (sửa lỗi toast nói dối).
6. Khối "Người bạn đồng hành đáng tin cậy": giữ.

Bỏ khỏi Home: form ngày/phòng dính đầu trang, hai danh sách cứng, "tìm kiếm gần đây" giả (lịch sử tìm kiếm thật, nếu làm, là việc riêng).

### 5. Chiến lược tải dữ liệu

Hai hook mới trong `src/frontend/src/hooks/` (thư mục có sẵn):

- `useInView(ref, { rootMargin: '300px', once: true })` bọc IntersectionObserver; không có IntersectionObserver (SSR, test) thì coi như đã vào vùng nhìn.
- `useLazySection(key, fetcher, { enabled, ttlMs = 60_000, timeoutMs? })`: bộ đệm `Map` theo `key`, gộp request đang bay, `AbortController` khi unmount, trả `{ items, loading, error, retry }`. `fetcher` luôn là hàm của `services/` (component không gọi `fetch`).

| Màn | Trước (đọc từ code) | Sau (mục tiêu) |
|---|---|---|
| Home, khách | 2 request khi mount | 0–1 khi tải (chỉ ④ nếu trong vùng nhìn); phần dưới chỉ tải khi cuộn tới ≤ 300 px |
| Home, đã đăng nhập | 3 | ≤ 2 (①, ④) |
| Mở menu header | — | `/destinations` 1 lần, dùng chung cache |
| Trang danh mục | — | 1 khi tải (khối 1); khối 2 và điểm đến khi vào vùng nhìn |

### 6. Ngữ cảnh chuyến đi qua URL

`src/frontend/src/features/search/tripContext.ts`: `parseTripContext(searchParams)` và `serializeTripContext(ctx)` cho `checkIn`, `checkOut` (`YYYY-MM-DD`), `adults`, `children`, `rooms`. Kiểm tra giá trị (ngày hợp lệ, không quá khứ, `checkOut > checkIn`, số nguyên trong khoảng 1–9 theo FR-BKG-08); giá trị sai bị bỏ im lặng.

- `SearchView.tsx`: đọc ngữ cảnh, hiện một chip tóm tắt ("15/10 – 17/10 · 1 phòng, 2 người lớn"), chuyển tiếp qua `ProductCard`.
- `ProductCard.tsx`: prop `tripQuery` nối vào `/product/{id}`.
- `ProductDetailView.tsx`: điền sẵn ngày/số khách nếu nằm trong `availableFrom`–`availableTo` của hạng phòng đang chọn, ngoài khoảng thì bỏ qua (Backend vẫn là nơi quyết định, `DATE_OUT_OF_RANGE`).

Đây là thêm query param cho `/product/{productId}` (hiện ghi "—" ở frontend §3): cập nhật bảng đó cùng thay đổi. Không đưa gì nhạy cảm vào URL (không họ tên, không token).

### 7. Giao diện, đáp ứng, tiếp cận

- Token và tiện ích mới chỉ đặt trong `src/app/globals.css` (Tailwind v4, không có `tailwind.config.ts`): `.glass-pill`, `.glass-sheet`, `.skeleton-wave`, bo `4xl`, `prefers-reduced-motion` tắt sóng skeleton và hiệu ứng gõ chữ.
- Kiểm ở 375, 768, 1024, 1440, 1920 px: không cuộn ngang trang; vùng chạm ≥ 44 px; carousel cuộn trong khung có scroll-snap; chữ trắng trên hero đạt tương phản ≥ 4.5:1 (lớp phủ 36% + viên kính); `:focus-visible` rõ trên nền kính.
- Footer: cột "Dịch vụ" trỏ đúng bốn route; không tạo thêm trang pháp lý giả. Liên kết pháp lý hiện `navigate('/')` là tồn đọng, liệt kê ở mục Rủi ro thay vì làm thêm liên kết chết.

## Cấu trúc file (đề xuất)

Code mới theo `docs/prd/architecture.md` §6.2 và `AGENTS.md` §3 (`features/` sở hữu nghiệp vụ, `components/` cho UI dùng chung). File cũ sửa tại chỗ, không di chuyển (nhất quán quyết định ở `history/2026-09-25-trang-chi-tiet-san-pham-that-va-chon-hang-phong.md`).

```
src/frontend/src/
├── app/(storefront)/{hotels,flights,experiences,combos}/page.tsx   # chỉ ghép <VerticalLandingPage vertical="…"/>
├── features/catalog/landing/
│   ├── verticals.ts  VerticalLanding.tsx  LandingHero.tsx  LandingSearchSheet.tsx
│   ├── DateRangePicker.tsx  GuestsPopover.tsx  LocationField.tsx
│   └── ProductShelf.tsx  DestinationTiles.tsx  PromoBanner.tsx
├── features/search/tripContext.ts
├── components/layout/nav/{navConfig.ts,NavMenu.tsx,AllServicesMenu.tsx,VerticalChips.tsx}
├── hooks/{useInView.ts,useLazySection.ts}
└── (sửa) components/common/{Header,ProductCard,Footer}.tsx · components/layout/AppShell.tsx
        components/home/HomeView.tsx · components/search/SearchView.tsx
        components/detail/ProductDetailView.tsx · app/globals.css
```

Tái sử dụng, không viết lại: `listProducts`, `productFromApi`, `PLACEHOLDER_IMAGE` (`services/catalog.ts`); `listDestinations` (`services/destinations.ts`); `fetchRecommendations` (`services/recsys.ts`); `ProductCard`, `PriceTag`, `TaxonomyBadge`, `WhyPopover`; `useTravel` (`navigate`, `currentRoute`, `cartCount`, `openLoginModal`); tham số `type|taxonomy`, `q`, `destination` mà `SearchView` đã đọc.

## Các bước thực hiện

Mỗi bước một entry `history/` và một commit; không gộp.

| # | Bước | Gác PRD | Trạng thái |
|---|---|---|---|
| P0 | Xác nhận theo `AGENTS.md` §1.3; đọc docs Next 16 (`Link`); đo baseline; tạo đề xuất PRD route; chốt A1–A6 | — | Xong (2026-09-29): người dùng chốt A1–A6 và đề xuất PRD; đề xuất đã áp dụng vào `user-flow.md` và nằm ở `update-archive/` |
| P1 | Nền chung: `globals.css`, `useInView`, `useLazySection`, `tripContext`, `navConfig`, `verticals` + unit test | Không | Xong |
| P2 | Header: menu nhóm, nút "Tất cả dịch vụ", overlay/solid, viên Trợ lý AI, bỏ chuông/V-Points, `VerticalChips` | Không | Xong |
| P3 | Home bớt request | Không | Xong, gộp làm cùng P5 (đề xuất PRD đã chốt nên không cần giữ form khách sạn trên Home) |
| P4 | Bốn trang danh mục + tấm tìm kiếm + `DateRangePicker`; ngữ cảnh chuyến đi; "Xem thêm" | Đã chốt | Xong |
| P5 | Home hoàn thiện (bốn ô danh mục, tab phổ biến, điểm đến), Footer, `user-flow.md`, spec, README | Đã chốt | Xong |
| P6 | Kiểm thử, đo lại request, đáp ứng và tiếp cận, `history/` | — | Xong phần tự động và đo bằng script; **chờ nghiệm thu bằng mắt của người dùng** (AC-REC-01/02 cần Backend + seed) |

P1–P3 không cần đợi PRD. Nếu đề xuất route bị từ chối: P4 đổi thành trang `/search?type=…` có chế độ "duyệt" (hero + tấm tìm kiếm khi chưa có `q`), phần còn lại giữ nguyên vì `navConfig` là điểm đổi duy nhất.

**Nội dung đề xuất PRD (tạo ở P0, theo mẫu `AGENTS.md` §8):** `docs/prd/user-flow.md` §2 thêm bốn dòng vào bảng route: `/hotels` (Khách sạn & resort), `/flights` (Vé máy bay), `/experiences` (Tour và trải nghiệm; `?type=attraction|golf`), `/combos` (Combo du lịch); mỗi route công khai, nhận `destination`; và §4.1 chỉnh thanh điều hướng wireframe thành bốn nhóm + "Trợ lý AI". Lý do: "duyệt danh mục" đã trong phạm vi (`project-brief.md` §4.1) nhưng bảng route chưa liệt kê các trang này.

## Kiểm thử và nghiệm thu

Chạy từ `src/frontend`: `npm run typecheck`, `npm run lint`, `npm run test:unit`, `npm run test:e2e` (build rồi Playwright). Không đổi contract hay mock nên không cần `validate_contract.py`; nếu phát sinh đổi contract (ví dụ thêm `taxonomy` cho `/destinations`) thì dừng và xin xác nhận trước.

**Unit (vitest + Testing Library):**
- `navConfig`: suy ra nhóm đang chọn từ `pathname` + `type`; không nhóm nào ở `/`.
- `NavMenu`: mở/đóng bằng chuột, Enter/Space, Esc trả focus, bấm ngoài, `aria-expanded`; `/destinations` chỉ gọi lần mở đầu.
- `useLazySection`: không gọi `fetcher` trước khi vào vùng nhìn (giả lập IntersectionObserver), gộp request trùng, hủy khi unmount, hết hạn bộ đệm.
- `VerticalLanding`: đúng `taxonomy`/`sort` mỗi khối; trạng thái skeleton/lỗi/rỗng; không có tên hay số liệu sản phẩm cứng trong DOM.
- `LandingSearchSheet`: đúng URL đích cho từng danh mục; `q` rỗng dùng `defaultQuery`; chặn ngày quá khứ, `checkOut ≤ checkIn`.
- `tripContext`: parse/serialize, bỏ giá trị sai.
- `HomeView`: khách không gọi `/recommendations`; đã đăng nhập gọi đúng một lần; không gọi khối dưới màn hình khi chưa cuộn.

**E2E (Playwright, chặn mạng bằng `page.route('**/api/v1/**')`):** mở `/` đếm request đúng ngân sách ở §5; đi qua bốn nhóm trên header bằng bàn phím tới đúng trang; gửi tấm tìm kiếm tới `/search` đúng tham số và ngày xuất hiện ở hộp đặt; viewport 375 px không cuộn ngang. Các spec hiện có (`routes.spec.ts`, `widget-opening.spec.ts`) phải vẫn pass.

**Nghiệm thu bằng tay** (`make web` ở gốc repo, DevTools → Network lọc `/api/v1/`): AC-REC-01 (P1 thấy khối gợi ý kèm `because`), AC-REC-02 (sau khi đặt phòng, Home ưu tiên vé máy bay cùng điểm đến), bốn trang danh mục ở 5 độ rộng, tô đậm nhóm đúng route.

## Tài liệu cập nhật cùng thay đổi

- `docs/prd/user-flow.md` §2, §4.1 — chỉ sau khi đề xuất PRD được chốt (`AGENTS.md` §8 bước 3), rồi chuyển đề xuất sang `docs/prd/update-archive/`.
- `docs/spec/hop-dong-tich-hop-frontend.md`: §3 (bốn route, query param của `/product/{id}`), §4.1 (Home: hai carousel → một carousel có tab; thêm mục "Trang danh mục" theo mẫu ma trận màn hình → endpoint → trường).
- `docs/spec/product.md`: §3.1 bảng route, §3.3 điều hướng toàn cục (theo wireframe PRD: bốn nhóm + Trợ lý AI thay cho ô tìm kiếm giữa header), §4.1, §4.2.1 (bổ sung tấm tìm kiếm có ngày/số khách ở trang danh mục; ô tự do vẫn là chính ở Home và `/search`), §7.2.
- `src/frontend/README.md`: cấu trúc `features/catalog/landing`, cách thêm một danh mục vào `verticals.ts`.
- `history/`: một entry cho lần lưu plan, mỗi bước P1–P6 một entry.

## Rủi ro và việc chưa rõ

- **Sắp xếp giá.** Cha khách sạn/tuyến bay có thể có `unitPrice: null` (`types/travel.ts`); chưa xác nhận `sort=price_asc` xếp `null` ở đâu. Xác nhận bằng một lần gọi thật ở P0; nếu `null` đứng đầu thì lọc `unitPrice != null` phía client cho khối "Giá tốt nhất" và ghi vào entry.
- **`/destinations` không có ảnh và không tách theo danh mục.** `productCount` gộp mọi danh mục, nên chip ở `/flights?destination=X` có thể rỗng: đã có EmptyState. Muốn chip đúng theo danh mục cần thêm tham số `taxonomy` vào contract, để lại làm việc riêng.
- **Dữ liệu chưa có kiểm chứng:** hai khối 2 trên `/experiences` (golf) và `/combos` phụ thuộc số sản phẩm của catalog hiện tại; khối nào < 3 thẻ thì ẩn (`MIN_CARDS_FOR_CAROUSEL`, frontend §6.4).
- **Ảnh hero, ảnh điểm đến.** Hiện dùng URL Unsplash như code cũ; nên chuyển về `public/` khi có ảnh được cấp phép. Không dùng ảnh của mẫu.
- **Hiệu năng thật của API.** `/search` ~2 giây, `/similar` 0,6–1,1 giây theo `history/2026-09-25-trang-chi-tiet-san-pham-that-va-chon-hang-phong.md`; tấm tìm kiếm chỉ điều hướng nên không chịu ảnh hưởng, nhưng `/products` chưa đo trên staging.
- **Tồn đọng, không xử lý ở đây:** liên kết pháp lý/hỗ trợ ở Footer đều trỏ `/`; `docs/spec/product.md` §1.5 (bảng tình trạng 21/09) đã cũ; `docs/prd/user-flow.md` ghi `/products/:id` trong khi route thật là `/product/{id}` và bị lặp §4.2–§4.4.
- **Bộ tài liệu API/backend chưa đọc** (`contracts-guide.md`, `api-contract.md`, `hop-dong-tich-hop-backend.md`) vì plan không đổi API; phải đọc trước nếu phạm vi đổi.

## Căn cứ đã đọc (`AGENTS.md` §1.3)

`AGENTS.md`, `docs/prd/README.md`, `docs/prd/requirements.md` §1–§3, `docs/prd/user-flow.md`, `docs/prd/architecture.md` §6, `docs/prd/project-brief.md` §4, `docs/spec/hop-dong-tich-hop-frontend.md` §1–§9, `docs/spec/product.md` §0–§4.4, §5.3, §7, `docs/spec/architecture-repo.md` §6, `src/frontend/README.md` và `AGENTS.md`; `docs/prd/update/` (hai đề xuất đang chờ đều thuộc trợ lý, không chạm phạm vi này); `src/shared/contracts` (`paths/catalog.yaml`, `Taxonomy`, `ProductSort`, `ProductSummary`, `SearchRequest`, `TravelContext`); mã `HomeView`, `Header`, `AppShell`, `MobileTabBar`, `Footer`, `ProductCard`, `SearchView`, `TravelContext`, `services/{catalog,destinations,search}`. `history/`: README, 10 entry mới nhất, và các entry từng chạm Home/Header (`2026-09-17-home-search-assistant`, `2026-09-21-homeview-recommend-api`, `2026-09-21-home-buttons-webp`, `2026-09-21-setup-destination-carousel-columns`, `2026-09-24-noi-vong-dat-cho-goi-y-k1`, `2026-09-24-go-bo-tai-khoan-demo`, `2026-09-25-trang-chi-tiet-san-pham-that-va-chon-hang-phong`). Không có entry `dang dở` nào thuộc phạm vi UI (`2026-09-28-frontend-vm-deploy` là hạ tầng deploy).

## Kết quả triển khai (2026-09-29)

- **Request của Home** (khách, 1440 px, đo bằng Playwright trên dev server): trước 2 request danh mục khi tải (4 ở dev do React StrictMode gọi hai lần) + 1 phiên; sau **1** request danh mục, `/destinations` chỉ khi cuộn tới. `/hotels`: 2 khối sản phẩm + phiên khi tải, `/destinations` khi cuộn.
- **Khác với plan:** (1) `AllServicesMenu` nằm chung file `NavMenu.tsx`; (2) `useLazySection` không hủy request khi unmount (kết quả vẫn vào bộ đệm), thay cho "hủy khi unmount"; (3) `sort=price_asc` không cần lọc `null` phía client vì Backend đã xếp sản phẩm chưa có giá xuống cuối (`domain/catalog/listing.py`); (4) `DEFAULT_QUERY` đặt ở `services/search.ts`, sửa luôn lỗi `/search?type=flight` không có `q` tìm "khách sạn"; (5) trang danh mục đọc query ở Server Component (`searchParams`) thay vì `useSearchParams` để hero có sẵn trong HTML; (6) header mobile ẩn chữ V-OTA và mã tiền tệ để không tràn ngang ở 375 px; (7) menu tài khoản bỏ dòng "Ưu đãi thành viên V-OTA Silver" và V-Points (nội dung bịa), giữ "Hồ sơ cá nhân", "Cài đặt".
- **Chưa làm / còn lại:** liên kết pháp lý ở Footer vẫn trỏ `/`; ảnh hero và ảnh điểm đến vẫn là URL Unsplash (ảnh "Nha Trang" cũ trông không đúng địa điểm); chưa chạy `npm run test:e2e` chuẩn (môi trường không có `npm` trong PATH và build sẽ ghi đè `.next` của dev server đang chạy); các spec e2e mới và cũ đã chạy bằng Playwright trỏ vào dev server.
