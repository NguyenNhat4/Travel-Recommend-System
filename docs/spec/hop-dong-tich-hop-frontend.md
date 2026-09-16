# Hợp đồng tích hợp Frontend

**Phiên bản:** 1.0  
**Người tạo:** mihhquan  
**Bên cung cấp:** Team Web  
**Bên phụ thuộc:** Team Backend, Team Agent, Team Recommendation/Search  
**Giao thức:** REST/JSON qua HTTP  
**Xác thực:** JWT Bearer Token, không bắt buộc với các API đọc  
**Mã hóa:** UTF-8  
**Tiền tệ mặc định:** VND  
**Prefix:** `/api/v1`  
**Ngày:** `2026-09-16`  
**Múi giờ:** `Asia/Ho_Chi_Minh`

> Tài liệu này chốt hợp đồng dữ liệu **nhìn từ phía Web**: Web tiêu thụ những trường nào ở màn hình nào, Web cung cấp route và deep link nào cho các team khác, quy tắc nào client sở hữu, và Web phản ứng thế nào với từng mã lỗi. Định nghĩa trường của năm nhóm API web-facing **không lặp lại ở đây** — nguồn là `hop-dong-tich-hop-backend.md`. Riêng Itinerary Assistant, §9 đề xuất một shape hợp nhất **chờ Team Agent duyệt**.
>
> Bản máy đọc được của toàn bộ hợp đồng nằm ở `src/shared/contracts/openapi.yaml`. Khi tài liệu này và file OpenAPI mâu thuẫn, **OpenAPI thắng** và tài liệu phải được sửa.

---

## 1. Phạm vi trách nhiệm

### 1.1. Team Web chịu trách nhiệm

- Sinh kiểu TypeScript từ `openapi.yaml`; không tự khai báo lại payload trong feature.
- Gọi HTTP **chỉ** qua `src/frontend/src/services/`; component không gọi `fetch` trực tiếp (`ARCHITECTURE.md` §6).
- Cung cấp các route và deep link ở §3, giữ ổn định để Agent, email mẫu và tài liệu demo trỏ vào.
- Sở hữu mọi chuỗi hiển thị: nhãn `taxonomy`, nhãn `attributes`, hậu tố đơn vị giá, câu `BecauseLine`, tiêu đề section theo `strategy` (§6).
- Áp dụng quy tắc render grounding cho lịch trình (§9.5) như lưới an toàn cuối, bất kể Agent trả gì.
- Sinh và gửi `X-Request-ID` cho mọi request; hiển thị `requestId` ở chế độ debug.
- Không log hoặc đưa JWT vào URL.
- Không dùng state phía client làm nguồn chính thức cho giá, `available` và tổng tiền giỏ.

### 1.2. Web cần từ Team Backend

- Đúng các endpoint, trường và mã lỗi của `hop-dong-tich-hop-backend.md` §3–§8.
- Fixture và OpenAPI được cập nhật **trước** khi đổi hành vi endpoint.
- Thông báo trước khi thêm giá trị `strategy` hoặc `taxonomy`.

### 1.3. Web cần từ Team Agent

- Response `POST /api/v1/assistant/itineraries` theo shape §9 (sau khi duyệt).
- Mọi sản phẩm trong lịch trình nhúng nguyên `ProductSummary` từ Search/Recommendation, không sửa tên, giá, ảnh.
- Không trả URL; Web tự dựng `/product/{productId}`.

### 1.4. Ngoài phạm vi

- Endpoint ghi event `product_view` (D3, hoãn — §12).
- Stream SSE cho trợ lý (D9, hoãn — §12).
- Thiết kế giao diện chi tiết: xem `docs/product.md` §4–§7.
- Insider clone, CDP clone, thuật toán xếp hạng.

---

## 2. Nguồn sự thật và quy trình

### 2.1. File và thư mục

| Artifact | Vị trí | Chủ sở hữu |
|---|---|---|
| Hợp đồng máy đọc | `src/shared/contracts/openapi.yaml` | Integration (review: Web + Backend) |
| Fixture response | `src/shared/mocks/<domain>/<operationId>.<status>-<case>.json` | Backend cung cấp, Web bổ sung ca biên UI |
| Danh mục fixture | `src/shared/mocks/index.json` | Như trên |
| Kiểu TypeScript sinh ra | `src/frontend/src/types/api.gen.ts` | Sinh tự động, **không sửa tay** |
| HTTP client | `src/frontend/src/services/` | Web |

### 2.2. Sinh kiểu

```bash
npx openapi-typescript src/shared/contracts/openapi.yaml -o src/frontend/src/types/api.gen.ts
```

Feature dùng alias từ file sinh ra, ví dụ:

```ts
import type { components } from "@/types/api.gen";
type ProductSummary = components["schemas"]["ProductSummary"];
```

`api.gen.ts` được commit và CI kiểm tra nó khớp với `openapi.yaml` (sinh lại rồi `git diff --exit-code`).

### 2.3. Mock

- Chế độ mock bật bằng `NEXT_PUBLIC_API_MOCK=1`. Tầng `services` đọc fixture theo `index.json` thay vì gọi mạng.
- Chọn ca biên bằng query `?mock=<case>` trên trình duyệt, ví dụ `/?mock=p4-cold-start`.
- Mọi fixture phải hợp lệ với schema tương ứng trong `openapi.yaml`; CI chạy kiểm tra này cho cả Web và Backend.

### 2.4. Thay đổi hợp đồng

1. Sửa `openapi.yaml` trước, kèm fixture.
2. Sửa tài liệu này nếu hành vi phía Web đổi.
3. PR cần reviewer của Web và Backend; phần itinerary cần thêm reviewer Agent.
4. Quy tắc tương thích theo `hop-dong-tich-hop-backend.md` §8.7.

---

## 3. Route và deep link Web cung cấp

