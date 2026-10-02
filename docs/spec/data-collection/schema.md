# Schema catalog du lịch V-OTA

Tài liệu tham chiếu cho `products.jsonl` · 11.387 sản phẩm · bản 23/09/2026 · ban đầu sinh bởi `make_docs.py` (đã gỡ ngày 29/09/2026), từ đó sửa tay khi thêm khoá

Bản máy đọc được, liệt kê **mọi** khoá `attributes` theo từng loại kèm độ phủ: **`template.json`** cùng thư mục
(bản 23/09/2026; công cụ sinh lại `make_template.py` đã gỡ ngày 29/09/2026). Tài liệu này giải thích các khoá quan trọng; `template.json` là danh
sách đầy đủ. Bản ghi thật để đọc và chạy thử: **`sample/`**.

---

## 1. Nguyên tắc

- Mỗi dòng của `products.jsonl` là **một sản phẩm**, gồm **đúng 13 trường** của CDP V-OTA theo §6 handbook.
- Mọi thông tin khác nằm trong `attributes`. Cố ý như vậy: thêm field cấp cao nhất mà CDP thật không có
  sẽ thành cái bẫy cho người tích hợp về sau.
- `products.csv` là cùng dữ liệu ở dạng bảng, chỉ để mở xem. **Khi viết code, đọc `products.jsonl`.**
- 11.351/11.387 mô tả được nhận diện là tiếng Việt; 11.387/11.387 giá là VND; 11.387/11.387 sản phẩm có toạ độ.
- Toàn bộ là dữ liệu quan sát được từ nguồn (Vinpearl, booking.com, agoda.com, trip.com, OurAirports, OpenStreetMap),
  **không có giá trị sinh ngẫu nhiên**. Phần *suy ra* (vd. `familyFriendly`, mô tả tự sinh) đều có nhãn ở `attributes`.

```python
import json
products = [json.loads(line) for line in open("products.jsonl", encoding="utf-8")]
```

## 2. Mười ba trường cấp cao nhất

| Trường | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `productId` | string, UUIDv5 | 100% | Khoá chính. Sinh từ `sourceRef` nên **ổn định giữa các lần chạy lại** — dùng làm khoá ngoại được, không cần lưu bảng ánh xạ |
| `name` | string | 100% | Tên hiển thị. Hạng phòng theo mẫu `"<Khách sạn> - <Hạng phòng>"`, vé máy bay `"Vé máy bay <A> - <B>"` |
| `taxonomy` | enum | 100% | `hotel` · `flight` · `attraction` · `combo` · `golf` |
| `destination` | string | 100% | Nhãn **điểm đến du lịch**, không phải tỉnh hành chính. Tỉnh nằm ở `attributes.province` |
| `description` | string | 100% | Văn bản dùng để embedding. Không chứa điều khoản vé |
| `attributes` | object | 100% | Xem mục 3. Tập khoá thay đổi theo `taxonomy` |
| `unitPrice` | number \| null | 97,4% | Khách sạn: giá **một đêm**. Vé máy bay: giá một chiều tham khảo. `null` = chưa có giá (mục 2, điểm 2) |
| `currency` | string | 100% | Luôn là `"VND"` |
| `available` | boolean | 100% | Nguồn có trả giá tại thời điểm crawl (điểm tham quan trip.com: địa điểm có trên trip.com, có thể chưa có giá). **Không phải xác nhận còn chỗ** |
| `availableFrom` | date \| null | 94,9% | Vé/combo/golf Vinpearl: ngày bắt đầu bán (API Vinpearl). Vé máy bay: ngày bay sớm nhất trip.com liệt kê (giờ VN). Còn lại `null` |
| `availableTo` | date \| null | 94,9% | Vé/combo/golf Vinpearl: ngày hết hạn bán (API Vinpearl). Vé máy bay: ngày bay muộn nhất trip.com liệt kê (giờ VN). Còn lại `null` |
| `imageUrl` | URL \| null | 94,7% | Ảnh chính. Ảnh phụ ở `attributes.images`. Vé máy bay không có ảnh |
| `sourceRef` | string | 100% | `"<nguồn>:<loại>:<id>"`, ví dụ `vinpearl:tour:VW00466`. Truy ngược về bản ghi gốc |

