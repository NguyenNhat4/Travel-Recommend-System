# Search query plan (Phase A) qua pipeline thật — F3 phủ định, F4 loại sản phẩm, F5 chiều bay, F6 giá/sao: số chẩn đoán Sprint 1 trên gold_v3

- Ngày chạy và viết: **05/10/2026** (tối; Sprint 1 theo plan `fix/search` Phase A).
- Phục vụ: **FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01**; kiến trúc `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` §4–§6, §11
  (guard Forbidden@10, filter pass, direction). **Không phải số nghiệm thu**: gold_v3 chỉ có 5 câu phủ định (`filter: null`), 1 câu tuyến
  bay có hai đầu (c0373), 3 câu lẫn loại; gold v4 (người dùng đang gán) mới quyết định bật cờ.
- Nhánh `fix/search`, HEAD `942f5aa`; code backend + bench của report này ở working tree **chưa commit** —
  `history/2026-10-05-search-query-plan-f3-f6.md`, `history/2026-10-05-search-bench-query-plan-guards.md`.
- Run `2026-10-05-fix-search-qp` (8 arm `APP.e5s.*`, collection `ProductBench_e5_small` 3.183 object, e5-small 384 chiều, Weaviate bench
  Docker local, `query embed: cache 131/131`). Mốc so sánh cũ: `2026-10-05-e5s-det`, `2026-10-05-fix-search-e5s`.
