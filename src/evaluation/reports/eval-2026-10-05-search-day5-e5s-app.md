# Search Day 5 — `/search` production với e5-small: 3 arm APP, cutoff, regression, F1 (05/10)

- Phục vụ: FR-SRC-01..04, FR-SRC-02 (model embedding), AC-SRC-01, NFR-PERF-01; `docs/prd/test-plan.md` §2.5. Plan: lịch 10 ngày Day 5 / Day 6
  (`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`), plan Day 4–5 §2.3 việc 5, 8, 10 (`docs/plan/2026-10-01-plan-day4-5.md`).
- Commit: `bench_search_recomSys @ 02ccddf` + thay đổi chưa commit của entry `history/2026-10-05-search-day5-e5s-app-cutoff-regress.md` (cổng APP
  nhận model khác Cohere, 6 arm `APP.e5s.*`, lệnh `sb gold devtest`, `sb regress baseline|check`).
- Gold: `gold_v3` (131 câu active / 13 slice, 5.021 nhãn, sha `4d2ac02f…`). Catalog: snapshot bench 2026-09-23, 3.183 search unit, text
  `catalog-text-v2`. Weaviate bench local `1.37.3` (`:58080`), collection hình dạng production, hnsw.
- Model: e5-small = `intfloat/multilingual-e5-small` (384, embed local CPU, prefix `query:` / `passage:`); Cohere v3 =
  `embed-multilingual-v3.0` (1024) **chỉ đọc cache truy vấn** (chạy với khoá API giả → 0 lượt gọi Cohere).
- Run: `20261005-e5s-app-r2` (6 arm e5s + 3 arm Cohere — nguồn số chính, nguồn `baseline_v1`), `20261005-e5s-app-r3` (lặp lại y hệt — kiểm
  ổn định), `20261005-day5-app-e5s` (lượt đầu, **bỏ**, xem mục 1), `20261005-e5s-repeat` (chẩn đoán), `20261005-e5s-guard` (kiểm guard BM25, mục 9).

> **Caveat:** gold được dựng bằng pooling chủ yếu từ Cohere + BM25; e5-small có Judged@10 0,79–0,85 (Cohere 0,98–1,00). Số "full" coi kết quả
> chưa nhãn là không liên quan nên **thiên lệch có lợi cho Cohere**; luôn đọc kèm "condensed" (bỏ kết quả chưa nhãn). Slice có 3–18 câu: chênh
> theo slice chỉ là hướng.

## Đọc nhanh

1. **`/search` cấu hình production (hybrid + normalize) với e5-small ngang Cohere v3:** nDCG@10 0,680 so với 0,684 (Δ −0,4 [−4,6; +3,7]);
   condensed 0,690 so với 0,686 (Δ +0,4 [−3,7; +4,5]) → TIE. Dense-only và hybrid không normalize: e5-small nhỉnh hơn 1,5–4 điểm (CI chứa 0).
2. **Tổng hoà nhưng slice lệch mạnh:** e5-small **tốt hơn nhiều ở câu không dấu** (`no_diacritics` +35,8 điểm) và tên riêng (+7,7), **kém nhiều
   ở `cross_vertical`** (−26,0, n = 10) và kém 4–6 điểm ở `abbrev_typo`, `audience_style`, `dest_type`. `cross_vertical` là rủi ro cần xem
   trước khi đổi production.
3. **Cutoff 0,62 (chỉnh cho Cohere) không lọc gì với e5:** cosine e5 dồn ở 0,85–0,92, mọi câu trả ~200 kết quả. Sweep trên **dev** chọn
   **0,85** (giá trị cao nhất giữ zero-result trong catalog < 2 %); trên **test**: nDCG@10 0,647 (−1,1 so với không cutoff), zero-result 1,6 %,
   số kết quả p50 108. Không cutoff nào làm câu ngoài catalog trả rỗng mà không làm rỗng ≥ 5 % câu trong catalog — giống Cohere (0,62 cũng
   không làm rỗng câu ngoài catalog). **Đề xuất, chưa chốt; không sửa config production.**
4. **Số hybrid của report Day 4 (`eval-2026-10-01-search-v1-3arm.md`) không tái lập được:** cùng code, cùng cache, hôm nay hai lượt lặp trùng
   nhau 100 % nhưng lệch Day 4 ở 93/131 (hybrid) và 79/131 (hybrid + normalize) câu: Cohere hybrid 0,597 → **0,623**, hybrid + normalize
   0,648 → **0,684**. Lượt đầu hôm nay cũng lệch kiểu đó (e5s hybrid 0,415 → 0,655 khi chạy lại). Nguyên nhân khả dĩ: chạy ngay sau khi
   Weaviate nạp lại collection, BM25 chưa sẵn sàng (guard hiện chỉ chờ index vector). Kết luận Day 4 "dense giữ làm mốc vì hybrid +
   normalize thua guard slice" cần xét lại bằng số mới.
5. **Regression gọn chạy được:** `baseline_v1` = `APP.e5s.hybrid_norm` trên gold_v3; `sb regress check` trên lượt lặp → PASS, Δ 0, 0/131 câu
   đổi kết quả. **F1 smoke filter PASS** (439/439 kết quả thoả filter, 10 câu). **BM25-only** (nếu embed hỏng) mất 9,1 điểm nDCG@10.
6. **Xét lại Day 4 bằng số đúng:** hybrid + normalize thắng dense rõ ở cả hai model — Cohere +6,4 [+2,7; +10,8] nDCG@10, e5-small +4,6
   [+0,5; +8,8]; nhãn "LOSE" của `win_rule` chỉ vì slice `amenity_negation` (5 câu) / `cross_vertical`. Cấu hình production là tốt nhất (mục 8).
