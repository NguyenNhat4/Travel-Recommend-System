# Kế hoạch `/search` 1.30.0: cổng bằng chứng theo cụm, trả rỗng khi câu chỉ có tên lạ, thời lượng theo vai trò (P0) · trường BM25 riêng + ablation text builder (P1)

> Nhánh nền **`release-mvp-v2`** (@3d059212, contract 1.27.0). Code search trên nhánh này khớp `fix/search-count` @1873f4d5 (đã diff 13/10: chỉ thêm `StageTimer.record`, cấu hình recsys/agent, preload vector) → trích dẫn `domain/search`, `use_cases.py` còn đúng; số dòng `main.py`/`config.py` đọc lại ở Bước 0.1. Đề xuất PRD đi kèm: `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md` (chờ chốt).

- **Phục vụ:** **FR-SRC-01**, **FR-SRC-03**, **FR-SRC-04**, **AC-SRC-01**, **NFR-PERF-01** (p95 ≤ 250 ms), **NFR-REL-01** — `docs/prd/requirements.md`. Contract §9 AC 5 ("truy vấn vô nghĩa → `results: []`"), AC 7, AC 10b — `docs/spec/hop-dong-tich-hop-search-recommendation.md`.
- **Phạm vi P0:** backend `/search`, contract OpenAPI **1.30.0 additive** (lấy minor kế tiếp tại thời điểm Bước 4 nếu nhánh khác đã chiếm 1.30.0), frontend banner + empty state, bench + gold, spec. **Không** DDL, **không** re-embed, **không** thêm vector, **không** thêm tham số request. Mọi cờ mới mặc định **tắt** → response byte-identical 1.27.0.
- **Phạm vi P1:** trường BM25 riêng (backfill lexical, không re-embed) + ablation text builder T0–T5.
- **Đầu vào:** `H:/study/VIN20K/VSF/ke_hoach_xu_ly_false_positive_e5_dense_bm25.md`, probe live 13/10 (read-only), `docs/plan/2026-10-07-search-duration-entity-poi.md` (tiền lệ F7/entity role), report `eval-2026-10-06-search-query-plan-gold-v4.md`, `eval-2026-10-07-search-duration-entity-poi.md`, `eval-2026-10-05-search-e5s-dest-nodia.md`.
- **Trạng thái:** đề xuất PRD Bước 1 **đã chốt** (tqanh123, 13/10) và PRD đã cập nhật (FR-SRC-03, FR-SRC-04, deployment-plan §2) — làm tiếp từ Bước 0; Bước 0.3 vượt ngưỡng chặn nhầm thì mở đề xuất sửa trước khi code Bước 5.

## Quyết định đã chốt (13/10) — thắng các mục dưới khi mâu thuẫn

| # | Quyết định | Nội dung |
|---|---|---|
| Q1 | Thời lượng **có lọc, theo vai trò** | Suy `durationDays/Nights` từ tên/`suggestedDuration`/`attributes.nights` cho `attraction`/`combo`. Lọc cứng **chỉ** trên hai taxonomy này; khách sạn **không bao giờ** bị loại vì thời lượng (§2.3). |
| Q2 | Tên lạ → **trả rỗng + giải thích** | Chỉ khi residual (sau khi trừ mọi filter + cue loại) **toàn bộ** là cụm không giải thích được **và** cụm có dạng tên riêng, hoặc cả câu không chữ nào có nghĩa trong catalog. Cụm lạ khác ("rẻ bèo", "sống ảo") chỉ bị bỏ khỏi truy vấn, vẫn tìm tiếp (§2.6). |
| Q3 | Plan gồm P0 + P1 chi tiết | |
| Q4 | Đề xuất `2026-10-06-search-hybrid-min-coverage-rrf.md` bị thay thế | `git mv` sang `update-archive/` với trạng thái `từ chối (thay bằng …)` sau khi chốt. |
| Q5 | Không thêm vector | Tên/alias = lexical; tiện ích = filter; description_vector chỉ xét sau ablation P1. |
| Q6 | Cổng bằng chứng **chỉ** cho nhánh lexical | Dense vẫn nhận theo cosine như hôm nay; cổng chỉ quyết BM25 có được vớt / cộng điểm hay không (§2.1–2.2). |
| Q7 | Contract **1.30.0**, nhánh nền `release-mvp-v2` | Ghim: `openapi.yaml:4`, `main.py:889`, `test_search_contract.py:144`. |

---

## 0. Tóm tắt

### Lớp lỗi (đã xác minh bằng code + probe live)

