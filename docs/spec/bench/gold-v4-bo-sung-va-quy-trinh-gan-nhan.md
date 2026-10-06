# Bổ sung Gold Set v4 và quy trình gán nhãn

- Phục vụ: **FR-SRC-01**, **FR-SRC-03**, **FR-SRC-04**, **AC-SRC-01** (`docs/prd/requirements.md`) và test-plan §2.5 (`docs/prd/test-plan.md`).
- Trạng thái (05/10, người dùng chốt — `docs/plan/2026-10-05-gold-v4a-mo-rong.md` §12):
  - **Rubric §4 áp dụng cho mọi nhãn gán từ `gold_v4` trở đi** — câu mới và hole của câu cũ (D1; mở rộng 06/10 sau khi người dùng soát hole D9a). Bản thi hành: `docs/spec/bench/gold-guide.md` mục "Rubric v4" (kèm quy ước #8–#14 và chính sách từng câu). Nhãn đã có trong `gold_v1`–`gold_v3` giữ nguyên (gold chỉ được thêm).
  - Slice mới: chỉ `taxonomy_collision`, `flight_direction` (§14). Các slice khác của §5 gộp vào slice v3 có sẵn hoặc để sau.
  - Guard và luật WIN ở §7, ngưỡng ở §7 / §9: **chỉ báo cáo**, WIN vẫn tính trên câu `gold_v3` (D7). Chưa cài trong đợt này.
  - Một người gán (QAnh) và cho phép nhãn máy cả 1 / 2, người duyệt (D5, D6) — lệch có chủ đích so với §8.6, §9.1, §10, §13 #3–#4.
  - Câu "parse và filter trước retrieval" ở §1 là **giả thuyết bench** (D12): đo trên bench trước, đổi `/search` production sau và phải qua đề xuất `docs/prd/update/`.

## 1. Mục tiêu

Gold v3 hiện đã có nền tốt: pooling, `judgments` 0/1/2, `filter`, `child_filter`, `expected_children`, `expected_no_result`, provenance, Full/Condensed scoring và paired bootstrap.

Gold v4 **không thay cấu trúc cũ**. Mục tiêu là bổ sung khả năng đánh giá các lỗi production mà metric relevance trung bình có thể che mất:

- Query không dấu, alias, viết tắt và sai chính tả.
- Phủ định, bao gồm/loại trừ, điều kiện số học.
- Lẫn taxonomy: golf, golf voucher, VinWonders/attraction ticket, hotel/room/combo.
- Flight route có chiều: origin, destination, “từ”, “đến”, “ra”, “vào”, “về”.
- Query trong catalog nhưng không có kết quả phù hợp và query ngoài catalog.

Nguyên tắc **khi chấm nhãn**: semantic relevance là tín hiệu mềm; taxonomy, route, destination, phủ định và các thuộc tính cấu trúc là ràng buộc cứng. **Giả thuyết bench** (chưa phải hành vi `/search`): parse các constraint này và filter trước retrieval sẽ tốt hơn giao hoàn toàn cho embedding — kiểm bằng arm S3/S4 (`docs/spec/bench/arms.md`). Hợp đồng search hiện tại (§2.2 "bước 2") chưa tách constraint thành filter; đưa vào production cần đề xuất `docs/prd/update/` (D12).

---

## 2. Giữ nguyên schema cũ

Một query hiện có dạng:

```json
{
  "qid": "c0481",
  "slice": "multi_constraint",
  "status": "active",
  "text": "khách sạn 5 sao ở Hà Tĩnh dưới 2 triệu",
  "filter": {
    "and": [
      {"eq": ["destination", "Hà Tĩnh"]},
      {"eq": ["variant", "hotel_property"]},
      {"gte": ["star_rating", 5]}
    ]
  },
  "child_filter": {"lte": ["unit_price", 2000000]},
  "expected_no_result": false,
  "expected_children": {},
  "judgments": {
    "<productId>": 2,
    "<productId>": 0,
    "<productId>": 1
  },
  "provenance": {
    "<productId>": "pool@gold_v1",
    "<productId>": "holes:D5a@gold_v3"
  }
}
```

Tiếp tục giữ:

- `judgments`: nhãn relevance parent product 0/1/2.
- `filter`, `child_filter`: điều kiện cứng có thể machine-check.
- `expected_children`: kết quả child/room phù hợp.
- `expected_no_result`: query đúng là không có kết quả.
- `provenance`: nguồn pool hoặc hole batch.
- `per_query.parquet.top_ids`: để rescore khi gold có label mới.
- Recall@5/10, nDCG@10, MRR@10, Judged@10, Full/Condensed và paired bootstrap.

---

## 3. Schema bổ sung (optional)

Các trường dưới đây là optional để không phá gold/evaluator hiện tại.

```json
{
  "canonical_text": "voucher golf Hội An",
  "equivalence_group": "golf_voucher_hoi_an_01",
  "query_variants": [
    "voucher golf Hội An",
    "voucher golf hoi an",
    "voucer golf hoi an",
    "voucher gofl hoi an"
  ],
  "expected_intent": {
    "intent": "catalog_search",
    "vertical": ["golf"],
    "product_kind": ["voucher"],
    "destination": "Hội An"
  },
  "expected_parse": {
    "origin": null,
    "destination": "Hội An",
    "negation_scope": null
  },
  "forbidden": {
    "taxonomy": ["vinwonders_ticket", "attraction_ticket"],
    "product_ids": ["<optional-product-id>"],
    "attributes": [
      {"eq": ["has_golf", true]}
    ],
    "reason": "optional audit description"
  },
  "soft_preferences": [
    {"field": "beachfront", "mode": "do_not_require"}
  ],
  "label_policy": {
    "2": "Exact intent and every hard constraint are satisfied",
    "1": "Useful partial alternative under the stated policy",
    "0": "Hard-constraint violation, wrong core taxonomy, wrong destination, or irrelevant"
  }
}
```

### Ý nghĩa

| Field | Mục đích |
|---|---|
| `canonical_text` | Câu chuẩn có dấu/đúng chính tả, dùng để gom các variant cùng intent |
| `equivalence_group` | Nhóm canonical, không dấu, alias và typo; bootstrap theo nhóm thay vì coi variant là độc lập |
| `query_variants` | Các realization cùng intent cần kiểm tra robustness |
| `expected_intent` | Chuẩn để chấm query understanding: intent, vertical, subtype, destination |
| `expected_parse` | Slot có vai trò, đặc biệt origin/destination của flight và scope phủ định |
| `forbidden` | Product/taxonomy/attribute không được xuất hiện ở top-k |
| `soft_preferences` | Những điều không bắt buộc; tránh biến mọi câu chứa “không” thành `must_not` |
| `label_policy` | Quy ước cục bộ của query khi distinction 1 vs 2 có thể gây tranh cãi |

---

## 4. Quy tắc gán nhãn 0/1/2

### 4.1 Định nghĩa chuẩn

| Nhãn | Quy tắc |
|---:|---|
| **2** | Đúng sản phẩm khách tìm: đúng core intent, destination/entity bắt buộc, taxonomy/subtype bắt buộc và mọi hard constraint có thể chấm |
| **1** | Có ích một phần: gần intent nhưng thiếu hoặc sai một điều kiện mềm; hoặc là alternative được cho phép rõ trong `label_policy` |
| **0** | Không liên quan hoặc vi phạm hard constraint: sai destination, sai chiều route, sai core taxonomy, sai brand exclusion, vi phạm phủ định/giá/sao/availability |

### 4.2 Thứ tự quyết định label

1. Kiểm tra product có trong benchmark scope và search-able hay không.
2. Kiểm tra mọi hard constraint: destination, variant/taxonomy, route direction, price, star, availability, `must_not`.
3. Nếu có hard violation, gán **0**; semantic similarity không thể bù cho hard violation.
4. Nếu pass hard constraints, xét core intent và subtype.
5. Nếu exact intent, gán **2**.
6. Nếu là alternative có ích theo `label_policy`, gán **1**.
7. Nếu không chắc hoặc metadata thiếu, gán trạng thái review; không tự nâng lên 2.

### 4.3 Ví dụ: `voucher golf Hội An`

| Product | Facts | Final label | Lý do |
|---|---|---:|---|
| Golf voucher tại Hội An | Golf + voucher + Hội An | 2 | Exact intent |
| Green fee/tee time tại Hội An | Golf + Hội An, không phải voucher | 1 hoặc 0 | Chốt trước trong `label_policy`: có coi là alternative hợp lệ không |
| Combo golf + resort Hội An | Combo có golf | 1 hoặc 0 | Tuỳ UX: query có chấp nhận package thay standalone voucher không |
| Voucher khách sạn Hội An | Hotel voucher | 0 | Sai core taxonomy |
| Vé VinWonders Nam Hội An | Attraction ticket | 0 | Forbidden taxonomy |
| Golf voucher Nha Trang | Golf voucher, sai destination | 0 | Hard destination violation |
| Resort gần sân golf Hội An | Hotel property | 0 | Query là transactional golf voucher |

### 4.4 Ví dụ: phủ định

Query: `resort Nha Trang không có sân golf`

- Resort Nha Trang, `has_golf=false` → 2 nếu các điều kiện chính khác phù hợp.
- Resort Nha Trang, `has_golf=true` → 0, dù mô tả rất gần nghĩa.
- Resort Phú Quốc, `has_golf=false` → 0 vì sai destination.

Query: `villa có hồ bơi riêng, không cần gần biển`

- Villa có hồ bơi riêng và gần biển → không bị loại chỉ vì gần biển.
- “Không cần gần biển” là `soft_preference/do_not_require`, không phải `must_not beachfront=true`.

### 4.5 Ví dụ: flight direction

Query: `vé máy bay từ Hà Nội vào Đà Nẵng`

- Route Hà Nội → Đà Nẵng → 2.
- Route Đà Nẵng → Hà Nội → 0, không phải 1.
- Route Hà Nội → Phú Quốc → 0.
- Query `bay đến Đà Nẵng` chỉ có destination: không tự bịa origin; chấm slot destination và xử lý theo UX discovery/clarification đã chốt.

---

## 5. Slice mới cần bổ sung

| Slice | Mục tiêu | Quy mô canonical đề xuất | Guard trọng tâm |
|---|---|---:|---|
| `no_diacritic` | Không dấu | 15–20 | Variant pass, taxonomy accuracy |
| `alias_abbreviation` | `vw`, `vp`, `pq`, `nt`, `ks` | 12–15 | Entity resolution |
| `typo` | Lỗi mobile, sai 1–2 ký tự, tách/ghép | 20–25 | Variant pass, Forbidden@10 |
| `negation_hard` | `không có`, `không gồm`, `không phải`, `trừ` | 15–20 | Negation violation = 0% |
| `negation_soft` | `không cần`, `không nhất thiết` | 8–10 | Không loại oan |
| `taxonomy_collision` | Golf/voucher/VinWonders/ticket/hotel | 20–25 | Top-1 taxonomy, Forbidden@10 |
| `flight_direction` | Origin–destination có chiều | 20–25 | Direction accuracy = 100% |
| `flight_partial_route` | Chỉ origin hoặc destination | 10–12 | Slot-level accuracy, không bịa slot |
| `out_of_catalog` | Intent hợp lệ nhưng catalog không có | 8–10 | No-result correctness |
| `mixed_constraints` | Nhiều constraint kết hợp | 15–20 | Filter pass, forbidden rate |

Không cần thêm toàn bộ ngay. Đợt `gold_v4a` ưu tiên 70–90 canonical query thuộc `no_diacritic`, `typo`, `negation_hard`, `taxonomy_collision`, `flight_direction` và một số `out_of_catalog`.

---

## 6. Ví dụ record Gold v4

### 6.1 Taxonomy collision + không dấu

```json
{
  "qid": "tx_001",
  "slice": "taxonomy_collision",
  "status": "active",
  "text": "voucher golf Hoi An",
  "canonical_text": "voucher golf Hội An",
  "equivalence_group": "golf_voucher_hoi_an_01",
  "query_variants": [
    "voucher golf Hội An",
    "voucher golf hoi an",
    "voucer golf hoi an",
    "voucher gofl hoi an"
  ],
  "filter": {
    "and": [
      {"eq": ["destination", "Hội An"]},
      {"eq": ["vertical", "golf"]},
      {"eq": ["product_kind", "voucher"]}
    ]
  },
  "expected_intent": {
    "intent": "catalog_search",
    "vertical": ["golf"],
    "product_kind": ["voucher"],
    "destination": "Hội An"
  },
  "forbidden": {
    "taxonomy": ["vinwonders_ticket", "attraction_ticket"]
  },
  "expected_no_result": false,
  "judgments": {
    "<golfVoucherHoiAn1>": 2,
    "<golfTeeTimeHoiAn1>": 1,
    "<vinWondersHoiAn1>": 0
  },
  "provenance": {
    "<golfVoucherHoiAn1>": "pool@gold_v4a",
    "<golfTeeTimeHoiAn1>": "adversarial@taxonomy_collision_v1",
    "<vinWondersHoiAn1>": "adversarial@taxonomy_collision_v1"
  }
}
```

### 6.2 Phủ định hard

```json
{
  "qid": "neg_003",
  "slice": "negation_hard",
  "status": "active",
  "text": "resort Nha Trang không có sân golf",
  "filter": {
    "and": [
      {"eq": ["destination", "Nha Trang"]},
      {"in": ["variant", ["hotel_property", "resort"]]},
      {"eq": ["has_golf", false]}
    ]
  },
  "expected_intent": {
    "intent": "hotel_search",
    "destination": "Nha Trang",
    "must_not": [{"field": "has_golf", "value": true}]
  },
  "forbidden": {
    "attributes": [{"eq": ["has_golf", true]}]
  },
  "expected_no_result": false,
  "judgments": {
    "<resortNoGolf1>": 2,
    "<resortNoGolf2>": 2,
    "<resortWithGolf1>": 0
  }
}
```

### 6.3 Flight route có chiều

```json
{
  "qid": "fl_001",
  "slice": "flight_direction",
  "status": "active",
  "text": "vé máy bay từ Hà Nội vào Đà Nẵng",
  "expected_parse": {
    "intent": "flight_search",
    "origin": "Hà Nội",
    "destination": "Đà Nẵng",
    "direction": "Hà Nội->Đà Nẵng",
    "trip_type": "one_way"
  },
  "filter": {
    "and": [
      {"eq": ["variant", "flight_route"]},
      {"eq": ["origin_city", "Hà Nội"]},
      {"eq": ["destination_city", "Đà Nẵng"]}
    ]
  },
  "forbidden": {
    "attributes": [
      {
        "and": [
          {"eq": ["origin_city", "Đà Nẵng"]},
          {"eq": ["destination_city", "Hà Nội"]}
        ]
      }
    ]
  },
  "expected_no_result": false,
  "judgments": {
    "<HAN_DAD_route>": 2,
    "<DAD_HAN_route>": 0
  }
}
```

---

## 7. Guard và scoring bổ sung

Giữ metric chính hiện tại:

- Recall@5/10 với relevance >= 1.
- nDCG@10 với gain `2^label - 1`.
- MRR@10 với label = 2.
- Judged@10.
- Full và Condensed scoring.
- Paired bootstrap 1.000 lượt trên cùng query/family.

Bổ sung các guard sau:

| Guard | Cách tính | Ngưỡng đề xuất |
|---|---|---:|
| `Forbidden@10` | Query có ít nhất một forbidden item trong top-10 | 0% cho safety slice |
| `Forbidden@3` | Query có forbidden item trong top-3 | 0% |
| `Top1 taxonomy accuracy` | Top-1 thuộc taxonomy hợp lệ | >= 98% ở taxonomy collision |
| `Top3 taxonomy purity` | Top-3 thuộc taxonomy hợp lệ | >= 95% |
| `Negation violation` | Top-k vi phạm `must_not` | 0% cho negation hard |
| `Direction accuracy` | Origin và destination đúng thứ tự | 100% cho explicit route |
| `Parse exact match` | All required slots đúng | >= 98%, tuỳ slice |
| `Variant constraint pass` | Variant không vi phạm filter/forbidden | >= 90–95% |
| `No-result correctness` | Query ngoài catalog không trả product | 100% trên explicit no-result |

### Quy tắc WIN bổ sung

Một arm không được WIN nếu có một trong các điều kiện sau:

- `Forbidden@10` tăng ở bất kỳ hard-constraint/safety slice nào.
- Direction accuracy dưới 100% ở `flight_direction` explicit.
- Filter pass rate giảm hơn 1 điểm.
- nDCG của một safety slice giảm quá 3 điểm.
- Query trong catalog trả rỗng vượt ngưỡng hiện hành.

### Query variant và bootstrap

Không coi canonical, không dấu, typo và alias của cùng một intent là các mẫu độc lập. Aggregate metric theo `equivalence_group` trước, sau đó paired bootstrap theo group/canonical intent.

Báo cáo thêm:

```text
RobustnessGap_nDCG = nDCG@10(canonical) - mean(nDCG@10(variants))
VariantConstraintPass = variants_without_filter_or_forbidden_violation / all_variants
```

---

## 8. Workflow gán nhãn

### 8.1 Nguyên tắc phân vai

| Thành phần | Vai trò | Không được làm |
|---|---|---|
| Rule/catalog | Chốt hard failure theo evidence schema | Không tự coi mọi item pass filter là label 2 |
| LLM | Pre-label, reason code, tìm ambiguity/metadata thiếu | Không là ground truth cuối; không bịa facts |
| Human domain reviewer | Chốt label 1/2, conflict, high-risk/safety cases | Không label khi thiếu product evidence |

Không cần label toàn bộ catalog. Dùng pooling: chỉ label union các sản phẩm lọt top-k từ nhiều arm, cộng adversarial candidates và hole candidates.

### 8.2 Bước 1 — Viết query spec trước khi pool

Mỗi query/family có một policy rõ ràng:

```json
{
  "qid": "tx_golf_hoi_an_001",
  "canonical_text": "voucher golf Hội An",
  "slice": "taxonomy_collision",
  "hard_constraints": {
    "destination": "Hội An",
    "vertical": "golf",
    "product_kind": "voucher"
  },
  "soft_preferences": [],
  "must_not": ["vinwonders_ticket", "attraction_ticket"],
  "label_policy": {
    "2": "golf voucher at Hội An",
    "1": "golf tee-time at Hội An if the UX treats it as an acceptable alternative",
    "0": "all attraction tickets, hotels, non-golf vouchers and wrong destinations"
  }
}
```

Chốt policy trước để annotator không tự diễn giải khác nhau theo từng batch.

### 8.3 Bước 2 — Pool candidate

Với mỗi canonical query/family, lấy union và dedupe từ:

- Dense-only top 20–30.
- BM25/lexical có dấu top 20–30.
- BM25/unaccent top 20–30.
- Alias-expanded lexical top 20–30.
- Trigram/fuzzy top 20–30 cho name/entity/typo.
- Hybrid/RRF baseline top 20–30.
- Arm filter-first/query-understanding mới.
- LLM rewrite/parser arm, nếu có.
- Random sample có điều kiện cùng destination hoặc taxonomy.
- Adversarial candidates: cùng destination/keyword nhưng sai taxonomy.
- Reverse route candidate với query flight.

Target sau dedupe:

| Slice | Pool mục tiêu/query |
|---|---:|
| Hotel/filter thông thường | 30–45 |
| Semantic/multi-constraint | 40–60 |
| No-diacritic/alias | 35–50 |
| Typo | 45–70 |
| Negation | 40–60 |
| Taxonomy collision | 45–70 |
| Flight direction | 20–40 |
| Out-of-catalog | 20–40 |

### 8.4 Bước 3 — Rule pre-label

Rule engine chỉ đưa ra suggestion và evidence:

```json
{
  "product_id": "<id>",
  "rule_status": "hard_fail",
  "rule_reasons": [
    "variant=attraction_ticket not in allowed [golf_voucher]",
    "forbidden_taxonomy=vinwonders_ticket"
  ],
  "suggested_label": 0,
  "confidence": 1.0
}
```

Trạng thái chuẩn:

| Rule status | Ý nghĩa | Hành động |
|---|---|---|
| `hard_fail` | Sai destination, taxonomy, route direction, giá/sao hoặc `must_not` | Auto-final 0 nếu evidence đầy đủ |
| `hard_pass` | Pass tất cả hard filters | Chuyển sang semantic assessment |
| `partial_match` | Đúng một phần, ví dụ golf đúng nhưng voucher/tee-time khác | LLM draft + human review |
| `unknown_metadata` | Thiếu subtype, amenity, airport mapping hoặc facts cần thiết | Human review hoặc sửa metadata |
| `not_in_scope` | Không search-able/retired theo benchmark policy | Loại hoặc 0 theo policy cố định |

### 8.5 Bước 4 — LLM pre-label

LLM chấm batch 10–30 products, chỉ nhận dữ liệu catalog có kiểm chứng: name, variant, destination, product kind, attributes, child facts, combo facts và description grounded.

LLM phải trả JSON:

```json
{
  "suggested_label": "0|1|2",
  "confidence": 0.0,
  "hard_violation": false,
  "reason_codes": [
    "destination_match",
    "taxonomy_partial_match",
    "not_voucher"
  ],
  "evidence_fields": [
    "variant",
    "product_kind",
    "destination"
  ],
  "needs_human_review": true
}
```

LLM nên làm:

- Chuẩn hoá query không dấu/typo thành candidate canonical form.
- Đề xuất intent/slot/negation scope.
- Pre-label semantic ambiguity.
- Viết rationale ngắn và reason code.
- Flag metadata thiếu/mâu thuẫn.
- Gợi ý adversarial product để làm pool khó hơn.

LLM không nên:

- Tạo final ground truth một mình.
- Suy luận price, availability, amenity, child room hoặc route direction khi facts không được truyền vào.
- Auto-accept label 2.
- Chấm full catalog.
- Làm annotator duy nhất cho phủ định, taxonomy collision, flight direction hay no-result.

### 8.6 Bước 5 — Human adjudication

Human review bắt buộc cho:

1. Mọi candidate được đề xuất label 2.
2. Mọi candidate label 1.
3. Rule và LLM không đồng ý.
4. Mọi candidate nằm top-10 của một arm mới hoặc là hole.
5. Mọi forbidden item xuất hiện top-10, đặc biệt top-3.
6. Toàn bộ safety slice lúc ban đầu: negation hard, taxonomy collision, flight direction.
7. `unknown_metadata`.

Human UI cần hiển thị query, canonical query, hard constraints, forbidden conditions, product facts, rule suggestion, LLM suggestion, evidence và rank ở từng arm. Không yêu cầu annotator tự đọc raw catalog JSON hoặc tự tìm dữ liệu từ hệ thống khác.

---

## 9. Auto-label được bao nhiêu, human review bao nhiêu?

### 9.1 Quy tắc auto-accept

| Trường hợp | Có thể auto-final? | Chính sách |
|---|---|---|
| Hard filter fail, có evidence schema | Có | Final 0 |
| Forbidden taxonomy/route/attribute match | Có | Final 0 + audit sample |
| LLM label 0, confidence >= 0.95, không nằm top-10 arm nào | Có điều kiện | Audit ngẫu nhiên 10–20% |
| LLM label 1 hoặc 2 | Không | Human final |
| Rule/LLM conflict | Không | Human final |
| Negation hard / flight direction | Không auto-final positive | Human review positive và top-10 |
| Metadata thiếu | Không | Human review/sửa metadata |
| Top-3 của bất kỳ arm | Không | Human review bắt buộc |

### 9.2 Quy mô gold_v4a

Khởi đầu với 80 canonical query mới:

| Thành phần | Ước lượng |
|---|---:|
| Pool trung bình | 45 product/query |
| Candidate thô trước dedupe | 3.600 |
| Auto-label hard fail = 0 | 35–50% |
| LLM pre-label queue | 1.800–2.300 |
| Human final adjudication | khoảng 900–1.400 |
| Review kỹ top-10/hole/conflict | khoảng 600–900 decisions |

Gold v3 đang có 4.991 active judgments, median khoảng 38 judgments/query. Nếu thêm 80 query với khoảng 45 judgments/query, gold active tăng thêm khoảng 3.600, đạt khoảng 8.500–9.000 labels — hợp lý cho benchmark OTA hẹp.

### 9.3 Quy mô dài hạn

Với 240–300 canonical intent:

| Thành phần | Ước lượng |
|---|---:|
| Tổng judgments | khoảng 10.000–15.000 |
| Auto-label 0 chắc chắn | 4.000–7.000 |
| LLM pre-label | 4.000–6.000 |
| Human final adjudication | 2.500–4.500 |
| Double-label/recheck | 10–20% sample và 100% conflict/high-risk |

Không cần và không nên chấm tay toàn bộ 3.183 product cho từng query.

---

## 10. Annotation metadata và QA

Nên lưu annotation metadata song song với `provenance`:

```json
{
  "annotation": {
    "<productId>": {
      "label": 2,
      "source": "human_adjudicated",
      "annotator": "domain_owner_01",
      "reviewed_at": "2026-10-05",
      "reason_codes": [
        "destination_match",
        "taxonomy_exact",
        "voucher_scope_exact"
      ],
      "evidence": {
        "destination": "Hội An",
        "variant": "golf",
        "product_kind": "voucher"
      },
      "llm_suggestion": {
        "label": 2,
        "confidence": 0.98
      }
    }
  }
}
```

Quality control:

- Double-label 10–20% semantic/ambiguous candidates.
- Double-label 100% ở batch đầu cho negation hard, taxonomy collision và flight direction.
- Adjudicator resolve disagreement.
- Theo dõi agreement riêng cho `0 vs 1`, `1 vs 2`, và safety slices.
- Nếu disagreement lặp lại, sửa `gold-guide.md` trước khi gán thêm labels.
- Version mọi thay đổi rubric; không overwrite silent các label cũ.
- Lưu evidence fields, không chỉ rationale prose.

---

## 11. Thay đổi benchmark artifact

Giữ `top_ids`, đồng thời arm nên ghi thêm các cột optional vào `per_query.parquet` để debug:

```text
qid
top_ids
retriever_sources
dense_rank
lexical_rank
fusion_score
query_normalized
query_rewritten
intent
intent_confidence
parsed_filter
applied_filter
filter_pass_rate
forbidden_ids_hit
forbidden_attribute_hit
taxonomy_top1
taxonomy_top3_purity
actual_parse
parse_slot_match
latency_ms
cache_hit
```

Tách dashboard làm hai phần:

1. **Query understanding:** intent accuracy, slot F1, parse exact, negation scope accuracy, route direction accuracy.
2. **Retrieval/ranking:** Recall, nDCG, MRR, Judged, Full/Condensed, Forbidden@k, filter pass và no-result correctness.

Nhờ đó, case `voucher golf Hoi An -> vé VinWonders` được định vị chính xác là lỗi parser/filter, candidate generation hay ranking; không chỉ là một điểm nDCG thấp.

---

## 12. Checklist triển khai gold_v4a

- [ ] Chốt rubric toàn cục 0/1/2 và policy cho voucher vs tee-time, combo vs standalone, property vs room, nearby vs included.
- [ ] Thêm schema optional: `canonical_text`, `equivalence_group`, `expected_intent`, `expected_parse`, `forbidden`, `soft_preferences`.
- [ ] Tạo 70–90 canonical queries priority slices.
- [ ] Tạo query variants không dấu/alias/typo nhưng aggregate theo family.
- [ ] Chạy union pooling từ dense, lexical, unaccent, fuzzy, hybrid, filter-first và arm mới.
- [ ] Thêm adversarial candidates cho taxonomy collision và reverse route cho flight.
- [ ] Rule pre-label hard fail và lưu evidence.
- [ ] LLM pre-label candidates còn lại theo JSON schema.
- [ ] Human adjudicate label 1/2, conflict, top-10/hole, safety cases.
- [ ] Double-label safety batch đầu và resolve disagreement.
- [ ] Bổ sung `Forbidden@k`, taxonomy, direction và parse guards vào evaluator/report.
- [ ] Rescore các arm cũ sau khi hole/label mới được merge.

## 13. Quyết định chốt

1. Không label full catalog; label pooled candidates và reuse label trong cùng query family.
2. Auto-final nhãn 0 chỉ khi hard violation có evidence catalog/filter rõ ràng.
3. LLM là pre-annotator và triage tool, không phải nguồn ground truth cuối.
4. Human chốt mọi label 2, label 1, conflict, top-k/hole và safety slice.
5. Dùng `forbidden` và hard guard để một arm không thể thắng chỉ nhờ average nDCG trong khi trả sai taxonomy, phủ định hoặc chiều bay.
6. Tách rõ query understanding correctness khỏi retrieval/ranking correctness.

## 14. Đề xuất đổi `gold_schema.SLICES` (người dùng chốt 05/10 — D3)

`gold_schema.py` ghi "chỉ sửa trên main; nhánh nào cần đổi thì ghi đề xuất". Đề xuất và quyết định:

- Thêm đúng hai slice, **nối vào cuối** `SLICES` (giữ luồng RNG của `split` theo `SLICES.index` cho 13 slice cũ, golden test không đổi): `taxonomy_collision` (va chạm loại sản phẩm cùng nơi: khách sạn / vé / combo / golf), `flight_direction` (vé máy bay có chiều; câu chỉ có điểm đi hoặc chỉ có điểm đến).
- Các slice khác của §5 không thêm tên mới: `no_diacritic` ≈ `no_diacritics`, `typo` + `alias_abbreviation` ≈ `abbrev_typo`, `negation_hard` ≈ `amenity_negation`, `mixed_constraints` ≈ `multi_constraint`; `negation_soft`, `flight_partial_route` (gộp vào `flight_direction`) để sau.
- `config/sbench.yaml`: quota tham khảo `taxonomy_collision: 5`, `flight_direction: 6`; `target` 200 → 211, `minimum` 39 → 45 (15 slice × 3).
- Nhánh: `search_bench` chưa có trên `main`; thay đổi nằm trên nhánh bench (`feat/gold-v4`) cùng commit với file này.
