# Trang /search: tab theo nhóm, hàng cuộn ngang, sắp xếp popup, bỏ điểm đến và vé máy bay

- Ngày: 2026-09-30
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (chưa chạy e2e với backend thật; xem Còn lại)
- Phạm vi: frontend, docs
- Thay thế: `2026-09-30-de-xuat-search-bo-diem-den-ve-may-bay-tab-nhom.md` (đề xuất đã được chốt và áp dụng)

## Mục tiêu

Sửa `/search` (tìm kiếm ngữ nghĩa) theo đề xuất `docs/prd/update-archive/2026-09-30-trang-search-bo-diem-den-ve-may-bay-va-tab-theo-nhom.md`, mihhquan chốt ngày 2026-09-30 sau khi xem bản mẫu giao diện: bỏ lọc điểm đến, bỏ vé máy bay, tab Tất cả · Lưu trú · Tour và trải nghiệm · Tiện ích khác, "Tất cả" là các hàng cuộn ngang chỉ lấy vài mục và có cache, sắp xếp là popup ở mọi tab trừ Tất cả. Phục vụ FR-SRC-01, FR-SRC-03.

## File thay đổi

PRD (cập nhật trước khi sửa source):
- `docs/prd/requirements.md` — sửa: FR-SRC-03 mục Địa điểm.
- `docs/prd/user-flow.md` — sửa: dòng `/search` ở bảng route.
- `docs/prd/update-archive/2026-09-30-trang-search-bo-diem-den-ve-may-bay-va-tab-theo-nhom.md` — thêm: đề xuất, trạng thái `đã áp dụng`, chốt bởi mihhquan 2026-09-30 (chuyển từ `update/`).

Spec/docs:
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §3 dòng `/search` (tham số `type`), §4.2 viết lại (tab nhóm, tải nhanh, cache, nút cuộn, popup sắp xếp).
- `docs/spec/product.md` — sửa: §4.2.2 wireframe và §4.2.3 (tab, bộ lọc, sắp xếp).
- `src/frontend/README.md` — sửa: thêm đoạn `/search`.

Frontend:
- `src/frontend/src/services/search.ts` — sửa: thêm nhóm (`SEARCH_GROUPS`, `TAB_GROUPS`, `parseGroupParam`), `searchGroupApi`, `searchOverviewApi`, `viewItems`, `searchCacheKey`, `PREVIEW_LIMIT` = 6, `GROUP_PAGE_SIZE` = 20. `searchProductsApi` giữ nguyên.
- `src/frontend/src/hooks/useLazySection.ts` — sửa: thêm `loadSection` (không phải hook, dùng bộ đệm chung) cho danh sách nối trang.
- `src/frontend/src/components/search/SearchView.tsx` — sửa: viết lại (tab nhóm, số kết quả từ `searchOverviewApi`, chế độ `type=flight`, chip điểm đến có ✕).
- `src/frontend/src/components/search/GroupShelf.tsx` — thêm: hàng cuộn ngang của tab Tất cả, tải lười, thẻ "Còn N kết quả".
- `src/frontend/src/components/search/GroupResults.tsx` — thêm: danh sách đầy đủ của một nhóm, "Xem thêm", thanh bên chỉ ở Lưu trú.
- `src/frontend/src/components/search/HScroller.tsx` — thêm: hàng cuộn có nút trái/phải giữa hai bên, ẩn ở đầu/cuối (`scrollEdges`).
- `src/frontend/src/components/search/SortMenu.tsx` — thêm: popup sắp xếp.
- `src/frontend/src/components/search/SearchAssistantBanner.tsx` — thêm: tách thẻ mời trợ lý ra khỏi SearchView.
- `src/frontend/src/components/common/SearchBox.tsx` — sửa: gợi ý mặc định bỏ "Vé máy bay Hà Nội - Đà Nẵng", thay bằng "Sân golf nghỉ dưỡng".
- `src/frontend/tests/unit/searchService.test.ts` — sửa: thêm ca cho nhóm, tổng hợp số tab, `viewItems`, khóa cache.
- `src/frontend/tests/unit/searchView.test.tsx` — thêm: `scrollEdges`, `SortMenu`, `SearchView` (Tất cả, tab nhóm, cache "Xem thêm", chế độ flight, chip điểm đến).

- Bổ sung sau yêu cầu của mihhquan: bỏ chip "Chuyến đi: ngày · số khách" khỏi đầu `/search` (`SearchView.tsx`, spec frontend §4.1a). Chip chỉ có trong spec/code, PRD không nhắc nên không cần đề xuất. Ngữ cảnh vẫn đi theo liên kết tới trang chi tiết để điền sẵn hộp đặt.

## Quyết định

- Không đổi contract: contract chỉ nhận một `taxonomy` mỗi request, nên mỗi nhóm là một request cho mỗi taxonomy (Tour và trải nghiệm = attraction + golf, trộn theo `score`). Số tab lấy từ một request không lọc taxonomy, `limit: 1`, đọc `facets.taxonomy` (facets đổi theo taxonomy nên không dùng response của tab để đếm).
- Cache dùng lại `useLazySection` (60 giây, gộp request đang bay, xóa khi đổi tài khoản) thay vì viết bộ đệm mới.
- Backend `/search` hiện không nhận `sort`, giá, sao (`routes/search.py`) nên sắp xếp và lọc vẫn chạy client trên các mục đã tải, như trước.
- `?type=` nhận cả taxonomy cũ (`hotel`, `attraction`, `golf`, `combo`) để tấm tìm kiếm trang danh mục và `tests/e2e/routes.spec.ts` không phải đổi. `type=flight` là ngoại lệ đã chốt (danh sách phẳng, không tab).
- Sắp xếp giá có ở cả Tour và Tiện ích khác (mihhquan yêu cầu popup cho mọi tab trừ Tất cả), khác nháp đầu của đề xuất.

## Kiểm tra

- `./node_modules/.bin/tsc --noEmit`: sạch.
- `./node_modules/.bin/eslint .`: 0 lỗi, 2 cảnh báo có sẵn (`ItineraryMap`).
- `./node_modules/.bin/vitest run`: 44 file, 431 test pass.
- Không đổi contract/mock nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Chưa chạy Playwright và chưa xem bằng mắt với backend thật (`make web`); cần người dùng xem `/search?q=Nha+Trang` ở 1440 px và 375 px.
- Cache 60 giây: tìm lại cùng câu trong 60 giây không sinh thêm event `search` ở backend.
- Nhóm Tour và trải nghiệm phân trang bằng cùng `offset` cho cả attraction và golf, thứ tự trong trang theo `score`, không theo RRF của backend.
- `searchProductsApi` vẫn còn `categoryCounts.flight`; không dùng ở `/search` mới nhưng chưa gỡ để không đổi hợp đồng hàm.