| Mã | Cơ chế | Code | Bằng chứng live |
|---|---|---|---|
| C1 | Cosine tuyệt đối 0,84 (0,80 khi không dấu) nhận hàng trăm unit sát sàn | `hybrid.py:75`, `use_cases.py:346-348` | "2 ngày 1 đêm" 204; "nguyen khac tiep" 214; "resort ở Mộc Châu" 91 |
| C2 | RRF cộng hạng BM25 của **mọi** hit OR (khớp 1 âm tiết vẫn được đẩy lên) | `hybrid.py:85` | "3 ngày 2 đêm Đà Lạt" → #1 "Chợ Đêm Đà Lạt"; "Nguyễn Khắc Tiệp Đà Lạt" → #1 "Đường Hầm Điêu Khắc" |
| C3 | Độ phủ = túi âm tiết **đã bỏ dấu**, không thứ tự | `lexical.py:25,53`; `use_cases.py:273` | "Trần Thị Mai" → "Thị trấn Hoàng Hôn"; "Phạm Văn Đồng" → "Sân Vận động"; "Lê Văn Tám" → "Trung tâm Văn hoá" |
| C4 | Không có đường "câu không được giải thích"; span chỉ bỏ khỏi BM25, dense embed nguyên câu; thời lượng không lọc | `use_cases.py:361,427-428`; `query_plan.py:495-500` | "khách sạn Nguyễn Khắc Tiệp" → 153 KS |

### Luật chung, giải thích bằng ví dụ

1. **Tách "điều kiện" khỏi câu.** Điểm đến, loại sản phẩm, thời lượng, giá, số khách → bộ lọc. Phần còn lại = **residual**.
   - "khách sạn Nguyễn Khắc Tiệp" → lọc khách sạn; residual "Nguyễn Khắc Tiệp".
   - "khách sạn Đà Lạt rẻ bèo" → lọc Đà Lạt, khách sạn; residual "rẻ bèo".
   - "2 ngày 1 đêm" → lọc thời lượng; residual rỗng.
2. **Catalog có hiểu residual không?** So theo cụm 2 âm tiết liền nhau, đúng thứ tự, giữ dấu, với toàn bộ chữ của catalog (tên + mô tả).
   - "Nguyễn Khắc Tiệp": không cụm nào có **và** là dạng tên riêng (bắt đầu bằng họ Việt) **và** chiếm toàn bộ residual → **trả rỗng**: "Không tìm thấy 'Nguyễn Khắc Tiệp'".
   - "rẻ bèo": không có trong catalog nhưng không phải tên → **bỏ cụm này**, vẫn trả khách sạn Đà Lạt, kèm `unparsed: ["rẻ bèo"]`.
   - "xkcd qwzt": cả câu không chữ nào có → trả rỗng.
3. **BM25 chỉ được vớt / đẩy kết quả khi khớp đúng cụm, đúng thứ tự, đúng dấu.**
   - "Trần Thị Mai" ↔ "Thị trấn Hoàng Hôn": giữ dấu thì "Trần" ≠ "trấn", thứ tự ngược → BM25 không vớt.
   - "khách sạn gần biển" ↔ mô tả "…gần biển…": khớp cụm trong mô tả → BM25 vẫn được cộng điểm xếp hạng.
   - Dense không bị cổng này chặn: câu tìm theo nhu cầu/tiện ích chạy như hôm nay.

Kèm: embed residual (để "khách sạn" không kéo ra 153 khách sạn); lọc thời lượng cho vé/combo; câu không dấu phục hồi dấu thay vì hạ ngưỡng; nhãn "Kết quả gần nhất" khi điểm top chỉ nhỉnh hơn mặt bằng.

---

## 1. Mục tiêu

| # | Mục tiêu | Đo bằng | Mã |
|---|---|---|---|
| M1 | BM25 không vớt / đẩy unit chỉ khớp rời rạc, đảo thứ tự, mất dấu | slice `name_collision` `forbidden_at_10 = 0`; AC 10b `lexicalCount == 0` | FR-SRC-01, AC-SRC-01 |
| M2 | Câu chỉ có tên lạ / vô nghĩa trả rỗng + lý do | slice `no_answer` zero-result ≥ 90 % (dev và test); `emptyReason == unexplained` | FR-SRC-04, AC 5 |
| M3 | Câu có cụm lạ không phải tên vẫn trả kết quả | slice `slang_residual` (mới) zero-result = 0 | FR-SRC-04 |
| M4 | Thời lượng chỉ lọc vé/combo; khách sạn không mất | `duration_false_positive` + `duration_only` `forbidden_at_10 = 0`; `duration_stay` (mới, "khách sạn Đà Lạt 2 ngày 1 đêm") zero-result = 0 | FR-SRC-03 |
| M5 | Câu không dấu không hạ cutoff mà giữ recall | `no_diacritics` nDCG@10 không tụt > 3 điểm so với `prod_f12356` | FR-SRC-01 |
| M6 | Câu có đáp án không bị chặn nhầm | `named_entity`, `abbrev_typo`, `dest_type`, `amenity_*`, `audience_style`: `regress check` PASS; zero-result in-catalog ≤ 0,02 | test-plan §2.5 |
| M7 | Cờ tắt = không đổi; latency giữ | `topids-diff` identity rỗng; `test_search_v116_defaults` xanh; p95 tăng ≤ 30 ms | NFR-PERF-01 |