7. **Nguyên nhân lệch đã tái hiện và đã chặn:** ~60 s đầu sau khi nạp collection, BM25 của Weaviate chấm sai thứ tự ở 10/10 câu thăm dò rồi
   mới ổn định. Thêm guard `wait_bm25_settled` khi nạp; nạp lại rồi đo ngay → chỉ 4/131 câu khác (nhiễu HNSW dựng mới), nDCG không đổi (mục 9).
8. **Hub check:** e5-small (hub max 13,4; 297 sản phẩm > 3) ngang Cohere v3 (14,6; 299) — không model nào có vấn đề hub riêng. **GTE cắt chiều**
   768 → 512 / 256 / 128 không mất chất lượng (Δ nDCG ≥ −0,35, CI chứa 0) (mục 10).
9. **`cross_vertical` −26 điểm của e5-small** do 3/10 câu: e5 khớp tên thành phố ở **điểm đi** của combo "Vé máy bay khứ hồi Hà Nội – …"
   thay vì điểm đến (mục 11). **466 cặp chưa nhãn** trong top-10 e5-small → pool gán `gold/holes/gold_v3__D6a/` (mục 12).
10. **Gate P (p95 `/search` cloud < 250 ms) chưa đo được:** cần quyền VM; số cloud gần nhất 4,0 s (01/10, Cohere, Weaviate Frankfurt) — nút
   thắt ở Weaviate, đổi model không giải quyết.

## 1. Độ ổn định — vì sao bỏ lượt đầu

| Arm (e5-small) | nDCG@10 lượt 1 (`day5-app-e5s`) | lượt 2 (`r2`) | lượt 3 (`r3`) | top-10 khác nhau r2 / r3 |
|---|---:|---:|---:|---:|
| APP.e5s.dense | 0,635 | 0,635 | 0,635 | 0 / 131 |
| APP.e5s.hybrid | **0,415** | 0,655 | 0,655 | 0 / 131 |
| APP.e5s.hybrid_norm | **0,532** | 0,680 | 0,680 | 0 / 131 |
| APP.e5s.hybrid_norm_nocut | 0,680 | 0,680 | 0,680 | 0 / 131 |

Lượt 1 chạy ngay sau khi tạo và nạp `ProductBench__e5_small`; chỉ các arm có nhánh BM25 chạy sớm bị lệch, dense không lệch. Cohere (`ProductBench`,
không nạp lại): r2 = r3 100 %, nhưng lệch Day 4 ở 93 / 79 câu (bảng mục 2). Code search không đổi kể từ lượt Day 4 (01/10 12:31; commit cuối chạm
`domain/search`, `application/search`, `weaviate_store.py`, `app_adapter.py` là `fe7e04d` 10:31). Nguyên nhân đã tái hiện và chặn bằng guard — mục 9.

## 2. Ba arm APP: Cohere v3 so với e5-small (run `20261005-e5s-app-r2`, cutoff YAML 0,62)

| Arm | Model | Recall@10 | nDCG@10 | MRR@10 | Judged@10 | nDCG@10 condensed | Zero-result trong catalog | Số Day 4 (nDCG@10) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| dense | Cohere v3 | 0,306 | 0,620 | 0,693 | 1,000 | 0,620 | 0,164 | 0,620 |
| dense | e5-small | 0,317 | 0,635 | 0,728 | 0,789 | 0,647 | 0,000 | — |
| hybrid | Cohere v3 | 0,302 | 0,623 | 0,681 | 0,976 | 0,625 | 0,148 | 0,597 |
| hybrid | e5-small | 0,319 | 0,655 | 0,751 | 0,840 | 0,665 | 0,000 | — |
| hybrid + normalize | Cohere v3 | 0,339 | 0,684 | 0,746 | 0,975 | 0,686 | 0,039 | 0,648 |
| hybrid + normalize | e5-small | 0,336 | 0,680 | 0,770 | 0,845 | 0,690 | 0,000 | — |

Zero-result ngoài catalog = 0,000 ở mọi arm cả hai model (3 câu): không cấu hình nào làm câu ngoài catalog trả rỗng.

**So cặp** (`sb compare A B`, paired bootstrap 1.000 lượt seed 42, n = 128 câu có nhãn dương; Δ = e5-small − Cohere, điểm ×100):

| Cặp | Δ nDCG@10 full [CI95] | Δ nDCG@10 condensed [CI95] | Δ Recall@10 [CI95] | Kết luận `win_rule` | Slice tụt nhiều nhất |
|---|---|---|---|---|---|
| dense | +1,50 [−2,00; +5,15] | +2,75 [−0,81; +6,39] | +1,15 [−0,67; +3,18] | TIE (full) / LOSE (condensed: slice) | cross_vertical −12,7 |
| hybrid | +3,18 [−1,41; +7,72] | +4,03 [−0,59; +8,69] | +1,76 [−1,02; +4,42] | LOSE (slice) | cross_vertical −26,0 / −27,4 |
| hybrid + normalize | −0,36 [−4,59; +3,66] | +0,42 [−3,74; +4,47] | −0,31 [−2,87; +2,10] | TIE | cross_vertical −26,0 |

`LOSE` ở hai dòng đầu là luật "không slice nào thua > 3 điểm" của `win_rule`, không phải tổng thua.

**Theo slice — cấu hình production (hybrid + normalize), nDCG@10 condensed:**

| Slice | n | Cohere v3 | e5-small | Δ |
|---|---:|---:|---:|---:|
| no_diacritics | 12 | 0,200 | 0,558 | **+35,80** |
| named_entity | 18 | 0,756 | 0,833 | +7,69 |
| amenity_offtaxonomy | 5 | 0,500 | 0,576 | +7,52 |
| parent_child | 11 | 0,658 | 0,684 | +2,65 |
| amenity_negation | 5 | 0,368 | 0,368 | −0,07 |
| amenity_multi | 10 | 0,899 | 0,879 | −2,07 |
| amenity_single | 13 | 0,829 | 0,787 | −4,20 |
| multi_constraint | 9 | 0,755 | 0,706 | −4,97 |
| audience_style | 11 | 0,656 | 0,606 | −5,04 |
| abbrev_typo | 12 | 0,705 | 0,648 | −5,68 |
| dest_type | 12 | 0,785 | 0,722 | −6,34 |
| cross_vertical | 10 | 0,852 | 0,592 | **−26,02** |

