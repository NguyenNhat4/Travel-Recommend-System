# arms.md — toàn bộ arm của benchmark embedding + search (Weaviate + Cohere)

Phục vụ: FR-SRC-01, FR-SRC-02, FR-SRC-03, NFR-PERF-01, NFR-PERF-03 (`docs/prd/requirements.md`).

Bản 23/09/2026 · đi kèm `search-eval-local-spec.md` (cách chạy) và `search-eval-checklist.md` (ai chạy ngày nào). File này là **nguồn duy nhất** liệt kê arm: `arms/*.yaml` phải khớp bảng §1; arm không có trong file này không được chạy.

Mọi ví dụ dưới đây là **minh hoạ cách arm hoạt động**, không phải số đo. Sản phẩm ví dụ: *Vinpearl Resort Nha Trang* (hotel_property, 5 sao, Nha Trang, family-friendly, amenities gồm bãi biển riêng · hồ bơi · công viên nước · spa · kids club · buffet sáng · Wi-Fi · máy lạnh · lễ tân 24h · bãi đỗ xe · nhà hàng · phòng gym…; hạng phòng Deluxe Ocean View · Family Suite · Villa Private Pool; giá từ 2,8 triệu; review 8,9).

Sáu query dùng xuyên suốt:

| | Query | Slice |
|---|---|---|
| q1 | `resort nha trang cho gia dinh co tre nho` | no_diacritics |
| q2 | `KS 5 sao PQ có kids club dưới 3 triệu cho 4 người` | multi_constraint + abbrev |
| q3 | `VinWonders` | named_entity |
| q4 | `villa hồ bơi riêng Phú Quốc` | parent_child |
| q5 | `resort ở Sapa` | out_of_catalog |
| q6 | `khách sạn Đà Nẵng không có hồ bơi` | amenity_negation |

---

## 0. Đã đủ chưa — đối chiếu với các plan trước

So với plan ngày 23/09 (chiều 1 T0–T7 / E, chiều 2 R0–R6) và plan Weaviate (E1–E6, S0–S8, F1, P1–P6), bản này **bổ sung 5 arm** còn thiếu và **tách 1 arm** cho rõ:

| Thiếu ở plan trước | Thêm vào | Bắt buộc? |
|---|---|---|
| Đối chứng model mở thứ hai (`gte-multilingual-base`, §6 `EMBEDDING_STACK_SWITCH`) | E2.gte | Tuỳ chọn — chỉ khi máy chạy nổi |
| Vector phụ synthetic query: embed ở không gian `document` hay `query`? | E5.doc / E5.qry | Bắt buộc cả hai (rẻ) |
| Tham số BM25 `k1`/`b` cho tiếng Việt | S1.k1b | Tuỳ chọn |
| CSLS chống hub (R5 plan cũ, rơi khi sang Weaviate) | S9 | Tuỳ chọn — chỉ khi `hub_score_max` > 3 |
| `attribute_vector` riêng (R6 plan cũ) | S10 | **Giai đoạn 3**, không chạy tuần này |
| E4.w60 trùng T4 (T4 đã dùng 60 từ) | E4 thành w30 / w150 / full, w60 = arm E1 thắng | — |

Tổng: **43 arm** — 39 bắt buộc, 3 tuỳ chọn (E2.gte, S1.k1b, S9), 1 giai đoạn 3 (S10). *(Bản trước ghi nhầm 36 / 6 / 1.)* Hai arm bắt buộc có điều kiện: E6 chỉ chạy khi model chốt là Cohere; E4.* bị bỏ qua nếu E1a chọn T1 (không có description).

Collection Weaviate: 14–16 collection chính (8–9 text variant, 0–3 độ dài, 3 model, 1 int8) + 2 collection vector phụ (doc, qry) + collection phụ cho P4/P5 nếu luồng dùng vector phụ. Chi phí Cohere cho toàn bộ ước **$0,5–2** tuỳ số search unit thật (1.125–5.000) và độ dài `embed_text`, cộng ~$0,8 cho rerank ở S8 và P6.

**Rev 2 (cùng ngày) đổi cách chạy, không đổi số arm:**