### Bốn chỗ dễ hiểu sai

1. **`available = true` không phải là còn phòng.** Nó chỉ nói nguồn có trả giá lúc crawl (điểm tham quan trip.com chưa có giá cũng được đánh dấu `true` để dùng trong demo; 15/09–22/09/2026).
   Với vé máy bay: trip.com liệt kê chuyến này kèm giá ở các ngày trong `datesSeen`. Luồng đặt chỗ thật phải gọi lại nguồn.
2. **`unitPrice = null` không phải là miễn phí.** 300 sản phẩm còn `null`; 300 là điểm trip.com (tham quan, golf)
   không hiện giá — **chưa rõ có bán vé hay không** (`attributes.ticketed` vắng mặt). Web cần trạng thái hiển thị riêng, không quy về 0 đồng.
3. **Giá là một lần hỏi giá tại một thời điểm.** Khách sạn: nhận phòng 2026-10-15, 1 đêm, 2 người lớn (9.095 sản phẩm; ngày khác: 2026-09-29, 2026-10-23, 2026-11-14, 2026-11-20). Vé máy bay: giá tham khảo theo ngày trip.com liệt kê. Đọc `priceDate` / `datesSeen` thay vì giả định.
4. **`destination` ≠ `province`.** `destination` là nhãn du lịch dùng để lọc và gợi ý (Hội An, Sa Pa);
   `attributes.province` là đơn vị hành chính (Quảng Nam, Lào Cai).

## 3. `attributes` theo nhóm

Độ phủ tính trên toàn bộ 11.387 sản phẩm. Chỉ liệt kê khoá quan trọng và có mặt trong catalog; đầy đủ ở `template.json`.

### 3.1 Định danh và liên kết

| Khoá | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `level` | enum | 93% | `property` / `room` cho khách sạn; `route` / `flight` cho vé máy bay. Điểm tham quan, combo, golf không có |
| `parentProductId` | string | 72% | `productId` của khách sạn cha (hạng phòng) hoặc tuyến bay cha (chuyến cụ thể) |
| `url` | URL | 100% | Trang nguồn của sản phẩm |
| `fieldSources` | object | 100% | Trường nào lấy từ nguồn nào, ví dụ `{"unitPrice": "booking.com", "description": "vinpearl"}` |
| `sameAs` | array | 2% | `sourceRef` của các bản ghi cùng sản phẩm ở nguồn khác đã gộp vào dòng này |
| `mergedInto` | string | mới | Chỉ có trong `cdp.products`, không có trong `products.jsonl`: `product_id` của dòng mà dòng này đã được gộp vào khi nạp DB (nạp theo phần hoặc lượt sau gộp trùng hai dòng đã nạp riêng); dòng mang khoá này có `available = false` và không được tra theo `sourceRef`/`sameAs` nữa. Xem `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md` (L4) |
| `brand` | string | 5% | Thương hiệu, chủ yếu là `Vinpearl` |

### 3.2 Vị trí

| Khoá | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `latitude` | number | 100% | Vĩ độ WGS84 (kinh độ: `longitude`) |
| `locationSource` | enum | 100% | Nguồn toạ độ (bảng bên dưới) |
| `locationPrecision` | enum | 100% | `exact` = vị trí riêng của sản phẩm · `venue` = khu vui chơi/sân golf dùng vé · `airport` = sân bay đến · `poi` = điểm tham quan trip.com · `destination` = tâm điểm đến (combo bay+ở trip.com, KHÔNG có toạ độ khách sạn thật — không dùng để tính khoảng cách/hiển thị "cách bạn N km") |
| `address` | string | 91% | Địa chỉ nguồn cung cấp |
| `province` | string | 88% | Đơn vị hành chính (khác `destination`) |
| `city` | string | 88% | Thành phố theo địa chỉ |
| `locationWarning` | string | <1% | Toạ độ bất thường; chỉ còn ở sản phẩm Vinpearl được giữ lại (dòng khác có cảnh báo đã bị xoá, xem `excluded_location.csv`) |

### 3.3 Mô tả

