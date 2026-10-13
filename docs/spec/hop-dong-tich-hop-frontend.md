# Hợp đồng tích hợp Frontend

> **MVP 1.2.0:** ưu tiên hiển thị recommendation; [bộ trường tối thiểu](mvp-minimal-fields-1.2.0.md) và OpenAPI hiện hành thay thế danh sách required/optional cũ bên dưới. Các trường mở rộng vẫn được hỗ trợ nhưng không bắt buộc gửi.

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
- Gọi HTTP **chỉ** qua `src/frontend/src/services/`; component không gọi `fetch` trực tiếp (`architecture-repo.md` §6).
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

- Stream SSE cho trợ lý (D9, hoãn — §12).
- Thiết kế giao diện chi tiết: xem `docs/product.md` §4–§7.
- Insider clone, CDP clone, thuật toán xếp hạng. Web không gọi CDP clone; mọi hành vi đi qua Backend (`hop-dong-tich-hop-cdp.md`).

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
| `/hotels`, `/flights`, `/combos` | Trang danh mục: khách sạn & resort, vé máy bay, combo (đề xuất PRD `update-archive/2026-09-29-route-trang-danh-muc-dich-vu.md`) | Không | `destination`; `q` (có `q` là đang tìm: kết quả hiện ngay dưới tấm tìm kiếm, §4.1a; `/hotels` và `/combos`) kèm ngữ cảnh chuyến đi `checkIn`, `checkOut`, `adults`, `children`, `rooms`. `/flights` có `origin` **và** `destination` thì hiện chuyến bay của lần tìm dưới tấm tìm kiếm (§4.1b), kèm ngữ cảnh chuyến đi `checkIn`, `checkOut`, `adults`, `children`; không có thì hiện lời nhắc nhập |
| `/experiences` | Trang danh mục: tour và trải nghiệm | Không | `destination`, `type` (`attraction` mặc định \| `golf`), `q` và ngữ cảnh chuyến đi như `/hotels` (kết quả chỉ trong tab đang chọn) |
| `/search` | Kết quả tìm kiếm | Không | `q` (bắt buộc), `type` (hoặc `taxonomy`): `stay` \| `exp` \| `more` — nhận cả taxonomy cũ `hotel`, `attraction`, `golf`, `combo`; không có thì là tab Tất cả; `flight` chỉ khi mở từ `/flights` (danh sách phẳng, không tab), `destination` (chip ✕ ở "Đang lọc", không có checkbox); ngữ cảnh chuyến đi `checkIn`, `checkOut`, `adults`, `children`, `rooms` (§4.1a) |
| `/product/{productId}` | Chi tiết sản phẩm | Không | ngữ cảnh chuyến đi tùy chọn `checkIn`, `checkOut`, `adults`, `children`, `rooms` (điền sẵn hộp đặt, §4.1a) |
| `/cart` | Giỏ hàng | Có | — |
| `/checkout` | Checkout | Có | — |
| `/profile` | Hồ sơ cá nhân: sửa họ tên, số điện thoại, đổi mật khẩu (FR-USR-04, §4.6b) | Có (chưa đăng nhập thì hiện lời mời đăng nhập, mở hộp đăng nhập) | — (đường dẫn cũ có `tab`, `taxonomy`, `days` hoặc `page` được chuyển sang `/profile/booking_history` giữ nguyên bộ lọc) |
| `/profile/booking_history` | Lịch sử đặt chỗ: ba tab, lọc, phân trang (FR-BKG-14, §4.6a) | Có (chưa đăng nhập thì hiện lời mời đăng nhập, mở hộp đăng nhập) | `tab` (`upcoming` mặc định \| `done` \| `cancelled`), `taxonomy` (`hotel` \| `flight` \| `attraction` \| `combo` \| `golf`), `days` (`1` \| `7` \| `30` \| `60`), `page` — giá trị lạ về mặc định |
| `/booking/{referenceCode}` | Trạng thái đơn / chi tiết đơn hàng (FR-BKG-15) | Có | `payment` (`return` \| `cancelled`) — do Backend đặt vào `success_url`/`cancel_url` của phiên Stripe |
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
| ① Gợi ý cá nhân hóa | `GET /recommendations?k=4` | tùy | `strategy`, `nextVertical`, `destination`, `recommendations[]` (`rank`, `productId`, `name`, `taxonomy`, `destination`, `unitPrice`, `currency`, `available`, `imageUrl`, `attributes`, `score`, `because[]`), `diagnostics.excludedVerticals`, `diagnostics.coldStart` | 5xx / timeout > 10 giây (`RECOMMENDATION_TIMEOUT_MS`, §6.4) → ẩn ①, hiện dòng "Chưa tải được gợi ý · Thử lại". Chưa có kết quả thì chưa hiện khối, không hiện bản cũ. Khách vãng lai → không gọi, hiện banner đăng nhập |
| ② Đã xem gần đây | — | — | — | **Bỏ section** (D13) |
| ③ Thẻ trợ lý | dùng lại response ① | — | `destination` | Không có → câu chung |
| ④ Phổ biến | `GET /products?sort=popular&availableOnly=true&limit=8`, thêm theo tab (contract 1.27.0): Tất cả `diversify=taxonomy`; Khách sạn / Vé máy bay / Combo `taxonomy=<loại>`; Vé tham quan `taxonomy=attraction,golf` | — | `results[]` (`ProductSummary`) | **Luôn render**. Một carousel có tab Tất cả · Khách sạn · Vé máy bay · Vé tham quan (gồm sân golf, không có tab Golf riêng) · Combo; **chỉ tab đang chọn gọi API**, mỗi tab một request. Tab Tất cả do Backend trộn theo nhóm loại (2 ô mỗi nhóm trong 8 ô khi đủ hàng) và là kệ duy nhất hiện nhãn loại trên thẻ (`TaxonomyBadge`); các tab khác không có nhãn. Lỗi → "Chưa tải được · Thử lại" cục bộ |
| Điểm đến ("Bạn muốn đi đâu?") | `GET /destinations` | — | `destinations[].destination`, `productCount` | Chỉ gọi khi khối tới gần vùng nhìn (≤ 300 px), bộ đệm 5 phút dùng chung với tấm tìm kiếm. Lỗi hoặc rỗng → ẩn khối |
| Lối vào danh mục | — | — | — | Bốn ô tĩnh từ `navConfig.ts` → `/flights`, `/hotels`, `/experiences`, `/combos` |
| Gợi ý khi gõ ở ô tìm kiếm (FR-SRC-05) | `GET /search/suggestions?q=&limit=8` | — | `suggestions[]` (`type` = `destination` \| `product`, `label`, `productId`, `taxonomy`, `destination`, `productCount`) | Chỉ gọi khi có ≥ 2 ký tự chữ/số, sau 200 ms không gõ; huỷ lượt cũ; bộ nhớ đệm trang 50 khoá / 5 phút. Lỗi → "Chưa tải được gợi ý", vẫn có "Xem tất cả". Không tính vào ngân sách request khi tải trang vì chỉ gọi lúc gõ. Ô rỗng không gọi |

**Ngân sách request của Home:** khách ≤ 1 request khi tải (khối ④ nếu trong vùng nhìn), đã đăng nhập ≤ 2 (thêm ①); các khối dưới màn hình chỉ tải khi cuộn tới (`useInView` + `useLazySection`). ① quá 10 giây (`RECOMMENDATION_TIMEOUT_MS`) thì ẩn khối và hiện dòng "Thử lại".

### 4.1a. Trang danh mục `/hotels`, `/flights`, `/experiences`, `/combos`

Một template (`features/catalog/landing`), cấu hình ở `verticals.ts`. Hero + tấm tìm kiếm, rồi các khối. **`/flights` là ngoại lệ** (đề xuất PRD `update-archive/2026-09-30-trang-ve-may-bay-tim-tai-cho-bo-khoi-pho-bien-va-gia-tot.md`): không có hai khối 1 và 2 dưới đây; bên dưới tấm tìm kiếm là kết quả chuyến bay hoặc lời nhắc nhập (§4.1b), rồi điểm đến và banner trợ lý.

**Tìm tại chỗ** (đề xuất PRD `update-archive/2026-10-07-tim-kiem-tai-trang-danh-muc.md`): ở `/hotels`, `/experiences`, `/combos`, URL có `?q=` là đang tìm. Hero thu gọn, kết quả của tab đang chọn hiện ngay dưới tấm tìm kiếm (`features/catalog/landing/LandingResults.tsx`, dùng lại `components/search/GroupResults.tsx`) thay cho hai khối 1, 2, điểm đến và banner trợ lý; không có `?q=` thì là trang danh mục như bảng dưới.

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Khối 1 "… phổ biến" (tải ngay) | `GET /products?taxonomy=<t>&sort=popular&availableOnly=true&limit=8` (+ `destination` khi có `?destination=`) | — | `results[]` (`ProductSummary`) | Lỗi → "Chưa tải được · Thử lại" tại khối. Rỗng → "Chưa có {loại} tại {điểm đến}" + liên kết `/search` |
| Khối 2 "… giá tốt nhất" (tải khi vào vùng nhìn) | như trên với `sort=price_asc` (sản phẩm chưa có giá xếp cuối) | — | như trên | Dưới 3 thẻ hoặc lỗi rỗng → ẩn khối |
| Kết quả tìm kiếm (chỉ khi có `?q=`; thay khối 1, 2 và điểm đến) | `POST /search` một lần cho loại của tab (`taxonomy`; `/experiences` chỉ attraction **hoặc** golf), `destination` khi có, `travelContext.guests` khi URL có số người lớn và `travelContext.checkIn` / `checkOut` khi URL có ngày (xem dưới), `limit: 20`, `offset += 20`, qua bộ đệm 60 giây như §4.2 | tùy | `results[]` (`ProductSummary` + `score`), `total` | Lỗi → "Thử lại"; rỗng → "Chưa tìm thấy dịch vụ nào cho …" + "Nhờ Trợ lý AI gợi ý"; rỗng do lọc → "Xóa bộ lọc" |
| Điểm đến (tải khi vào vùng nhìn) | `GET /destinations` | — | `destination`, `productCount` | Lỗi hoặc rỗng → ẩn khối |
| Gợi ý điểm đến trong tấm tìm kiếm (vé máy bay: cả ô Điểm đi) | `GET /destinations` | — | như trên | Lỗi → vẫn gõ tự do được |

`/experiences` có hai tab (`?type=attraction|golf`); các trang khác một tab. Tấm tìm kiếm gửi bằng điều hướng về **chính trang danh mục** `/{hotels|experiences|combos}?q[&type][&destination]&checkIn&checkOut&adults&children&rooms` (`searchHref.ts` `buildSearchHref`; `type` chỉ ghi khi không phải tab đầu; vé máy bay **không** rời trang: tìm ngay tại `/flights`, §4.1b): điểm đến chọn từ gợi ý (hoặc gõ đúng nhãn) thành `destination`, còn lại vào `q` (rỗng thì dùng câu mặc định theo danh mục, `services/search.ts` `DEFAULT_QUERY`; câu mặc định không hiện thành "Kết quả cho …"). Mở lại URL thì tấm tìm kiếm được điền sẵn từ `destination`, `q` (chữ tự do), ngày, số khách và số phòng. Kết quả có bộ lọc hạng sao và giá (chỉ khách sạn; gửi lên API cùng số khách và ngày, §4.2), popup sắp xếp và "Xem thêm" như tab nhóm của `/search`; ngày và số khách mang tiếp tới liên kết sản phẩm. Băng "kết quả yếu" chỉ có ở `/search`.

**Số khách là bộ lọc thật ở trang danh mục** (đang tìm bằng `?q=`): gửi `travelContext.guests` (contract 1.16.0, hard filter sức chứa; sản phẩm chưa khai sức chứa vẫn giữ). Backend so `adults + children` với sức chứa của **một** hạng phòng, nên nhiều phòng thì chia đều làm tròn lên (4 người ở 2 phòng gửi 2; `LandingResults.guestsOf`); không có số người lớn trên URL thì không gửi. `/search` không gửi.

**Ngày là bộ lọc thật ở trang danh mục** (đề xuất PRD `update-archive/2026-10-07-loc-theo-ngay-o-tim-kiem.md`, contract 1.19.0): gửi `travelContext.checkIn` (+ `checkOut` khi có, ví dụ khách sạn nhiều đêm) cùng `guests` (`LandingResults.stayOf`). Backend loại sản phẩm không dùng được vào khoảng ngày đó (khách sạn: ngoài luật đặt phòng hoặc mọi hạng phòng kín lịch; vé tham quan, golf, combo: ngoài cửa sổ mở bán hoặc ngày kín lịch); thiếu dữ liệu lịch thì giữ. Lịch không chặn đặt chỗ nên khách sạn bị loại vẫn đặt được nếu mở thẳng trang chi tiết. `/search` không gửi ngày.

