# Hợp đồng tích hợp Search & Recommendation

**Phiên bản:** 1.0
**Bên cung cấp:** Team Recommendation/Search
**Bên sử dụng:** Team Backend, Team Agent, Team Web
**Bên phụ thuộc:** Team Data (catalog, seed events), CDP clone
**Giao thức:** REST/JSON qua HTTP
**Xác thực:** JWT Bearer, **không bắt buộc** — không có JWT thì trả kết quả không cá nhân hóa
**Prefix:** `/api/v1`
**Múi giờ:** lưu và trả UTC
**Schema máy đọc được:** `src/shared/contracts/schemas/{common,catalog,search,recommendations}.yaml`

> Tài liệu này **lấp đúng khoảng trống** mà `hop-dong-tich-hop-backend.md` §1.3
> để ngỏ: *"Sinh embedding, quản lý vector index và thuật toán xếp hạng… Tài
> liệu này chỉ chốt hình dạng response, không chốt cách tính điểm."*
>
> Hình dạng response vẫn do hợp đồng backend sở hữu và **không được lặp lại ở
> đây**. Tài liệu này chốt **hành vi**: thứ tự xử lý, bất biến, ngưỡng, quy tắc
> chọn `strategy`, và những gì bên tiêu thụ **không được** suy ra.

---

## 1. Phạm vi trách nhiệm

### 1.1. Engine chịu trách nhiệm

- Dựng và duy trì `product_vectors` từ `products`, giữ đồng bộ khi catalog đổi.
- Trả kết quả `/search` và `/similar` theo thứ tự xử lý ở §2.2, với `total` và
  `facets` chính xác.
- Trả `/recommendations` cá nhân hóa kèm `because[]` có căn cứ, và đường lui
  `popular` khi không đủ dữ liệu hoặc khi CDP lỗi.
- Khai báo trung thực chế độ truy xuất trong `diagnostics` (§2.4).
- Giữ p95 trong ngân sách §7.1.
- Thông báo trước mọi thay đổi enum `strategy`, giá trị `cutoff`, hoặc
  `embedding_version`.

### 1.2. Bên tiêu thụ chịu trách nhiệm

**Team Backend**

- Gọi engine trong process, không để Web gọi trực tiếp tầng vector.
- Cung cấp `cdpUserId` từ JWT; **không tin** `userId` do client gửi.
- Vô hiệu hóa cache user vector **đồng bộ** khi ghi `purchase` (§5).

**Team Agent**

- Gọi `/search` **không kèm JWT**, để lượt tìm của Agent không bị ghi thành
  hành vi người dùng (`hop-dong-tich-hop-cdp.md` §1.4).
- Sao chép nguyên `productId`, `name`, `unitPrice` từ response. Không tự tạo sản phẩm.
- Kiểm tra ngày và số khách **sau** retrieval; không tuyên bố engine đã xác minh.
- Dùng `/similar?strategy=cross_taxonomy` cho cross-sell, không dùng
  `/recommendations` cho việc đó.

**Team Web**

- Sinh kiểu từ OpenAPI, không tự định nghĩa lại payload.
- Sở hữu ngưỡng hiển thị (§3.4) nhưng **đọc `cutoff` từ response**, không
  hard-code bản sao.
- Không dùng `score` làm phần trăm phù hợp.

### 1.3. Ngoài phạm vi

- Ghi event: thuộc Backend và `hop-dong-tich-hop-cdp.md`.
- Availability theo ngày: thuộc availability service.
- Booking, cart, auth: `hop-dong-tich-hop-backend.md`.
- Sinh lịch trình và grounding: `hop-dong-tich-hop-itinerary-assistant.md`.
- Insider clone và activation loop.

### 1.4. Quan hệ với hợp đồng khác

| Tài liệu | Quan hệ |
|---|---|
| `hop-dong-tich-hop-backend.md` §5, §6 | Sở hữu **hình dạng** request/response. Tài liệu này sở hữu **hành vi** |
| `hop-dong-tich-hop-cdp.md` §6 | Nguồn lịch sử cho `/recommendations`, kèm quy tắc đường lui |
| `schema-freeze-decisions.md` | Nguồn của mọi quyết định đánh dấu C*/U*/P* dưới đây |