**Không làm ở P0:** vector phụ; DDL; tham số request mới; reranker online; LLM phân loại câu; fuzzy channel.

---

## 2. Thiết kế P0

### 2.1 Bằng chứng cụm giữ dấu — `domain/search/lexical.py`
- Thêm `syllables(s, keep_tone) -> list[str]` (NFC → lower → bỏ dấu nếu `keep_tone=False` → tách `[^\w]`), `bigrams(seq)`. Không đổi `fold` (BM25 + bench dùng chung).
- `Evidence(name_cov, name_bigram, text_bigram)` và `evidence(q_seq, unit) -> Evidence`, tính theo **chế độ dấu**: câu có dấu → âm tiết giữ dấu; câu không dấu → âm tiết fold (sau phục hồi dấu §2.5, phần đã phục hồi so giữ dấu).
- Hai mức bằng chứng:
  - **Bằng chứng tên** (dùng để **vớt** unit chỉ có ở BM25): residual 1 token → token có trong tên; ≥ 2 token → ≥ 1 bigram có trong tên **và** coverage tên ≥ `min_coverage`.
  - **Bằng chứng văn bản** (dùng để **cộng điểm RRF** cho unit dense đã nhận): residual 1 token → token có trong tên hoặc text; ≥ 2 token → ≥ 1 bigram có trong tên hoặc text (embed text).
- `SearchProducts` dựng lúc load (chỉ khi cờ bật), cạnh `_name_tokens` (`use_cases.py:273`): tập unigram/bigram giữ dấu + fold của tên và của text từng unit. Nguồn text: kiểm ở Bước 0.2 xem `UnitIndex` có embed text trong RAM không; không có thì dựng `name + description` (đủ cho bằng chứng, không cần đúng embed text).
- Phạm vi (Q6): cổng chỉ áp cho nhánh lexical. Unit vào R bằng cosine ≥ cutoff vẫn vào; câu tiện ích/phong cảnh ("resort có bãi biển riêng", "khách sạn yên tĩnh") không bị chặn.

### 2.2 Áp cổng trong fusion — `domain/search/hybrid.py`
- `HybridConfig.evidence_gate: bool = False`; truyền thêm `rrf_admissible: Callable[[int], bool]` (bằng chứng văn bản) cạnh `admissible` (bằng chứng tên).
- Bật:
  1. `kept_lex` (vớt): `admissible` = bằng chứng tên (thay coverage túi chữ).
  2. `rrf`: `lexical_rank` chỉ gồm unit `rrf_admissible` → khớp 1 âm tiết không còn đẩy thứ hạng.
  3. `kept_dense` **không đổi** (kể cả hit chỉ-BM25 có cosine ≥ cutoff: thực chất là dense bị cắt ở top-200, không phải khớp chữ).
- Tắt → code path cũ (test equivalence `_legacy_*` trong `test_hybrid.py`).

### 2.3 Thời lượng theo vai trò — `unit_attributes.py`, `unit_index.py`, `query_plan.py`
- `UnitAttributes`: `duration_days`, `duration_nights: tuple[frozenset[int], ...]` (rỗng = chưa biết), chỉ điền cho `attraction`/`combo` trong `build()`; nguồn: `attributes.nights` (nếu có — Bước 0.2), `suggestedDuration` "N ngày", tên "[N ngày]", "N ngày M đêm", "NnMd", "[Combo 01/02 ngày]" → {1, 2}. Tái dùng `parse_duration` (`constraints.py:920`). Không suy từ `durationMinutes`.
- Vai trò (trong `build_query_plan`, tiền lệ entity role của plan 07/10 §3.3), chỉ khi cờ `duration_mask`:
  - **`stay`**: câu có cue lưu trú **trong text** ("khách sạn", "resort", "homestay", "villa", "căn hộ", "phòng" — tái dùng `VERTICAL_CUES` taxonomy hotel) → thời lượng chỉ khai (`queryPlan.duration.role = stay`), **không mask**. "khách sạn Đà Lạt 2 ngày 1 đêm" → khách sạn Đà Lạt như hôm nay.
  - **`gate`**: các trường hợp còn lại (câu chỉ có thời lượng, hoặc cue vé/combo/tour) → mask.