**Ngữ cảnh chuyến đi** (`features/search/tripContext.ts`) còn điền sẵn ngày và số khách ở trang chi tiết (hộp đặt của vé, thanh ngày/số khách của khách sạn). `/search` không hiển thị ngữ cảnh này (không chip ngày/số khách, vì hộp đặt ở trang chi tiết đã có chỗ chọn) mà chỉ nối query vào liên kết sản phẩm; kết quả ở trang danh mục chỉ ghi nó thành một dòng ngắn cạnh tiêu đề; trang `/product/{id}` điền sẵn ngày, số khách, số phòng nếu hợp lệ (ngày nằm trong `availableFrom`–`availableTo`, riêng khách sạn: nhận phòng từ hôm nay đến hôm nay + 3 tháng, trả phòng sau 1–30 đêm, theo FR-CAT-03). Giá trị sai bị bỏ im lặng (riêng sức chứa của khách sạn: không bỏ, mà khoá nút Đặt ngay của hạng phòng không chứa nổi, xem §4.3); Backend vẫn quyết định (`DATE_OUT_OF_RANGE`, `VALIDATION_ERROR`). Luật đoàn theo FR-BKG-08: tối đa 9 khách mỗi mục; khách sạn tối đa 9 khách mỗi phòng và 9 phòng (`maxGuestsFor(rooms)`, ví dụ 2 phòng tối đa 18 khách); mỗi phòng ít nhất 1 người lớn. Không đưa họ tên hay token vào URL.

Sau checkout (cờ `justBooked`): gọi lại ① bỏ qua cache. Chỉ hiện toast "Trang chủ đã cập nhật" khi `strategy` **hoặc** `nextVertical` khác lần gọi trước.

### 4.1b. Chuyến bay ngay trên `/flights`

Phục vụ FR-SRC-03 (vé máy bay chỉ duyệt và tìm ở `/flights`), FR-CAT-02, FR-CAT-03, FR-BKG-10. Không đổi contract, không thêm route. **Tìm ngay tại trang, không chuyển trang:** bấm Tìm thì chuyến bay hiện luôn dưới tấm tìm kiếm, hero và tấm tìm kiếm giữ nguyên để sửa tiếp; URL được cập nhật tại chỗ (`history.replaceState`) thành `/flights?origin&destination[&checkIn&checkOut&adults&children]` để chia sẻ, và vào thẳng URL đó cũng ra kết quả.

Chưa có lần tìm (vào `/flights` trơn, hoặc `/flights?destination=X` chỉ điền sẵn điểm đến) thì bên dưới chỉ có lời nhắc "Nhập chuyến đi để xem chuyến bay", rồi điểm đến và banner trợ lý. Bấm Tìm khi còn thiếu thì lời nhắc nói rõ thiếu gì: chưa nhập điểm đi, chưa chọn điểm đến, hoặc điểm đến gõ tay không khớp nhãn nào của `/destinations` (phải chọn từ gợi ý). Đã có kết quả mà lần Tìm sau thiếu thông tin thì kết quả cũ ở lại kèm lời báo. Tấm tìm kiếm của vé máy bay không dẫn sang `/search?type=flight` nữa (URL đó vẫn mở được trực tiếp). Code: `features/flights/` (`FlightsPage.tsx`, `results/`), dữ liệu qua `services/flights.ts`.

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Tuyến | `GET /products?taxonomy=flight&destination=<điểm đến>&limit=50` (mọi trang) | — | `attributes.level = route`, `originCity`, `originAirports`, `destinationAirports` | Không tuyến khớp điểm đi → "Chưa có chặng A → B" kèm các điểm đi có chuyến tới B. Lỗi → "Thử lại" |
| Chuyến của tuyến | `GET /products?parentProductId=<tuyến>&sort=price_asc&limit=50` (mọi trang) | — | `ProductSummary` tầng con: `unitPrice`, `available`, `availableFrom`, `attributes` (`airline`, `airlineCode`, `flightNumber`, `originAirport`, `destinationAirport`, `departureAt`, `arrivalAt`, `durationMinutes`, `nonstop`, `tripType`, `priceObservedAt`), `fareClasses` | Tuyến không có chuyến → "Chưa có chuyến bay đặt được" |
| Chiều về (chỉ khi khứ hồi) | như hai dòng trên với tuyến ngược (điểm đến = thành phố đi của chặng đi) | — | như trên | Không có tuyến ngược → báo và vẫn đặt được vé một chiều |
| Đặt vé | `POST /booking-drafts` một lần cho một hoặc hai chặng (qua `startBooking`) | không cần | mỗi chặng gửi `productId` của hạng đã chọn, `usingDate` = ngày bay, `guests` | Vé máy bay không vào giỏ (§4.5a). Lỗi → toast, ở lại trang, bấm lại được. Xong → `/checkout?draft=<draftId>`; đăng nhập khi bấm Thanh toán |

**Ô Điểm đi và Điểm đến** (`LandingSearchSheet`, `PlacePanel`, `recentPlaces.ts`) cùng là ô gõ có gợi ý, lấy từ `GET /destinations` (nhiều sản phẩm nhất trước, lọc theo chữ gõ không phân biệt dấu). Điểm đi vẫn gõ tự do được (gợi ý chỉ để chọn nhanh; tuyến khớp theo `matchRoute`). Chọn điểm đi xong thì con trỏ sang ô Điểm đến; điểm đã chọn ở ô này không được gợi ý ở ô kia. Mỗi ô có nhóm **"Tìm gần đây"** khi ô còn trống: tối đa 5 nhãn, mới nhất trước, có nút "Xóa", lưu ở `localStorage` của trình duyệt (`vota_flight_recent_origins`, `vota_flight_recent_destinations`; chỉ nhãn địa điểm, không token hay dữ liệu cá nhân, không gửi lên Backend). Ghi khi bấm Tìm với đủ điểm đi và điểm đến; nhãn được đổi về nhãn chuẩn của `/destinations`, và nhãn không còn trong `/destinations` thì không được gợi ý lại. Chỉ vé máy bay có lịch sử; các danh mục khác không đổi.

Quy tắc:
- **Mỗi hành trình một thẻ.** Các sản phẩm cùng hành trình có chung `fareClasses` nên được gom (`flightOptionsFromVariants`); chọn hạng nằm trong thẻ, giá và nút Chọn theo hạng đó. Bỏ vé khứ hồi (`tripType: roundTrip`), vé hết chỗ, không giá, `ticketed: false`, thiếu giờ bay. Khứ hồi đóng gói vẫn xem và đặt ở `/product/{id}`.
- **Chọn từng chặng** (FR-BKG-10): chiều đi rồi chiều về. Chiều về chỉ có chuyến cất cánh sau khi chiều đi hạ cánh (`canFollow`). Mỗi chặng là một mục của cùng một đơn nháp; trang thanh toán hiển thị hai chặng ngược chiều là một chuyến khứ hồi.
- **Chỉ hiện điều nguồn có.** `null` hoặc vắng mặt là chưa biết: không hiện hành lý ("0 kg"), suất ăn, điều kiện đổi khi `fareClasses` là `null`; hạng vẫn là "Giá rẻ nhất" khi `code` là `null`; `nonstop` vắng mặt thì không nhãn "Bay thẳng" và không lọt bộ lọc điểm dừng. Vé mô phỏng (`attributes.simulated` hoặc tên kết thúc "(giá minh hoạ)") có nhãn "Giá minh hoạ". `EXPIRED` hiện "Giá có thể đã thay đổi" và không khoá nút đặt (`docs/guide/hien-thi-hang-ve-may-bay.md`).
- **Dải ngày** chỉ có ngày còn chuyến (dữ liệu catalog thưa), kèm giá thấp nhất mỗi ngày và số chuyến. Ngày đã qua (giờ Việt Nam) bị bỏ. Mở ở đúng ngày khách tìm (`checkIn` của chiều đi, `checkOut` của chiều về) nếu ngày đó có chuyến.
- **Ngày khách tìm không có chuyến thì không tự đổi sang ngày khác** (quyết định 2026-10-08, thay quy tắc "mở ngày gần nhất" trước đó): không thẻ chuyến nào được hiện, dải ngày không có ngày nào được chọn, và trang báo "Không có chuyến bay {điểm đi} → {điểm đến} ngày {thứ}, {dd/mm/yyyy}" kèm nút cho ngày gần nhất có chuyến trước và sau ngày đó (`pickDate` trả `nearest`; thiếu phía nào thì chỉ có một nút). Khách bấm nút hoặc một ngày trên dải ngày mới xem chuyến của ngày ấy. Tấm tìm kiếm luôn gửi `checkIn` (mặc định ngày mai), nên ngày mặc định không có chuyến cũng nhận thông báo này. Chiều về: cùng quy tắc với ngày `checkOut`, tính trên các chuyến cất cánh sau khi chiều đi hạ cánh; khách không nhập ngày về thì mở ngày đầu tiên có chuyến nối được.
- **Bộ lọc** chạy client trên các chuyến của ngày đang xem vì Backend chưa lọc ngày, giờ, hãng: khung giờ theo buổi (Sáng 05–11, Trưa 11–14, Chiều 14–18, Tối 18–22, Khuya 22–05, tính theo giờ đi, đầu khung tính, cuối khung không tính; chọn nhiều), hãng (mặc định chọn hết), điểm dừng (Bay thẳng / Có điểm dừng). Giá trị không có chuyến nào ở ngày đang xem thì mờ và tự bỏ khỏi bộ lọc. Sắp xếp: giá thấp nhất (mặc định), giờ đi sớm nhất, giờ đi muộn nhất, bay nhanh nhất.
- **"Vé của tôi"** hiện các chặng đã chọn và **Tổng ước tính** = `estimateFares` của từng chặng theo số khách (`adults`, `children` từ URL, mặc định 1 người lớn), cùng công thức và cùng lời rào với hộp đặt (§4.3): Web không gửi số tiền, giá chính thức là `fares`/`lineTotal` của `BookingDraft`. Nút Đặt vé bật khi đủ các chặng cần thiết.
- Bộ đệm 60 giây của `loadSection` cho hai lời gọi trên; mỗi lần tìm khác dựng lại kết quả từ đầu (`key` theo URL), nên chuyến đã chọn, ngày và bộ lọc của lần trước không được giữ.

### 4.2. Search `/search`

Đề xuất PRD `update-archive/2026-09-30-trang-search-bo-diem-den-ve-may-bay-va-tab-theo-nhom.md`. Tab theo nhóm header: **Tất cả · Lưu trú (`hotel`) · Tour và trải nghiệm (`attraction` + `golf`) · Tiện ích khác (`combo`)**. Vé máy bay không nằm trong tìm kiếm ngữ nghĩa; `?type=flight` (từ `/flights`) là ngoại lệ, một danh sách phẳng không tab. Không có bộ lọc điểm đến; `?destination=` (từ liên kết cũ hoặc chọn điểm đến ở gợi ý tức thì) vẫn truyền cho API và hiện thành chip có ✕. Tấm tìm kiếm ở trang danh mục không còn dẫn sang đây: kết quả hiện ngay tại trang danh mục (§4.1a).

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Tab **Tất cả**: hàng theo nhóm | `POST /search` một lần cho mỗi taxonomy của nhóm (hotel · attraction + golf · combo), `limit: 6` | tùy | `results[]`, `total`, `topScore` | Lỗi → "Chưa tải được nhóm này · Thử lại" ngay hàng; nhóm 0 kết quả bị ẩn; tất cả 0 → EmptyState |
| Số kết quả các tab và dòng "Tìm thấy N dịch vụ phù hợp" | **cùng các request của hàng ở trên** (cùng khóa bộ đệm, không gọi thêm); ở tab nhóm vẫn gọi để có số cho cả bốn tab | tùy | `total` của từng nhóm (Tour và trải nghiệm = attraction + golf); Tất cả = tổng ba nhóm | Lỗi ở bất kỳ nhóm nào → tab không hiện số; tab 0 kết quả vẫn hiện |
| Tab nhóm: danh sách đầy đủ | như hàng, `limit: 20`, `offset += 20`; tab Lưu trú gửi thêm `starRatingMin` / `priceMax` khi có bộ lọc | tùy | `results[]` (`ProductSummary` + `score`), `total` | Lỗi → "Thử lại"; rỗng do lọc → "Xóa bộ lọc" |
| Băng "kết quả yếu" | response của các hàng | — | `topScore` cao nhất của các nhóm | `topScore < 0.35` → hiện băng; mọi nhóm `null` → không hiện |