Mâu thuẫn thì **OpenAPI thắng**, và tài liệu phải được sửa.

---

## 2. Nền tảng dùng chung cho cả ba endpoint

### 2.1. Hai tầng catalog · `[C5]`

Catalog có quan hệ cha–con qua `attributes.level` và `attributes.parentProductId`:

| Tầng | `level` | Số lượng | Có vector |
|---|---|---:|---|
| Cha | `property`, `route`, và taxonomy không phân tầng | 1.125 | ✅ |
| Con | `room`, `flight` | 1.091 | ❌ |

**Cam kết:**

1. `/search`, `/recommendations` mặc định **chỉ trả tầng cha**.
   `includeVariants: true` mới trả tầng con.
2. `/similar` nhận `productId` tầng con thì **resolve lên cha**, trả
   `resolvedFrom` là id gốc, và **loại cả cụm** khỏi kết quả.
3. `facets` đếm trên cùng tập với `results` — nếu không, bất biến §2.3 sai.

Lý do: 907 hạng phòng trỏ về 316 property, và mô tả của 771 hạng phòng là tự
sinh từ mô tả khách sạn cha. Embed cả hai tầng làm `/search` trả 5 hạng phòng
của cùng một resort.

### 2.2. Thứ tự xử lý bắt buộc · `[C4]`

```
FILTER → SCORE → CUTOFF → TOTAL/FACETS → SORT → PAGE

F       = tập sản phẩm sau structured filter
R       = { p ∈ F | score(p, query) >= cutoff }
total   = |R|
facets  = aggregation trên R
results = một trang của R
```

Áp cho cả ba endpoint. Với `/recommendations`, `query` được thay bằng user vector.

**Vì sao filter trước:** category exclusion của `/recommendations` loại khoảng
50% catalog. Chấm điểm trước rồi lọc sau (kiểu ANN top-K) có thể để lại dưới
`k` kết quả. Lọc trước còn ~300 ứng viên rồi chấm 300 cosine vừa đúng vừa nhanh hơn.

### 2.3. Bất biến

```
1. sum(facets.taxonomy) == total
2. total và facets KHÔNG đổi khi thay limit/offset
3. mọi results[].score >= cutoff
4. results, total, facets dùng CÙNG filter và CÙNG cutoff
5. sản phẩm thiếu destination → bucket "UNKNOWN", không biến mất
```

### 2.4. Chế độ truy xuất — khai báo, không đổi ngầm · `[C4]`

```yaml
search:           { mode: EXACT_FILTER_SCORE, cutoff: 0.62 }
similar:          { mode: EXACT_FILTER_SCORE, topK: 20 }
recommendations:  { mode: EXACT_FILTER_SCORE, candidateK: 200 }
```

> **Cần duyệt lại (22/09/2026) — xem rủi ro S8.** Đoạn dưới viết khi vector còn
> nằm trong Postgres/pgvector. Vector đã chuyển sang Weaviate (Cohere
> `embed-multilingual-v3.0`, 1024 chiều), nơi HNSW là mặc định, nên tiền đề
> "toàn bộ vector nằm trong `shared_buffers`" không còn đúng. Giữ nguyên chữ cũ
> để đối chiếu; chưa đổi cam kết `facets` trong contract khi chưa chốt.

Cả ba dùng exact scan. Ở 1.125 vector × 768 chiều = 3,4 MB, toàn bộ nằm trong
`shared_buffers`; exact scan mất 2–7 ms, HNSW ~1 ms nhưng là xấp xỉ và không
trả được tập đầy đủ để đếm `facets`.

**Ngưỡng lật sang ANN:**

```
Lật khi:  số vector > 50.000  HOẶC  p95 bước scan > 50 ms
Lật thì:  BẮT BUỘC searchMode = ANN_CANDIDATE_SCORE
                   approximate = true
                   totalExact = false
                   facetsExact = false
```

Chuyển sang approximate mà không đổi bốn trường này là **vi phạm hợp đồng** — nó
phá tiêu chí 8 của `hop-dong-tich-hop-backend.md` §12 một cách âm thầm.

### 2.5. Hard filter và soft filter · `[C6]`