## 3. Cutoff cho e5-small — sweep trên dev, báo trên test

Split cố định `gold/splits/devtest@gold_v3.json` (`sb gold devtest --seed 42`): phân tầng theo slice, dev 66 / test 65 câu
(out_of_catalog chỉ 3 câu: dev 1, test 2). Cấu hình = `APP.e5s.hybrid_norm`, chỉ đổi `app.cutoff` (`lexical_cutoff = min(0,50; cutoff)` như
production). Quy tắc S7 (`docs/spec/bench/arms.md`): câu ngoài catalog trả rỗng 100 % **và** zero-result trong catalog < 2 %; không đạt cả hai
thì lấy giá trị cao nhất còn giữ zero-result trong catalog < 2 %.

Phân bố cosine top-1 (gold, p10 / p50 / p90): Cohere v3 0,651 / 0,708 / 0,765 · e5-small 0,849 / 0,886 / 0,916. Ở cutoff 0,62 Cohere giữ p50
27 ứng viên / câu, e5-small giữ đủ 200.

**Dev (66 câu):**

| Cutoff | nDCG@10 | Recall@10 | MRR@10 | Judged@10 | nDCG@10 condensed | Zero-result trong catalog | Zero-result ngoài catalog (n = 1) | Số kết quả p50 / p10 |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| không (−1) | 0,702 | 0,350 | 0,822 | 0,868 | 0,711 | 0,000 | 0,000 | 215 / 203 |
| 0,62 | 0,702 | 0,350 | 0,822 | 0,868 | 0,711 | 0,000 | 0,000 | 215 / 203 |
| 0,80 | 0,702 | 0,350 | 0,822 | 0,865 | 0,711 | 0,000 | 0,000 | 211 / 201 |
| 0,82 | 0,700 | 0,352 | 0,810 | 0,872 | 0,709 | 0,000 | 0,000 | 205 / 119 |
| 0,84 | 0,691 | 0,346 | 0,820 | 0,888 | 0,699 | 0,000 | 0,000 | 122 / 10 |
| **0,85** | 0,685 | 0,342 | 0,800 | 0,889 | 0,692 | **0,015** | 0,000 | 57 / 4 |
| 0,86 | 0,656 | 0,326 | 0,768 | 0,938 | 0,663 | 0,046 | 0,000 | 28 / 2 |
| 0,87 | 0,595 | 0,289 | 0,730 | 0,957 | 0,596 | 0,108 | 1,000 | 8 / 0 |
| 0,88 | 0,434 | 0,211 | 0,600 | 0,983 | 0,435 | 0,292 | 1,000 | 2 / 0 |
| 0,89 | 0,280 | 0,138 | 0,446 | 0,983 | 0,280 | 0,446 | 1,000 | 1 / 0 |

**Test (65 câu) — chỉ đọc sau khi đã chọn trên dev:**

| Cấu hình | nDCG@10 | Recall@10 | MRR@10 | Judged@10 | nDCG@10 condensed | Zero-result trong catalog | Zero-result ngoài catalog (n = 2) | Số kết quả p50 / p10 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| e5-small, không cutoff / 0,62 | 0,658 | 0,322 | 0,717 | 0,825 | 0,669 | 0,000 | 0,000 | 211 / 201 |
| e5-small, 0,84 | 0,646 | 0,312 | 0,718 | 0,853 | 0,657 | 0,000 | 0,000 | 186 / 17 |
| **e5-small, 0,85 (chọn)** | **0,647** | 0,311 | 0,714 | 0,876 | 0,657 | **0,016** | 0,000 | 108 / 2 |
| e5-small, 0,86 | 0,621 | 0,289 | 0,699 | 0,882 | 0,630 | 0,032 | 0,000 | 64 / 1 |
| e5-small, 0,87 | 0,583 | 0,260 | 0,686 | 0,891 | 0,592 | 0,048 | 0,500 | 22 / 1 |
| Cohere v3, 0,62 (production hiện tại) | 0,636 | 0,313 | 0,706 | 0,974 | 0,641 | 0,079 | 0,000 | 38 / 1 |

Đọc: với e5-small, cutoff chủ yếu quyết định **số kết quả / facet / `total`** chứ ít đổi top-10. 0,85 cắt danh sách từ ~210 xuống ~60–110 kết quả
mà chỉ mất ~1 điểm nDCG và zero-result trong catalog vẫn thấp hơn Cohere hiện tại (1,6 % so với 7,9 %). `lexical_cutoff` 0,50 cũng không còn
tác dụng với e5 (mọi cosine > 0,5) — chưa sweep, cần chỉnh cùng cutoff khi đổi production. Áp dụng cần: chốt model (đề xuất PRD FR-SRC-02),
rồi đổi `SEARCH_CUTOFF` và contract §2.4 (ghi cutoff mốc 0,62).

## 4. Regression gọn (`sb regress`)

- `regression/baseline_v1.json`: arm `APP.e5s.hybrid_norm`, run `20261005-e5s-app-r2`, `gold_v3`, 131 câu, nDCG@10 0,680 / Recall@10 0,336,
  kèm metric + top_ids từng câu, sha catalog, commit (`git_dirty: true` — cây có thay đổi chưa commit lúc ghi). Ngưỡng `regression.regress_v1`:
  FAIL khi nDCG@10 hoặc Recall@10 tụt > 1,0 điểm tổng hoặc > 3,0 điểm ở một slice.
