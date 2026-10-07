# /flights: ô Điểm đi gõ có gợi ý, cả hai ô có "Tìm gần đây"

- Ngày: 2026-10-01
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Yêu cầu của mihhquan (kèm ảnh chụp): ở tấm tìm kiếm của `/flights`, ô Điểm đi chưa có gợi ý khi gõ như ô Điểm đến, và các ô địa điểm phải có phần lịch sử. Phục vụ FR-SRC-03 (vé máy bay chỉ duyệt và tìm ở `/flights`).

## File thay đổi

Frontend (`src/frontend/`):
- `src/features/catalog/landing/LandingSearchSheet.tsx` — sửa: ô Điểm đi thành combobox (gợi ý, mũi tên, Enter), chọn xong chuyển sang ô Điểm đến; hai ô dùng chung `PlacePanel`; ghi lịch sử khi bấm Tìm (chỉ vé máy bay).
- `src/features/catalog/landing/PlacePanel.tsx` — thêm: nội dung dropdown (nhóm "Tìm gần đây" kèm nút Xóa, nhóm "… phổ biến").
- `src/features/catalog/landing/recentPlaces.ts` — thêm: lưu/đọc lịch sử ở `localStorage` (tối đa 5, bỏ trùng không phân biệt dấu, lỗi lưu thì bỏ qua), `useRecentPlaces`, `buildPlaceOptions`.
- `tests/unit/landingSearchSheet.test.tsx` — sửa: thêm 6 ca (gợi ý điểm đi, phím, ghi và hiện lịch sử, Xóa, nhãn đã mất khỏi `/destinations`, danh mục khác không có lịch sử); ca vé máy bay gọi ô Điểm đến theo tên vì nay có hai combobox.
- `tests/unit/flightsPage.test.tsx` — sửa: gọi ô Điểm đến theo tên.

Docs:
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.1a (dòng gợi ý), §4.1b (đoạn mới về hai ô và lịch sử).
- `src/frontend/README.md` — sửa: đoạn `/flights`.

## Quyết định

- **Không lệch PRD, không cần đề xuất.** PRD không mô tả ô Điểm đi; mẫu "Tìm kiếm gần đây" (tối đa 5, nút xóa, `localStorage`) đã có ở `docs/spec/product.md` §4.2.1. `localStorage` chỉ giữ nhãn địa điểm, không đụng quy tắc cấm JWT/token (`docs/prd/architecture.md` §6.2). Không đổi contract, DDL, route.
- Gợi ý điểm đi lấy cùng `GET /destinations` với điểm đến (không có API điểm đi riêng). Điểm đi vẫn gõ tự do; điểm đi không có tuyến vẫn xử lý như cũ (trang gợi ý các điểm đi có chuyến).
- Lịch sử tách hai khoá (điểm đi, điểm đến), chỉ ghi khi có đủ cả hai lúc bấm Tìm, và chỉ cho vé máy bay (các danh mục khác không yêu cầu). Nhãn lịch sử được đổi về nhãn chuẩn; nhãn không còn trong `/destinations` không được gợi ý lại để tránh tìm vô nghĩa.
- Điểm đã chọn ở ô này bị ẩn khỏi gợi ý của ô kia.

## Kiểm tra

- `tsc --noEmit`: sạch. `eslint .`: 0 lỗi, 2 cảnh báo có sẵn (`ItineraryMap`).
- `vitest run`: 48 file, 481 test pass.
- Trình duyệt thật (Playwright, `localhost:3000`, backend local): focus ô Điểm đi hiện gợi ý; gõ "ha" lọc ra Hà Nội, Hải Phòng…; chọn Hà Nội thì con trỏ sang ô Điểm đến; tìm Hà Nội → Đà Nẵng ra `/flights?origin=…&destination=…`; `localStorage` lưu `["Hà Nội"]` và `["Đà Nẵng"]`; tải lại trang rồi mở từng ô trống thì hiện "Tìm gần đây" đúng nhãn. Không có lỗi trang hay console.
- Không đổi contract/mock nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Gợi ý điểm đi là mọi điểm đến có sản phẩm (xếp theo số sản phẩm), không phải chỉ nơi có chuyến bay đi; chọn điểm đi không có tuyến thì trang báo như trước. Muốn chính xác hơn cần endpoint điểm đi từ Backend.
- Lịch sử theo từng trình duyệt, không đồng bộ giữa thiết bị.
- Chưa có Playwright e2e cho phần này; chưa xem ở khổ điện thoại.
- Chưa commit.