| Loại | Trường | Độ phủ | Hành vi |
|---|---|---:|---|
| **Hard** | `taxonomy`, `destination`, `priceMin/Max`, `availableOnly` | ≥ 93% | Loại thẳng |
| **Soft** | `starRatingMin` | 51% | Thiếu dữ liệu **không bị loại**, chỉ xếp sau |

Response echo `appliedFilters.hard` và `.soft`. Agent **phải đọc** khối này: nếu
`starRatingMin` nằm trong `soft`, Agent không được nói với người dùng "khách sạn
này 4 sao" cho một kết quả không khai `starRating`.

### 2.6. Điểm số — và điều bên tiêu thụ không được suy ra

```
score = clamp(cosine(query_vector, product_vector), 0, 1)
```

Vector đã L2-normalize, nên cosine ≈ inner product.

**`score` KHÔNG phải phần trăm phù hợp.** Model họ e5 có dải cosine bị nén: cặp
*không liên quan* thường đã nằm ở `0.72–0.78`, cặp *liên quan tốt* ở `0.82–0.90`.
`0.81` không có nghĩa "81% phù hợp", và hiệu số `0.02` giữa hai kết quả có thể
là khác biệt lớn.

Chỉ hiển thị `score` cho khách ở chế độ debug.

### 2.7. Năm điều bên tiêu thụ **không được** suy ra

| Từ | Không được kết luận |
|---|---|
| `score: 0.81` | "81% phù hợp" |
| `available: true` | "còn phòng ngày 15/10" — đó là `bookable` |
| `because[]` | Bằng chứng nhân quả. Đó là đóng góp vào điểm số, không phải lý do khách mua |
| `total: 87` | Kích thước catalog. Đó là `|R|` sau filter và cutoff |
| Thuộc tính vắng mặt | `false`. Vắng mặt nghĩa là **không biết** — xem `[C2]` |

---

## 3. Search engine

### 3.1. Endpoint

```http
POST /api/v1/search
Authorization: Bearer <jwt>    # tùy chọn
```

`POST` vì truy vấn là câu tiếng Việt tự do kèm nhiều bộ lọc. Route frontend
`/search?q=…` là route trình duyệt, không phải endpoint API.

Hình dạng: `SearchRequest` / `SearchResponse` trong `search.yaml`.

### 3.2. Ghi hành vi

| Điều kiện | Hành vi |
|---|---|
| Có JWT **và** `offset = 0` **và** `query` không rỗng | Backend ghi event `search` sang CDP ở nền |
| Đổi trang, không JWT, hoặc Agent gọi | **Không** ghi event |
| CDP lỗi | Response search không đổi |

Agent gọi không kèm JWT là **quy tắc**, không phải khuyến nghị: lượt tìm của
Agent lọt vào lịch sử sẽ làm lệch user vector của chính người dùng đó.

### 3.3. Cutoff · `[C3]`

Mọi sản phẩm đều có cosine với mọi truy vấn. Không có cutoff thì `results: []`
**không bao giờ xảy ra**, trong khi `hop-dong-tich-hop-backend.md` §5.3 mục 6
yêu cầu điều đó.

```yaml
search.cutoff: 0.62     # PROVISIONAL — benchmark Ngày 3
```

Nguồn sự thật duy nhất là `application.yml`. Response trả lại giá trị đã áp
trong trường `cutoff`; frontend đọc từ đó, không giữ bản sao.

### 3.4. Ngưỡng "kết quả yếu" — hai quy tắc, client sở hữu · `[C3]`

Engine **trả số, không trả nhãn**. Client quyết định hiển thị.

```
backgroundScore = trung vị cosine của TOÀN BỘ tập F
margin          = topScore − backgroundScore

weak khi:  topScore < WEAK_RESULT_TOP_SCORE   HOẶC   margin < WEAK_RESULT_MARGIN
```

| Hằng số | Giá trị tạm | Chủ sở hữu |
|---|---|---|
| `WEAK_RESULT_TOP_SCORE` | `0.70` PROVISIONAL | Frontend |
| `WEAK_RESULT_MARGIN` | `0.06` PROVISIONAL | Frontend |

Quy tắc margin tồn tại vì ngưỡng tuyệt đối mong manh với model dải nén:

