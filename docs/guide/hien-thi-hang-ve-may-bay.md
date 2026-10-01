# Hiển thị hạng vé máy bay (`fareClasses`) — đọc trước khi làm UI chọn hạng

Dành cho team FE. Phục vụ FR-CAT-01, FR-CAT-03 và grounding (NFR-REL-01). Cập nhật 30/09/2026: thêm hạng Thương gia (thật và
mô phỏng "giá minh hoạ", xem mục [Vé Thương gia](#vé-thương-gia)). Tài liệu này chỉ hướng dẫn cách dùng; nguồn
sự thật là contract 1.9.0 (`src/shared/contracts/schemas/catalog.yaml`, schema `FareClass`) và
`docs/spec/hop-dong-tich-hop-backend.md` §2.2.1. Lệch nhau thì hai nguồn đó thắng.

## Thay đổi so với shape FE đưa

Giữ nguyên tên trường của FE: `code`, `name`, `price`, `soldOut`, `carryOnKg`, `checkedKg`, `mealIncluded`, `changeRule`.

Thêm:

| Trường | Vì sao |
|---|---|
| `productId` | Mỗi hạng / mỗi hành trình là một sản phẩm riêng; đặt vé bằng id này |
| `currency` | Như mọi giá khác trong contract |
| `priceValidUntil` | `YYYY-MM-DD`, hạn báo giá tại nguồn; `null` khi nguồn không có |
| `availabilityStatus` | `AVAILABLE` \| `EXPIRED` \| `NOT_CHECKED` — dùng lại enum sẵn có, cùng nghĩa với `ProductSummary.availabilityStatus` |

`code`: `ECO` \| `PRE` \| `BUS` \| `FST` \| `null`. Kiểu TypeScript đã có trong `src/frontend/src/types/api.gen.ts`.

Ví dụ (minh hoạ, `productId` giả; giá lấy theo khoảng của dữ liệu khứ hồi trip.com hiện có):

```json
"fareClasses": [
  {
    "productId": "<id>",
    "code": null,
    "name": "Giá rẻ nhất",
    "price": 1320000,
    "currency": "VND",
    "priceValidUntil": "2026-09-30",
    "availabilityStatus": "AVAILABLE",
    "soldOut": null,
    "carryOnKg": null,
    "checkedKg": null,
    "mealIncluded": null,
    "changeRule": null
  },
  {
    "productId": "<id vé mô phỏng>",
    "code": "BUS",
    "name": "Thương gia",
    "price": 3498000,
    "currency": "VND",
    "priceValidUntil": "2026-09-30",
    "availabilityStatus": "AVAILABLE",
    "soldOut": null,
    "carryOnKg": null,
    "checkedKg": null,
    "mealIncluded": null,
    "changeRule": null
  }
]
```

Phần tử `BUS` ở ví dụ là vé mô phỏng (1.320.000 × 2,65). `FareClass` không có cờ mô phỏng: xem cách nhận biết ở mục
[Vé Thương gia](#vé-thương-gia).

## Có dữ liệu trên máy

Snapshot mặc định `2026-09-30` có vé khứ hồi trip.com kèm hạng vé (cào ngày 30/09/2026). Sau khi pull:

```bash
make demo-db-reset
```

- Lệnh này xoá dữ liệu demo local (user thử, giỏ, đơn) rồi seed lại. Máy đã seed trước đây thì `make demo-db` dừng vì DB đã
  có dữ liệu.
- Khởi động lại backend. Không cần `make index-vectors`: chuyến bay không được index.
- Kết quả: 12.515 sản phẩm = 11.718 của snapshot + 797 vé Thương gia mô phỏng. **290 vé khứ hồi, tất cả đặt được** ở bất kỳ
  ngày seed nào, trong đó **268 vé hạng Phổ thông** (`code: ECO`); 507 vé một chiều / vé cũ. Mỗi vé này có thêm một vé
  Thương gia mô phỏng (`code: BUS`). Vé khứ hồi
  thuộc 29 tuyến giữa 6 thành phố: Hà Nội, TP.HCM, Đà Nẵng, Nha Trang, Đà Lạt, Phú Quốc.
- Vé có ngày đi ngoài cửa sổ 30 ngày được seed dời vào cửa sổ, cả hai chặng cùng số ngày; tên / `returnDate` đổi theo. Giá giữ
  nguyên của ngày gốc, nên chỉ là **giá tham khảo** trên máy dev. Dữ liệu thật trên VM giữ ngày thật và cào lại hằng ngày.
- Kiểm nhanh: `GET /api/v1/products?parentProductId=<id tuyến>` có vé tên "Khứ hồi …" kèm `fareClasses`.

## Lấy ở đâu

- `GET /products?parentProductId=<tuyến>` — backend gom hạng trên **toàn tuyến trước khi phân trang**, nên trang một dòng
  vẫn đủ hạng. `limit` tối đa 20 theo contract (`limit=100` trả `VALIDATION_ERROR`).
- `GET /products/{id}` của một chuyến bay (`level: flight`).
- Sản phẩm không phải vé máy bay: **không có** key `fareClasses`.

## Hiển thị

- **Mỗi hành trình một thẻ.** Các sản phẩm cùng hành trình trả về cùng một mảng `fareClasses`; đừng hiện mỗi `productId`
  một thẻ. Chọn hạng nằm trong thẻ.
- Thứ tự mảng đã sắp sẵn: `ECO`, `PRE`, `BUS`, `FST`, rồi hạng chưa rõ.
- **`null` = chưa biết.** Đừng hiện "0 kg", "không có suất ăn" hay "không đổi được". Hiện chưa nguồn nào có số liệu hành
  lý / suất ăn / đổi vé nên các trường này đang `null`.
- `soldOut: null` = chưa biết. `EXPIRED` **không** có nghĩa hết ghế — chỉ là báo giá cũ, chờ lượt cào sau làm mới.
  Vé khứ hồi trong snapshot có `priceValidUntil: 2026-10-01`, nên từ 02/10 trên máy dev hiện `EXPIRED` nhưng vẫn
  đặt được. Nên hiện nhãn kiểu "Giá có thể đã thay đổi", không khoá nút đặt.
- Hạng lấy từ nguồn: vé khứ hồi trip.com mà trang ghi "Economy class" có `code: ECO`, `name: "Phổ thông"`. Vé một chiều và
  22 vé khứ hồi trang không ghi hạng: `code: null`, `name: "Giá rẻ nhất"`. Backend không đoán hạng; đừng gắn nhãn "Phổ thông"
  cho `code: null`.
- Thiếu một hạng là chưa có dữ liệu, không phải hết chỗ. Hạng mới chỉ thêm phần tử vào mảng, shape không đổi.

## Vé Thương gia

Có hai loại, cùng `code: BUS`, `name: "Thương gia"`; shape `fareClasses` không đổi (quy tắc: `docs/prd/data-model.md` §3).

| | Thật | Mô phỏng ("giá minh hoạ") |
|---|---|---|
| Nguồn giá | Trip.com, đọc tay 30/09/2026 | Giá vé gốc (Phổ thông / Giá rẻ nhất) × 2,65, làm tròn nghìn |
| Số lượng | 43 vé một chiều, 6 tuyến, **chỉ ngày bay 15/10/2026** | Mỗi vé có số hiệu chuyến một vé (seed local: 797) |
| `attributes.simulated` | không có | `true` |
| Tên sản phẩm | "… — Thương gia (2026-10-15)" | "… — Thương gia (giá minh hoạ)" |
| `attributes.fieldSources.unitPrice` | `trip.com` | `mô phỏng` |

- **Nhận biết vé mô phỏng:** `FareClass` không có cờ riêng. Lấy `productId` của phần tử `BUS`, tra trong danh sách
  `GET /products?parentProductId=<tuyến>` (hoặc `GET /products/{id}`): `attributes.simulated === true`, hoặc tên kết thúc
  bằng "(giá minh hoạ)".
- **Bắt buộc:** vé mô phỏng phải có nhãn **"Giá minh hoạ"** cạnh giá, ở thẻ chọn hạng, giỏ và trang đơn. Không trình bày như
  giá hãng bán.
- Vé mô phỏng chép ngày, giờ, chiều về, `available`, cửa sổ đặt chỗ và `priceValidUntil` của vé gốc, nên cùng
  `availabilityStatus` với hạng Phổ thông cạnh nó (vé gốc `EXPIRED` thì vé mô phỏng cũng `EXPIRED`).
- Có vé Thương gia thật cùng hành trình và ngày thì vé mô phỏng bị khoá (`available: false`), chỉ vé thật được bán.
- Đặt như mọi hạng khác (`productId` của phần tử `BUS`). Thanh toán trên staging là Stripe test.
- **Trên DB VM (web staging):** mặc định có, từ lượt nạp đầu tiên của job sau khi bản này được deploy
  ([guide deploy](trien-khai-job-cao-du-lieu.md#vé-thương-gia-mô-phỏng-trên-vm)). Trước đó staging chỉ có 43 vé thật ngày
  15/10. Đội deploy tắt (`SIMULATED_BUSINESS_FARES=0`) thì vé mô phỏng chuyển `available: false`, không biến mất khỏi đơn cũ.

## Vé khứ hồi

- `attributes.tripType`: `oneWay` \| `roundTrip`. Vé cũ (snapshot 23/09) không có khoá này: coi là một chiều.
- `price` của vé khứ hồi là **giá tổng cả hai chiều cho một người lớn** (`priceBasis: per_person`).
- Chiều về: `attributes.returnFlight` và `attributes.returnDate`.

## Đặt vé — không qua giỏ hàng

Vé máy bay không vào giỏ (từ 2026-10-01, `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`): `POST /cart/items` với vé
máy bay trả `422 DIRECT_BOOKING_ONLY`. Chọn hạng xong thì `POST /booking-drafts` với `items[]`, mỗi chặng một phần tử có
`productId` của hạng đó, `usingDate` là ngày bay và `guests` (hoặc `quantity` là số khách), rồi mở
`/checkout?draft=<draftId>`. Hình dạng một phần tử vẫn là `AddCartItemRequest`; đơn không đổi.

## Việc của FE

`FlightSummary` hiện đọc `attributes`; chuyển sang đọc `fareClasses` khi làm UI chọn hạng.