| Khoá | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `descriptionLang` | enum | 100% | Luôn là `vi` sau chuẩn hoá. Ước lượng theo tỷ lệ ký tự có dấu, không phải kiểm tra ngôn ngữ đầy đủ |
| `descriptionSource` | string | 76% | **Có giá trị nghĩa là mô tả được tự sinh**, không phải văn bản gốc của nguồn. Xem mục 5 |
| `descriptionOriginal` | string | 1% | Văn bản gốc của nguồn khi mô tả đã được dựng lại bằng tiếng Việt |
| `policies` | object | 3% | Điều khoản, chính sách hoàn huỷ, hướng dẫn sử dụng — tách khỏi `description` để không làm nhiễu embedding |
| `conditions` | array | 67% | Điều kiện đặt phòng của hạng phòng OTA, mỗi phần tử một điều kiện |
| `highlights` | array | 14% | Điểm nổi bật do nguồn gắn |

### 3.4 Giá và tình trạng

| Khoá | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `priceObservedAt` | datetime | 100% | Thời điểm quan sát giá |
| `priceQuery` | object | 88% | Khách sạn: điều kiện đã hỏi giá (ngày nhận/trả phòng, số người lớn, tiền tệ) |
| `priceDate` | date | 88% | Ngày nhận phòng đã dùng để hỏi giá. **Không đồng nhất**: đọc trường này thay vì giả định một ngày |
| `priceNights` | int | 88% | Số đêm của `unitPrice` — luôn là 1 |
| `priceAdults` | int | 20% | Số người lớn đã dùng để hỏi giá |
| `availabilityEvidenceKind` | enum | 88% | `queried_stay_not_a_general_date_range` = chỉ có bằng chứng cho đúng kỳ lưu trú đã hỏi, KHÔNG phải khoảng ngày còn phòng |
| `availabilityDatesObserved` | array | <1% | Các ngày nhận phòng đã có giá (chỉ khi crawl nhiều ngày) |
| `otaPrices` | object | 20% | Giá cùng sản phẩm ở các OTA khác, để so sánh |
| `vinpearlPrice` | number | <1% | Giá niêm yết trên vinpearl.com khi OTA thắng ở `unitPrice` |
| `memberPrices` | object | <1% | Giá theo hạng thành viên VinClub: `{"Gold": …, "Platinum": …, "Diamond": …}` |
| `adultOriginalPrice` | number | 3% | Vé Vinpearl: giá gốc người lớn trước khuyến mãi (`childPrice`: giá trẻ em) |
| `pricesByDate` | object | 1% | Hạng phòng Vinpearl: giá theo từng ngày nhận phòng đã hỏi |
| `availabilityRangeKind` | enum | 3% | `sale_window` = `availableFrom/To` là khoảng thời gian bán vé do Vinpearl công bố |

### 3.5 Đặc tính sản phẩm

| Khoá | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `starRating` | number | 62% | Khách sạn, hạng phòng |
| `starRatingType` | enum | 61% | `official` hoặc `booking_estimate` (Booking tự ước lượng) |
| `propertyType` | string | 34% | Loại hình lưu trú |
| `amenities` | array | 88% | Tiện ích, đã gộp từ nhiều nguồn nên có thể trùng ý |
| `images` | array | 28% | Ảnh phụ |
| `roomName` | string | 68% | Tên hạng phòng (`hotelName`: tên khách sạn cha) |
| `roomSizeM2` | int | 64% | Diện tích hạng phòng (m²) |
| `maxOccupancy` | int | 65% | Sức chứa tối đa của hạng phòng |
| `bed` | string | 66% | Loại giường, chuỗi tự do của nguồn |
| `familyFriendly` | bool | 35% | Suy ra từ tên, mô tả và tiện ích |
| `oceanView` | bool | 19% | Suy ra từ tên, mô tả và tiện ích |
| `openingHours` | string | 4% | Giờ mở cửa |
| `durationMinutes` | int | 7% | Thời lượng tham quan đề xuất, hoặc thời gian bay, quy về phút |
| `venue` | string | 3% | Địa điểm sử dụng vé, tra trong `collectors/venues.csv` |
| `ticketed` | bool | <1% | `true` = trip.com có hiện giá vé. **Vắng mặt = chưa rõ**: trip.com không hiện giá KHÔNG có nghĩa là miễn phí hay không bán vé |
| `audience` | array | 3% | Đối tượng phù hợp do nguồn gắn nhãn |
| `tags` | array | 2% | Nhãn loại hình của điểm tham quan trip.com |