1. E3, E1.T6, E1.T7 chuyển lên cổng **SAN** chạy ngay sau B0 và so với B0 — eval hỏng thì biết trước khi tốn công chạy 40 arm còn lại.
2. E1 tách hai cổng: **E1a** chọn cách xử lý description (T0–T3); **E1b** thêm từ vựng con `R` và lọc câu `DF` lên **base thắng của E1a**. Bản trước dựng T4 cố định trên T3, nên nếu tóm tắt LLM (T3) thua thì lợi ích của từ vựng phòng không bao giờ được đo.
3. `parent` ghi bằng tham chiếu `@<cổng>` thay cho "★".

---

## 1. Bảng tổng

| id | Cổng | parent | Đổi đúng một thứ | Collection mới? | Đo chính | Bắt buộc |
|---|---|---|---|---|---|---|
| **B0** | B0 | — | Mốc: `T3+R` · cohere-v3 · dense-only · không filter | có | mọi metric | ✔ |
| **E1.T0** | E1a | B0 | text = description gốc | có | Recall/nDCG theo slice | ✔ |
| **E1.T1** | E1a | B0 | text = template attributes, không description | có | như trên | ✔ |
| **E1.T2** | E1a | E1.T1 | + description gốc ≤ 60 từ (chỉ khi không derived) | có | audience_style | ✔ |
| **E1.T3** | E1a | E1.T1 | + tóm tắt LLM từ attributes (khi derived) | có | audience_style, hub | ✔ |
| **E1.T4** | E1b | `@E1a` | + từ vựng hạng phòng / hãng bay / BOM combo (`@E1a+R`) | = B0 nếu E1a chọn T3 | parent_child | ✔ |
| **E1.T5** | E1b | `@E1a` | + từ vựng con và − câu có DF > 20 sản phẩm (`@E1a+R+DF`) | có | hub_score, nDCG | ✔ |
| **E1.T6** | SAN | B0 | B0 viết dạng `key: value` (control, `T3+R+KV`) | có | phải **giảm** | ✔ |
| **E1.T7** | SAN | B0 | B0 + giá / review / toạ độ (control, `T3+R+NUM`) | có | phải **giảm** | ✔ |
| **E2.v4** | E2 | `@E4` | model `embed-v4.0` 1024-d | có | nDCG × latency | ✔ |
| **E2.bge** | E2 | `@E4` | model `bge-m3` local | có | no_diacritics, audience | ✔ |
| **E2.gte** | E2 | `@E4` | model `gte-multilingual-base` local | có | như trên | tuỳ chọn |
| **E3** | SAN | B0 | query embed bằng `search_document` (sai cố ý) | không | phải **giảm** | ✔ |
| **E4.w30** | E4 | `@E1b` | description ≤ 30 từ | có | audience, hub | ✔ |
| **E4.w150** | E4 | `@E1b` | description ≤ 150 từ | có | như trên | ✔ |
| **E4.full** | E4 | `@E1b` | description không cắt | có | như trên + token gate | ✔ |
| **E5.doc** | E5 | `@E2` | + `query_vec` (synthetic, embed `document`) | collection phụ | audience, abbrev | ✔ |
| **E5.qry** | E5 | `@E2` | + `query_vec` (synthetic, embed `query`) | collection phụ | như trên | ✔ |
| **E6** | E6 | `@E2` | `embedding_types = int8` | có | Δ ≈ 0 | ✔ |
| **S0** | S0 | `@E2` | dense-only trên text + model đã chốt | = collection của `@E2` | mốc chiều 2 | ✔ |
| **S1.word** | S1 | S0 | BM25-only, `tokenization = word` | không | named_entity, no_diacritics | ✔ |
| **S1.whitespace** | S1 | S0 | BM25-only, `tokenization = whitespace` | không | như trên | ✔ |
| **S1.k1b** | S1 | S1.word | BM25 `k1 ∈ {0.9, 1.2, 1.5}`, `b ∈ {0.5, 0.75}` | không | như trên | tuỳ chọn |
| **S2.ranked** | S2 | `@S1` | hybrid, fusion RRF (`RANKED`) | không | toàn bộ | ✔ |
| **S2.rs_a03** | S2 | `@S1` | hybrid `RELATIVE_SCORE`, α = 0,3 | không | toàn bộ | ✔ |
| **S2.rs_a05** | S2 | `@S1` | hybrid `RELATIVE_SCORE`, α = 0,5 | không | toàn bộ | ✔ |
| **S2.rs_a07** | S2 | `@S1` | hybrid `RELATIVE_SCORE`, α = 0,7 | không | toàn bộ | ✔ |
| **S3** | S3 | `@S2` | + QU rule: filter destination / taxonomy / giá / sao / khách | không | multi_constraint, constraint precision, QU exact-match | ✔ |
| **S4a** | S4 | `@S3` | amenity `must` = filter `contains_all` | không | amenity_*, filter_recall_loss | ✔ |
| **S4b** | S4 | `@S3` | amenity `must` = boost mạnh, `nice` = +w, không phạt | không | amenity_* | ✔ |
| **S5** | S5 | `@S4` | + dedupe ≤ 1 / `parent_product_id` | không | parent_dup_rate | ✔ |
| **S6** | S6 | `@S5` | + alias + SymSpell trên query | không | abbrev_typo, no_diacritics | ✔ |
| **S7** | S7 | `@S6` | cutoff `max_vector_distance` sweep | không | zero-result in/out | ✔ |
| **S8** | S8 | `@S9` | + `rerank-v3.5` top-25 | không | Δ nDCG vs +latency, $ | ✔ |
| **S9** | S9 | `@S7` | + CSLS rescoring top-50 ở app | không | hub_score, nDCG | tuỳ chọn |
| **S10** | S10 (tắt) | `@S7` | + `attribute_vector` riêng, fusion | có | amenity_* | giai đoạn 3 |
| **F1** | F1 | `@S9` | BM25-only khi embed timeout (`degraded`) | không | nDCG của fallback | ✔ |
| **P1** | Pa | `@S0` | luồng: text + model đã chốt, dense-only | — | bảng cuối | ✔ |
| **P2** | Pa | `@S9` | luồng: đủ pipeline S1→S7 (→S9), không vector phụ, không rerank | — | bảng cuối | ✔ |
| **P3** | Pa | P2 | luồng: P2 + `query_vec` chế độ `@E5` | — | bảng cuối | ✔ |
| **P4** | Pb | `@Pa` | luồng: `@Pa` với cohere-v4, cutoff sweep lại | — | bảng cuối | ✔ |
| **P5** | Pb | `@Pa` | luồng: `@Pa` với bge-m3, cutoff sweep lại | — | bảng cuối | ✔ |
| **P6** | Pc | `@best(Pa, Pb)` | luồng tốt nhất của Pa/Pb + `rerank-v3.5` | — | bảng cuối | ✔ |