```
"nghỉ dưỡng biển cho gia đình"   top 0.86 · nền 0.76 · margin 0.10  → tốt
"khách sạn con nhộng ở Sa Pa"    top 0.74 · nền 0.71 · margin 0.03  → YẾU
```

Truy vấn thứ hai bị bắt đúng dù `0.74` vượt mọi ngưỡng tuyệt đối đang đặt.

`backgroundScore` lấy **miễn phí** trong cùng lượt quét exact của §2.2.

### 3.5. Cam kết dữ liệu

1. `productId` duy nhất và ổn định.
2. `name`, `unitPrice`, `available`, `attributes` lấy **nguyên** từ catalog —
   tầng search không sửa.
3. `destination` chuẩn hóa theo `GET /destinations`.
4. `taxonomy` chỉ dùng enum trong `common.yaml`.
5. `availableOnly: true` thì không trả sản phẩm `available: false`.
6. Không khớp thì `results: []`, `topScore: null`, `backgroundScore: null` —
   **không lấp bằng sản phẩm ngẫu nhiên**.
7. `facets` luôn có mặt, kể cả khi `results` rỗng — khi đó mọi giá trị bằng 0.
8. `filteredCount` và `relevantCount` luôn có trong `diagnostics`.

### 3.6. `/similar` — cùng tầng retrieval

```http
GET /api/v1/products/{productId}/similar?limit=8&strategy=same_taxonomy
```

Ba ràng buộc bắt buộc:

```
1. Loại chính nó VÀ mọi variant cùng parentProductId
2. strategy=same_taxonomy (mặc định): chỉ trả cùng taxonomy
   — xem khách sạn thì gợi ý khách sạn, không gợi ý vé máy bay
3. Tối đa 2 kết quả mỗi parentProductId
   — nếu không sẽ trả 10 hạng phòng của cùng một resort
```

`strategy=cross_taxonomy` là biến thể cross-sell dành cho Agent.

**Không embed lại.** Lấy thẳng vector đã lưu của anchor. Embed lại vừa tốn ~60 ms
vừa có nguy cơ so hai vector thuộc hai `embedding_version` khác nhau — kết quả
vẫn trả về, chỉ là vô nghĩa.

| Lỗi | HTTP |
|---|---|
| `productId` không tồn tại | `404 PRODUCT_NOT_FOUND` |
| Có trong catalog nhưng chưa có vector | `409 PRODUCT_NOT_INDEXED` |

Hai mã khác nhau vì cách xử lý khác nhau: cái đầu là sai id, cái sau là cần reindex.

---

## 4. Recommendation engine

### 4.1. Endpoint

```http
GET /api/v1/recommendations?k=5&destination=Nha%20Trang
Authorization: Bearer <jwt>    # tùy chọn
```

**`strategy` KHÔNG phải tham số request.** Nó là kết luận của engine sau khi đọc
lịch sử. Client gửi `strategy=cross_vertical` cho khách 0 event thì engine phải
làm gì — trả rỗng hay lờ đi? Cả hai đều là contract xấu.

### 4.2. Nguồn dữ liệu và đường lui

```
Backend ──HTTP──> CDP clone: tối đa 500 event mới nhất, bỏ event đã huỷ
```

| Tình huống | Hành vi |
|---|---|
| CDP lỗi hoặc timeout | `200` · `strategy: "popular"` · `because: []` · `coldStart: true` · `eventsUsed: 0` |
| JWT sai hoặc hết hạn | `401 INVALID_TOKEN` — **không** âm thầm hạ xuống chế độ ẩn danh |
| Không có JWT | `200` · `cdpUserId: null` · `strategy: "popular"` |

Phân biệt "CDP lỗi" với "chưa có lịch sử": cả hai cho `popular`, nhưng chỉ lỗi
CDP mới ghi log `WARNING`.

### 4.3. User vector — công thức

```
u_raw = Σ_j  w(event_j) · decay(Δt_j) · tripFactor(j) · v_j
u     = u_raw / ‖u_raw‖₂

decay(Δt) = exp( −ln(2) · Δt / halfLifeDays )
```

