# Trang /search: số trên tab, hàng và "Xem thêm" lấy từ cùng một nguồn; lọc sao/giá gửi lên API; bỏ dấu "+"

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/search-count
- Trạng thái: hoàn thành (chưa xem trên trình duyệt với backend thật; xem "Còn lại")
- Phạm vi: frontend, docs
- Thay thế: quyết định "Số tab lấy từ một request không lọc taxonomy, `limit: 1`, đọc `facets.taxonomy`" và "lọc sao/giá chạy client" trong `2026-09-30-search-tab-nhom-hang-cuon-ngang.md`

## Mục tiêu

Sau khi tìm ở `/search`, các số trên trang không khớp nhau. Ví dụ câu "Nha Trang" trên backend local ngày 12/10: tab ghi Tất cả 14 / Lưu trú 9 / Tour 5 / Tiện ích khác 0, trong khi các hàng ghi 13 / 12 / 9 kết quả. Hàng Tiện ích khác vẫn hiện 9 combo dù tab ghi 0. Thêm hai chỗ lệch khác:
- Lọc sao/giá chạy trên trình duyệt: danh sách ngắn lại nhưng "Xem thêm (20/42)" vẫn giữ số cũ.
- Đầu trang luôn hiện "N+" trong khi tab ghi "(N)".

Người dùng chọn phương án A + D + E (bỏ hẳn "+"). Phục vụ FR-SRC-03 (lọc loại, giá, sao) và FR-SRC-04 (trang rỗng). Không đổi AC.

Nguyên nhân: backend tính tập kết quả R trên tập đã lọc của **từng** request (top-K dense, `lexicalK` = 10 suất vớt BM25; hợp đồng Search §2.2):
- Request không lọc taxonomy có 10 suất vớt dùng chung cho mọi loại. Vé máy bay chiếm suất nhưng Web lại bỏ số của vé máy bay.
- Request lọc theo loại có 10 suất riêng cho loại đó.

Vì vậy `facets.taxonomy[t]` của request tổng quan thường nhỏ hơn `total` của request `taxonomy = t`. Đo ngày 12/10: câu không có hit được vớt ("khách sạn Hà Nội") thì khớp tuyệt đối; câu có hit vớt ("Nha Trang", "Đà Nẵng", "VinWonders Phú Quốc") thì lệch.

## File thay đổi

- `src/frontend/src/services/search.ts` — sửa:
  - Đếm và lọc:
    - `searchOverviewApi` đếm tab bằng `total` của các request hàng, cùng khóa `shelfCacheKey` và nhận `SectionLoader`. Bỏ request không lọc taxonomy.
    - `searchProductsApi` gửi `priceMin`/`priceMax`/`starRatingMin`, bỏ lọc trên trang.
    - `searchGroupApi` nhận `maxPrice`/`minStarRating` và trả `topScore`.
  - Thêm `shelfCacheKey`, `searchShelfApi`, `PriceStarFilter`, `SectionLoader`; `searchCacheKey` có thêm tham số bộ lọc.
  - `viewItems` → `sortItems` (chỉ sắp xếp).
  - Bỏ `totalExact`, `categoryCounts`, `EMPTY_SEARCH_RESPONSE` (không còn nơi dùng).
- `src/frontend/src/components/search/SearchView.tsx` — sửa: số tab qua `searchOverviewApi(…, loadSection)`, bỏ dấu "+", `GroupShelf` không nhận `total`/`lazy`.
- `src/frontend/src/components/search/GroupShelf.tsx` — sửa: dùng `shelfCacheKey`/`searchShelfApi` (chung với số tab), bỏ tải lười, chỉ hiện "N kết quả" khi đã có dữ liệu.
- `src/frontend/src/components/search/GroupResults.tsx` — sửa:
  - Bộ lọc sao/giá vào request và khóa bộ đệm; đổi bộ lọc thì về trang 1.
  - Thanh trượt giá chờ 400 ms rồi mới gọi API.
  - Thanh "Đang lọc" hiện "· N kết quả theo bộ lọc".
- `src/frontend/tests/unit/searchService.test.ts` — sửa: test gửi bộ lọc, `topScore`/kết quả yếu, đếm tab từ request hàng (không request không lọc taxonomy, cùng khóa bộ đệm), `sortItems`, khóa bộ đệm theo bộ lọc.
- `src/frontend/tests/unit/searchView.test.tsx` — sửa:
  - Stub không còn nhánh `taxonomy: null` và có `diagnostics.totalExact: false`.
  - Thêm test tab = hàng; không có dấu "+".
  - Thêm test tab Lưu trú: lọc sao/giá gửi API, về trang 1, số theo bộ lọc, một request sau khi kéo thanh trượt, "Xóa tất cả".
