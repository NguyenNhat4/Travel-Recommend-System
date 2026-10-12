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

- Với dữ liệu thật, tool gọi engine Search/Recommendation trong cùng tiến trình
  qua port (`ITINERARY_DATA_MODE=inprocess`, `application/itinerary/engine_tools.py`);
  mode `http` gọi các endpoint dưới đây và chỉ còn là tuỳ chọn. Output giữ đúng
  hình dạng response của route, nên hành vi engine trong tài liệu này áp như nhau
  cho route lẫn tool (`hop-dong-tich-hop-itinerary-assistant.md` §2).
- Tìm kiếm **không gắn danh tính**: mode `inprocess` gọi engine không qua route
  nên không ghi event, mode `http` gọi `/search` **không kèm JWT**. Nhờ vậy lượt
  tìm của Agent không bị ghi thành hành vi người dùng (`hop-dong-tich-hop-cdp.md` §1.4).
- Sao chép nguyên `productId`, `name`, `unitPrice` từ response. Không tự tạo sản phẩm.
- Kiểm tra ngày và số khách **sau** retrieval; không tuyên bố engine đã xác minh.
- Chỉ dùng `/products/{productId}/similar` (`same_taxonomy`) ở lượt đổi món, qua
  tool `get_similar_products`, với sản phẩm gốc lấy từ lịch trình lượt trước
  (`hop-dong-tich-hop-itinerary-assistant.md` §2.5; đã chốt 2026-09-29,
  `docs/prd/update-archive/2026-09-28-tool-similar-cho-agent.md`). Agent không
  dùng `cross_taxonomy`: route chưa hiện thực chế độ này.

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
FILTER → TOP-K (Weaviate) → CUTOFF → TOTAL/FACETS → SORT → PAGE

F       = tập sản phẩm sau structured filter (tính trên metadata trong RAM)
C       = top-K của F theo score(p, query), Weaviate trả về (filter theo id của F)
R       = { p ∈ C | score(p, query) >= cutoff }
total   = |R|
facets  = aggregation trên R
results = một trang của R
```

Áp cho cả ba endpoint. Với `/recommendations`, `query` được thay bằng user vector.
`K` là `candidateK` (mặc định 200); `score = 1 − cosine distance`.

**Riêng `/search` ở chế độ `HYBRID_CANDIDATE_SCORE` (từ 25/09/2026, FR-SRC-01):**

```
CHUẨN HOÁ → FILTER → TOP-K dense ∪ TOP-K BM25 (Weaviate) → CUTOFF + VỚT → TOTAL/FACETS → SORT (RRF) → PAGE

q'      = chuẩn_hoá(query): NFC → viết tắt (KS, KDL, gd, VW; NT, PQ, ĐN, HN, HL, SG/HCM/TPHCM/Sài Gòn; Ntr → N triệu)
          → sửa chính tả tên riêng theo từ vựng tên sản phẩm + điểm đến của catalog (không bảng chép tay)
          → tên điểm đến về đúng giá trị catalog (khớp dài nhất trên token đã fold)
          → kiểu đi về nhãn `audience` catalog dùng (bạn trai/bạn gái → cặp đôi, 1 mình → một mình, công ty → công tác)
          Embed và BM25 đều dùng q'. Số khách chưa thành filter. `query` gốc giữ ở event `search` (§3.2).
F       = structured filter, trong đó điểm đến (từ 2026-10-05, FR-SRC-03, sau cờ `SEARCH_DEST_FILTER`, mặc định tắt
          cho tới khi bench xác nhận): `destination` của request luôn thắng; không có thì lấy địa danh **duy nhất** mà
          bước chuẩn hoá nhận ra trong q'; câu nêu ≥ 2 nơi (nơi đi + nơi đến, "A hoặc B", thương hiệu chứa địa danh) hay
          câu hỏi vé máy bay (`taxonomy = flight`, cụm "vé máy bay / chuyến bay / đường bay / chặng bay") thì **không**
          lọc theo điểm đến. F rỗng sau khi lọc theo địa danh suy ra → chạy lại không lọc (FR-SRC-04), khai
          `diagnostics.destinationFilter.fallback = dropped_empty`. Khi filter suy ra đang áp, token địa danh không tính
          vào `phủ(tên, truy vấn)` ở bước VỚT. Khai báo: `diagnostics.derivedDestinations` (luôn, khi câu có địa danh),
          `diagnostics.destinationFilter` và `appliedFilters.hard.destinationSource` (khi cờ bật) — contract 1.14.0.
Câu không dấu (từ 2026-10-05, `SEARCH_NO_DIACRITICS_MODE=relax`, mặc định `off`): câu gốc không có dấu nào và có ≥ 3 token
          truy vấn → bước VỚT dùng bộ ngưỡng riêng (`lexicalK 20 / lexicalCutoff 0 / lexicalMinCoverage 0,4`, tạm — chưa
          qua dev/test) và cutoff dense riêng nếu cấu hình; vector và khoá cache không đổi; khai
          `diagnostics.queryProfile = no_diacritics`, `cutoff` của response là cutoff hiệu lực.
