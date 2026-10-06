# Spec tạo bảng và mock data — tuần 1

Bản 20/09/2026 · dành cho Claude Code sinh code trong `src/data_collection/`. Schema là `db/vota_schema.sql` và `db/insider_schema.sql` (đã chạy thử); giải thích ở `docs/DATABASE_SCHEMA.md`, `docs/PRODUCT_SCHEMA.md`. Mọi thứ trong spec này chạy được lại từ đầu bằng một lệnh và cho cùng kết quả với cùng `--seed`.

## 0. Kết quả phải đạt (definition of done)

| # | Kiểm tra | Kỳ vọng |
|---|---|---|
| 1 | `docker compose up -d postgres` rồi `psql vota -c "\dt cdp.* catalog.* app.*"` | 15 bảng, 3 view (`catalog.product_meta`, `product_parents`, `search_rows`) |
| 2 | `psql insider -c "\dt"` | 5 bảng + view `live_events` |
| 3 | `make demo-db AS_OF=2026-09-22` từ repo root, hoặc chạy CLI seed từ `src/` | kiểm tra/bung snapshot, chạy < 2 phút, `demo-db-reset` xoá và nạp lại, log tóm tắt ra stdout và khối `seed-report` trong `src/data_collection/README.md` |
| 4 | `psql "$SEED_DATABASE_URL" -f db/verify.sql` | mọi dòng `PASS` (xem §7), trừ hai dòng FAIL dự kiến khi dùng catalog tổng hợp (xem ghi chú dưới bảng) |
| 5 | Baseline most-popular-in-destination (Evaluation chạy) | Recall@20 không gần 0, không > 0.6 |
| 6 | Đăng nhập 4 persona | Home hiện đúng section theo UX spec §4.1.3 |

**Ba điểm chốt 20/09 khi triển khai (khác chữ trong bản gốc bên dưới):**

1. **Connection của seed và verify là `SEED_DATABASE_URL`** (superuser), không phải `DATABASE_URL`. Role `vota_app` của `DATABASE_URL` không có quyền ghi `cdp.*` và không SELECT được `cdp.events`/`profiles`, nên chạy `db/verify.sql` bằng nó sẽ lỗi `insufficient_privilege` chứ không ra `FAIL`. Ghi chú lệnh trong `db/verify.sql` đã được đồng bộ theo biến này.
2. **Báo cáo ghi vào khối đánh dấu** `<!-- seed-report:start -->`…`<!-- seed-report:end -->` ở cuối `src/data_collection/README.md`. Thư mục `data-collection/` (gạch nối) nhắc ở §1 và §8 không tồn tại trong monorepo này, và `src/data_collection/README.md` là sổ tay crawler viết tay — `report.py` chỉ thay phần trong khối, không ghi đè cả file.
3. **Hai dòng `db/verify.sql` FAIL theo thiết kế khi dùng `products.synthetic.jsonl`:** `products >= 11387` và `is_recommendable properties >= 300`. Đây là ngưỡng tối thiểu theo snapshot catalog thật 2026-09-23 (11.387 sản phẩm; catalog mở rộng chỉ tăng nên vẫn PASS), trong khi catalog tổng hợp §1b cố ý chỉ khoảng 400–450 dòng với 40 property. Không thổi phồng §1b để lách; `report.py` ghi rõ nguồn catalog. Có `src/data_collection/data/products.jsonl` thật thì cả hai phải PASS.

**Điểm chốt 21/09 — seed làm đúng §2, §4–§6; mọi tham số ở `src/data_collection/seed/config.py`:**

Người dùng chốt sáu quyết định (21/09):

1. **Phạm vi:** code theo §2 (lịch, ngày bay, giờ nhận/trả phòng), §4, §5, §6. §1b (`gen_products.py`) và §2.3/§3 (`parse_combos.py`, đã tinh chỉnh cùng 64 mapping duyệt tay) giữ nguyên. RNG là `random.Random` của stdlib theo stream chuỗi, không đổi sang numpy — kết quả vẫn tất định theo `--seed`.
2. **Khách sạn `quantity = 1`** (số phòng, khớp hợp đồng booking). P1 ở **1 đêm** vì `app.booking_items.line_total = unit_price × quantity` (GENERATED) không nhân số đêm.
3. **Có event `search`** (30% chuyến), `product_id`/`taxonomy`/`event_group_id` NULL và không có câu truy vấn: `cdp.events` không có cột query, `app.search_logs` không seed. Hệ quả đã biết: các dòng này không replay được qua `HttpCdpClient` vì `schemas/cdp-clone.yaml` bắt buộc `searchQuery`.
4. **Chỉ `purchase` mang `event_group_id`**, giống dữ liệu app ghi thật (`BrowseEvent` không có gid). "3% event bỏ `event_group_id`" vì vậy áp lên purchase.
5. **Lịch phòng:** ~~kín 25–40%, Vinpearl `min(40%, gốc × 1,3)`~~ — thay ngày 02/10/2026: hạng phòng không có lịch thật mở đủ 30 đêm và cửa sổ là nguyên `[as_of, as_of + 29]`, không cắt theo ngày nguồn; ngày nguồn đã hỏi và báo hết phòng vẫn là `0`.
6. **`lifetime_order_count` đúng chữ §4:** chỉ đếm `event_group_id` khác NULL. Vài khách có purchase mất gid (cạnh lộn xộn) nên có 0 đơn nhưng `days_since_last_booking` khác NULL — dữ liệu bẩn có chủ đích.

