# Ô sân bay ở /flights và khách sạn nổi tiếng ở /hotels, /combos

- Ngày: 2026-10-13
- Tác giả: người dùng (yêu cầu) / Claude Haiku 5.5 (thực hiện)
- Nhánh: khoa/flight-hotels-combos-design
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

1. `/flights`: ô Điểm đi và Điểm đến chỉ nhận sân bay hiện hành của catalog. Chữ không khớp thì ô tự xoá khi rời ô; tìm chỉ gửi được khi cả hai ô là sân bay thật.
2. `/hotels` và `/combos`: khi bấm ô Địa điểm, dropdown hiện "Khách sạn nổi tiếng" thay cho "Điểm đến phổ biến", kèm danh sách khách sạn. Bấm một khách sạn mở trang chi tiết.
3. Không dùng dữ liệu giả: sân bay và khách sạn đều đến từ `GET /api/v1/products`.

Spec đầy đủ: `docs/spec/ui-dia-diem-san-bay-va-khach-san-noi-tieng.md`. Đề xuất PRD đã chốt theo yêu cầu trong chat: `docs/prd/update-archive/2026-10-13-san-bay-va-khach-san-noi-tieng.md`.

## File thay đổi

Tài liệu:

- `docs/prd/requirements.md` — sửa: FR-SRC-03 thêm hai mục con (ô sân bay, khách sạn nổi tiếng) và trỏ tới đề xuất.
- `docs/prd/user-flow.md` — sửa: dòng `/flights` ghi "chọn sân bay hiện hành trong danh sách".
- `docs/prd/update-archive/2026-10-13-san-bay-va-khach-san-noi-tieng.md` — chuyển từ `update/` (trạng thái đã áp dụng).
- `docs/spec/ui-dia-diem-san-bay-va-khach-san-noi-tieng.md` — thêm: spec đầy đủ, khảo sát dữ liệu, quyết định D1–D10, hành vi, kiểm thử.

Source (`src/frontend`):

- `src/services/flights.ts` — sửa: thêm `FlightAirport`, `collectFlightAirports` (gom sân bay từ tuyến còn bán), `listFlightAirports`.
- `src/features/flights/airports/airportOptions.ts` — thêm: khớp sân bay, nhóm gợi ý, thứ tự phím.
- `src/features/flights/airports/AirportField.tsx` — thêm: ô sân bay (dropdown, phím mũi tên, Enter, Escape).
- `src/features/flights/airports/useFlightAirports.ts` — thêm: hook tải sân bay, TTL 5 phút.
- `src/features/flights/results/flightHref.ts` — sửa: `FlightSearchInput` thêm `originText`, `airportsReady`.
- `src/features/flights/FlightsPage.tsx` — sửa: thông báo thiếu sân bay, chữ gợi ý trang.
- `src/features/catalog/landing/LandingSearchSheet.tsx` — sửa: ô sân bay cho `/flights`, dropdown khách sạn nổi tiếng cho `/hotels`, `/combos`; `/experiences` giữ nguyên.
- `src/features/catalog/landing/FamousHotelsPanel.tsx` — thêm: dropdown khách sạn nổi tiếng, `famousHotelOptions`.
- `src/features/catalog/landing/useFamousHotels.ts` — thêm: hook tải khách sạn `sort=popular`, dùng chung cho `/hotels` và `/combos`.
- `src/features/catalog/landing/fieldStyles.ts` — thêm: lớp CSS chung của các ô (tách từ tấm tìm kiếm).
- `src/features/catalog/landing/searchHref.ts` — sửa: thêm `startsAWord` (khớp đầu từ, FR-SRC-05).
- `src/features/catalog/landing/verticals.ts` — sửa: `location.suggest` (`destinations` | `famous-hotels` | `airports`).

Test (`src/frontend/tests`):

- `tests/unit/airportOptions.test.ts` — thêm (13 test).
- `tests/unit/flightAirports.test.ts` — thêm (6 test).
- `tests/unit/landingSearchSheet.test.tsx` — sửa: viết lại phần vé máy bay theo sân bay; thêm test khách sạn nổi tiếng (26 test).
- `tests/unit/flightsPage.test.tsx` — sửa: thông báo mới và luồng sân bay (8 test).
- `tests/unit/verticalLanding.test.tsx` — sửa: tìm kệ phổ biến theo `sort`, vì tấm tìm kiếm vé giờ cũng gọi danh sách sân bay (không đổi ý nghĩa test).

## Quyết định