Đây là **hợp đồng ngược**: các team khác được phép trỏ vào những URL này và Web cam kết giữ chúng ổn định trong v1.

| Route | Màn hình | Cần đăng nhập | Query param chính thức |
|---|---|---:|---|
| `/` | Home | Không | `debug` |
| `/search` | Kết quả tìm kiếm | Không | `q` (bắt buộc), `taxonomy`, `destination`, `priceMin`, `priceMax`, `starRatingMin`, `sort` (`relevance` \| `price_asc` \| `price_desc`) |
| `/product/{productId}` | Chi tiết sản phẩm | Không | — |
| `/assistant` | Trợ lý lịch trình | Không | `q` (prompt điền sẵn, không tự gửi), `destination` |
| `/cart` | Giỏ hàng | Có | — |
| `/checkout` | Checkout | Có | — |
| `/booking/{referenceCode}` | Xác nhận đặt chỗ | Có | — |
| `/login`, `/register` | Đăng nhập, đăng ký | — | `redirect` (đường dẫn nội bộ, bắt đầu bằng `/`) |

Quy ước:

1. Route chi tiết là **số ít** `/product/{productId}`. Hợp đồng Agent §3.2 đang ghi `/products/{productId}` — sai, xem §10.
2. Backend và Agent **không** trả URL frontend. Mọi link do Web dựng từ `productId` hoặc `referenceCode`.
3. Tham số query của `/search` trùng tên với trường của `SearchRequest`, để Web chuyển thẳng sang body `POST /search`.
4. `redirect` không phải đường dẫn nội bộ thì bị bỏ qua, chuyển về `/`.
5. `?debug=1` bật chế độ chẩn đoán trên mọi route (`docs/product.md` §5.6).
6. Route cần đăng nhập mà khách vãng lai truy cập thẳng → `/login?redirect=<route hiện tại>`.

---

## 4. Ma trận màn hình → endpoint → trường

Ký hiệu auth: **—** không gửi JWT · **tùy** gửi nếu có · **bắt buộc** phải có.

### 4.1. Home `/`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Lời chào | `GET /auth/me` (khi khôi phục phiên) | bắt buộc | `fullName` (`AuthUser`) | Không có phiên → lời chào chung |
| ① Gợi ý cá nhân hóa | `GET /recommendations?k=5` | tùy | `strategy`, `nextVertical`, `destination`, `recommendations[]` (`rank`, `productId`, `name`, `taxonomy`, `destination`, `unitPrice`, `currency`, `available`, `imageUrl`, `attributes`, `score`, `because[]`), `diagnostics.excludedVerticals`, `diagnostics.coldStart` | 5xx / timeout > 3 giây → ẩn ①, hiện dòng "Chưa tải được gợi ý · Thử lại". Khách vãng lai → không gọi, hiện banner đăng nhập |
| ② Đã xem gần đây | — | — | — | **Bỏ section** (D13) |
| ③ Thẻ trợ lý | dùng lại response ① | — | `destination` | Không có → câu chung |
| ④ Phổ biến | `GET /products?sort=popular&taxonomy=<tab>&limit=10` | — | `results[]` (`ProductSummary`) | **Luôn render**. Lỗi → `ErrorState` cục bộ |
| Chip điểm đến | `GET /destinations` | — | `destinations[].destination` | Lỗi → ẩn chip |

Sau checkout (cờ `justBooked`): gọi lại ① bỏ qua cache. Chỉ hiện toast "Trang chủ đã cập nhật" khi `strategy` **hoặc** `nextVertical` khác lần gọi trước.

### 4.2. Search `/search`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Danh sách | `POST /search` | tùy | `results[]` (`ProductSummary` + `score`), `total`, `limit`, `offset` | `results: []` với bộ lọc → EmptyState "bỏ bộ lọc"; không bộ lọc → EmptyState + carousel `GET /products?sort=popular` |
| Tab danh mục, bộ đếm lọc | cùng response | — | `facets.taxonomy`, `facets.destination` | Giá trị 0 → ẩn tab |
| Băng "kết quả yếu" | cùng response | — | `topScore` | `topScore < 0.35` → hiện băng; `null` → không hiện |
| Xem thêm | `POST /search` với `offset += limit` | tùy | như trên | Lỗi → nút "Thử lại" dưới danh sách |

`503 SEARCH_UNAVAILABLE` → `ErrorState` có "Thử lại", giữ nguyên truy vấn trong ô.

### 4.3. Product detail `/product/{productId}`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Thông tin, hộp đặt | `GET /products/{productId}` | — | `ProductDetail` đầy đủ | `404 PRODUCT_NOT_FOUND` → trang "Sản phẩm này không còn trên V-OTA" |
| Tương tự | `GET /products/{productId}/similar?limit=8` | — | `results[]` + `score` | Lỗi hoặc rỗng → ẩn section |
| Hoàn thiện chuyến | `GET /recommendations?k=4&destination=<product.destination>` | bắt buộc | như Home ① | Chỉ render khi `destination` response trùng sản phẩm |
| Thêm vào giỏ | `POST /cart/items` | bắt buộc | `CartResponse.itemCount` (badge header) | Xem §8 |

Hộp đặt gửi `nights` chỉ khi `taxonomy = hotel`. Tổng tiền trong hộp đặt là **ước tính hiển thị**, tính theo công thức `hop-dong-tich-hop-backend.md` §2.6; giá chính thức là `lineTotal` do backend trả.