`@<cổng>` = arm được promote ở cổng đó (ví dụ `@E1a` = text base thắng E1a; `@S4` = cách xử lý amenity thắng S4). `arms/*.yaml` ghi đúng tham chiếu này; giá trị thật giải lúc chạy từ `state/promotions.yaml` (spec Part 12) — `sb list-arms --resolved` in ra. Cột **Cổng** là cổng mà arm thuộc về; thứ tự cổng ở §3.

---

## 2. Từng arm làm gì — có ví dụ

### B0 — mốc

`embed_text` `T3+R` (= `build_text` production của backend, `catalog-text-v2` — chốt 24/09, xem spec §1.1), Cohere v3, `near_vector` top-10, không filter, không preproc. Mọi Δ về sau so với đây hoặc với parent gần nhất.

**q1** → embed câu không dấu → cosine với 5.000 vector → top-10. Kỳ vọng thấy resort Nha Trang lẫn vài resort nơi khác (không có filter).
**q5** → vẫn trả 10 kết quả (chưa có cutoff) — đây là lỗi mà S7 sửa.

---

### Nhóm E1 — text builder (chỉ đổi cái được embed)

**E1.T0 — description gốc.** Embed nguyên đoạn mô tả từ nguồn (trung vị 921 ký tự với khách sạn).

> *Vinpearl Resort Nha Trang tọa lạc trên đảo Hòn Tre thơ mộng, nơi giao hòa giữa biển xanh cát trắng… Với hệ thống nhà hàng đẳng cấp quốc tế, spa thư giãn, hồ bơi ngoài trời, Wi-Fi miễn phí toàn khu, lễ tân 24 giờ, bãi đỗ xe rộng rãi… Chính sách nhận phòng từ 14:00, trả phòng trước 12:00. Giá phòng từ 2.800.000đ…* (≈ 350 từ)

