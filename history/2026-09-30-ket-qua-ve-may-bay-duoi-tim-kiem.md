# Kết quả vé máy bay dưới tấm tìm kiếm của /flights (bộ lọc theo buổi, dải ngày, Vé của tôi)

- Ngày: 2026-09-30
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (chưa chạy trọn luồng đặt vé bằng tài khoản đăng nhập; xem Còn lại)
- Phạm vi: frontend, docs
- Bị thay thế một phần bởi: 2026-09-30-flights-tim-tai-cho-bo-khoi-pho-bien-va-gia-tot.md

## Mục tiêu

mihhquan gửi ảnh chụp trang chọn vé máy bay của một OTA và yêu cầu làm phần tìm vé máy bay theo phong cách đó, xem bản mẫu trên artifact trước, rồi áp dụng vào project với **dữ liệu lấy từ database**. Sau đó yêu cầu sửa ở `/flights`, phần phía dưới tấm tìm kiếm. Bộ lọc giờ khởi hành là khung theo buổi (Sáng · Trưa · Chiều · Tối · Khuya), không kéo thanh trượt.

Phục vụ FR-SRC-03 (vé máy bay chỉ duyệt và tìm ở `/flights`; ngày khởi hành), FR-CAT-02, FR-CAT-03 (chuyến bay tầng con, `fareClasses`), FR-BKG-10 và AC-BKG-09 (hai chặng ngược chiều là một chuyến khứ hồi), NFR-REL-01 (grounding).

## File thay đổi

Frontend (`src/frontend/`):
- `src/services/flights.ts` — thêm: `listRoutesTo` (tuyến theo điểm đến) và `listRouteFlights` (chuyến của tuyến), đọc mọi trang qua `listProducts`.
- `src/features/flights/results/flightModel.ts` — thêm: hàm thuần gom các hạng vé cùng hành trình thành một thẻ, lọc theo buổi/hãng/điểm dừng, sắp xếp, gom ngày, ghép chặng đi–về, khớp tuyến theo điểm đi.
- `src/features/flights/results/flightHref.ts` — thêm: dựng và đọc URL `/flights?origin&destination&…`.
- `src/features/flights/results/flightFormat.ts` — thêm: định dạng ngày, thứ, giá.
- `src/features/flights/results/useFlightLegs.ts` — thêm: tải chặng đi và chặng về.
- `src/features/flights/results/FlightResultsView.tsx` — thêm: màn hình ghép các phần, chọn từng chặng, "Đặt vé".
- `src/features/flights/results/FlightFilters.tsx`, `FlightDateStrip.tsx`, `FlightCard.tsx`, `TicketPanel.tsx`, `AirlineBadge.tsx` — thêm: bộ lọc, dải ngày, thẻ chuyến bay, "Vé của tôi", ô hãng.
- `src/app/(storefront)/flights/page.tsx` — sửa: có `origin` và `destination` thì dựng hero, tấm tìm kiếm điền sẵn và kết quả bên dưới; không thì vẫn là `VerticalLanding`.
- `src/features/catalog/landing/LandingHero.tsx` — sửa: prop `search` (điền sẵn tấm tìm kiếm, hero thấp hơn), `key` theo lần tìm.
- `src/features/catalog/landing/LandingSearchSheet.tsx` — sửa: prop `initialSearch`; vé máy bay có điểm đi và điểm đến chuẩn thì điều hướng sang `/flights?origin&destination…`, còn lại như cũ.
- `src/components/search/SortMenu.tsx` — sửa: generic, nhận `labels` (mặc định bộ của `/search`).
- `src/components/search/GroupResults.tsx` — sửa: chỉ ghi rõ kiểu `SortMenu<SortOption>`.
- `src/frontend/README.md` — sửa: thêm đoạn `/flights?origin&destination`.
- `tests/unit/flightModel.test.ts`, `flightsService.test.ts`, `flightResultsView.test.tsx` — thêm; `tests/unit/landingSearchSheet.test.tsx` — sửa: ba ca vé máy bay.