- Mask `UnitIndex.mask(..., duration_days=None, duration_nights=None, duration_taxonomies=("attraction","combo"))`, sau khối entity (`unit_index.py:125-127`):
  - unit thuộc `duration_taxonomies`: phải có days khớp; nights đã biết thì phải khớp, chưa biết thì giữ.
  - unit thuộc taxonomy khác: **loại** khi role = gate (câu "2 ngày 1 đêm" không hỏi khách sạn); vai trò stay không gọi mask.
- Tab Web gửi `taxonomy=hotel` cho câu "2 ngày 1 đêm" (không cue lưu trú trong text) → gate → F rỗng → `emptyReason: duration`, tab Lưu trú (0) — giống tiền lệ entity gate. Tab vé/combo hiện các unit "[2 ngày]".
- `families_in_order` thêm bước `duration` sau `entity` → `emptyReason: duration` bắt đầu phát.

### 2.4 Embed residual — `use_cases.py`, `query_plan.py`
- Cờ `embed_residual`. `QueryPlan.dense_text` = `text` bỏ span đã consume (thời lượng, giá/sao, số khách, phủ định, cụm `unparsed` §2.6); **giữ** điểm đến, entity và cue loại (khi F4 tắt, cue là tín hiệu taxonomy duy nhất cho dense).
- "Nội dung" của `dense_text` = token còn lại sau khi bỏ stopword, cue loại (`VERTICAL_CUES` — "tour", "combo", "khách sạn", "vé máy bay"…), token điểm đến:
  - còn nội dung → embed `dense_text`.
  - hết nội dung **và** duration role = gate → **chế độ chỉ-filter**: R = toàn F (≤ `candidate_k`), không cutoff, thứ tự = cosine với câu đầy đủ (`score` vẫn là cosine), `diagnostics.filterOnly = true`. Vd "combo 3 ngày 2 đêm", "tour 2 ngày 1 đêm", "2 ngày 1 đêm".
  - hết nội dung, không có gate ("khách sạn Đà Lạt") → embed **câu đầy đủ** như hôm nay (không đổi hành vi).
- Khoá cache embed = chuỗi thật sự embed; `query_text()` (`use_cases.py:470`) dựng plan để prewarm cùng khoá.

### 2.5 Phục hồi dấu thay cho nới cutoff — `normalize.py`, `config.py`, `main.py`
- `search_no_diacritics_mode: off | relax | restore` (thêm `restore`; `relax` giữ để rollback).
- Bảng n-gram (n = 2…`MAX_ALIAS_TOKENS`) `fold → surface` dựng từ tên catalog, destination, alias gazetteer (cạnh `self._surface`, `normalize.py:153-170`); mỗi n-gram fold giữ surface đa số **nếu** chiếm ≥ 80 % lần xuất hiện, không thì bỏ (tránh mơ hồ).
- Thuật toán: chạy sau pass alias (đã đổi "dalat" → "Đà Lạt" qua `DESTINATION_ALIASES`), quét trái → phải, tại mỗi vị trí thử **n-gram dài nhất trước** (gazetteer/destination ưu tiên trên tên catalog), khớp thì thay và nhảy qua; không khớp n ≥ 2 thì giữ token fold và sang vị trí kế. **Không** phục hồi âm tiết đơn.
  - "cho dem dalat" → alias: "cho dem Đà Lạt" → bigram "cho dem" → "chợ đêm" → "chợ đêm Đà Lạt".
  - "nguyen khac tiep" → không n-gram nào → giữ fold.
- Sau phục hồi: dùng cutoff/`HybridConfig` thường (bỏ 0,80 / `lexical_cutoff 0.0` / coverage 0,4). `diagnostics.accentRestored: [span]`; `queryProfile` vẫn `no_diacritics`.