| Tham số | Giá trị | Ở đâu |
|---|---|---|
| `w(purchase)` | 5.0 | `application.yml` |
| `w(add_to_cart)` | 3.0 | |
| `w(product_view)` | 1.0 | |
| `halfLifeDays` | 30 | |
| `finishedTripFactor` | 0.2 | |
| `dormantDays` | 90 | Khớp `hop-dong-tich-hop-backend.md` §6.2 |

**`Δt` tính bằng NGÀY, kiểu số thực.** Đây là lỗi âm thầm nguy hiểm nhất của cả
engine: tính bằng giây thì `decay ≈ 0` cho mọi event, `u_raw` gần vector 0, sau
normalize thành hướng ngẫu nhiên — và `/recommendations` vẫn trả về 5 sản phẩm
trông hoàn toàn hợp lý. Không exception, không log.

`diagnostics.userVectorNorm` tồn tại để bắt đúng lỗi này: phải ≈ 1.0.

**`tripFactor`** — hứng thú với một chuyến hết hạn khi chuyến kết thúc:

```
tripFactor = 1.0  nếu trip chưa kết thúc (max(usingDate) >= hôm nay)
           = 0.2  nếu trip đã kết thúc
           = 1.0  nếu event không thuộc trip nào
```

Không có nó thì hệ thống gợi ý Nha Trang mãi cho người đã đi xong từ tháng trước.

### 4.4. Quy tắc chọn `strategy`

```
có trip đang mở + đã purchase ít nhất 1 taxonomy  → cross_vertical
>= 3 event dùng được, không có trip đang mở       → recent_activity
event gần nhất > 90 ngày                          → dormant
< 3 event, không JWT, hoặc CDP lỗi                → popular
```

**Ràng buộc bắt buộc:**

1. `cross_vertical` ⟹ `nextVertical` **và** `destination` khác `null`
2. `dormant` ⟹ ít nhất một `because` có `daysAgo > 90`
3. `popular` ⟹ `because` của **mọi** gợi ý là mảng rỗng
4. `coldStart: true` ⟹ `because` rỗng

Thêm giá trị `strategy` mới là thay đổi tương thích ngược nhưng **phải thông báo
trước** — client map từng giá trị sang một tiêu đề section riêng.

### 4.5. Category exclusion

```
bookedThisTrip = { taxonomy của mọi purchase trong eventGroupId đang mở }
excluded       = bookedThisTrip, mở rộng: combo kéo theo hotel
```

Áp làm **hard filter trong câu truy vấn**, không phải phép trừ vector. Ngoài ra
loại mọi `productId` khách đã từng mua.

**Nếu loại hết mọi taxonomy** (khách đã đặt đủ 5 nhóm trong một chuyến): bỏ
exclusion, trả theo similarity thuần, đặt `diagnostics.exclusionRelaxed: true`.
Hiếm, nhưng không được trả danh sách rỗng.

`diagnostics.excludedVerticals` là dữ liệu client dùng vẽ checklist
*"✓ Khách sạn / ○ Vé máy bay"* — hiển thị ở giao diện thường, không riêng debug.

### 4.6. `because[]` — công thức và cam kết

```
raw_j          = w_j · decay_j · tripFactor_j · cos(v_j, v_candidate)
contribution_j = raw_j / Σ_k raw_k        (chỉ tính raw_k > 0)
```

Lấy 1–2 nguồn cao nhất, ngưỡng tối thiểu `0.15`.

**Cam kết:**

1. Mảng sắp giảm dần theo `contribution`; `because[0]` là thứ client hiển thị trên thẻ.
2. `productId` khác `null` ⟹ sản phẩm mở được `GET /products/{id}` và trả `200`.
3. Sản phẩm nguồn `INACTIVE` ⟹ `productId: null`, `imageUrl: null`, **vẫn giữ
   `productName`** · `[U1]`
4. `event: "search"` ⟹ `productId: null`, `productName` là truy vấn đã gõ.
5. Không nguồn nào vượt `0.15` ⟹ mảng rỗng. **Không bịa lý do.**

> `[U1]` Cam kết 3 là lý do `products` phải **soft delete**. `UserEvent` trong
> CDP không lưu tên sản phẩm, nên `DELETE` hàng khỏi `products` làm mất tên vĩnh
> viễn và biến cam kết này thành không thực hiện được.