### 4.4. Cart `/cart`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Danh sách, tóm tắt | `GET /cart` | bắt buộc | `items[]` (`cartItemId`, `product`, `usingDate`, `quantity`, `nights`, `lineTotal`), `itemCount`, `subtotal`, `total`, `currency` | `items: []` → EmptyState. Mục có `product.available: false` → viền đỏ, khóa CTA checkout |
| Sửa / xóa | `PATCH` / `DELETE /cart/items/{cartItemId}` | bắt buộc | toàn bộ `CartResponse` thay thế state | `404 CART_ITEM_NOT_FOUND` → tải lại `GET /cart` |
| Gom nhóm "Chuyến {destination}" | — | — | `items[].product.destination` | Client tự gom |
| Thường được đặt cùng | `GET /recommendations?k=4&destination=<điểm đến đầu tiên>` | bắt buộc | như Home ① | Lỗi → ẩn |

Web **không** tự cộng tiền. Mọi con số tiền trên trang giỏ lấy từ `CartResponse`.

### 4.5. Checkout `/checkout`

| Khu vực | Endpoint | Auth | Trường Web đọc / gửi | Khi lỗi |
|---|---|---|---|---|
| Tóm tắt | `GET /cart` | bắt buộc | như §4.4 | `items: []` → chuyển `/cart` |
| Điền sẵn | phiên hiện tại | — | `user.fullName`, `user.email` | — |
| Xác nhận | `POST /bookings` | bắt buộc | gửi `contact`, `itemDetails[]`; đọc `referenceCode` | Xem §8. Thành công → `replace` sang `/booking/{referenceCode}` |

Quy tắc form → `itemDetails[]`: `hotel` gửi `guestNames` 1 phần tử; `flight` gửi `guestNames` đủ `quantity` phần tử; loại khác không gửi `guestNames`. `specialRequest` tùy chọn.

### 4.6. Confirmation `/booking/{referenceCode}`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Đơn đặt | dùng response `POST /bookings` nếu có trong state; tải lại → `GET /bookings/{referenceCode}` | bắt buộc | `referenceCode`, `createdAt`, `contact`, `groups[]` (`destination`, `items[]`, `groupTotal`), `total` | `404 BOOKING_NOT_FOUND` → "Không tìm thấy đơn đặt chỗ này" |
| Tiếp theo cho chuyến | `GET /recommendations?k=4&destination=<groups[0].destination>` — gọi **sau** khi đơn đã hiển thị | bắt buộc | như Home ① | Lỗi hoặc rỗng → ẩn section, giữ CTA |
| CTA trợ lý | — | — | `groups[0].destination`, `usingDate` của mục `hotel` | → `/assistant?destination=…&q=…` |

### 4.7. Login / Register

| Hành động | Endpoint | Trường gửi | Trường đọc | Lỗi |
|---|---|---|---|---|
| Đăng nhập | `POST /auth/login` | `email`, `password` | `accessToken`, `expiresIn`, `user` | `401 INVALID_CREDENTIALS` → một thông điệp chung |
| Đăng ký | `POST /auth/register` | `email`, `password`, `fullName` | như đăng nhập | `409 EMAIL_ALREADY_EXISTS` dưới trường email; `400 VALIDATION_ERROR` → `details.fields` gắn vào từng trường |
| Khôi phục phiên | `GET /auth/me` | — | `AuthUser` | `401` → xóa token, chế độ khách |
| Tài khoản demo | `GET /auth/demo-accounts` | — | `accounts[]` | `404` (production) → ẩn `DemoAccountSwitcher` |

### 4.8. Assistant `/assistant`

| Hành động | Endpoint | Auth | Trường Web đọc | Ghi chú |
|---|---|---|---|---|
| Gửi tin nhắn | `POST /assistant/itineraries` | tùy | theo `status`, xem §9.3 | Nút "Dừng" hủy request bằng `AbortController` |
| Sửa chip ý định | cùng endpoint với `intentOverride` | tùy | như trên | §9.2 |
| Thêm vào giỏ từ kế hoạch | `POST /cart/items` (mỗi mục một lần, tuần tự) | bắt buộc | `CartResponse` cuối cùng | Một mục lỗi không chặn mục còn lại; tổng kết lỗi trong một toast |
| Danh sách điểm đến (thẻ hỏi lại) | `GET /destinations` | — | `destinations[]` | Dùng khi `suggestedValues.destination` rỗng |

---

## 5. Hợp đồng dữ liệu của component dùng chung

Prop của component dùng **đúng tên schema** trong OpenAPI. Không có lớp map đổi tên trường giữa `services` và component.

| Component | Prop dữ liệu | Schema nguồn | Ghi chú |
|---|---|---|---|
| `ProductCard` | `product` | `ProductSummary` (hoặc `RecommendationItem`, `ScoredProduct` — cùng tập trường tối thiểu) | Trường tối thiểu dùng: `productId`, `name`, `taxonomy`, `destination`, `unitPrice`, `currency`, `available`, `imageUrl`, `attributes`. `rating`/`reviewCount` vắng mặt hoặc `null` → không render. Link luôn là `/product/{productId}` |
| `TaxonomyBadge` | `taxonomy` | `Taxonomy` | Giá trị lạ → badge trung tính "Dịch vụ" |
| `PriceTag` | `unitPrice`, `currency`, `taxonomy`, `prefix?` | `ProductSummary` | Hậu tố theo §6.2 |
| `AttributeTags` | `attributes`, `max` | `ProductAttributes` | Key lạ bỏ qua; `starRating` render bằng sao, không thành tag |
| `BecauseLine` | `because` | `BecauseItem[]` | Chỉ đọc `because[0]`; mảng rỗng → không render |
| `WhyPopover` | `because`, `strategy`, `destination`, `excludedVerticals`, `nextVertical` | `RecommendationResponse` | `because[].productId = null` → tên không link |
| `SectionHeader` | `strategy`, `destination`, `nextVertical`, `excludedVerticals`, `coldStart`, `context` (`home` \| `detail` \| `cart` \| `confirmation`) | `RecommendationResponse` | Bảng tiêu đề ở `docs/product.md` §5.3 |
| `TripChecklist` | `excludedVerticals`, `nextVertical` | `RecommendationDiagnostics` | Chỉ render khi `strategy = cross_vertical` |
| `ActivityNote` | `slot` | `ItinerarySlot` với `product: null` | Không giá, không nút, không ảnh |
| `ItineraryProductCard` | `slot` | `ItinerarySlot` với `product` khác `null` | `ProductCard` compact + `note` + nhãn "Hợp với bạn" khi `source = RECOMMENDATION` |
| `ErrorState` | `error` | `ErrorResponse.error` | `retryable: true` → nút "Thử lại" |