Quy tắc:
- **Một nguồn đếm** (sửa 2026-10-12): số trên tab, số trên hàng ("N kết quả", "Còn N · Xem tất cả N"), mẫu số "Xem thêm (x/N)" và dòng "Tìm thấy N" đều là `total` của request lọc theo taxonomy. **Không** đếm tab bằng `facets.taxonomy` của một request không lọc taxonomy: backend tính tập kết quả trên tập đã lọc của từng request (top-K dense, 10 suất vớt BM25 dùng chung cho mọi loại kể cả vé máy bay; hợp đồng Search §2.2), nên facets đó thường nhỏ hơn `total` của request lọc theo loại — đo trên backend local ngày 12/10, câu "Nha Trang": tab 14 / 9 / 5 / 0, trong khi các hàng ra 13 / 12 / 9. Số không kèm dấu "+": ở hybrid `totalExact` luôn `false`, dấu này không mang thông tin.
- **Tất cả** chỉ lấy vài mục đầu mỗi nhóm (`PREVIEW_LIMIT` = 6) để tải nhanh. Ba hàng tải cùng lúc (số trên tab cần cả ba). Cuối hàng có thẻ "Còn N kết quả · Xem tất cả"; "Xem tất cả" chuyển sang tab của nhóm, lúc đó mới tải trang đầy đủ (`GROUP_PAGE_SIZE` = 20, "Xem thêm" nối trang kế).
- Mọi lần gọi qua bộ đệm 60 giây của `hooks/useLazySection` (`useLazySection`, `loadSection`), khóa theo (truy vấn, điểm đến, nhóm, limit, offset, bộ lọc); quay lại tab hoặc "Xem thêm" không tải lại trang đã có. Đổi tài khoản thì xóa bộ đệm (§7 điều 7). Hệ quả: cùng truy vấn tìm lại trong 60 giây có thể không sinh thêm event `search` phía Backend.
- Hàng cuộn ngang có nút trái/phải ở giữa chiều cao hàng, sát hai bên: nút trái ẩn ở đầu hàng, nút phải ẩn ở cuối hàng hoặc khi hàng không tràn; dưới `md` chỉ vuốt (`components/search/HScroller.tsx`).
- **Sắp xếp** là popup ("Sắp xếp: Phù hợp nhất ▾": Phù hợp nhất · Giá thấp → cao · Giá cao → thấp) ở mọi tab trừ Tất cả. Backend chưa nhận `sort` nên sắp xếp chạy trên các mục đã tải (`sortItems`); mục chưa có giá luôn xếp cuối.
- **Hạng sao và giá tối đa** chỉ ở tab Lưu trú, gửi lên API (`starRatingMin`, `priceMax`; contract 1.15.0, hợp đồng Search §2.5): giá lọc cứng trên giá thấp nhất kể cả phòng con, sản phẩm chưa có giá bị loại; sao lọc mềm, sản phẩm khai sao thấp hơn bị loại, chưa khai sao vẫn giữ và xếp sau. Đổi bộ lọc thì về trang 1; thanh trượt giá chỉ gọi API sau khi dừng kéo 400 ms. Số trên tab là số **chưa** áp sao/giá; khi đang lọc, thanh "Đang lọc" ghi thêm "· N kết quả theo bộ lọc".
- Nhóm Tour và trải nghiệm là hai request (attraction, golf) trộn theo `score`.

`503 SEARCH_UNAVAILABLE` → `ErrorState` có "Thử lại", giữ nguyên truy vấn trong ô.

**Ô tìm kiếm đầu trang** (`components/common/SearchBox.tsx`) dùng chung hook và panel gợi ý tức thì với hero Home (`features/search/instant/`, FR-SRC-05): `GET /search/suggestions`, không phải `POST /search`, nên gõ không sinh event `search` và không đổi bộ đệm 60 giây ở trên. Mic, chữ lớn, chip gợi ý và Enter giữ nguyên.

### 4.3. Product detail `/product/{productId}`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Thông tin, hộp đặt | `GET /products/{productId}` | — | `ProductDetail` đầy đủ, `variantSummary` | `404 PRODUCT_NOT_FOUND` → trang "Sản phẩm này không còn trên V-OTA" + carousel `GET /products?sort=popular` |
| Chọn hạng phòng / chuyến bay | `GET /products?parentProductId={productId}&sort=price_asc` | — | `results[]` (`ProductSummary` của tầng con) | Chỉ gọi khi `attributes.level` là `property` hoặc `route`. Rỗng → "chưa có hạng phòng/chuyến bay đặt được", khoá nút đặt. Lỗi → dòng thông báo, khoá nút đặt |
| Hoàn thiện chuyến | `GET /recommendations?k=4&destination=<product.destination>` | bắt buộc | như Home ① | Chỉ render khi `destination` response trùng sản phẩm |
| Thêm vào giỏ (chỉ `attraction`, `golf`, `combo`) | `POST /cart/items` | không cần | gửi `productId`, `usingDate`, `guests` (số người lớn và trẻ em) và `quantity` (combo); đọc `CartResponse.itemCount` (badge header) | Xem §8. `400 VALIDATION_ERROR` → toast `message`. Khách sạn và vé máy bay **không có nút này**, chỉ có Đặt ngay kèm dòng "được đặt trực tiếp, không thêm vào giỏ hàng" |
| Đặt ngay (mọi loại) | `POST /booking-drafts` | không cần | gửi `items[]` một phần tử: `productId`, `usingDate`, `nights` (khách sạn), `guests`, `quantity` (khách sạn, combo); đọc `draftId` | Xong → `/checkout?draft=<draftId>`: chỉ thanh toán sản phẩm này, không kèm mục nào trong giỏ. Lỗi → toast, ở lại trang |
| Ghi lượt xem | `POST /events` `{ eventName: "product_view", productId }` | bắt buộc | — (`202` không body) | Không JWT thì không gọi. Mọi lỗi bỏ qua im lặng, không hiện gì cho người dùng |

**Không có mục "Tương tự"** ở trang chi tiết (quyết định 2026-10-07: tương đồng ngữ nghĩa không phải lý do đúng để đề xuất thêm ở đây); Web không gọi `GET /products/{productId}/similar`, endpoint vẫn do Backend cung cấp cho Agent.

**Ảnh và tiện ích** (`components/detail/ProductGallery.tsx`, `AmenityList.tsx`): bộ ảnh đầu trang đọc `attributes.images` (một ảnh lớn, tối đa bốn ảnh nhỏ, nút "N ảnh", trình xem ảnh lớn). Mục "Tiện ích khách sạn" đọc `attributes.amenities` của sản phẩm. Mỗi hạng phòng trong danh sách chọn phòng (`GET /products?parentProductId=`, `components/detail/RoomCard.tsx`) là một thẻ: ảnh lớn bên trái (`imageUrl`, nút "Xem ảnh phòng (N)" mở các ảnh của riêng phòng `attributes.images`); tên phòng; thông số mỗi mục một icon (`maxOccupancy`, `roomSizeM2`, `bed`, `bedrooms`, `oceanView`, `familyFriendly`); tối đa 5 tiện ích nổi bật có icon (Wifi, điều hoà, bồn tắm, vòi sen, TV, ban công, két… chọn theo thứ tự quan trọng, mỗi loại icon một lần); nút "Tiện ích phòng (N)" mở toàn bộ `attributes.amenities` của phòng, mỗi mục một icon theo loại (`amenityIcons.ts`, nhận chữ tiếng Việt không phân biệt dấu; không nhận ra thì dấu tích); giá lớn "/ đêm" kèm "Đã gồm thuế & phí"; nhãn "Giá tốt nhất" ở hạng rẻ nhất khi có từ hai hạng bán được; nút giả "Chọn phòng" / "Đã chọn" (cả thẻ là một ô `role="radio"`). Hạng không bán được hiện "Hết chỗ" và không chọn được. Nút ảnh và tiện ích nằm trên ô chọn nên bấm không đổi lựa chọn. Chuyến bay vẫn dùng hàng gọn cũ.

**Thanh phân cấp** (`components/detail/ProductBreadcrumb.tsx`): Trang chủ › {Loại} tại {điểm đến} › tên sản phẩm (mục cuối không phải liên kết). Mục giữa là liên kết thật về trang danh mục của loại (`/hotels`, `/experiences` kèm `type=golf` cho sân golf, `/combos`; vé máy bay về `/flights?destination=`) với kết quả của điểm đến đó và **giữ ngày, số khách** của tấm tìm kiếm trên URL (`checkIn`, `checkOut`, `adults`, `children`, `rooms`); không dẫn sang `/search`, trang gộp dành cho câu tìm tự do. Không có điểm đến thì bỏ mục giữa. Kiểu dáng: chữ 14px, mỗi mục là vùng bấm cao tối thiểu 32px bo góc có nền `brand-50` khi rê chuột, "Trang chủ" có icon nhà, mục hiện tại là chip xám đậm; trên điện thoại thanh cuộn ngang một dòng.

Gọi `POST /events` **một lần** khi trang chi tiết đã hiển thị trên trình duyệt với người dùng đã đăng nhập; không gọi trong Server Component, khi prefetch link hay khi render lại cùng sản phẩm. Web không gửi event `search` hay `add_to_cart`: Backend tự ghi khi xử lý `/search`, `/cart/items` và `/booking-drafts`.

Khách sạn (`property`) và tuyến bay (`route`) không đặt trực tiếp: `POST /booking-drafts` gửi `productId` của **tầng con**. Tuyến bay dùng hộp đặt dính bên phải theo mục tầng con khách đã chọn (mặc định mục rẻ nhất còn đặt được); chưa có chuyến bay đặt được thì nút Đặt ngay bị khoá.

**Khách sạn không có hộp đặt dính** (quyết định 2026-10-08): khách đi từ kết quả tìm kiếm đã mang sẵn ngày và số khách trên URL nên không cần chọn lại ở một hộp riêng. Trên cùng trang, phía trên thanh phân cấp, có thanh tìm kiếm cùng kiểu với tấm tìm kiếm ở trang danh mục (`components/detail/HotelTripBar.tsx`: ô địa điểm điền sẵn tên khách sạn, gõ được và có gợi ý điểm đến (`GET /destinations`), ngày ở kèm số đêm, số phòng và khách, nút tìm; dùng lại `DateRangePicker` và `GuestsPopover`; điền sẵn từ URL, khách vào thẳng trang vẫn sửa được, lỗi ngày hiện dưới thanh; giữ nguyên ô địa điểm thì nút tìm ghi ngày và đoàn khách lên URL rồi cuộn tới hạng phòng; đổi địa điểm thì sang `/hotels?q=…&destination=…` kèm ngày và số khách, như tấm tìm kiếm ở trang danh mục), và **nút Đặt ngay nằm trên từng thẻ hạng phòng** (`RoomCard.tsx`), bấm là tạo đơn nháp cho hạng phòng đó với ngày và đoàn khách đang hiện. Trên danh sách phòng có bộ lọc tiện ích phòng (`RoomAmenityFilter.tsx`, từ hai hạng phòng trở lên và khi có ít nhất một tiện ích): chip nhiều lựa chọn, kèm số phòng có tiện ích đó, phòng phải có đủ mọi tiện ích đã chọn, đọc `attributes.amenities` của từng hạng phòng và lọc ngay trên trình duyệt (không gọi API; bỏ mục chỉ là diện tích "N m²"), hiện "x/y hạng phòng phù hợp", "Xoá bộ lọc" và trạng thái rỗng khi không phòng nào hợp. Không còn ô chọn phòng, hạng phòng mặc định hay tổng ước tính trên trang (tổng tiền do bước thanh toán tính). Hạng phòng không chứa nổi đoàn khách (`maxOccupancy` × số phòng) có nút Đặt ngay khoá kèm dòng "cần ít nhất N phòng"; hạng khác vẫn đặt được. Trang của một hạng phòng lẻ (không phân tầng) hiện đúng thẻ của nó và thanh ngày/số khách. Sản phẩm không phân tầng đặt bằng chính `productId` của nó. Chuyến bay có một ngày cố định (`availableFrom = availableTo`) nên ngày hiện ở dạng chỉ đọc.

Đặt ngay gửi `nights` chỉ khi `taxonomy = hotel`. Bộ đếm khách theo loại dịch vụ (spec `booking/checkout-nhieu-buoc-hanh-khach.md` §6.9): vé tham quan, golf, chuyến bay có Người lớn (≥ 1) và Trẻ em (≥ 0) kèm đơn giá từng loại, và gửi `guests` (không gửi `quantity`, Backend tự tính bằng `adults + children`); khách sạn có số phòng, người lớn, trẻ em (ở thanh `HotelTripBar`, không còn gợi ý chung "Tối đa N khách/phòng" vì mỗi hạng phòng một sức chứa) và gửi cả `quantity` (số phòng) lẫn `guests`; combo chỉ có số gói và chỉ gửi `quantity`. Tối đa 9 khách mỗi mục, mỗi phòng ít nhất 1 người lớn; nút thêm khoá khi lựa chọn chưa hợp lệ. Tổng tiền trong hộp đặt là **ước tính hiển thị** theo các dòng giá của spec đó (§4.3, §4.4); giá chính thức là `lineTotal` và `fares` do backend trả.