### 4.7. Điểm cuối và đa dạng

```
final = cos(u, v_c) + γ · log(1 + review_count)      γ = 0.05
```

Sau đó MMR re-rank với `λ = 0.7`, cộng giới hạn cứng tối đa 2 kết quả mỗi
`parentProductId`.

Lấy trung bình vector kéo kết quả về cùng một cụm; không có bước này thì top-5
hay là 5 biến thể của một resort.

### 4.8. Cold start, dormant, ẩn danh

**Cold start** (dưới 3 event) — fallback theo thứ tự:

```
1. Có destination trong request → phổ biến nhất trong điểm đến đó
2. Có profile.homeCity          → điểm đến phổ biến từ thành phố đó
3. Còn lại                      → most-popular toàn hệ thống, tối đa 2 mỗi taxonomy
```

**Dormant** (event gần nhất > 90 ngày): vẫn dựng user vector nhưng
`halfLifeDays × 3`, ưu tiên `lastDestination`.

**Ẩn danh**: `strategy: "popular"`, `cdpUserId: null`, `200` — không `401`.

Không có endpoint `/recommendations/popular` riêng. Cùng một endpoint phục vụ
hai chế độ, vì Home của khách vãng lai và Home của P4 render cùng một component,
chỉ khác chữ.

---

## 5. Vòng lặp phản hồi K1

Đây là khoảnh khắc demo quan trọng nhất: đặt phòng xong, quay lại Home, gợi ý
đã chuyển sang danh mục còn thiếu.

```
checkout thành công
  → Backend ghi purchase sang CDP (đồng bộ, trước commit)
  → Backend vô hiệu hóa cache user vector (ĐỒNG BỘ, cùng transaction)   [P3]
  → lần gọi /recommendations kế tiếp dựng lại vector
  → strategy chuyển sang cross_vertical, nextVertical khác null
```

**Vô hiệu hóa cache phải đồng bộ.** Để chạy nền là hỏng K1 — người demo bấm
"Về trang chủ" trong vòng một giây sau khi đặt, và gợi ý vẫn là cái cũ.

`diagnostics.userVectorCacheHit: false` ở lần gọi ngay sau checkout là **hành vi
đúng**, không phải lỗi hiệu năng.

---

## 6. Lỗi

| HTTP | Mã | Khi nào | `retryable` |
|---:|---|---|---|
| 400 | `VALIDATION_ERROR` | `priceMin > priceMax`, `limit` ngoài 1–50, `query` > 500 ký tự | false |
| 401 | `INVALID_TOKEN` | JWT sai hoặc hết hạn | false |
| 404 | `PRODUCT_NOT_FOUND` | `/similar` với id không tồn tại | false |
| 409 | `PRODUCT_NOT_INDEXED` | Có trong catalog, chưa có vector | false |
| 503 | `SEARCH_UNAVAILABLE` | `product_vectors` rỗng hoặc model chưa nạp | **true** |
| 500 | `INTERNAL_ERROR` | Không lường trước | **true** |

**Không tìm thấy kết quả là `200` với `results: []`, không phải `404`.** Agent
phân biệt "không có" với "engine hỏng" bằng status code, và hai trường hợp xử lý
khác hẳn nhau.

---

## 7. Yêu cầu phi chức năng

### 7.1. Ngân sách thời gian

| Hoạt động | p95 |
|---|---:|
| `POST /search` (exact) | 300 ms |
| `GET /products/{id}/similar` | 300 ms |
| `GET /recommendations`, cache hit | 300 ms |
| `GET /recommendations`, cache miss (đọc 500 event từ CDP) | 800 ms |
| Embed một truy vấn | 60 ms |

Dòng "cache miss" là thừa nhận thẳng: đường đó phải gọi HTTP sang CDP clone rồi
tra tối đa 500 vector. Nó chỉ xảy ra sau `purchase` hoặc khi cache trống.
Tỉ lệ cache miss cao là dấu hiệu quy tắc vô hiệu hóa đang sai, không phải engine chậm.

### 7.2. Tracing

`X-Request-ID` truyền tiếp qua mọi lời gọi, kể cả Backend → CDP ở nền. Lặp lại
trong `requestId` của response và trong mọi dòng log liên quan.