- Nguồn sân bay: tuyến bay còn bán (`availableOnly=true`) trong catalog, không có danh sách cố định trong mã nguồn. Lý do: không dữ liệu giả, khớp AC-AGT-03.
- URL vẫn dùng tên thành phố (`origin`, `destination`), kết quả và `listRoutesTo` không đổi. Mỗi thành phố hiện có đúng một sân bay trong catalog.
- Khớp sân bay: mã IATA, nhãn "Thành phố (MÃ)", hoặc tên thành phố khi thành phố đó chỉ có một sân bay. Không phân biệt dấu và hoa thường.
- Khớp chữ gõ theo đầu từ (FR-SRC-05). Mục bắt đầu bằng chữ gõ xếp trước; "da" vẫn thấy "Côn Đảo" vì "Đảo" bỏ dấu là "dao", đúng quy tắc không phân biệt dấu.
- Ô xoá chữ khi rời ô hoặc khi gửi, nếu chữ không khớp sân bay nào. Lỗi chạy thật đã sửa: chọn một dòng rồi chuyển focus sang ô kia làm ô đi bị xoá bằng chữ cũ trong closure; sửa bằng cập nhật hàm (`settleAirport`).
- Khách sạn nổi tiếng = `sort=popular` của catalog (cùng thứ tự kệ "Khách sạn và resort phổ biến"). Bấm khách sạn mở `/product/{id}` kèm ngày và số khách.
- Ô Điểm đến của `/experiences` và dropdown ở `HotelTripBar` không đổi.

## Kiểm tra

- `npx tsc --noEmit` (src/frontend): exit 0.
- `npx eslint` trên 17 file TypeScript đã chạm: exit 0.
- `npx vitest run tests/unit` (src/frontend): các file đã chạm đều pass (flightsPage, landingSearchSheet, verticalLanding, airportOptions, flightAirports, searchHref, navMenu). Chạy toàn bộ trước sửa cuối chỉ còn 1 test vỡ (`verticalLanding`), đã sửa. Kết quả toàn bộ sau cùng: 76 file, 824 test, đều pass.
- Stack thật: Postgres + `make demo-db` (snapshot 2026-09-30, verify PASS), FastAPI `127.0.0.1:8000`, Next dev `:3000`. `GET /api/v1/products?taxonomy=flight&availableOnly=true`: 137 tuyến, 19 sân bay, đều có tên. `GET /api/v1/products?taxonomy=hotel&sort=popular&availableOnly=true&limit=20`: 2.320 khách sạn, 20 lấy về.
- Chụp ảnh Playwright (ngoài repo, thư mục scratchpad): sân bay phổ biến, gõ "Đà" ra sân bay khớp, chữ không hợp lệ bị xoá, kết quả tìm Hà Nội → Đà Nẵng, khách sạn nổi tiếng ở `/hotels`, `/combos`.
- Không đổi contract OpenAPI hay DDL, không chạy `validate_contract.py` (không có thay đổi contract/mock).

## Còn lại / rủi ro

- Cần người dùng xác nhận:
  - "Nổi tiếng" đang là "phổ biến theo catalog". Đầu bảng hiện là homestay ("09 Homestay" Cần Thơ, "1 House" Đà Lạt), không phải resort Vinpearl như ảnh tham chiếu. Nếu muốn xếp theo thương hiệu hoặc sao thì cần quy tắc riêng.
  - Bấm khách sạn mở trang chi tiết, không điền khách sạn vào ô (D7).
  - Đề xuất PRD ghi "đã chốt" dựa trên yêu cầu trong chat. Chốt lại nếu chưa đúng ý.
- Ảnh tham chiếu có Seoul (ICN), Singapore (SIN), Cà Mau (CAH). Catalog không có tuyến tới các sân bay này nên không hiển thị (không thêm dữ liệu giả). Chưa có sân bay quốc tế; chưa có trường quốc gia trong catalog nên chưa có nhóm "Quốc tế".
- Tên sân bay: 4 sân bay (DIN, PXU, TBB, VDO) không có tên trên snapshot trip.com gốc. Stack demo hiện có tên nhờ tuyến mô phỏng chiều ngược của seed. Việc ghi `originAirportName` vào tuyến là việc sau.
- Demo catalog có tuyến mô phỏng (nhãn "giá minh hoạ"). Sân bay trong danh sách là mã thật, nhưng một số chuyến hiển thị là mô phỏng.
- `/destinations` đọc từ chỉ mục tìm kiếm (Weaviate). Máy không chạy chỉ mục thì nhóm "Điểm đến" khi gõ ở `/hotels` rỗng; đã kiểm bằng unit test, không kiểm bằng ảnh.
- `src/frontend/AGENTS.md` yêu cầu đọc `node_modules/next/dist/docs` trước khi viết code. Chưa đọc. Thay đổi chỉ dùng React và mẫu component có sẵn trong repo, không dùng API Next mới.
- `src/data_collection/README.md` bị seed ghi khối `seed-report` khi chạy `make demo-db`; đã hoàn nguyên, không thuộc thay đổi này.
- Môi trường chạy (Postgres Docker, `src/backend/.venv`, `src/frontend/node_modules`, `secrets/`, `src/frontend/.env.local`) nằm ngoài git, không commit.