Docs:
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §3 dòng `/flights`, §4.1a, thêm §4.1b.
- `docs/spec/product.md` — sửa: dòng route danh mục, thêm §4.2.0.
- `history/2026-09-30-ket-qua-ve-may-bay-duoi-tim-kiem.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD, không cần đề xuất.** Ở lượt đầu tôi nhận định luồng "chọn chiều đi rồi chiều về" lệch PRD; sau khi đọc FR-BKG-10 thì rút lại: FR-BKG-10 đã cho phép hai chặng ngược chiều trong giỏ hiển thị là một chuyến khứ hồi, mỗi chặng một mục, tổng bằng tổng hai chặng. Kết quả nằm ở `/flights` (FR-SRC-03: "chỉ duyệt và tìm ở `/flights`"), không thêm route, không đổi contract. Nếu người review thấy vẫn cần đề xuất `docs/prd/update/` thì làm trước khi merge.
- `/search?type=flight` (ngoại lệ đã chốt ở entry `2026-09-30-search-tab-nhom-hang-cuon-ngang`) giữ nguyên; tấm tìm kiếm chỉ chuyển sang `/flights` khi có điểm đi và điểm đến chuẩn.
- Dữ liệu chỉ từ `GET /products` (tuyến theo `destination`, chuyến theo `parentProductId`), gom hạng theo `fareClasses` như `docs/guide/hien-thi-hang-ve-may-bay.md`: mỗi hành trình một thẻ, `null` là chưa biết (không hiện "0 kg"), vé mô phỏng có nhãn "Giá minh hoạ", `EXPIRED` không khoá nút. Bộ lọc điểm dừng chỉ có "Bay thẳng" và "Có điểm dừng" vì dữ liệu chỉ có `nonstop` (true hoặc vắng mặt).
- Dải ngày chỉ có ngày còn chuyến: catalog thưa (1–3 chuyến mỗi ngày), ngày trống không được hiện như đã có giá. Ngày `checkIn` không có chuyến thì mở ngày gần nhất kèm câu báo.
- "Tổng ước tính" dùng `estimateFares` như hộp đặt (chỉ hiển thị, Web không gửi số tiền); giá chính thức là của `CartResponse`. "Đặt vé" thêm từng chặng bằng `addToCart` (`guests` từ URL) rồi sang `/checkout`.
- Bố cục theo ảnh mẫu: hero và tấm tìm kiếm ở lại, kết quả bên dưới (theo yêu cầu "sửa phần phía dưới phần tìm kiếm" của `/flights`). Header giữ kiểu nổi trên hero như các trang danh mục, không đổi `Header.tsx`.
- Logo hãng không dùng: ô chữ viết tắt, màu chọn theo tên hãng.

## Kiểm tra

- `tsc --noEmit`: sạch. `eslint .`: 0 lỗi, 2 cảnh báo có sẵn (`ItineraryMap`).
- `vitest run`: 47 file, 470 test; lần chạy đầy đủ có 1 ca `assistantProvider.test.tsx` fail (không liên quan), chạy riêng và chạy trên cây sạch (`git stash`) đều pass 9/9, nghi ca phụ thuộc thời gian khi máy tải nặng (đã gặp ở entry `2026-09-30-thong-tin-giay-to-hanh-khach-ve-may-bay`). Các ca của thay đổi này pass ba lần chạy liên tiếp.
- Không đổi contract, DDL hay mock nên không chạy `validate_contract.py`.
- Trình duyệt thật (Playwright trên dev server `localhost:3000`, backend `127.0.0.1:8000`, database local 113 tuyến, 787 chuyến): HAN → SGN khứ hồi tải 4 request (`/products` tuyến theo điểm đến và chuyến của tuyến, cho chiều đi và chiều về), dải ngày 01/10 … 12/10 khớp API, chọn chiều đi rồi chiều về, tổng ước tính 4.455.000 ₫ = (853.000 + 632.000) × 3 khách, "Đặt vé" khi chưa đăng nhập mở modal đăng nhập, `/flights` không tham số vẫn là trang danh mục, ở 400 px không tràn ngang. Dev server chỉ hydrate qua `localhost`, không qua `127.0.0.1`.

## Còn lại / rủi ro

- Chưa chạy trọn luồng đặt vé bằng tài khoản đăng nhập trên trình duyệt thật (thêm hai chặng vào giỏ rồi sang `/checkout`); mới có test đơn vị với `addToCart` giả và kiểm modal đăng nhập.
- Database local chưa nạp snapshot `2026-09-30`: không có chuyến nối chặng, hạng Phổ thông/Thương gia, hành lý hay vé mô phỏng, nên các nhánh đó chỉ được kiểm bằng test đơn vị. Cần xem lại sau `make demo-db-reset`.
- 290 vé khứ hồi đóng gói không có trong danh sách này (thẻ chỉ có vé một chiều); chúng vẫn xem và đặt ở `/product/{id}`.
- Ô "Điểm đi" của tấm tìm kiếm vẫn là ô gõ tự do; điểm đi không có tuyến thì trang gợi ý các điểm đi có chuyến tới điểm đến.
- Chưa có Playwright e2e cho luồng này. Đã xem bằng mắt ở 1440, 900 và 400 px, chưa xem ở các khổ khác.
- Chưa commit.