- Gold `gold_v3` SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`, 131 câu active (128 trong catalog), 4.991
  nhãn; **không thêm nhãn**. Judged@10 của e5 0,79–0,86 → đọc condensed cạnh full.
- Engine: đúng `SearchProducts` của backend (`src/evaluation/search_bench/app_adapter.py`), hybrid + normalize production (`candidate_k 200,
  rrf_k 60, lexical_k 10, lexical_cutoff 0.50, min_coverage 0.6, lexical_candidate_k 50`); 4 cờ query plan mặc định tắt.
- **Không có arm Cohere, chưa đo HTTP** (adapter e5 trong backend chờ chốt đề xuất FR-SRC-02).

## 1. Kết luận ngắn

1. **Cờ tắt ≡ hôm nay — đã kiểm trên bench thật.** Mốc `APP.e5s.hybrid_norm_nocut` chạy lại với mã mới (config_hash đổi vì thêm 4 khoá)
   trùng **131/131** `top_ids` với run det 05/10; mốc `APP.e5s.hybrid_norm_dest_nodia_nc80` trùng **131/131** với run 05/10. Lần chạy đầu chỉ
   trùng 124/131: 7 câu `multi_constraint` bị xếp lại vì use case áp sắp xếp sao mềm khi plan *parse ra* sao thay vì khi sao *đang áp* —
   lỗi test đơn vị không thấy (so hai engine cùng mã), bench identity bắt được; đã sửa và thêm test.
2. **F3 phủ định tiện ích làm đúng việc của nó.** Forbidden@10 trên 5 câu phủ định: mốc 7/10 · 7/10 · 2/10 · 8/10 · 4/10 → `_neg` **0/10 cả
   năm** (`forbidden_query_rate` 0,875 → 0,25, hai câu còn hits là tuyến bay/lẫn loại không thuộc F3). `amenity_negation` nDCG **+8,95**
   full / **+19,58** condensed; mọi slice khác bất biến (chỉ 5 câu áp). `filter_recall_loss` 31: 31 nhãn rel ≥ 1 của sản phẩm **có ghi**
   tiện ích bị phủ định — chúng là nhãn 1 theo quy ước cũ "có tiện ích bị loại trừ → tối đa 1" (gold-guide 30/09 #3 đổi thành 0) → không
   phải engine sai, là nhãn cũ cần rà khi làm gold v4.
3. **F6 giá/sao suy từ câu**: `multi_constraint` nDCG **+11,04** full / **+11,75** condensed (9 câu, giá hard + sao mềm). `filter_recall_loss`
   72 — nhãn rel ≥ 1 cho sản phẩm vượt giá trần hoặc sao thấp hơn (gold chấm liên quan không bắt buộc đúng giá) → ghi nhận để gold v4
   định nghĩa lại hoặc chấp nhận loại.
4. **F5 chiều bay**: áp 3 câu; c0373 "Vé máy bay Buôn Ma Thuột - Hà Nội" từ 9/10 kết quả **sai chiều/sai tuyến** về **0/1** (catalog chỉ có một
   tuyến BMT→HN). `dest_type` −2,43 vì c0070/c0078 ("vé máy bay đến Hà Nội", "đường bay tới Huế") giờ khoá đích → kết quả ít hơn, nhãn
   cũ chấm cả tuyến khác. Cần gold v4 có `origin/destination_city` để chấm đúng.
5. **F4 loại sản phẩm suy từ câu — chưa dùng được với bảng cue hiện tại.** 99/131 câu bị khoá một loại; `abbrev_typo` **−6,09**,
   `amenity_negation` −5,89 (vượt guard 3,0), `filter_recall_loss` **148**: gold chấm nhiều loại cho câu nêu một loại ("KDL NT cho gia
   đình" 0,484 → 0,167; "combo vui chơi PQ dưới 2tr" 0,671 → 0,462; "resort Hoi An cho gd co tre nho" 1,000 → 0,699). Ba nguyên nhân:
   (a) cue `khu du lịch`/`kdl`/`nghỉ dưỡng` và `combo` không đồng nghĩa với taxonomy; (b) gold không coi loại là hard constraint ở các slice
   này; (c) Judged tụt (0,842 → 0,801) vì sản phẩm mới lọt top-10 chưa có nhãn. Ngược lại "tìm vé VW Nha Trang" 0,743 → 0,905, "vé Safari
   PQ" 0,709 → 0,852 — F4 có giá trị khi câu rõ loại. **Khuyến nghị:** giữ `SEARCH_TAXONOMY_FILTER` tắt; Sprint 2 thu hẹp bảng cue về cụm rõ
   loại (vé/voucher/máy bay/golf), bỏ `kdl`/`nghỉ dưỡng`/`combo` khỏi hard, đo lại trên slice lẫn loại của gold v4.
6. **Tổ hợp**: `_qp` (cả bốn) so mốc: nDCG +0,36 full / +1,18 cond, recall −0,82 (do F4); Forbidden@10 **0/0** trên cả 8 câu chẩn đoán.
   Trên mốc có cutoff + F1 + F2(0,80): `_nc80_qp` −0,56 full / +0,23 cond, recall −1,06 (F4). `revalidatedDrops` = 0 và `emptyReason` không
   xuất hiện ở câu nào (filter-first không làm rỗng câu gold nào; `filter_pass_rate` 1,0).
7. Latency: Weaviate p50 ~41–53 ms (local Docker); arm có F4/F1 nhanh hơn (mask nhỏ: 11–42 ms p50).

## 2. Bảng tổng (nguyên văn `results.json` + đếm từ `per_query.parquet`)

| arm | R@10 | nDCG@10 | Judged | nDCG cond | forbidden_at_10 | forbidden_query_rate | filter_pass_rate | filter_recall_loss Σ | applied (số câu) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| APP.e5s.hybrid_norm_nocut (mốc) | 0.3346 | 0.6769 | 0.842 | 0.6870 | 0.525 | 0.875 | – | 0 | {} |
| APP.e5s.hybrid_norm_nocut_neg | 0.3352 | 0.6804 | 0.829 | 0.6947 | 0.175 | 0.25 | 1.0 | 31 | mustNot 5 |
| APP.e5s.hybrid_norm_nocut_tax | 0.3269 | 0.6664 | 0.801 | 0.6791 | 0.553 | 0.75 | 1.0 | 148 | taxonomy 99 |
| APP.e5s.hybrid_norm_nocut_route | 0.3331 | 0.6746 | 0.840 | 0.6848 | 0.465 | 0.75 | 1.0 | 0 | route 3 |
| APP.e5s.hybrid_norm_nocut_num | 0.3315 | 0.6835 | 0.837 | 0.6952 | 0.525 | 0.875 | 1.0 | 72 | price 10, star 9 |
| APP.e5s.hybrid_norm_nocut_qp | 0.3264 | 0.6805 | 0.789 | 0.6988 | 0.0 | 0.0 | 1.0 | 248 | taxonomy 99, route 3, mustNot 5, price 10, star 9 |
| APP.e5s.hybrid_norm_dest_nodia_nc80 | 0.3562 | 0.7013 | 0.863 | 0.7149 | 0.512 | 0.875 | 1.0 | 10 | {} (F1 108 câu) |
| APP.e5s.hybrid_norm_dest_nodia_nc80_qp | 0.3457 | 0.6957 | 0.837 | 0.7172 | 0.0 | 0.0 | 1.0 | 258 | như `_qp` + F1 |

`forbidden_at_10` = Σ hits / Σ n trên 8 câu có AST cấm (`config/forbidden_v3.yaml` — chẩn đoán, không phải gold); mốc không có
`applied_filter` nên `filter_pass_rate` không định nghĩa. `emptyReason`, `revalidatedDrops`: 0 ở mọi arm.

### 2.1 Forbidden@10 từng câu (hits/n trong top-10)

| arm | c0241 hồ bơi | c0244 bếp riêng | c0247 ban công | c0250 nhà hàng | c0253 đưa đón | c0373 BMT→HN | c0070 đến HN | c0088 golf Hội An |
|---|---|---|---|---|---|---|---|---|
| mốc nocut | 7/10 | 7/10 | 2/10 | 8/10 | 4/10 | 9/10 | 0/10 | 5/10 |
| `_neg` (F3) | **0/10** | **0/10** | **0/10** | **0/10** | **0/10** | 9/10 | 0/10 | 5/10 |
| `_tax` (F4) | 7/10 | 7/10 | 5/10 | 8/10 | 6/10 | 9/10 | 0/10 | **0/6** |
| `_route` (F5) | 7/10 | 7/10 | 2/10 | 8/10 | 4/10 | **0/1** | 0/10 | 5/10 |
| `_num` (F6) | 7/10 | 7/10 | 2/10 | 8/10 | 4/10 | 9/10 | 0/10 | 5/10 |
| `_qp` (F3–F6) | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/1 | 0/10 | 0/6 |
| mốc nc80 (F1+F2) | 7/10 | 7/10 | 3/10 | 7/10 | 3/10 | 9/10 | 0/10 | 5/10 |
| `_nc80_qp` | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/1 | 0/10 | 0/1 |

c0088 "voucher golf tại Hội An": F4 khoá taxonomy golf → 6 kết quả (catalog có 6 unit golf), không còn vé tham quan — đúng ví dụ mở đầu
của kiến trúc. c0373: catalog chỉ có một tuyến BMT→HN nên F5 trả 1 kết quả đúng chiều.

## 3. So cặp có CI (paired bootstrap 1.000, Δ = B − A, điểm %; win rule WIN nếu Δrecall ≥ 2 & p < 0,05 & slice thua ≤ 3; TIE nếu |ΔnDCG| < 2)

| A → B | thang | Δrecall@10 [CI95], p | ΔnDCG@10 [CI95], p | slice đổi (Δ nDCG) | kết luận |
|---|---|---|---|---|---|
| mốc → `_neg` | full | +0,07 [−0,31; +0,53], 0,391 | +0,35 [−0,41; +1,44], 0,268 | amenity_negation **+8,95**; khác 0,00 | TIE |
| | cond | +0,07 | +0,76 [−0,06; +1,93], 0,040 | amenity_negation **+19,58** | TIE |
| mốc → `_tax` | full | −0,77 [−1,70; +0,15], 0,947 | −1,05 [−2,57; +0,52], 0,909 | abbrev_typo **−6,09**, amenity_negation −5,89, no_diacritics −2,33, multi_constraint +1,32 | TIE (guard slice vỡ) |
| | cond | −0,77 | −0,79 [−2,24; +0,75] | abbrev_typo −3,92, amenity_negation −6,08 | TIE |
| mốc → `_route` | full / cond | −0,14 [−0,43; +0,00] | −0,23 [−0,68; +0,00] | dest_type −2,43 (c0070, c0078) | TIE |
| mốc → `_num` | full | −0,30 [−0,61; −0,02], 0,987 | +0,67 [−0,19; +1,77], 0,070 | multi_constraint **+11,04**, abbrev_typo −1,17 | TIE |
| | cond | −0,30 | +0,81 [+0,05; +1,86], 0,014 | multi_constraint **+11,75** | TIE |
| mốc → `_qp` | full | −0,82 [−1,84; +0,28], 0,934 | +0,36 [−1,59; +2,34], 0,350 | amenity_negation +9,26, multi_constraint +10,66, dest_type +2,32, abbrev_typo −6,21, no_diacritics −2,33 | TIE |
| | cond | −0,82 | +1,18 [−0,76; +3,11], 0,120 | amenity_negation +23,02, multi_constraint +10,73, abbrev_typo −3,92 | TIE |
| nc80 → `_nc80_qp` | full | −1,06 [−2,07; −0,01], 0,975 | −0,56 [−2,80; +1,53], 0,722 | amenity_negation +10,83, multi_constraint +10,08, abbrev_typo −4,08, no_diacritics −4,57 | TIE |
| | cond | −1,06 | +0,23 [−1,94; +2,29], 0,430 | amenity_negation +24,29, multi_constraint +9,23, abbrev_typo −3,57, no_diacritics −3,85 | TIE |

Đọc: phần được của F3/F6 nằm ở 14 câu, phần mất của F4 trải trên ~99 câu → tổng gần hoà; win rule không bắt được vì Δrecall < 2 cả hai
chiều. Quyết định phải theo **từng cờ**, không theo tổ hợp.

## 4. Kiểm tổng hợp không nhãn (`sb qu gold-scan`, mọi cờ bật, parser thật của backend)

131 câu · 3.183 unit · 19 thành phố bay · 19 mã IATA. amenity_negation `must_not` **5/5** · cross_vertical taxonomy None **10/10** · dest_type
≤ 1 vertical **12/12** · multi_constraint destination **9/9**, price_max **9/9**, star_min **9/9** · route c0373 **1/1**. Đây là kiểm độ chính xác
parse theo **định nghĩa câu** (filter/child_filter của gold, không dùng judgments) — chỉ báo parser không lệch với cách gold mô tả câu.

## 5. Caveat

1. Trong mẫu, n nhỏ: F3 5 câu, F5 3 câu (1 câu hai đầu), lẫn loại 3 câu. Guard chỉ **khai**, chưa enforce; ngưỡng (đề xuất) chờ chốt Sprint 2.
2. `forbidden_v3.yaml` là AST **tôi suy từ câu**, không phải nhãn người; gold v4 có trường cấm thì gold thắng (`gold_fields` cấu hình được vì
   tên trường chưa chốt).
3. `filter_recall_loss` lớn ở F4/F6 phản ánh **cách gold chấm** (liên quan không bắt buộc đúng loại/giá, nhãn 1 theo quy ước cũ) nhiều hơn lỗi
   engine — nhưng cũng là bằng chứng F4 với cue hiện tại thu hẹp quá tay.
4. Chưa có arm Cohere; chưa đo HTTP (NFR-PERF-01) — adapter e5 backend chờ chốt FR-SRC-02. Weaviate p50 ở Docker local không đại diện cloud.
5. 48 test bench fail có sẵn (fixture CRLF, streamlit) không đổi; test mới không dùng fixture đó.

## 6. Lệnh tái sinh

```bash
# từ src/, .venv-sbench, PYTHONPATH=<repo>/src PYTHONUTF8=1, Weaviate bench 127.0.0.1:58080
sb --run-id 2026-10-05-fix-search-qp run --arm APP.e5s.hybrid_norm_nocut --arm APP.e5s.hybrid_norm_nocut_neg \
  --arm APP.e5s.hybrid_norm_nocut_tax --arm APP.e5s.hybrid_norm_nocut_route --arm APP.e5s.hybrid_norm_nocut_num \
  --arm APP.e5s.hybrid_norm_nocut_qp --arm APP.e5s.hybrid_norm_dest_nodia_nc80 --arm APP.e5s.hybrid_norm_dest_nodia_nc80_qp
sb topids-diff 2026-10-05-fix-search-qp APP.e5s.hybrid_norm_nocut --run-b 2026-10-05-e5s-det            # 131/131
sb topids-diff 2026-10-05-fix-search-qp APP.e5s.hybrid_norm_dest_nodia_nc80 --run-b 2026-10-05-fix-search-e5s   # 131/131
sb --run-id 2026-10-05-fix-search-qp compare APP.e5s.hybrid_norm_nocut APP.e5s.hybrid_norm_nocut_neg [--condensed]   # và các cặp §3
sb qu gold-scan
```

Bảng §2/§2.1 đọc `results.json` (`overall.forbidden_at_10`, `forbidden_query_rate`, `filter_pass_rate`, `filter_recall_loss`) và
`per_query.parquet` (`forbidden_hits/n`, `extra.queryPlan.applied/emptyReason/revalidatedDrops`).