### 3.6 Đánh giá — không có dữ liệu cá nhân

| Khoá | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `reviewScore` | number | 20% | Điểm trung bình (`reviewScoreScale`: thang 10 hoặc 5) |
| `reviewCount` | int | 22% | Số lượt đánh giá |
| `tripAdvisorRating` | number | <1% | Điểm TripAdvisor do vinpearl.com công bố (`tripAdvisorReviewCount`) |

### 3.7 Vé máy bay

| Khoá | Kiểu | Độ phủ | Ý nghĩa |
|---|---|---|---|
| `originCity` | string | 5% | Thành phố đi (`destinationCity`: thành phố đến) |
| `originDestination` | string | 5% | Nhãn điểm đến của đầu đi, để lọc theo cặp điểm đến |
| `destinationAirportName` | string | 5% | Tên sân bay đến |
| `originLatitude` | number | 5% | Toạ độ sân bay đi (`latitude`/`longitude` là sân bay đến) |
| `airline` | string | 4% | Hãng bay của chuyến (`airlines`: các hãng của tuyến) |
| `flightNumber` | string | 4% | Số hiệu chuyến bay |
| `departureTimeLocal` | string HH:MM | 4% | Giờ cất cánh **theo giờ Việt Nam** (`arrivalTimeLocal`: giờ hạ cánh) |
| `departureAt` | datetime | 4% | Thời điểm cất cánh của chuyến rẻ nhất đã thấy, kèm múi giờ `+07:00` (`arrivalAt`: hạ cánh) |
| `datesSeen` | array | 4% | Các ngày bay (giờ VN) mà trip.com liệt kê chuyến này; `availableFrom/To` là ngày nhỏ nhất/lớn nhất trong đây |
| `monthlyPrices` | object | <1% | Tuyến: giá trung bình một chiều theo tháng |
| `roundTripFrom` | number | <1% | Tuyến: giá khứ hồi rẻ nhất |
| `tripType` | string | Vé mới | `oneWay` hoặc `roundTrip`; khứ hồi vẫn là `level: flight` |
| `cabinClass` | string | Khi nguồn xác nhận | `ECONOMY`, `PREMIUM_ECONOMY`, `BUSINESS`, `FIRST`; thiếu thì chưa biết |
| `fixedDepartureDate` | boolean | Báo giá có ngày | `true`: job cào giữ nguyên ngày hai chặng; seed demo dời vào cửa sổ khi ngày đi nằm ngoài cửa sổ (`docs/prd/data-model.md` §3, `docs/spec/MOCK_DATA_SPEC.md` §2.1) |
| `returnFlight` | object | Khứ hồi | Số hiệu, hãng, sân bay đi/đến, `departureAt`, `arrivalAt` của chặng về |
| `returnDate`, `stayDays` | date, integer | Khứ hồi | Ngày về và khoảng ngày; không dùng để nhân giá hoặc ghi `using_date_to` |
| `priceValidUntil`, `priceObservedAt` | date, datetime | Khi nguồn cung cấp | Hạn báo giá và thời điểm quan sát; hết hạn không đồng nghĩa hết chỗ |
| `simulated` | boolean | Vé mô phỏng | `true`: vé Thương gia "(giá minh hoạ)" sinh khi nạp DB, `sourceRef` `demo:business:…`, `fieldSources.unitPrice = "mô phỏng"`; không phải giá nguồn (`docs/prd/data-model.md` §3). Normalizer không sinh khoá này |

Bổ sung phục vụ FR-CAT-01, FR-CAT-03 theo PRD đã chốt ngày 29/09/2026: mỗi hành trình/ngày/hạng là một sản phẩm đặt được riêng; giữ ID các vé cũ. `unitPrice` là giá toàn hành trình cho một người lớn (`priceBasis: per_person`), `quantity` là số khách. Giá cả nhóm không được chia để suy ra giá một người. Khứ hồi Trip chỉ nhận cặp đi/về đầy đủ, sân bay đảo chiều, ngày giờ hợp lệ và giá tổng từ nguồn; dữ liệu cũ thiếu hạng không được tự gán phổ thông/thương gia. Tất cả thuộc tính bổ sung nằm trong JSONB, giữ 13 trường cấp cao nhất.


