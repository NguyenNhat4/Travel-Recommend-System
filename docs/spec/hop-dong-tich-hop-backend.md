# Hợp đồng tích hợp Backend

> **MVP 1.2.0:** ưu tiên hiển thị recommendation; [bộ trường tối thiểu](mvp-minimal-fields-1.2.0.md) và OpenAPI hiện hành thay thế danh sách required/optional cũ bên dưới. Các trường mở rộng vẫn được hỗ trợ nhưng không bắt buộc gửi.

**Phiên bản:** 1.0  
**Người tạo:** mihhquan  
**Bên sử dụng:** Team Web, Team Agent  
**Bên phụ thuộc:** Team Recommendation/Search, Team Data  
**Giao thức:** REST/JSON qua HTTP  
**Xác thực:** JWT Bearer Token, không bắt buộc với các API đọc  
**Mã hóa:** UTF-8  
**Tiền tệ mặc định:** VND  
**Prefix:** `/api/v1`  
**Ngày:** `2026-09-16`  
**Múi giờ:** `Asia/Ho_Chi_Minh`

> Tài liệu này chốt hợp đồng dữ liệu cho **năm nhóm API web-facing**: Auth, Catalog, Search, Recommendation và Booking, cộng endpoint ghi hành vi `POST /api/v1/events` (§7.5). Bề mặt Itinerary Assistant nằm ở `hop-dong-tich-hop-itinerary-assistant.md` và không được lặp lại ở đây. Tích hợp với CDP clone nằm ở `hop-dong-tich-hop-cdp.md`.

---

## 1. Phạm vi trách nhiệm

### 1.1. Backend chịu trách nhiệm

- Đăng ký, đăng nhập, phát hành JWT và ánh xạ mỗi tài khoản web tới đúng một `cdpUserId`.
- Cung cấp danh sách và chi tiết sản phẩm từ catalog, kể cả cho khách chưa đăng nhập.
- Cung cấp semantic search trên catalog kèm bộ lọc điểm đến, danh mục, khoảng giá và trạng thái còn chỗ.
- Cung cấp gợi ý cá nhân hóa kèm mảng `because` giải thích được, và fallback phổ biến cho khách ẩn danh hoặc cold start.
- Quản lý giỏ hàng phía server, khóa theo `cdpUserId`.
- Xử lý checkout: giữ chỗ, thanh toán Stripe (test mode, V-OTA là MoR), huỷ và hoàn tiền; sinh `referenceCode` và trả về đơn đặt đọc lại được.
- Là cổng duy nhất giữa Web và CDP clone: ghi `product_view`, `search`, `add_to_cart` ở nền và `purchase` đồng bộ qua `CdpClient` (`hop-dong-tich-hop-cdp.md`).
- Là nguồn chính thức của giá và tình trạng còn chỗ tại thời điểm checkout.
- Giữ ổn định tên trường trong `/api/v1` và thông báo trước mọi thay đổi enum.

### 1.2. Bên tiêu thụ chịu trách nhiệm

**Team Web:**

- Sinh kiểu TypeScript từ `src/shared/contracts/openapi.yaml`, không tự định nghĩa lại payload trong từng feature.
- Tự dựng đường dẫn chi tiết sản phẩm `/product/{productId}`; backend không trả `bookingUrl`.
- Format tiền tệ, đơn vị giá và nhãn `attributes` sang tiếng Việt ở phía client.
- Không dùng state phía client làm nguồn chính thức cho giá và `available`.

**Team Agent:**

- Chỉ gọi Search, Recommendation và Similar (Similar chỉ ở lượt đổi món, `hop-dong-tich-hop-itinerary-assistant.md` §2.5) qua port của tầng application; không truy cập trực tiếp bảng dữ liệu. Với dữ liệu thật, tool gọi engine trong cùng tiến trình (`ITINERARY_DATA_MODE=inprocess`); gọi HTTP (`=http`) chỉ còn là mode tuỳ chọn. Output của tool khớp response của route (`hop-dong-tich-hop-itinerary-assistant.md` §2).
- Sao chép nguyên `productId`, `name` và `unitPrice` từ response; không tự tạo sản phẩm.
- Không tạo booking trong MVP v1; bàn giao sang Web bằng `productId`.

### 1.3. Ngoài phạm vi của tài liệu này

- API CDP clone, cách ghi nền, bù trừ `purchase`, đường lui khi CDP lỗi: `hop-dong-tich-hop-cdp.md` và `src/shared/contracts/cdp-clone.openapi.yaml`.
- Insider clone: `POST /user/v1/upsert`, `PATCH /user/v1/identity`, `POST /user/v1/profile`, `POST /raw/v1/export` và các quy tắc TTL 90/730 ngày.
- Toàn bộ bề mặt `POST /api/v1/assistant/itineraries`.
- Sinh embedding, quản lý vector index và thuật toán xếp hạng. Tài liệu này chỉ chốt *hình dạng* response, không chốt cách tính điểm.

**Mâu thuẫn cần Team Backend xử lý:** `src/backend/app/core/config.py` đang đặt `database_url="sqlite:///./data/app.db"` và `chroma_persist_dir`, trong khi `architecture-repo.md` §2 và handbook §5 quyết định PostgreSQL + pgvector. Hợp đồng này viết theo quyết định PostgreSQL + pgvector.

---

## 2. Mô hình dữ liệu dùng chung

### 2.1. Nguồn gốc tên trường

Tên trường **bám nguyên handbook §6**, vì handbook yêu cầu CDP clone "phản chiếu CDP của V-OTA từng trường một — cùng tên, cùng kiểu, cùng hình dạng". Một trường đặt lại tên ở tầng API là một cái bẫy cho đội tiếp quản production sau này.

Hệ quả: `hop-dong-tich-hop-itinerary-assistant.md` §2.1 và §2.4 đang dùng bộ tên khác và **phải sửa theo** — danh sách thay đổi ở §9.

### 2.2. `ProductSummary`

Payload dùng cho mọi danh sách: kết quả tìm kiếm, carousel gợi ý, sản phẩm tương tự, mục trong giỏ.

```json
{
  "productId": "nt-h-01",
  "name": "Vinpearl Resort Nha Trang - Deluxe Ocean View",
  "taxonomy": "hotel",
  "destination": "Nha Trang",
  "unitPrice": 3400000,
  "currency": "VND",
  "available": true,
  "availableFrom": "2026-10-01",
  "availableTo": "2027-03-31",
  "imageUrl": "https://cdn.example.vn/nt-h-01.jpg",
  "rating": 4.6,
  "reviewCount": 1293,
  "attributes": {
    "starRating": 5,
    "oceanView": true,
    "privateBeach": true,
    "familyFriendly": true
  }
}
```

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---:|---|
| `productId` | string | Có | Định danh duy nhất và ổn định trong toàn hệ thống |
| `name` | string | Có | Tên hiển thị, đã chuẩn hóa từ nguồn crawl |
| `taxonomy` | enum | Có | Xem §2.4 |
| `destination` | string | Có | Tên điểm đến đã chuẩn hóa, xem §2.6 |
| `unitPrice` | integer | Có | Giá một đơn vị, số nguyên VND, không có phần thập phân |
| `currency` | string | Có | Luôn là `"VND"` trong MVP |
| `available` | boolean | Có | Còn chỗ tại thời điểm truy vấn |
| `availableFrom` | date | Có | `YYYY-MM-DD`, ngày đầu tiên dùng được |
| `availableTo` | date | Có | `YYYY-MM-DD`, ngày cuối cùng dùng được |
| `imageUrl` | string \| null | Không | Ảnh đại diện. `null` thì client dùng placeholder theo `taxonomy` |
| `rating` | number \| null | Không | Điểm đánh giá tổng hợp 0–5, một chữ số thập phân. `null` khi nguồn crawl không có |
| `reviewCount` | integer \| null | Không | Số lượt đánh giá. `null` đi kèm `rating: null` |
| `attributes` | object | Có | Object thuộc tính, xem §2.5. Có thể là object rỗng `{}` |
| `fareClasses` | array \| vắng | Không | Chỉ vé máy bay tầng con (`level: flight`): các hạng vé của cùng hành trình, xem §2.2.1 (contract 1.9.0) |

#### 2.2.1. `fareClasses` — hạng vé của một hành trình bay

Mỗi hạng vé là một sản phẩm `level: flight` riêng (đề xuất đã chốt `docs/prd/update-archive/2026-09-29-ve-khu-hoi-dat-duoc.md`).
Backend gom các sản phẩm cùng tuyến có **cùng hành trình** (cùng loại vé, cùng số hiệu chuyến và giờ đi; khứ hồi thêm chuyến
và giờ về) thành mảng `fareClasses`, trả ở `GET /products?parentProductId=<tuyến>` (gom trên mọi chuyến của tuyến, trước
khi phân trang) và `GET /products/{id}`. Các sản phẩm cùng hành trình có cùng mảng; Web hiển thị một thẻ cho mỗi hành trình
và thêm giỏ bằng `productId` của hạng đã chọn (`AddCartItemRequest` không đổi).

| Trường | Ý nghĩa |
|---|---|
| `productId` | Sản phẩm của hạng này |
| `code`, `name` | `ECO`/`PRE`/`BUS`/`FST` từ `attributes.cabinClass`; `null` + "Giá rẻ nhất" khi nguồn không ghi hạng (trip.com). Không mặc định phổ thông |
| `price`, `currency` | `unitPrice` của sản phẩm; khứ hồi là giá tổng cho một người lớn |
| `priceValidUntil` | Hạn báo giá tại nguồn, `null` khi nguồn không có |
| `availabilityStatus` | `AVAILABLE` (còn mở bán, báo giá còn hạn) · `EXPIRED` (quá `priceValidUntil`, ngày Việt Nam) · `NOT_CHECKED` |
| `soldOut`, `carryOnKg`, `checkedKg`, `mealIncluded`, `changeRule` | `null` = chưa biết: chưa nguồn nào cung cấp. Báo giá hết hạn không có nghĩa `soldOut` |

Chỉ liệt kê hạng có báo giá thật; thiếu hạng nào (vd. thương gia) là chưa có dữ liệu, không phải hết chỗ. Không tạo giá
thay thế cho hạng thiếu (grounding).

### 2.3. `ProductDetail`

Kế thừa toàn bộ `ProductSummary`, thêm:

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---:|---|
| `description` | string | Có | Mô tả tiếng Việt. Chuỗi rỗng nếu nguồn crawl thiếu |
| `sourceRef` | string \| null | Không | Nguồn của bản ghi, ví dụ `"vinpearl:HTNHA001"`. Chỉ hiện ở chế độ debug, không hiển thị cho khách |

`ProductDetail` **không** có thêm ảnh. MVP chỉ có một `imageUrl` — xem D11 ở §10.

### 2.4. Enum `taxonomy`

```text
hotel
flight
attraction
combo
golf
```