### 4.4. Cart `/cart`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Danh sách, tóm tắt | `GET /cart` | không cần | `items[]` (`cartItemId`, `product`, `usingDate`, `quantity`, `nights`, `guests`, `fares`, `lineTotal`), `itemCount`, `subtotal`, `total`, `currency` | `items: []` → EmptyState. Mục có `product.available: false` → viền đỏ, khóa CTA checkout |
| Sửa / xóa | `PATCH` / `DELETE /cart/items/{cartItemId}` | không cần | gửi `guests` (và `quantity` với combo); toàn bộ `CartResponse` thay thế state | `404 CART_ITEM_NOT_FOUND` → tải lại `GET /cart`. `400 VALIDATION_ERROR` → toast `message`, giữ bộ đếm để sửa tiếp |
| Gom nhóm "Chuyến {destination}" | — | — | `items[].product.destination` | Client tự gom |

Mỗi mục hiện "2 người lớn · 1 trẻ em" (từ `guests`) và các dòng giá (`fares`); nút [Sửa] mở cùng bộ đếm với trang chi tiết và gọi `PATCH` khi bấm Cập nhật. Đơn giá vé trẻ em (`attributes.childPrice`) không nằm trong `CartResponse`, nên Web tải `GET /products/{productId}` khi mở [Sửa]. Mục hết chỗ không có [Sửa].

Web **không** tự cộng tiền. Mọi con số tiền trên trang giỏ lấy từ `CartResponse`.

Giỏ chỉ có tour, trải nghiệm và tiện ích khác (`attraction`, `golf`, `combo`); trang có dòng ghi chú khách sạn và vé máy bay được đặt ngay ở trang sản phẩm. Khách chưa đăng nhập xem và sửa giỏ của mình như người đã đăng nhập (giỏ giữ 3 ngày, gộp vào tài khoản khi đăng nhập, §7). Trang giỏ **không** còn khối "Thường được đặt cùng chuyến" và không gọi `/recommendations`. Nút "Tiến hành đặt chỗ" mở `/checkout` (thanh toán giỏ).

### 4.5. Checkout `/checkout`

Ba bước trên cùng một route, bước hiện tại ở `?step=travelers|services|review`, mỗi lần chuyển bước là một mục trong lịch sử trình duyệt (spec `booking/checkout-nhieu-buoc-hanh-khach.md` §6). Chỉ sửa giỏ ở hai bước đầu; không giữ chỗ, không tạo đơn, không gọi Stripe cho tới khi bấm Thanh toán.

**Hai nguồn mục (§4.5a).** `/checkout` thanh toán toàn bộ giỏ. `/checkout?draft=<draftId>` thanh toán đúng một đơn nháp của Đặt ngay; mọi chỗ bảng dưới ghi `GET /cart` và `PATCH /cart/items/…` thì với đơn nháp là `GET /booking-drafts/{draftId}` và `PATCH` / `DELETE /booking-drafts/{draftId}/items/{cartItemId}`, cùng hình dạng mục. Tham số `draft` được giữ khi chuyển bước (`?draft=…&step=…`).

| Bước | Endpoint | Auth | Trường Web đọc / gửi | Khi lỗi |
|---|---|---|---|---|
| Tóm tắt (cả ba bước) | `GET /cart` (mỗi lần chuyển bước) | không cần | như §4.4 | `items: []` → chuyển `/cart` (đơn nháp: về trang chủ). Mục `product.available: false` → khoá nút Thanh toán |
| ① Hành khách | — (không gọi Backend) | — | Đoàn ít nhất 1 người lớn, tối đa bằng trần của mục lớn nhất trong đơn (`orderPartyCap`: đơn chỉ có khách sạn thì 9 × số phòng, đơn có mục khác thì 9); mỗi người có họ và tên đệm và tên (hai ô), trẻ em có ngày sinh; người liên hệ (`fullName`, `phone`; email khoá theo tài khoản, khách chưa đăng nhập thì để trống và không bị kiểm cho tới khi đăng nhập). Điền sẵn: số người lớn, trẻ em từ `guests` lớn nhất của giỏ; họ tên Người lớn 1 từ tài khoản nếu dùng được | Kiểm ở Web theo cùng bộ luật với Backend (spec §5.2). Bấm Tiếp tục khi còn lỗi: ở lại bước, hộp "Còn n thông tin cần sửa", con trỏ về ô lỗi đầu tiên |
| ② Dịch vụ | `PATCH /cart/items/{cartItemId}` cho mỗi mục có `guests` hoặc số phòng khác phân bổ (chờ 400 ms, các lần của cùng mục chạy lần lượt) | không cần | Chọn ai dùng từng dịch vụ; khách sạn xếp người vào phòng và chọn người đại diện. Đọc `fares`, `lineTotal` mới sau mỗi `PATCH` | `PATCH` lỗi → gắn lỗi vào thẻ dịch vụ. Bấm Tiếp tục kiểm luật dịch vụ (spec §5.3) |
| ③ Xem lại và thanh toán | `POST /bookings` | bắt buộc: chưa đăng nhập thì bấm Thanh toán mở hộp đăng nhập ngay trên trang (thông tin đã nhập còn nguyên), đăng nhập xong tự gửi tiếp | gửi `draftId` (khi thanh toán đơn nháp), `contact`, `travelers[]` (`travelerRef`, `type`, `surname`, `givenNames`, `birthDate` của trẻ em), `itemDetails[]` (`cartItemId`, `travelerRefs` hoặc `rooms[]` với `leadTravelerRef`, `specialRequest`); đọc `referenceCode`, `payment.checkoutUrl` | Xem §8. `201` → `window.location.assign(payment.checkoutUrl)` sang trang Stripe |

Phương thức thanh toán: chỉ Stripe (chọn sẵn); ví điện tử, chuyển khoản hiển thị vô hiệu hoá, nhãn "Sắp có" (`user-flow.md` §3.3). Nút **Thanh toán** ở bước ③ bị khoá tới khi đã đồng ý điều khoản (gộp việc xác nhận họ tên) và đã chọn phương thức, hoặc khi giỏ còn mục hết chỗ; khi đang gửi thì hiện trạng thái xử lý và chặn bấm lặp. Web không gửi số tiền; mọi số tiền hiển thị lấy từ `CartResponse` (`fares`, `lineTotal`, `total`).

Họ tên và ngày sinh chỉ nằm trong bộ nhớ của trang, không ghi `localStorage`, `sessionStorage`, URL hay cookie; tải lại trang thì mất và Web nói rõ điều đó. Web không gửi `guestNames` (chỉ client cũ gửi, spec §7.6). Hạn hoàn tiền hiển thị ở bước ③ tính theo FR-BKG-07 nhưng chỉ để hiển thị; Backend quyết định `cancellableUntil`.

**Rời trang khi chưa thanh toán (FR-BKG-01, AC-BKG-20).** Khách bấm logo, nút quay lại, "Sửa giỏ hàng", một liên kết khác trên trang hoặc Back của trình duyệt ở bước Hành khách thì Web hỏi lại bằng hộp "Rời trang thanh toán?" trước khi rời; đóng tab hoặc tải lại thì trình duyệt hỏi bằng hộp mặc định. Không gọi endpoint nào: đơn nháp tự hết hạn, tour và tiện ích đã nằm trong giỏ. `TravelContext.setNavigationGuard` cho trang đang mở đăng ký một guard cho `navigate()`. Chi tiết và giới hạn của nút Back: spec `booking/checkout-nhieu-buoc-hanh-khach.md` §6.2.

### 4.5a. Đặt ngay và đơn nháp

Phục vụ FR-BKG-01, AC-BKG-13…17. Bộ luật: `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`.

| Hành động | Endpoint | Auth | Web làm gì |
|---|---|---|---|
| Đặt ngay một sản phẩm, đặt vé máy bay, đặt một mục của lịch trình trợ lý | `POST /booking-drafts` (`items[]`; `allowPartial` chỉ khi đặt lại đơn) | không cần | `startBooking` trong `TravelContext`: tạo đơn nháp, báo các mục trong `rejectedItems`, tải lại giỏ (tour và tiện ích của lần đặt được chép vào giỏ), mở `/checkout?draft=<draftId>` |
| Đặt lại đơn chưa thanh toán xong | `POST /booking-drafts` (`fromBooking`) | bắt buộc | Trang đơn, §4.6 |
| Mở trang thanh toán của đơn nháp | `GET /booking-drafts/{draftId}` | không cần | Hiện đồng hồ "Phiên thanh toán còn mm:ss" theo `expiresAt`; không có lối "Sửa giỏ hàng"; nút quay lại về trang trước |
| Sửa số khách, bỏ một mục | `PATCH` / `DELETE /booking-drafts/{draftId}/items/{cartItemId}` | không cần | Như sửa giỏ ở checkout; chỉ đụng tới đơn nháp |

- **Đặt ngay chỉ thanh toán đúng các mục của lần đặt đó.** Giỏ đang có gì cũng không vào đơn. Giỏ chỉ được thanh toán từ màn hình giỏ.
- **`410 BOOKING_DRAFT_EXPIRED`** (khi tải, khi sửa hoặc khi bấm Thanh toán): màn hình "Phiên thanh toán đã hết hạn". Có khách sạn hoặc vé máy bay thì nói rõ lựa chọn đó không được giữ, kèm nút "Chọn lại phòng" (về trang sản phẩm) và "Tìm lại chuyến bay" (về `/flights`); mục có `inCart: true` thì ghi "vẫn nằm trong giỏ hàng" kèm nút "Về giỏ hàng". Response không kèm `details.items` thì Web suy từ đơn nháp đang mở.
- **`404 BOOKING_DRAFT_NOT_FOUND`**: "Không tìm thấy phiên thanh toán này" + nút về trang chủ.
- **`422 DIRECT_BOOKING_ONLY`** không xảy ra trong luồng bình thường (Web không hiện nút thêm giỏ cho khách sạn, vé máy bay); nếu gặp thì toast "Khách sạn và vé máy bay được đặt trực tiếp".
- Khách chưa đăng nhập: BFF phát cookie `vota_guest` (HttpOnly, 3 ngày) và gắn mã khách vào request; trình duyệt không đọc hay gửi mã này. Đăng nhập xong, BFF gộp giỏ và đơn nháp của khách vào tài khoản rồi xoá cookie (`docs/spec/hop-dong-tich-hop-auth.md`).

### 4.6b. Hồ sơ cá nhân `/profile` (FR-USR-04)

Hai trang `/profile` và `/profile/booking_history` dùng chung khung tài khoản (`features/profile/AccountShell.tsx`): menu trái có thẻ người dùng và hai mục trên máy tính, hai tab ngang trên điện thoại; mục đang mở theo địa chỉ trang.

| Khu vực | Endpoint | Auth | Trường Web đọc / gửi | Khi lỗi |
|---|---|---|---|---|
| Hồ sơ | `GET /api/auth/session` (đã có sẵn khi tải trang) | cookie phiên | `user.fullName`, `user.email`, `user.phone` | — |
| Sửa họ tên, số điện thoại | `PATCH /auth/me` | bắt buộc | gửi chỉ trường đã đổi (`fullName`, `phone`; `phone: null` xoá số); đọc lại `AuthUser` | `422 VALIDATION_ERROR` → "Thông tin chưa hợp lệ…"; mất mạng → "Mất kết nối…"; lỗi khác → "Chưa lưu được thông tin…". Giữ nguyên nội dung đang nhập |
| Đổi mật khẩu | `PUT /auth/password` | bắt buộc | `currentPassword`, `newPassword` (8–128 ký tự; ô nhập lại chỉ ở Web) | `401 INVALID_CREDENTIALS` → "Mật khẩu hiện tại không đúng." dưới ô đó; `400 WEAK_PASSWORD` → lỗi dưới ô mật khẩu mới; `429` → báo thử lại sau |

- Email chỉ xem. Họ tên bắt buộc, tối đa 100 ký tự; số điện thoại để trống hoặc đúng 10 chữ số bắt đầu bằng 0 (`features/profile/profileModel.ts`, cùng luật với Backend). Lỗi hiện dưới ô khi rời ô, không hiện lúc đang gõ; nút "Lưu thay đổi" chỉ bật khi có thay đổi hợp lệ.
- Lưu xong: `TravelContext.updateProfile` cập nhật ngay người dùng hiện tại (header, menu tài khoản) và BFF ghi họ tên, số điện thoại mới vào phiên, nên tải lại trang không hiện tên cũ (`services/server/proxy.ts`).
- Số điện thoại hồ sơ điền sẵn ô số điện thoại liên hệ ở bước thanh toán nếu người dùng chưa gõ gì (`components/checkout/useCheckout.ts`).
- Đổi mật khẩu thành công: BFF đăng xuất các phiên khác và cấp lại cookie cho phiên này (như `docs/spec/hop-dong-tich-hop-auth.md` §3.8 dòng J).

