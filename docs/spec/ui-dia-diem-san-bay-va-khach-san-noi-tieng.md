# Spec: ô điểm đi/đến sân bay (`/flights`) và khách sạn nổi tiếng (`/hotels`, `/combos`)

- Ngày: 2026-10-13
- Trạng thái: đã triển khai trên nhánh `khoa/flight-hotels-combos-design`
- Phục vụ: FR-SRC-03 (ô Địa điểm và ô Điểm đi/Điểm đến của trang danh mục), FR-CAT-01 (tuyến bay là nguồn sân bay), FR-CAT-03 (lịch khả dụng: chỉ tuyến còn bán)
- Đề xuất PRD đã chốt: `docs/prd/update-archive/2026-10-13-san-bay-va-khach-san-noi-tieng.md`; PRD đã cập nhật ở `docs/prd/requirements.md` FR-SRC-03 và `docs/prd/user-flow.md` dòng `/flights`
- Không có endpoint mới, không đổi contract OpenAPI, không đổi DDL.

## 1. Mục tiêu

1. `/flights`: ô Điểm đi và Điểm đến chỉ nhận **sân bay hiện hành** lấy từ catalog. Chữ không khớp sân bay nào thì ô tự xoá khi rời ô. Tìm chỉ gửi được khi cả hai ô là sân bay thật.
2. `/hotels` và `/combos`: khi bấm ô Địa điểm (chữ còn trống), dropdown hiện **"Khách sạn nổi tiếng"** thay cho "Điểm đến phổ biến", kèm danh sách khách sạn. Bấm một khách sạn mở trang chi tiết của khách sạn đó.

Ràng buộc chung: **không dùng dữ liệu giả**. Mọi sân bay, khách sạn, ảnh và giá đều đến từ `GET /api/v1/products` (catalog). Không có danh sách sân bay hay khách sạn viết cứng trong mã nguồn. Ảnh thay thế (`/placeholders/*.svg`) chỉ dùng khi sản phẩm không có `imageUrl`, đúng như `productFromApi` làm từ trước.

## 2. Khảo sát dữ liệu (data design)

Nguồn đã kiểm tra: API chạy trên stack demo (`make demo-db` nạp snapshot `src/data_collection/snapshots/2026-09-30/products.jsonl.gz`, sau đó có thêm tuyến mô phỏng của seed).

### 2.1 Sân bay lấy từ đâu

Không có bảng sân bay riêng trong catalog. Sân bay nằm trong thuộc tính của **tuyến bay** (`taxonomy=flight`, `attributes.level = route`), tầng cha của `GET /products` (không có `parentProductId` thì chỉ trả tầng cha, nên không lẫn chuyến con):

| Trường (`attributes`) | Ý nghĩa | Dùng cho |
|---|---|---|
| `originCity` | Thành phố đi (ví dụ "Nha Trang") | Nhãn sân bay đi |
| `originAirports` | Mảng mã IATA đi (ví dụ `["CXR"]`) | Mã sân bay đi |
| `destinationCity` | Thành phố đến | Nhãn sân bay đến |
| `destinationAirports` | Mảng mã IATA đến | Mã sân bay đến |
| `destinationAirportName` | Tên sân bay đến (ví dụ "Sân bay quốc tế Cam Ranh") | Tên hiển thị, khi tuyến có đúng một sân bay đến |
| `flightCount`, `monthlyPrices` | Số chuyến, giá theo tháng | Không dùng ở đây |

Lọc `availableOnly=true` để chỉ lấy tuyến còn bán: đây là định nghĩa "sân bay hiện hành" trong spec này.

Số liệu thật (API, 2026-10-13): **137 tuyến còn bán**, **19 mã sân bay**, mọi mã đều có tên sân bay trong catalog. Trong đó có sân bay nhiều tuyến nhất: SGN (36), HAN (31), DAD (26), PQC, CXR, DLI (20 mỗi sân bay).

### 2.2 Những gì catalog chưa có (không bịa)

- **Không có sân bay quốc tế.** Mọi tuyến đều nội địa Việt Nam. Ảnh tham chiếu có Seoul (ICN) và Singapore (SIN) và Cà Mau (CAH): catalog không có tuyến nào tới hoặc đi các sân bay này, nên **không hiển thị**. Thêm chúng là thêm dữ liệu giả, bị cấm.
- **Chưa có quốc gia của sân bay** trong `attributes`, nên không phân được "Quốc tế". Nhóm "Trong nước" là toàn bộ danh sách. Khi catalog có tuyến quốc tế, cần thêm trường quốc gia trước rồi mới thêm nhóm (xem §10).
- **Tên sân bay gốc chỉ có ở tuyến đến.** Với một sân bay chỉ xuất hiện là điểm đi, tên có thể thiếu. Trên stack demo hiện tại mọi sân bay đều có tên nhờ tuyến mô phỏng chiều ngược. Trên snapshot trip.com gốc, 4 sân bay (DIN, PXU, TBB, VDO) không có tên. Quy tắc: thiếu tên thì dòng chỉ ghi thành phố và mã, không suy đoán tên.