Không component nào nhận `priceString`, `price{}`, `category`, `bookingUrl` hoặc `semanticScore` — các trường đó không tồn tại trong v1.

---

## 6. Quy tắc client sở hữu

Backend chỉ trả **key và số**. Mọi quy tắc dưới đây là hằng số của Web, đặt trong feature tương ứng (không tạo `utils` chung, `ARCHITECTURE.md` §12).

### 6.1. Nhãn `taxonomy`

| `taxonomy` | Nhãn badge | Danh từ trong câu |
|---|---|---|
| `hotel` | Khách sạn | khách sạn |
| `flight` | Vé máy bay | vé máy bay |
| `attraction` | Vé tham quan | vé tham quan |
| `combo` | Combo | combo |
| `golf` | Golf | sân golf |

### 6.2. Giá

- Định dạng: `new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' })` → `1.890.000 ₫`.
- Hậu tố theo `hop-dong-tich-hop-backend.md` §2.6: `hotel` "/ đêm", `flight` "/ khách", `attraction` "/ khách", `combo` "/ gói", `golf` "/ lượt". `docs/product.md` §4.0 đang thiếu `golf` — bảng này là bản đúng.
- Giá trong hộp đặt và kế hoạch lịch trình là **ước tính**; giá trong `CartResponse` và `BookingResponse` là **chính thức**.

### 6.3. Nhãn `attributes`

Dùng bảng nhãn tiếng Việt ở `hop-dong-tich-hop-backend.md` §2.5. Key không có trong bảng → bỏ qua im lặng, không hiện tên key thô. Thứ tự hiển thị tag: theo thứ tự của bảng, không theo thứ tự key trong JSON.

### 6.4. Ngưỡng và hằng số

| Hằng số | Giá trị | Dùng ở |
|---|---|---|
| `WEAK_RESULT_TOP_SCORE` | `0.35` | Băng "kết quả yếu" ở Search |
| `RECOMMENDATION_TIMEOUT_MS` | `3000` | Home ① |
| `ASSISTANT_SLOW_MS` | `8000` | Trạng thái "chậm" của trợ lý |
| `ITINERARY_NOTE_MAX_CHARS` | `160` | Ghi chú 💬 |
| `BECAUSE_NAME_MAX_CHARS` | `32` | `BecauseLine` |
| `MIN_CARDS_FOR_CAROUSEL` | `3` | Home ①: dưới ngưỡng thì ẩn carousel |

### 6.5. `strategy` và `because`

- Map `strategy` → tiêu đề section theo `docs/product.md` §5.3; giá trị lạ → "Có thể bạn quan tâm".
- `event` → động từ và `daysAgo` → cụm thời gian theo `docs/product.md` §5.2.
- `contribution` hiển thị định tính: `≥ 0.5` Nhiều · `0.2–0.5` Vừa · `< 0.2` Ít.
- `event: "search"` → hiển thị `productName` trong ngoặc kép, không link.

### 6.6. Ảnh

`imageUrl: null` hoặc tải lỗi → placeholder theo `taxonomy` trong `src/frontend/src/assets/placeholders/`.

---

## 7. Auth và phiên phía client

1. `accessToken` lưu trong bộ nhớ và `sessionStorage` (khóa `vota.session`), không lưu `localStorage`, không đưa vào URL, không log.
2. Mỗi request có token gửi `Authorization: Bearer <accessToken>`. API đọc vẫn gửi token nếu có, để nhận kết quả cá nhân hóa.
3. Tải lại trang → đọc token từ `sessionStorage` → `GET /auth/me`. `401` → xóa phiên, chuyển chế độ khách, **không** mở modal.
4. Nhận `401 INVALID_TOKEN` hoặc `TOKEN_EXPIRED` giữa phiên → mở modal "Phiên đăng nhập đã hết hạn" với email điền sẵn; sau khi đăng nhập lại, **gửi lại đúng request đã hỏng** một lần. Người dùng hủy → chế độ khách tại trang hiện tại.
5. Web **không** tự hạ về chế độ ẩn danh khi token hỏng; backend cũng không (`hop-dong-tich-hop-backend.md` §6.5).
6. Khách vãng lai bấm hành động ghi (thêm giỏ, checkout) → modal đăng nhập tại chỗ; thành công → tự thực hiện hành động đang chờ.
7. Đổi tài khoản (demo hoặc đăng xuất) → xóa **mọi** cache phía client: query cache, `conversationId`, state kế hoạch, badge giỏ.
8. Không tự làm mới token trong v1 (backend không có refresh token). Có thể chủ động mở modal khi `expiresIn` còn dưới 60 giây và người dùng đang ở Checkout.

---

## 8. Xử lý lỗi

Mọi response không phải 2xx có envelope `ErrorResponse` (`hop-dong-tich-hop-backend.md` §8.1). Tầng `services` ném một lỗi có kiểu chứa `status`, `code`, `message`, `retryable`, `requestId`, `details`; component quyết định hiển thị theo bảng dưới.