### 4.6a. Lịch sử đặt chỗ `/profile/booking_history` (FR-BKG-14)

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Danh sách đơn | `GET /bookings?tab=&taxonomy=&days=&page=&pageSize=5` | bắt buộc | `data[]` (`referenceCode`, `createdAt`, `status`, `tab`, `holdExpiresAt`, `cancellableUntil`, `paymentStatus`, `paymentFailureReason`, `total`, `items[]`), `pagination` | `401` → mời đăng nhập, đăng nhập xong tải lại; lỗi khác → "Chưa tải được đơn hàng của bạn" + "Thử lại" + `requestId`; `data` rỗng → trạng thái trống |

- Ba tab Sắp đến · Hoàn thành · Đã huỷ do **Backend** xếp (`tab` của mỗi đơn); Web không tự lọc hay đếm. Chip dịch vụ (Tất cả, Khách sạn, Vé máy bay, Vé tham quan, Combo, Sân Golf) và ô "Ngày đặt" (Tất cả, 1, 7, 30, 60 ngày qua) dùng chung cho cả ba tab. Bộ lọc nằm trên URL; đổi bất kỳ bộ lọc nào thì về trang 1; `page` vượt quá số trang thì lùi về trang cuối.
- Phân trang đánh số, 5 đơn mỗi trang; chỉ một trang thì ẩn.
- Nhãn thẻ: đơn `PENDING_PAYMENT` mà Backend đã xếp vào Đã huỷ là đơn giữ chỗ quá hạn, hiện "Hết hạn giữ chỗ" và có "Đặt lại" (`POST /booking-drafts` với `fromBooking`, như §4.6). Đơn `PENDING_PAYMENT` còn hạn có "Tiếp tục thanh toán" (mở `/booking/{referenceCode}`). Huỷ đơn làm ở trang chi tiết, không làm ở thẻ.
- Bố cục: thanh lọc (tab trạng thái, chip dịch vụ) dính ở đầu khi cuộn; số đơn và bộ lọc "Ngày đặt" ngay dưới; mỗi thẻ đơn có ô ngày của dịch vụ đầu tiên và chân thẻ nền riêng chứa tổng tiền và nút. "Ngày đặt" là danh sách thả xuống tự dựng (`features/bookings/DaysFilter.tsx`, không dùng ô chọn gốc của trình duyệt): rộng bằng nút hoặc ít nhất 11 rem, mép phải thẳng hàng với nút, dòng đang chọn có dấu tick, tự mở lên trên khi sát đáy màn hình; bàn phím mũi tên, Home/End, Enter, Esc.
- Trạng thái trống: chưa có đơn thì lời nhắn theo tab kèm nút "Tìm khách sạn" (tab Đã huỷ không có nút); đang lọc mà không khớp thì "Không có đơn nào khớp bộ lọc." kèm nút "Xoá bộ lọc".

### 4.6. Trạng thái đơn `/booking/{referenceCode}`

| Khu vực | Endpoint | Auth | Trường Web đọc | Khi lỗi / rỗng |
|---|---|---|---|---|
| Đơn đặt | `GET /bookings/{referenceCode}` (dùng bản trong state nếu có để hiện ngay) | bắt buộc | `status`, `holdExpiresAt`, `cancellableUntil`, `payment` (`status`, `amount`, `checkoutUrl`, `failedAttempts`, `failureReason`, `refundedAmount`), `cancellation`, `contact`, `groups[]` (mỗi mục: `fares`, `travelers`, `guestNames`), `total` | `404 BOOKING_NOT_FOUND` → "Không tìm thấy đơn đặt chỗ này" |
| Chờ xác nhận | `GET /bookings/{referenceCode}` lặp lại | bắt buộc | `status`, `payment.status` | `?payment=return`, `payment.status = SUCCEEDED` hoặc đồng hồ giữ chỗ về 0: hỏi lại 2 giây/lần, tối đa 15 lần, dừng khi `status` khác `PENDING_PAYMENT`. Quay về từ Stripe **không** phải bằng chứng đã trả |
| Huỷ đơn | `POST /bookings/{referenceCode}/cancel` | bắt buộc | `BookingResponse` thay thế state | Xem §8 |
| Tiếp theo cho chuyến | `GET /recommendations?k=4&destination=<groups[0].destination>` — **chỉ khi `CONFIRMED`**, gọi sau khi đơn đã hiển thị | bắt buộc | như Home ① | Lỗi hoặc rỗng → ẩn section, giữ CTA |
| CTA trợ lý | — | — | `groups[0].destination` | → `/assistant?destination=…` |

Hiển thị theo trạng thái (spec booking §5.1):

| `status` | Web hiển thị |
|---|---|
| `PENDING_PAYMENT`, `payment.status = OPEN` | "Đơn đang được giữ chỗ" + đồng hồ đếm ngược theo `holdExpiresAt` + nút "Tiếp tục thanh toán" (mở lại `checkoutUrl`) + "Huỷ đơn". Có `failureReason` thì hiện lý do lần trước và số lần còn thử. Đồng hồ về 0 → "Hết thời gian giữ chỗ", ẩn nút tiếp tục |
| `PENDING_PAYMENT`, `payment.status = SUCCEEDED` | "Đã nhận thanh toán, đang xác nhận đơn. Bạn có thể đóng trang." |
| `CONFIRMED` | Mã đặt chỗ, tóm tắt chuyến, gợi ý chặng tiếp, nút "Huỷ đơn" khi còn trước `cancellableUntil`; tải lại giỏ (Backend đã bỏ các mục vừa đặt) và bật cờ `justBooked` nếu vừa quay về từ Stripe |
| `PAYMENT_FAILED` | Lý do theo `failureReason` (spec booking §10.2) + "Đặt lại" |
| `EXPIRED` | "Hết thời gian giữ chỗ" + "Đặt lại" |
| `CANCELLED` | "Đã huỷ đơn" + trạng thái hoàn tiền theo `payment.status` (`REFUND_PENDING`, `REFUNDED`, `REFUND_FAILED`, hoặc `EXPIRED` = chưa thanh toán nên không hoàn) |

Trang là hai cột trên máy tính (một cột trên điện thoại), mở đầu bằng đường dẫn "Đơn hàng của tôi / Chi tiết đơn hàng" (FR-BKG-15). Cột trái: thẻ trạng thái ở trên; mỗi dịch vụ một khối "Thông tin đặt chỗ" (mốc nhận/trả phòng hoặc điểm đi/đến, cơ sở, tiện ích); Thông tin khách hàng; Thông tin hành khách hoặc khách lưu trú; Thông tin dịch vụ; Chính sách hoàn huỷ. Cột phải: Thông tin thanh toán (mã đơn, dòng giá, tổng, trạng thái, nút "Huỷ đơn" khi được huỷ). Tên, hạng sao, địa chỉ và tiện ích của khách sạn lấy từ `GET /products/{id}` của hạng phòng và của khách sạn cha, nạp sau khi đơn đã hiện; lỗi thì chỉ bỏ phần đó, không bịa địa chỉ. Giờ nhận phòng "Sau 14:00", trả phòng "Trước 12:00" và số tổng đài là giá trị mặc định chung ở `components/confirmation/bookingDefaults.ts` (số tổng đài hiện là số giả lập). Hạn hoàn 100% lấy từ `cancellableUntil` của Backend. **Chưa có trên trang:** trạng thái xuất vé và mã đặt chỗ của hãng (FR-BKG-12), vì `BookingResponse` chưa trả; diện tích phòng; giờ bay chính xác khi catalog không có.

Mỗi mục của đơn hiện hành khách và dòng giá (spec `booking/checkout-nhieu-buoc-hanh-khach.md` §6.8): khách sạn hiện khách theo phòng ("Phòng 1: …") và đánh dấu người đại diện nhận phòng (`isLead`); dịch vụ khác hiện một dòng tên, trẻ em có nhãn "(trẻ em)"; các dòng giá từ `fares`. Response không có ngày sinh nên trang không hiện. Đơn tạo trước thay đổi có `travelers` rỗng: hiện `guestNames` như trước.

**"Đặt lại"** (đơn `PAYMENT_FAILED`, `EXPIRED`, hoặc đồng hồ giữ chỗ đã về 0) gọi `POST /booking-drafts` với `{ fromBooking: referenceCode, allowPartial: true }` rồi mở `/checkout?draft=<draftId>`: các dịch vụ của đơn theo giá hiện tại, hành khách nhập lại. Có `rejectedItems` thì toast số dịch vụ không còn đặt được. Lỗi thì toast `message`, ở lại trang.

Hộp thoại huỷ: đơn `CONFIRMED` hiện số tiền hoàn (`payment.amount`), `cancellableUntil` và "không thể hoàn tác"; đơn chưa thanh toán ghi rõ không phát sinh tiền, tour và tiện ích của đơn vẫn nằm trong giỏ, khách sạn và vé máy bay cần đặt lại.

### 4.7. Login / Register

| Hành động | Endpoint | Trường gửi | Trường đọc | Lỗi |
|---|---|---|---|---|
Web gọi route BFF `/api/auth/*`, không gọi thẳng `/api/v1/auth/*` (docs/spec/hop-dong-tich-hop-auth.md §4). Response không bao giờ chứa token.

| Hành động | Endpoint | Trường gửi | Trường đọc | Lỗi |
|---|---|---|---|---|
| Đăng nhập | `POST /api/auth/login` | `email`, `password` | `state`, `user`, `csrfToken` | `401 INVALID_CREDENTIALS` → một thông điệp chung; `429 TOO_MANY_ATTEMPTS` → đếm ngược theo `Retry-After` |
| Đăng ký | `POST /api/auth/register` | `email`, `password`, `fullName` | như đăng nhập | `409 EMAIL_ALREADY_EXISTS` dưới trường email; `400 WEAK_PASSWORD` → `details.reasons`; `400 VALIDATION_ERROR` → `details.fields` |
| Khôi phục phiên | `GET /api/auth/session` | — | `state`, `user?`, `csrfToken` | Không bao giờ 401: khách nhận `state: anonymous` |
| Đăng xuất | `POST /api/auth/logout` | — | `204` | Cookie luôn bị xoá, kể cả khi backend lỗi |

### 4.8. Trợ lý (widget nổi, không có route riêng)

**Trạng thái mở đầu của widget nổi (FR-AGT-01, hỗ trợ AC-AGT-01):** Khi mở icon AI trong cuộc trò chuyện chưa có request, hiển thị lời chào ngắn và một ô nhập yêu cầu tự nhiên dạng search box. Chip Nghỉ dưỡng/Gia đình/Khám phá chỉ điền bản nháp, không tự gửi. Nút “Thêm thông tin chuyến đi” mở đúng form thông tin chuyến đi của chat (`TripDetailsForm`, AC-AGT-01): đủ các ô, không chọn sẵn điểm đến hay ngày đi, sở thích là 5 lựa chọn cố định; danh sách điểm đến chỉ tải qua service `GET /destinations` khi mở phần này (cập nhật 2026-10-12, thay form chọn nhanh cũ có điểm đến, phong cách và nhóm chọn sẵn). **Form thông tin chuyến đi** gửi đúng những gì đang hiện: số ngày và số người trên stepper luôn đi trong câu yêu cầu; ngày đi không tự điền (ô trống, hai nút chọn nhanh “Thứ 7 này”, “Thứ 7 tuần sau” tính từ `startDateMin`/hôm nay giờ Việt Nam), chưa chọn điểm đến hoặc ngày đi thì nút Xác nhận khoá; ngày trong câu yêu cầu viết `dd/mm/yyyy`. Khi gửi câu đầu, chuyển sang transcript với một ô nhập ở đáy. Enter gửi, Shift+Enter xuống dòng (dòng gợi ý phím tắt ẩn dưới `sm`); đang xử lý thì khóa gửi và cho dừng. Đóng/mở hoặc mở rộng giữ bản nháp; tạo cuộc mới xóa bản nháp và trở về màn mở đầu. Component của widget nằm trong `src/frontend/src/features/itinerary/widget/`; `components/assistant/AiFloatingWidget.tsx` giữ entry point tương thích.