Đo: baseline "hiện trạng". Kỳ vọng: tốt ở audience_style (văn tự nhiên) nhưng `hub_score` cao vì 57,5% mô tả là template, và q2/q7-kiểu-giá bị nhiễu bởi số.

**E1.T1 — template attributes, không description.**

> *Vinpearl Resort Nha Trang là khu nghỉ dưỡng 5 sao tại Nha Trang, Khánh Hòa, phù hợp gia đình có trẻ nhỏ. Nổi bật với bãi biển riêng, hồ bơi, công viên nước, spa, club trẻ em, buffet sáng.*

Đo: giá trị thuần của attributes. Kỳ vọng: dest_type và amenity tăng so với T0; audience_style có thể giảm vì mất synonym tự nhiên.

**E1.T2 — T1 + description gốc ≤ 60 từ (chỉ item không derived).** Với item có `descriptionSource` (derived) thì text = T1. Với item có mô tả thật: T1 + 60 từ đầu của mô tả.

> *…buffet sáng. Tọa lạc trên đảo Hòn Tre thơ mộng, nơi giao hòa giữa biển xanh cát trắng, resort mang đến kỳ nghỉ trọn vẹn cho gia đình…*

Đo: mô tả người viết có thêm gì ngoài attributes không.

**E1.T3 — T1 + tóm tắt LLM chỉ từ attributes (item derived).** LLM nhận đúng JSON attributes, prompt cấm thêm sự kiện, 2–3 câu.

> *…buffet sáng. Không gian nghỉ dưỡng hướng đến gia đình có con nhỏ, thuận tiện kết hợp vui chơi tại công viên nước và thư giãn bên biển riêng.*

Đo: LLM có tạo ra synonym/intent giúp match q1-kiểu-audience mà không bịa không. So T3 với T2 trả lời câu "template hay LLM".

**E1.T4 — `@E1a` + từ vựng con (`R`).** Hotel: ≤ 8 hạng phòng khử trùng; flight_route: hãng + "bay thẳng"; combo: một câu tổng hợp BOM. Ví dụ dưới giả sử E1a chọn T3.

> *…bên biển riêng. Có các lựa chọn phòng Deluxe hướng biển, Suite gia đình, Villa hồ bơi riêng.*

Đo: **q4** "villa hồ bơi riêng Phú Quốc" phải ra property (không phải phòng — phòng không có vector). Kỳ vọng parent_child tăng rõ. Nếu E1a chọn T3 thì E1.T4 = B0 (`T3+R`) và dùng lại collection của B0.

**E1.T5 — `@E1a` + `R` + `DF`.** Tính document frequency theo câu chuẩn hoá trên toàn catalog; câu xuất hiện ở > 20 sản phẩm bị bỏ.

Ví dụ câu bị loại: *"Khách sạn cung cấp dịch vụ lễ tân 24 giờ và Wi-Fi miễn phí."* (có ở 300+ item). Câu giữ: *"Có công viên nước và club trẻ em."*

Đo: `hub_score_max` giảm (mục tiêu < 3), nDCG không giảm. Nếu T4 đã có hub < 3 thì T5 là TIE → chọn T4 (ít bước hơn).

**E1.T6 — control `key: value`** (cổng SAN, so với B0).

> *name: Vinpearl Resort Nha Trang; type: resort; star: 5; destination: Nha Trang; family_friendly: true; amenities: private_beach, pool, water_park, spa, kids_club; rooms: deluxe_ocean_view, family_suite, villa_private_pool*

Đo: phải **thua** B0 (Tereshin: −19% Recall@10 khi để dạng JSON). Không thua → cảnh báo mềm ở cổng SAN, người xem rồi `sb ack` kèm ghi chú.

**E1.T7 — control có số** (cổng SAN, so với B0).

> *…Villa hồ bơi riêng. Giá từ 2.800.000 đồng một đêm, điểm đánh giá 8,9 trên 10, tọa độ 12,21 N 109,24 E.*

Đo: phải **thua** hoặc ngang B0, và q2 (dưới 3 triệu) không được tốt lên — chứng minh số phải ở filter.

---

### Nhóm E2 — model (cùng text, đổi model)

**E2.v4 — `embed-v4.0`, `output_dimension = 1024`.** Cùng `embed_text` thắng E1. Đo nDCG@10 × latency; v4 có context 128k nên E4.full có thể chạy lại trên v4 nếu v3 bị gate 512 token.