- `sb --run-id 20261005-e5s-app-r3 regress check` → **PASS**, Δ 0,00, 0/131 câu đổi top-10; `--split dev` → PASS (0/66).
- Đổi cutoff hoặc model thì đặt lại baseline (`regress baseline --force --note …`).

## 5. F1 — filter và BM25-only

**(a) Smoke filter** — 10 câu gold đầu tiên (theo qid) có nhãn 2, filter lấy từ sản phẩm nhãn 2 đầu tiên của câu; `SearchProducts` của
`APP.e5s.hybrid_norm`, limit 50:

| qid | Câu | taxonomy | destination | Kết quả | Thoả filter |
|---|---|---|---|---:|---:|
| c0005 | tìm khách sạn nghỉ dưỡng tại Hạ Long | hotel | Hạ Long | 50 | 50/50 |
| c0020 | tìm chỗ nghỉ tại Hà Tĩnh | hotel | Hà Tĩnh | 28 | 28/28 |
| c0030 | khách sạn nghỉ dưỡng tại Hội An, có lựa chọn nào? | hotel | Hội An | 50 | 50/50 |
| c0037 | điểm vui chơi ở Phú Quốc | attraction | Phú Quốc | 50 | 50/50 |
| c0052 | hoạt động trải nghiệm ở Nghệ An | combo | Nghệ An | 11 | 11/11 |
| c0056 | tìm combo du lịch Quy Nhơn | — | Quy Nhơn | 50 | 50/50 |
| c0059 | tìm gói vui chơi ở Hội An | — | Hội An | 50 | 50/50 |
| c0061 | combo trải nghiệm tại Phú Quốc | — | Phú Quốc | 50 | 50/50 |
| c0070 | vé máy bay đến Hà Nội | flight | — | 50 | 50/50 |
| c0078 | đường bay tới Huế, có lựa chọn nào? | flight | — | 50 | 50/50 |

**439/439 kết quả thoả filter → PASS.**

**(b) BM25-only** — `/search` production **không có** chế độ dự phòng khi embed lỗi (route trả lỗi). Số dưới đây chỉ đo "nếu thêm fallback BM25
thì mất bao nhiêu": `lexical.bm25` của chính adapter Weaviate production trên câu đã chuẩn hoá, top-10; so với `APP.e5s.hybrid_norm` (r2). Judged
của BM25-only chưa tính — kết quả chưa nhãn bị coi là sai nên số BM25 là cận dưới.

| Tập | n | BM25-only nDCG@10 | hybrid + normalize nDCG@10 | Δ | BM25-only Recall@10 | hybrid + normalize Recall@10 | BM25 zero-result trong catalog |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | 128 | 0,589 | 0,680 | −9,1 | 0,305 | 0,336 | 0,000 |
| dev | 65 | 0,595 | 0,702 | −10,7 | 0,310 | 0,350 | 0,000 |
| test | 63 | 0,582 | 0,658 | −7,6 | 0,300 | 0,322 | 0,000 |

Theo slice, BM25-only / hybrid + normalize (e5): mất nhiều nhất ở `multi_constraint` 0,316 / 0,700, `amenity_offtaxonomy` 0,342 / 0,568,
`cross_vertical` 0,393 / 0,578, `audience_style` 0,404 / 0,590; **hơn** ở `no_diacritics` 0,694 / 0,526.

## 6. Ngoài phạm vi / chưa làm

- **Arm S0–S9** (BM25 riêng, fusion Weaviate, QU, amenity, dedupe, SymSpell, rerank, CSLS): không chạy — người dùng chốt 05/10 chỉ làm phần cần
  cho việc đổi model; cutoff (S7) làm ở mục 3.
- **Gate P** (p95 `/search` cloud < 250 ms, NFR-PERF-01): cần quyền VM; chưa có owner. Sau khi đổi sang e5-small phải đo lại (embed local thay
  API Cohere; số cũ: embed Cohere miss p95 437 ms, Weaviate dense + BM25 nối tiếp ~4 s).
- Đổi production sang e5-small (collection Weaviate mới, `SEARCH_CUTOFF`, contract §2.4, `modelVersion`): cần đề xuất PRD FR-SRC-02 được chốt.
- `cross_vertical` −26 điểm với e5-small: chưa phân tích từng câu.
- Guard "BM25 sẵn sàng sau khi nạp" (mục 1): đã sửa và kiểm ở mục 9.

## 8. Xét lại cấu hình mốc của Day 4 (run `r2`, `sb compare`, Δ = B − A, điểm ×100)

| A → B | Δ nDCG@10 full [CI95] | Δ nDCG@10 condensed [CI95] | Δ Recall@10, p | `win_rule` | Slice tụt nhiều nhất |
|---|---|---|---|---|---|
| Cohere dense → hybrid | +0,38 [−1,73; +2,39] | +0,56 [−1,50; +2,60] | — | TIE | — |
| Cohere dense → hybrid + normalize | **+6,42 [+2,67; +10,75]** | +6,62 [+2,87; +10,92] | +3,32, p 0,001 | LOSE (slice) | amenity_negation −4,40 (n = 5) |
| Cohere hybrid → hybrid + normalize | +6,04 [+3,03; +9,77] | +6,06 [+3,03; +9,81] | +3,73, p < 0,001 | LOSE (slice) | multi_constraint −3,90 |
| e5s dense → hybrid | +2,06 [−1,50; +5,70] | +1,84 [−1,69; +5,46] | +0,19 | LOSE / TIE | cross_vertical −16,15 |
| e5s dense → hybrid + normalize | **+4,55 [+0,48; +8,75]** | +4,29 [+0,21; +8,44] | +1,85, p 0,049 | LOSE (slice) | cross_vertical −16,15 |
| e5s hybrid → hybrid + normalize | +2,49 [+0,84; +4,44] | +2,45 [+0,81; +4,42] | +1,66, p < 0,001 | LOSE (*) | multi_constraint 0,00 |

