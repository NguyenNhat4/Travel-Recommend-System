# /flights: tìm ngay tại trang, chưa nhập thì nhắc nhập, bỏ hai khối "phổ biến" và "giá tốt"

- Ngày: 2026-09-30
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs
- Thay thế một phần: `2026-09-30-ket-qua-ve-may-bay-duoi-tim-kiem.md` (cách kết quả được kích hoạt và phần bên dưới khi chưa tìm)

## Mục tiêu

Yêu cầu của mihhquan sau bản đầu: (1) làm phần bên dưới ô tìm kiếm của `/flights`, tìm kiếm **không ra trang khác**, kết quả nằm ngay trên chính trang; chưa có thì chỉ hiện cho người dùng biết phải nhập; (2) "bỏ phần chặng bay phổ biến và vé giá tốt". Phục vụ FR-SRC-03 (vé máy bay chỉ duyệt và tìm ở `/flights`), FR-BKG-10.

## File thay đổi

PRD (cập nhật trước khi sửa source, đề xuất chốt ngay trong chat theo tiền lệ `2026-09-30-ve-thuong-gia-mo-phong-mac-dinh-bat`):
- `docs/prd/update-archive/2026-09-30-trang-ve-may-bay-tim-tai-cho-bo-khoi-pho-bien-va-gia-tot.md` — thêm: đề xuất, trạng thái `đã áp dụng`, chốt bởi mihhquan 2026-09-30.
- `docs/prd/user-flow.md` — sửa: dòng `/flights` của bảng route (bỏ Product Shelves, thêm kết quả chuyến bay hoặc lời nhắc nhập).

Spec và docs:
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §3 dòng `/flights`, §4.1a (ngoại lệ `/flights`), §4.1b viết lại phần mở đầu.
- `docs/spec/product.md` — sửa: dòng route danh mục, §4.2.0.
- `src/frontend/README.md` — sửa: đoạn `/flights`.

Frontend (`src/frontend/`):
- `src/features/flights/FlightsPage.tsx` — thêm: hero + tấm tìm kiếm + kết quả hoặc lời nhắc; giữ lần tìm trong state, cập nhật URL bằng `history.replaceState`; `missingFlightInput` nói còn thiếu gì.
- `src/app/(storefront)/flights/page.tsx` — sửa: render `FlightsPage`; chưa tìm thì bên dưới lời nhắc chỉ có Destination Tiles và banner trợ lý (hai khối `CatalogShelf` bị bỏ).
- `src/features/catalog/landing/LandingSearchSheet.tsx` — sửa: prop `onFlightSearch` (vé máy bay gửi giá trị lên trang, kể cả khi còn thiếu, không điều hướng), `initialSearch`; không có handler thì vẫn sang `/search` như cũ.
- `src/features/catalog/landing/LandingHero.tsx` — sửa: props `search`, `compact`, `onFlightSearch`.
- `src/features/flights/results/flightHref.ts` — sửa: kiểu `FlightSearchInput`.
- `src/features/flights/results/FlightResultsView.tsx` — sửa: prop `notice` (lần Tìm sau còn thiếu thông tin thì kết quả cũ ở lại kèm lời báo).
- `tests/unit/flightsPage.test.tsx` — thêm; `tests/unit/landingSearchSheet.test.tsx` — sửa: ca `onFlightSearch`.

## Quyết định

- Lệch PRD ở dòng `/flights` của bảng route (bỏ "Product Shelves") nên có đề xuất; mihhquan ra lệnh trực tiếp "bỏ phần chặng bay phổ biến và vé giá tốt", ghi thẳng vào `update-archive` với trạng thái `đã áp dụng` như tiền lệ. Không đổi FR/NFR/AC, contract hay DDL.
- Chỉ bỏ đúng hai khối được nêu; Destination Tiles ("Bạn muốn đi đâu?") và banner trợ lý giữ nguyên. Chưa nói rõ với mihhquan là giữ hai khối này (xem Còn lại).
- Tìm tại chỗ bằng state cục bộ + `history.replaceState`, không đi qua router: không tải lại trang, không dựng lại hero; kiểm bằng cách gắn cờ vào `window` rồi tìm hai lần, cờ còn nguyên. `key` theo URL ở `page.tsx` chỉ dựng lại trang khi điều hướng thật (menu, ô điểm đến).
- Điểm đến gõ tay không khớp nhãn của `/destinations` bị coi là thiếu và lời nhắc bảo chọn từ gợi ý, không đoán.
- `VerticalLanding.tsx` giữ nguyên (đã thử tách `LandingShelves` rồi hoàn lại); `/hotels`, `/experiences`, `/combos` không đổi.

## Kiểm tra

- `tsc --noEmit`: sạch. `eslint .`: 0 lỗi, 2 cảnh báo có sẵn (`ItineraryMap`).
- `vitest run`: 48 file, 475 test pass.
- Trình duyệt thật (Playwright, `localhost:3000`, backend và database local): `/flights` trơn chỉ có hero, tấm tìm kiếm, lời nhắc, Destination Tiles, banner; không còn hai khối shelf. Bấm Tìm khi trống hiện "Nhập điểm đi và chọn điểm đến để xem chuyến bay."; nhập Hà Nội → TP. Hồ Chí Minh rồi Tìm hiện chuyến bay ngay bên dưới, URL thành `/flights?origin=…&destination=…`, cờ `window` còn nguyên (không tải lại trang); tìm lần hai sang Đà Nẵng cũng tại chỗ. Không có lỗi trang hay console.

## Còn lại / rủi ro

- Hỏi mihhquan: Destination Tiles và banner trợ lý dưới lời nhắc có giữ không (đang giữ). Bỏ cũng chỉ là xoá hai dòng ở `page.tsx`, kèm sửa dòng `/flights` của PRD qua đề xuất.
- `/search?type=flight` không còn được tấm tìm kiếm dẫn tới nhưng code và test của nó còn; có thể gỡ sau nếu không ai dùng.
- Nút Back của trình duyệt sau khi tìm tại chỗ: URL dùng `replaceState` nên Back rời hẳn trang `/flights` thay vì về lần tìm trước.
- Các điểm còn lại của entry `2026-09-30-ket-qua-ve-may-bay-duoi-tim-kiem.md` (chưa chạy trọn luồng đặt vé bằng tài khoản đăng nhập, dữ liệu local thưa, chưa có e2e) vẫn đúng.
- Chưa commit.