**Nguồn toạ độ** (`locationSource`): `booking.com` 9.466 · `ourairports` 579 · `trip.com` 568 · `agoda.com` 496 · `vinpearl` 95 · `destination_center` 79 · `manual` 52 · `osm` 52.
**Độ chính xác** (`locationPrecision`): `exact` 10.432 · `airport` 579 · `venue` 297 · `destination` 79.
`venue` nghĩa là vé dùng chung toạ độ của khu vui chơi, không phải vị trí riêng — đúng bản chất của vé vào cửa.
52 toạ độ `manual` được xác minh tay, ghi nguồn trong `collectors/venues.csv` và `collectors/location_overrides.csv`.

**Hạng sao** (`starRating`): 5 sao 1.844 · 4 sao 2.090 · 3 sao 2.189 · 2 sao 761 · 1 sao 165; `starRatingType`: `official` 5.904 · `booking_estimate` 1.029 · `không ghi loại` 116.
**Hãng bay** (chuyến): VietJet Air 323 · Vietnam Airlines 79 · Sun PhuQuoc Airways 39 · Vietravel Airlines 25.
**Không có nội dung review, tên hay ảnh người đánh giá** trong catalog; chỉ giữ chỉ số tổng hợp (theo §3 handbook).

## 4. Các biến thể sản phẩm

| Biến thể | Số lượng | `level` | Đặc điểm |
|---|---|---|---|
| `hotel_property` | 2.321 | – | Cơ sở lưu trú. 1.823 cái có hạng phòng đi kèm (trung bình 4,2 hạng) |
| `hotel_room` | 7.738 | – | Hạng phòng, luôn có `parentProductId` |
| `attraction` | 610 | – | Điểm tham quan và vé: 372 từ trip · 199 từ vinpearl · 39 từ booking · 299 điểm trip.com chưa có giá |
| `flight` | 466 | – | Chuyến bay cụ thể, có `parentProductId` trỏ về tuyến |
| `flight_route` | 113 | – | Tuyến bay giữa hai thành phố |
| `combo` | 133 | – | Combo nghỉ dưỡng và vé vui chơi: 93 từ vinpearl · 39 từ trip · 1 từ booking |
| `golf` | 6 | – | Voucher / sân golf: 5 từ vinpearl · 1 từ trip · 1 điểm trip.com chưa có giá |

## 5. Mô tả tự sinh — đọc trước khi làm text builder

**8.611/11.387 mô tả (75,6%) là tự sinh** từ dữ liệu có cấu trúc của nguồn (không bịa), không phải văn bản gốc.
Nhận biết bằng `attributes.descriptionSource`:

| Giá trị `descriptionSource` | Số lượng | Dựng từ gì |
|---|---|---|
| `derived: thông tin phòng + mô tả khách sạn` | 7.515 | Hạng phòng OTA |
| `derived: dữ liệu chuyến bay trip.com` | 579 | Chặng bay, hãng, giờ bay, giá |
| `derived: loại hình, địa chỉ, giờ mở cửa, thời lượng` | 285 | Điểm tham quan thiếu phần giới thiệu |
| `derived: dựng tiếng Việt từ thuộc tính (mô tả gốc không phải tiếng Việt)` | 127 | Nguồn chỉ có mô tả tiếng Anh; bản gốc ở `descriptionOriginal` |
| `derived: mô tả gốc quá ngắn, bổ sung từ thông tin vé` | 57 | Vé Vinpearl |
| `derived: tên vé, thời lượng, đối tượng, địa điểm, giá` | 46 | Vé Vinpearl không có phần giới thiệu |
| `derived: thông tin phòng (mô tả gốc quá ngắn)` | 2 | Hạng phòng Vinpearl |

Câu mô tả khách sạn và câu mô tả vé máy bay **không nên xây theo cùng một cách** — chúng có cấu trúc khác
hẳn nhau, và điều này ảnh hưởng tới chất lượng embedding nhiều hơn cả việc chọn mô hình.
Hạng phòng cùng khách sạn có mô tả gần trùng nhau (đều ghép từ mô tả khách sạn): khi tìm kiếm nên gom kết quả theo `parentProductId`.