(*) không slice nào tụt; `LOSE` vì `win_rule` chỉ có WIN (Δrecall ≥ 2, p < 0,05, không slice thua > 3), TIE (|Δndcg| < 2), còn lại LOSE — ở đây
Δrecall 1,66 < 2 nên không WIN dù nDCG tăng có ý nghĩa. **Kết luận:** hybrid + normalize (cấu hình production) tốt nhất cho cả hai model; kết
luận "giữ dense làm mốc" của `eval-2026-10-01-search-v1-3arm.md` dựa trên số đo lỗi (mục 9) và không còn đúng.

## 9. Lỗi đo hybrid ngay sau khi nạp — tái hiện và guard

Tái hiện (`scratchpad bm25_probe.py`): nạp lại `ProductBench__e5_small` (guard vector READY sau 3,3 s), rồi mỗi 3 s chạy BM25 (`nameAscii^2`,
`searchTextAscii`) cho 10 câu gold:

| Thời điểm sau nạp | Top-10 khác trạng thái cuối | Tổng điểm BM25 3 câu đầu |
|---|---:|---|
| 0 – 58,7 s (20 lần đo) | 10/10 câu | 52,0 · 32,8 · 34,0 |
| 61,8 – 89,1 s (10 lần đo) | 0/10 câu | 133,7 · 80,9 · 171,6 |

Điểm nhảy một lần quanh giây 60 rồi đứng yên — phù hợp với việc Weaviate cập nhật thống kê độ dài thuộc tính cho BM25 theo chu kỳ (chưa đối
chiếu tài liệu Weaviate). Ảnh hưởng: lượt đo hybrid ngay sau khi tạo collection (Day 4 `20261001-day4-local`, lượt 1 hôm nay); dense không bị.
Production cũng có thể trả hybrid sai ~1 phút sau khi job index tạo collection mới — chưa kiểm trên Cloud.

Sửa: `app_adapter.load_collection` gọi `wait_bm25_settled` sau `wait_index_ready` — chụp top-10 + điểm BM25 của 5 câu thăm dò qua GraphQL, chờ
tới khi **đổi** so với lần đầu rồi giữ nguyên 2 lần liền (mỗi 3 s); không đổi trong 90 s thì coi là đã ổn định. Kiểm: `sb app-load --model
e5-small --recreate` (1 phút 16 s) rồi chạy ngay `APP.e5s.hybrid`, `APP.e5s.hybrid_norm` (run `20261005-e5s-guard`) → khác `r2` 4/131 câu mỗi
arm (trước guard: 68–93), nDCG@10 0,656 / 0,680 (r2: 0,655 / 0,680). 4 câu còn lại là nhiễu của đồ thị HNSW dựng mới.

## 10. Hub check và đường cong số chiều GTE (`scratchpad hub_dims.py`; dense exact trên `.npy` + vector truy vấn trong cache, 0 lượt API)

**Hub** — top-20 của 131 câu gold; hub = số lần lọt top-20 / kỳ vọng (131 × 20 / 3.183 = 0,823), `metrics.hub_scores`:

| Model | Hub max | Sản phẩm hub > 3 | Sản phẩm khác nhau trong top-20 | Sản phẩm hub cao nhất |
|---|---:|---:|---:|---|
| Cohere v3 | 14,58 | 299 | 1.437 | Moscow Hotel Ha Long (hotel · Hạ Long) |
| Cohere v4 / 1024 | 9,72 | 282 | 1.459 | Hào Anh Villa Hội An (hotel · Hội An) |
| e5-small | 13,36 | 297 | 1.429 | Tam Coc Thoms House (hotel · Ninh Bình) |
| e5-base | 15,79 | 270 | 1.454 | San Hô Đỏ Hostel (hotel · Rạch Giá) |
| e5-large-instruct | 12,15 | 286 | 1.425 | An Peaceful Homestay (hotel · Cát Bà) |
| BGE-M3 | 12,15 | 287 | 1.475 | Private Ninh Binh Full Day (attraction · Hà Nội) |
| GTE | 10,93 | 274 | 1.521 | Vinpearl Golf Nha Trang voucher (golf · Nha Trang) |

Ngưỡng `hub_score_max` 3,0 của spec giả định 500 câu ngẫu nhiên; 131 câu gold dồn theo điểm đến (nhiều câu cùng hỏi Hạ Long, Nha Trang…) nên
hub bị thổi lên ở **mọi** model. Đọc tương đối: các model cùng mức, không có "sản phẩm hút mọi câu" riêng của e5-small. Muốn đo đúng spec cần
bộ câu sinh (Part 7, chưa làm).

**GTE Matryoshka** — cắt vector document + truy vấn 768 → d chiều, chuẩn hoá lại, condensed-deep (như `eval-2026-10-02-search-local-fair.md`):

| Chiều | Recall@10 | nDCG@10 | MRR@10 | Δ nDCG vs 768 [CI95] | Δ Recall vs 768 [CI95] |
|---:|---:|---:|---:|---|---|
| 768 | 0,3531 | 0,6882 | 0,7281 | — | — |
| 512 | 0,3506 | 0,6879 | 0,7169 | −0,03 [−0,84; +0,83] | −0,25 [−1,27; +0,60] |
| 256 | 0,3444 | 0,6856 | 0,7163 | −0,26 [−1,69; +1,20] | −0,87 [−2,95; +0,51] |
| 128 | 0,3496 | 0,6847 | 0,7070 | −0,35 [−2,18; +1,34] | −0,35 [−2,47; +1,07] |

GTE giữ chất lượng tới 128 chiều. Không đổi quyết định model (e5-small hoà GTE ở 768 và rẻ hơn), nhưng là phương án dự phòng nếu cần vector nhỏ.