### 7.3. Logging

**Được phép:** `requestId`, `cdpUserId` đã pseudonymize, truy vấn tìm kiếm, bộ
lọc, danh sách `productId` trả về, `strategy`, `cutoff`, `topScore`,
`filteredCount`, `relevantCount`, độ trễ, mã lỗi.

**Không được:** JWT, `X-Service-Token`, email hoặc số điện thoại đầy đủ.

### 7.4. Versioning

- Thêm field hoặc thêm giá trị enum là tương thích ngược, được phép trong `v1`.
- **Phải thông báo trước:** enum `strategy`, enum `taxonomy`, giá trị `cutoff`,
  `embedding_version`, và mọi thay đổi `searchMode`.
- Đổi `embedding_version` yêu cầu reindex toàn bộ và phải chạy lại bộ 80 cặp gán nhãn.
- Không xóa hoặc đổi tên field trong `v1`.
- Một thay đổi contract cần reviewer của cả Web và Backend.

---

## 8. Dữ liệu cần có trước khi tích hợp

Team Data cung cấp:

- ≥ 2.000 sản phẩm, ≥ 10 điểm đến, đủ 5 taxonomy.
- **Ma trận điểm đến × taxonomy**: ít nhất một điểm đến có đủ `hotel` +
  `flight`/`attraction` — nếu không, K1 không demo được.
- 4 tài khoản demo theo persona P1–P4, event seed gom theo `eventGroupId`.
- ≥ 25% khách có dưới 3 event, để nhánh cold start thực sự chạy.
- Ít nhất một event trỏ tới `productId` đã `INACTIVE`.
- Ít nhất một truy vấn cho `results: []`.

Team Search cung cấp:

- **80 cặp** `query → productId` gán nhãn tiếng Việt, để hiệu chỉnh `cutoff` và
  so sánh embedding model.
- **10 truy vấn âm** — câu mà catalog chắc chắn không có đáp án. Đây là thứ duy
  nhất cho phép hiệu chỉnh `WEAK_RESULT_MARGIN`; không có chúng thì chỉ hiệu
  chỉnh được hai ngưỡng tuyệt đối, tức là phần mong manh.

---

## 9. Tiêu chí nghiệm thu

### Search

1. `search("nghỉ dưỡng biển cho gia đình")` → top-5 toàn resort/hotel biển hoặc
   `familyFriendly`.
2. Đổi `limit`/`offset`, giữ nguyên filter → `total` và `facets` **không đổi**.
3. `sum(facets.taxonomy) == total` trên mọi truy vấn.
4. Mọi `results[].score >= cutoff`.
5. Truy vấn vô nghĩa → `results: []`, `topScore: null`, `backgroundScore: null`.
6. ≥ 95% cặp đúng trong bộ 80 cặp có `score >= cutoff`.
7. Cả 10 truy vấn âm rơi vào nhánh weak (theo abs hoặc theo margin).
8. `availableOnly: true` không trả sản phẩm `available: false`.
9. Mặc định không có sản phẩm `level: room` trong `results`.
10. `diagnostics.approximate: false` và `totalExact: true` ở chế độ exact.
11. p95 dưới 300 ms trên catalog đầy đủ.

### Similar

12. `/similar` với id một hạng phòng → `productId` trả về là property cha,
    `resolvedFrom` là id đã gửi.
13. Kết quả **không chứa** hạng phòng anh em cùng `parentProductId`.
14. `strategy=same_taxonomy` không trả taxonomy khác.
15. Mock `embedQuery` ném exception mà `/similar` vẫn chạy — chứng minh không embed lại.

### Recommendation

16. Đăng nhập lần lượt 4 tài khoản demo → 4 `strategy` khác nhau.
17. P1 vừa đặt hotel Nha Trang → `strategy: cross_vertical`, không có item
    `taxonomy: hotel`, `nextVertical` khác `null`.
18. P4 (0 event) → `coldStart: true` và **mọi** `because` rỗng.
19. Mọi `because[].productId` khác `null` đều mở được `GET /products/{id}` → `200`.
20. Hai event giống hệt cách nhau đúng 30 ngày → trọng số sau decay chênh **hệ
    số 2.0 ± 0.01**.