| Mã lỗi | Nơi gặp | Web hiển thị |
|---|---|---|
| `VALIDATION_ERROR` | form bất kỳ | Gắn `details.fields[]` vào trường tương ứng; không có `fields` → `message` phía trên nút |
| `CART_EMPTY` | Checkout | Chuyển `/cart` |
| `INVALID_CREDENTIALS` | Login | "Email hoặc mật khẩu không đúng" phía trên nút |
| `INVALID_TOKEN`, `TOKEN_EXPIRED` | mọi nơi có JWT | §7 mục 3–4 |
| `DEMO_ONLY`, `NOT_FOUND` | Demo switcher | Ẩn switcher (`GET /auth/demo-accounts` trả `404 NOT_FOUND` ở production) |
| `PRODUCT_NOT_FOUND` | Detail; thêm giỏ | Detail → trang 404 sản phẩm. Thêm giỏ → toast `message` |
| `CART_ITEM_NOT_FOUND` | Cart | Tải lại `GET /cart`, không báo lỗi |
| `BOOKING_NOT_FOUND` | Confirmation | "Không tìm thấy đơn đặt chỗ này" + Về trang chủ |
| `EMAIL_ALREADY_EXISTS` | Register | Dưới trường email + link Đăng nhập |
| `PRODUCT_UNAVAILABLE` | Thêm giỏ; Checkout | Banner "{tên} vừa hết chỗ" dùng `details.productId` để tìm tên trong giỏ; giữ form; link Quay lại giỏ |
| `PRICE_CHANGED` | Checkout | Banner "Giá {tên} đã đổi từ {oldPrice} thành {newPrice}" + nút "Cập nhật và tiếp tục" (gọi lại `GET /cart`, người dùng bấm xác nhận lần nữa) |
| `DATE_OUT_OF_RANGE` | Thêm giỏ; Checkout | Lỗi dưới ô ngày, dùng `details.availableFrom/To` để giới hạn lịch |
| `SEARCH_UNAVAILABLE` | Search; Assistant | `ErrorState` + Thử lại |
| `INVALID_TRIP_DURATION` | Assistant | Tin nhắn trợ lý với `message`, mở stepper số ngày |
| `CONVERSATION_NOT_FOUND` | Assistant | Xóa `conversationId`, gửi lại tin nhắn như cuộc hội thoại mới, thêm dòng hệ thống "Đã bắt đầu cuộc trò chuyện mới" |
| `UNSUPPORTED_DESTINATION` | Assistant | "V-OTA chưa có dịch vụ ở {details.destination}" + chip từ `details.supportedDestinations` |
| `LLM_UNAVAILABLE` | Assistant | Chạy `POST /search` với tin nhắn gốc, hiển thị như `FALLBACK` |
| `ITINERARY_VALIDATION_FAILED` | Assistant | `ErrorState` + Thử lại |
| `INTERNAL_ERROR` | mọi nơi | `ErrorState` cục bộ + Thử lại |
| mã lạ | mọi nơi | Như `INTERNAL_ERROR`, hiển thị `message` nếu có |

Quy tắc chung:

1. Nút "Thử lại" chỉ xuất hiện khi `retryable: true` hoặc lỗi mạng (không có response).
2. Lỗi một section không làm hỏng cả trang.
3. Lỗi mạng hoặc timeout phía client dùng mã giả `NETWORK_ERROR`, `retryable: true`, **không** gửi lên server.
4. Ở chế độ debug, mọi `ErrorState` hiện `requestId`.

### 8.1. `X-Request-ID`

Web sinh ULID cho mỗi request người dùng khởi tạo và gửi trong header `X-Request-ID`. Thử lại cùng một thao tác dùng ID mới. Backend lặp lại giá trị trong `requestId` của response.

---

## 9. Itinerary Assistant — đề xuất shape hợp nhất

> **Trạng thái: ĐỀ XUẤT — chờ Team Agent duyệt.** Mục này gộp hợp đồng Agent §4 với nhu cầu UI ở `docs/product.md` §6.2–§6.6 (D10), và đổi tên trường theo bộ canonical của `hop-dong-tich-hop-backend.md`. Hợp đồng Agent chưa được sửa; danh sách thay đổi ở §10. Schema tương ứng trong OpenAPI mang ghi chú "Đề xuất".

### 9.1. Request

```http
POST /api/v1/assistant/itineraries
Authorization: Bearer <jwt>    # tùy chọn
Content-Type: application/json
```

```json
{
  "conversationId": "conv-01JXYZ",
  "message": "Lên lịch 3 ngày ở Nha Trang cho gia đình 2 người lớn và 1 trẻ em, ngân sách 15 triệu",
  "intentOverride": null,
  "context": { "language": "vi" }
}
```

| Trường | Bắt buộc | Ý nghĩa |
|---|---:|---|
| `conversationId` | Không | `null` → hội thoại mới |
| `message` | Có điều kiện | 1–1000 ký tự. Bắt buộc khi `intentOverride` là `null` |
| `intentOverride` | Không | `TripIntentPatch` — chỉ các trường người dùng sửa bằng chip. Có giá trị thì Agent **bỏ qua bước trích xuất LLM**, gộp vào intent đã lưu và tạo lại kế hoạch. Cần `conversationId` khác `null` |
| `context.language` | Không | `vi` \| `en`; thiếu thì tự phát hiện |

Ví dụ sửa chip "3 ngày → 2 ngày":

```json
{ "conversationId": "conv-01JXYZ", "message": null, "intentOverride": { "days": 2 } }
```

### 9.2. `TripIntent`