### 2.6 Residual không giải thích được — `domain/search/explain.py` (mới), `query_plan.py`, `use_cases.py`
- Vocab dựng lúc load: unigram + bigram (giữ dấu và fold) từ tên + text unit + alias + gazetteer + `VERTICAL_CUES` + nhãn tiện ích (`amenities.py`).
- `unexplained_spans(residual_seq, vocab, keep_tone)`: chuỗi liên tiếp token (đã bỏ stopword, số, span consume, điểm đến, entity, cue loại) mà mọi bigram kề nhau ∉ vocab (span 1 token: unigram ∉ vocab).
- Phân loại span:
  - **`name_like`**: ≥ 2 âm tiết **và** (âm tiết đầu thuộc danh sách họ Việt — hằng số domain ~30 họ: nguyễn, trần, lê, phạm, hoàng/huỳnh, phan, vũ/võ, đặng, bùi, đỗ, hồ, ngô, dương, lý, …; **hoặc** viết hoa chữ đầu mọi âm tiết trong câu gốc).
  - **`unknown`**: còn lại ("rẻ bèo", "sống ảo", "chill chill", chuỗi vô nghĩa).
- Quyết định (cờ `unexplained_empty`):

| Trường hợp | Kết quả | Ví dụ |
|---|---|---|
| Span `name_like` chiếm **toàn bộ** nội dung residual | rỗng, `emptyReason: unexplained`, `queryPlan.unexplained = [span]` | "Nguyễn Khắc Tiệp"; "khách sạn Nguyễn Khắc Tiệp"; "Nguyễn Khắc Tiệp Đà Lạt"; "Dương Tu Minh" |
| **Mọi** token nội dung của **cả câu** đều unknown và plan không có filter nào | rỗng | "xkcd qwzt plorb" |
| Span `unknown` (không phải toàn câu), hoặc `name_like` đi kèm phần residual đã giải thích được | bỏ span khỏi `dense_text` + `lexical_text`, tìm tiếp, `queryPlan.unparsed = [span]` | "khách sạn Đà Lạt rẻ bèo"; "homestay sống ảo view đồi"; "resort Phú Quốc chill chill"; "Nguyễn Khắc Tiệp gần biển" |
- Span nào **giải thích được** (có trong mô tả, vd "Phạm Văn Đồng" là tên đường trong địa chỉ) thì không vào bảng trên; BM25 vẫn bị §2.1 chặn vớt "Sân Vận động".
- Rỗng sớm → không gọi dense/BM25 (bớt latency).
- Bước 0.3 đo trước trên gold + probe: tỉ lệ chặn nhầm câu có đáp án ≤ 2 % mới được giữ định nghĩa.

### 2.7 Nhãn "Kết quả gần nhất" — `use_cases.py`, frontend
- Backend phát `backgroundScore` (đã khai ở `search.yaml:783`, chưa phát) = median cosine danh sách dense top-`candidate_k` trong F; mô tả contract thêm "xấp xỉ khi |F| > candidateK". Thêm `diagnostics.saturated` (|kept_dense| ≥ `candidate_k`) — chỉ để quan sát.
- Frontend (`search.ts:134`, `SearchView.tsx:124-129`): weak khi **cả ba**:
  1. `filteredCount ≥ WEAK_MIN_F` (mặc định 20 — F nhỏ thì median ≈ top, margin vô nghĩa: thị trấn có 3–4 KS không bị gắn nhãn);
  2. `topScore − backgroundScore < WEAK_RESULT_MARGIN` (chọn trên dev, dự kiến ~0,058);
  3. `topScore < WEAK_TOP_CEILING` (chọn trên dev, dự kiến ~0,88).
  Không áp khi `diagnostics.filterOnly`.
- Empty state (`SearchView.tsx:141-153`) đọc `emptyReason`: `unexplained` → "Không tìm thấy “…”. Thử tên khác hoặc mô tả nhu cầu"; `duration` → "Không có vé/combo đúng thời lượng"; `entity` như hiện có.

### 2.8 Contract 1.30.0 (additive)
- `queryPlan`: `unexplained: [string]`, `unparsed: [string]`, `denseText`, `duration.role ∈ {gate, stay}` (chỉ khai khi cờ tương ứng bật); `emptyReason` += `unexplained`; mô tả `duration` "P0 không lọc" → "lọc vé/combo khi `SEARCH_DURATION_MASK`, role gate".
- `EngineDiagnostics` (mở): `filterOnly`, `saturated`, `accentRestored`, `evidenceGate`.
- `SearchResponse.backgroundScore` bắt đầu phát (ghi chú xấp xỉ).
- `common.yaml:70-74` (định nghĩa R): thêm "khi `evidenceGate` bật: R_lex yêu cầu bằng chứng tên theo cụm giữ dấu; RRF chỉ cộng hạng BM25 của unit có bằng chứng văn bản".
- Ghim 1.30.0: `openapi.yaml:4`, `main.py:889`, `test_search_contract.py:144`; changelog `search.yaml:1-21`; regen `src/frontend/src/types/api.gen.ts`.