**E2.bge — `bge-m3` local, không prefix.** Đối chứng model mở có số VN-MTEB. Đây là arm trả lời "Cohere có tốt cho tiếng Việt của mình không". **q1** (không dấu) và slice audience là chỗ hai model có thể khác nhau nhiều nhất.

**E2.gte — `gte-multilingual-base` (tuỳ chọn).** 305M, rẻ hơn bge-m3; chỉ chạy nếu còn thời gian máy.

---

### E3 — sanity `input_type`

Chạy ở cổng **SAN** ngay sau B0, so với B0. Query embed bằng `search_document` thay vì `search_query`. Hai lớp kiểm tra:

- **Cứng:** embed 200 query gold theo hai cách; nếu vector giống hệt nhau thì `input_type` không tới API (hoặc cache trả vector cũ) → lỗi pipeline, chuỗi dừng cho tới khi sửa.
- **Mềm:** vector khác nhau nhưng nDCG **không giảm** → có thể Cohere v3 ít nhạy với `input_type` trên dữ liệu này; cổng dừng ở cảnh báo, người xem rồi `sb ack SAN --note "…"` để đi tiếp.

Tách hai lớp để không chặn nhầm cả chuỗi chỉ vì model thật sự ít nhạy.

---

### Nhóm E4 — độ dài description trong text

`E4.w30` / `E4.w150` / `E4.full`; w60 là mặc định, chính là `@E1b`. Cả cổng bị bỏ qua nếu E1a chọn T1 (không có description). Với E4.full, `sb tokens` sẽ báo item > 512 token → arm này chỉ chạy được nếu bỏ các item đó (ghi số bị bỏ) hoặc chạy trên v4.

Ví dụ E4.full với item T0 dài 350 từ: text ≈ T1 + 350 từ → vector "mờ", hub tăng. Ví dụ E4.w30: chỉ *"Không gian nghỉ dưỡng hướng đến gia đình có con nhỏ, thuận tiện kết hợp vui chơi tại công viên nước…"* (cắt tại 30 từ).

Đo: đường cong nDCG theo độ dài; chọn điểm gãy.

---

### Nhóm E5 — vector phụ synthetic query

Mỗi search unit có 6–10 query sinh sẵn, đã lọc bằng reranker (giữ query mà sản phẩm gốc lọt top-3). Ví dụ query giữ lại cho Vinpearl Resort Nha Trang:

> *resort cho gia đình ở Nha Trang* · *nghỉ dưỡng biển có công viên nước cho trẻ* · *villa co ho boi rieng nha trang* · *KDL 5 sao NT*

Retrieve: dense `content` top-50 ∪ `query_vec` top-50 (gộp max theo product) → RRF.

**E5.doc** embed các query này với `input_type = document` (chúng đại diện cho tài liệu). **E5.qry** embed với `input_type = query` (cùng không gian với query thật). Không có bằng chứng sẵn cho lựa chọn nào → chạy cả hai. Đo: **q1**, slice abbrev, audience — kỳ vọng tăng vì có sẵn cách diễn đạt của khách.

---

### E6 — `int8`

Cohere trả `embedding_types = int8`, cast về float trước khi nạp. Kỳ vọng Δ ≈ 0; nếu ≈ 0 thì về sau nén được ở API mà không cần quantization của Weaviate.

---

### Nhóm S — retrieval (text + model đã chốt)

**S0 — dense-only.** = `@E2` chạy lại làm mốc chiều 2.

**S1.word / S1.whitespace — BM25-only.** Tiếng Việt viết cách theo âm tiết nên `word` và `whitespace` cho token gần giống; khác nhau ở dấu câu và ký tự đặc biệt.

**q3** "VinWonders": BM25 match chính xác tên → top-1; dense một mình có thể xếp VinWonders sau "công viên giải trí" khác. **q1** không dấu: match nhờ `ascii_fold` (analyzer) hoặc property `*_ascii` (shadow) — nếu S1 thua ở q1-kiểu thì fold dấu chưa chạy.

**S1.k1b (tuỳ chọn)** — grid nhỏ `k1`/`b`. Chỉ khi S1.word thua dense ở named_entity một cách khó hiểu.