### 2.3 Khách sạn nổi tiếng lấy từ đâu

`GET /api/v1/products?taxonomy=hotel&sort=popular&availableOnly=true&limit=20`. Tầng cha (`level = property`), xếp theo `popularity_score` (cùng thứ tự với kệ "Khách sạn và resort phổ biến" đã có). Số liệu thật: 2.320 khách sạn còn bán, lấy 20 đầu.

**Lưu ý quan trọng (cần người dùng xác nhận):** "nổi tiếng" đang nghĩa là *phổ biến theo catalog*. Đầu bảng hiện là homestay ("09 Homestay" ở Cần Thơ, "1 House" ở Đà Lạt), không phải resort Vinpearl như ảnh tham chiếu. Vinpearl có trường `brand` trong catalog. Nếu muốn xếp theo thương hiệu hoặc sao, đó là quy tắc mới, cần chốt riêng (§10).

## 3. Quyết định thiết kế

| # | Quyết định | Lý do |
|---|---|---|
| D1 | Nguồn sân bay là tuyến bay còn bán trong catalog. Không có bảng sân bay trong frontend. | Không dữ liệu giả; khớp AC-AGT-03 của PRD ("danh sách thành phố có sân bay của catalog"). |
| D2 | Đường dẫn `/flights?origin&destination` vẫn dùng **tên thành phố** (`originCity`, `destinationCity`). | Kết quả (`listRoutesTo`, `listRouteFlights`, `flightModel`) và link đã chia sẻ đều dựa trên tên thành phố. Đổi sang mã IATA là thay đổi kết quả, ngoài phạm vi. Mỗi thành phố hiện có đúng một sân bay (xem kiểm thử), nên tên thành phố xác định sân bay. |
| D3 | Chữ khớp sân bay: mã IATA, tên thành phố (**chỉ khi thành phố đó có đúng một sân bay**), hoặc nhãn "Thành phố (MÃ)"; so khớp không phân biệt dấu và hoa thường (`fold`). | "Đúng sân bay" nghĩa là không mơ hồ. Thành phố có nhiều sân bay thì bắt buộc chọn bằng mã hoặc nhãn đầy đủ. |
| D4 | Ô hiển thị nhãn "Hà Nội (HAN)" sau khi chọn. URL và kết quả vẫn dùng "Hà Nội". | Người dùng thấy đúng sân bay; đường dẫn không đổi. |
| D5 | Rời ô (blur) hoặc gửi tìm kiếm mà chữ không khớp → ô **xoá chữ**. Khi đang gõ thì không xoá. | Đúng yêu cầu "ô tự xoá". Không xoá giữa chừng để không cắt ngang khi gõ. |
| D6 | Ô Địa điểm của `/hotels` và `/combos` đổi nội dung dropdown; chữ đang gõ vẫn khớp được điểm đến (có nhóm "Điểm đến") để giữ khả năng tìm theo thành phố. | Đúng yêu cầu; không làm mất tìm theo điểm đến. |
| D7 | Bấm một khách sạn mở `/product/{id}` kèm ngày và số khách đang chọn (`serializeTripContext`), không điền khách sạn vào ô. | Giống thẻ sản phẩm (`ProductCard`). Đây là quyết định mở để người dùng chỉnh được. |
| D8 | Khách sạn nổi tiếng dùng cùng một nguồn và cùng khoá cache cho cả `/hotels` và `/combos`. | Cùng nội dung, tránh gọi lại. |
| D9 | Khi có khách sạn hay sân bay nhưng nhóm trống (ví dụ gõ "xyz"): hiện câu "Không có … khớp" thay vì để dropdown trống. | Người dùng biết vì sao không có gợi ý. |
| D10 | Ô Điểm đến của `/experiences` không đổi. Dropdown `HotelTripBar` ở trang chi tiết không đổi. | Ngoài phạm vi yêu cầu. |

## 4. Hành vi: `/flights` (ô Điểm đi và Điểm đến)

### 4.1 Gợi ý khi mở ô

Khi ô được focus hoặc bấm, dropdown có các nhóm theo thứ tự:

1. **Tìm gần đây** (chỉ khi ô còn trống và có lịch sử): lịch sử ở trình duyệt (`vota_flight_recent_origins`, `vota_flight_recent_destinations`), tối đa 5, chỉ hiện mục vẫn là sân bay hiện hành.
2. **Sân bay phổ biến**: 5 sân bay có nhiều tuyến còn bán nhất. Hoà số thì xếp theo tên thành phố.
3. **Trong nước**: các sân bay còn lại, theo tên thành phố (tiếng Việt).