## 11. `cross_vertical` — vì sao e5-small kém 26 điểm

10 câu dạng "khách sạn, vé máy bay, vé tham quan [, sân golf] và combo du lịch ở X". 7 câu hai model gần như nhau; 3 câu tạo gần hết khoảng cách:

| qid | X | nDCG@10 Cohere → e5-small | e5-small đưa lên đầu |
|---|---|---|---|
| c0551 | Hà Nội | 0,86 → 0,00 | 5/5 combo "Vé máy bay khứ hồi **Hà Nội** – Hạ Long / Huế / Đà Lạt" (nhãn 0: sai điểm đến) |
| c0560 | Hải Phòng | 1,00 → 0,18 | combo khứ hồi tới Hạ Long, vé máy bay Đà Lạt – Hải Phòng (chưa nhãn) |
| c0569 | Nha Trang | 1,00 → 0,29 | vé máy bay Nghệ An / Đà Lạt – Nha Trang (chưa nhãn), combo Hạ Long |

e5-small bị chi phối bởi cụm "vé máy bay … combo" và khớp tên thành phố ở **điểm đi** trong tên combo / chuyến bay; Cohere giữ điểm đến tốt
hơn. Hai trong ba câu có kết quả chưa nhãn (cần gán ở D6a). Hướng xử lý (chưa làm): tách điểm đến thành filter `destination` (QU, arm S3 —
`/search` đã nhận filter này), hoặc thêm điểm đến vào text truy vấn có trọng số; đo lại `cross_vertical` sau khi gán D6a.

## 12. Việc còn lại có thể làm ngay

- **Gán nhãn D6a:** `gold/holes/gold_v3__D6a/` (`sb --run-id 20261005-e5s-app-r2 gold holes --arms APP.e5s.dense,APP.e5s.hybrid,APP.e5s.hybrid_norm
  --tag D6a --split`): 466 cặp / 92 câu (A 251, B 215) + 7 hole ngoài catalog tự gán 0. Sau khi gán: `sb gold holes import …` → tag `gold_v4` →
  `sb rescore --run-id 20261005-e5s-app-r2` → đặt lại `baseline_v1` trên gold_v4.
- **Model đã dùng (revision HF trong cache máy chạy):** e5-small `614241f6`, e5-base `d1287505`, e5-large-instruct `274baa43`, GTE `9bbca17d`;
  BGE-M3 tokenizer / config `5617a9f6` (main), trọng số `model.safetensors` từ revision `9a0624b8` (cả hai tải 01/10 13:33–13:36, trước khi embed
  15:28), fp32, CPU.

## 13. Lệnh tái sinh

```bash
cd src
sb() { PYTHONUTF8=1 python -m evaluation.search_bench "$@"; }
sb gold devtest --seed 42                       # gold/splits/devtest@gold_v3.json (đã có thì giữ)
sb app-load --model e5-small                    # ProductBench__e5_small (0 lượt gọi API); chạy một lượt khởi động trước khi đo (mục 1)
sb --run-id 20261005-e5s-app-r2 run --arm APP.e5s.dense --arm APP.e5s.dense_nocut --arm APP.e5s.hybrid --arm APP.e5s.hybrid_nocut \
   --arm APP.e5s.hybrid_norm --arm APP.e5s.hybrid_norm_nocut
COHERE_API_KEY=disabled-cache-only sb --run-id 20261005-e5s-app-r2 run --arm APP.dense --arm APP.hybrid --arm APP.hybrid_norm   # chỉ cache
sb --run-id 20261005-e5s-app-r2 compare APP.hybrid_norm APP.e5s.hybrid_norm [--condensed]
sb --run-id 20261005-e5s-app-r2 regress baseline --arm APP.e5s.hybrid_norm --note "…"
sb --run-id 20261005-e5s-app-r3 regress check [--split dev]
PYTHONPATH=. python sweep_cutoff.py APP.e5s.hybrid_norm dev -1 0.62 0.80 0.82 0.84 0.85 0.86 0.87 0.88 0.89   # phụ lục A
PYTHONPATH=. python sweep_cutoff.py APP.e5s.hybrid_norm test -1 0.62 0.84 0.85 0.86 0.87
PYTHONPATH=. python f1_smoke.py                                                                            # phụ lục B
PYTHONPATH=. python hub_dims.py                                                                            # phụ lục C
sb app-load --model e5-small --recreate && sb --run-id 20261005-e5s-guard run --arm APP.e5s.hybrid --arm APP.e5s.hybrid_norm   # mục 9
```

## Phụ lục A — `sweep_cutoff.py`

```python
"""Sweep cutoff `/search` trên split dev / test của gold. Chạy đúng `SearchProducts` của backend (cổng APP), cấu hình = arm gốc,
chỉ đổi `app.cutoff`. Không ghi run, không sửa config. Dùng (từ src/): python sweep_cutoff.py <arm> <dev|test|all> <cutoff> ..."""
import json
import sys

import numpy as np

from evaluation.search_bench import devtest as DT, paths, runner as R
from evaluation.search_bench.app_adapter import AppContext, retrieve_app
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.config import load_config, load_env
from evaluation.search_bench.embed import make_embedder

base, which, *cuts = sys.argv[1:]
load_env()
cfg = load_config(None)
env = R.load_env(cfg, "jsonl", paths.GOLD_JSONL, run_id="sweep")
keep = None if which == "all" else {q for q, s in DT.load(env.gold_version)["assignment"].items() if s == which}
arm0 = load_arm(base)
ctx = AppContext.open(cfg, "jsonl", model=arm0.model)
emb = make_embedder(cfg, arm0.model, embedding_type=arm0.embedding_types, preflight=False)
try:
    for c in map(float, cuts):
        arm = arm0.model_copy(update={"app": {**arm0.app, "cutoff": c}})
        _, rows = R.score_arm(env, retrieve_app(arm, env, ctx, emb))
        rows = [r for r in rows if keep is None or r["qid"] in keep]
        inc = [r for r in rows if not r["expected_no_result"]]
        ooc = [r for r in rows if r["expected_no_result"]]
        tot = [json.loads(r["extra"]).get("total") or 0 for r in rows]

        def m(key, rs=inc):
            v = [r[key] for r in rs if r.get(key) is not None and not (isinstance(r[key], float) and np.isnan(r[key]))]
            return float(np.mean(v)) if v else float("nan")
        print(c, len(rows), m("ndcg@10"), m("recall@10"), m("mrr@10"), m("judged@10"), m("condensed_ndcg@10"),
              m("zero_result"), m("zero_result", ooc), np.percentile(tot, 50), np.percentile(tot, 10))
finally:
    ctx.close()
    emb.close()
```