### 2.9 Cờ (`config.py`, mặc định tắt)
`SEARCH_EVIDENCE_GATE`, `SEARCH_DURATION_MASK`, `SEARCH_EMBED_RESIDUAL`, `SEARCH_UNEXPLAINED_EMPTY`, `SEARCH_NO_DIACRITICS_MODE=restore`, `SEARCH_EMIT_BACKGROUND`. Bảng biến `docs/prd/deployment-plan.md` cập nhật theo đề xuất (Bước 1).

---

## 3. Các bước thực hiện

Mỗi bước: 1 commit + 1 entry `history/`; cổng xanh trước bước sau. Chạy từ repo root; Windows `PYTHONUTF8=1`.

| # | Bước | File chính | Cổng | Ghi chú |
|---|---|---|---|---|
| 0.1 | Tách nhánh từ `release-mvp-v2`; đọc tài liệu AGENTS §1.1–1.2 (PRD README, requirements FR-SRC, architecture §2/§5, hop-dong search, contracts-guide, history search 10 mới nhất); đọc lại số dòng `main.py`, `config.py`; đăng xác nhận §1.3 | — | ghi vào chat | |
| 0.2 | Đo dữ liệu: số unit attraction/combo suy được days/nights; `attributes.nights` có thật sau `parse_combos` không (`parse_combos.py:157,183-187` ghi `nights` nhưng jsonl không có); `UnitIndex` có embed text trong RAM không | script scratch trên `items.parquet` bench + DB local | bảng số vào §2.3, §2.1 | |
| 0.3 | Đo offline §2.1 + §2.6 trên gold_v6 + probe: chặn nhầm in-catalog, tỉ lệ `name_like` bắt nhầm (vd "Hồ Tràm", "Lý Sơn" phải được giải thích bởi destination) | script scratch | chặn nhầm ≤ 2 %, nếu vượt → sửa định nghĩa trước Bước 1 | |
| 0.4 | Probe baseline live (read-only, ≤ 100 GET) ~50 câu | `scratch/probe_live.py` | lưu JSON | |
| 1 | **Đề xuất PRD** `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md` (**đã chốt 13/10**, PRD đã cập nhật): (a) `deployment-plan.md:53` "giới hạn đã biết" → cơ chế mới; (b) FR-SRC-04: rỗng khi residual chỉ là tên lạ; (c) FR-SRC-03: lọc thời lượng vé/combo; (d) định nghĩa R; (e) thay thế đề xuất 2026-10-06; (f) P1: thêm property BM25 | `docs/prd/update/` | **người dùng chốt** | **DỪNG** Bước 4–10 tới khi chốt |
| 2 | Gold + probe: `no_answer` (~40: tên người, tên trùng đường/di tích, vô nghĩa, POI/entity không có), `name_collision` (~12, `forbidden`), `duration_only` (~8), `duration_stay` (~6: "khách sạn Đà Lạt 2 ngày 1 đêm"…), `slang_residual` (~8: "khách sạn Đà Lạt rẻ bèo", "homestay sống ảo view đồi"…), đối chứng tên ngắn có thật + không dấu có đáp án; 10 câu âm AC 7; split `devtest@gold_v7.json` | `search_bench/gold/gold.jsonl`, `config/query_annotations.yaml` | `sb gold check` xanh | song song Bước 1; nhãn máy → QAnh duyệt |
| 3 | Bench wiring: key app mới trong adapter; arm `APP.e5s.prod_f12356_ev`, `_dm`, `_er`, `_ue`, `_rs`, `_all` | `search_bench/app_adapter.py`, `arms/*.yaml` | identity `topids-diff` rỗng khi tắt | |
| 4 | Contract 1.30.0 (§2.8) | `schemas/search.yaml`, `common.yaml`, `openapi.yaml`, `api.gen.ts` | `PYTHONDONTWRITEBYTECODE=1 python src/shared/contracts/tests/validate_contract.py`; `pytest src/backend/tests/contract` | sau Bước 1 |
| 5 | Domain: `lexical.syllables/bigrams/evidence`; `hybrid.evidence_gate` + `rrf_admissible`; `explain.py` (vocab, span, phân loại, danh sách họ) | `domain/search/lexical.py`, `hybrid.py`, `explain.py`, `__init__.py` | `pytest tests/unit/domain/test_lexical.py test_hybrid.py test_explain.py` | bảng ca §0/§2.6 parametrize; equivalence khi tắt |
| 6 | Catalog: `duration_days/nights`; `mask(duration_*, duration_taxonomies)` | `domain/catalog/unit_attributes.py`, `application/ports/unit_index.py` | `pytest .../test_unit_attributes.py .../test_unit_index_mask.py` | ca: hotel không bị loại khi role stay |
| 7 | Query plan: duration role, `dense_text`, `unexplained`/`unparsed`, `families_in_order` | `domain/search/query_plan.py`, `constraints.py` | `pytest .../test_query_plan.py .../test_constraints.py .../test_query_plan_filters.py` | |
| 8 | Normalizer `restore` (longest-match) | `domain/search/normalize.py` | `pytest .../test_normalize.py .../test_no_diacritics.py` | ca: "cho dem dalat", "nguyen khac tiep", "thi tran" mơ hồ |
| 9 | Use case + wiring: bảng bằng chứng/vocab, embed residual + chỉ-filter, rỗng sớm, `backgroundScore`, cờ | `application/search/use_cases.py`, `core/config.py`, `main.py` | `pytest tests/unit/application -k search`; `test_search_v116_defaults`; `test_search_settings_wiring.py`; `pytest tests/architecture` | coverage domain/application ≥ 80 % |
| 10 | Frontend: luật weak 3 điều kiện, banner, empty state theo `emptyReason`; spec FE | `services/search.ts`, `components/search/SearchView.tsx`, `tests/unit/searchService.test.ts`, `docs/spec/hop-dong-tich-hop-frontend.md` | `npm test` xanh | ngưỡng từ Bước 11 dev |
| 11 | Bench: run arm + `_all` trên gold_v7, compare dev/test, guards, regress | `src/evaluation/reports/eval-2026-10-1x-search-evidence-gate.md` | §4 | |
| 12 | Đồng bộ spec (`hop-dong-tich-hop-search-recommendation.md`, `arms.md`, `kien_truc_search_ota_so_do_va_giai_doan.md`); áp PRD theo đề xuất; `git mv` đề xuất mới + cũ sang `update-archive/` | docs | review | |
| 13 | Rollout (§5) | env VM | smoke + 48 h | |