| Hành động | Endpoint | Auth | Trường Web đọc | Ghi chú |
|---|---|---|---|---|
| Gửi tin nhắn | `POST /assistant/itineraries` | tùy | theo `status`, xem §9.3 | Nút "Dừng" hủy request bằng `AbortController` |
| Sửa chip ý định | cùng endpoint với `intentOverride` | tùy | như trên | §9.2 |
| Đặt ngay một mục của lịch trình | `POST /booking-drafts` (một mục) | không cần | `BookingDraft` | Mọi thẻ và ghim bản đồ của sản phẩm đặt được có nút "Đặt ngay"; mỗi mục một đơn nháp riêng. Lịch trình **không có** nút "Thanh toán tất cả" (bỏ từ 2026-10-08, trước mắt mỗi mục thanh toán riêng). Sản phẩm chưa đặt được (ví dụ khách sạn chưa có hạng phòng trong lịch trình) không có nút, thẻ vẫn mở trang chi tiết |
| Thêm vào giỏ từ kế hoạch (chỉ `attraction`, `golf`, `combo`) | `POST /cart/items` (mỗi mục một lần, tuần tự) | không cần | `CartResponse` cuối cùng | Một mục lỗi không chặn mục còn lại; tổng kết lỗi trong một toast. Nút theo thẻ, cạnh "Đặt ngay"; khách sạn và vé máy bay không có nút này. Mục đủ điều kiện: `available`, `unitPrice` khác null, `bookable` khác `false`, `attributes.ticketed` khác `false`; mỗi `productId` một lần. `usingDate` = `day.date` của slot; mỗi khách sạn trong `stays` (hoặc `stay`) lấy check-in = `days[0].date` + `fromNight − 1`, check-out = check-in + `nights` |
| Chỉnh nhanh lịch trình | cùng endpoint: `intentOverride.days` (1–7) hoặc `message` soạn sẵn nêu tên sản phẩm cần đổi | tùy | như trên | Khoá khi đang chạy; ẩn khi xem lịch trình đã lưu/chia sẻ |
| Danh sách điểm đến (thẻ hỏi lại) | `GET /destinations` | — | `destinations[]` | Dùng khi `suggestedValues.destination` rỗng |
| Nơi đi trong form gợi ý; "Dùng vị trí hiện tại" (AC-AGT-02, AC-AGT-03) | `GET /products?taxonomy=flight` (tuyến) | — | `attributes.originCity`, `originLatitude`, `originLongitude` | Ô `origin` khi `clarificationForm.fields` có `origin`, không bắt buộc; giá trị vào câu yêu cầu ("đi từ Hà Nội"). Chỉ khi bấm nút mới gọi `navigator.geolocation`; được phép thì chọn thành phố có sân bay gần nhất trong catalog (`services/flights.ts` `nearestDepartureCity`) và điền vào ô. Toạ độ không lưu, không gửi đi; từ chối/lỗi thì giữ ô để gõ tay |
| Vé máy bay của lịch trình | — (trong response) | — | `itinerary.flights[]`: `direction`, `date`, `returnDate`, `passengers`, `product` (`attributes.airline`, `flightNumber`, `departureTimeLocal`/`arrivalTimeLocal`, `nonstop`) | Thẻ chặng đi/khứ hồi mở đầu ngày đầu, chặng về khép ngày cuối (`WidgetDays`); giá hiện `unitPrice/khách × passengers`. Chỉ có "Đặt ngay" (`usingDate` = `date` của chặng), có trong "Thanh toán tất cả"; vé cũng có thẻ trong lời diễn giải (`narrationProducts`) |
| Thẻ ngày–giá của câu trả lời vé máy bay (FR-AGT-07, contract 1.25.0) | — (trong response) | — | `searchResults.flight[]` của `NEEDS_CLARIFICATION`: `unitPrice`, `attributes.departureAt`, `airline`, `flightNumber`, `originCity`, `destinationCity` | `WidgetFareDays`: một hàng thẻ (2 cột, 3–4 cột khi widget rộng) ở dòng đầu tiên nhắc chuyến; thẻ đầu là chuyến câu trả lời nêu. Mỗi thẻ là link `flightProductHref` → `/flights?origin&destination&checkIn=<ngày bay>`, bấm thì đóng widget (Ctrl/Cmd+bấm mở tab mới). Các chuyến thuộc nhiều tuyến thì thẻ ghi "Đi <nơi đến>". Tên chuyến trong chữ không mở panel chi tiết (vé không có trang chi tiết) |
| Nút dưới lịch trình (`COMPLETED`, 1.25.0) | — (trong response) | — | `suggestions` | Như nút của `NEEDS_CLARIFICATION`, chỉ ở tin nhắn mới nhất; bấm là gửi nguyên văn ("Đi Phú Quốc 3 ngày từ ngày 28/10/2026") |
| Xem lịch sử hội thoại | `GET /assistant/conversations` | bắt buộc | `data[]`, `pagination` | Mới nhất trước; chỉ của user hiện tại |
| Mở lại hội thoại | `GET /assistant/conversations/{conversationId}` | bắt buộc | `conversation`, `messages[]` | Nạp transcript rồi tiếp tục chat với cùng `conversationId` |
| Xem chi tiết sản phẩm trong widget (bấm thẻ hoặc tên trong lời diễn giải) | `GET /products/{productId}` | — | `name`, `description`, `imageUrl`, `attributes.images`, `attributes.address`, `attributes.latitude`/`longitude`, `attributes.openingHours`, `rating`, `reviewCount`, `unitPrice`, `priceUnit`, `available` | Panel ở cột phải (desktop), X/Esc về lịch trình. Thẻ gọn trong khung chat đặt sau lần nhắc đầu tiên, dữ liệu từ `itinerary`/`searchResults` của response (PRD `user-flow.md` §4.2). Không có danh sách bình luận vì catalog không có dữ liệu |

---

## 5. Hợp đồng dữ liệu của component dùng chung

Prop của component dùng **đúng tên schema** trong OpenAPI. Không có lớp map đổi tên trường giữa `services` và component.

| Component | Prop dữ liệu | Schema nguồn | Ghi chú |
|---|---|---|---|
| `ProductCard` | `product` | `ProductSummary` (hoặc `RecommendationItem`, `ScoredProduct` — cùng tập trường tối thiểu) | Trường tối thiểu dùng: `productId`, `name`, `taxonomy`, `destination`, `unitPrice`, `currency`, `available`, `imageUrl`, `attributes`. `rating`/`reviewCount` vắng mặt hoặc `null` → không render. Link luôn là `/product/{productId}`. Biến thể `tile` chỉ hiện `TaxonomyBadge` (góc trên trái ảnh) khi bật `showTaxonomy`; hiện chỉ khối ④ tab Tất cả ở Home bật |
| `TaxonomyBadge` | `taxonomy` | `Taxonomy` | Giá trị lạ → badge trung tính "Dịch vụ". Dùng ở giỏ, checkout và khối ④ tab Tất cả ở Home (nơi trộn nhiều loại mà không có tab theo loại) |
| `PriceTag` | `unitPrice`, `currency`, `taxonomy`, `prefix?` | `ProductSummary` | Hậu tố theo §6.2 |
| `AttributeTags` | `attributes`, `max` | `ProductAttributes` | Key lạ bỏ qua; `starRating` render bằng sao, không thành tag |
| `BecauseLine` | `because` | `BecauseItem[]` | Chỉ đọc `because[0]`; mảng rỗng → không render |
| `WhyPopover` | `because`, `strategy`, `destination`, `excludedVerticals`, `nextVertical` | `RecommendationResponse` | `because[].productId = null` → tên không link |
| `SectionHeader` | `strategy`, `destination`, `nextVertical`, `excludedVerticals`, `coldStart`, `context` (`home` \| `detail` \| `cart` \| `confirmation`) | `RecommendationResponse` | Bảng tiêu đề ở `docs/product.md` §5.3 |
| `TripChecklist` | `excludedVerticals`, `nextVertical` | `RecommendationDiagnostics` | Chỉ render khi `strategy = cross_vertical` |
| `ActivityNote` | `slot` | `ItinerarySlot` với `product: null` | Không giá, không nút, không ảnh |
| `ItineraryProductCard` | `slot` | `ItinerarySlot` với `product` khác `null` | `ProductCard` compact + `note` + nhãn "Hợp với bạn" khi `source = RECOMMENDATION`. Trong khung chat: `ProductCard` compact đặt sau dòng đầu tiên nhắc `[Tên](product:id)`, mỗi sản phẩm một lần; id không có trong `itinerary`/`searchResults` thì không render |
| `ErrorState` | `error` | `ErrorResponse.error` | `retryable: true` → nút "Thử lại" |

Không component nào nhận `priceString`, `price{}`, `category`, `bookingUrl` hoặc `semanticScore` — các trường đó không tồn tại trong v1.

---

## 6. Quy tắc client sở hữu

Backend chỉ trả **key và số**. Mọi quy tắc dưới đây là hằng số của Web, đặt trong feature tương ứng (không tạo `utils` chung, `architecture-repo.md` §12).

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
| `RECOMMENDATION_TIMEOUT_MS` | `10000` | Home ① |
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

### 6.7. Màu

Bảng màu "Travel Blue" (chốt 2026-10-08), khai báo một lần ở `src/frontend/src/app/globals.css` (`@theme static`); code dùng tên token, **không dùng `blue-*`/`indigo-*`/`violet-*` trực tiếp**, đổi màu cả app chỉ sửa ở đó:

| Token | Giá trị gốc | Vai trò |
|---|---|---|
| `brand` (50…950) | 600 = `#2563EB`, 700 = `#1D4ED8`, 100 = `#DBEAFE` | Đặt chỗ và điều hướng: nút chính (Tìm, Đặt ngay, Đăng ký), liên kết, trạng thái chọn, hero, focus |
| `secondary` | `#0EA5E9` | Điểm nhấn thông tin phụ (huy hiệu, minh hoạ), không dùng cho nút |
| `accent` | `#F59E0B` | Khuyến mãi và một hành động nổi bật mỗi màn hình |
| `ai` (50…950) | cùng giá trị với `brand` (600 = `#2563EB`); trước đó là tím `#7C3AED` | Trợ lý AI và gợi ý (widget nổi, banner trợ lý). Giữ token riêng để sau này đổi màu AI mà không đụng màu đặt chỗ |

Nền trang `#F8FAFC`, chữ `#0F172A`. Giá tiền dùng màu chữ `slate-900`, không dùng màu brand (brand chỉ nhấn hành động). Giữ màu theo nghĩa: emerald (thành công), amber (cảnh báo), rose/red (lỗi), cùng màu phân loại sản phẩm, hãng bay và ghim bản đồ. Ô tìm kiếm: nền trắng, viền `slate-200`, focus và nút Tìm màu `brand-600`.

---

## 7. Auth và phiên phía client

> Điều 1, 2 và 8 cũ (token trong `sessionStorage`, browser tự gửi `Authorization`, không refresh) **bị thay thế** bởi `docs/spec/hop-dong-tich-hop-auth.md` §4.2 và §6. Các điều còn lại giữ tinh thần, diễn đạt theo cơ chế phiên BFF.

1. Trình duyệt **không bao giờ** giữ token: không `sessionStorage`, không `localStorage`, không URL, không body. Phiên là cookie `vota_sid` (HttpOnly) do BFF phát; mọi `fetch` đi qua `services/http.ts` với `credentials: 'same-origin'`.
2. Method ghi gửi `X-CSRF-Token` đọc từ cookie `vota_csrf`. BFF gắn `Authorization: Bearer` khi proxy sang FastAPI; client không bao giờ tự đặt header này.
3. Tải lại trang → `GET /api/auth/session`. `state = anonymous` → chế độ khách, **không** mở modal.
4. Nhận `401 SESSION_EXPIRED` giữa phiên → mở modal "Phiên đăng nhập đã hết hạn" với email điền sẵn; sau khi đăng nhập lại, **gửi lại đúng request đã hỏng** một lần. Người dùng hủy → chế độ khách tại trang hiện tại.
5. Web **không** tự hạ về chế độ ẩn danh khi token hỏng; backend cũng không (`hop-dong-tich-hop-backend.md` §6.5).
6. Khách vãng lai bấm hành động ghi (thêm giỏ, checkout) → modal đăng nhập tại chỗ; thành công → tự thực hiện hành động đang chờ.
7. Đổi tài khoản (đăng nhập tài khoản khác hoặc đăng xuất) → xóa **mọi** cache phía client: query cache, `conversationId`, state kế hoạch, badge giỏ.
8. Web không biết hạn token: BFF tự refresh khi access token còn ≤ 60 giây (auth §3.4).

---

## 8. Xử lý lỗi

Mọi response không phải 2xx có envelope `ErrorResponse` (`hop-dong-tich-hop-backend.md` §8.1). Tầng `services` ném một lỗi có kiểu chứa `status`, `code`, `message`, `retryable`, `requestId`, `details`; component quyết định hiển thị theo bảng dưới.