Diễn giải cho chỗ spec mơ hồ hoặc tự mâu thuẫn:

| Chỗ | Cách làm |
|---|---|
| Khoảng "active 1–4 · dormant 1–2 · churned 1–2" cộng 1–3 view, 40% add_to_cart, 30% search | Giữ đúng *khoảng*, nhưng trọng số nghiêng về 1 (`TRIPS_PER_STAGE`, `VIEWS_PER_TRIP`, `NEW_VIEW_TRIP_RATE`). Phân bố đều cho ~15.000 event, vượt cổng 6.000–8.000 của `db/verify.sql`; cổng nghiệm thu thắng (tiền lệ 20/09) |
| "40% có add_to_cart" | 40% **chuyến** có add_to_cart cho mọi mục của chuyến, 5–120 phút trước purchase |
| "1–3 product_view" | Theo chuyến. View đầu là search unit cha của mục đầu (property của phòng, tuyến của chuyến bay); view thêm là search unit **khác** cùng điểm đến. Luôn trước purchase, trong 7 ngày |
| "Trải trong 24 tháng" | Áp cho mọi event, không chỉ purchase: lần mua cũ nhất cách as_of ≤ 730 − 7 − 1 ngày để view / search của chuyến đó cũng nằm trong 730 ngày |
| using_date = ngày mua + 7–45 ngày | Kẹp để mọi using_date của khách thường ≤ as_of − 1 (vé bay chỉ mở đúng một ngày, using_date tương lai sẽ làm FAIL `future purchases inside window`). Lần mua cuối của active cách as_of ≥ 9 ngày nên lead vẫn ≥ 7 |
| attraction = nhận phòng + 1 | Áp cho mọi vé (attraction, combo, golf), kể cả chuyến chỉ có vé |
| home_city có "Vinh" | Catalog gắn sân bay Vinh vào nhãn `originDestination = "Nghệ An"`; map qua `HOME_CITY_FLIGHT_ORIGIN` |
| Chọn sản phẩm theo Zipf | Một tầng trên mọi sản phẩm bookable của vertical trong điểm đến (khách sạn là hạng phòng), thứ tự `crc32(product_id)` thay `hash()` (hash đổi giữa các tiến trình). Hạng phòng thiếu brand thì lấy brand của property cha. Vé bay chỉ lấy tuyến xuất phát từ home_city |
| Điểm đến | Trọng số = số sản phẩm bookable; bốc lại tối đa 30 lần khi không đủ vertical cho chuyến; hết lượt thì là chuyến chỉ khách sạn ở điểm đến nặng nhất có phòng |
| Golf 3% | 3% **mọi chuyến**, luôn là chuyến nhiều vertical, điểm đến bốc lại tới khi có golf |
| Chuyến một / nhiều vertical | Một vertical: bốc loại trước (`SINGLE_VERTICAL_WEIGHTS`), rồi điểm đến. Nhiều vertical: luôn có phòng, thêm vé bay (`MULTI_FLIGHT_RATE`) và/hoặc vé (`MULTI_TICKET_RATE`); không có gì thì ép loại có sẵn |
| Khách new | 0 hoặc 1 chuyến chỉ có product_view (không search), 1–90 ngày trước as_of |
| Persona | Khuôn cố định: không search, 1 view mỗi chuyến, không add_to_cart ở chuyến cũ (P1 = 12 event, P3 = 6, dưới cap 15 mà `verify.sql` tính cả persona). Persona luôn opt-in, gdpr true, không bị cạnh lộn xộn. P1 lấy phòng Vinpearl Nha Trang phổ biến nhất còn trống đêm as_of + 12 |
| Lịch phòng | Từ 02/10/2026: phòng không có lịch thật mở đủ 30 đêm (`"1" × 30`); chỉ ngày nguồn đã hỏi và báo hết phòng là `0`. Lịch mô phỏng kín 25–40% theo cụm (chốt 21/09) đã bỏ |
| Ngày bay | Ngày trip.com đã liệt kê (`datesSeen`) sớm nhất trong cửa sổ — trùng `sourceAvailableFrom` khi nó nằm trong cửa sổ; không có thì `as_of + crc32(product_id) % 30`. Vé báo giá ngày cố định (`fixedDepartureDate`, gồm khứ hồi): giữ ngày đi thật khi nằm trong cửa sổ, không thì dời như trên (xem §2.1) |
| Phễu "open 35% → click 8%" | click 8% tính trên delivered, như open |
| Email Insider | Luôn `<cdp_user_id viết thường>@example.com`, kể cả persona (hợp đồng Insider chỉ yêu cầu khớp `cdpUserId`) |
| gdpr opt-out | `max(as_of − U(0, 180) ngày, created_at + 1 ngày)`, lưu ở `insider_profiles.updated_at` (mốc `verify_insider.sql` dùng) |
| unsubscribe | Sau unsubscribe profile không còn dòng `channel_events` nào, ở mọi kênh |
| campaign_id | 12 chiến dịch cách đều từ as_of − 176 tới as_of − 11, id `CMP-yyyymm-NN` với NN là thứ tự trong tháng |
| Baseline Recall@20 trong report | Ẩn lần đặt cuối của khách có ≥ 2 `event_group_id` **khác NULL**. Đòn bẩy trong phạm vi spec: `MULTI_FLIGHT_RATE`, `MULTI_TICKET_RATE`, `SINGLE_VERTICAL_WEIGHTS` (mục bị ẩn là mục cuối checkout, vé bay / vé tham quan ít sản phẩm nên dễ trúng top-20). Không vặn `TRIPS_PER_STAGE` về phía 1 — làm recall tăng. Tập ẩn chỉ ~270 khách nên chỉ số dao động mạnh giữa các seed; vượt `RECALL_CEILING` thì report ghi **VƯỢT TRẦN** và `seed_histories` in WARNING nhưng không dừng pipeline (DoD #5 đo trên seed demo 42) |

Số đo trên snapshot 11.387 dòng, `--as-of 2026-10-02 --seed 42`, `MULTI_TICKET_RATE = 0.35`, lịch phòng mở đủ 30 đêm (đo 02/10/2026): 7.324 event (purchase 3.288, product_view 2.175, add_to_cart 1.332, search 529), stage đúng 25/45/20/10, 64% chuyến ≥ 2 vertical, golf 2,9%, chuyến có search 29%, có add_to_cart 41%, purchase attraction 597 / combo 246, Recall@20 = 59,9%. Quét seed 1–61 cùng snapshot: `MULTI_TICKET_RATE = 0.35` cho Recall trung bình 51,5%, cao nhất 59,9%, 0/61 seed vượt 60%; mức cũ 0.10 cho trung bình 51,4%, cao nhất 60,7%, 1/61 vượt. Đợt quét 62 seed cũ trên snapshot 10.320 dòng (0.10, lịch kín 25–40%): trung bình 54,0%, 4/62 vượt.

## 1. Đầu vào và bố cục code

```
src/data_collection/
├── data/products.jsonl         # runtime artifact từ crawler, 13 trường CDP; bị gitignore
├── data/products.synthetic.jsonl # fallback do gen_products.py sinh; sourceRef bắt đầu bằng 'synthetic:'
├── snapshots/2026-09-30/       # snapshot catalog mặc định nén + manifest/checksum + mapping combo đã duyệt; có trong Git
├── seed/
│   ├── __main__.py             # CLI: python -m data_collection.seed --as-of YYYY-MM-DD --seed 42 [--reset] [--users 2000]
│   ├── config.py               # mọi tỷ lệ, phân bố, danh sách từ khoá — KHÔNG hard-code trong logic
│   ├── gen_products.py         # bước 0: catalog tổng hợp khi chưa có crawl (§1b)
│   ├── load_products.py        # bước 1: products.jsonl → cdp.products (+ cửa sổ 30 ngày, availability, combo attrs)
│   ├── parse_combos.py         # bước 2: description → catalog.combo_items
│   ├── seed_histories.py       # bước 3: cdp.profiles + cdp.events (2.000 khách, ~7.000 event, theo chuyến)
│   ├── seed_app.py             # bước 4: app.users (4 persona + 50 test), app.bookings cho persona có chuyến sắp tới
│   ├── seed_insider.py         # bước 5: database insider — partners, profiles, identifiers, events (TTL), channel_events
│   └── report.py               # in tóm tắt + ghi data-collection/README.md
└── README.md                   # sinh bởi report.py: số liệu, as_of, seed, nguồn từng trường
```

Kết nối: `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vota`, `INSIDER_DATABASE_URL=…/insider` (env, `.env.example`). Thư viện: `psycopg[binary]`, `numpy` cho phân bố; không ORM. Mọi bước ghi bằng `COPY` hoặc batch insert 1.000 dòng; toàn bộ một bước trong một transaction.

**Seed PostgreSQL không nạp vector.** Vector thuộc collection `ProductE5` của Weaviate (model local `intfloat/multilingual-e5-small`, 384 chiều; collection `Product` của Cohere chỉ còn cho đường lui) và được đồng bộ riêng bằng `python -m src.backend.jobs.embed_products`/`make index-vectors`; job chỉ embed lại khi `textHash` hoặc `modelVersion` đổi. **Không nạp `carts`, `conversations`, `recommendation_logs`, `search_logs`** — sinh khi chạy app.

## 1b. Bước 0 — `gen_products.py` (chỉ chạy khi chưa có crawl)

Crawler chưa xong không chặn mock: sinh một catalog tổng hợp **đúng contract `SCHEMA.md`** (13 trường, khoá `attributes` theo taxonomy) rồi mọi bước sau chạy y nguyên. Loader nhận `--products PATH`; mặc định ưu tiên `src/data_collection/data/products.jsonl`, sau đó dùng snapshot nén có version trong `src/data_collection/snapshots/`. Snapshot được kiểm số dòng/SHA-256 và bung vào `data/snapshots/<snapshotId>/`; bản nén cùng mapping combo đã duyệt được commit, còn JSONL đã bung và output seed vẫn bị ignore. Chỉ khi cả runtime catalog lẫn snapshot đều không có mới sinh fallback tổng hợp trong `data/`.

| Taxonomy | Số lượng | Cấu trúc bắt buộc |
|---|---|---|
| hotel | 40 property (60% `brand = Vinpearl`), mỗi property 2–5 room → ~140 room | `level`, `parentProductId`, `province`, `city`, `latitude/longitude` (property), `starRating` 3–5, `reviewScore/Count`, `roomName`, `maxOccupancy`, `oceanView`; property `unitPrice = null` |
| flight | 12 route (HAN/SGN ↔ CXR/PQC/DAD/VDO) × 8–15 flight trong cửa sổ → ~150 | route `level = route`; flight `level = flight`, `parentProductId`, `airline` ∈ {VN, VJ, QH}, `flightNo`, `departureAt/arrivalAt` (+07:00), `availableFrom = availableTo = ngày bay` |
| attraction | 60 (VinWonders/Safari/Grand World + điểm công cộng) | 15% `ticketed = false` và `unitPrice = null`; `openingHours`, `province` |
| golf | 8 | `holes` 18/27, `teeTimeSlots` |
| combo | 40 | `description` sinh từ mẫu liệt kê thành phần bằng **đúng tên** hotel_room / attraction / golf cùng `destination` ("2 đêm phòng Deluxe Ocean View tại Vinpearl Resort Nha Trang + vé VinWonders Nha Trang + buffet sáng") để `parse_combos` map được ≥ 70%; 30% ghi "giá cho 1 khách" → `priceBasis = per_person`; `name` chứa "3N2Đ"/"4N3Đ" để regex `nights` bắt được |

Tổng ≈ 450 dòng. `destination` lấy từ danh sách Vinpearl: Nha Trang, Phú Quốc, Đà Nẵng, Hội An, Hạ Long, Cửa Hội, Tây Ninh; `productId = uuid5(NAMESPACE_URL, sourceRef)` với `sourceRef = "synthetic:<taxonomy>:<slug>"`. `imageUrl` = `https://placehold.co/800x600?text=<slug>`. Cạnh lộn xộn cố ý: 3% thiếu `imageUrl`, 2% `description` < 40 ký tự, 2 cặp property gần trùng tên (để dedupe/search có việc), 1 route không có flight nào (để câu hỏi "mọi route có ≥ 1 chuyến?" có ví dụ). Quy mô nhỏ hơn crawl thật ~5 lần là cố ý: chạy nhanh, đọc tay được; phân bố event ở §4 tính theo tỷ lệ nên không đổi.

## 2. Bước 1 — `load_products.py`

Đọc `products.jsonl`, mỗi dòng → một dòng `cdp.products`, tên trường camelCase → snake_case. `attributes` giữ nguyên rồi bổ sung:

1. **Cửa sổ 30 ngày.** Lưu giá trị gốc: `attributes.sourceAvailableFrom/To` = `availableFrom/To` của file (nếu có). Rồi:
   `available_from = max(sourceFrom, as_of)`, `available_to = min(sourceTo, as_of + 29)`; nguồn không có → `[as_of, as_of + 29]`.
   Chuyến bay (`taxonomy = flight`, `level = flight`): `available_from = available_to = ngày bay`; ngày bay = `sourceAvailableFrom` nếu nằm trong cửa sổ, nếu không thì **dời** vào cửa sổ: `as_of + (hash(product_id) % 30)`. Tuyến (`level = route`): min/max của các chuyến con.
   Vé báo giá ngày cố định (`fixedDepartureDate: true`, gồm khứ hồi; `docs/prd/data-model.md` §3): giữ ngày đi thật khi nằm trong cửa sổ, kể cả khi `priceValidUntil` đã qua; ngày đi ngoài cửa sổ thì dời như trên, dùng `product_id` nhỏ nhất của hành trình (các hạng vé của cùng hành trình dời cùng ngày), ngày đã có hành trình khác cùng chuyến thì lùi sang ngày kế tiếp. Hai chặng dời cùng số ngày, giữ giờ và `stayDays`; `returnDate` và ngày trong `name`/`description` đổi theo; giá và `priceValidUntil` giữ nguyên, không thêm khoá. Chỉ seed làm vậy: job cào (`fresh_catalog_db.apply_window`) giữ ngày thật và khoá vé hết hạn báo giá.
   Sau khi cắt mà `available_from > available_to` → đặt `available = false`, `available_from = available_to = NULL`.
2. **Lịch 30 ngày** `attributes.availability = {from: as_of, days: 30, calendar: "…30 ký tự…"}` chỉ cho `level = room` và `taxonomy ∈ {attraction, golf}`:
   - room: nếu Vinpearl có `pricesByDateQueried` phủ ≥ 85% cửa sổ (ít nhất 26/30 ngày), dùng lịch thật từ `pricesByDate`; ngày đã hỏi có giá = `1`, đã hỏi không có giá = `0`. Dữ liệu hỏi thưa không được coi ngày chưa hỏi là hết phòng: mở đủ 30 đêm, chỉ ngày đã hỏi mà không có giá là `0` (từ 02/10/2026; trước đó là lịch mô phỏng kín 25–40%). Cửa sổ của hạng phòng là nguyên `[as_of, as_of + 29]`, không cắt theo ngày nguồn. Ký tự i = ngày `as_of + i`; `1` trống, `0` kín.
   - attraction/golf: toàn `1`, trừ blackout: 2–3 ngày ngẫu nhiên cho 15% sản phẩm.
   - flight, property, route, combo: không có khoá này.
   - Job cào mới (`src/data_collection/fresh_catalog_db.py`) áp đúng bước 1–2 cho toàn catalog mỗi lượt, với `as_of` = ngày chạy, thêm hai điểm: phòng có dữ liệu hỏi thưa (ví dụ Trip.com 3 ngày mẫu) dùng lịch mô phỏng nhưng các ngày đã hỏi nằm trong cửa sổ ghi theo kết quả thật (có giá = `1`, hết phòng = `0`); dòng `available = false` (hết bán, giá quá hạn, ngoài cửa sổ) có lịch toàn `0`.
3. **Combo:** `attributes.nights` từ regex `(\d+)\s*[Nn]\s*(\d+)\s*[ĐđD]` hoặc "(\d+) ngày (\d+) đêm" trên `name + description`; `attributes.minPax` từ "cho (\d+) (người|khách)"; `attributes.priceBasis = per_person` nếu text khớp `/khách|/người|giá cho 1 người|mỗi khách|per person`, ngược lại `per_package`.
4. **Giờ cố định** (khi parse được, không thì bỏ qua): flight `departureAt`, `arrivalAt` (ISO 8601 +07:00) từ attributes crawl nếu có; hotel `checkInTime = "14:00"`, `checkOutTime = "12:00"` mặc định cho property.

5. **Vé Thương gia mô phỏng** (`seed/simulated_business.py`, `docs/prd/data-model.md` §3): sau khi nạp, mỗi vé `level = flight` có số hiệu chuyến, hạng khác `BUSINESS`/`FIRST`, sinh một dòng `sourceRef = demo:business:<sourceRef gốc>`, `cabinClass = BUSINESS`, giá = giá gốc × 2,65 làm tròn nghìn, `attributes.simulated = true`, `fieldSources.unitPrice = "mô phỏng"`, tên "(giá minh hoạ)"; ngày, cửa sổ, `available`, `priceValidUntil` chép từ vé gốc. Vé Thương gia thật cùng hành trình và ngày thắng (vé mô phỏng `available = false`). Seed đầy đủ luôn bật; `--catalog-only` và job fresh mặc định bật, `SIMULATED_BUSINESS_FARES=0` thì khoá (không xoá) vé mô phỏng đã có. Snapshot 2026-09-30 → 797 vé (290 khứ hồi, 507 một chiều / vé cũ).

Idempotent: `INSERT … ON CONFLICT (product_id) DO UPDATE` toàn bộ cột.

## 3. Bước 2 — `parse_combos.py`

Chạy sau bước 1 cho mọi `taxonomy = combo`. Thuật toán và bảng từ khoá: `docs/DATABASE_SCHEMA.md` §9. Ghi `catalog.combo_items` với `source = 'description_parse'`, `confidence`, `evidence`. Trước khi ghi: `DELETE WHERE combo_product_id = … AND source = 'description_parse'` (giữ `manual`). Map sang `item_product_id` bằng `pg_trgm` (`CREATE EXTENSION IF NOT EXISTS pg_trgm` trong script, không sửa DDL): `similarity(unaccent(label), unaccent(name)) > 0.45` trong cùng `destination`, ưu tiên `brand = Vinpearl`; hotel map về `hotel_room` con có `roomName` khớp, không có thì về property và `confidence = 0.6`.

Combo có cấu trúc trong `attributes` (từ 02/10/2026) thì không tách từ tên, `source = 'api'`:
- `comboKind = flight_hotel`: bundle Vinpearl.
- `comboKind = trip_real_flight_hotel`: combo bay + ở của trip.com.
  - Thành phần vé máy bay: tuyến tìm theo `fromCode`/`toCode`, số khách lấy `adult` trong `url`, nhãn là phần tên trước " + ".
  - Thành phần khách sạn: nhãn là `<roomType> tại <hotelName>`, số đêm = `oDate − iDate` trong `url`. Chỉ map theo `hotelName` khi `similarity ≥ 0.7`. `roomType` không khớp phòng nào thì gán về property, `confidence = 0.6`.
  - Lý do: tách theo tên thì cắt mất điểm đến ở " - " và cắt đôi tên khách sạn ở "&" hoặc ",".

Với mọi combo:
- Mảnh chỉ nêu địa điểm (tên venue, "Phá đảo 04 khu", "trọn vẹn 03 khu") thành vé vào cửa của venue, nếu combo chưa có attraction nào.
- "N người/khách" không phải thành phần.

Job nạp DB (`fresh_catalog_db.load_into_db`) chép `combo_items_manual.jsonl` của snapshot mặc định vào thư mục lượt cào trước khi parse, để không mất các dòng đã duyệt tay.

Báo cáo: số combo, số hạng mục, tỷ lệ map được theo `item_kind`, số dòng `confidence < 0.8` (hàng đợi soát tay).

## 4. Bước 3 — `seed_histories.py`

Tất cả ngày tính từ `as_of`. RNG = `numpy.random.default_rng(seed)`.

**Khách (2.000):** `cdp_user_id = "VP" + 7 số` (không trùng, bắt đầu từ 0000001). Phân bố life stage: new 25%, active 45%, dormant 20%, churned 10%. `vinclub_tier`: Member 60 / Gold 25 / Platinum 10 / Diamond 5. `home_city` từ 8 thành phố (Hà Nội 35%, TP.HCM 35%, còn lại chia đều: Đà Nẵng, Hải Phòng, Cần Thơ, Nha Trang, Huế, Vinh). `email_optin = false` cho 5%; `sms_optin`, `push_optin` độc lập 3%.

**Chuyến (event_group_id = "OFF" + yyyymmdd + 3 số thứ tự trong ngày):**
- Số chuyến/khách theo stage: new 0–1 (1 chuyến chỉ có `product_view`, không mua) · active 1–4 · dormant 1–2 (chuyến cuối cách `as_of` 180–365 ngày) · churned 1–2 (> 365 ngày). Trải trong 24 tháng trước `as_of`.
- Mỗi chuyến **một destination**, chọn theo trọng số số sản phẩm bookable của destination. Ngày đi `using_date` = ngày đặt + 7–45 ngày; hotel `using_date` = nhận phòng; flight = ngày bay = nhận phòng; attraction = nhận phòng + 1.
- Vertical trong chuyến: luôn có 1 vertical; 65% chuyến ≥ 2 (thứ tự hotel → flight → attraction/combo → golf 3%). Mỗi vertical chọn **một** sản phẩm `is_bookable = true` trong destination theo **power-law** Zipf s = 0.8 trên thứ tự cố định (hash product_id); `brand = Vinpearl` nhân trọng số 2. Mức 0.8 được hiệu chỉnh trên snapshot 10.320 dòng để baseline popular-in-destination Recall@20 khoảng 0.58, không vượt trần 0.60.
- Event của một chuyến, theo thứ tự thời gian: 1–3 `product_view` (0–7 ngày trước mua, có thể là sản phẩm khác cùng destination) → 40% có `add_to_cart` → `purchase` với `quantity` 1–2 (hotel: 1; flight: 1–3 khách; attraction: 2–4), `unit_price` = `products.unit_price` lúc đó (cộng ±5% nhiễu, làm tròn nghìn), `taxonomy` copy từ products. `search` event: 30% chuyến có 1 event `search` trước tiên (`product_id` NULL).
- Giới hạn: không khách nào > 15 event; tổng mục tiêu 6.000–8.000.

**Cạnh lộn xộn (sau khi sinh):** 2% event `purchase` đổi `product_id` thành UUID không tồn tại; 3% event bỏ `event_group_id`; 1% khách có `product_view` ở hai destination khác nhau cùng ngày.

**Profiles suy từ event, không sinh độc lập:** `lifetime_order_count` = số `event_group_id` có purchase; `days_since_last_booking` = `as_of − max(timestamp của purchase)`; `purchased_verticals` = tập `taxonomy` đã mua; `last_destination` = destination của chuyến purchase gần nhất; `lifecycle_stage` gán lại từ số liệu: 0 purchase → new, ≤ 180 ngày → active, 181–365 → dormant, > 365 → churned (phải khớp phân bố mục tiêu ±5%, nếu lệch thì điều chỉnh số chuyến, không sửa tay stage).

### 4.1. Bộ đánh giá RecSys `eval-v2` (05/10/2026, người dùng chốt) — KHÔNG phải seed demo

Mục đích: đủ tín hiệu để đánh giá mọi thuật toán RecSys (CF, chuyến kế tiếp, bỏ giỏ, khách mới) — bộ demo §4 chỉ có ~270 khách quay lại và
0 lần bỏ giỏ. Bật bằng `--profile eval-v2` (`seed_histories` hoặc CLI `python -m data_collection.seed`); không có cờ thì §4 không đổi
một byte (kiểm 05/10: cùng sha output trước / sau thay đổi). Tham số ở `config.PROFILES["eval-v2"]`:

| Tham số | Demo §4 | eval-v2 |
|---|---|---|
| Số khách | 2.000 | 5.000 (stage 25/45/20/10 giữ nguyên) |
| Số chuyến / khách (active · dormant · churned) | 1–4 · 1–2 · 1–2, nghiêng mạnh về 1 | cùng khoảng, trọng số `(0,50; 0,25; 0,15; 0,10)` · `(0,70; 0,30)` → **≈ 40 % khách có mua quay lại ≥ 2 chuyến** |
| Event tối đa / khách | 15 | 40 |
| Chuyến một vertical | hotel 85 % · vé 10 % · bay 5 % | hotel 50 % · vé 30 % · bay 20 % |
| product_view / chuyến (1 / 2 / 3) | 90 / 8 / 2 % | 50 / 30 / 20 % |
| **Bỏ giỏ** | không có | trước mỗi chuyến có mua, xác suất 0,22 chèn một lần bỏ giỏ: product_view → add_to_cart mọi mục, **không purchase, không `event_group_id`** (như app thật); 50 % cùng điểm đến với chuyến mua kế sau, 3–60 ngày trước đó → ≈ 20 % số chuyến |

Persona P1–P4 và 50 tài khoản test giống hệt demo. Số đo (snapshot 30/09, `as_of` 05/10, seed 42): 32.782 event, 3.722 khách có mua, 1.502
quay lại (40 %), 2.482 add_to_cart không mua.

`db/verify.sql` trên bộ này FAIL theo thiết kế đúng ba dòng quy mô: `profiles = 2000`, `events 6000-8000`, `max events per user <= 15`.
Nạp vào **database riêng** (đánh giá) hoặc thay lịch sử bằng `--history-only` (dưới); Insider clone không sinh lại ở `--history-only`.

**`--history-only`** (`database.load_history`, sửa 05/10 sau review) — thay lịch sử seed trên database đang dùng (staging) trong một transaction:

| Phần | Xử lý |
|---|---|
| `cdp.profiles` khách seed (`VP` + 7 số) | upsert từ file; khách có event được giữ / bị bỏ event được **tính lại từ `cdp.events` trong database** theo luật §4 (số đơn, loại đã mua, điểm đến gần nhất, ngày từ lần mua cuối, vòng đời) |
| `cdp.events` khách seed / tài khoản test | xoá lịch sử sinh cũ (`timestamp` < ngày seed cũ), **giữ event phát sinh qua web** (≥ ngày seed cũ — seed luôn sinh trước `as_of`; mặc định suy từ đơn seed P1 = `as_of` cũ, ghi đè `--keep-events-since`) và event mua của đơn thật |
| Persona P1–P4 (người dùng chốt phương án **B1**) | **reset về kịch bản**: xoá cả event phát sinh qua web, chỉ giữ event mua của đơn đặt thật (đơn không bị xoá) — demo lặp lại được |
| Đơn seed (`app.payments.provider = 'seed'`, P1) | xoá rồi nạp đơn mới; đơn thật giữ nguyên |
| `app.users` | chỉ thêm persona / test còn thiếu, không đổi mật khẩu đã có |
| Tài khoản web (`VPW…`), giỏ, hội thoại, catalog, Weaviate, Insider | không đụng (Insider không sinh lại) |
| Sản phẩm thiếu ở catalog đích | mặc định **dừng** nếu có ≥ 1 event trỏ sản phẩm của catalog nguồn mà đích không có; `--drop-missing-products` bỏ các event đó và tính lại hồ sơ khách bị ảnh hưởng |
| Sao lưu / khôi phục | `--history-backup FILE` lưu mọi cột của profile + event khách seed và đơn seed trước khi nạp; `--history-restore FILE` đưa về đúng bản đó (xoá 3.000 profile mới nếu không bảng nào trỏ tới). Chỉ dùng ngay sau lần nạp hỏng: event web phát sinh sau khi nạp cũng bị xoá |

Diễn tập 05/10 trên bản sao giống staging (seed demo `as_of` 30/09 + hoạt động web 02–04/10 của P1, `test01`, một tài khoản `VPW…`, 3 sản phẩm bị
xoá khỏi catalog): lần nạp không cờ dừng (88 event thiếu sản phẩm); có `--drop-missing-products` → event web `test01` + đơn thật P1 + tài khoản
`VPW…` (event, đơn, giỏ) và mật khẩu đã đổi giữ nguyên, event web của P1 bị reset, 0 profile lệch số đơn với event; khôi phục → hash event,
profile, đơn seed **trùng 100 %** trạng thái trước khi nạp.

### 4.2. Bổ sung CDP `append-v1` (05/10/2026)

Phục vụ FR-CDP-01/03, FR-REC-01/02. Theo yêu cầu người dùng, làm giàu staging bằng **khách tổng hợp mới**; không dùng
`--history-only` để thay lịch sử. `python -m data_collection.seed.append_histories` có hai bước:

- `prepare --batch <id> --as-of YYYY-MM-DD --out <thư-mục-mới>`: đọc catalog hiện hành qua `SEED_DATABASE_URL`, lưu catalog và batch có SHA256.
- `apply --artifact <batch.json> --receipt <file-mới>`: thêm trong một transaction, giữ receipt chứa ID chính xác sau commit.

Phân bố nằm ở `config.PROFILES["append-v1"]`: kế thừa eval-v2, sinh 5.000 khách ngoài bốn persona; không sinh cạnh sản phẩm giả/mất group.
ID khách và group có tiền tố `VPX:<batch>:`. Không sửa hồ sơ/event cũ, app.users, đơn, catalog hoặc Insider. Persona sinh nội bộ được loại khỏi
batch. Hồ sơ suy từ event như §4. Batch này không đại diện khách thật; không dùng số đo để tuyên bố chất lượng production.

Cùng batch + nội dung đã nạp → no-op; thiếu sản phẩm, batch một phần hoặc dữ liệu đã đổi → dừng, rollback. Khóa theo batch ngăn hai job
cùng batch chạy đồng thời. Không có bảng job mới; catalog/batch/receipt là artifact ngoài DB. Lệnh không tự sao lưu toàn DB vì không thay/xóa
lịch sử cũ. Nếu cần bỏ batch, dùng danh sách ID trong receipt sau kiểm tra các tham chiếu phát sinh; không xóa theo khoảng ID hoặc reset DB.

Giữ nguyên `db/verify.sql`: ba ngưỡng quy mô demo (2.000 hồ sơ, 6.000–8.000 event, ≤15 event/khách) không áp cho dữ liệu đã bổ sung;
báo cáo vẫn ghi mọi PASS/FAIL thực tế, phân biệt lỗi sẵn có và lỗi mới. Tqanh phải đóng băng snapshot/split mới để đo sau nạp;
không tái sử dụng split eval-v2 trên database đã gộp thêm dữ liệu.

## 5. Bước 4 — `seed_app.py`

`app.users`: 4 persona + 50 tài khoản test `test01@vota.demo`…; mật khẩu chung `Demo@2026` băm **Argon2id** (m=19456, t=2, p=1 — đúng tham số backend, auth §8.1; salt tất định theo `user_id` để seed tái lập được); `cdp_user_id` cố định cho persona: P1 `VP0000001`, P2 `VP0000002`, P3 `VP0000003`, P4 `VP0000004` (seed_histories phải chừa 4 id này và sinh lịch sử đúng bảng dưới).

| Persona | Lịch sử phải sinh (tương đối `as_of`) | Kỳ vọng Home |
|---|---|---|
| P1 Minh Anh `P1_frequent` | 3 chuyến Nha Trang trong 18 tháng (hotel + attraction); **chuyến sắp tới**: purchase `hotel_room` Vinpearl Nha Trang tại `as_of − 3`, `using_date = as_of + 12`, có `app.bookings` + `booking_items` tương ứng, chưa có flight/attraction; active, Gold | "Hoàn thiện chuyến Nha Trang" → flight / attraction |
| P2 Quốc Bảo `P2_first_time` | 2 `product_view` Phú Quốc tại `as_of − 2`, `as_of − 1`; không purchase; new | cold start có `because` |
| P3 Thu Hà `P3_dormant` | 2 chuyến Phú Quốc, chuyến cuối `as_of − 190`; dormant | "Chào mừng quay lại" |
| P4 Khách mới `P4_no_history` | 0 event; new | chỉ "Được đặt nhiều" |

`app.bookings` cho P1: `reference_code = "VOTA-" + yyyymmdd(as_of+12) + "-" + 4 ký tự`, `event_group_id` trùng với event purchase, `total_amount` = Σ line_total. Không tạo bookings cho khách seed khác.

## 6. Bước 5 — `seed_insider.py` (database `insider`, ghi trực tiếp SQL — đây là storage của clone)

1. `partners`: `('vota', token từ env INSIDER_TOKEN, mặc định 'dev-token')`.
2. `insider_profiles`: một profile / `cdp_user_id` (2.000). `attributes` = tập con: `{vinclub_tier, home_city, last_destination, lifecycle_stage}`; `gdpr_optin = false` cho đúng những khách có cả `email_optin = sms_optin = push_optin = false` (≈ 0.005%) **cộng** thêm 2% ngẫu nhiên.
3. `identifiers`: mỗi profile 3 dòng đang hiệu lực — `cdp_user_id`, `email` (`<cdp_user_id lowercase>@example.com`), `phone` (09 + 8 số, không trùng). 1% profile có thêm một `email` cũ đã đóng (`valid_to = as_of − 30`) để PATCH identity có lịch sử sẵn.
4. `insider_events`: **bản sao** `cdp.events` với `event_time ≥ as_of − 90 ngày`, cộng `purchase` với `event_time ≥ as_of − 730`; `event_params` = `{product_id, taxonomy, quantity, unit_price, event_group_id, using_date}`. Không chép event cũ hơn — TTL là luật, view `live_events` sẽ lọc.
5. `channel_events`: ~10 dòng/profile trong 6 tháng, chuỗi `sent → delivered 97% → open 35% → click 8%`; `bounce` 2% thay delivered; `unsubscribe` 1% (sau đó không còn dòng nào); profile `gdpr_optin = false` không có dòng nào sau ngày opt-out (`as_of − ngẫu nhiên 0–180`). `campaign_id = "CMP-" + yyyymm + "-" + 2 số`.

## 7. `db/verify.sql` — mỗi câu trả về `PASS` / `FAIL`

Cột đếm và ngưỡng của snapshot hiện hành: products ≥ 11.387 · profiles 2.000 · events 6.000–8.000 · combo_items ≥ 93 · mọi `purchase` có `event_group_id` trừ ~3% · mọi chuyến một destination (JOIN events → products theo `event_group_id`, `count(DISTINCT destination) = 1`, cho phép ≤ 1% vi phạm do cạnh lộn xộn) · `is_recommendable` true cho ≥ 300 property · P1 có đúng 1 `app.bookings` và event purchase cùng `event_group_id` · `using_date` của mọi purchase tương lai nằm trong `[available_from, available_to]` · insider: `live_events` không có `product_view` cũ hơn 90 ngày · profiles = 2.000 · identifiers hiệu lực = 6.000.

## 8. Việc Claude Code KHÔNG được tự quyết

Không thêm cột vào `cdp.products`; không thêm bảng; không ghi vector; không sửa DDL để "cho tiện" — nếu spec thiếu thì hỏi. Mọi tỷ lệ ở §4–§6 nằm trong `config.py` để Evaluation chỉnh mà không đọc code.
