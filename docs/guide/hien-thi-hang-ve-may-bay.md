# Hiển thị hạng vé máy bay (`fareClasses`) — đọc trước khi làm UI chọn hạng

Dành cho team FE. Phục vụ FR-CAT-01, FR-CAT-03 và grounding (NFR-REL-01). Tài liệu này chỉ hướng dẫn cách dùng; nguồn
sự thật là contract 1.9.0 (`src/shared/contracts/schemas/catalog.yaml`, schema `FareClass`) và
`docs/spec/hop-dong-tich-hop-backend.md` §2.2.1. Lệch nhau thì hai nguồn đó thắng.

## Thay đổi so với shape FE đưa

Giữ nguyên tên trường của FE: `code`, `name`, `price`, `soldOut`, `carryOnKg`, `checkedKg`, `mealIncluded`, `changeRule`.

Thêm:

| Trường | Vì sao |
|---|---|
| `productId` | Mỗi hạng / mỗi hành trình là một sản phẩm riêng; thêm giỏ bằng id này |
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
  }
]
```

## Lấy ở đâu

- `GET /products?parentProductId=<tuyến>` — backend gom hạng trên **toàn tuyến trước khi phân trang**, nên trang một dòng
  vẫn đủ hạng.
- `GET /products/{id}` của một chuyến bay (`level: flight`).
- Sản phẩm không phải vé máy bay: **không có** key `fareClasses`.

## Hiển thị

- **Mỗi hành trình một thẻ.** Các sản phẩm cùng hành trình trả về cùng một mảng `fareClasses`; đừng hiện mỗi `productId`
  một thẻ. Chọn hạng nằm trong thẻ.
- Thứ tự mảng đã sắp sẵn: `ECO`, `PRE`, `BUS`, `FST`, rồi hạng chưa rõ.
- **`null` = chưa biết.** Đừng hiện "0 kg", "không có suất ăn" hay "không đổi được". Hiện chưa nguồn nào có số liệu hành
  lý / suất ăn / đổi vé nên các trường này đang `null`.
- `soldOut: null` = chưa biết. `EXPIRED` **không** có nghĩa hết ghế — chỉ là báo giá cũ, chờ lượt cào sau làm mới.
- Vé trip.com: `code: null`, `name: "Giá rẻ nhất"`. Backend không đoán hạng; đừng gắn nhãn "Phổ thông".
- Chưa có giá thương gia. Thiếu hạng là chưa có dữ liệu, không phải hết chỗ. Khi có, hạng mới chỉ thêm phần tử vào mảng,
  shape không đổi.

## Vé khứ hồi

- `attributes.tripType`: `oneWay` \| `roundTrip`.
- `price` của vé khứ hồi là **giá tổng cả hai chiều cho một người lớn** (`priceBasis: per_person`).
- Chiều về: `attributes.returnFlight` và `attributes.returnDate`.

## Giỏ hàng — không đổi

Chọn hạng xong thì `POST /cart/items` với `productId` của hạng đó, `usingDate` là ngày bay chiều đi, `quantity` là số
khách. `AddCartItemRequest`, giỏ và đơn không đổi.

## Việc của FE

`FlightSummary` hiện đọc `attributes`; chuyển sang đọc `fareClasses` khi làm UI chọn hạng.