Độ dài mô tả trung vị theo loại (ký tự): hotel 978 · golf 733 · combo 233 · attraction 192 · flight 225.

## 6. Nguồn của từng trường

| Trường | Thứ tự ưu tiên | Lý do |
|---|---|---|
| `name`, `description` | vinpearl.com → booking.com (nếu tiếng Việt) → agoda.com | Mô tả Vinpearl là đầu vào embedding tốt nhất |
| `unitPrice`, `available` | nguồn có giá quan sát mới nhất; cùng ngày thì booking.com → agoda.com → vinpearl.com; vé máy bay và điểm tham quan: trip.com → Vinpearl | OTA sát thực tế hơn về giá; booking.com không cào lại được trên VPS nên giá cũ dần — giá mới hơn thắng (chốt 23/09/2026) |
| `availableFrom`, `availableTo` | Vinpearl `saleStartDate`/`saleEndDate`; vé máy bay: min/max `datesSeen` | Chỉ điền khi nguồn có bằng chứng; không sinh ngày |
| toạ độ | Nguồn chính → OpenStreetMap; sân bay từ OurAirports; 52 điểm xác minh tay |  |
| hạng sao, tiện ích | Nguồn chính, thiếu thì nguồn khác bù |  |

Mỗi sản phẩm mang `attributes.fieldSources` nên truy nguồn được từng giá trị.
Sản phẩm trùng giữa các nguồn đã gộp: 220 dòng trong `dedup_report.csv`.
Theo nguồn chính của dòng: booking 9.470 · trip 991 · agoda 498 · vinpearl 428.

Ngoài các quy tắc tự động, 10 sản phẩm bị loại sau khi soát tay (`collectors/excluded_products.csv`), và các dòng lỗi dữ liệu
(toạ độ sai/thiếu, hạng phòng giá phi lý, mồ côi) bị xoá tự động, danh sách ở `data/excluded_location.csv`.

## 7. Bắt đầu nhanh

```python
import json
from collections import Counter

products = [json.loads(l) for l in open("products.jsonl", encoding="utf-8")]

# lọc theo điểm đến và loại
hotels = [p for p in products if p["taxonomy"] == "hotel"
          and p["attributes"].get("level") == "property"
          and p["destination"] == "Nha Trang"]

# hạng phòng của một khách sạn
rooms_of = {}
for p in products:
    parent = p["attributes"].get("parentProductId")
    if parent:
        rooms_of.setdefault(parent, []).append(p)

# văn bản để embedding: bỏ qua hay giữ mô tả tự sinh là quyết định của bạn
texts = [p["description"] for p in products if not p["attributes"].get("descriptionSource")]

print(Counter(p["taxonomy"] for p in products))
```

Bộ mẫu để chạy thử nhanh: `sample/products-sample.jsonl`, xem `sample/README.md`.

## 8. Quy đổi sang hợp đồng API

Catalog và CDP clone giữ dữ liệu **đúng như nguồn**. `ProductSummary` của hợp đồng Backend
(`docs/spec/hop-dong-tich-hop-backend.md` §2) có vài trường dữ liệu không có sẵn ở dạng đó; tầng API quy đổi theo
các quy tắc dưới đây. Số liệu tính trên 11.387 sản phẩm thật.

### 8.1 `rating` và `reviewCount`

Hợp đồng dùng thang 0–5, một chữ số thập phân; `reviewCount` là `null` khi `rating` là `null`.

| Thứ tự | Nguồn | Có ở | Quy đổi |
|---|---|---|---|
| 1 | `reviewScore`, `reviewScoreScale` | 2.292 sản phẩm (2.291 thang 10) | `rating = round(reviewScore / reviewScoreScale × 5, 1)`, `reviewCount = reviewCount` |
| 2 | `tripAdvisorRating`, `tripAdvisorReviewCount` | 15 khách sạn Vinpearl, thang 5 | giữ nguyên |
| 3 | `rating`, `ratingScale` | 178 điểm tham quan (snapshot 2026-09-30, thang 5) | `rating = round(rating / ratingScale × 5, 1)`, `reviewCount = reviewCount` |
| — | không có điểm | còn lại | `rating = null`, `reviewCount = null` — kể cả khi có `reviewCount` |