Viết thường, đúng như handbook §6. Giá trị `RESTAURANT` trong hợp đồng Agent §2.3 **không tồn tại** trong catalog và phải bỏ; `golf` thì ngược lại, có trong catalog nhưng thiếu ở hợp đồng Agent.

Team Agent chỉ tạo khoảng nghỉ ăn uống chung, không nêu tên nhà hàng, vì catalog không có `taxonomy` nhà hàng.

### 2.5. Từ vựng `attributes`

`attributes` là **object**, không phải mảng. Mọi giá trị là `true` hoặc vắng mặt, trừ `starRating` là integer. Không bao giờ gửi `false` — thuộc tính không có thì bỏ hẳn key, để client render "tag có mặt" mà không phải lọc.

| Key | Kiểu | Nhãn tiếng Việt (tham khảo) |
|---|---|---|
| `starRating` | integer 1–5 | Hạng sao |
| `oceanView` | true | Hướng biển |
| `privateBeach` | true | Bãi biển riêng |
| `pool` | true | Hồ bơi |
| `kidsPool` | true | Hồ bơi trẻ em |
| `familyFriendly` | true | Phù hợp gia đình |
| `kidsClub` | true | Khu vui chơi trẻ em |
| `spa` | true | Spa |
| `freeBreakfast` | true | Bữa sáng miễn phí |
| `nearBeach` | true | Gần biển |
| `nearCenter` | true | Gần trung tâm |
| `shuttle` | true | Xe đưa đón |
| `wifi` | true | Wi-Fi miễn phí |
| `parking` | true | Chỗ đậu xe |
| `directFlight` | true | Bay thẳng |
| `baggage` | true | Có hành lý ký gửi |
| `indoor` | true | Trong nhà |
| `outdoor` | true | Ngoài trời |
| `waterPark` | true | Công viên nước |
| `show` | true | Có suất diễn |
| `buffet` | true | Có buffet |
| `seaside` | true | Cạnh biển |
| `caddie` | true | Có caddie |

Nhãn tiếng Việt do client sở hữu (`prototype/data.js` `ATTR_LABELS`, `docs/product.md` §4.0). Backend chỉ trả key.

Thêm key mới là thay đổi tương thích ngược, được phép trong v1. Client gặp key lạ thì **bỏ qua im lặng**, không hiển thị tên key thô.

### 2.6. Quy ước giá, đơn vị và điểm đến

**Giá là số nguyên.** `unitPrice` luôn là integer VND. Backend không trả chuỗi đã format; trường `priceString` của handbook §7 bị bỏ. Lý do: `priceString` khóa cứng locale vào payload, trong khi client đã có `Intl.NumberFormat('vi-VN')`.

**Đơn vị giá là quy tắc dẫn xuất từ `taxonomy`, không phải một trường.** Đây là thứ thay thế cho `price.unit` của hợp đồng Agent:

| `taxonomy` | Hậu tố hiển thị | Công thức thành tiền |
|---|---|---|
| `hotel` | `/ đêm` | `unitPrice × nights × quantity` (`quantity` là số phòng; số khách không đổi giá) |
| `flight` | `/ khách` | `unitPrice × quantity` (mọi hành khách trả `unitPrice`, kể cả trẻ em) |
| `attraction` | `/ khách` | `unitPrice × người lớn + giá vé trẻ em × trẻ em`; không có trẻ em thì `unitPrice × quantity` |
| `combo` | `/ gói` | `unitPrice × quantity` |
| `golf` | `/ lượt` | như `attraction` |