## Phụ lục B — `f1_smoke.py` (rút gọn phần in bảng)

```python
"""(a) 10 câu gold (qid tăng dần, câu thường có nhãn 2), filter từ sản phẩm nhãn 2 đầu tiên (5 câu taxonomy + destination, 3 câu chỉ
destination, 2 câu chỉ taxonomy) → mọi kết quả phải thoả filter. (b) BM25-only: `lexical.bm25` trên câu đã chuẩn hoá, top-10."""
from evaluation.search_bench import paths, runner as R
from evaluation.search_bench.app_adapter import AppContext
from evaluation.search_bench.arms import load_arm
from evaluation.search_bench.config import load_config, load_env
from evaluation.search_bench.embed import make_embedder

load_env()
cfg = load_config(None)
env = R.load_env(cfg, "jsonl", paths.GOLD_JSONL, run_id="f1")
arm = load_arm("APP.e5s.hybrid_norm")
ctx = AppContext.open(cfg, "jsonl", model=arm.model)
emb = make_embedder(cfg, arm.model, embedding_type=arm.embedding_types, preflight=False)
s, idx = ctx.make_search(arm.app, emb), ctx.cat.index
picks = []
for g in sorted(env.gold, key=lambda g: g.qid):
    top = [p for p, v in g.judgments.items() if v == 2 and idx.resolve(p) is not None]
    if not g.expected_no_result and top:
        picks.append((g, idx.units[idx.resolve(top[0])]))
    if len(picks) == 10:
        break
for (g, p), mode in zip(picks, ["both"] * 5 + ["destination"] * 3 + ["taxonomy"] * 2):
    tax = p.taxonomy if mode in ("both", "taxonomy") else None
    dest = p.destination if mode in ("both", "destination") else None
    res = s.engine(g.text, taxonomy=tax, destination=dest, limit=50)["results"]
    assert all((tax is None or r["taxonomy"] == tax) and (dest is None or r["destination"] == dest) for r in res)
vs = ctx.vector_search()
retrieved = [R.Retrieved(qid=g.qid, top_ids=[h.product_id for h in vs.bm25(s.engine.query_text(g.text), None, 10)
                                             if h.product_id in idx.idx], top_scores=[], applied_filter=None, latency_ms=0.0, extra={})
             for g in env.gold]
_, rows = R.score_arm(env, retrieved)   # so với per_query của APP.e5s.hybrid_norm (run r2) theo qid, chia all / dev / test
```

## Phụ lục C — `hub_dims.py` (mục 10; chạy từ `src/` với `PYTHONPATH=.`)