**S2.ranked — hybrid RRF.** `fusion_type = RANKED`, k = 60 (server). Kết quả = xếp hạng theo `1/(60+rank_dense) + 1/(60+rank_bm25)`. Ví dụ **q3**: VinWonders rank 1 BM25, rank 4 dense → vẫn top-1.

**S2.rs_a03 / a05 / a07 — hybrid relativeScore.** Điểm = α·dense_norm + (1−α)·bm25_norm. α = 0,3 nghiêng lexical (tốt cho tên riêng, kém cho audience), 0,7 nghiêng dense. Đo toàn bộ, chọn fusion thắng.

**S3 — QU filter.** Query → `qu()` → filter cứng + `semantic_text`.

**q2** `KS 5 sao PQ có kids club dưới 3 triệu cho 4 người` →
`{destination: "Phú Quốc", taxonomy: hotel_property, star_min: 5, price_max: 3000000, pax: 4, amenity_nice: [kids_club], semantic_text: "khách sạn 5 sao Phú Quốc có kids club"}` → Weaviate `filters = destination == "Phú Quốc" AND taxonomy == hotel_property AND star_rating >= 5 AND unit_price_min <= 3000000` → hybrid trên tập lọc.

Đo: constraint precision (≥ 95%), **QU exact-match rate** theo trường trên slice multi_constraint. Ở S3 amenity chưa lọc (chỉ vào semantic_text).

**S4a — amenity `must` = filter.** Khi khách bấm checkbox hoặc câu có "phải có / bắt buộc": `contains_all(amenity_ids, [kids_club])`. Sản phẩm không ghi nhận kids club bị loại — kể cả có thật mà nguồn không liệt kê. Đo thêm `filter_recall_loss`: số cặp đúng trong gold bị filter loại.

**S4b — amenity `must` = boost.** Không lọc; sản phẩm có `kids_club` +w lớn, `nice` +w nhỏ, không ghi nhận = 0 (không phạt). Đo cùng slice; chọn theo Recall@10 + constraint precision. Với q2 (amenity chỉ nhắc trong câu, không bấm checkbox) cả hai arm đều xử lý như `nice`.

**q6** `khách sạn Đà Nẵng không có hồ bơi` (cả S4a/S4b): `amenity_not: [pool]` → `NOT contains_any(amenity_ids, [pool])`. Kết quả: khách sạn không **ghi nhận** hồ bơi. Metric phủ định = 0 kết quả có `pool = true`; không cam kết "chắc chắn không có".

**S5 — dedupe theo cha.** Lấy top-30, giữ ≤ 1 / `parent_product_id`, cắt 10. Với catalog hiện tại search unit = property nên dup theo cha hiếm; arm này bảo vệ khi sau này room/flight thành search unit. Đo `parent_dup_rate ≤ 1`.

**S6 — alias + SymSpell.** Trước QU: `KS→khách sạn, PQ→Phú Quốc, NT→Nha Trang, VW→VinWonders, tr→triệu`; SymSpell sửa token không có trong từ điển: `Vinpeal→Vinpearl`, `nha trng→nha trang`. Log `applied_aliases`, `corrections`. Đo abbrev_typo, no_diacritics — đây là arm bù cho việc mất `pg_trgm` khi rời Postgres.

**S7 — cutoff.** Sweep `max_vector_distance ∈ {0.30 … 0.60, bước 0.02}` (distance = 1 − cosine). Chọn giá trị: **q5** `resort ở Sapa` → 0 kết quả (out_of_catalog = 100%), đồng thời zero-result trong catalog < 2%. Hit BM25 (tên riêng) giữ lại kể cả dưới cutoff. Ghi `cutoff.source = CALIBRATED_<date>`.

**S8 — rerank.** Top-25 sau S7 → `rerank-v3.5` → top-10. Đo Δ nDCG, +latency (một lượt gọi mạng nữa), $2/1.000 query. Chỉ giữ nếu Δ ≥ 3 điểm và p95 vẫn ≤ 250 ms (NFR-PERF-01).

**S9 — CSLS (tuỳ chọn).** Trên top-50 dense: `score' = 2·cos(q,d) − r_d`, với `r_d` = cosine trung bình của d tới 10 láng giềng gần nhất (tính trước, một lần). Sản phẩm "hub" (gần mọi thứ) bị trừ điểm. Chỉ chạy nếu sau T5 `hub_score_max` vẫn > 3.