Nguồn đầu tiên có điểm hợp lệ thắng; `reviewCount` luôn lấy cùng nguồn với `rating`. Code: `RATING_SOURCES` trong
`src/backend/app/domain/catalog/models.py`. Nguồn 3 có từ snapshot 2026-09-30: 178 sản phẩm trước đây chỉ có
`reviewCount` nay có thêm điểm.

### 8.2 `attributes`

Hợp đồng chỉ nhận một bộ khoá cố định, giá trị là `true` hoặc vắng mặt, riêng `starRating` là số nguyên. API
**chỉ trả các khoá trong bảng này**; mọi khoá khác trong `attributes` của catalog (mảng `amenities`, `nonstop: false`…) không đi ra ngoài.

| Khoá hợp đồng | Lấy từ | Số sản phẩm |
|---|---|---|
| `starRating` | `starRating` làm tròn xuống (4,5 sao → 4) | 7.049 |
| `oceanView`, `familyFriendly` | cùng tên, khi là `true` | 2.150, 3.985 |
| `directFlight` | `nonstop = true` | 315 |
| `wifi` | `amenities` khớp `wi-fi`, `wifi`, `internet` | 8.314 |
| `pool` | `amenities` khớp `hồ bơi`, `bể bơi`, `pool` | 2.450 |
| `freeBreakfast` | `amenities` khớp `bữa sáng`, `breakfast` — **cần loại mục ghi có phí** | 1.216 |
| `spa` | `amenities` khớp `spa`, `massage` | 868 |
| `parking` | `amenities` khớp `chỗ đỗ xe`, `bãi đỗ xe`, `parking` | 1.188 |
| `shuttle` | `amenities` khớp `đưa đón`, `shuttle` | 904 |
| `nearBeach` | `amenities` khớp `gần biển`, `sát biển`, `bãi biển`, `beachfront` | 159 |
| `privateBeach` | `amenities` khớp `bãi biển riêng`, `private beach` | 108 |
| `kidsClub` | `amenities` khớp `câu lạc bộ trẻ em`, `kids club` | 0 |
| `kidsPool`, `nearCenter`, `baggage`, `indoor`, `outdoor`, `waterPark`, `show`, `buffet`, `seaside`, `caddie` | chưa có nguồn | 0 |

So khớp trên chuỗi đã bỏ dấu và viết thường. Đây là suy luận từ từ khoá, không phải dữ liệu nguồn gắn nhãn sẵn.

### 8.3 `availableFrom`, `availableTo`

Hợp đồng bắt buộc cả hai để kiểm tra `DATE_OUT_OF_RANGE`. Hiện có 10.804/11.387 sản phẩm có giá trị
(hotel_room 7.622 · hotel_property 2.306 · flight 466 · attraction 199 · flight_route 113 · combo 93 · golf 5). **Không có** ở 131 khách sạn/hạng phòng, 411 điểm tham quan,
40 combo, 1 sân golf, 0 vé máy bay. Nguồn không công bố khoảng bán cho khách sạn và điểm trip.com,
nên không có giá trị đúng để điền — catalog để `null` thay vì bịa.
Đề xuất cho Backend: khi `null`, dùng cửa sổ đặt chỗ cấu hình được, từ hôm nay đến hôm nay + N ngày, và ghi rõ đây là giả định của bản demo.
Lưu ý khoảng của vé/combo/golf Vinpearl là **thời gian bán**, có thể hết hạn sớm hơn ngày demo: lọc `availableTo >= hôm nay`.
Khoảng của vé máy bay là **các ngày bay trip.com đã liệt kê** (cửa sổ quan sát), không phải lịch khai thác đầy đủ.

### 8.4 `unitPrice`

Hợp đồng ghi `unitPrice` bắt buộc là số nguyên, nhưng 300 sản phẩm có `unitPrice = null` (300 là điểm trip.com
không hiện giá, chưa rõ có bán vé không). Cần Backend chọn: cho phép `null` trong hợp đồng và hiển thị "chưa có giá", hoặc không trả các sản phẩm này ra API.
