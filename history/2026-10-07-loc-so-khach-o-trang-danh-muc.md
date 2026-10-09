# Số khách ở tấm tìm kiếm trang danh mục thành bộ lọc sức chứa

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Người dùng yêu cầu những gì điền ở tấm tìm kiếm của `/hotels`, `/experiences`, `/combos` phải là tiêu chí tìm. Số khách: Backend đã có sẵn `travelContext.guests` (contract 1.16.0, bộ lọc cứng sức chứa) nhưng frontend chưa gửi. Phần ngày cần backend và đề xuất PRD, xem `history/2026-10-07-de-xuat-loc-theo-ngay-o-tim-kiem.md` (chờ chốt). Số khách không lệch PRD (FR-SRC-03, FR-BKG-08).

## File thay đổi

- `src/frontend/src/services/search.ts` — sửa: `SearchFilters.guests`, `searchProductsApi` gửi `travelContext.guests`, `searchGroupApi` nhận `guests`, `searchCacheKey` thêm `guests`.
- `src/frontend/src/components/search/GroupResults.tsx` — sửa: prop `guests`, vào khóa bộ đệm và dependency của effect.
- `src/frontend/src/features/catalog/landing/LandingResults.tsx` — sửa: `guestsOf(trip)` đổi số người lớn, trẻ em, số phòng thành `guests` một phòng.
- `src/frontend/src/features/catalog/landing/LandingSearchSheet.tsx` — sửa: chú thích.
- `src/frontend/tests/unit/{landingResults,searchService}.test.*` — sửa: test gửi `guests`, không gửi khi thiếu, chia theo phòng, khóa bộ đệm.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§4.1a), `docs/spec/product.md`, `src/frontend/README.md` — sửa: mô tả số khách là bộ lọc, ngày vẫn chưa.
- `history/2026-10-07-loc-so-khach-o-trang-danh-muc.md` — thêm: entry này.

## Quyết định

- Backend so tổng `adults + children` với sức chứa của một hạng phòng, nên nhiều phòng thì gửi số khách chia đều làm tròn lên thay vì cả đoàn (4 người, 2 phòng gửi 2). Chia đều là xấp xỉ: đoàn 3 người lớn 1 trẻ em ở 2 phòng có thể xếp 3+1 nhưng gửi 2.
- Chỉ trang danh mục gửi `guests`; `/search` giữ nguyên.
- Không có số người lớn trên URL thì không gửi.

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 62 file, 659 test pass. `tsc --noEmit`: sạch.
- Backend thật (:8000), `POST /search` khách sạn Nha Trang: `guests` 2 người trả 109 kết quả, 9 người trả 25; `appliedFilters.hard.minOccupancy` khớp.
- Chưa kiểm trên giao diện sau thay đổi này; `playwright` không chạy lại.

## Còn lại / rủi ro

- Ngày chưa lọc, chờ mihhquan chốt đề xuất `docs/prd/update/2026-10-07-loc-theo-ngay-o-tim-kiem.md`.
- Sản phẩm chưa khai sức chứa (một số khách sạn và mọi vé, combo) vẫn được giữ, nên số khách không loại chúng.