```json
{
  "destination": "Nha Trang",
  "startDate": null,
  "days": 3,
  "party": { "type": "FAMILY_WITH_KIDS", "adults": 2, "children": 1 },
  "budget": 15000000,
  "interests": ["biển", "vui chơi cho trẻ nhỏ"],
  "pace": "RELAXED"
}
```

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `destination` | string \| null | Chuẩn hóa theo `GET /destinations` |
| `startDate` | date \| null | Ngày bắt đầu nếu người dùng nêu |
| `days` | integer 1–7 \| null | Số ngày |
| `party` | object \| null | `type`: `SOLO` \| `COUPLE` \| `FAMILY_WITH_KIDS` \| `FRIENDS` \| `null`; `adults` ≥ 1; `children` ≥ 0 |
| `budget` | integer \| null | Tổng ngân sách VND. Thay cho `budget: { amount, currency }` |
| `interests` | string[] | Nhãn tiếng Việt ngắn, dùng trực tiếp làm chip. Có thể rỗng |
| `pace` | `RELAXED` \| `BALANCED` \| `PACKED` \| null | Nhịp độ |

`TripIntentPatch` có cùng các trường, tất cả tùy chọn; trường vắng mặt nghĩa là không đổi.

### 9.3. Response `200` — phân biệt theo `status`

| `status` | Khi nào | Web render |
|---|---|---|
| `COMPLETED` | Có kế hoạch | Panel kế hoạch + thẻ tóm tắt trong chat |
| `NEEDS_CLARIFICATION` | Thiếu `destination` hoặc `days` | Thẻ hỏi lại có lựa chọn |
| `NO_RESULTS` | Search không có sản phẩm phù hợp | Tin nhắn + chip `suggestions` |
| `FALLBACK` | LLM lỗi nhưng Search chạy được | Tin nhắn fallback + panel "Dịch vụ gợi ý ở {destination}" |

Lỗi thật (4xx/5xx) **không** dùng `status: "ERROR"` trong body 200 mà trả `ErrorResponse` với HTTP status tương ứng (§8), để cả hệ thống chỉ có một kiểu lỗi.

Trường chung mọi `status`: `status`, `conversationId`, `metadata`.

#### `COMPLETED`

```json
{
  "status": "COMPLETED",
  "conversationId": "conv-01JXYZ",
  "intent": { "destination": "Nha Trang", "startDate": null, "days": 3, "party": { "type": "FAMILY_WITH_KIDS", "adults": 2, "children": 1 }, "budget": 15000000, "interests": ["biển"], "pace": "RELAXED" },
  "itinerary": {
    "title": "Lịch trình gia đình 3 ngày tại Nha Trang",
    "stay": {
      "product": { "productId": "nt-h-01", "...": "ProductSummary" },
      "nights": 2,
      "note": "Có hồ bơi trẻ em và bãi biển riêng, gần VinWonders.",
      "source": "RECOMMENDATION",
      "because": [ { "productId": "nt-h-02", "productName": "…", "imageUrl": null, "event": "product_view", "daysAgo": 1, "contribution": 0.4 } ]
    },
    "days": [
      {
        "day": 1,
        "date": null,
        "title": "Vui chơi trọn ngày",
        "slots": [
          { "slotId": "d1-s1", "time": "MORNING", "startTime": "08:30", "endTime": "12:00", "activityType": null, "product": { "productId": "nt-a-01", "...": "ProductSummary" }, "note": "Đi sớm tránh nắng cho trẻ.", "source": "SEARCH", "because": [] },
          { "slotId": "d1-s2", "time": "NOON", "startTime": null, "endTime": null, "activityType": "MEAL", "product": null, "note": "Ăn trưa trong khu vui chơi, nghỉ ngơi.", "source": null, "because": [] }
        ]
      }
    ],
    "bookableCount": 5,
    "estimatedTotal": 12350000,
    "currency": "VND",
    "budgetStatus": "WITHIN_BUDGET",
    "priceAsOf": "2026-09-16T08:00:00Z"
  },
  "searchResults": { "hotel": [], "attraction": [], "combo": [] },
  "warnings": [],
  "metadata": { "personalised": true, "searchRequestIds": ["search-01JABC"], "generatedAt": "2026-09-16T08:00:00Z", "requestId": "agent-01JXYZ" }
}
```

| Trường | Quy tắc |
|---|---|
| `itinerary.stay` | Khối chỗ ở cho cả chuyến, **không lặp** trong `days`. `null` khi không có khách sạn phù hợp |
| `stay.nights` | Số đêm dùng khi "Thêm tất cả vào giỏ" |
| `days[].date` | Có khi `intent.startDate` khác `null`; Web dùng làm `usingDate` |
| `days[].title` | Do LLM đặt, tối đa 6 từ |
| `slots[].time` | `MORNING` \| `NOON` \| `AFTERNOON` \| `EVENING`. Web nhóm theo trường này |
| `slots[].startTime`, `endTime` | `HH:mm` hoặc `null`. Chỉ hiển thị phụ, không bắt buộc |
| `slots[].product` | `ProductSummary` đầy đủ, sao chép nguyên từ Search/Recommendation. `null` → `ActivityNote` |
| `slots[].activityType` | Chỉ khi `product` là `null`: `MEAL` \| `REST` \| `FREE_TIME` \| `TRANSFER` \| `SIGHTSEEING` |
| `slots[].note` | Ghi chú LLM, tối đa 160 ký tự, không chứa giá |
| `slots[].source` | `SEARCH` \| `RECOMMENDATION` khi có `product`; `null` khi không |
| `slots[].because` | Schema `BecauseItem` của `/recommendations`. Chỉ khác rỗng khi `source = RECOMMENDATION` |
| `bookableCount` | Số mục có `product.available = true`, gồm cả `stay` |
| `estimatedTotal` | Integer VND do backend tính (không phải LLM), theo `intent.party` và công thức §2.6 hợp đồng Backend |
| `budgetStatus` | `WITHIN_BUDGET` \| `OVER_BUDGET` \| `NO_BUDGET` |
| `priceAsOf` | Thời điểm lấy giá; Web ghi "giá tại thời điểm tạo kế hoạch" |
| `searchResults` | Object key `taxonomy` → `ProductSummary[]`, tối đa 6 mỗi nhóm. Có mặt kể cả khi `COMPLETED`, phục vụ "Tìm lựa chọn khác" |
| `warnings[]` | `{ code, message, productId }` — ví dụ `PRODUCT_DROPPED_UNAVAILABLE`, `DAY_WITHOUT_PRODUCTS`, `OVER_BUDGET` |