21. Event cách 1 giờ so với cách 1 ngày → `decay` chênh dưới 3%.
    *(Chênh lớn nghĩa là `Δt` đang tính bằng giây.)*
22. `diagnostics.userVectorNorm` trong `1.0 ± 1e-5`.
23. Khách có chuyến Nha Trang đã kết thúc 60 ngày trước + 1 view Đà Nẵng hôm qua
    → kết quả thiên về **Đà Nẵng**. *(Kiểm tra `tripFactor` thực sự chạy.)*
24. Tắt CDP clone → `200` `strategy: "popular"`, không phải `500`.
25. Ngay sau checkout → `strategy` hoặc `nextVertical` đã đổi (**K1**).
26. p95 dưới 300 ms khi cache hit.

Bốn tiêu chí **20, 21, 22, 23** là quan trọng nhất trong cả danh sách. Chúng bắt
đúng bốn lỗi chạy được nhưng sai — sai đơn vị thời gian, quên normalize,
`tripFactor` không chạy, decay bị vô hiệu hóa. Không lỗi nào trong số đó bắt
được bằng cách đọc code.

---

## 10. Phụ thuộc còn mở

| # | Nội dung | Quy tắc tạm |
|---|---|---|
| S1 | `cutoff = 0.62` chưa benchmark | Dùng `0.62`, đo Ngày 3 trên 80 cặp + 10 truy vấn âm |
| S2 | `WEAK_RESULT_TOP_SCORE` / `MARGIN` chưa đo | `0.70` / `0.06` |
| S3 | Quy tắc 2 tầng chưa duyệt · `[C5]` | Code theo `includeVariants: false` |
| S4 | Soft delete chưa duyệt · `[U1]` | `because[].productName` giả định sản phẩm còn hàng trong `products` |
| S5 | Cache user vector chưa duyệt · `[P3]` | Không cache thì p95 `/recommendations` là 800 ms, không phải 300 ms |
| S6 | Công thức `popularity_score` chưa chốt · `[C7]` | Tạm dùng `log(1 + review_count)` |
| S7 | ~~Model embedding chưa chốt~~ — **đã chốt 22/09/2026** | Cohere `embed-multilingual-v3.0`, **1024 chiều**, vector lưu ở Weaviate (không còn pgvector). Xem `docs/prd/architecture.md` §4–§5. Kéo theo S8. |
| S8 | **Mới (22/09/2026): `EXACT_FILTER_SCORE` cần duyệt lại.** Mục "Chế độ truy xuất" phía trên lập luận rằng exact scan hợp lý vì toàn bộ vector nằm trong `shared_buffers` của Postgres. Weaviate là HNSW-first nên tiền đề đó không còn đúng, và HNSW chỉ trả top-K — không đủ tập đầy đủ để đếm `facets` như `[C4]` yêu cầu | Chưa chốt. Team Search quyết: (a) đếm `facets` bằng SQL trên Postgres rồi chỉ dùng Weaviate cho top-K, hay (b) đổi cam kết `facets` trong contract. **Không tự đổi `schemas/search.yaml` trước khi chốt.** |

S5 là phụ thuộc nặng nhất: không duyệt `[P3]` thì tiêu chí nghiệm thu 26 không
đạt được, và ngân sách §7.1 phải sửa.

---

## 11. Definition of Done

> Team Backend gọi được cả ba endpoint bằng mock sinh từ
> `src/shared/contracts/schemas/`, rồi đổi sang engine thật mà không phải sửa
> tầng `services`. Team Agent dựng được lịch trình 3 ngày mà mọi `productId`
> trong đó truy nguyên về một response của `/search` hoặc `/recommendations`
> trong cùng request.

Luồng nghiệm thu bắt buộc:

```
Đăng nhập P1
→ Home hiện gợi ý kèm because có contribution
→ Tìm "nghỉ dưỡng biển cho gia đình" → kết quả hợp lý, facets cộng bằng total
→ Mở chi tiết → /similar trả cùng taxonomy, không trả hạng phòng anh em
→ Thêm giỏ → checkout
→ Quay lại Home → strategy đổi sang cross_vertical, nextVertical khác null
```