---

## 4. Bench và cổng

```
python -m evaluation.search_bench --run-id 2026-10-1x-identity run --arm APP.e5s.prod_f12356
python -m evaluation.search_bench --run-id 2026-10-1x-identity topids-diff 2026-10-06-gold-v4-r2 APP.e5s.prod_f12356 --run-b 2026-10-1x-identity
python -m evaluation.search_bench --run-id 2026-10-1x-gold-v7 run --arm APP.e5s.prod_f12356 --arm ..._ev --arm ..._dm --arm ..._er --arm ..._ue --arm ..._rs --arm ..._all
python -m evaluation.search_bench --run-id 2026-10-1x-gold-v7 compare APP.e5s.prod_f12356 <arm> --split dev|test
sb guards --arms ...
sb regress check --arm <arm> --split test
```
(từ `src/`, `PYTHONUTF8=1`, `PYTHONPATH=<repo>/src`)

Cổng bật cờ (đo trên test, ngưỡng chọn trên dev):
- `compare` WIN/TIE (`metrics.py:859-867`), không slice tụt > 3 điểm nDCG@10.
- `forbidden_at_10 = 0`: `name_collision`, `duration_false_positive`, `duration_only`.
- Zero-result: `no_answer` + `out_of_catalog` ≥ 0,90; `slang_residual`, `duration_stay` = 0; in-catalog ≤ 0,02.
- `named_entity`: không câu nào mất item rel-2 khỏi top-10.
- guards xanh (`constraint_precision_min 0.95`, `p95_cache_miss_ms_max 250`).
- Probe live sau deploy staging khớp kỳ vọng (3 câu gốc + ~50 câu).

## 5. Rollout
- R0: deploy cờ tắt → probe live = baseline.
- R1: `SEARCH_EVIDENCE_GATE` + `SEARCH_DURATION_MASK` + `SEARCH_EMBED_RESIDUAL` → 48 h theo dõi tỉ lệ total = 0 (`app.search_logs`).
- R2: `SEARCH_NO_DIACRITICS_MODE=restore`.
- R3: `SEARCH_UNEXPLAINED_EMPTY` + `SEARCH_EMIT_BACKGROUND` + frontend (Web ký).
- Rollback: tắt cờ qua env; `relax` còn nguyên.

---

## 6. P1 chi tiết