#### `NEEDS_CLARIFICATION`

```json
{
  "status": "NEEDS_CLARIFICATION",
  "conversationId": "conv-01JXYZ",
  "question": "Bạn muốn đi đâu và mấy ngày?",
  "missingFields": ["destination", "days"],
  "knownIntent": { "destination": null, "startDate": null, "days": null, "party": null, "budget": null, "interests": ["biển"], "pace": null },
  "suggestedValues": { "destination": ["Nha Trang", "Phú Quốc", "Đà Nẵng"], "days": [2, 3, 4, 5] },
  "metadata": { "personalised": false, "searchRequestIds": [], "generatedAt": "2026-09-16T08:00:00Z", "requestId": "agent-01JXYZ" }
}
```

`missingFields` chỉ nhận `destination` \| `days`. Người dùng chọn trên thẻ → Web gửi `intentOverride` với các giá trị đã chọn.

#### `NO_RESULTS`

```json
{
  "status": "NO_RESULTS",
  "conversationId": "conv-01JXYZ",
  "intent": { "destination": "Quy Nhơn", "...": "TripIntent" },
  "message": "Hiện chưa có sản phẩm phù hợp tại Quy Nhơn trong khoảng giá này.",
  "suggestions": ["Tăng ngân sách", "Chọn điểm đến khác"],
  "metadata": { "...": "ItineraryMetadata" }
}
```

`suggestions` là câu gửi được nguyên văn khi người dùng bấm chip.

#### `FALLBACK`

```json
{
  "status": "FALLBACK",
  "conversationId": "conv-01JXYZ",
  "intent": { "destination": "Nha Trang", "...": "TripIntent" },
  "message": "Trợ lý đang bận nên chưa sắp được lịch trình. Đây là các dịch vụ phù hợp ở Nha Trang để bạn tự chọn.",
  "searchResults": { "hotel": [ { "productId": "nt-h-01", "...": "ProductSummary" } ], "attraction": [], "combo": [] },
  "metadata": { "...": "ItineraryMetadata" }
}
```

`intent` có thể là `null` khi cả bước trích xuất cũng lỗi; khi đó `searchResults` là kết quả Search của nguyên tin nhắn.

### 9.4. Lỗi

HTTP status và `ErrorResponse` như §8. Mã riêng của trợ lý: `INVALID_TRIP_DURATION` (400), `CONVERSATION_NOT_FOUND` (404), `UNSUPPORTED_DESTINATION` (422, `details: { destination, supportedDestinations }`), `LLM_UNAVAILABLE` (503, chỉ khi Search cũng không dùng được), `ITINERARY_VALIDATION_FAILED` (500). Request sai định dạng dùng `VALIDATION_ERROR`; Search lỗi dùng `SEARCH_UNAVAILABLE`.

### 9.5. Quy tắc render grounding Web cam kết

Áp dụng `docs/product.md` §6.4 mục 1–7 làm hợp đồng render. Tóm tắt kiểm tra phía Web trước khi render mỗi slot có `product`:

1. `product.productId` khác rỗng.
2. `product.available = true`.
3. `product.destination = intent.destination`.

Không đạt → không render thẻ; hiển thị dòng mờ "Mục này hiện không còn chỗ · Tìm lựa chọn khác" (→ `/search?q={destination} {nhãn taxonomy}`), và ở chế độ debug ghi lý do loại. Tên, ảnh, giá luôn lấy từ `product`, **không bao giờ** từ `note` hay `title`. Không tự link hóa tên riêng trong văn bản LLM.

### 9.6. Hội thoại

- Web giữ `conversationId` trong state của route `/assistant` và `sessionStorage` (khóa `vota.assistant.conversationId`), xóa khi đổi tài khoản.
- Kế hoạch không tự cập nhật giá. Giỏ và Checkout luôn dùng giá mới nhất.
- Không stream trong v1: Web hiện danh sách 3 bước với một spinner chung, không đánh ✓ giả (`docs/product.md` §6.1).

---

## 10. Thay đổi cần Team Agent chấp thuận

Bổ sung cho bảng đối chiếu `hop-dong-tich-hop-backend.md` §9. File `hop-dong-tich-hop-itinerary-assistant.md` **chưa sửa**; việc cập nhật cần buổi thống nhất có reviewer Web, Backend và Agent.

| Hợp đồng Agent hiện tại | Đề xuất | Lý do |
|---|---|---|
| §3.2 route `/products/{productId}`, trường `bookingUrl` | Bỏ `bookingUrl`; Web dựng `/product/{productId}` | Route thật là số ít; URL thuộc Web |
| §4.2 `items[].type`, `productName`, `price`, `imageUrl` phẳng | `slots[].product: ProductSummary \| null` | Thẻ render từ đúng schema catalog, không có bản sao trường lệch tên |
| §4.2 `items[].type: "FREE_TIME"` | `product: null` + `activityType` | Hai trạng thái rõ ràng: thẻ sản phẩm hoặc `ActivityNote` |
| §4.2 `startTime`/`endTime` bắt buộc | `time` (khung giờ) bắt buộc; `startTime`/`endTime` tùy chọn | UI nhóm theo Sáng/Trưa/Chiều/Tối |
| Khách sạn nằm trong từng ngày | `itinerary.stay` riêng | Khối "Chỗ ở cho cả chuyến" |
| Không có `source`, `because`, `note` | Thêm | Nhãn "Hợp với bạn", `BecauseLine`, ghi chú 💬 |
| `estimatedTotal: { amount, currency }` | `estimatedTotal` integer + `currency` | Đồng bộ `unitPrice` phẳng |
| `intent.budget: { amount, currency }` | `intent.budget` integer | Như trên |
| `intent.party: { adults, children }` | Thêm `party.type` | Chip đoàn khách |
| Không nhận ý định có cấu trúc | `intentOverride` trong request | Sửa chip không qua LLM (D10) |
| §4.3 không có lựa chọn | `suggestedValues` | Thẻ hỏi lại có nút chọn |
| Không có trạng thái fallback | `status: "FALLBACK"` + `searchResults` | Handbook §9: LLM lỗi vẫn hiện kết quả tìm kiếm |
| §4.5 `status: "ERROR"` trong body | Chỉ `ErrorResponse` với HTTP status | Một kiểu lỗi cho cả hệ thống |
| `INVALID_REQUEST` | `VALIDATION_ERROR` | Trùng nghĩa với mã của Backend |
| `SEARCH_SERVICE_UNAVAILABLE` | `SEARCH_UNAVAILABLE` | Như trên |
| `metadata` | Thêm `requestId` | Debug trên UI |
| `warnings: []` không định nghĩa | `{ code, message, productId }` | Hiển thị ở chế độ debug |