**S10 — attribute_vector (giai đoạn 3, không chạy tuần này).** Named vector thứ hai embed câu *"Tiện ích: bãi biển riêng, hồ bơi, công viên nước…"*; fusion với `content`. Chỉ cân nhắc nếu sau S4 slice amenity vẫn thua rõ — HyST cho thấy phần lớn lợi ích đến từ filter.

**F1 — fallback.** Mô phỏng Cohere timeout > 150 ms: chạy BM25-only + QU filter trên toàn gold. Số này cho biết "khi API chậm, khách mất bao nhiêu chất lượng" — đưa vào ngân sách P99.

---

### Nhóm P — luồng end-to-end cho bảng cuối

Mỗi P là một YAML `composite: true`, gộp các arm thắng. Chạy lại từ đầu trên gold (không lấy số cũ ghép) để bảng cuối nhất quán.

| Luồng | Gồm | Trả lời câu hỏi |
|---|---|---|
| P1 | `@S0`: text + model đã chốt, dense-only | "Nếu chỉ vector thì được bao nhiêu?" |
| P2 | `@S9`: text + model + fusion `@S2` + QU + amenity `@S4` + dedupe + alias/SymSpell + cutoff (+ CSLS nếu S9 chạy) | Luồng production đề xuất |
| P3 | P2 + `query_vec` chế độ `@E5` | Vector phụ có đáng thêm một pipeline không |
| P4 | `@Pa` (thắng giữa P2/P3) với cohere-v4, cutoff sweep lại cho v4 | v4 có đáng đổi không |
| P5 | `@Pa` với bge-m3 local, cutoff sweep lại cho bge-m3 | Model mở có thắng trên tiếng Việt của mình không |
| P6 | tốt nhất của Pa/Pb + `rerank-v3.5` top-25 | Rerank có đáng $ và latency không |

Cutoff (`max_vector_distance`) phụ thuộc phân bố cosine của từng model, nên P4/P5 **không** dùng lại cutoff đã chọn cho Cohere v3 mà sweep lại theo đúng quy tắc S7. Nếu `@Pa` đã dùng đúng model của P4 hoặc P5 (ví dụ cổng E2 đã đổi sang v4), arm đó bị bỏ qua vì trùng.

Ví dụ một dòng bảng cuối (minh hoạ định dạng, không phải số): `P2 | 0,74 | 0,61 | 0,66 | no_diacritics (−4,1) | 0,97 | 0,3 | 0,01 / 1,00 | 240 ms | 95 ms | $0,11 | 5`.

---

## 3. Thứ tự chạy và điểm chốt

```
B0 → SAN ─┬─ (E3, T6, T7 so với B0; hỏng cứng → dừng)
          └→ E1a ─chốt base─→ E1b ─chốt R/DF─→ E4 ─chốt độ dài─→ E2 ─chốt model─→ E6 (info) → E5 ─chốt chế độ query_vec─→
S0 → S1 ─chốt BM25─→ S2 ─chốt fusion─→ S3 → S4 ─chốt amenity─→ S5 → S6 → S7 ─chốt cutoff─→ S9 (nếu hub > 3) → S8 (info) → F1 (info) →
Pa (P1, P2, P3) → Pb (P4, P5) → Pc (P6) → FINAL (người ký)
```

Mỗi cổng: chạy hết arm của cổng → `select()` đề xuất (cùng quy tắc với bảng cuối: guard → nDCG@10 cao nhất → TIE thì chọn ứng viên đơn giản hơn) → promote bằng tay hoặc `--auto-promote`. Promote ghi vào `state/promotions.yaml`; arm ở cổng sau đọc tham chiếu `@<cổng>` từ file đó, không ai phải sửa YAML bằng tay. Ba cổng luôn cần người: **SAN** khi có cảnh báo mềm, **E2** khi đề xuất đổi khỏi Cohere v3 (quyết định của team 23/09), và **FINAL**.

Trước khi promote, nếu arm nào trong cổng có `judged@10 < 0,80` (hoặc slice < 0,70) thì cổng dừng ở `NEEDS_LABELS`: chạy `sb gold holes --stage <cổng>`, gán nhãn các sản phẩm mới lọt top-10, tag gold version mới, `sb rescore`, rồi cổng tự tính lại. Chi tiết: spec Part 11–12.