Mỗi dòng: biểu tượng, **thành phố** (đậm), dòng dưới là **mã · tên sân bay**. Ví dụ: "Nha Trang" / "CXR · Sân bay quốc tế Cam Ranh".

Ô Điểm đến bỏ qua sân bay đã chọn ở Điểm đi (không cho chọn cùng một sân bay).

### 4.2 Gõ chữ

Khi chữ không rỗng, dropdown chỉ còn một nhóm, cũng tên **"Sân bay phổ biến"** (theo yêu cầu cập nhật ngày 2026-10-13: cả hai ô đều là sân bay nên không dùng "Thành phố hoặc sân bay" hay "Sân bay khớp"): các sân bay có thành phố, mã hoặc tên chứa chữ đã gõ (không phân biệt dấu), tối đa 8. Không khớp: "Chưa có sân bay nào khớp “…”. Chọn một sân bay trong danh sách."

### 4.3 Chọn

- Bấm một dòng, hoặc dùng mũi tên lên/xuống rồi Enter: ô hiển thị nhãn "Thành phố (MÃ)", dropdown đóng. Điểm đi chọn xong thì con trỏ sang ô Điểm đến.
- Enter khi chưa tô sáng dòng nào: để form gửi đi (khi chữ đã khớp sân bay thì vẫn được gửi).
- Escape đóng dropdown.

### 4.4 Rời ô và gửi tìm kiếm

- **Blur**: nếu chữ khớp đúng một sân bay thì giữ nhãn; không khớp thì xoá chữ về rỗng (D5).
- **Gửi** (bấm Tìm hoặc Enter): mọi ô chưa khớp bị xoá; nếu thiếu thì hiện thông báo:
  - Chưa có điểm đi: "Bạn chưa chọn sân bay đi."
  - Có chữ nhưng không khớp: "Chưa nhận ra sân bay đi “…”. Chọn một sân bay trong danh sách gợi ý." (tương tự cho điểm đến)
  - Cả hai trống: "Chọn sân bay đi và sân bay đến để xem chuyến bay."
- Đủ hai sân bay: kết quả hiện ngay bên dưới (hành vi cũ, không đổi).

### 4.5 Mở lại từ URL

`/flights?origin=Hà Nội&destination=Đà Nẵng` điền sẵn ô bằng nhãn sân bay tương ứng (sau khi danh sách sân bay tải xong). Nếu thành phố trong URL không còn là sân bay hiện hành, ô giữ chữ đó đến khi người dùng rời ô hoặc gửi tìm kiếm; lúc đó chữ không khớp bị xoá và báo như §4.4.

### 4.6 Tải danh sách sân bay

Danh sách tải khi trang vào `/flights` (vì ô được điền sẵn từ URL cần biết sân bay). Dùng `useLazySection` với khoá `flight-airports`, TTL 5 phút, gộp request đang bay. Chưa tải xong thì ô hiện skeleton; lỗi thì dòng "Chưa tải được danh sách sân bay. Thử lại sau giây lát." và **không** gửi tìm kiếm (không đoán được sân bay).

## 5. Hành vi: `/hotels` và `/combos` (ô Địa điểm)

### 5.1 Khi bấm ô (chữ còn trống)

Dropdown có:

- **Khách sạn nổi tiếng** (thay cho "Điểm đến phổ biến"): tối đa 5 dòng. Mỗi dòng: ảnh vuông bo góc (hoặc ảnh thay thế của loại khách sạn nếu thiếu), tên (đậm), thành phố. Nguồn: 20 khách sạn đầu của `sort=popular`.
- Không có nhóm điểm đến khi ô trống.

### 5.2 Khi đang gõ

- **Khách sạn nổi tiếng** lọc theo tên hoặc thành phố chứa chữ gõ (trong 20 khách sạn đã tải).
- **Điểm đến**: tối đa 5 điểm đến khớp chữ gõ (danh sách `/destinations`, như trước). Bấm một điểm đến thì điền ô và chuyển sang Ngày, như cũ.
- Không khớp gì: "Không có khách sạn hay điểm đến nào khớp “…”. Bạn vẫn có thể tìm theo “…”."

### 5.3 Chọn một khách sạn

Bấm hoặc Enter trên dòng khách sạn: `navigate('/product/{productId}?{trip}')`. Dropdown đóng. Ô không đổi.

### 5.4 Trạng thái

| Trạng thái | Hiển thị |
|---|---|
| Đang tải | 3 khung skeleton |
| Lỗi | "Chưa tải được khách sạn nổi tiếng. Bạn vẫn có thể gõ tên điểm đến." |
| Không có khách sạn | "Chưa có khách sạn nổi tiếng để hiển thị lúc này." |
| Có khách sạn | Danh sách như §5.1 |