Từ OpenAPI 1.10.0, thành tiền của một mục là **tổng các dòng giá** `fares[].amount` (`ADULT`, `CHILD`, `ROOM`, `PACKAGE`); các công thức trên là kết quả của dòng giá theo từng `taxonomy`. Giá vé trẻ em là `attributes.childPrice` khi `0 < childPrice ≤ unitPrice`, còn lại trẻ em trả `unitPrice`. Chi tiết và ví dụ: `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §4.3, §4.4.

**Điểm đến** là chuỗi tiếng Việt có dấu, đã chuẩn hóa theo danh sách thống nhất giữa các team. Lấy danh sách hiện hành qua `GET /api/v1/destinations` (§4.4), không hardcode phía client.

**Ngày** dùng `YYYY-MM-DD`. **Thời điểm** dùng ISO 8601 UTC kết thúc bằng `Z`, ví dụ `2026-09-16T08:00:00Z`.

---

## 3. Auth

Theo handbook §8: xác thực tồn tại để bản demo cho những người khác nhau thấy những gợi ý khác nhau. Không có OAuth, không xác minh email, không đặt lại mật khẩu, không phân quyền.

> **Cơ chế xác thực và mã lỗi auth:** xem `docs/spec/hop-dong-tich-hop-auth.md` (hybrid: cookie phiên ở BFF + JWT RS256 nội bộ). Bốn endpoint dưới đây giữ nguyên shape cho client nội bộ, Agent, CLI và test; web đi qua BFF `/api/auth/*` và nhóm `/auth/session*` (auth §4, §5).

### 3.1. Đăng ký

```http
POST /api/v1/auth/register
Content-Type: application/json
```

#### Request

```json
{
  "email": "giahuy@example.vn",
  "password": "matkhau12345",
  "fullName": "Phạm Gia Huy"
}
```

| Trường | Bắt buộc | Quy tắc |
|---|---:|---|
| `email` | Có | Định dạng email hợp lệ, không phân biệt hoa thường, lưu dạng thường |
| `password` | Có | 8–128 ký tự, chính sách ở auth §8.3. Băm bằng Argon2id (auth §8.1), không bao giờ trả về hoặc ghi log |
| `fullName` | Có | 1–100 ký tự |

#### Response `201`

Giống hệt response của §3.2 — đăng ký thành công thì tự đăng nhập luôn.

Backend sinh một `cdpUserId` mới cho tài khoản này. Tài khoản mới có 0 event, nên `/recommendations` sẽ trả `coldStart: true` và `strategy: "popular"`.

### 3.2. Đăng nhập

```http
POST /api/v1/auth/login
Content-Type: application/json
```

#### Request

```json
{
  "email": "minhanh@example.vn",
  "password": "matkhau12345"
}
```

#### Response `200`

```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIs...",
  "tokenType": "Bearer",
  "expiresIn": 3600,
  "user": {
    "userId": "web-user-001",
    "cdpUserId": "VP0092381",
    "email": "minhanh@example.vn",
    "fullName": "Nguyễn Minh Anh"
  }
}
```

`expiresIn` tính bằng giây. JWT hạn ngắn theo handbook §8; client xử lý 401 bằng modal đăng nhập lại và giữ nguyên state trang (`docs/product.md` §4.7.5).

Sai email hoặc sai mật khẩu đều trả cùng một lỗi `INVALID_CREDENTIALS` với cùng một thông điệp, không chỉ ra trường nào sai.

### 3.3. Thông tin phiên hiện tại

```http
GET /api/v1/auth/me
Authorization: Bearer <jwt>
```

Trả về đúng object `user` của §3.2. Dùng để khôi phục phiên sau khi tải lại trang.

```http
PATCH /api/v1/auth/me
Authorization: Bearer <jwt>
{ "fullName": "Trần Minh Quân", "phone": "0345484496" }
```

Sửa hồ sơ (FR-USR-04) và trả `AuthUser` mới. Chỉ trường có mặt mới đổi; `phone: null` xoá số. `fullName` 1–100 ký tự sau khi cắt khoảng trắng; `phone` đúng 10 chữ số bắt đầu bằng 0 (cùng quy tắc `Contact.phone` của đơn đặt chỗ, ràng buộc CHECK `users_phone_format` ở `app.users`). Body rỗng, trường lạ (kể cả `email`, `persona`), hoặc sai quy tắc đều là `422 VALIDATION_ERROR`, không đổi gì. Email không sửa được. Số điện thoại chỉ ở `app.users`, không gửi CDP, Insider hay Stripe. Use case `UpdateProfile` kiểm principal khớp hàng `app.users` như `GetCurrentUser`. Đổi mật khẩu dùng `PUT /auth/password` có sẵn.

### 3.4. Danh sách tài khoản demo — đã gỡ

`GET /api/v1/auth/demo-accounts` và bộ chọn tài khoản demo đã bị gỡ ngày 2026-09-24 (`docs/prd/update-archive/2026-09-24-go-bo-chon-tai-khoan-demo.md`). Tài khoản seed đăng nhập bằng `POST /auth/login` như mọi user. Giữ số mục để không đổi các tham chiếu tới §3.5.

### 3.5. JWT claims

```json
{
  "sub": "web-user-001",
  "cdp_user_id": "VP0092381",
  "email": "minhanh@example.vn",
  "exp": 1789000000,
  "iat": 1788996400
}
```

- `cdp_user_id` dùng `snake_case` vì đó là quy ước claim của JWT; trong body JSON thì luôn là `cdpUserId`. Đây là ngoại lệ duy nhất.
- Mọi API đọc (`/products`, `/search`, `/recommendations`, `/destinations`) **phải chấp nhận request không có JWT**. Không có JWT thì trả kết quả không cá nhân hóa.
- Mọi API ghi (`/cart/*`, `/bookings`) **bắt buộc** JWT, vì event phải khóa theo `cdpUserId` (handbook §10).

---

## 4. Catalog

### 4.1. Danh sách sản phẩm

```http
GET /api/v1/products?destination=Nha%20Trang&taxonomy=hotel&sort=popular&limit=20&offset=0
```

| Tham số | Bắt buộc | Mặc định | Ý nghĩa |
|---|---:|---|---|
| `destination` | Không | — | Lọc đúng một điểm đến |
| `taxonomy` | Không | — | Lọc đúng một danh mục |
| `parentProductId` | Không | — | Trả tầng con (hạng phòng, chuyến bay cụ thể) của sản phẩm cha này thay vì tầng cha |
| `availableOnly` | Không | `false` | `true` thì loại sản phẩm hết chỗ |
| `sort` | Không | `popular` | `popular` \| `price_asc` \| `price_desc` |
| `limit` | Không | `20` | 1–50 |
| `offset` | Không | `0` | — |

#### Response `200`

```json
{
  "results": [ { "productId": "nt-h-01", "...": "ProductSummary" } ],
  "total": 48,
  "limit": 20,
  "offset": 0,
  "requestId": "cat-01JXYZ"
}
```

Không có `parentProductId` thì chỉ trả **tầng cha** (search unit của `catalog.product_meta`: property, route, taxonomy không phân tầng), cùng tập với `/search`. Có `parentProductId` thì trả các **tầng con** của sản phẩm đó — đơn vị đặt chỗ mà Web thêm vào giỏ (FR-CAT-02: không đặt trên property, đặt qua hạng phòng); `sort=popular` với tầng con xếp theo giá tăng dần. Cha không tồn tại hoặc không có con → `results: []`.

**Bộ nhớ đệm HTTP:** áp dụng cho cả ba endpoint catalog công khai: `GET /products`, `GET /products/{id}` và `GET /products/{id}/similar`. Response `200` có `Cache-Control: public, max-age=60, s-maxage=300`. Use case không đọc người dùng nên kết quả giống nhau cho mọi người: trình duyệt giữ 60 giây, lớp cache trung gian giữ 5 phút để giảm tải origin. Lỗi (`400`, `404`, `409`, `503`) không có header này. Cùng quy ước với `GET /search/suggestions` trong `hop-dong-tich-hop-search-recommendation.md`. Trên response được cache, `requestId` trong body (`GET /products` và `/similar`) và header `X-Request-ID` là của request đã tạo bản cache, không phải của lần gọi hiện tại; lượt trúng cache không có log tương ứng.

`sort=popular` dùng baseline độ phổ biến theo số lượt `purchase` trong `events` (90 ngày, cùng số liệu RecSys dựng lúc khởi động qua `CdpHistoryReader`); hoà điểm thì sản phẩm gợi ý được (`is_recommendable`) và có giá đứng trước. Đây là nguồn dữ liệu cho section "Phổ biến tại các điểm đến Việt Nam" ở Home (`docs/product.md` §4.1.2 ④), section phải **luôn render được** kể cả khi `/recommendations` lỗi.

### 4.2. Chi tiết sản phẩm

```http
GET /api/v1/products/{productId}
```

Trả `ProductDetail` (§2.3) ở cấp cao nhất, không bọc thêm lớp. Mọi tầng đều đọc được (property, hạng phòng, route, chuyến bay).

`variantSummary` chỉ có ở sản phẩm cha (`attributes.level` là `property` hoặc `route`): `count` đếm mọi tầng con, `minPrice`/`maxPrice` tính trên tầng con đang mở bán và có giá, `maxOccupancy` lớn nhất trong các con. Property không có hạng phòng nào → `count: 0` (chỉ để xem). Sản phẩm không phân tầng → `variantSummary: null`.

Sản phẩm không tồn tại hoặc đã bị xóa khỏi catalog → `404` với code `PRODUCT_NOT_FOUND`. Đây là trường hợp "event trỏ tới sản phẩm đã bị xóa" mà handbook §6 gọi là "những rìa lộn xộn"; client hiển thị trang "Sản phẩm này không còn trên V-OTA" thay vì lỗi kỹ thuật.

**Endpoint này không ghi event `product_view`** — xem D3 ở §10.

### 4.3. Sản phẩm tương tự

```http
GET /api/v1/products/{productId}/similar?limit=8
```

#### Response `200`

```json
{
  "productId": "nt-h-01",
  "results": [ { "productId": "nt-h-02", "...": "ProductSummary", "score": 0.83 } ],
  "requestId": "sim-01JXYZ"
}
```

Cam kết:

1. Không bao giờ chứa chính `productId` được hỏi.
2. Chỉ dựa trên độ gần vector sản phẩm, **không** dùng user vector. Endpoint này giống nhau với mọi người dùng.
3. Trả mảng rỗng khi không đủ ứng viên; client ẩn hẳn section, không báo lỗi.
4. Id của tầng con được resolve lên cha: `productId` là cha, `resolvedFrom` là id đã gửi.

Lỗi: `limit` ngoài 1–20 → `400 VALIDATION_ERROR`; id không có trong catalog → `404 PRODUCT_NOT_FOUND`; có trong catalog nhưng chưa có vector → `409 PRODUCT_NOT_INDEXED`; RecSys chưa khởi động được → `503 SEARCH_UNAVAILABLE` (`retryable: true`). OpenAPI 1.8.0 khai báo đủ các mã này.

### 4.4. Danh sách điểm đến

```http
GET /api/v1/destinations
```

#### Response `200`

```json
{
  "destinations": [
    { "destination": "Nha Trang", "productCount": 9 },
    { "destination": "Phú Quốc", "productCount": 8 },
    { "destination": "Đà Nẵng", "productCount": 7 }
  ]
}
```

Đây là nguồn duy nhất cho bộ lọc điểm đến và cho chip gợi ý ở Home. Client không hardcode danh sách.

---

## 5. Search

### 5.1. `SearchRequest`

```http
GET /api/v1/search?q=khu%20nghỉ%20dưỡng&destination=Nha%20Trang&taxonomy=hotel
Authorization: Bearer <jwt>    # tùy chọn
```

Dùng `GET` theo endpoint RecSys hiện hành. Tham số `q` là truy vấn tự do; client phải URL-encode tiếng Việt. Route frontend `/search?q=…` và endpoint API có cùng tên tham số nhưng là hai bề mặt khác nhau.

`POST /api/v1/search` với body `SearchRequest` vẫn được giữ trong OpenAPI v1 để không phá client hiện có. GET là compatibility endpoint; Agent chỉ gọi nó ở mode `http` (tuỳ chọn), còn mode `inprocess` gọi thẳng engine Search trong tiến trình.

**Ghi hành vi:** request có JWT và `offset = 0` thì Backend ghi event `search` (`searchQuery` lấy từ `q` hoặc `query`) sang CDP ở nền. Đổi trang, không JWT, hoặc CDP lỗi đều không ảnh hưởng response. Agent không gắn danh tính khi tìm kiếm: mode `http` gọi endpoint này **không kèm JWT**, mode `inprocess` gọi engine không qua route nên không ghi event. Nhờ vậy lượt tìm của Agent không bị tính là hành vi người dùng (`hop-dong-tich-hop-cdp.md` §1.4).

#### Query parameters

| Trường | Bắt buộc | Mặc định | Ý nghĩa |
|---|---:|---|---|
| `q` | Có | — | Câu tự do tiếng Việt hoặc tiếng Anh, 1–500 ký tự |
| `destination` | Không | `null` | Lọc đúng một điểm đến |
| `taxonomy` | Không | `null` | Lọc đúng một danh mục |
| `limit` | Không | `20` | 1–50 |
| `offset` | Không | `0` | — |

Agent vẫn có schema tool giàu hơn (`priceMin`, `priceMax`, `starRatingMin`, `availableOnly`, `sort`) và hậu kiểm các ràng buộc đó sau retrieval; cả adapter `http` lẫn `inprocess` chỉ chuyển các tham số endpoint GET hỗ trợ: `query` (adapter `http` đổi thành `q`), `taxonomy`, `destination`, `limit`, `offset`.

### 5.2. `SearchResponse`

```json
{
  "results": [
    {
      "productId": "nt-h-01",
      "name": "Vinpearl Resort Nha Trang - Deluxe Ocean View",
      "taxonomy": "hotel",
      "destination": "Nha Trang",
      "unitPrice": 3400000,
      "currency": "VND",
      "available": true,
      "availableFrom": "2026-10-01",
      "availableTo": "2027-03-31",
      "imageUrl": "https://cdn.example.vn/nt-h-01.jpg",
      "rating": 4.6,
      "reviewCount": 1293,
      "attributes": { "starRating": 5, "oceanView": true, "familyFriendly": true },
      "score": 0.87
    }
  ],
  "total": 48,
  "limit": 20,
  "offset": 0,
  "topScore": 0.87,
  "facets": {
    "taxonomy": { "hotel": 21, "attraction": 12, "combo": 9, "flight": 6 },
    "destination": { "Nha Trang": 28, "Phú Quốc": 12, "Đà Nẵng": 8 }
  },
  "requestId": "search-01JXYZ"
}
```

| Trường | Ý nghĩa |
|---|---|
| `results[].score` | Điểm gần nghĩa, `0.0`–`1.0`. Chỉ hiển thị cho khách ở chế độ debug |
| `total` | Tổng số kết quả trước phân trang |
| `topScore` | `score` cao nhất trong toàn bộ kết quả, hoặc `null` khi rỗng |
| `facets` | Số lượng theo từng giá trị, tính trên **toàn bộ** kết quả chứ không riêng trang hiện tại. Dùng cho tab danh mục và bộ đếm bộ lọc |

### 5.3. Cam kết dữ liệu từ Search

1. `productId` là duy nhất và ổn định.
2. `name`, `unitPrice`, `available` và `attributes` lấy nguyên từ catalog, không được sửa trong tầng search.
3. `destination` được chuẩn hóa theo `GET /destinations`.
4. `taxonomy` chỉ dùng enum §2.4.
5. Khi `availableOnly=true`, kết quả không chứa sản phẩm hết chỗ.
6. Không có sản phẩm phù hợp thì trả `results: []` và `topScore: null`; không tự sinh dữ liệu thay thế.
7. `facets` luôn có mặt, kể cả khi `results` rỗng — khi đó mọi giá trị bằng 0.
8. Backend **trả số, không trả nhãn**: client tự quyết ngưỡng "kết quả yếu" dựa trên `topScore`. Ngưỡng khuyến nghị ban đầu là `0.35`, client sở hữu hằng số này.
9. Mục tiêu độ trễ p95 dưới 300 ms.
10. Thay đổi phá vỡ tương thích phải tạo phiên bản API mới.

---

## 6. Recommendation

### 6.1. Response

```http
GET /api/v1/recommendations?k=5&destination=Nha%20Trang
Authorization: Bearer <jwt>    # tùy chọn
```

| Tham số | Bắt buộc | Mặc định | Ý nghĩa |
|---|---:|---|---|
| `k` | Không | `5` | Số gợi ý, 1–20. Tên tham số theo handbook §7 |
| `destination` | Không | `null` | Giới hạn trong một điểm đến. Bỏ trống thì backend tự chọn theo `last_destination` của profile |

#### Response `200`

```json
{
  "cdpUserId": "VP0092381",
  "generatedAt": "2026-09-16T10:14:22Z",
  "modelVersion": "multilingual-e5-base-v1.2",
  "strategy": "cross_vertical",
  "nextVertical": "flight",
  "destination": "Nha Trang",
  "recommendations": [
    {
      "rank": 1,
      "productId": "nt-f-01",
      "name": "Vé máy bay Hà Nội – Cam Ranh (khứ hồi)",
      "taxonomy": "flight",
      "destination": "Nha Trang",
      "unitPrice": 1890000,
      "currency": "VND",
      "available": true,
      "imageUrl": "https://cdn.example.vn/nt-f-01.jpg",
      "attributes": { "directFlight": true, "baggage": true },
      "score": 0.81,
      "because": [
        {
          "productId": "nt-h-01",
          "productName": "Vinpearl Resort Nha Trang - Deluxe Ocean View",
          "imageUrl": "https://cdn.example.vn/nt-h-01.jpg",
          "event": "purchase",
          "daysAgo": 3,
          "contribution": 0.62
        }
      ]
    }
  ],
  "diagnostics": {
    "eventsUsed": 14,
    "coldStart": false,
    "excludedVerticals": ["hotel"],
    "latencyMs": 47
  }
}
```

Mỗi phần tử `recommendations[]` là một `ProductSummary` rút gọn (bỏ `availableFrom`/`availableTo`/`rating`/`reviewCount`) cộng thêm `rank`, `score` và `because`. Client cần đủ trường để render `ProductCard` mà không phải gọi thêm `/products/{id}`.

### 6.2. Enum `strategy`

```text
cross_vertical     Người dùng đã đặt một danh mục trong chuyến, hệ thống gợi ý danh mục còn thiếu
recent_activity    Có event gần đây nhưng chưa thành chuyến rõ ràng
dormant            Chuyến gần nhất cách đây trên 365 ngày (từ 2026-10-09; trước đó 90) — `diagnostics.dormant` vẫn là 90 ngày
popular            Không đủ dữ liệu cá nhân hóa, hoặc khách ẩn danh
long_term          Có lịch sử, không có chuyến đang mở, chưa quá ngưỡng dormant của engine
cold_start_content Có chuyến đang mở, tổng dưới 3 event dùng được, chưa mua gì trong chuyến
```

`long_term` và `cold_start_content` bổ sung ngày 2026-09-28 (OpenAPI 1.8.0): engine đã trả hai giá trị này nhưng contract thiếu. Điều kiện chính xác, và chỗ các dòng cũ lệch với engine (đang chờ quyết định), ở `hop-dong-tich-hop-search-recommendation.md` §4.4.

Quy tắc bắt buộc:

1. `strategy: "cross_vertical"` **phải** đi kèm `nextVertical` và `destination` khác `null`.
2. `strategy: "dormant"` phải có ít nhất một phần tử `because` với `daysAgo` trên 90.
3. `strategy: "popular"` thì `because` của mọi gợi ý là mảng rỗng.
4. Thêm giá trị `strategy` mới là thay đổi tương thích ngược nhưng **phải thông báo trước**, vì client map từng giá trị sang một tiêu đề section riêng (`docs/product.md` §5.3). Giá trị lạ được client map về tiêu đề chung "Có thể bạn quan tâm".

### 6.3. `because[]`

Handbook §7: mảng `because` "không phải đồ trang trí… là ranh giới giữa một cuộc tranh cãi và một chẩn đoán".

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
|---|---|---:|---|
| `productId` | string \| null | Có | Sản phẩm nguồn. `null` khi sản phẩm đã bị xóa khỏi catalog, hoặc khi `event` là `search` |
| `productName` | string | Có | Tên sản phẩm nguồn tại thời điểm sinh gợi ý. Với `event: "search"` thì là truy vấn người dùng đã gõ |
| `imageUrl` | string \| null | Có | Ảnh sản phẩm nguồn, cho popover "Vì sao?" |
| `event` | enum | Có | `purchase` \| `add_to_cart` \| `product_view` \| `search` |
| `daysAgo` | integer | Có | Số ngày tính tới `generatedAt` |
| `contribution` | number | Có | `0.0`–`1.0`, mức đóng góp vào điểm cuối |

Cam kết:

1. Mảng sắp giảm dần theo `contribution`; `because[0]` là lý do mạnh nhất và là thứ client hiển thị trên thẻ.
2. `productId` khác `null` thì sản phẩm đó phải tồn tại trong catalog và mở được `/product/{productId}`.
3. Sản phẩm nguồn đã bị xóa thì trả `productId: null` và `imageUrl: null`, nhưng vẫn giữ `productName` — client hiển thị chữ thường, không link.
4. `coldStart: true` thì `because` là mảng rỗng. Không bao giờ bịa lý do.
5. Mục tiêu độ trễ p95 dưới 300 ms.

### 6.4. `diagnostics`

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `eventsUsed` | integer | Số event của người dùng đã đưa vào tính toán |
| `coldStart` | boolean | `true` khi dưới 3 event |
| `excludedVerticals` | array\<taxonomy\> | Danh mục đã bị loại vì người dùng đã có trong chuyến. Đây là dữ liệu cho checklist "✓ Khách sạn / ○ Vé máy bay" |
| `latencyMs` | integer | Thời gian xử lý phía backend |

`diagnostics` luôn có mặt. Client chỉ hiển thị ở chế độ `?debug=1`, trừ `excludedVerticals` và `coldStart` vốn được dùng để sinh chữ ở giao diện thường.

### 6.5. Hành vi với khách ẩn danh và cold start

**Không có endpoint `/recommendations/popular` riêng.** Cùng một endpoint phục vụ hai chế độ:

| Tình huống | Hành vi |
|---|---|
| Không có JWT | `200` với `cdpUserId: null`, `strategy: "popular"`, mọi `because` rỗng, `diagnostics.coldStart: true`, `eventsUsed: 0` |
| Có JWT, dưới 3 event | `200` với `cdpUserId` thật, `strategy: "popular"` hoặc `"recent_activity"` tùy có `because` hay không, `coldStart: true`. Engine hiện chạy khác dòng này, xem ghi chú lệch ở `hop-dong-tich-hop-search-recommendation.md` §4.4 |
| JWT sai hoặc hết hạn | `401` `INVALID_TOKEN`. Không âm thầm hạ xuống chế độ ẩn danh — client cần biết để mở modal đăng nhập lại |
| Có JWT, CDP clone lỗi hoặc timeout | `200` với `cdpUserId` thật, `strategy: "popular"`, mọi `because` rỗng, `coldStart: true`, `eventsUsed: 0`. Không trả `500` vì lỗi CDP (`hop-dong-tich-hop-cdp.md` §6) |

Lý do một endpoint: `docs/product.md` §4.1.3 yêu cầu Home của khách vãng lai và Home của P4 render cùng một section với cùng một component, chỉ khác chữ. Tách endpoint sẽ buộc client phải rẽ nhánh hai lần cho cùng một giao diện.

---

## 7. Booking

### 7.1. Giỏ hàng

Giỏ lưu **phía server**, khóa theo `cdpUserId`. Lý do: khi kiểm thử, nhiều tài khoản đăng nhập lần lượt trên cùng một máy; giỏ lưu ở client sẽ lẫn giữa các tài khoản.

**Giỏ chỉ giữ tour, trải nghiệm và tiện ích khác** (`attraction`, `golf`, `combo`). Khách sạn và vé máy bay có giá và chỗ đổi liên tục nên **chỉ đặt trực tiếp** qua đơn nháp (§7.1a): `POST /cart/items` với `hotel` hoặc `flight` trả `422 DIRECT_BOOKING_ONLY` (FR-BKG-01). Bộ luật đầy đủ: `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`.

```http
GET    /api/v1/cart
POST   /api/v1/cart/items
PATCH  /api/v1/cart/items/{cartItemId}
DELETE /api/v1/cart/items/{cartItemId}
Authorization: Bearer <jwt>    # người đã đăng nhập
X-Service-Token: <token>       # khách chưa đăng nhập: chỉ BFF gửi được,
X-Guest-Id: g_<22 ký tự>       # kèm mã khách do BFF phát (§7.1b)
```

Không có `Authorization` lẫn cặp header của khách thì `401`. Giỏ của khách chưa đăng nhập có `cdpUserId: null`, tối đa 20 mục.

#### `POST /api/v1/cart/items` — Request

```json
{
  "productId": "nt-a-01",
  "usingDate": "2026-10-16",
  "guests": { "adults": 2, "children": 1 }
}
```

Cùng hình dạng này là một phần tử của `items[]` khi tạo đơn nháp (§7.1a); `nights` và luật khách sạn bên dưới áp dụng ở đó.

| Trường | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `productId` | Có | Phải tồn tại và `available: true` |
| `usingDate` | Có | Ngày sử dụng, phải nằm trong `availableFrom`–`availableTo` |
| `quantity` | Có, trừ khi gửi `guests` cho dịch vụ tính theo người | Số phòng, số gói hoặc số khách, ≥ 1. Vé máy bay, vé tham quan, golf: gửi `guests` thì được bỏ `quantity` (Backend tính `adults + children`); gửi cả hai mà lệch thì `GUEST_COUNT_MISMATCH` |
| `guests` | Không | `{adults, children}`: `adults` ≥ 1, tổng ≤ 9; khách sạn tổng ≤ 9 × số phòng (mỗi phòng tối đa 9 khách) và số phòng ≤ 9 (vượt thì `ROOMS_TOO_MANY`, FR-BKG-08). Không gửi (client cũ): khách sạn và dịch vụ tính theo người mặc định `adults = quantity`, `children = 0`; combo mặc định `adults = 1` |
| `nights` | Chỉ với `hotel` | Số đêm, ≥ 1. Các `taxonomy` khác gửi `nights` thì bị bỏ qua |

Khách sạn: mỗi phòng cần ít nhất 1 người lớn (`adults ≥ quantity`) và `adults + children ≤ maxOccupancy × quantity` khi hạng phòng có `maxOccupancy`. Vi phạm thì `400 VALIDATION_ERROR` với `details.fields[].reason` (`ADULT_REQUIRED`, `PARTY_TOO_LARGE`, `OCCUPANCY_EXCEEDED`, `GUEST_COUNT_MISMATCH`). Bộ luật R-CRT-01…05: `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §5.5. `PATCH` nhận cùng các trường (ít nhất một trường).

Thêm thành công thì Backend ghi event `add_to_cart` sang CDP ở nền, với `taxonomy` và `unitPrice` lấy từ catalog. Thêm thất bại không ghi event; `PATCH`/`DELETE` không ghi event; CDP lỗi không ảnh hưởng response. Khách chưa đăng nhập không có danh tính CDP nên không sinh event lúc thêm; event được ghi khi gộp giỏ vào tài khoản (§7.1b).

#### Response `200` — `CartResponse` (chung cho cả bốn thao tác)

```json
{
  "cartId": "cart-01JXYZ",
  "cdpUserId": "VP0092381",
  "items": [
    {
      "cartItemId": "ci-2m9d7c",
      "product": { "productId": "nt-a-01", "...": "ProductSummary" },
      "usingDate": "2026-10-16",
      "quantity": 3,
      "nights": null,
      "guests": { "adults": 3, "children": 0 },
      "fares": [
        { "fareType": "ADULT", "unitPrice": 880000, "count": 3, "nights": null, "amount": 2640000 }
      ],
      "lineTotal": 2640000
    }
  ],
  "itemCount": 1,
  "subtotal": 2640000,
  "total": 2640000,
  "currency": "VND",
  "updatedAt": "2026-09-16T10:20:00Z"
}
```

Cam kết:

1. Mọi thao tác giỏ trả về **toàn bộ** `CartResponse`, không trả delta. Client không tự tính lại tổng tiền.
2. `product` là snapshot **tại thời điểm đọc**, không phải lúc thêm vào giỏ. `available` và `unitPrice` luôn được tải lại, nên sản phẩm hết chỗ sẽ tự lộ ra ở `GET /cart`.
3. `lineTotal` do backend tính, bằng tổng `fares[].amount` (§2.6). `guests` là số người lớn và trẻ em theo loại giá tại `usingDate` của mục; `product.attributes.maxOccupancy` có với hạng phòng để client kiểm sức chứa mà không gọi thêm.
4. `subtotal` bằng `total` trong MVP — không có thuế, phí hay mã giảm giá.
5. Không gom nhóm theo điểm đến ở tầng API. Client tự gom theo `product.destination` để hiện "Chuyến {destination}"; backend chỉ chốt nhóm ở bước checkout (§7.2).
6. Thêm một `productId` đã có trong giỏ với cùng `usingDate` thì **cộng dồn** `quantity` và `guests`, không tạo mục mới; kết quả sau khi cộng vẫn phải đạt luật (tối đa 9 khách, khách sạn 9 khách mỗi phòng, sức chứa). Riêng combo: `quantity` cộng dồn, `guests` lấy giá trị lớn hơn theo từng loại.

### 7.1a. Đơn nháp của Đặt ngay

"Đặt ngay" ở mọi sản phẩm (kể cả từng mục của lịch trình trợ lý; trợ lý không có thanh toán gộp) tạo một **đơn nháp**: đúng các mục của lần đặt đó, sống 30 phút (`BOOKING_DRAFT_TTL_MINUTES`), không liên quan tới các mục đang có trong giỏ.

```http
POST   /api/v1/booking-drafts                              # 201 BookingDraft
GET    /api/v1/booking-drafts/{draftId}
PATCH  /api/v1/booking-drafts/{draftId}/items/{cartItemId}
DELETE /api/v1/booking-drafts/{draftId}/items/{cartItemId}
```

Xác thực như giỏ (JWT, hoặc cặp header của khách). `POST` nhận đúng một trong hai:

```json
{ "items": [ { "productId": "nt-h-luckysun-d3", "usingDate": "2026-10-17", "quantity": 1, "nights": 2,
               "guests": { "adults": 2, "children": 1 } } ],
  "allowPartial": false }
```

```json
{ "fromBooking": "VOTA-20260916-8K3F" }
```

Cam kết:

1. `BookingDraft` có `draftId`, `expiresAt`, `cdpUserId` (null với khách) và `items`, `itemCount`, `subtotal`, `total`, `currency` cùng hình dạng với `CartResponse`; `cartItemId` của mục là mã mục đơn nháp. Tối đa 20 mục một đơn nháp, 5 đơn nháp còn hạn một người.
2. Một mục không đặt được làm cả request lỗi (cùng mã lỗi với thêm giỏ). `allowPartial: true` thì mục lỗi bị bỏ và trả trong `rejectedItems[{productId, usingDate, code, message}]`; không còn mục nào thì `409`.
3. Mục thuộc loại vào giỏ được (`attraction`, `golf`, `combo`) được **chép vào giỏ** lúc tạo đơn nháp nếu giỏ chưa có cùng `productId` + `usingDate`. Nhờ vậy khi khách không hoàn thành thanh toán, tour và tiện ích vẫn còn trong giỏ, còn khách sạn và vé máy bay thì không.
4. `fromBooking` đặt lại một đơn `PAYMENT_FAILED` hoặc `EXPIRED` của chính người gọi: mục, số lượng, số khách lấy từ đơn, giá tính lại theo catalog, luôn chạy như `allowPartial`. Tên, ngày sinh, giấy tờ hành khách không được chép sang. Cần đăng nhập.
5. Quá `expiresAt`: mọi thao tác trả `410 BOOKING_DRAFT_EXPIRED` với `details.items[{productId, taxonomy, inCart}]`. Không tìm thấy hoặc không thuộc người gọi: `404 BOOKING_DRAFT_NOT_FOUND`.
6. Tạo đơn nháp ghi `add_to_cart` cho từng mục (người đã đăng nhập), kể cả khách sạn và vé máy bay: đây là tín hiệu "đã chọn để đặt" cho Recommendation.

### 7.1b. Khách chưa đăng nhập và gộp vào tài khoản

Khách chưa đăng nhập thêm giỏ, Đặt ngay và điền thông tin được; chỉ `POST /bookings` cần đăng nhập. Giỏ và đơn nháp của khách nằm trong **Redis** (`BOOKING_REDIS_URL`), khoá theo `guestId` do BFF phát, giữ `GUEST_BOOKING_TTL_DAYS` = 3 ngày (đơn nháp vẫn chỉ thanh toán được trong 30 phút). `guestId` không bao giờ được ghi vào PostgreSQL. Backend chỉ tin `X-Guest-Id` khi `X-Service-Token` hợp lệ.

```http
POST /api/v1/guest-bookings/merge
Authorization: Bearer <jwt>
X-Service-Token: <token>
{ "guestId": "g_…" }
→ 200 { "mergedCartItems": 2, "skippedDuplicates": 1, "mergedDrafts": 1 }
```

BFF gọi endpoint này một lần sau khi khách đăng nhập (không mở ra ngoài). Mục chưa có trong giỏ tài khoản được thêm vào giỏ ở database; mục trùng `productId` + `usingDate` thì giữ mục của tài khoản; đơn nháp còn hạn chuyển sang tài khoản với `draftId` cũ; dữ liệu Redis của khách bị xoá. `add_to_cart` chỉ ghi cho mục thực sự được chép sang. Gọi lại với cùng `guestId` không gây trùng.

### 7.2. Checkout

```http
POST /api/v1/bookings
Authorization: Bearer <jwt>
Content-Type: application/json
```

#### Request

```json
{
  "contact": {
    "fullName": "Nguyễn Minh Anh",
    "email": "minhanh@example.vn",
    "phone": "0912345678"
  },
  "travelers": [
    { "travelerRef": "t1", "type": "ADULT", "surname": "Nguyễn", "givenNames": "Minh Anh" },
    { "travelerRef": "t2", "type": "CHILD", "surname": "Nguyễn", "givenNames": "Gia Bảo", "birthDate": "2019-05-12" }
  ],
  "itemDetails": [
    {
      "cartItemId": "ci-8k3f2a",
      "rooms": [ { "travelerRefs": ["t1", "t2"], "leadTravelerRef": "t1" } ],
      "specialRequest": "Phòng tầng cao nếu còn"
    }
  ]
}
```

Checkout có hai nguồn mục. Không gửi `draftId`: đặt **toàn bộ giỏ hiện tại** (thanh toán từ màn hình giỏ). Gửi `draftId`: đặt đúng các mục của đơn nháp đó, giỏ không bị đụng tới; đơn nháp bị xoá trong cùng transaction với việc tạo đơn, và `itemDetails[].cartItemId` là mã mục của đơn nháp. Khi đơn `CONFIRMED`, mục giỏ trùng `productId` + `usingDate` với mục của đơn bị gỡ khỏi giỏ. `travelers` là đoàn khách (1–9 người, ít nhất 1 người lớn; trẻ em có `birthDate`); mỗi mục giỏ có đúng một `itemDetails` cho biết ai dùng: `travelerRefs` với dịch vụ tính theo người và combo, `rooms[]` (mỗi phòng có `travelerRefs` và `leadTravelerRef`) với khách sạn. `itemDetails` không được thay đổi thành phần giỏ; `cartItemId` lạ thì trả `VALIDATION_ERROR`. Body không có trường tiền nào: số tiền do Backend tính từ catalog. Request cũ không có `travelers` (chỉ `guestNames`) vẫn được nhận khi giỏ không có trẻ em (`TRAVELERS_REQUIRED` nếu có), và cũng được kiểm thật. Họ tên và ngày sinh chỉ lưu ở `app.booking_travelers`, không trả trong response, không gửi sang CDP, Insider, Stripe (NFR-SEC-01).

`201` nghĩa là **đã giữ chỗ, chờ thanh toán** (FR-BKG-05, FR-BKG-06), không phải đã đặt xong. Backend kiểm giỏ, gọi Stripe tạo Checkout Session (`expires_at` = `holdExpiresAt`, 30 phút), rồi mới ghi đơn `PENDING_PAYMENT` + dòng `app.payments`. Web chuyển trình duyệt tới `payment.checkoutUrl`. Luồng đầy đủ và sơ đồ: `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md`.

#### Response `201`

```json
{
  "referenceCode": "VOTA-20260916-8K3F",
  "createdAt": "2026-09-16T10:22:00Z",
  "status": "PENDING_PAYMENT",
  "holdExpiresAt": "2026-09-16T10:53:00Z",
  "cancellableUntil": null,
  "payment": {
    "status": "OPEN",
    "amount": 14180000,
    "currency": "VND",
    "checkoutUrl": "https://checkout.stripe.com/c/pay/cs_test_…",
    "failedAttempts": 0,
    "failureReason": null,
    "refundedAmount": 0
  },
  "cancellation": null,
  "contact": {
    "fullName": "Nguyễn Minh Anh",
    "email": "minhanh@example.vn",
    "phone": "0912345678"
  },
  "groups": [
    {
      "destination": "Nha Trang",
      "eventGroupId": "OFF20260916001",
      "items": [
        {
          "bookingItemId": "bi-01",
          "product": { "productId": "nt-h-01", "...": "ProductSummary" },
          "usingDate": "2026-10-15",
          "quantity": 1,
          "nights": 3,
          "lineTotal": 10200000,
          "fares": [
            { "fareType": "ROOM", "unitPrice": 3400000, "count": 1, "nights": 3, "amount": 10200000 }
          ],
          "travelers": [
            { "fullName": "Nguyễn Minh Anh", "type": "ADULT", "roomNo": 1, "isLead": true },
            { "fullName": "Nguyễn Gia Bảo", "type": "CHILD", "roomNo": 1, "isLead": false }
          ],
          "guestNames": ["Nguyễn Minh Anh", "Nguyễn Gia Bảo"],
          "specialRequest": "Phòng tầng cao nếu còn"
        }
      ],
      "groupTotal": 10200000
    }
  ],
  "total": 14180000,
  "currency": "VND"
}
```

| Trường | Quy tắc |
|---|---|
| `referenceCode` | Định dạng `VOTA-YYYYMMDD-XXXX`, `XXXX` là 4 ký tự chữ hoa và số. Duy nhất toàn hệ thống |
| `status` | `PENDING_PAYMENT` → `CONFIRMED` \| `PAYMENT_FAILED` \| `EXPIRED` \| `CANCELLED` (máy trạng thái: spec booking §5.1). `CONFIRMED` chỉ khi Stripe đã thu tiền **và** event `purchase` đã ghi |
| `holdExpiresAt` | Hạn giữ chỗ; khác `null` chỉ khi `PENDING_PAYMENT` |
| `cancellableUntil` | 00:00 giờ Việt Nam của ngày liền trước `usingDate` sớm nhất; khác `null` chỉ khi `CONFIRMED` |
| `payment` | Trạng thái thanh toán tách khỏi trạng thái đơn (spec booking §5.2). `checkoutUrl` khác `null` chỉ khi `payment.status = OPEN`. `failureReason` theo bảng spec booking §10.2 |
| `cancellation` | Khác `null` chỉ khi `CANCELLED`: `cancelledAt`, `reason`, `refundAmount` |
| `groups[]` | **Gom theo `destination`**. Triển khai hiện tại dùng **một** `eventGroupId` cho cả đơn (DDL: `app.bookings.event_group_id` UNIQUE), nên mọi nhóm của một đơn mang cùng giá trị |
| `total` | Tổng toàn đơn, bằng tổng các `groupTotal`, bằng `payment.amount` |

Kiểm tra bắt buộc trước khi tạo booking (hợp đồng Agent §3.3), theo thứ tự (chi tiết: `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §8.3):

1. Giỏ không rỗng → nếu rỗng, `400` `CART_EMPTY`.
2. Mọi sản phẩm trong giỏ còn tồn tại.
3. **Luật dữ liệu đoàn khách và phân bổ** (họ tên, ngày sinh, tuổi, mỗi mục có người dùng, khớp `guests` của giỏ, sức chứa và người lớn mỗi phòng, người đại diện): gom **mọi** vi phạm vào một `400 VALIDATION_ERROR` với `details.fields[]` (`field`, `reason`, `message`, `cartItemId?`). Có vi phạm thì không gọi Stripe và không ghi gì. Sai kiểu dữ liệu (ví dụ ngày sinh không phải ngày) vẫn là `422`.
4. `available` vẫn là `true` → nếu không, `409` `PRODUCT_UNAVAILABLE` kèm `productId`.
5. `unitPrice` hiện tại khớp với lúc thêm vào giỏ → nếu lệch, `409` `PRICE_CHANGED` kèm giá cũ và giá mới. Mục có trẻ em còn so giá vé trẻ em hiệu lực với snapshot: lệch thì `PRICE_CHANGED` kèm `details.fareType = CHILD`. Giá trong giỏ và trong lịch trình của Agent chỉ là ước tính; **giá tại checkout là dữ liệu chính thức**.
6. `usingDate` vẫn nằm trong `availableFrom`–`availableTo`.

Kiểm thêm trước khi tạo đơn: người dùng không có đơn `PENDING_PAYMENT` còn hạn → nếu có, `409 BOOKING_PENDING_PAYMENT` kèm `{ referenceCode, holdExpiresAt }` của đơn đó. Đơn cũ đã quá hạn mà webhook hết hạn chưa tới thì Backend hỏi lại Stripe để đóng nó ngay trong request rồi tạo đơn mới. Stripe timeout/5xx khi tạo phiên → không tạo đơn, `503 PAYMENT_PROVIDER_UNAVAILABLE` (`retryable: true`, header `Retry-After`).

`PRICE_CHANGED` so giá hiện tại với giá snapshot lúc thêm giỏ (người lớn, và trẻ em khi mục có trẻ em). `PATCH /cart/items/{cartItemId}` ghi lại cả hai snapshot bằng giá hiện tại (khách đã thấy giá mới), nên Web xác nhận giá mới bằng một `PATCH` rồi cho khách bấm Thanh toán lần nữa.

Stripe nhận mỗi dòng giá của mỗi mục một line item (tên "{sản phẩm} · Người lớn", "· Trẻ em", "· {n} đêm", "· Gói"), nên tổng trang Stripe bằng `payment.amount` và khớp tóm tắt đơn. Sự kiện `purchase` gửi CDP vẫn một event mỗi mục (`quantity` của mục, `unitPrice` giá người lớn).

**Giỏ giữ nguyên** trong lúc giữ chỗ; chỉ các mục đã đặt (khoá theo `productId` + `usingDate`) bị xoá khỏi giỏ khi đơn chuyển `CONFIRMED`. Hết hạn hay thanh toán thất bại thì khách đặt lại ngay từ giỏ. Mỗi người dùng chỉ có một đơn giữ chỗ (unique index `bookings_one_pending_per_user`), đây là cơ chế chống bấm hai lần ở phía server; client vẫn phải khóa nút khi đang gửi (`docs/product.md` §4.5.3).

#### Xác nhận thanh toán — webhook Stripe

```http
POST /api/v1/payments/stripe/webhook
Stripe-Signature: t=…,v1=…      # bắt buộc; không dùng JWT, không qua BFF
```

- Backend kiểm chữ ký HMAC-SHA256 trên **raw body** với `STRIPE_WEBHOOK_SECRET`, timestamp lệch tối đa 5 phút. Sai chữ ký → `400 INVALID_WEBHOOK_SIGNATURE`, không đổi dữ liệu.
- Loại event xử lý: `checkout.session.completed` (và `async_payment_succeeded`), `checkout.session.expired`, `payment_intent.payment_failed`, `refund.created|updated|failed`, `charge.dispute.created` (chỉ log). Loại khác trả `200` và bỏ qua.
- Xử lý theo máy trạng thái nên gửi trùng hay sai thứ tự không đổi gì lần hai. Lỗi tạm thời (CDP, DB) → `500` không kèm chi tiết để Stripe gửi lại.
- Thẻ bị từ chối lần thứ `PAYMENT_MAX_FAILED_ATTEMPTS` (mặc định 3) → Backend đóng phiên Stripe, đơn `PAYMENT_FAILED`, `failureReason = TOO_MANY_ATTEMPTS`.
- Tiền về mà số tiền/loại tiền lệch, hoặc về cho đơn đã đóng → hoàn tự động toàn bộ.
- Job đối soát chạy trong Backend (mặc định 5 phút/lần) làm lại các việc dở dang khi webhook bị lỡ: đơn giữ chỗ quá hạn, đơn đã thu tiền chưa xác nhận, lệnh hoàn tiền chưa gửi, event `purchase` chưa huỷ.

### 7.3. Đọc lại đơn đặt chỗ

```http
GET /api/v1/bookings/{referenceCode}
Authorization: Bearer <jwt>
```

Trả về đúng payload của §7.2 với trạng thái hiện tại. Phục vụ việc tải lại trang `/booking/:referenceCode` và polling sau khi khách quay về từ Stripe (2 giây/lần, tối đa 15 lần). Việc trình duyệt quay về `success_url` **không** phải bằng chứng đã trả tiền.

Chỉ chủ đơn đọc được. `referenceCode` của người khác trả `404` `BOOKING_NOT_FOUND`, không trả `403` — không tiết lộ mã nào tồn tại.

#### Huỷ đơn — `POST /api/v1/bookings/{referenceCode}/cancel`

Body tuỳ chọn `{ "reason": "…" }` (≤ 500 ký tự). Huỷ **cả đơn** (FR-BKG-07), trả `200 BookingResponse`.

| Trạng thái đơn | Kết quả |
|---|---|
| `PENDING_PAYMENT`, thanh toán `OPEN` | Đóng phiên Stripe trước, đóng được mới ghi `CANCELLED` (payment `EXPIRED`). Phiên đã `complete` → `409 BOOKING_ALREADY_PAID`. Stripe không phản hồi → `503 PAYMENT_PROVIDER_UNAVAILABLE` |
| `CONFIRMED`, trước `cancellableUntil` | Ghi `CANCELLED` + payment `REFUND_PENDING`, gọi Refund API toàn bộ (`Idempotency-Key = refund:{bookingId}`), rồi `cancel_purchases` trên CDP. Lỗi Stripe/CDP ở hai bước sau để job đối soát làm lại |
| `CONFIRMED`, từ `cancellableUntil` | `409 BOOKING_NOT_CANCELLABLE`, `details { referenceCode, reason: "TOO_LATE", cancellableUntil }` |
| `CANCELLED` | `200`, trả lại đơn như cũ; không hoàn tiền lần hai |
| `EXPIRED`, `PAYMENT_FAILED` | `409 BOOKING_NOT_CANCELLABLE`, `reason: "NOT_ACTIVE"` |

### 7.3a. Danh sách đơn — `GET /api/v1/bookings` (FR-BKG-14)

```http
GET /api/v1/bookings?tab=upcoming&taxonomy=hotel&days=7&page=1&pageSize=5
Authorization: Bearer <jwt>
```

Trả `{ data: BookingSummary[], pagination: { page, pageSize, totalItems, totalPages } }`, mới nhất trước, chỉ đơn của người gọi. `tab` (`upcoming` mặc định, `done`, `cancelled`) do Backend xếp bằng `domain/booking/listing.py::tab_of`, theo giờ Việt Nam:

| Tab | Gồm |
|---|---|
| `upcoming` | `CONFIRMED` có ngày kết thúc dịch vụ (ngày trả phòng của khách sạn, ngày sử dụng của dịch vụ khác; lấy ngày muộn nhất của đơn) từ hôm nay trở đi; `PENDING_PAYMENT` còn hạn giữ chỗ |
| `done` | `CONFIRMED` mà mọi dịch vụ đã qua ngày kết thúc |
| `cancelled` | `CANCELLED`, `EXPIRED`, `PAYMENT_FAILED`; `PENDING_PAYMENT` đã quá `holdExpiresAt` (job đối soát chưa kịp chuyển `EXPIRED`) |

`taxonomy` giữ đơn có ít nhất một dịch vụ thuộc loại đó; `days` (1, 7, 30, 60) giữ đơn có `createdAt` trong N × 24 giờ gần nhất. `page` vượt quá `totalPages` trả `data` rỗng. Tham số sai kiểu hoặc ngoài khoảng trả `422 VALIDATION_ERROR`. Use case `ListBookings` nạp phần tóm tắt (`BookingTx.list_overviews`) rồi chỉ nạp dịch vụ của đúng trang (`BookingTx.get_many`), không nạp hành khách. Phân trang theo `page`/`pageSize` (như `/assistant/conversations`, `docs/prd/api-contract.md` §1.3), khác quy ước `limit`/`offset` ở §8.3 của các danh sách catalog.

### 7.4. Cam kết ghi event

Đây là vòng lặp phản hồi cốt lõi của cả sản phẩm (handbook §2, §10; `docs/product.md` §1.1 K1). Backend cam kết:

1. Mỗi mục trong booking thành công sinh **một** bản ghi trong bảng `events`, khóa theo `cdpUserId`.
2. Event dùng `eventName: "purchase"`, `eventGroupId` = `app.bookings.event_group_id` (một mã cho cả đơn, theo DDL và `DATABASE_SCHEMA.md` §5: một checkout = một chuyến).
3. Mỗi bản ghi mang đủ `productId`, `taxonomy`, `quantity`, `unitPrice`, `usingDate`, `timestamp` — đúng hình dạng `UserEvent` của handbook §6.
4. CDP clone là service riêng nên không có transaction chung. `purchase` chỉ ghi khi Stripe đã thu tiền: Backend commit payment `SUCCEEDED` trước, rồi ghi `purchase` sang CDP, rồi commit đơn `CONFIRMED`. CDP lỗi hoặc commit lỗi thì **không huỷ** event đã ghi (tiền đã thu, đơn phải được xác nhận); đơn giữ `PENDING_PAYMENT` + payment `SUCCEEDED`, Stripe gửi lại webhook hoặc job đối soát chạy lại cho tới khi `CONFIRMED`. Booking `CONFIRMED` mà thiếu event là trạng thái không được phép tồn tại. Khách huỷ đơn đã xác nhận thì Backend gọi `cancel_purchases`. Chi tiết: `hop-dong-tich-hop-cdp.md` §5.
5. Event được ghi **trước khi** đơn chuyển `CONFIRMED`; Web chỉ gọi `/recommendations` sau khi thấy `CONFIRMED`, nên thấy kết quả đã đổi (AC-REC-02).
6. Một booking không bao giờ sinh hai event cho cùng một `bookingItemId`: `eventId` là `purchase:{bookingItemId}`, CDP clone trả `duplicate` khi gửi lại. Lần checkout sau một lần lỗi sinh `bookingItemId` mới.

`add_to_cart` (thêm giỏ, tạo đơn nháp, gộp giỏ của khách) là event ghi ở nền, không nằm trong các cam kết giao dịch trên: lỗi CDP không làm hỏng thao tác của khách.

### 7.5. Ghi hành vi `product_view`

```http
POST /api/v1/events
Authorization: Bearer <jwt>    # bắt buộc
Content-Type: application/json

{ "eventName": "product_view", "productId": "nt-h-01" }
```

| Tình huống | Response |
|---|---|
| Hợp lệ | `202`, không body. Backend ghi sang CDP ở nền; không bảo đảm CDP đã lưu |
| Thiếu, sai hoặc hết hạn JWT | `401` `INVALID_TOKEN` / `TOKEN_EXPIRED` |
| `productId` không có trong catalog | `404` `PRODUCT_NOT_FOUND`, `details.productId`; không ghi event |
| `eventName` khác `product_view` hoặc có trường lạ | `400` `VALIDATION_ERROR` |

- Web gọi khi người dùng **thật sự mở** trang chi tiết, không gọi khi prefetch hay render phía server. `GET /products/{productId}` không ghi event.
- `taxonomy` lấy từ catalog; client không gửi.
- Chỉ nhận `product_view`. `search`, `add_to_cart`, `purchase` do Backend tự ghi (§5.1, §7.1, §7.4).

---

## 8. Quy ước xuyên suốt

### 8.1. Envelope lỗi

Dùng chung một hình dạng với hợp đồng Agent §4.5, để cả hệ thống chỉ có một kiểu lỗi:

```json
{
  "error": {
    "code": "PRODUCT_UNAVAILABLE",
    "message": "Vinpearl Resort Nha Trang vừa hết chỗ.",
    "retryable": false,
    "requestId": "book-01JXYZ",
    "details": { "productId": "nt-h-01" }
  }
}
```

`message` là tiếng Việt và có thể hiển thị trực tiếp cho người dùng. `details` là object tùy chọn, chỉ có với các lỗi cần thông tin bổ sung.

### 8.2. Bảng mã lỗi

Mã lỗi riêng của auth (`UNAUTHENTICATED`, `SESSION_EXPIRED`, `CSRF_FAILED`, `TOO_MANY_ATTEMPTS`, `WEAK_PASSWORD`, `CDP_UNAVAILABLE`…) ở `docs/spec/hop-dong-tich-hop-auth.md` §17.

| HTTP | Mã lỗi | Ý nghĩa | `details` |
|---:|---|---|---|
| 400 | `VALIDATION_ERROR` | Request vi phạm luật nghiệp vụ (đoàn khách, phân bổ, số khách của mục giỏ) hoặc `POST /events` sai | `{ fields: [{ field, reason, message, cartItemId? }] }`; mọi vi phạm trong một lần. Sai kiểu dữ liệu ở request khác vẫn là `422` |
| 400 | `CART_EMPTY` | Checkout khi giỏ rỗng | — |
| 404 | `BOOKING_DRAFT_NOT_FOUND` | Đơn nháp không tồn tại, đã dùng, hoặc không thuộc người gọi | `{ draftId }` |
| 410 | `BOOKING_DRAFT_EXPIRED` | Đơn nháp quá 30 phút | `{ draftId, items: [{ productId, taxonomy, inCart }] }` |
| 422 | `DIRECT_BOOKING_ONLY` | Thêm khách sạn hoặc vé máy bay vào giỏ | `{ productId, taxonomy }` |
| 401 | `INVALID_CREDENTIALS` | Sai email hoặc mật khẩu | — |
| 401 | `INVALID_TOKEN` | JWT không hợp lệ | — |
| 401 | `TOKEN_EXPIRED` | JWT hết hạn | — |
| 404 | `PRODUCT_NOT_FOUND` | Sản phẩm không tồn tại hoặc đã bị xóa | `{ productId }` |
| 404 | `CART_ITEM_NOT_FOUND` | `cartItemId` không thuộc giỏ hiện tại | `{ cartItemId }` |
| 404 | `BOOKING_NOT_FOUND` | Không tìm thấy đơn, hoặc đơn không thuộc người dùng | — |
| 409 | `EMAIL_ALREADY_EXISTS` | Email đã được đăng ký | — |
| 409 | `PRODUCT_UNAVAILABLE` | Sản phẩm hết chỗ tại thời điểm thêm giỏ hoặc checkout | `{ productId }` |
| 409 | `PRICE_CHANGED` | Giá đã đổi kể từ lúc thêm vào giỏ | `{ productId, oldPrice, newPrice, fareType? }`; `fareType = CHILD` khi giá vé trẻ em đổi |
| 422 | `DATE_OUT_OF_RANGE` | `usingDate` ngoài `availableFrom`–`availableTo`; riêng khách sạn: ngoài khoảng hôm nay (giờ Việt Nam) đến hôm nay + 3 tháng, khi đó `availableFrom`/`availableTo` là hai mốc này, không phải cửa sổ mở bán (FR-CAT-03). Khách sạn tối đa 30 đêm (`nights` ≤ 30, vượt thì 400 `VALIDATION_ERROR`); lịch `attributes.availability` không dùng để chặn (chỉ bộ lọc ngày của `POST /search` dùng lịch, `search-recommendation` §2.5) | `{ productId, availableFrom, availableTo }` |
| 409 | `BOOKING_PENDING_PAYMENT` | Đã có đơn giữ chỗ còn hạn | `{ referenceCode, holdExpiresAt }` |
| 409 | `BOOKING_ALREADY_PAID` | Huỷ đơn chưa trả nhưng Stripe vừa thu tiền | `{ referenceCode }` |
| 409 | `BOOKING_NOT_CANCELLABLE` | Quá hạn huỷ hoặc đơn đã đóng | `{ referenceCode, reason: TOO_LATE \| NOT_ACTIVE, cancellableUntil? }` |
| 400 | `INVALID_WEBHOOK_SIGNATURE` | Webhook Stripe sai chữ ký (chỉ Stripe nhận) | — |
| 503 | `SEARCH_UNAVAILABLE` | Vector index không khả dụng | — |
| 503 | `PAYMENT_PROVIDER_UNAVAILABLE` | Stripe timeout hoặc 5xx khi tạo/đóng phiên; kèm `Retry-After` | — |
| 500 | `INTERNAL_ERROR` | Lỗi không lường trước | — |

`retryable: true` chỉ dành cho `SEARCH_UNAVAILABLE`, `PAYMENT_PROVIDER_UNAVAILABLE`, `DATABASE_UNAVAILABLE` và `INTERNAL_ERROR` (danh sách đầy đủ gồm cả mã auth: `schemas/common.yaml`).

**PostgreSQL không với tới được (contract 1.14.0, NFR-REL-03 đang chờ chốt).** Mọi endpoint cần DB trả `503 DATABASE_UNAVAILABLE` (`retryable: true`, header `Retry-After: 5`) thay cho `500 INTERNAL_ERROR` hoặc treo: adapter Postgres mở kết nối qua `infrastructure/persistence/db_connection.py` (`DB_CONNECT_TIMEOUT_SECONDS`, mặc định 3 giây; keepalive và `tcp_user_timeout` cho DB chết giữa chừng), ném `DatabaseUnavailableError`, và `api/errors.py` ánh xạ lỗi này. Riêng `LocalCdpClient` vẫn trả `CDP_UNAVAILABLE` như cũ. `GET /health` (liveness) không đụng DB; `GET /health/ready` thêm trường `database: ok|down|unknown` (kiểm `SELECT 1`, cache 5 giây) nhưng vẫn trả 200 khi app đã khởi động xong, để orchestrator không restart app và deploy không bị hoàn tác chỉ vì DB gián đoạn. DB hồi phục thì request kế tiếp tự thành công, không cần restart. Mọi lỗi còn lại là `false` — thử lại nguyên request sẽ cho cùng kết quả.

### 8.3. Phân trang

Danh sách catalog (`/products`, `/search`) dùng `limit` và `offset`, và trả lại cả hai trong response cùng với `total`. Danh sách theo người dùng (`/assistant/conversations`, `GET /bookings`) dùng `page` và `pageSize` kèm `pagination`. Mặc định `limit=20`, tối đa `50`. Không dùng cursor trong MVP.

### 8.4. Request tracing

```http
X-Request-ID: 01JXYZ
```

Mọi service truyền tiếp header này, kể cả lời gọi Backend → CDP clone chạy ở nền. Caller chưa gửi thì service đầu tiên tự sinh. Giá trị được lặp lại trong `requestId` của response và trong mọi dòng log liên quan.

### 8.5. Ngân sách thời gian

| Hoạt động | Mục tiêu p95 |
|---|---:|
| `POST /search` | 300 ms |
| `GET /recommendations` | 300 ms |
| `GET /products/{id}` | 150 ms |
| `GET /products/{id}/similar` | 300 ms |
| `POST /bookings` (gồm tạo phiên Stripe) | 1 giây, không tính thời gian Stripe (timeout 10 giây) |

### 8.6. Logging

Log **được phép** chứa: `requestId`, `cdpUserId` đã pseudonymize, truy vấn tìm kiếm, bộ lọc, danh sách `productId` trả về, `strategy`, độ trễ, mã lỗi, `referenceCode`.

Log **không được** chứa: mật khẩu ở bất kỳ dạng nào, JWT, API key, email và số điện thoại đầy đủ của khách.

### 8.6a. Đo lần gọi web / agent (`/metrics`, `/internal/calls`)

Theo `docs/prd/deployment-plan.md` §5. Hai endpoint vận hành nằm ngoài `/api/v1`, cùng nhóm với `/health`, không thuộc
contract public (`include_in_schema=False`):

- `GET /metrics` — text Prometheus: `vota_calls_total`, `vota_call_errors_total`, `vota_call_duration_ms` (p50 / p95 trên
  500 lần gần nhất) theo nhãn `source` (`web` | `agent`), `kind` (`http` | `tool`), `name`; `vota_catalog_products`,
  `vota_catalog_reloads_total` của bản recsys / catalog đang trong bộ nhớ.
- `GET /internal/calls?after=<seq>&limit=<≤1000>` — JSON `{lastSeq, startedAt, catalog, summary[], events[]}`; mỗi sự
  kiện: `seq`, `at`, `source`, `kind`, `name` (web: `METHOD /api/v1/route/{tham số}` — tên tham số, không phải giá trị;
  agent: tên công cụ), `status` (HTTP hoặc `ok` / `error:<mã>` / `cancelled`), `ms`, và nếu có `useCase`, `useCaseMs`,
  `resultCount`, `productIds` (≤ 20), `stageMs` (của `/search`, `StageTimer`). Không có query string, câu tìm kiếm, body
  hay dữ liệu cá nhân. Monitor job cào đọc endpoint này (tab "Realtime").

Nguồn `web` = request dưới `/api/v1` (middleware `api/middleware.py`); nguồn `agent` = công cụ itinerary gọi engine trong
tiến trình (`application/itinerary/engine_tools.py`). Engine search / similar / recommend và use case catalog được bọc ở
composition root (`application/telemetry.py`), nên hai nguồn đo cùng một cách. Bộ đệm trong bộ nhớ
(`infrastructure/telemetry/memory.py`, 2.000 sự kiện) mất khi restart.

### 8.7. Versioning

- Mọi endpoint bắt đầu bằng `/api/v1`.
- Thêm field mới hoặc thêm giá trị enum là thay đổi tương thích ngược, được phép trong v1. Riêng enum `strategy` và `taxonomy` phải thông báo trước khi triển khai.
- Không xóa hoặc đổi tên field trong v1.
- Thay đổi phá vỡ tương thích phải tạo `/api/v2`.
- Một thay đổi contract cần reviewer của cả Web và Backend (`architecture-repo.md` §11).

---

## 9. Đối chiếu với hợp đồng Itinerary Assistant

`docs/spec/hop-dong-tich-hop-itinerary-assistant.md` được viết trước tài liệu này và dùng một bộ tên trường khác. Bộ tên trong tài liệu này là bộ canonical, vì nó phản chiếu CDP theo yêu cầu của handbook §6.

| Hợp đồng Agent hiện tại | Đổi thành | Lý do |
|---|---|---|
| `category`, enum `HOTEL`/`FLIGHT`… | `taxonomy`, enum `hotel`/`flight`… | Khớp tên và kiểu chữ của CDP |
| `RESTAURANT` | Bỏ; bổ sung `golf` | Catalog không có nhà hàng, nhưng có sân golf |
| `price: { amount, currency, unit }` | `unitPrice` + `currency`; đơn vị dẫn xuất từ `taxonomy` (§2.6) | CDP lưu `unitPrice` phẳng |
| `attributes: ["family-friendly"]` | `attributes: { familyFriendly: true }` | CDP lưu object; từ vựng ở §2.5 |
| `semanticScore` | `score` | Đồng bộ với `/recommendations` và `/similar` |
| `recommendationScore` | `score` | Như trên |
| `strategy: PERSONALISED` \| `POPULAR_IN_DESTINATION` | `cross_vertical` \| `recent_activity` \| `dormant` \| `popular`; bổ sung `long_term` \| `cold_start_content` (2026-09-28) | Các giá trị này là thứ UI cần để sinh tiêu đề section |
| `userId` trong response recommendation | `cdpUserId` | Phân biệt rõ với `userId` của bảng `users` |
| `bookingUrl: "/products/{productId}"` | Bỏ khỏi payload; client dựng `/product/{productId}` | Route thật là số ít, và URL frontend không thuộc trách nhiệm backend |
| `reason` (chuỗi lý do) | `because[]` (§6.3) | Chuỗi tự do không render được popover "Vì sao?" |

Tài liệu này **không tự sửa** file hợp đồng Agent. Việc cập nhật cần buổi thống nhất có reviewer của Web, Backend và Agent.

---

## 10. Trả lời các phụ thuộc D1–D13 của `docs/product.md` §9

| # | Câu hỏi | Trả lời |
|---|---|---|
| D1 | Giá trị `strategy` ngoài `cross_vertical` | **Chốt.** `cross_vertical`, `recent_activity`, `dormant`, `popular`; bổ sung `long_term`, `cold_start_content` 2026-09-28 — §6.2 |
| D2 | `because[]` có `productId` / `imageUrl` không | **Chốt: có cả hai**, `productId` nhận `null` khi sản phẩm đã bị xóa — §6.3 |
| D3 | Ai ghi event `product_view` | **Chốt: Web gọi `POST /api/v1/events`**, Backend ghi sang CDP clone — §7.5. `GET /products/{id}` không ghi event. `search` và `add_to_cart` do Backend tự ghi. Web không gọi CDP clone |
| D4 | `/search` hỗ trợ lọc và ngưỡng điểm không | **Chốt.** Lọc `taxonomy`, `destination`, `priceMin`/`priceMax`, `starRatingMin`; trả `topScore` và `facets` — §5.1, §5.2 |
| D5 | Endpoint "phổ biến" cho Home công khai | **Chốt: không tách endpoint.** `GET /recommendations` không JWT trả `strategy: "popular"`. Ngoài ra `GET /products?sort=popular` phục vụ section ④ luôn-render — §4.1, §6.5 |
| D6 | Giỏ lưu server hay client | **Chốt: server**, khóa theo `cdpUserId` — §7.1 |
| D7 | Checkout gán `eventGroupId` thế nào | **Chốt: gom theo `destination`**, mỗi nhóm một `eventGroupId`, trả về trong `groups[]` — §7.2 |
| D8 | Endpoint đọc booking theo `referenceCode` | **Chốt: có** — `GET /api/v1/bookings/{referenceCode}` — §7.3 |
| D9 | Chat có stream SSE không | **Ngoài phạm vi.** Thuộc hợp đồng Agent |
| D10 | Hình dạng response chat và intent có cấu trúc | **Ngoài phạm vi.** Thuộc hợp đồng Agent. Lưu ý `docs/product.md` §6.4 và hợp đồng Agent §4.2 đang mô tả hai shape khác nhau, cần thống nhất riêng |
| D11 | Sản phẩm có nhiều ảnh không | **Chốt: không trong MVP.** Chỉ một `imageUrl`. Client hiển thị một ảnh full-width — §2.3 |
| D12 | Ngữ nghĩa ngày của vé máy bay | **Chốt: theo khoảng.** `flight` dùng `availableFrom`–`availableTo` như mọi `taxonomy` khác; `usingDate` là ngày bay người dùng chọn — §2.2, §7.1 |
| D13 | Danh sách "sản phẩm đã xem gần đây" | **Hoãn.** D3 đã chốt nên dữ liệu có trong CDP, nhưng chưa có endpoint Backend đọc và hydrate sản phẩm. Client vẫn bỏ section ② của Home |

---

## 11. Mock data cần có trước khi tích hợp

Team Data cung cấp seed thỏa mãn:

- Tối thiểu 5 khách sạn, 10 vé tham quan, 3 vé máy bay, 2 combo, 1 sân golf.
- Tối thiểu 3 điểm đến.
- Ít nhất một sản phẩm `available: false`.
- Ít nhất một sản phẩm có `rating: null` và `reviewCount: null`.
- Ít nhất một sản phẩm có `description` rỗng và một sản phẩm có `attributes: {}`.
- Bốn tài khoản demo đúng theo persona P1–P4 của `docs/product.md` §2, kèm event seed gom theo `eventGroupId`.
- Ít nhất một event trỏ tới `productId` đã bị xóa khỏi catalog, để kiểm thử quy tắc §6.3 mục 3.
- Ít nhất một truy vấn tìm kiếm cho `results: []`.

Team Backend cung cấp fixture response mẫu cho từng endpoint tại `src/shared/mocks/`, sinh từ chính `src/shared/contracts/openapi.yaml`.

---

## 12. Tiêu chí nghiệm thu tích hợp

1. Frontend sinh được kiểu TypeScript từ `openapi.yaml` và biên dịch sạch.
2. Mọi trường mà `ProductCard`, `PriceTag`, `BecauseLine`, `WhyPopover` và `SectionHeader` cần đều có trong response, không phải gọi thêm request phụ.
3. Khách chưa đăng nhập gọi được `/products`, `/search`, `/recommendations`, `/destinations` và nhận `200`.
4. Đăng nhập lần lượt bốn tài khoản demo cho ra bốn `strategy` khác nhau.
5. P4 (0 event) trả `coldStart: true` và mọi `because` rỗng — không có lý do bịa.
6. `/search` với truy vấn không khớp trả `results: []` và `topScore: null`, không lấp bằng sản phẩm ngẫu nhiên.
7. `/search` với `availableOnly=true` không trả sản phẩm nào có `available: false`.
8. `facets.taxonomy` cộng lại đúng bằng `total`.
9. Mọi `because[].productId` khác `null` đều mở được `GET /products/{id}` và trả `200`.
10. Thêm giỏ → đổi tài khoản demo → giỏ của người mới không chứa mục của người cũ.
11. Checkout thành công trả `201 PENDING_PAYMENT` với `referenceCode` đúng định dạng `VOTA-YYYYMMDD-XXXX` và `payment.checkoutUrl`; `GET /bookings/{referenceCode}` đọc lại được đầy đủ; sau webhook thanh toán hợp lệ đơn chuyển `CONFIRMED`.
12. Checkout với giỏ có hai điểm đến trả hai `groups[]`; theo DDL hiện hành cả hai mang cùng `eventGroupId` của đơn. (Tiêu chí cũ "hai `eventGroupId` khác nhau" mâu thuẫn với `app.bookings.event_group_id` UNIQUE — chờ người dùng quyết định, xem `history/2026-09-24-trien-khai-booking-thanh-toan-stripe.md`.)
13. Ngay sau khi đơn chuyển `CONFIRMED`, `GET /recommendations` trả `strategy` hoặc `nextVertical` đã thay đổi — đây là khoảnh khắc K1.
14. Sản phẩm bị đánh dấu hết chỗ giữa lúc checkout trả `409 PRODUCT_UNAVAILABLE` kèm `productId`, và giỏ không bị xóa.
15. p95 của `/search` và `/recommendations` dưới 300 ms trên seed data.
16. Backend integration test và frontend mock cùng kiểm tra với một file `openapi.yaml` duy nhất.
17. Tiêu chí ghi hành vi và CDP ở `hop-dong-tich-hop-cdp.md` §12 đều đạt.

---

## 13. Definition of Done

Hợp đồng backend được xem là hoàn thành khi:

> Team Web sinh toàn bộ kiểu dữ liệu từ `openapi.yaml`, dựng được cả tám màn hình bằng mock sinh từ chính file đó, rồi đổi sang backend thật mà không phải sửa một dòng nào trong tầng `services`.

Luồng nghiệm thu bắt buộc:

```text
Đăng nhập tài khoản demo
→ Home hiện gợi ý có because
→ Tìm kiếm bằng câu tiếng Việt tự do
→ Mở chi tiết một sản phẩm thật (sinh product_view trong CDP)
→ Thêm vào giỏ (sinh add_to_cart trong CDP)
→ Checkout, nhận mã tham chiếu
→ Booking sinh event purchase trong CDP
→ Quay lại Home, gợi ý đã đổi sang danh mục còn thiếu
```
