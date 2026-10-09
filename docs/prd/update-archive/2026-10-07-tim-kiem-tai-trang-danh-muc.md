# Tìm kiếm ngay tại trang danh mục: Khách sạn, Tour và trải nghiệm, Combo

- Ngày: 2026-10-07
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-07 ("tôi chốt" sau khi xem đề xuất)
- PRD bị ảnh hưởng: `docs/prd/user-flow.md` §2 (bảng route, dòng `/hotels`, `/experiences`, `/combos`), §3.1 (luồng tìm kiếm); `docs/prd/requirements.md` §1.2 FR-SRC-03
- Mã FR/NFR: FR-SRC-01, FR-SRC-03, FR-CAT-01; không đổi AC. AC-SRC-01 và AC-SRC-02 vẫn đúng vì `/search` giữ nguyên.

## Lý do

Hiện bấm Tìm ở tấm tìm kiếm của `/hotels`, `/experiences` và `/combos` đều chuyển sang `/search`, trang kết quả gộp có tab Tất cả · Lưu trú · Tour và trải nghiệm · Tiện ích khác. Người dùng đã chọn một mục mà vẫn bị đưa sang trang gộp. Người dùng muốn mỗi mục hiện kết quả ngay tại trang của mình, giống `/flights` (đề xuất đã áp dụng `update-archive/2026-09-30-trang-ve-may-bay-tim-tai-cho-bo-khoi-pho-bien-va-gia-tot.md`).

Trang `/search` giữ nguyên cho tìm tự do (ô tìm ở trang chủ, gợi ý tức thì của FR-SRC-05, thanh tab điện thoại, liên kết "Xem tất cả kết quả cho …"), vì câu tìm tự do chưa biết trước loại dịch vụ. Bản xem trước giao diện: https://claude.ai/artifact/1TW1CyUAmGzAn4sSCHfMse (người dùng đã duyệt giao diện ngày 2026-10-07).

## Nội dung đề xuất

**1. `docs/prd/user-flow.md` §2, ba dòng `/hotels`, `/experiences`, `/combos`.**

- `/hotels`
  - Mục đích hiện tại: "Duyệt và bắt đầu tìm khách sạn theo điểm đến, ngày, số phòng và số khách".
  - Thay bằng: "Duyệt và tìm khách sạn theo điểm đến, ngày, số phòng và số khách; kết quả hiện ngay dưới tấm tìm kiếm".
  - Thành phần hiện tại: "Hero, Search Sheet, Product Shelves (phổ biến, giá tốt), Destination Tiles".
  - Thay bằng: "Hero, Search Sheet, Kết quả tìm kiếm (Filter Sidebar hạng sao và giá, Sort popup, Product Row Cards, Xem thêm) khi đã tìm; chưa tìm thì Product Shelves (phổ biến, giá tốt), Destination Tiles".
- `/experiences`
  - Mục đích hiện tại: "Duyệt vé tham quan, vui chơi và sân golf (`?type=attraction|golf`)".
  - Thay bằng: "Duyệt và tìm vé tham quan, vui chơi và sân golf (`?type=attraction|golf`); kết quả hiện ngay dưới tấm tìm kiếm, chỉ trong tab đang chọn".
  - Thành phần: như `/hotels`, thêm Tab loại, không có Filter Sidebar.
- `/combos`
  - Mục đích hiện tại: "Duyệt gói kết hợp".
  - Thay bằng: "Duyệt và tìm gói kết hợp; kết quả hiện ngay dưới tấm tìm kiếm".
  - Thành phần: như `/experiences`, không có Tab loại.
- Dòng `/search`: không đổi.

Khi đã tìm, hai khối Product Shelves, Destination Tiles và banner trợ lý ẩn đi, giống `/flights`. Có `?q=` trên URL là đang tìm; không có `?q=` là trang danh mục như hiện nay (các liên kết `?destination=` từ ô điểm đến nổi bật và menu vẫn mở trang danh mục).

**2. `docs/prd/user-flow.md` §3.1.** Thêm nhánh vào sơ đồ: "Người dùng ở trang danh mục (`/hotels`, `/experiences`, `/combos`) → nhập điểm đến, ngày, số khách → Tìm → kết quả hiện ngay tại trang đó (cùng URL, thêm `?q=`) → chọn sản phẩm → mở `/products/:id`". Các nhánh hiện có đi qua `/search` giữ nguyên.

**3. `docs/prd/requirements.md` FR-SRC-03, gạch đầu dòng "Địa điểm".**

- Hiện tại: "…áp dụng ở API `/search` và ở tấm tìm kiếm của trang danh mục. Trang `/search` không có bộ lọc điểm đến; điểm đến do câu truy vấn ngữ nghĩa quyết định. Vé máy bay không nằm trong kết quả `/search` (chỉ duyệt và tìm ở `/flights`)."
- Thay bằng: "…áp dụng ở API `/search` và ở tấm tìm kiếm của trang danh mục; tấm này hiện kết quả ngay tại trang danh mục đó, chỉ trong loại dịch vụ của trang (và của tab đang chọn ở `/experiences`). Trang `/search` không có bộ lọc điểm đến; điểm đến do câu truy vấn ngữ nghĩa quyết định. Vé máy bay không nằm trong kết quả `/search` (chỉ duyệt và tìm ở `/flights`)."

Không đổi: các FR/NFR/AC khác, API `POST /search` và `GET /products`, contract OpenAPI, DDL, backend. Ngày và số khách vẫn chỉ là ngữ cảnh điền sẵn cho trang chi tiết, không lọc phòng trống (Backend chưa lọc theo ngày). Băng "kết quả yếu" (`topScore < 0.35`) chỉ có ở `/search`, không đưa sang trang danh mục trong đợt này.

## Thay đổi source sau khi chốt

- `src/frontend/src/features/catalog/landing/searchHref.ts`: `buildSearchHref` trỏ về route của danh mục (trừ vé máy bay) thay cho `/search`.
- `src/frontend/src/features/catalog/landing/LandingResults.tsx` (mới), `VerticalLanding.tsx`, `LandingSearchSheet.tsx`, `LandingHero.tsx`: hiện kết quả tại trang, điền sẵn tấm tìm kiếm từ URL.
- `src/frontend/src/components/search/GroupResults.tsx`, `src/frontend/src/services/search.ts`: thu hẹp về một taxonomy cho tab ở `/experiences`.
- `src/frontend/src/app/(storefront)/{hotels,experiences,combos}/page.tsx`: đọc `q` và ngữ cảnh chuyến đi.
- Test: `tests/unit/{searchHref,landingSearchSheet,verticalLanding,searchService}.test.*`, mới `landingResults.test.tsx`; e2e `navigation.spec.ts`, `routes.spec.ts`.
- Tài liệu: `docs/spec/hop-dong-tich-hop-frontend.md` §3, §4.1a, §4.2; `docs/spec/product.md` §4.2.1; `src/frontend/README.md`.