### 5.5 Khoá cache

`useLazySection('famous-hotels', …)`, TTL 5 phút, bật khi ô được focus hoặc bấm. Dùng chung cho `/hotels` và `/combos`.

## 6. Dữ liệu và API

Không đổi contract. Dùng có sẵn:

- `GET /api/v1/products?taxonomy=flight&availableOnly=true` (phân trang 50, tối đa 10 trang, như `allPages` hiện có) → `listFlightAirports()` trong `services/flights.ts`.
- `GET /api/v1/products?taxonomy=hotel&sort=popular&availableOnly=true&limit=20` → `listProducts()` (`services/catalog.ts`), chuyển bằng `productFromApi`.
- `GET /api/v1/destinations` (không đổi, cho gợi ý điểm đến khi gõ).

Frontend không gọi `fetch` trực tiếp; mọi lời gọi đi qua `services/`.

## 7. Không dùng mock data

- Không có mảng sân bay hay khách sạn viết cứng trong `src/frontend/src`. Test dùng dữ liệu giả **chỉ trong thư mục `tests/`** và được mock service (đúng cách test hiện có).
- Không thêm sân bay không có tuyến trong catalog (ICN, SIN, CAH trong ảnh tham chiếu).
- Ảnh khách sạn thiếu: dùng ảnh thay thế có sẵn của loại (`placeholderImage('hotel')`), không tạo ảnh.
- Các số trong spec này là số đo từ API demo ngày 2026-10-13, không phải số viết tay.

## 8. Khả năng truy cập

- Ô là `combobox` với `aria-expanded`, `aria-controls`, `aria-autocomplete="list"`; danh sách là `listbox`, mỗi dòng là `option` với `aria-selected`.
- Dòng khách sạn là nút trong `option`, có tên đầy đủ (tên khách sạn).
- Mũi tên, Enter, Escape như §4.3 và §5.3. Trạng thái đang tô sáng có viền và nền khác, không chỉ dựa vào màu.
- Thông báo lỗi ở vùng `role="alert"` như hiện có.

## 9. Kiểm thử

Unit (Vitest, jsdom, mock `services/`):

- `collectFlightAirports`: gom sân bay từ tuyến, đếm tuyến, tên từ `destinationAirportName` khi tuyến có một sân bay đến, sắp xếp.
- `matchAirport`: mã, tên thành phố có đúng một sân bay, nhãn "Thành phố (MÃ)", không dấu, hoa thường; thành phố có hai sân bay không khớp theo tên.
- `airportSections`: nhóm khi trống (phổ biến 5, trong nước), nhóm khi gõ, loại sân bay đã chọn ở ô kia, lịch sử chỉ còn sân bay hiện hành.
- Ô sân bay: gõ chữ không khớp rồi blur → chữ bị xoá; chọn bằng mũi tên và Enter; Enter không tô sáng thì gửi form.
- `FlightsPage`: thông báo mới; gửi với hai sân bay hợp lệ tới `/flights?origin&destination`.
- `LandingSearchSheet` (`/hotels`, `/combos`): khi bấm hiện "Khách sạn nổi tiếng" và không hiện "Điểm đến phổ biến"; gõ lọc khách sạn và điểm đến; bấm khách sạn → `navigate('/product/…')` kèm trip; `/experiences` vẫn "Điểm đến phổ biến".

Tích hợp và kiểm tay:

- Chạy stack thật (Postgres + `make demo-db`, FastAPI, Next dev), mở `/flights`, `/hotels`, `/combos`, kiểm từng trạng thái §4 và §5, chụp ảnh.
- `npm run typecheck`, `npm run lint` (chỉ các file đã chạm), `npm run test:unit`.
- Giới hạn của môi trường demo đã kiểm: `GET /api/v1/destinations` đọc từ chỉ mục tìm kiếm (Weaviate). Máy không chạy chỉ mục thì danh sách rỗng, nên nhóm "Điểm đến" khi gõ ở `/hotels` chỉ được kiểm bằng unit test, không kiểm trên ảnh chụp. Trên staging có chỉ mục thì nhóm này hiện bình thường.

## 10. Việc còn lại (ngoài phạm vi lần này)

1. Thêm quốc gia cho sân bay trong catalog (trường `attributes`) rồi mới thêm nhóm "Quốc tế".
2. Quy tắc "nổi tiếng" theo thương hiệu hoặc sao (Vinpearl, hạng sao, điểm đánh giá) nếu người dùng muốn thay `popularity_score`. Cần chốt trước khi làm.
3. Ghi `originAirportName` vào tuyến trong job dữ liệu, để mọi sân bay đi có tên mà không phụ thuộc tuyến chiều ngược.
4. Đưa mã sân bay vào URL (`originAirport=CXR`) khi có nhiều sân bay cho một thành phố.