QUERY PLAN (từ 2026-10-05, kiến trúc Phase A — `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md`; contract
          1.15.0 `diagnostics.queryPlan`): sau chuẩn hoá, parse hard constraint từ q' theo thứ tự giá/sao → phủ định → loại
          sản phẩm → tuyến bay. Tham số request luôn thắng giá trị suy ra; mỗi họ một cờ, mặc định tắt (tắt vẫn parse và khai
          ở `queryPlan` để bench đo — trừ ba họ 07/10 bên dưới: tắt thì không parse, không khai). Ngữ nghĩa từng họ:
          · F6 `SEARCH_NUMERIC_FILTER`: "dưới / không quá / tối đa N triệu|nghìn" → priceMax (hard, trên giá thấp nhất của
            unit kể cả phòng con; giá null bị loại khi có lọc giá); "từ / không dưới / N sao" → starRatingMin (SOFT theo
            [C6]: unit khai sao thấp hơn bị loại, unit không khai sao giữ và xếp sau). "không nhất thiết N sao" → bỏ điều
            kiện, không lọc.
          · F3 `SEARCH_NEGATION_FILTER`: "không có / không ghi nhận / không gồm / không phải / trừ X" với X trong từ vựng
            tiện ích (`domain/search/amenities.py`) → loại unit CÓ GHI NHẬN X (property ∪ phòng con); vắng = không biết →
            qua ([C2], khớp quy ước gán nhãn #3/#7 của `docs/spec/bench/gold-guide.md`). "không cần / không nhất thiết X" →
            bỏ điều kiện. Cụm ngoài từ vựng → `queryPlan.unresolved`, không lọc, không bịa khoá.
          · F4 `SEARCH_TAXONOMY_FILTER`: câu nêu đúng MỘT loại sản phẩm (khách sạn/resort/villa…, vé máy bay/chuyến bay…,
            vé tham quan/VinWonders…, combo, golf) và không có `taxonomy` request → lọc taxonomy; ≥ 2 loại (cross-vertical)
            hoặc cụm nằm trong tên thương hiệu → không lọc. Bật cờ này làm request tổng quan của Web (không taxonomy, dùng để
            đếm tab) chỉ còn đếm loại câu nêu — bật cần ý kiến Web (`docs/spec/product.md` §4.2.3).
          · F5 `SEARCH_ROUTE_FILTER`: chỉ câu vé máy bay (`taxonomy = flight` hoặc cụm bay ở trên): "từ A đến/đi/vào/ra B",
            "A - B", "A đi B" → origin A, destination B (lọc `originCity` / `destinationCity` của tuyến); chỉ "đến B" → chỉ
            đích; thiếu nơi đi thì không bịa; hai nơi không rõ vai → không lọc. Tham số `origin` (1.15.0) thắng câu; ngoài
            câu bay `origin` bị bỏ qua và khai ở `queryPlan.ignored`.
          · Từ 2026-10-06 (contract 1.16.0; mọi phần mới sau cờ, mặc định tắt):
            – Loại trừ loại sản phẩm / thành phần (thuộc F3, cờ `SEARCH_NEGATION_FILTER`): "vé lẻ", "không lấy combo", "không
              phải khách sạn" → `queryPlan.mustNot.taxonomies`; "không kèm vé máy bay / khách sạn" → `mustNot.flags`
              (`includesFlight` / `includesHotel`, suy từ `catalog.combo_items.item_kind` của combo). Không bao giờ loại chính
              loại câu (hoặc tham số) đang hỏi — xung đột khai `unresolved`.
            – Combo đứng đầu câu ("combo vé máy bay và khách sạn Đà Lạt") → taxonomy combo, thành phần không tính là loại thứ
              hai. Câu đã có một loại khác flight (tham số hoặc suy ra) không phải câu vé máy bay: không parse tuyến, điểm đến
              lọc như câu thường.
            – `SEARCH_TAXONOMY_STRONG_ONLY`: F4 chỉ lọc khi câu có cue MẠNH; bảng cue yếu `constraints.WEAK_VERTICAL_CUES`
              ("nghỉ dưỡng", "phòng", "tham quan", "công viên", "khu vui chơi", "gói du lịch", tên điểm VinWonders / Safari /
              Grand World — combo chứa vé được tính là đúng ý) chọn theo dữ liệu nhãn 06/10; khai `queryPlan.taxonomy.strength`.
              Tên điểm vui chơi luôn giữ trong `lexicalText` (là tên sản phẩm, BM25 cần). Với F4 chúng vẫn chỉ là cue yếu; bật thêm
              `SEARCH_ENTITY_FILTER` (khối 07/10 dưới) thì tên đó còn làm cổng entity — F4 bật cùng entity → AND (taxonomy ∧ tên chứa entity).
            – `SEARCH_PARTY_FILTER`: "N người", "N người lớn M trẻ em" → `appliedFilters.hard.minOccupancy` = tổng; tham số
              `travelContext.guests` của request luôn áp (không cờ — tuân thủ contract). Loại unit có sức chứa tối đa (unit ∪
              phòng con) < tổng; không khai sức chứa → giữ ([C2]). Giá và số khách cùng áp → phải có MỘT phòng con thoả cả hai.
              `results[].matchedChildren` (≤ 5 id phòng con, giá tăng dần) phát mỗi khi lọc giá hoặc số khách đang áp.
            – `SEARCH_TONE_NORMALIZE`: đưa vị trí dấu thanh (oà/òa, oé/óe, uý/úy) về kiểu đa số của catalog trước mọi bước.
            – Độ tin cậy router (không LLM): `queryPlan.confidence` (0–1) và `fallbackReasons` (phủ định không rõ phạm vi, tuyến
              hai nơi không rõ vai, nhiều loại, cue loại yếu, xung đột tham số ↔ câu, câu dài nhiều ràng buộc…). Luôn khai, không
              cờ. LLM fallback cho câu độ tin cậy thấp: đề xuất đã chốt và áp dụng 06/10
              (`docs/prd/update-archive/2026-10-06-search-llm-fallback-query-plan.md`), ship ở contract 1.17.0 — `queryPlan.llm`,
              `stageMs.llm`, cờ `SEARCH_LLM_FALLBACK` off|shadow|on (mặc định off → response y như 1.16.0); giả thuyết LLM chỉ điền ô
              mà rule để trống, kiểm theo catalog, khai `llm.accepted` / `rejected`. Wiring production (settings + `main.py`) bị merge
              `21d72ae` làm mất, khôi phục 07/10 (`history/2026-10-07-restore-search-prod-defaults-llm-fallback.md`).
          · Từ 2026-10-07 (contract 1.18.0; spec `docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md`, plan
            `docs/plan/2026-10-07-search-duration-entity-poi.md`; ba cờ mặc định tắt — tắt thì KHÔNG parse, không khai, response
            y như 1.17.0; thứ tự parse khi bật: giá/sao → thời lượng → số khách → phủ định → loại → vai trò entity → tuyến →
            POI/điểm đến; dense text, khoá cache embed, `confidence` và tập câu kích hoạt LLM không đổi):
            – F7 `SEARCH_DURATION_FILTER`: "N ngày M đêm", "3N2Đ", "N ngày", "M đêm", "N days M nights" (chữ số 1–30; cụm đã nằm
              trong span giá / số khách như "2 triệu/đêm", "2 người" không tính; "qua đêm", "chợ đêm", "ngay trung tâm", "3 tiếng"
              không khớp) → `queryPlan.duration {days, nights, source: query}`, `applied` có `duration`, cụm bị bỏ khỏi `lexicalText`
              ("VinWonders 3 ngày 2 đêm" → `lexicalText = "VinWonders"`, hết vớt hotel "… Ngay … Chợ Đêm" qua BM25). Chỉ khai + bỏ
              cụm, KHÔNG lọc — catalog chưa có trường thời lượng (`nights` 0 unit); câu chỉ có thời lượng không phát `appliedFilters`;
              `emptyReason = duration` khai cho đủ họ, không bao giờ phát.
            – `SEARCH_POI_RESOLVE`: địa danh / khu vực / quận / sân bay / venue trong bảng gazetteer của repo
              (`domain/search/gazetteer.py`: Hồ Hoàn Kiếm / Hồ Gươm, Hồ Tây, Nội Bài, Cầu Rồng, Bà Nà, Bãi Sao, Hòn Tằm…; chỉ entry
              có điểm đến thuộc catalog đang phục vụ) → điểm đến catalog của nó vào F1 đúng luật địa danh thường: duy nhất → lọc
              (`diagnostics.destinationFilter.source` vẫn là `query`, giữ fallback FR-SRC-04); ≥ 2 điểm đến ("khách sạn Hà Nội gần
              Cầu Rồng") → `skipped = multi`; hai POI cùng thành phố ("Hồ Gươm hoặc Hồ Tây") → một điểm đến; câu vé máy bay không
              lọc. Khai `queryPlan.location {key, name, kind, destination}` (POI đầu tiên trong câu),
              `diagnostics.derivedDestinations` gồm điểm đến suy từ POI, `appliedFilters.hard.destinationSource = poi` (chỉ khi điểm
              đến đang áp đến từ POI; tuyến bay IATA vẫn `query`). POI trong span phủ định bỏ; token POI giữ trong BM25. Chưa có geo
              (bán kính, khoảng cách) — P1, contract 1.19.0.
            – `SEARCH_ENTITY_FILTER` — cổng entity CỨNG: câu nêu điểm vui chơi trong gazetteer (khoá `vinwonders`, `safari`,
              `grand_world`, `hon_tam`…; brand khách sạn "Vinpearl" không phải entity; chỉ khoá có ≥ 1 unit attraction/combo trong
              catalog mới gate, không thì rơi về `location`). Vai trò theo cue loại của câu: `gate` khi câu không nêu loại khác (hoặc
              chỉ cue attraction/combo, kể cả combo đứng đầu — "combo VinWonders Phú Quốc"); `location` khi câu có cue loại khác —
              khách sạn / phòng / vé máy bay / golf, kể cả cue yếu ("phòng gần Grand World") — hoặc ≥ 2 loại. `gate` → `applied`
              có `entity`, mask chỉ giữ unit attraction/combo có **tên** chứa ≥ 1 khoá (hard, không nới; nhiều khoá → OR),
              `appliedFilters.hard.entity` = danh sách khoá; `location` → chỉ khai `queryPlan.entity {keys, role}`, không lọc.
              Entity trong span phủ định bỏ ("không lấy VinWonders, vé Safari" → chỉ `safari`); token entity không bỏ khỏi
              `lexicalText`; F3 `mustNot.taxonomies` giao bình thường ("vé lẻ VinWonders, không lấy combo" → chỉ attraction). Tham số
              `taxonomy` của request KHÔNG đổi vai trò, chỉ giao với mask → request tab Lưu trú của Web cho câu VinWonders về
              `total 0`, `emptyReason = entity` (không phải `param`) — bật cần Web xác nhận như F4 (`docs/spec/product.md` §4.2.3);
              Agent tool không truyền `derive_plan` nên cổng áp cả Agent khi cờ bật. Combo chỉ nhận entity qua tên
              (`catalog.combo_items` → P1).
          Cụm đã thành filter (và cụm thời lượng F7, 07/10) bị bỏ khỏi câu đưa vào BM25 và độ phủ vớt (`queryPlan.lexicalText`);
          vector dense vẫn dùng q' đầy đủ (khoá cache embed không đổi). Sau RRF kiểm lại hard filter trên R
          (`queryPlan.revalidatedDrops`, kỳ vọng 0). F rỗng do filter suy ra → `total 0` + `queryPlan.emptyReason` (`entity` khi
          cổng entity 07/10 làm rỗng, kể cả khi request có `taxonomy`), KHÔNG nới ngầm (kiến trúc Phase A §6); chỉ điểm đến suy
          ra (kể cả suy từ POI) giữ fallback ở trên. `appliedFilters.hard/soft` khai những gì đã áp (§2.5).
C_dense = top-candidateK của F theo cosine
C_lex   = top-lexicalCandidateK của F theo BM25 trên nameAscii + searchTextAscii (đã fold dấu; truy vấn fold cùng cách)
R_dense = { p ∈ C_dense | score(p) >= cutoff }
R_lex   = { p ∈ C_lex \ R_dense | rank_lex(p) <= lexicalK ∧ score(p) >= lexicalCutoff ∧ phủ(tên p, truy vấn) >= lexicalMinCoverage }
R       = R_dense ∪ R_lex
SORT    = giảm dần theo RRF(p) = Σ 1/(rrfK + rank) trên các nhánh p có mặt; hoà thì theo score
```

Từ 2026-10-06 (contract 1.16.0, kiến trúc §7 kênh 5C) có thêm kênh **fuzzy tên** và RRF **có trọng số**, mặc định tắt / trung tính:

```
C_fuzzy = (SEARCH_FUZZY_K > 0) top-fuzzyCandidateK của F theo độ giống trigram (kiểu pg_trgm, trong tiến trình — không
          trigram Postgres) giữa tên unit và cửa sổ token cùng độ dài tên của lexicalText
R_fuzzy = { p ∈ C_fuzzy \ (R_dense ∪ R_lex) | rank_fuzzy(p) <= fuzzyK ∧ sim(p) >= fuzzyMinSim ∧ score(p) >= lexicalCutoff }
RRF(p)  = Σ w_kênh / (rrfK + rank_kênh(p)),  w = SEARCH_RRF_DENSE_WEIGHT / _LEXICAL_WEIGHT / _FUZZY_WEIGHT (mặc định 1 → như cũ)
```

`diagnostics.fuzzyCount` = số unit chỉ vào R nhờ kênh fuzzy; `stageMs.fuzzy` gồm cả lấy vector để tính `score`.

`score` vẫn là cosine (§2.6); RRF chỉ quyết định thứ tự, nên `score` không đơn điệu trong một trang.
`phủ(tên, truy vấn)` = tỉ lệ token của truy vấn (đã fold, dài ≥ 2, bỏ từ chức năng) có trong tên. Truy vấn gần
như là tên/thương hiệu thì qua ("VinWonders" → mọi tên chứa VinWonders: 1/1; "melia vinpearl hue" →
"Meliá Vinpearl Hai Phong": 2/3); câu mô tả dài để nhánh dense lo; "khách sạn ở Cà Mau" không vớt được
"Hoa Mau Don Homestay" (1/4). Không dùng độ hiếm (DF) của token: trên catalog 2026-09-21 "vinwonders" có mặt
trong 4,9% tên, "trang" 5,0% — DF không tách được thương hiệu với địa danh phổ biến.
Nhánh BM25 lỗi (collection chưa có property) → engine chạy dense-only nhưng vẫn khai `HYBRID_CANDIDATE_SCORE`
với `diagnostics.lexicalCandidates = 0`, không trả 500.

Thời gian từng bước khai ở `diagnostics.stageMs` (từ 2026-09-29, contract 1.11.0; phục vụ NFR-PERF-01/03): ms nguyên
của `normalize` (chỉ khi bước chuẩn hoá bật), `embed`, `dense` (gồm dựng bộ lọc cấu trúc), `lexical` (chỉ ở hybrid,
kể cả khi nhánh BM25 lỗi), `fuse` (RRF + cutoff + facets) và `hydrate`. Đo trong engine nên tổng các bước ≤
`latencyMs` của route. Chỉ `/search` có trường này.

Vector truy vấn được **cache trong tiến trình** (từ 2026-09-30, contract 1.12.0; NFR-PERF-03 yêu cầu cache vector của
truy vấn lặp lại): khoá là câu **sau chuẩn hoá và gộp khoảng trắng** (`SearchProducts.query_text`), nên "KS ở NT" và
"khách sạn ở Nha Trang" dùng chung một vector; không fold hoa/thường/dấu. `diagnostics.embedCache` = `hit` / `miss`
(chỉ `/search`; vắng khi `SEARCH_EMBED_CACHE=false`). Cache không đổi kết quả hay thứ tự — chỉ `stageMs.embed` khác.
LRU `SEARCH_EMBED_CACHE_SIZE` (mặc định 10.000 ≈ 15 MB với e5-small 384 chiều), single-flight: nhiều request cùng câu chỉ embed một lần.
Sau lần nạp catalog đầu tiên backend **nạp sẵn** cache ở nền (`SEARCH_PREWARM`): file câu gold đóng băng
`src/backend/data/search_prewarm_queries.txt` (131 câu gold_v1) + head query của `app.search_logs`, pacing
`SEARCH_PREWARM_INPUTS_PER_MINUTE`; job `python -m src.backend.jobs.prewarm_query_cache --base-url URL` làm nóng một
backend đang chạy qua HTTP (lần hai phải `miss 0`).

Bước chuẩn hoá khai ở `diagnostics.normalizedQuery` / `appliedAliases` / `corrections` / `party`, chỉ khi có
nhận ra hoặc đổi gì; `SEARCH_NORMALIZE=false` tắt cả bước. Sửa chính tả chỉ đụng token không phải âm tiết tiếng
Việt, dài ≥ 5, cách ≤ 1 ký tự (≤ 2 khi ≥ 8) so với token có mặt ở ≥ 3 tên sản phẩm — "Vinpeal" → "Vinpearl",
còn "cong", "bien", "view" không bao giờ bị sửa. Bảng viết tắt chỉ chứa cách viết; điểm đến đích không có trong
catalog thì alias đó bị bỏ. Từ vựng sửa chính tả và danh sách điểm đến dựng từ catalog đang phục vụ, lúc khởi động
và mỗi lần nạp lại catalog (`CATALOG_REFRESH_SECONDS`, §2.4).

**Vì sao filter trước:** category exclusion của `/recommendations` loại khoảng
50% catalog. Chấm điểm trước rồi lọc sau có thể để lại dưới `k` kết quả. Vì vậy
id của `F` được gửi làm filter cho truy vấn top-K, không lấy top-K rồi mới lọc.

### 2.3. Bất biến

Các bất biến dưới đây tính trên tập ứng viên `C`, không phải toàn bộ catalog.

```
1. sum(facets.taxonomy) == total
2. total và facets KHÔNG đổi khi thay limit/offset (trong phạm vi K ứng viên)
3. mọi results[].score >= cutoff — TRỪ ở HYBRID_CANDIDATE_SCORE: phần vớt từ nhánh BM25
   có score >= diagnostics.lexicalCutoff, số lượng ghi ở diagnostics.lexicalCount
4. results, total, facets dùng CÙNG filter và CÙNG cutoff
5. sản phẩm thiếu destination → bucket "UNKNOWN", không biến mất
```

### 2.4. Chế độ truy xuất — khai báo, không đổi ngầm · `[C4]`

```yaml
search:           { mode: HYBRID_CANDIDATE_SCORE, cutoff: 0.84, candidateK: 200,
                    lexicalCandidateK: 50, lexicalK: 10, lexicalCutoff: 0.50, lexicalMinCoverage: 0.6, fusion: rrf(60),
                    normalize: true, destFilter: false, noDiacriticsMode: off,   # hai knob này: 2026-10-05, §2.2
                    negationFilter: false, taxonomyFilter: false, routeFilter: false, numericFilter: false,   # 2026-10-05, QUERY PLAN §2.2
                    toneNormalize: false, taxonomyStrongOnly: false, partyFilter: false,                     # 2026-10-06, §2.2
                    fuzzyK: 0, fuzzyCandidateK: 50, fuzzyMinSim: 0.75, rrfWeights: { dense: 1, lexical: 1, fuzzy: 1 },
                    llmFallback: off,                                                                        # 2026-10-06, §2.2 (contract 1.17.0)
                    durationFilter: false, poiResolve: false, entityFilter: false,                           # 2026-10-07, §2.2 (contract 1.18.0)
                    logQueries: false }                                                                      # 2026-10-06, §7.3
similar:          { mode: ANN_CANDIDATE_SCORE, topK: 20 }
recommendations:  { mode: ANN_CANDIDATE_SCORE, candidateK: 200 }
```

`/search` chuyển sang hybrid ngày 25/09/2026 (§2.2). `SEARCH_HYBRID=false` đưa `/search` về
`ANN_CANDIDATE_SCORE` dense-only đúng như trước; các tham số `lexical*` đọc từ `core/config.py`
(`SEARCH_LEXICAL_K`, `SEARCH_LEXICAL_CUTOFF`…) và chưa benchmark (§10 S9).

**Chốt 24/09/2026 (S8, hướng b — `docs/prd/update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md`).**
Backend không còn tải toàn bộ vector vào RAM lúc khởi động: tải 3.183 vector từ
Weaviate Cloud mất 453 giây. Mỗi request gửi truy vấn top-K sang Weaviate
(`nearVector` qua gRPC, filter theo id), đúng `docs/prd/architecture.md` §5.
Metadata (taxonomy, destination, available, recommendable, parent) vẫn nạp từ
Postgres để tính filter: lúc khởi động và sau đó mỗi `CATALOG_REFRESH_SECONDS`
(mặc định 900 giây), để giá, trạng thái và cửa sổ ngày theo kịp job cào hằng ngày.
Mỗi lần nạp lại hỏi Postgres mã băm của catalog (một dòng); mã trùng lần trước thì
dùng lại catalog đang giữ, không kéo lại — kiểm vector và độ phổ biến vẫn chạy mỗi
chu kỳ. Hỏi mã băm lỗi thì kéo đầy đủ như cũ.
Lần nạp lại lỗi thì giữ bản đang phục vụ. Mỗi lần nạp kiểm từng search unit
theo object id, `modelVersion`, `textHash` (không tải vector): unit chưa có vector
vẫn nằm trong metadata nhưng Weaviate chưa trả nó cho tới khi job index xong; unit
có vector của text cũ dùng tạm vector đó. Engine chỉ từ chối (tương đương
`SEARCH_UNAVAILABLE` ở §6) khi dưới một nửa search unit có vector đúng model —
collection rỗng, chưa index, hoặc vừa đổi text builder.

Vì chỉ có top-K, sản phẩm ngoài tập ứng viên vẫn có thể vượt cutoff. Do đó bốn
trường sau là **bắt buộc**:

```
searchMode  = ANN_CANDIDATE_SCORE
approximate = true
totalExact  = false
facetsExact = false
```

Trả `approximate: true` mà vẫn khai `totalExact: true` là **vi phạm hợp đồng** — nó
phá tiêu chí 8 của `hop-dong-tich-hop-backend.md` §12 một cách âm thầm.
`EXACT_FILTER_SCORE` chỉ còn dùng cho engine quét toàn bộ vector trong RAM (bản
chạy offline trong test).

### 2.5. Hard filter và soft filter · `[C6]`

| Loại | Trường | Độ phủ | Hành vi |
|---|---|---:|---|
| **Hard** | `taxonomy`, `destination`, `priceMin/Max`, `availableOnly` | ≥ 93% | Loại thẳng |
| **Soft** | `starRatingMin` | 51% | Thiếu dữ liệu **không bị loại**, chỉ xếp sau |
| **Hard** suy từ câu (05/10, sau cờ, §2.2 QUERY PLAN) | `taxonomy` (F4), `origin` / `destinationCity` tuyến bay (F5), `mustNotAmenities` (F3), `priceMin/priceMax` (F6) | taxonomy 100 % · tuyến 100 % · amenities 99 % property · giá 100 % | Loại thẳng; `mustNot` chỉ loại unit **có ghi nhận** tiện ích, không cam kết "chắc chắn không có" ([C2]); giá null bị loại khi có lọc giá |
| **Soft** suy từ câu (05/10) | `starRatingMin` (F6) | 70 % property | Unit khai sao thấp hơn bị loại; không khai → giữ, xếp sau |
| **Hard** số khách (06/10) | `minOccupancy` — `travelContext.guests` (luôn áp) hoặc "N người" (cờ `SEARCH_PARTY_FILTER`) | sức chứa biết ở 1.807/2.321 khách sạn | Loại unit có sức chứa tối đa < tổng; không khai → giữ ([C2]); cùng lọc giá hoặc ngày → MỘT phòng con đang bán phải thoả đồng thời tất cả (1.19.0, kiểm ngay ở mask) |
| **Hard** ngày (07/10, contract 1.19.0) | `travelContext.checkIn` / `checkOut` (luôn áp, chỉ từ request; `domain/catalog/stay_dates.py`, `UnitIndex._stay_mask`) | khách sạn: lịch có ở mọi hạng phòng; vé tham quan / golf: lịch + cửa sổ; combo: cửa sổ | Khách sạn: nhận trong [hôm nay, +3 tháng], 1–30 đêm, và còn ≥ 1 hạng phòng đang bán (`available` + có giá) không có đêm kín (`0`) trong [checkIn, checkOut), cùng phòng đó phải thoả số khách và giá đang áp; vé / golf: `checkIn` trong cửa sổ mở bán và ngày đó không kín; combo: `checkIn` trong cửa sổ; route bay: không lọc. Không biết (không lịch, đêm ngoài 30 ngày lịch, không cửa sổ) → giữ ([C2]). Lịch KHÔNG chặn đặt chỗ (FR-CAT-03) |
| **Hard** loại trừ suy từ câu (06/10, F3) | `mustNotTaxonomies` ("vé lẻ", "không lấy combo"), `mustNotFlags` (`includesFlight` / `includesHotel` của combo) | taxonomy 100 % · cờ combo 39/39 combo vé+phòng | Loại thẳng; không loại chính loại câu đang hỏi |
| **Hard** cổng entity (07/10, cờ `SEARCH_ENTITY_FILTER`, chỉ vai trò `gate`) | `entity` — danh sách khoá điểm vui chơi từ gazetteer (`vinwonders`, `safari`, `grand_world`, `hon_tam`…) | tên unit attraction/combo (VinWonders có trong 141 tên trên catalog bench 3.183 unit; combo chỉ qua tên, `combo_items` → P1) | Loại thẳng mọi unit không phải attraction/combo có tên chứa ≥ 1 khoá (nhiều khoá → OR); không nới; giao với `taxonomy` request và F3 → F rỗng khai `emptyReason = entity` |

Response echo `appliedFilters.hard` và `.soft`. Agent **phải đọc** khối này: nếu
`starRatingMin` nằm trong `soft`, Agent không được nói với người dùng "khách sạn
này 4 sao" cho một kết quả không khai `starRating`.

Từ 2026-10-05 (contract 1.14.0) `/search` phát `appliedFilters` khi `SEARCH_DEST_FILTER` bật và có hard filter đang áp;
`hard.destinationSource` = `param` (destination của request) hoặc `query` (địa danh suy ra từ câu, §2.2); từ 2026-10-07
(contract 1.18.0, cờ `SEARCH_POI_RESOLVE`) còn `poi` — điểm đến suy từ địa danh / khu vực / sân bay trong gazetteer ("Hồ Hoàn
Kiếm" → Hà Nội), khi đó `diagnostics.destinationFilter.source` vẫn là `query` và `queryPlan.location` cho biết địa danh nào.
Sau fallback (`diagnostics.destinationFilter.fallback`) khối `hard` không còn `destination`. Agent đọc `destinationSource =
query` / `poi` để biết engine đã khoá điểm đến theo câu, không theo yêu cầu tường minh của người dùng.

Từ 2026-10-05 (contract 1.15.0) `appliedFilters` còn được phát khi bất kỳ hard/soft filter nào đang áp — tham số request
tường minh (`origin`, `priceMin/priceMax`, `starRatingMin`, `availableOnly`) hoặc filter suy từ câu khi cờ bật — với các khoá
`taxonomySource`, `origin`, `originSource`, `destinationCity`, `mustNotAmenities`, `priceSource` (hard) và `starRatingMin`,
`starRatingSource` (soft) — cùng `mustNotBrands`; 1.16.0 thêm `mustNotTaxonomies`, `mustNotFlags`, `minOccupancy`, `partySource`;
1.18.0 thêm `entity` (hard, cổng entity) và giá trị `poi` cho `destinationSource`. `diagnostics.queryPlan` là "parse ra gì",
`appliedFilters` là "đã lọc gì" (thời lượng F7 chỉ có ở `queryPlan`, không bao giờ vào `appliedFilters`).

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
| `available: true` | "còn phòng ngày 15/10" — đó là `bookable`. Có `travelContext.checkIn` thì kết quả đã qua bộ lọc ngày (§2.5) nhưng vẫn là snapshot lịch, không phải xác nhận còn phòng |
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

Agent tìm không gắn danh tính là **quy tắc**, không phải khuyến nghị (mode `http`
không kèm JWT, mode `inprocess` gọi engine không qua route): lượt tìm của
Agent lọt vào lịch sử sẽ làm lệch user vector của chính người dùng đó.

### 3.3. Cutoff · `[C3]`

Mọi sản phẩm đều có cosine với mọi truy vấn. Không có cutoff thì `results: []`
**không bao giờ xảy ra**, trong khi `hop-dong-tich-hop-backend.md` §5.3 mục 6
yêu cầu điều đó.

```yaml
search.cutoff: 0.84     # e5-small, hiệu chỉnh trên gold_v4 (06/10)
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

`backgroundScore` lấy **miễn phí** từ cùng tập ứng viên top-K của §2.2, không cần truy vấn thêm.

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

`strategy=cross_taxonomy` là biến thể cross-sell trong schema, nhưng route chưa
hiện thực (luôn trả `same_taxonomy`) và Agent không dùng. Agent chỉ gọi
`same_taxonomy` ở lượt đổi món (§1.2).

**Không embed lại.** Lấy thẳng vector đã lưu của anchor từ Weaviate, rồi truy vấn top-K với filter id (cùng taxonomy, loại chính nó và anh em cùng cha). Embed lại vừa tốn ~60 ms
vừa có nguy cơ so hai vector thuộc hai `embedding_version` khác nhau — kết quả
vẫn trả về, chỉ là vô nghĩa.

| Lỗi | HTTP |
|---|---|
| `productId` không tồn tại | `404 PRODUCT_NOT_FOUND` |
| Có trong catalog nhưng chưa có vector | `409 PRODUCT_NOT_INDEXED` |

Hai mã khác nhau vì cách xử lý khác nhau: cái đầu là sai id, cái sau là cần reindex.

---

### 3.7. `/search/suggestions` — gợi ý tức thì khi gõ · FR-SRC-05

```http
GET /api/v1/search/suggestions?q=ha&limit=8
```

Hình dạng: `SearchSuggestionResponse` trong `search.yaml` (contract 1.14.0). Đây **không** phải một chế độ của `/search`: khớp chữ, không điểm số, không embed, không kho vector.

| Hạng mục | Quy tắc |
|---|---|
| Nguồn | `UnitIndex` đang phục vụ: tên điểm đến (cùng giá trị và số đếm với `/destinations`) và tên search unit còn bán. Không có vé máy bay, hạng phòng, chuyến bay hay unit `available = false` |
| Khớp | Sau `fold` (bỏ dấu, chữ thường): hạng 0 tên bắt đầu bằng truy vấn · hạng 1 truy vấn khớp từ đầu một từ · hạng 2 mọi token của truy vấn là tiền tố của một từ trong tên. Không khớp giữa từ ("ha" ≠ "nhạc") |
| Xếp và chia | Nhóm theo thứ tự điểm đến, `hotel`, `attraction`, `golf`, `combo`; trong nhóm theo hạng khớp, rồi độ phổ biến (`BuildPopularity`), rồi tên ngắn hơn. Chia chỗ theo vòng giữa các nhóm đến `limit` (mặc định 8, tối đa 10), nên một nhóm đông không đẩy nhóm khác ra |
| Truy vấn ngắn | Dưới 2 ký tự chữ/số sau `fold` → `200` với `suggestions: []`, không phải lỗi. `q` thiếu, dài hơn 100 ký tự hoặc `limit` ngoài 1–10 → `422 VALIDATION_ERROR` |
| Ghi hành vi | **Không** ghi event `search` sang CDP và không ghi `app.search_logs`: Web gọi theo từng lần gõ. Không cần JWT |
| Bộ nhớ đệm | LRU trong tiến trình theo `(fold(q), limit)`, dựng lại cùng mỗi lần catalog nạp lại; response có `Cache-Control: public, max-age=300` (RecSys chưa sẵn sàng thì trả rỗng và không có header này) |
| Ngân sách | p95 ≤ 250 ms (AC-SRC-02). Không gọi dịch vụ ngoài nên không chịu độ trễ Weaviate/Cohere ở §7.1 |

Code: `domain/search/suggest.py`, `application/search/suggest.py`, `api/v1/routes/search.py`.

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
| `dormantDays` | 365 | Ngưỡng `strategy = dormant` (chuyến gần nhất), chốt 2026-10-09; `diagnostics.dormant` vẫn 90 ngày theo contract |

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

**Bổ sung 2026-10-09 (PR-A, `ENGINE_RULES_VERSION = "2026-10-09-p2-combo-explore"`) — vector dài hạn có độ tin cậy chuyến.**
Engine hiện hành (`domain/recommendation/profile.py`) dựng vector mỗi chuyến `vec_t` (chuẩn hoá) rồi
`u_long = Σ_t 2^(−tuổi_t / H_LONG) · confidence_t · vec_t`, với `confidence_t = min(1, Σ W_TYPE của event trong chuyến sau cap)`:
một lượt xem lẻ nặng 0,2, một lần mua 1,0, ba lượt xem 0,6. Trước đó mọi chuyến nặng như nhau sau chuẩn hoá nên một lượt xem
vu vơ kéo `u_long` mạnh bằng cả chuyến đã mua (P2 trong `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` §3.A; số đo
`src/evaluation/reports/eval-2026-10-09-recsys-g6-so-thich-do-lai.md`). Vector chuyến đang mở (`u_short`) không nhân hệ số này.
Cap lặp `MAX_REPEAT_PER_TRIP = 3` chỉ đếm event yếu (view / search); `purchase` và `add_to_cart` luôn vào vector chuyến
(`CAP_EXEMPT_EVENTS`). `because[]` ở nhánh không chuyến mở phân rã đúng theo trọng số này (§4.6).

### 4.4. Quy tắc chọn `strategy`

```
có trip đang mở + đã purchase ít nhất 1 taxonomy  → cross_vertical
>= 3 event dùng được, không có trip đang mở       → recent_activity
chuyến gần nhất > 365 ngày (từ 09/10)             → dormant
< 3 event, không JWT, hoặc CDP lỗi                → popular
có trip đang mở, chưa purchase trong trip,
  tổng < 3 event dùng được                        → cold_start_content
có lịch sử, không có trip đang mở,
  chưa quá ngưỡng dormant của engine              → long_term
```

**Bổ sung 2026-09-28 (OpenAPI 1.8.0).** Hai dòng cuối ghi đúng điều kiện engine
đang chạy (`Profile.strategy` trong `domain/recommendation/profile.py`). Engine
đã trả hai giá trị này từ trước, nhưng contract thiếu. Các dòng cũ **lệch với
engine và chưa sửa**, đang chờ Team Recommendation/Search cùng Web quyết định:

- `recent_activity`: bảng ghi "không có trip đang mở", nhưng engine chỉ trả giá
  trị này khi **có** trip đang mở, trip đó chưa purchase và tổng ≥ 3 event dùng được. Engine
  coi trip đang mở là trip có event gần nhất trong 60 ngày (`ACTIVE_TRIP_MAX_AGE_DAYS`) — *luật tới 01/10/2026; từ đó theo
  bổ sung bên dưới (`usingDate`, N = 14).*
- `dormant`: trước 09/10 bảng này và `hop-dong-tich-hop-backend.md` §6.2 ghi 90 ngày, engine dùng 180. Từ 2026-10-09
  (đề xuất `update-archive/2026-10-09-persona-trang-thai-cold-start-va-phong-cach-du-lich.md`) cả hai là **365 ngày tính từ
  chuyến gần nhất** (`DORMANT_AFTER_DAYS`); `diagnostics.dormant` (event gần nhất > 90 ngày) của contract không đổi nghĩa.
- `< 3 event → popular`: engine trả `popular` khi không còn event nào dùng
  được (kể cả khách ẩn danh và CDP lỗi). Dưới 3 event mà có trip đang mở thì ra
  `cold_start_content`; chỉ có trip cũ thì ra `long_term` hoặc `dormant`.
- Ràng buộc 4 dưới đây: engine đặt `coldStart = eventsUsed < 3` nhưng vẫn sinh
  `because` khi có nguồn đạt ngưỡng, nên `coldStart: true` có thể đi kèm
  `because` khác rỗng. Mock `getRecommendations.200-cold-start-content.json`
  theo ràng buộc 4 (`because: []`).

**Bổ sung 2026-10-01 (FR-REC-02 sửa theo đề xuất `category-exclusion-theo-chuyen-dang-dien-ra`, đã chốt).** "Trip đang
mở" trong bảng trên là trip **chưa kết thúc** theo đúng định nghĩa `tripFactor` §4.3: `max(usingDate)` của các event trong
trip ≥ hôm nay; trip không có `usingDate` nào (chỉ view / search) thì mở khi event gần nhất cách ≤ `ACTIVE_TRIP_MAX_AGE_DAYS`
(tham số N của PRD: **14 ngày** từ 01/10, trước là 60 — đo trên split temporal đóng băng, `docs/spec/bench/recsys-offline-eval.md`
§4.14 v5 (`usingDate` + N = 14): Recall@20 0,196 → 0,216, LLBO không đổi; grid §4.13 với luật tuổi đơn thuần N = 14 cho 0,225
vì luật đó đóng luôn chuyến chưa đi tại T). Trip đã kết thúc không còn là trip mở dù mới 5 ngày trước → khách rơi về `long_term` /
`dormant`, engine gợi cho chuyến kế tiếp. Trip mua từ lâu nhưng `usingDate` còn ở tương lai vẫn là trip mở (chuyến sắp đi).
`usingDate` của event CDP là **ngày bắt đầu sử dụng** (check-in / ngày bay) và CDP không có ngày kết thúc, nên kỳ nghỉ nhiều
đêm được coi là xong từ ngày sau check-in; muốn giữ trip mở suốt kỳ nghỉ cần thêm số đêm / ngày kết thúc vào event (đề xuất PRD
riêng, chưa có). Tuổi trip, ngày kết thúc và món đã mua xét trên **mọi** event của trip; cap `MAX_REPEAT_PER_TRIP` chỉ giới hạn
trọng số vector. "Hôm nay" lấy theo giờ Việt Nam (UTC+7, `profile.local_today`) để khớp `usingDate` là ngày địa phương.
Engine ghi `ENGINE_RULES_VERSION` vào cấu hình để bench phân biệt hai luật.

**Bổ sung 2026-10-09 (FR-REC-02, đề xuất `update-archive/2026-10-09-recsys-uu-tien-chuyen-da-dat.md`, đã chốt).** Khi có nhiều
trip đang mở, trip **có purchase** (chuyến đã đặt) trẻ nhất là trip mở; chỉ khi không có trip đã đặt nào đang mở thì mới lấy trip
mở trẻ nhất như cũ. Trước đó một view / giỏ lẻ đến sau (`_solo_<productId>`, tuổi nhỏ hơn) chiếm chỗ chuyến đã đặt nên khách mất
`cross_vertical` và luật loại loại sản phẩm đã mua (lỗi I-3, `docs/spec/bench/recsys-offline-eval.md`). `ENGINE_RULES_VERSION =
"2026-10-09-booked-first"`; gương harness: `ceiling.engine_view`, `splits.excluded_taxonomies`, `arms.trip_destination`.

**Bổ sung 2026-10-09 (FR-REC-02, đề xuất `update-archive/2026-10-09-recsys-diem-xuat-phat-va-phien-xem.md`, đã chốt).** Không có
trip đã đặt nào đang mở nhưng có **≥ 2 trip chỉ-xem / giỏ đang mở** → engine gộp chúng thành **một chuyến ảo** (`_session_`):
vector = chuẩn hoá Σ `2^(−tuổi/H_SESSION_DAYS)` · độ tin cậy · vector trip (`H_SESSION_DAYS = 7`); điểm đến = điểm đến có tổng trọng
số lớn nhất (hoà → điểm đến của trip trẻ nhất); `purchasedTaxonomies` rỗng; event = hợp event các trip (dùng cho `because[]`).
Chuyến ảo không nằm trong `diagnostics.trips` và không đổi `eventsUsed`. Một trip chỉ-xem → giữ nguyên trip đó.
`ENGINE_RULES_VERSION = "2026-10-09-origin-session"`; gương harness như bổ sung trên.

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
excluded       = bookedThisTrip
```

Áp làm **hard filter trong câu truy vấn**, không phải phép trừ vector. Ngoài ra
loại mọi `productId` khách đã từng mua (luật dưới).

**Không gợi lại sản phẩm đã mua + combo ↔ thành phần (FR-REC-02, chốt 2026-10-09, đề xuất
`docs/prd/update-archive/2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md`).** Trong **mọi** nhánh (chuyến mở, chuyến kế
tiếp, request khoá `destination`), engine loại khỏi ứng viên:

- mọi search unit khách đã mua trên **toàn bộ lịch sử** (`purchase`, kể cả sản phẩm chưa có vector), theo search unit: mua một
  hạng phòng là đã mua khách sạn đó, mua một chuyến bay là đã mua tuyến đó;
- **đóng một bậc qua combo**: mua một sản phẩm → mọi combo chứa nó; mua một combo → mọi thành phần của combo đó. Không bắc
  cầu: mua combo A không loại combo B chỉ vì B chung thành phần với A.

Quan hệ combo → thành phần lấy từ `catalog.combo_items` và chỉ tin dòng **đã map** (`item_product_id NOT NULL`) với
`confidence ≥ 0,8` **hoặc** `source = 'manual'` (`infrastructure/vectors/postgres_store.combo_members_of`,
`COMBO_MEMBER_MIN_CONFIDENCE`); dòng chỉ khớp theo địa điểm (0,60) không dùng. Tập đã mua tính ở
`application/recommendation/use_cases.bought_units` → `UnitIndex.purchase_closure`; harness bench dùng cùng hàm. Luật cũ "combo
kéo theo hotel" (loại *taxonomy* hotel khi mua combo) **không** nằm trong luật này và chưa cài — ngoài phạm vi. Cold start
(`popular`) không có lịch sử nên không đổi.

**Chỉ áp cho trip đang mở** theo định nghĩa §4.4 (bổ sung 2026-10-01): chuyến đã kết thúc (`usingDate` đã qua) thì không
loại taxonomy đã mua và không khoá điểm đến — đó là gợi ý cho chuyến kế tiếp (PRD FR-REC-02). Lý do: trên split temporal
của bench, 22 % target bị chính exclusion / khoá điểm đến của chuyến đã đi xong chặn (`docs/spec/bench/recsys-offline-eval.md`
§4.7, §4.11).

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
final = W_SHORT · cos(u_short, v_c) + W_POP · pop_D(c) + W_LONG · cos(u_long, v_c)
W_SHORT / W_POP / W_LONG = 0.7 / 0.15 / 0.15
```

`u_short` = vector chuyến đang mở (không có chuyến mở thì dùng `u_long`); `pop_D` = mức phổ biến của ứng viên. **Điểm xuất phát
chuyến bay (FR-REC-04, chốt 2026-10-09):** `origin` = `originCity` của route bay mà khách xem / thêm giỏ / mua gần nhất
(`profile.infer_origin`); route bay có `originCity` khác rỗng và khác `origin` bị trừ `W_ORIGIN = 0.15` khi có chuyến mở, bị loại
(điểm −∞, MMR không chọn) khi không có chuyến mở; chưa có event chuyến bay → không áp dụng. `use_cases` truyền
`ScoreContext(taxonomy, originCity, origin)` cho `score_candidates`.

**Không có chuyến mở (FR-REC-04 / FR-REC-02, chốt 2026-10-09, đề xuất
`update-archive/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md`, PR-B):**

```
s     = clip((cos(u_long, v_c) − SEMANTIC_Q_LOW) / (SEMANTIC_Q_HIGH − SEMANTIC_Q_LOW), 0, 1)     # 0.8529 / 0.9387
final = W_NEXT_SHORT · s + W_NEXT_POP · pop_D(c) + W_NEXT_LONG · s                               # 0.50 / 0.35 / 0.15
```

Ngưỡng calibrate trên 120 request khách giả lập `between` (seed 99) theo phân vị p10 / p99 của cos trên không gian ứng viên của
engine; gắn với `SEMANTIC_CALIBRATION_MODEL_VERSION = "intfloat/multilingual-e5-small:catalog-text-v2"`. `index.model_version`
khác tag → dùng công thức 0.7 / 0.15 / 0.15 và ghi WARNING `recsys.next_trip_scoring.model_mismatch` (một lần mỗi model). Đổi
model / text builder thì calibrate lại bằng `python -m src.evaluation.recsys_bench.theme_study.calibrate`. MMR khi đó giới hạn
`MAX_PER_DESTINATION = 2` món mỗi điểm đến (`mmr_select(..., destination, max_per_destination)`, điểm đến lấy tại thời điểm MMR);
**không** áp khi request khoá `destination`. Luật điểm xuất phát chuyến bay ở trên vẫn áp sau F14c. Rollback không redeploy:
`RECOMMEND_NEXT_TRIP_SCORING=false`, `RECOMMEND_MAX_PER_DESTINATION=0`. `ENGINE_RULES_VERSION = "2026-10-09-next-trip-f14c"`. Hằng nằm ở
`src/backend/app/domain/recommendation/profile.py` (`W_SHORT, W_POP, W_LONG`). Trọng số chốt 2026-10-07, thay 0.6 / 0.25 / 0.15
(`docs/prd/update-archive/2026-10-06-recsys-trong-so-ngan-han-pho-bien.md`; số đo: `src/evaluation/reports/eval-2026-10-06-recsys-search-tong-hop.md`
phần A §4, `eval-2026-10-07-recsys-grid-llbo-coldstart.md`).

Sau đó MMR re-rank với `λ = 0.7`, cộng giới hạn cứng tối đa 2 kết quả mỗi
`parentProductId`.

Lấy trung bình vector kéo kết quả về cùng một cụm; không có bước này thì top-5
hay là 5 biến thể của một resort.

**Ô khám phá khi có chuyến mở (FR-REC-02, chốt 2026-10-09, đề xuất
`docs/prd/update-archive/2026-10-08-recsys-o-kham-pha-khi-co-chuyen-mo.md`).** Khi khách có chuyến mở tại X và sau MMR danh
sách tại X còn **ít hơn `k` món** (hết món hợp lệ tại X), engine lấp các ô còn trống bằng món ở điểm đến khác:

```
mask_B = recommendable ∧ destination ≠ X ∧ taxonomy ∈ {hotel, attraction, combo} ∧ ∉ đã mua (kể cả closure combo)
xếp theo cos(u_long, v) qua một lượt near_vector(u_long, mask_B, EXPLORE_CANDIDATE_K = 50)
tối đa EXPLORE_MAX_PER_DESTINATION = 1 món mỗi điểm đến; lấy đúng k − |món tại X| món
```

Món tại X **không bị thay** và đứng trước; món khám phá nối sau với `rank` liên tục, `score = cos(u_long, v)`, `because[]` phân
rã theo `u_long` (mọi chuyến, không chỉ chuyến mở). `strategy`, `destination`, `nextVertical`, `excludedVerticals` vẫn tính trên
món tại X. Request khoá `destination = X` cũng lấp (trang xác nhận: khách thấy cả hai nhóm). Không chuyến mở → không lấp
(nhánh chuyến kế tiếp vốn không khoá điểm đến). `diagnostics.exploreFilled` = số ô đã lấp (0 khi không lấp; trường chỉ có ở
nhánh có lịch sử). Công tắc `RECOMMEND_EXPLORE_FILL=false` (Settings) tắt luật mà không redeploy → list y hệt trước 09/10. Chi
phí: thêm một lượt `near_vector` chỉ khi còn ô trống — đo đầu-cuối ở `src/evaluation/reports/` (latency TRƯỚC / SAU PR-A).
Số nghiên cứu (`eval-2026-10-08-recsys-g2-va-wp4.md`, `--how ulong`): hit@4 không đổi, +1 điểm đến ở 29 % khách có chuyến mở.

### 4.8. Cold start, dormant, ẩn danh

**Cold start** (dưới 3 event) — fallback theo thứ tự:

```
1. Có destination trong request → phổ biến nhất trong điểm đến đó, tối đa 2 mỗi taxonomy
2. Có profile.homeCity          → điểm đến phổ biến từ thành phố đó
3. Còn lại                      → most-popular toàn hệ thống, tối đa 2 mỗi taxonomy
```

Trần "tối đa 2 mỗi taxonomy" (`MAX_PER_VERTICAL`, chốt 2026-10-12) áp cho cả danh sách của từng điểm đến, danh sách phẳng
ghép từ các section điểm đến, và nhánh xếp theo `reviewCount` khi chưa có bảng phổ biến. Lý do: lượt mua chuyến bay dồn về
tuyến, nên khi không có trần thì 2–3 món đầu ở các điểm đến lớn đều là tuyến bay. Trần đi theo taxonomy của engine
(golf là taxonomy riêng), khác các nhóm của `GET /products?diversify=taxonomy` (backend §4.1). Harness eval
(`max_per_vertical=None`) không có trần.

**Dormant** (chuyến gần nhất > 365 ngày, từ 09/10): vẫn dựng user vector như khách có lịch sử. `halfLifeDays × 3` và
`lastDestination` của bản thiết kế ban đầu **không** cài — bench 09/10 (`src/evaluation/reports/eval-2026-10-09-recsys-cong-thuc-oph.md`)
không thấy tác dụng của `H_LONG × 3` và `lastDestination` lấy từ snapshot lộ đáp án.

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
| `POST /search` | 300 ms (Weaviate cùng mạng nội bộ; qua Weaviate Cloud từ mạng dev thì mỗi lượt thêm 0,5–2 s) |
| `GET /products/{id}/similar` | 300 ms |
| `GET /recommendations`, cache hit | 300 ms |
| `GET /recommendations`, cache miss (đọc 500 event từ CDP) | 800 ms |
| Embed một truy vấn | p95 ≈ 11 ms khi `embedCache = miss` (e5-small trên CPU laptop; Cohere trước đây ≈ 60 ms, p95 437 ms trên VM); hit ≈ 0 ms — từ 30/09 vector truy vấn được cache (§2.2), số đo thật ở `docs/spec/bench/search-eval-results.md` |

Đo thật 01/10/2026 trên VM (`release-mvp-v2`, contract 1.12.0; Weaviate Cloud ở `eu-central-1`, VM ở `asia-southeast1`):
`/search` p95 **4,0 s** = dense 1,8 s + BM25 2,1 s nối tiếp (mỗi lượt gửi mask 3.146 id); embed cache hit 0 ms, miss p95 437 ms.
Ngân sách 300 ms ở bảng trên chỉ đạt được khi kho vector cùng vùng với backend — số và nguyên nhân ở
`docs/spec/bench/search-eval-results.md` §2–3, report `src/evaluation/reports/eval-2026-10-01-search-cloud-latency.md`.

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

**Ghi `app.search_logs` (từ 2026-10-06, cờ `SEARCH_LOG_QUERIES`, mặc định tắt; kiến trúc §11):** route `/search` ghi một dòng
cho trang đầu của câu thật — `query`, `filters` (taxonomy/destination của request + `appliedFilters.hard` + `queryPlan.confidence`),
`result_product_ids`, `result_count`, `model_version`, `latency_ms`, `cdp_user_id` chỉ khi request đã xác thực (token lỗi → NULL,
không 401). Ghi ngoài đường request (hàng đợi 1.000 dòng, một luồng ghi), lỗi ghi không bao giờ lên response. Bảng này là nguồn
head query cho prewarm (§2.2) và cho hole detection / gold mới (bench).

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
2. Đổi `limit`/`offset` (trong phạm vi `candidateK`), giữ nguyên filter → `total` và `facets` **không đổi**.
3. `sum(facets.taxonomy) == total` trên mọi truy vấn (tính trên tập ứng viên).
4. Mọi `results[].score >= cutoff`; ở `HYBRID_CANDIDATE_SCORE` phần vớt từ BM25 có
   `score >= diagnostics.lexicalCutoff` và đếm đúng bằng `diagnostics.lexicalCount`.
5. Truy vấn vô nghĩa → `results: []`, `topScore: null`, `backgroundScore: null`.
6. ≥ 95% cặp đúng trong bộ 80 cặp có `score >= cutoff`.
7. Cả 10 truy vấn âm rơi vào nhánh weak (theo abs hoặc theo margin).
8. `availableOnly: true` không trả sản phẩm `available: false`.
9. Mặc định không có sản phẩm `level: room` trong `results`.
10. `diagnostics.searchMode: HYBRID_CANDIDATE_SCORE` (hoặc `ANN_CANDIDATE_SCORE` khi `SEARCH_HYBRID=false`),
    `approximate: true`, `totalExact: false`, `facetsExact: false`.
10b. `search("VinWonders")` → có kết quả tên chứa VinWonders ở top và `diagnostics.lexicalCount >= 1` khi
    cosine của chúng dưới `cutoff`; `search("khách sạn ở Cà Mau")` → `diagnostics.lexicalCount == 0` (không vớt
    tên chỉ trùng một âm tiết). Nhánh dense của truy vấn ngoài catalog vẫn có thể trả kết quả ≥ cutoff — đó là
    việc của S1 (cutoff), không phải của hybrid.
10c. `search("KS ở PQ có hồ bơi")` → `diagnostics.normalizedQuery == "khách sạn ở Phú Quốc có hồ bơi"`;
    `search("Vinpeal Resort Nha Trang")` → `corrections` có Vinpeal → Vinpearl và top-1 như câu viết đúng;
    `search("khach san co ban cong")` → không có `corrections`; `search("chỗ nghỉ Đà Lạt đi cùng bạn gái")` →
    `party: COUPLE`, `normalizedQuery` chứa "cặp đôi".
10d. (07/10, cờ `SEARCH_DURATION_FILTER`) `search("VinWonders 3 ngày 2 đêm")` → `queryPlan.duration == {days: 3, nights: 2,
    source: query}`, `queryPlan.lexicalText == "VinWonders"`, `applied` chứa `duration`, không có `appliedFilters` khi không có
    filter khác đang áp (riêng cờ này bật); kết quả
    không còn hotel chỉ trùng "ngay"/"đêm" trong tên (ví dụ "… Ngay Trung Tâm & Chợ Đêm", "… ngay BẾN NINH KIỀU & CHỢ ĐÊM").
    `search("resort 2 triệu/đêm Phú Quốc")`, `search("khách sạn gần chợ đêm Đà Lạt")` → không có `queryPlan.duration`.
10e. (07/10, cờ `SEARCH_POI_RESOLVE` + `SEARCH_DEST_FILTER`) `search("khách sạn gần Hồ Hoàn Kiếm")` →
    `diagnostics.destinationFilter == {source: query, value: "Hà Nội"}`, `appliedFilters.hard.destinationSource == "poi"`,
    `queryPlan.location == {key: ho_hoan_kiem, name: "Hồ Hoàn Kiếm", kind: landmark, destination: "Hà Nội"}`,
    `derivedDestinations == ["Hà Nội"]`, mọi kết quả ở Hà Nội; `search("khách sạn gần Hồ Gươm hoặc Hồ Tây")` → cũng Hà Nội;
    `search("khách sạn Hà Nội gần Cầu Rồng")` → `destinationFilter.skipped == multi`, không lọc; `search("vé máy bay HAN DAD")`
    (F5 bật) → điểm đến Đà Nẵng suy từ IATA không bao giờ khai `destinationSource = poi`, không có `queryPlan.location`.
10f. (07/10, cờ `SEARCH_ENTITY_FILTER`) `search("VinWonders Nha Trang")` → mọi `results[]` là attraction/combo có tên chứa
    VinWonders, `appliedFilters.hard.entity == ["vinwonders"]`, `queryPlan.entity == {keys: [vinwonders], role: gate}`,
    `sum(facets.taxonomy) == total` vẫn đúng; cùng câu với `taxonomy=hotel` → `total 0`, `queryPlan.emptyReason == "entity"`;
    `search("khách sạn ở Grand World Phú Quốc")` → `entity.role == location`, `applied` không có `entity`, kết quả vẫn có khách sạn;
    `search("vé lẻ VinWonders Nam Hội An, không lấy combo")` (F3 bật) → `applied` có `mustNot` và `entity`, không có combo;
    `search("không lấy VinWonders, vé Safari")` → `hard.entity == ["safari"]`. Cả ba cờ tắt → response không có
    `queryPlan.duration` / `location` / `entity`, y như 1.17.0.
11. p95 dưới 300 ms trên catalog đầy đủ, đo với Weaviate cùng mạng nội bộ (local hoặc cùng region).
    *(Bổ sung 2026-09-29: PRD NFR-PERF-01 đặt ngưỡng chặt hơn, ≤ 250 ms; báo p95 tổng kèm p95 từng bước theo
    `diagnostics.stageMs` để thấy phần nào là embed, phần nào là Weaviate. Bổ sung 2026-09-30: báo p95 riêng cho
    `embedCache = hit` và `miss`; ngưỡng 250 ms áp cho đường hit, đường miss = hit + một lần embed e5-small.)*

### Similar

12. `/similar` với id một hạng phòng → `productId` trả về là property cha,
    `resolvedFrom` là id đã gửi.
13. Kết quả **không chứa** hạng phòng anh em cùng `parentProductId`.
14. `strategy=same_taxonomy` không trả taxonomy khác.
15. Mock `embedQuery` ném exception mà `/similar` vẫn chạy — chứng minh không embed lại.

### Recommendation

16. Đăng nhập lần lượt 4 tài khoản demo → 4 `strategy` khác nhau.
17. P1 vừa đặt hotel Nha Trang → `strategy: cross_vertical`, không có item
    `taxonomy: hotel`, `nextVertical` khác `null`. *(Từ 01/10 "vừa đặt" = chuyến chưa diễn ra xong: seed gắn `usingDate`
    cho P1 ~2 tuần sau `--as-of`, nên seed lại trước demo; quá ngày sử dụng P1 rơi về `long_term`.)*
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
27. Khách đã mua phòng của khách sạn H (bất kỳ lúc nào) → không có H lẫn combo chứa phòng/khách sạn H trong list; khách đã
    mua combo C → không có C lẫn các thành phần đã map tin cậy của C; combo khác chung thành phần với C vẫn có thể xuất hiện
    (§4.5, AC-REC-02/03; unit test `test_recommendation_combo_exclusion.py`).
28. Khách có chuyến mở tại X mà X còn ít hơn `k` món hợp lệ → list = món tại X trước, rồi món ở điểm đến khác (mỗi điểm đến
    ≤ 1, chỉ hotel / attraction / combo), `rank` liên tục, `strategy` / `nextVertical` không đổi so với khi không lấp,
    `diagnostics.exploreFilled` = số ô lấp; `RECOMMEND_EXPLORE_FILL=false` → không lấp (§4.7; unit test
    `test_recommendation_explore_fill.py`).

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
| S7 | ~~Model embedding chưa chốt~~ — **đổi 06/10/2026** | `intfloat/multilingual-e5-small`, **384 chiều**, chạy local trong backend, tiền tố `query: ` / `passage: `, collection `ProductE5Small` (`VECTOR_COLLECTION`) (thay Cohere `embed-multilingual-v3.0` 1024 chiều chốt 22/09; Cohere bỏ hẳn, không còn đường lui). Xem `docs/prd/architecture.md` §4–§5, `docs/prd/update-archive/2026-10-05-fr-src-02-embedding-local-e5-small.md`, `docs/prd/update-archive/2026-10-06-bo-duong-lui-cohere.md`. Kéo theo S8. |
| S8 | ~~`EXACT_FILTER_SCORE` cần duyệt lại~~ — **đã chốt 24/09/2026, hướng (b)** | Đổi cam kết `total`/`facets` thành xấp xỉ trên tập ứng viên, khai báo qua `approximate`/`totalExact`/`facetsExact`. `/similar`, `/recommendations` chạy `ANN_CANDIDATE_SCORE`; `/search` chạy `HYBRID_CANDIDATE_SCORE` từ 25/09 (§2.4). |
| S9 | `lexicalK` / `lexicalCutoff` / `lexicalMinCoverage` của hybrid chưa benchmark | Dùng `10` / `0.50` / `0.6`; đo ở cổng S2 của bench (`docs/spec/bench/arms.md`) trên gold, kèm slice `named_entity`, `no_diacritics`, `out_of_catalog` |
| S10 | Bảng viết tắt, cụm kiểu đi và ngưỡng sửa chính tả của bước chuẩn hoá chưa benchmark | Dùng bảng trong `domain/search/normalize.py`; đo trên slice `abbrev_typo`, `audience_style` (bench Part 6, cổng S3/S6). Bảng backend là nguồn cho `config/aliases.yaml` của bench |
| S12 | Từ vựng tiện ích và cue phủ định (F3) — **đã đo 06/10** trên `gold_v5` (`src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md`): `amenity_negation` nDCG@10 0,303 → 0,762, Forbidden@10 0,539 → 0,225 (một mình) / 0 (tổ hợp F1–F6); bỏ F3 khỏi tổ hợp LOSE (−5,2) | Cờ `SEARCH_NEGATION_FILTER` vẫn tắt tới khi người dùng chốt bật (đề xuất: bật). Danh sách tiện ích nguồn dừng ở 60 chuỗi ở một số khách sạn → tiện ích bị loại trừ có thể vắng (Data) |
| S13 | Bảng cue loại sản phẩm + guard thương hiệu (F4) — **đã đo 06/10**: `taxonomy_collision` +21,8; cue chỗ nghỉ giữ 99–100 % item đúng (dev/test), tên điểm vui chơi 47–73 % → yếu (`WEAK_VERTICAL_CUES`); F4 đủ +2,4 trên mốc; chỉ-cue-mạnh thua F4 đủ 1,1 (TIE); bỏ F4 khỏi tổ hợp → LOSE (−2,1), Forbidden 0,065. Bật đổi số đếm tab của Web | Cờ `SEARCH_TAXONOMY_FILTER` tắt; đề xuất bật **cần ý kiến Web**; `SEARCH_TAXONOMY_STRONG_ONLY` giữ tắt |
| S14 | Mẫu giá/sao và vai trò nơi đi/đến (F5/F6) — **đã đo 06/10**: chiều bay 0,11 → 1,00; constraint precision 0,79 → 0,92 (0,96 trong tổ hợp); nDCG TIE từng phần, bỏ khỏi tổ hợp làm hỏng guard | Cờ `SEARCH_ROUTE_FILTER` / `SEARCH_NUMERIC_FILTER` tắt tới khi chốt (đề xuất: bật); tham số request tường minh vẫn áp theo contract |
| S15 | Kênh fuzzy tên, RRF trọng số, chuẩn hoá dấu thanh, lọc số khách suy từ câu (1.16.0) — đo 06/10: fuzzy −0,6 (ngưỡng 0,75) / −1,2 (0,6); lexical weight 0,5 +1,2 trên F1–F6 (TIE dev/test cùng chiều); tone 0,0; party −0,6 — gold gần như không có câu dấu thanh lệch / số khách | Giữ tắt (`SEARCH_FUZZY_K=0`, trọng số 1,0, `SEARCH_TONE_NORMALIZE` / `SEARCH_PARTY_FILTER` false); cần gold riêng trước khi bật |
| S16 | Ngưỡng kết quả yếu trên e5 (S2) — đo 06/10 trên dev/test: margin **0,058** chặn 3/3 + 4/4 câu ngoài catalog, gắn weak nhầm 9–12 % câu trong catalog (0,06: 14–16 %); cutoff tuyệt đối không chặn câu ngoài catalog nào | Client dùng margin 0,058 khi người dùng chốt; S2 giữ "chưa chốt" (7 câu ngoài catalog, nền tính trên cả catalog) |
| S17 | Ghi `app.search_logs` (`SEARCH_LOG_QUERIES`) chưa chạy trên Postgres thật. LLM fallback cho câu độ tin cậy thấp — đề xuất **đã chốt, đã áp dụng 06/10** (`docs/prd/update-archive/2026-10-06-search-llm-fallback-query-plan.md`), ship contract 1.17.0 (`queryPlan.llm`, `stageMs.llm`); đo 06/10: gpt-4o-mini kích hoạt 10/59 câu (ngưỡng 0,75 / 1,0), 0 trường nhận, nDCG không đổi | `SEARCH_LOG_QUERIES` tắt; `SEARCH_LLM_FALLBACK=off` (shadow/on khi có bằng chứng trên gold); wiring production bị merge `21d72ae` làm mất, khôi phục 07/10 (`history/2026-10-07-restore-search-prod-defaults-llm-fallback.md`) |
| S18 | Thời lượng F7, địa danh gazetteer → F1, cổng entity cứng (contract 1.18.0, 07/10; spec `docs/spec/bench/tong-hop-chinh-sua-luong-search-ota.md`, plan `docs/plan/2026-10-07-search-duration-entity-poi.md`) — **chưa đo**: probe fixture c0736–c0756 rồi `gold_v6` (slice `duration_false_positive`, `poi_resolution`), arm `APP.e5s.prod_f12356_dur` / `_poi` / `_ent` / `_dur_poi_ent` | Ba cờ `SEARCH_DURATION_FILTER` / `SEARCH_POI_RESOLVE` / `SEARCH_ENTITY_FILTER` tắt tới khi bench WIN/TIE trên test + Forbidden@10 = 0 + guard + 12 qid hồi quy + p95 không tăng > 30 %; `SEARCH_ENTITY_FILTER` còn cần Web xác nhận (tab Lưu trú có thể 0, `docs/spec/product.md` §4.2.3). Gazetteer là bảng tay trong repo — địa danh ngoài bảng không resolve (Data/Search bổ sung khi có hole) |
| S11 | Kích thước cache vector truy vấn (10.000), danh sách prewarm (131 câu gold_v1 + head query `app.search_logs` — bảng này chưa có code ghi) và pacing 2.000 câu/phút chưa đo | Dùng mặc định trong `core/config.py`; đo hit/miss bằng `sb latency http` (bench Part 9) trên Cloud; đổi số qua biến môi trường `SEARCH_EMBED_CACHE_*`, `SEARCH_PREWARM_*` |

S5 là phụ thuộc nặng nhất: không duyệt `[P3]` thì tiêu chí nghiệm thu 26 không
đạt được, và ngân sách §7.1 phải sửa.

---

## 11. Definition of Done

> Team Backend gọi được cả ba endpoint bằng mock sinh từ
> `src/shared/contracts/schemas/`, rồi đổi sang engine thật mà không phải sửa
> tầng `services`. Team Agent dựng được lịch trình 3 ngày mà mọi `productId`
> trong đó truy nguyên về một kết quả Search hoặc Recommendation trong cùng
> request (tool gọi engine trong tiến trình, hoặc response của `/search`,
> `/recommendations` ở mode `http`).

Luồng nghiệm thu bắt buộc:

```
Đăng nhập P1
→ Home hiện gợi ý kèm because có contribution
→ Tìm "nghỉ dưỡng biển cho gia đình" → kết quả hợp lý, facets cộng bằng total
→ Mở chi tiết → /similar trả cùng taxonomy, không trả hạng phòng anh em
→ Thêm giỏ → checkout
→ Quay lại Home → strategy đổi sang cross_vertical, nextVertical khác null
```