### 6.1 Trường BM25 riêng (không re-embed)
- `weaviate_store.LEXICAL_PROPERTIES` thêm `nameTone` (tên lower giữ dấu, tokenization `word` — **xác minh** Weaviate 1.27 giữ ký tự có dấu), `nameBigrams` (bigram fold nối `_`), `aliasAscii` (tên trong ngoặc + alias gazetteer/normalize), `descAscii` (embed text trừ headline); `lexical_properties()` sinh đủ.
- `BM25_QUERY_PROPERTIES` theo chế độ câu: có dấu `["nameTone^3", "nameBigrams^3", "aliasAscii^2", "nameAscii", "descAscii"]`; không dấu bỏ `nameTone`. Truy vấn gửi thêm token bigram.
- Backfill: sửa điều kiện `weaviate_store.py:174` thành "đủ mọi `LEXICAL_PROPERTIES`"; `python -m src.backend.jobs.embed_products --lexical-only --dry-run` rồi `--lexical-only`.
- Bench: `app_adapter.py:246` (danh sách property cứng) + `sb app-load --recreate --model e5-small`.
- Arm `APP.e5s.prod_f12356_all_fbm25`; cổng §4. Kỳ vọng: bằng chứng tên vào thẳng BM25 → có thể nới `min_coverage` mà không tăng forbidden.

### 6.2 Ablation text builder T0–T5
- Chạy arm E1 chưa chạy (`docs/spec/bench/search-eval-checklist.md:101-126`, `arms.md`): HEADLINE · +FIT+FEATURES · +ROLLUP · +EXCERPT w30/w60/w150, cùng cờ P0 bật; re-embed **bench** (`.npy` cục bộ).
- Quyết định: EXCERPT tăng forbidden không tăng recall → rút/làm sạch; mọi biến thể đều có hard negative cao → giữ text, ưu tiên reranker/parser. Chỉ khi tách mô tả **tăng** recall mới xét `description_vector` (đề xuất PRD riêng, FR-SRC-02).
- Đổi text builder prod = `TEXT_BUILDER_VERSION` mới + re-embed prod + `modelVersion` mới.

---

## 7. Definition of Done
- Contract: `validate_contract.py` PASS; 1.30.0 ghim 3 nơi; `api.gen.ts` regen.
- Backend: unit + contract + architecture xanh; byte-identical khi tắt; coverage domain/application ≥ 80 %.
- Frontend: test xanh.
- Bench: report `eval-2026-10-1x-search-evidence-gate.md` (commit, run id, gold_v7, cấu hình arm, bảng nguyên văn, lệnh tái sinh); cổng §4 đạt cho mỗi cờ bật.
- Docs: đề xuất chốt → PRD cập nhật → đề xuất mới + cũ ở `update-archive/`; spec đồng bộ; mỗi bước có `history/`.

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| `name_like` theo họ bắt nhầm địa danh bắt đầu bằng họ ("Hồ Tràm", "Lý Sơn", "Phan Thiết") | chỉ xét span **không giải thích được**; địa danh catalog đã là destination/gazetteer → không vào; Bước 0.3 đo |
| Bỏ cụm `unknown` làm mất ý nghĩa ("giá rẻ bèo" → giá) | parser giá chạy trước; cụm bỏ ghi `unparsed` để log/mở rộng từ điển |
| Hotel bị loại vì thời lượng | role stay theo cue lưu trú; test bắt buộc "khách sạn Đà Lạt 2 ngày 1 đêm" > 0 kết quả; slice `duration_stay` |
| Tab hotel rỗng với câu "2 ngày 1 đêm" | chủ đích (tiền lệ entity gate); empty state giải thích |
| Gate giữ dấu chặn câu gõ sai dấu ("Đa Lat") | phục hồi dấu + so fold khi câu có dấu mà 0 khớp tone |
| Bằng chứng văn bản cần text trong RAM | Bước 0.2; dự phòng `name + description` |
| Nhãn weak sai ở điểm đến nhỏ | `WEAK_MIN_F` + `WEAK_TOP_CEILING` |
| Latency (bảng bigram, phục hồi dấu) | dựng lúc load; guard p95 |
| Nhánh khác chiếm contract 1.30.0 trước | lấy minor kế tiếp tại Bước 4, cập nhật plan |

## 9. Đánh giá lệch PRD
- Lệch, cần Bước 1 chốt: `deployment-plan.md:53`, hành vi FR-SRC-04 (rỗng khi chỉ có tên lạ), FR-SRC-03 (lọc thời lượng vé/combo), định nghĩa R trong contract, bảng biến môi trường; P1: property BM25 mới.
- Không lệch: không DDL, không vector mới, không tham số request, contract additive.