| Mã lỗi | Nơi gặp | Web hiển thị |
|---|---|---|
| `VALIDATION_ERROR` | form bất kỳ | Gắn `details.fields[]` vào trường tương ứng; không có `fields` → `message` phía trên nút. Checkout: `field` bắt đầu bằng `travelers[`, `contact.` → về bước ①; `itemDetails[` (kèm `cartItemId`) → về bước ②; lỗi ở cả hai thì về bước ①, và hộp "Còn n thông tin cần sửa" chỉ liệt kê lỗi của bước đó. `reason = GUEST_COUNT_MISMATCH` → tải lại giỏ, tính lại phân bổ, về bước ② (spec `booking/checkout-nhieu-buoc-hanh-khach.md` §6.7, §10.4) |
| `CART_EMPTY` | Checkout | Chuyển `/cart` |
| `BOOKING_DRAFT_EXPIRED` | Trang thanh toán của đơn nháp (tải, sửa mục, bấm Thanh toán) | Màn hình "Phiên thanh toán đã hết hạn" (§4.5a) |
| `BOOKING_DRAFT_NOT_FOUND` | Trang thanh toán của đơn nháp | "Không tìm thấy phiên thanh toán này" + Về trang chủ |
| `DIRECT_BOOKING_ONLY` | Thêm giỏ | Toast "Khách sạn và vé máy bay được đặt trực tiếp"; không xảy ra trong luồng bình thường |
| `BOOKING_PENDING_PAYMENT` | Checkout | Hộp thoại "Bạn đang có một đơn chờ thanh toán" với `details.referenceCode`, `details.holdExpiresAt`: "Tiếp tục thanh toán đơn đó" (đọc lại đơn, mở `checkoutUrl`) hoặc "Huỷ đơn đó và đặt lại từ giỏ" (thanh toán đơn nháp: "Huỷ đơn đó và đặt lại") |
| `BOOKING_ALREADY_PAID` | Huỷ đơn | Tải lại đơn, báo "Đơn vừa được thanh toán" |
| `BOOKING_NOT_CANCELLABLE` | Huỷ đơn | `details.reason = TOO_LATE` → "Đã quá hạn huỷ trực tuyến (hạn: {cancellableUntil})"; `NOT_ACTIVE` → "Đơn này không còn hiệu lực" |
| `PAYMENT_PROVIDER_UNAVAILABLE` | Checkout; Huỷ đơn | "Cổng thanh toán tạm thời không phản hồi" + Thử lại (`retryable: true`); ở lại trang, giỏ còn nguyên |
| `INVALID_CREDENTIALS` | Login | "Email hoặc mật khẩu không đúng" phía trên nút |
| `INVALID_TOKEN`, `TOKEN_EXPIRED` | mọi nơi có JWT | §7 mục 3–4 |
| `PRODUCT_NOT_FOUND` | Detail; thêm giỏ | Detail → trang 404 sản phẩm. Thêm giỏ → toast `message` |
| `CART_ITEM_NOT_FOUND` | Cart | Tải lại `GET /cart`, không báo lỗi |
| `BOOKING_NOT_FOUND` | Confirmation | "Không tìm thấy đơn đặt chỗ này" + Về trang chủ |
| `EMAIL_ALREADY_EXISTS` | Register | Dưới trường email + link Đăng nhập |
| `PRODUCT_UNAVAILABLE` | Thêm giỏ; Checkout | Banner "{tên} vừa hết chỗ" dùng `details.productId` để tìm tên trong giỏ; giữ form; link Quay lại giỏ |
| `PRICE_CHANGED` | Checkout | Banner "Giá {tên} đã đổi từ {oldPrice} thành {newPrice}" (có `details.fareType = CHILD` thì "Giá vé trẻ em của {tên} …") + nút "Cập nhật và tiếp tục": gọi `PATCH /cart/items/{cartItemId}` với `quantity` hiện tại để Backend ghi lại giá snapshot (khách đã thấy giá mới), rồi người dùng bấm Thanh toán lần nữa. Chỉ `GET /cart` thì lần bấm sau vẫn nhận `PRICE_CHANGED` |
| `DATE_OUT_OF_RANGE` | Thêm giỏ; Checkout | Lỗi dưới ô ngày, dùng `details.availableFrom/To` để giới hạn lịch (khách sạn: hai mốc này là hôm nay và hôm nay + 3 tháng) |
| `SEARCH_UNAVAILABLE` | Search; Assistant | `ErrorState` + Thử lại |
| `CONVERSATION_NOT_FOUND` | Assistant | Xóa `conversationId`, gửi lại tin nhắn như cuộc hội thoại mới, thêm dòng hệ thống "Đã bắt đầu cuộc trò chuyện mới" |
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
| `COMPLETED` | Có kế hoạch | Panel kế hoạch + lời diễn giải `message` trong chat: dòng đầu `**Tiêu đề**` và các mục in đậm; link `[Tên](product:<productId>)` hiện thành nút, bấm thì mở rộng widget, chọn tab ngày chứa sản phẩm, cuộn và tô viền thẻ đó ở panel và focus điểm trên bản đồ (`WidgetChat.tsx`, `useFloatingWidget.focusProduct`, `widgetPlan.locateProduct`). Không có `message` thì hiện `itinerary.title`, rồi câu cố định. Chỉ `**đậm**` và link sản phẩm được render, mọi markdown/HTML khác hiện nguyên chữ (`inlineBold.parseAssistantText`) |
| `NEEDS_CLARIFICATION` | Thiếu `destination`, `days`, hoặc chưa hỏi `startDate`/`party`/`budget`; hoặc có giá trị không hợp lệ (ngày đã qua, điểm đến ngoài catalog, số ngày/số người/ngân sách ngoài giới hạn) | Thẻ hỏi lại có lựa chọn; có `clarificationForm` (từ lượt hỏi thứ hai) thì hiện form đã điền sẵn thay cho chip. Dòng đầu `question` dạng `**Tiêu đề**` hiển thị **chữ đậm** (bong bóng chat, widget nổi và thẻ hỏi lại tách tiêu đề khỏi phần thân). Cùng dạng cho `message` của `NO_RESULTS`/`FALLBACK` (thẻ kết quả tách tiêu đề thành tiêu đề thẻ) và `error.message` của lỗi `VALIDATION_ERROR` 400 (khung lỗi in đậm dòng đầu); tên khi chia sẻ/lưu lấy từ tiêu đề |
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
| `itinerary.stay` | Khối chỗ ở, **không lặp** trong `days`. `null` khi không có khách sạn phù hợp. Từ 1.19.0 luôn bằng `stays[0]` |
| `itinerary.stays` | Từ 1.19.0: 1–2 khách sạn theo đêm (đổi khách sạn giữa chuyến, AC-AGT-04). Web hiện mỗi khách sạn kèm "Đêm a–b", ngày d dùng khách sạn của đêm `min(d, max(1, days − 1))`; không có `stays` thì dùng `stay`. Cột lịch trình (`WidgetDays`) chỉ hiện thẻ khách sạn đầy đủ (ảnh, tag, ghi chú, nút đặt) ở ngày nhận phòng (`fromNight`, mặc định 1); các ngày khác là một dòng "Tiếp tục nghỉ tại <tên>" mở trang khách sạn (cập nhật 2026-10-12) |
| `stayOptions` | Từ 1.20.0 (AC-AGT-04, chốt 2026-10-08): hàng thẻ "Phương án khác" là nội dung mục "Nơi nghỉ" của câu trả lời (`WidgetStayOptions`, chốt bổ sung 2026-10-08 `update-archive/2026-10-08-hang-the-thay-khach-san-noi-nghi.md`): mục chứa dòng đầu tiên nhắc một khách sạn của hàng thẻ là mục "Nơi nghỉ"; mọi dòng nhắc các khách sạn đó trong mục này bị bỏ, hàng thẻ đứng ở chỗ dòng đầu; các mục ngày giữ chữ, tên khách sạn là link mở chi tiết; khách sạn của hàng thẻ không có thẻ gọn; lời diễn giải không nhắc khách sạn nào thì hàng thẻ nằm cuối. Thẻ đầu là lịch đang chọn (`distanceKm`), mỗi `options[i]` một thẻ: khách sạn từ `options[i].itinerary.stays`, chip `moneyDelta` (xanh khi âm), `kmDelta` (xanh khi âm), nhãn đỏ khi `overBudget` khác null. Chạm thân thẻ (chỉ ở câu trả lời mới nhất) là xem trước: thẻ nổi lên ("Đang xem trước"), cột phải, bản đồ và tổng tiền dùng `options[i].itinerary` nhưng chưa lưu; cột phải có dải "Đang xem trước … · chưa đổi" với nút "Quay lại" và "Đổi sang khách sạn này", nút "Thanh toán tất cả" tạm khoá (chốt bổ sung 2026-10-08 `update-archive/2026-10-08-bam-nut-moi-doi-khach-san.md`). Nút "Đổi sang khách sạn này" (trên thẻ hoặc trên dải) mới đổi: cột phải dùng lịch của phương án, đồng thời gửi ở nền `POST /assistant/itineraries` `{conversationId, selectStayOption: {index}}` (không qua stream, không thêm tin nhắn); server trả `COMPLETED` không có `message` thì thay `response` của câu trả lời gần nhất (chữ giữ nguyên, hàng thẻ cập nhật), lỗi thì quay về lịch cũ và báo toast. Thứ tự thẻ giữ như lần hiện đầu (khoá `stayCardKey` = khách sạn kèm đêm bắt đầu và số đêm, như backend phân biệt phương án; không theo `index` vì server đánh số lại); thẻ đổi khách sạn giữa chuyến ghi "Đêm x–y · Tên" cho từng khách sạn; thẻ vừa đổi thành "Đang chọn" ngay, hàng trượt tới thẻ đang xem trước/đang lưu, lịch ở cột phải trượt vào. Chat chỉ tự cuộn xuống khi có tin nhắn mới hoặc chữ tin cuối dài thêm; widget mở rộng vì chạm thẻ thì giữ hàng thẻ ở giữa khung chat (thu gọn và mở rộng là hai cây DOM khác nhau). Vắng mặt thì không có hàng thẻ |
| `stayOptions` — km và bản đồ (chốt 2026-10-09, `update-archive/2026-10-09-loc-trung-giu-ve-km-san-bay-ban-do.md`) | `distanceKm`/`kmDelta` gồm chặng sân bay khi lịch có vé có toạ độ. Thẻ ghi "≈x km cả chuyến" một lần dưới số "Tổng chuyến"; thẻ phương án có dòng "So với lựa chọn hiện tại" và chip "Gần hơn ≈x km"/"Xa hơn ≈x km", "Rẻ hơn x"/"Đắt hơn x" (tiền làm tròn: "3,98 triệu", dưới 1 triệu "850 nghìn"; số đầy đủ ở bảng chi phí); điểm khách chấm ("★ 4,3/5 (410 đánh giá)") tách khỏi hạng sao ("Khách sạn 5 sao"); chỉ thẻ đang chọn có viền xanh đậm và nhãn "✓ Đang chọn", thẻ đang xem trước chỉ nổi lên với nhãn trắng (cập nhật 2026-10-12); dưới hàng thẻ có dòng "Số km là ước tính quãng đường di chuyển cả hành trình, gồm cả đường sân bay." (lịch không có sân bay thì bỏ vế sau; `routeGeometry.getAirportPoints`). Đang xem trước một thẻ thì `ItineraryMap` nhận `overview` và chuyển sang "Tất cả": vẽ đường mọi ngày, ngày đầu sân bay → khách sạn → các điểm → khách sạn, ngày cuối khách sạn → các điểm → sân bay (ghim "Sân bay"), chỉ có khách sạn của phương án đó; các đoạn vẽ dần theo thứ tự đi (`SEGMENT_DRAW_MS`), `prefers-reduced-motion` thì vẽ ngay. Vẫn không vẽ đường thẳng khi OSRM không trả tuyến |
| `itinerary.costBreakdown` | Từ 1.21.0 (user-flow §4.2 "Ngân sách dự tính", chốt 2026-10-09, `update-archive/2026-10-09-ngan-sach-du-tinh.md`): `{flights, stays, activities}` cộng bằng `estimatedTotal`, vắng khi tổng chưa biết. Web (`WidgetBudget`, cuối bong bóng câu trả lời) hiện tổng, "3N2Đ", thanh màu ba đoạn (nhóm 0 đ không có đoạn) và ba dòng Vé máy bay · Lưu trú · Vui chơi; có `intent.budget` thì thêm ngân sách và nhãn theo `budgetStatus`. Không tính lại số nào ở client, không có khoản ăn uống |
| `itinerary.flights` trong khung chat | Thẻ vé (`WidgetFlightCard`, AC-AGT-02, user-flow §4.2) thay thẻ gọn: nhãn "Đã chọn cho lịch", mỗi chặng (vé khứ hồi có thêm "Chiều về" từ `returnFlight`) ghi ngày, giờ và thành phố đi/đến, hãng, thời gian bay (từ `departureAt`/`arrivalAt`), "Bay thẳng" khi `nonstop=true`, số hiệu (dòng nhãn chiều chỉ ghi số hiệu, không lặp giờ); giá "`unitPrice` ₫/khách × `passengers` khách". Dòng "• Chặng đi — tên chuyến" của mục "Vé máy bay" trong lời diễn giải không nhắc lại ngày, giờ, bay thẳng (cập nhật 2026-10-12) và nút "Đặt ngay" (vé có trong `cartItems`). Catalog không có hạng vé, hành lý, logo hãng nên thẻ không hiện các mục này |
| `stay.nights`, `stay.fromNight` | Số đêm và đêm đầu tiên ở khách sạn đó (vắng `fromNight` coi là 1). Check-in = `days[0].date` + `fromNight − 1`, check-out = check-in + `nights` |
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
| `estimatedTotal` | Integer VND do backend tính (không phải LLM), theo `intent.party` và công thức §2.6 hợp đồng Backend. Chỉ gồm chi phí các sản phẩm trong lịch trình. `null` khi có mục thiếu giá hoặc thiếu `priceUnit` — nghĩa là **chưa tính được**, Web không được hiển thị thành `0`. Ngoại lệ: điểm tham quan/golf không có giá hoặc `ticketed=false` là "tham quan tự do", backend tính 0 đ vào tổng và Web ghi "Tham quan tự do" ở mục đó, không ghi 0 ₫. Người dùng có nêu `budget` không làm trường này thành `null` |
| `budgetStatus` | `WITHIN_BUDGET` \| `OVER_BUDGET` \| `NO_BUDGET` \| `UNKNOWN`. `NO_BUDGET` khi `intent.budget = null`; `UNKNOWN` chỉ khi `estimatedTotal = null`. So sánh đặt trên chi phí sản phẩm, không phải chi phí cả chuyến |
| `priceAsOf` | Thời điểm lấy giá; Web ghi "giá tại thời điểm tạo kế hoạch" |
| `searchResults` | Object key `taxonomy` → `ProductSummary[]`, tối đa 6 mỗi nhóm. Có mặt kể cả khi `COMPLETED`, phục vụ "Tìm lựa chọn khác" |
| `warnings[]` | `{ code, message, productId }` — ví dụ `PRODUCT_DROPPED_UNAVAILABLE`, `DAY_WITHOUT_PRODUCTS`. Về tiền: `PRODUCT_COST_ONLY` (tổng chỉ gồm sản phẩm) luôn đi kèm `estimatedTotal` khác `null`; `BUDGET_ON_PRODUCT_COST` thêm vào khi người dùng có nêu ngân sách; `FREE_ENTRY_ASSUMED` thêm vào khi tổng có điểm tham quan tự do (tính 0 đ); `UNKNOWN_TOTAL` thay cho cả ba khi `estimatedTotal = null`. `NO_STAY_AVAILABLE`: lịch không có chỗ ở, `message` nêu lý do (lời diễn giải đã có mục "Chưa có khách sạn") |

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