```python
"""Day 5 Search (05/10) — hai so sánh còn thiếu của plan Day 4–5 §2.1, dense exact trên vector .npy + vector truy vấn trong cache
(0 lượt gọi API, không embed lại). Chạy từ `src/` với PYTHONPATH=. :

(1) Hub check: với 131 câu gold active, top-20 cosine chính xác trên 3.183 unit; hub score của sản phẩm = số lần lọt top-20 / kỳ vọng
    (131 × 20 / 3.183 ≈ 0,82) — `metrics.hub_scores`. Báo max, số sản phẩm có hub > 3 (ngưỡng `hub_score_max` 3,0) và sản phẩm đầu.
(2) Đường cong số chiều GTE (Matryoshka): cắt vector GTE 768 → 512 / 256 / 128 (cả document lẫn query), chuẩn hoá L2 lại, chấm
    condensed-deep như `eval-2026-10-02-search-local-fair.md` (xếp cả catalog, giữ sản phẩm đã có nhãn, top-10), paired bootstrap so 768.
"""
import json
import sqlite3

import numpy as np
import pandas as pd

from evaluation.search_bench import metrics as M, paths
from evaluation.search_bench.config import load_config
from evaluation.search_bench.embed.cache import cache_key
from evaluation.search_bench.gold_schema import read_gold_jsonl

cfg = load_config()
root = paths.repo_root()
data = root / "bench_out/search/data"
gold = [g for g in read_gold_jsonl(paths.GOLD_JSONL) if g.status == "active"]
J = {g.qid: {p: int(l) for p, l in g.judgments.items()} for g in gold}
db = sqlite3.connect(str(root / "bench_out/search/cache/embeddings.sqlite"))
items = pd.read_parquet(data / "items.parquet").set_index("product_id")


def qv(name):
    return np.vstack([np.frombuffer(db.execute("SELECT vec FROM embeddings WHERE key=?",
                                               (cache_key(name, "query", g.text),)).fetchone()[0], dtype=np.float32) for g in gold])


def nz(x):
    return x / np.linalg.norm(x, axis=1, keepdims=True)


MODELS = [("cohere-v3", "embed-multilingual-v3.0"), ("cohere-v4-1024", "embed-v4.0@d1024"), ("e5-small", "intfloat/multilingual-e5-small"),
          ("e5-base", "intfloat/multilingual-e5-base"), ("e5-large-instruct", "intfloat/multilingual-e5-large-instruct"),
          ("bge-m3", "BAAI/bge-m3"), ("gte-mb", "Alibaba-NLP/gte-multilingual-base")]
VEC = {"cohere-v4-1024": "cohere-v4"}

print("## (1) Hub check — top-20 dense exact, 131 câu gold, kỳ vọng mỗi sản phẩm %.3f lần" % (len(gold) * 20 / 3183))
print("| Model | hub max | sản phẩm hub > 3 | sản phẩm khác nhau trong top-20 | sản phẩm hub cao nhất (taxonomy · destination) |")
print("|---|---:|---:|---:|---|")
for mk, name in MODELS:
    ids = json.loads((data / f"vec_T3+R_{VEC.get(mk, mk)}.ids.json").read_text())
    S = nz(qv(name)) @ nz(np.load(data / f"vec_T3+R_{VEC.get(mk, mk)}.npy")).T
    top = [[ids[j] for j in row] for row in np.argsort(-S, axis=1)[:, :20]]
    h = M.hub_scores(top, len(ids), 20)
    p, v = max(h.items(), key=lambda kv: kv[1])
    it = items.loc[p] if p in items.index else None
    label = f"{it['name'][:40]} ({it['taxonomy']} · {it['destination']})" if it is not None else p
    print(f"| {mk} | {v:.2f} | {sum(x > 3 for x in h.values())} | {len(h)} | {label} |")

print("\n## (2) GTE Matryoshka — condensed-deep, Δ so với 768 (paired bootstrap 1.000 lượt, seed 42)")
ids = json.loads((data / "vec_T3+R_gte-mb.ids.json").read_text())
D = np.load(data / "vec_T3+R_gte-mb.npy")
Q = qv("Alibaba-NLP/gte-multilingual-base")
res = {}
for d in (768, 512, 256, 128):
    S = nz(Q[:, :d]) @ nz(D[:, :d]).T
    order = np.argsort(-S, axis=1)
    rows = []
    for i, g in enumerate(gold):
        j = J[g.qid]
        cond = [ids[k] for k in order[i] if ids[k] in j][:10]
        rows.append(dict(qid=g.qid, slice=g.slice, recall=M.recall_at_k(cond, j, 10, 1), ndcg=M.ndcg_at_k(cond, j, 10),
                         mrr=M.mrr_at_k(cond, j, 10, 2)))
    res[d] = pd.DataFrame(rows)
print("| Chiều | Recall@10 | nDCG@10 | MRR@10 | Δ nDCG vs 768 [CI95] | Δ Recall vs 768 [CI95] |")
print("|---:|---:|---:|---:|---|---|")
base = res[768].set_index("qid")
for d, df in res.items():
    x = df.set_index("qid")
    if d == 768:
        cn = cr = "—"
    else:
        bn = M.paired_bootstrap(base["ndcg"].to_dict(), x["ndcg"].to_dict(), n_boot=1000, seed=42)
        br = M.paired_bootstrap(base["recall"].to_dict(), x["recall"].to_dict(), n_boot=1000, seed=42)
        cn = f"{bn['delta']:+.2f} [{bn['ci95'][0]:+.2f}; {bn['ci95'][1]:+.2f}]"
        cr = f"{br['delta']:+.2f} [{br['ci95'][0]:+.2f}; {br['ci95'][1]:+.2f}]"
    print(f"| {d} | {df.recall.mean():.4f} | {df.ndcg.mean():.4f} | {df.mrr.mean():.4f} | {cn} | {cr} |")
```

## Phụ lục D — `bm25_probe.py` (mục 9; `python bm25_probe.py e5-small 90`)

```python
"""Tái hiện: sau khi nạp lại collection APP, kết quả BM25 có đổi theo thời gian không. Chạy từ src/ với PYTHONPATH=. :
python bm25_probe.py <model> <giây> — nạp lại ProductBench__<model> (--recreate), rồi mỗi 3 s truy vấn BM25 cho 10 câu gold,
in thời điểm + số câu có top-10 khác lần đo cuối cùng (coi lần cuối là trạng thái ổn định)."""
import sys
import time

from evaluation.search_bench import paths, runner as R
from evaluation.search_bench.app_adapter import AppContext, app_collection, build_app_catalog, load_product_bench, model_vectors
from evaluation.search_bench.config import load_config, load_env

model, secs = sys.argv[1], float(sys.argv[2])
load_env()
cfg = load_config(None)
env = R.load_env(cfg, "jsonl", paths.GOLD_JSONL, run_id="probe")
qs = [g.text for g in env.gold][:40:4]
cat = build_app_catalog(cfg, "jsonl", model_version=model_vectors("jsonl", model)[3])
t0 = time.monotonic()
s = load_product_bench(cfg, "jsonl", cat, collection=app_collection(model), recreate=True, model=model)
print(f"nạp xong sau {time.monotonic() - t0:.1f} s ({s['loaded']} object; guard vector READY đã chờ)", flush=True)
ctx = AppContext.open(cfg, "jsonl", model=model, ensure_loaded=False)
vs = ctx.vector_search()
snaps = []
t1 = time.monotonic()
while time.monotonic() - t1 < secs:
    snaps.append((time.monotonic() - t1, [tuple(h.product_id for h in vs.bm25(q, None, 10)) for q in qs],
                  [round(sum(h.score for h in vs.bm25(q, None, 10)), 3) for q in qs[:3]]))
    time.sleep(3)
final = snaps[-1][1]
for t, ids, sc in snaps:
    print(f"t+{t:5.1f}s  khác trạng thái cuối: {sum(a != b for a, b in zip(ids, final))}/{len(qs)} câu · tổng điểm BM25 3 câu đầu {sc}")
ctx.close()
```
