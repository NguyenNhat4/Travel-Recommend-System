# Tìm kiếm ngay tại trang danh mục (Khách sạn, Tour và trải nghiệm, Combo)

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Bấm Tìm ở tấm tìm kiếm của `/hotels`, `/experiences`, `/combos` không còn chuyển sang trang gộp `/search`; kết quả hiện ngay dưới tấm tìm kiếm, trong đúng loại dịch vụ của trang (như `/flights`). `/search` giữ nguyên cho tìm tự do (trang chủ, gợi ý tức thì, thanh tab điện thoại). Thay entry đề xuất: `2026-10-07-de-xuat-tim-kiem-tai-trang-danh-muc.md` (đã chốt 2026-10-07).

Mã yêu cầu: FR-SRC-01, FR-SRC-03, FR-CAT-01. Không đổi AC.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-SRC-03, tấm tìm kiếm hiện kết quả tại trang danh mục.
- `docs/prd/user-flow.md` — sửa: §2 ba dòng `/hotels`, `/experiences`, `/combos`; §3.1 thêm nhánh tìm tại trang danh mục.
- `docs/prd/update-archive/2026-10-07-tim-kiem-tai-trang-danh-muc.md` — thêm (đổi tên từ `docs/prd/update/`): đề xuất, trạng thái đã áp dụng.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §3 query `q` và ngữ cảnh chuyến đi cho ba route, §4.1a thêm "Tìm tại chỗ" và hàng "Kết quả tìm kiếm", §4.2.
- `docs/spec/product.md` — sửa: bảng route và §4.2.1.
- `src/frontend/README.md` — sửa: mô tả trang danh mục và `/search`.
- `src/frontend/src/features/catalog/landing/searchHref.ts` — sửa: `buildSearchHref` trỏ về route của danh mục (vé máy bay vẫn `/search`), thêm `isDefaultQuery`.
- `src/frontend/src/features/catalog/landing/LandingResults.tsx` — thêm: khối kết quả dưới hero, dùng `GroupResults`.
- `src/frontend/src/features/catalog/landing/VerticalLanding.tsx` — sửa: nhận `query`, `trip`; có `?q=` thì hero thu gọn và hiện kết quả thay các khối.
- `src/frontend/src/features/catalog/landing/LandingHero.tsx`, `LandingSearchSheet.tsx` — sửa: điền sẵn từ URL (chữ tự do, ngày, số khách, số phòng); ô địa điểm theo `?q=` khi đổi.
- `src/frontend/src/components/search/GroupResults.tsx` — sửa: thêm prop `taxonomy`, `label`, `embedded` (mặc định giữ nguyên hành vi ở `/search`).
- `src/frontend/src/services/search.ts` — sửa: `searchGroupApi` nhận `taxonomy`, `searchCacheKey` thêm `taxonomy`.
- `src/frontend/src/app/(storefront)/{hotels,experiences,combos}/page.tsx` — sửa: đọc `q` và ngữ cảnh chuyến đi.
- `src/frontend/tests/unit/{searchHref,landingSearchSheet,searchService}.test.*` — sửa; `landingResults.test.tsx` — thêm.
- `src/frontend/tests/e2e/navigation.spec.ts`, `routes.spec.ts` — sửa: viết lại test tấm tìm kiếm khách sạn, thêm test mở thẳng `/hotels?q=…` và ba route smoke.
- `history/2026-10-07-tim-kiem-tai-trang-danh-muc.md` — thêm: entry này.

## Quyết định

- Có `?q=` là đang tìm; không có là landing, nên liên kết `?destination=` từ ô điểm đến nổi bật và menu không đổi.
- `/experiences` tìm theo tab: chỉ `attraction` hoặc chỉ `golf`, không trộn cả nhóm.
- Không đổi contract, DDL, backend: `POST /search` đã lọc theo `taxonomy` và `destination`.
- Băng "kết quả yếu" chỉ có ở `/search`, chưa đưa sang trang danh mục.
- Bản xem trước giao diện (ngoài repo): https://claude.ai/artifact/1TW1CyUAmGzAn4sSCHfMse.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 62 file, 655 test pass.
- `node_modules/.bin/tsc --noEmit`: sạch. `node_modules/.bin/eslint .`: 0 lỗi, 2 cảnh báo cũ ở `ItineraryMap.tsx` (không đụng tới).
- Playwright vào dev server `localhost:3000` (config tạm, đã xoá): `navigation.spec.ts` và `routes.spec.ts` pass (24 test ở lượt đầu; hai test sửa sau đó pass lại).
- Trình duyệt thật với backend thật (:8000): `/hotels` chọn Nha Trang + Tìm → ở lại `/hotels?q=…&destination=Nha+Trang&…`, có danh sách và bộ lọc sao/giá; `/experiences?q=sân golf&type=golf` ra sân golf, không có bộ lọc khách sạn. Tìm kiếm thật mất vài giây ở lượt đầu.
- Chưa chạy `npm run test:e2e` bản đầy đủ (máy không có `npm`, bản đó build và chạy server riêng ở cổng 3100). Không đổi contract nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Tấm tìm kiếm giữ giá trị người dùng đã gõ khi URL đổi bằng nút Back; chỉ điền sẵn lúc mở trang.
- Đổi tab ở `/experiences` khi đang tìm quay về landing của tab kia (giữ `destination`), như hiện nay.
- Ngày và số khách vẫn chỉ là ngữ cảnh điền sẵn, không lọc phòng trống (Backend chưa lọc theo ngày).