**Field tuỳ chọn `suggestions`** (OpenAPI 1.13.0): khi điều kiện bắt buộc (khách sạn, khách sạn/hoạt động cụ thể) không có sản phẩm nào, `question` nêu lý do thật và `suggestions` là câu gửi được nguyên văn (ví dụ `Đổi ngày khởi hành sang 15/10/2026`, `Đi Hà Nội 3 ngày, không cần khách sạn`). Widget hiện thành chip như `NO_RESULTS` (`useFloatingWidget.ts`, `SuggestionChips.tsx`).

`missingFields` chỉ nhận `destination` \| `days` \| `startDate` \| `party` \| `budget`. Ba giá trị sau đi cùng nhau trong một câu hỏi gộp và không có chip gợi ý: câu hỏi hiện như tin nhắn của trợ lý và người dùng trả lời bằng cách gõ.

**Field tuỳ chọn `clarificationForm`** (đề xuất `docs/prd/update-archive/2026-09-29-form-goi-y-thong-tin-chuyen-di.md`, đã áp dụng):
xuất hiện từ lượt hỏi thứ hai trở đi khi vẫn còn thiếu `destination`/`days`. Web hiển thị một form đã điền sẵn giá trị gợi ý
(`clarificationForm.defaults`) ngay dưới câu trả lời của trợ lý, cho từng `clarificationForm.fields`. Ô điểm đến chỉ liệt kê vài
lựa chọn tiêu biểu (gọi `GET /destinations`, sắp theo `productCount`, lấy top 8 — không đổ hết catalog). Form chặn tại chỗ: số
ngày trong khoảng 1–7 (`TripIntent.days`), `startDate` không sớm hơn `clarificationForm.startDateMin`. Bấm **Xác nhận** dựng một
câu yêu cầu hoàn chỉnh từ giá trị trên form và **gửi ngay** như một lượt chat bình thường; không dùng `intentOverride`. Component: `src/frontend/src/components/assistant/TripDetailsForm.tsx`.

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

`suggestions` là câu gửi được nguyên văn khi người dùng bấm chip. Chip hiện ngay dưới bong bóng trả lời của trợ lý, chỉ ở tin nhắn mới nhất (widget nổi: `WidgetChat.tsx`; trang `/assistant`: `AssistantConversation.tsx`; cùng dùng `SuggestionChips.tsx`); không dựng thêm card kết quả riêng cho `NO_RESULTS`.

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

HTTP status và `ErrorResponse` như §8. Mã riêng của trợ lý: `CONVERSATION_NOT_FOUND` (404), `LLM_UNAVAILABLE` (503, chỉ khi Search cũng không dùng được), `ITINERARY_VALIDATION_FAILED` (500). Request sai định dạng dùng `VALIDATION_ERROR`; Search lỗi dùng `SEARCH_UNAVAILABLE`. Điểm đến ngoài catalog và số ngày ngoài 1–7 **không còn là lỗi**: là `NEEDS_CLARIFICATION` (200) kèm `suggestedValues` (Web dùng chip điểm đến/số ngày như mọi lần hỏi lại; `conversationId` lấy từ response) — `UNSUPPORTED_DESTINATION`/`INVALID_TRIP_DURATION` vẫn ở enum nhưng trợ lý không trả nữa.

### 9.5. Quy tắc render grounding Web cam kết

Áp dụng `docs/product.md` §6.4 mục 1–7 làm hợp đồng render. Tóm tắt kiểm tra phía Web trước khi render mỗi slot có `product`:

1. `product.productId` khác rỗng.
2. `product.available = true`.
3. `product.destination = intent.destination`.

Không đạt → không render thẻ; hiển thị dòng mờ "Mục này hiện không còn chỗ · Tìm lựa chọn khác" (→ `/search?q={destination} {nhãn taxonomy}`), và ở chế độ debug ghi lý do loại. Tên, ảnh, giá luôn lấy từ `product`, **không bao giờ** từ `note` hay `title`. Không tự link hóa tên riêng trong văn bản LLM.

### 9.6. Hội thoại

- Web giữ `conversationId` trong state của route `/assistant` và `sessionStorage` (khóa `vota.assistant.conversationId`), xóa khi đổi tài khoản.
- Khi tải lại trang, Web chờ phiên đăng nhập được khôi phục rồi nạp transcript và response gần nhất qua `GET /assistant/conversations/{conversationId}` cho người dùng đã đăng nhập. Chỉ ID được giữ trong browser storage; khách không nạp archive lâu dài. Response lịch sử đến muộn sau khi tạo cuộc mới, gửi tin, đổi tài khoản hoặc rời trang bị bỏ qua. Lỗi tạm thời giữ ID và cho thử tải lại; hội thoại không còn tồn tại thì xóa ID.
- Khi đã đăng nhập, Web hiển thị nút **Lịch sử**, tải danh sách từ backend và cho chọn một hội thoại để nạp transcript. Khách không thấy lịch sử lâu dài.
- Kế hoạch không tự cập nhật giá. Giỏ và Checkout luôn dùng giá mới nhất.
- Tiến độ (AC-AGT-09, contract 1.27.0): theo loại lượt do server gửi — lập lịch 4 bước, khám phá 3, vé 2, trò chuyện/hỏi lại 1, bị chặn không ✓. `node.activity` hiện việc đang làm; `node.completed.progress` có dữ kiện và số đếm thật. Nhóm thay theo `groupId`, thông báo thay theo `(code, groupId, date)`, không cộng số; ẩn nhóm `superseded`. Không hiện `message`, tên node/tool hay tổng nguồn. Khi xong thu gọn ở đầu lời đáp, mở lại xem bằng nút có `aria-expanded`. Preview sau compose tối đa 6 thẻ, chỉ xem, hiện từ giây 5 nếu lượt chưa kết thúc; bấm mở panel chi tiết. Tiến trình không lưu ở server nên lịch sử không có tóm tắt. Nút gửi đổi thành Dừng, dừng thì có Gửi lại. Shift+D có thông tin request, node, activity, số đếm và mốc preview/kết quả.

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
| Kệ Phổ biến tab Tất cả trộn đủ 5 loại (`diversify=taxonomy`), có combo tên mở đầu "Vé máy bay khứ hồi" | `catalog/listProducts.200-diversified` |
| Search rỗng, `topScore: null` | `search/searchProducts.200-empty` |
| Sản phẩm 404 | `catalog/getProduct.404-not-found` |
| Giỏ rỗng / có hai điểm đến | `booking/getCart.200-empty`, `booking/getCart.200-two-destinations` |
| Checkout `409 PRICE_CHANGED`, `409 PRODUCT_UNAVAILABLE` | `booking/createBooking.409-*` |
| Booking hai nhóm điểm đến | `booking/createBooking.201-two-groups` |
| Đơn theo 5 trạng thái: giữ chỗ, đã xác nhận, thanh toán thất bại, hết hạn, đã huỷ + hoàn tiền | `booking/createBooking.201-default` (`PENDING_PAYMENT`), `booking/getBooking.200-default` (`CONFIRMED`), `booking/getBooking.200-payment-failed`, `booking/getBooking.200-expired`, `booking/getBooking.200-cancelled-refunded` |
| Đang có đơn giữ chỗ, Stripe không phản hồi, huỷ quá hạn | `booking/createBooking.409-pending-payment`, `booking/createBooking.503-payment-unavailable`, `booking/cancelBooking.409-too-late` |
| Trợ lý: bốn `status` + điểm đến không hỗ trợ + hội thoại hết hạn | `assistant/createItinerary.*` |
| Lịch trình chứa slot hết chỗ và slot sai điểm đến (lưới an toàn §9.5) | `assistant/createItinerary.200-completed-invalid-slots` |
| Search kết quả yếu (`topScore < 0.35`), Search `503` | `search/searchProducts.200-weak`, `search/searchProducts.503-unavailable` |
| Giỏ có mục hết chỗ | `booking/getCart.200-item-unavailable` |
| Giỏ gia đình 2 người lớn + 1 trẻ em (hạng phòng, vé có giá trẻ em, chuyến bay); đơn tương ứng | `booking/getCart.200-family`, `booking/createBooking.201-family` |
| Checkout `400 VALIDATION_ERROR` nhiều vi phạm ở cả bước ① và ② | `booking/createBooking.400-party-invalid` |
| Checkout `409 PRICE_CHANGED` của giá vé trẻ em (`details.fareType = CHILD`) | `booking/createBooking.409-price-changed-child` |
| Sửa số khách của mục giỏ: thành công / bị từ chối | `booking/updateCartItem.200-guests`, `booking/updateCartItem.400-guests-invalid` |
| Bộ ca kiểm thử luật đoàn khách dùng chung với Backend | `src/shared/contracts/tests/booking-rules-cases.json` |
| Đăng nhập sai | `auth/login.401-invalid-credentials` |

---

## 12. Phụ thuộc còn mở

| # | Nội dung | Mặc định Web trong lúc chờ |
|---|---|---|
| D3 | Endpoint ghi `product_view` | **Đã chốt** — `POST /api/v1/events`, xem §4.3 |
| D9 | SSE cho trợ lý | Đã có contract 1.27.0: node.activity, node.completed.progress, run.preview; ✓ chỉ từ bước đã hoàn thành |
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
10. Đăng xuất rồi đăng nhập tài khoản khác xóa sạch giỏ, gợi ý và hội thoại của người trước.
11. Với fixture `createItinerary.200-completed-invalid-slots`, slot `nt-a-02` (`available: false`) và slot `dn-a-01` (sai điểm đến) không render thành thẻ.

## 14. Definition of Done

> Team Web dựng cả tám màn hình và mọi ca biên chỉ bằng type sinh từ `openapi.yaml` và fixture trong `src/shared/mocks/`, rồi đổi sang backend thật mà không sửa tầng `services`; Team Backend và Team Agent chạy contract test trên cùng file OpenAPI và cùng bộ fixture.