- `src/frontend/tests/unit/landingResults.test.tsx` — sửa: thêm test lọc sao ở `/hotels` gửi cùng ngày và số khách.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.2 (bảng nguồn số tab, quy tắc "một nguồn đếm", bộ lọc gửi API, ba hàng tải cùng lúc), §4.1a (bộ lọc sao/giá gửi API).
- `docs/spec/product.md` — sửa: §4.2.3 ba dòng "Dòng truy vấn", "Tab nhóm", "Bộ lọc" (gồm cập nhật hai lưu ý về `SEARCH_TAXONOMY_FILTER` và `SEARCH_ENTITY_FILTER`).
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: §5.2 dòng `facets` ghi rõ facets của request không lọc taxonomy không bằng `total` theo loại, Web không dùng để đếm tab.
- `src/frontend/README.md` — sửa: đoạn `/search` (nguồn số tab, bộ lọc gửi API).
- `history/2026-10-12-dem-so-ket-qua-search-mot-nguon.md` — thêm: entry này.

## Quyết định

- Không đổi PRD, contract, backend.
  - PRD chỉ ghi "Tab hiện số kết quả" (`update-archive/2026-09-30-…`) và "tinh chỉnh bộ lọc Giá, Sao" (`user-flow.md` §3.1).
  - `priceMax`/`starRatingMin` đã có trong `SearchRequest` từ 1.15.0 và route đã áp. Không cần đề xuất PRD.
- Chọn sửa ở Web (phương án A) thay vì để backend trả số theo từng loại (B, cần đổi contract) hay chia suất vớt theo loại (C, đổi kết quả mọi lần tìm, phải chạy lại bench).
- Hệ quả của A:
  - Ba hàng ở tab Tất cả tải cùng lúc, mất tải lười (4 request: hotel, attraction, golf, combo).
  - Ở tab nhóm vẫn gọi 4 request đó để có số cho các tab.
  - Embed chỉ chạy một lần nhờ cache vector của backend.
- `total` không đổi theo `limit`/`offset` (bất biến §2.3 điều 2; đo lại ngày 12/10: `limit` 6 và 20 cùng 13), nên số tab (`limit: 6`) bằng mẫu số "Xem thêm" (`limit: 20`).
- Số trên tab là số chưa áp sao/giá. Khi đang lọc, danh sách ghi thêm "N kết quả theo bộ lọc" (đề xuất trong brainstorm, người dùng chấp nhận D).
- Bỏ hẳn dấu "+": ở hybrid `totalExact` luôn là `false`, nên dấu này không mang thông tin.
- Băng "kết quả yếu" dùng `topScore` cao nhất của ba nhóm.

## Kiểm tra

- Từ `src/frontend`:
  - `node_modules/.bin/vitest run tests/unit`: 70 file pass, 753 test pass. 1 file fail: `tests/unit/logger.test.ts` (`Cannot find package 'pino'`; `pino` có trong `package.json` nhưng chưa cài vào `node_modules` của checkout này; không liên quan).
  - Sau khi bỏ dòng `eslint-disable` thừa: 4 file test search/landing chạy lại 50 test pass.
- `node_modules/.bin/tsc --noEmit`: chỉ còn 2 lỗi có sẵn, không liên quan: `src/lib/logger.ts` thiếu `pino`, và `.next/dev/types/validator.ts` là file sinh cũ đã bị gitignore.
- `node_modules/.bin/eslint` trên các file đã sửa: 0 lỗi, 0 cảnh báo.
- Backend thật (:8000, `POST /api/v1/search`, câu "Nha Trang", `taxonomy: hotel`):
  - Không lọc: `total` 13.
  - `starRatingMin` 4: 12; `starRatingMin` 5: 11 (5 kết quả chưa khai sao, xếp sau).
  - `priceMax` 2.000.000: 13 (giá cao nhất trên trang 1.469.820).
  - Cả hai: 11. `appliedFilters` khai đúng hard/soft.
- Không đổi contract hay mock, nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Chưa xem trên trình duyệt với backend thật. Dev server ở :3000 đang chạy từ checkout khác (`Travel-Recommendation-Product/src/frontend`), còn `next dev` trong checkout này cần cài `pino` trước (`instrumentation.ts` import `lib/logger`).
- `total` vẫn là xấp xỉ (top-K và suất vớt tính trên tập đã lọc của từng request). Vì vậy bộ lọc giá có thể không làm giảm `total`: ví dụ trên chỉ ra 13 → 13, vì 10 suất vớt BM25 được lấp lại từ tập rẻ hơn. Lần sửa này chỉ bảo đảm mọi số trên **cùng một màn hình** đến từ cùng một request.
- Nếu đề xuất chờ chốt `docs/prd/update/2026-10-06-search-hybrid-min-coverage-rrf.md` (`lexicalMinCoverage` 0,1) được áp dụng, số hit được vớt tăng nhưng tab và hàng vẫn khớp nhau.