---

## 11. Mock và dữ liệu kiểm thử cho Web

Fixture nằm ở `src/shared/mocks/`, liệt kê trong `index.json`. Mọi fixture dùng chung một bộ `productId` (`nt-h-01`, `nt-f-01`, `nt-a-01`…) để tham chiếu chéo nhất quán.

Ca biên bắt buộc để dựng đủ 8 màn hình:

| Ca | Fixture |
|---|---|
| Bốn persona có bốn `strategy` khác nhau | `recommendations/getRecommendations.200-p1-cross-vertical` … `200-p4-cold-start` |
| Khách vãng lai | `recommendations/getRecommendations.200-anonymous` |
| `because[].productId: null` (sản phẩm nguồn đã xóa) | nằm trong `200-p3-dormant` |
| Sản phẩm `available: false`, `rating: null`, `attributes: {}` | `catalog/listProducts.200-popular` |
| Search rỗng, `topScore: null` | `search/searchProducts.200-empty` |
| Similar rỗng | `catalog/getSimilarProducts.200-empty` |
| Sản phẩm 404 | `catalog/getProduct.404-not-found` |
| Giỏ rỗng / có hai điểm đến | `booking/getCart.200-empty`, `booking/getCart.200-two-destinations` |
| Checkout `409 PRICE_CHANGED`, `409 PRODUCT_UNAVAILABLE` | `booking/createBooking.409-*` |
| Booking hai nhóm điểm đến | `booking/createBooking.201-two-groups` |
| Trợ lý: bốn `status` + điểm đến không hỗ trợ + hội thoại hết hạn | `assistant/createItinerary.*` |
| Lịch trình chứa slot hết chỗ và slot sai điểm đến (lưới an toàn §9.5) | `assistant/createItinerary.200-completed-invalid-slots` |
| Search kết quả yếu (`topScore < 0.35`), Search `503` | `search/searchProducts.200-weak`, `search/searchProducts.503-unavailable` |
| Giỏ có mục hết chỗ | `booking/getCart.200-item-unavailable` |
| Đăng nhập sai | `auth/login.401-invalid-credentials` |

---

## 12. Phụ thuộc còn mở

| # | Nội dung | Mặc định Web trong lúc chờ |
|---|---|---|
| D3 | Endpoint ghi `product_view` | Không ghi. P2 chỉ có `because` sau khi thêm giỏ hoặc đặt |
| D9 | SSE cho trợ lý | Không stream; spinner chung, không ✓ giả |
| D10 | Shape `ItineraryResponse` | Code theo §9; mock theo §9. Nếu Agent từ chối, chỉ `features/itinerary` và fixture phải đổi |
| D13 | "Đã xem gần đây" | Bỏ section ② Home |
| A1 | Agent duyệt §10 | Như D10 |
| A2 | `docs/product.md` §4.0 thiếu hậu tố `golf` | Dùng §6.2 tài liệu này |

---

## 13. Tiêu chí nghiệm thu

1. `openapi.yaml` lint sạch; `openapi-typescript` sinh `api.gen.ts` và `tsc --noEmit` pass.
2. Mọi fixture trong `index.json` hợp lệ với schema response tương ứng.
3. Không feature nào khai báo lại type của payload API (tìm `interface ProductSummary`, `type SearchRequest`… ngoài `api.gen.ts` → 0 kết quả).
4. Không component nào gọi `fetch` trực tiếp.
5. Mọi trường Web đọc ở §4 tồn tại trong schema tương ứng của OpenAPI.
6. Mọi mã lỗi ở §8 tồn tại trong enum `ErrorCode`.
7. Chế độ mock dựng đủ 8 màn hình và mọi ca biên §11.
8. Đổi `NEXT_PUBLIC_API_MOCK=0` và trỏ `NEXT_PUBLIC_API_BASE_URL` sang backend thật mà không sửa dòng nào trong `services`.
9. Mọi link sản phẩm trong app có dạng `/product/{productId}`; không có chuỗi `bookingUrl` trong code Web.
10. Đổi tài khoản demo xóa sạch giỏ, gợi ý và hội thoại của người trước.
11. Với fixture `createItinerary.200-completed-invalid-slots`, slot `nt-a-02` (`available: false`) và slot `dn-a-01` (sai điểm đến) không render thành thẻ.

## 14. Definition of Done

> Team Web dựng cả tám màn hình và mọi ca biên chỉ bằng type sinh từ `openapi.yaml` và fixture trong `src/shared/mocks/`, rồi đổi sang backend thật mà không sửa tầng `services`; Team Backend và Team Agent chạy contract test trên cùng file OpenAPI và cùng bộ fixture.
