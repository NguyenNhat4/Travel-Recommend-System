# Search local — so 5 model embedding trên cùng một thang đo (condensed-deep, không bù nhãn)

- Ngày chạy và viết: **02/10/2026**.
- Phục vụ: **FR-SRC-01..04, AC-SRC-01** (chất lượng truy xuất). Không đo lại latency; số latency trích từ [report Day 4–5](eval-2026-10-01-search-day4-local.md) §6.1, phục vụ NFR-PERF-01.
- Nhánh: `bench_search_recomSys`, HEAD `d7ea30a0f2fba9c59d9deadfbcd6e942a828a1bf`.
- Run nguồn: `20261002-day5-local-ranking` (5 arm `E2.e5s`, `E2.e5`, `E2.gte`, `E2.bge`, `E2.e5L`). Report này **không chạy retrieval mới trên Weaviate**: dùng lại vector document và vector câu hỏi đã cache của run đó, tính lại thứ hạng bằng cosine chính xác trong NumPy.
- Gold: `gold_v3`, SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`; 131 câu active, 4.991 nhãn active. **Không thêm nhãn nào.**
- Catalog: snapshot `2026-09-23`, 3.183 search unit, text `T3+R` (`catalog-text-v2`).
- Script tính: [Phụ lục A](#phụ-lục-a--script-tính-lại). Đã đối chiếu: top-10 tính lại **khớp 131/131 câu** với `per_query.parquet` của run nguồn ở cả 5 model.

## 1. Kết luận ngắn

1. **Xếp hạng trong report Day 4–5 (e5-base hơn các model khác 6–11 điểm nDCG) chủ yếu do độ phủ nhãn không đều, không phải do model.** e5-base có 100% kết quả top-10 đã được gán nhãn; bốn model còn lại thiếu 20–28%, và cách chấm full tính phần thiếu nhãn là "không liên quan".
2. **Khi đưa cả 5 model về cùng tập sản phẩm đã có nhãn, e5-small, BGE-M3, e5-base và GTE không phân biệt được về mặt thống kê**: nDCG@10 nằm trong khoảng 0,688–0,712, mọi khoảng tin cậy 95% của chênh lệch đều chứa 0.
3. **e5-large-instruct là model duy nhất kém rõ ràng:** thua e5-small 3,47 điểm nDCG (CI [−6,35; −0,44]) và thua BGE-M3 3,22 điểm (CI [−5,83; −0,66]). Nó cũng chậm nhất (p95 tạo vector 284 ms).
4. **Khi chất lượng hòa, quyết định theo chi phí → khuyến nghị e5-small / 384 chiều** làm model local chính: tạo vector câu hỏi p95 11 ms (nhanh hơn e5-base khoảng 6 lần), vector nhỏ bằng một nửa, re-index nhanh khoảng 2,5 lần. e5-base / 768 là dự phòng nếu đo pipeline thật thấy thiếu chất lượng.
5. **Về số chiều:** model 384 chiều hòa với các model 768 và 1024 chiều trên catalog và bộ câu hỏi này. Chưa có bằng chứng tăng số chiều cải thiện chất lượng.

Phương pháp chấm ở đây có một thiên lệch đã biết, hơi có lợi cho các model thiếu nhãn (§4.4). Vì vậy câu kết luận an toàn là **"e5-small hòa e5-base"**, không phải "e5-small thắng e5-base".

FR-SRC-02 trong PRD vẫn quy định Cohere v3 / 1024. Report chỉ cung cấp bằng chứng; muốn đổi model vận hành cần đề xuất trong `docs/prd/update/` và được chốt trước.

## 2. Vì sao phải đo lại

### 2.1 Gold được dựng bằng pooling, không chấm cả catalog

Gold không gán nhãn cho cả 3.183 sản phẩm của mỗi câu hỏi (131 × 3.183 ≈ 417.000 cặp). Gold chỉ gán nhãn cho những sản phẩm **mà một model nào đó đã trả về**: lấy top-k của các model, gộp thành "pool", rồi người gán nhãn chấm pool đó. Khi có model mới, các sản phẩm mới xuất hiện trong top-10 của nó được gọi là "hole" và được bù nhãn theo đợt. Lịch sử pool theo `gold/changelog.yaml`:

| Đợt | Model được quét | Giới hạn | Hệ quả |
|---|---|---|---|
| gold_v1 | pool ban đầu (depth 15) | — | 3.359 nhãn |
| D4a → gold_v2 | B0 (Cohere v3), **e5-base** | **không giới hạn** | top-10 của e5-base được gán nhãn đủ |
| D4b | APP.dense / hybrid / hybrid_norm (cùng Cohere v3) | không giới hạn | không liên quan tới model local |
| D5a → gold_v3 | GTE, BGE, e5-small, v4 × 4 | **cap 700 cặp cho cả 7 model** | còn sót nhiều hole |
| — | e5-large-instruct | chưa từng quét | — |

### 2.2 Số kết quả chưa nhãn trong top-10, trên gold_v3

| Model | ID chưa nhãn trong top-10 / 1.310 | Judged@10 |
|---|---:|---:|
| e5-small | 277 | 0,789 |
| e5-base | **0** | **1,000** |
| GTE | 363 | 0,723 |
| BGE-M3 | 259 | 0,802 |
| e5-large-instruct | 271 (8 thuộc câu ngoài catalog) | 0,793 |

### 2.3 Vì sao điều này làm lệch kết quả

Cách chấm **full** coi mọi sản phẩm chưa có nhãn là `rel = 0` (không liên quan). Trong khi đó, một sản phẩm chưa có nhãn chỉ có nghĩa là *chưa ai chấm*, không có nghĩa là *sai*. Vì vậy:

- e5-base không bị trừ điểm oan nào vì toàn bộ top-10 đã có nhãn.
- Các model còn lại bị tính 0 cho 20–28% kết quả, kể cả những kết quả thực ra phù hợp.

Hai model khác nhau đang bị chấm trên hai thang khác nhau. Chênh lệch đo được là tổng của *chất lượng model* và *mức độ được gán nhãn*, không tách ra được.

## 3. Ba cách chấm khi nhãn chưa đầy đủ

Các chỉ số Recall@10, nDCG@10, MRR@10 và Judged@10 giữ đúng định nghĩa và code của `metrics.py` (giải thích chi tiết ở report Day 4–5 §3). Ba cách chấm dưới đây chỉ khác nhau ở **danh sách 10 kết quả nào được đem đi chấm**.

### 3.1 Full — cách chấm chính của bench hiện tại

- **Làm gì:** lấy nguyên top-10 model trả về; sản phẩm chưa nhãn tính `rel = 0`.
- **Ưu điểm:** đúng như người dùng thấy; dễ hiểu.
- **Nhược điểm:** chỉ công bằng khi mọi model có Judged@10 gần bằng nhau. Model không góp vào pool bị phạt (đây là "pool bias" kinh điển trong đánh giá truy hồi thông tin).
- **Dùng khi:** độ phủ nhãn đã đủ và đều giữa các model (gate Judged ≥ 0,80, từng slice ≥ 0,70).

### 3.2 Condensed nông — `condensed_*` trong `metrics.add_condensed_metrics`

- **Làm gì:** lấy top-10 đã lưu, **bỏ** sản phẩm chưa nhãn, dồn hạng lên. **Không** lấy thêm từ hạng 11 trở đi.
- **Ví dụ:** top-10 có 3 sản phẩm chưa nhãn → danh sách condensed chỉ còn 7 sản phẩm.
- **Ưu điểm:** không phạt sản phẩm chưa nhãn ở vị trí đầu danh sách (dồn hạng).
- **Nhược điểm:** model nào nhiều kết quả chưa nhãn thì danh sách ngắn hơn. Danh sách ngắn hơn không thể có Recall cao bằng, và nDCG vẫn bị kéo xuống vì ít "ô" hơn để chứa sản phẩm đúng. **Vẫn chưa cùng thang.** Đây là cột "nDCG condensed" trong report Day 4–5.

### 3.3 Condensed-deep — cách dùng trong report này

- **Làm gì:** model xếp hạng **toàn bộ 3.183 sản phẩm** theo cosine; từ danh sách đó **chỉ giữ những sản phẩm đã có nhãn gold cho câu hỏi đó**, theo đúng thứ tự model xếp; lấy 10 sản phẩm đầu tiên.
- **Ví dụ:** model trả `[A?, B✓, C?, D✓, E✓, …]` (? = chưa nhãn, ✓ = có nhãn) → danh sách chấm là `[B, D, E, …]` cho tới đủ 10 sản phẩm có nhãn.
- **Tính chất quan trọng:**
  - Mọi model được chấm **trên cùng một tập ứng viên cho mỗi câu**: tập sản phẩm đã có nhãn trong gold_v3 (median 38 nhãn/câu, ít nhất 21). Câu hỏi nào cũng có ≥ 10 sản phẩm có nhãn, nên mọi danh sách đều đủ 10.
  - Judged@10 = **1,000 cho mọi model theo cấu tạo**. Không còn yếu tố "được gán nhãn nhiều hay ít".
  - Nếu một model không có kết quả chưa nhãn nào (e5-base), condensed-deep **trùng với full**. Điều này đúng ở bảng §4.1: e5-base có cùng số ở cả hai cách.
- **Bản chất:** đo khả năng **xếp đúng thứ tự** của model trên một tập sản phẩm cố định, đã có đáp án. Đây là cách "condensed list" được đề xuất cho đánh giá với nhãn không đầy đủ (Sakai, *Alternatives to Bpref*, SIGIR 2007).
- **Độ sâu phải đi xuống:** để gom đủ 10 sản phẩm có nhãn, model phải xếp xuống tới:

| Model | Hạng của sản phẩm có nhãn thứ 10: median | p90 | max |
|---|---:|---:|---:|
| e5-small | 12 | 40 | 276 |
| e5-base | 10 | 10 | 10 |
| GTE | 14 | 68 | 609 |
| BGE-M3 | 12 | 38 | 157 |
| e5-large-instruct | 12 | 36 | 257 |

Với phần lớn câu, chỉ cần đi xuống thêm 2–4 hạng; một số câu phải đi rất sâu, đó là các câu model trả nhiều sản phẩm mà chưa ai chấm.

### 3.4 Kiểm chứng chéo — tập con mà cả 5 model đều đủ nhãn

Cách kiểm thứ ba, không cần giả định gì về sản phẩm chưa nhãn: chỉ giữ các câu mà **top-10 gốc của cả 5 model đều đã có nhãn đầy đủ**, rồi chấm full trên tập câu đó. Trên tập con này full là công bằng tuyệt đối, nhưng cỡ mẫu nhỏ: chỉ **18 câu**, và nghiêng về các câu dễ mà mọi model đều trả sản phẩm quen thuộc. Dùng để xem chiều hướng, không dùng để kết luận.

## 4. Kết quả

### 4.1 Cùng một dữ liệu, ba cách chấm

n = 128 câu trong catalog (3 câu ngoài catalog không có sản phẩm liên quan nên Recall/nDCG/MRR không xác định, bị loại khỏi trung bình — giống bench).

**Full (cách chấm cũ, unjudged = 0):**

| Model / dim | Recall@10 | nDCG@10 | MRR@10 | Judged@10 |
|---|---:|---:|---:|---:|
| e5-small / 384 | 0,317468 | 0,634556 | 0,727883 | 0,788550 |
| e5-base / 768 | 0,347525 | 0,696969 | 0,756830 | 1,000000 |
| GTE / 768 | 0,282691 | 0,582810 | 0,686620 | 0,722901 |
| BGE-M3 / 1024 | 0,322666 | 0,636094 | 0,738046 | 0,802290 |
| e5-large-instruct / 1024 | 0,304645 | 0,610243 | 0,695799 | 0,793130 |

Các số full này trùng với report Day 4–5 §5, xác nhận script tính đúng như bench.

**Condensed-deep (cùng thang — số chính của report này):**

| Model / dim | Recall@10 | nDCG@10 | MRR@10 | Judged@10 |
|---|---:|---:|---:|---:|
| e5-small / 384 | 0,362913 | **0,712434** | 0,747197 | 1,000000 |
| e5-base / 768 | 0,347525 | 0,696969 | 0,756830 | 1,000000 |
| GTE / 768 | 0,353105 | 0,688177 | 0,728078 | 1,000000 |
| BGE-M3 / 1024 | **0,364296** | 0,709959 | **0,765861** | 1,000000 |
| e5-large-instruct / 1024 | 0,346749 | 0,677728 | 0,717063 | 1,000000 |

**Tập con 18 câu đủ nhãn ở cả 5 model (full):**

| Model | Recall@10 | nDCG@10 | MRR@10 |
|---|---:|---:|---:|
| e5-small | 0,4123 | 0,7881 | 0,8449 |
| e5-base | 0,4194 | 0,7741 | 0,8333 |
| GTE | 0,4087 | 0,7837 | 0,8704 |
| BGE-M3 | 0,4184 | 0,7484 | 0,8472 |
| e5-large-instruct | 0,3938 | 0,7336 | 0,7593 |

Trên tập con này e5-small vẫn ngang e5-base và e5-large vẫn đứng cuối, cùng chiều với condensed-deep.

### 4.2 So sánh từng cặp — paired bootstrap trên condensed-deep

Cách tính giữ nguyên bench (`metrics.paired_bootstrap`, `metrics.win_verdict`):

- **Paired bootstrap:** với mỗi câu hỏi lấy cặp điểm (A, B) của cùng câu; lấy mẫu lại có hoàn lại 128 câu, **1.000 lần, seed 42**; mỗi lần tính trung bình Δ = (B − A) × 100 (đơn vị: điểm). CI95 = percentile 2,5 và 97,5 của 1.000 giá trị trung bình đó.
- **p** (một phía, mid-p) = tỷ lệ lần bootstrap có Δ < 0, cộng nửa tỷ lệ Δ = 0. **p nhỏ → B tốt hơn A; p gần 1 → B kém hơn A.**
- **Đọc CI:** CI nằm hoàn toàn trên 0 thì B tốt hơn; nằm hoàn toàn dưới 0 thì B kém hơn; chứa 0 thì *chưa phân biệt được* (không chứng minh hai model bằng nhau).
- **Verdict theo `win_rule` của `config/sbench.yaml`** (min_delta_recall = 2,0; p_max = 0,05; max_slice_loss = 3,0; tie_delta_ndcg = 2,0):
  - **WIN:** ΔRecall ≥ +2 điểm, p < 0,05, và không slice nào giảm nDCG quá 3 điểm.
  - **TIE:** không WIN và |ΔnDCG| < 2 điểm.
  - **LOSE:** còn lại. LOSE nghĩa là *B không đủ điều kiện thay A*, **không nhất thiết B kém hơn**. Ví dụ GTE → BGE bị LOSE dù BGE cao hơn 2,18 điểm, vì ΔRecall chưa tới 2 điểm.

| A → B | ΔRecall [CI95] p | ΔnDCG [CI95] p | ΔMRR [CI95] | Verdict | Slice giảm nDCG nhiều nhất |
|---|---|---|---|---|---|
| e5-small → e5-base | −1,54 [−3,12; −0,01] 0,975 | −1,55 [−4,89; +1,92] 0,813 | +0,96 [−5,04; +6,96] | TIE | no_diacritics −14,86 |
| e5-small → GTE | −0,98 [−3,44; +1,12] 0,794 | −2,43 [−5,72; +0,71] 0,942 | −1,91 [−8,62; +4,38] | LOSE | amenity_multi −17,43 |
| e5-small → BGE-M3 | +0,14 [−1,08; +1,35] 0,421 | −0,25 [−2,99; +2,62] 0,584 | +1,87 [−3,46; +6,70] | TIE | multi_constraint −10,15 |
| e5-small → e5-large | −1,62 [−3,27; +0,07] 0,971 | **−3,47 [−6,35; −0,44] 0,987** | −3,01 [−8,55; +2,66] | LOSE | no_diacritics −15,15 |
| e5-base → GTE | +0,56 [−2,33; +2,99] 0,337 | −0,88 [−4,47; +2,66] 0,704 | −2,88 [−8,95; +3,25] | TIE | amenity_multi −13,85 |
| e5-base → BGE-M3 | +1,68 [−0,03; +3,31] 0,028 | +1,30 [−2,02; +4,59] 0,216 | +0,90 [−3,95; +5,88] | TIE | cross_vertical −8,41 |
| e5-base → e5-large | −0,08 [−1,85; +1,73] 0,553 | −1,92 [−5,27; +1,32] 0,887 | −3,98 [−9,81; +1,31] | TIE | audience_style −11,73 |
| GTE → BGE-M3 | +1,12 [−1,39; +3,91] 0,178 | +2,18 [−1,46; +6,00] 0,113 | +3,78 [−3,04; +10,14] | LOSE | multi_constraint −10,90 |
| GTE → e5-large | −0,64 [−2,78; +1,68] 0,718 | −1,04 [−4,04; +1,98] 0,769 | −1,10 [−7,38; +4,54] | TIE | multi_constraint −12,68 |
| BGE-M3 → e5-large | −1,75 [−3,49; +0,15] 0,966 | **−3,22 [−5,83; −0,66] 0,994** | **−4,88 [−9,37; −0,49]** | LOSE | no_diacritics −9,25 |

Đọc bảng:

- **Không cặp nào WIN.** Không model nào chứng minh được là tốt hơn model khác theo luật chọn của bench.
- **Hai kết quả có ý nghĩa thống kê về nDCG** đều là e5-large thua (trước e5-small và BGE-M3).
- **Giữa e5-small, e5-base, BGE-M3, GTE, mọi CI nDCG đều chứa 0.** Recall của e5-base thấp hơn e5-small sát ngưỡng (CI [−3,12; −0,01]), nhưng mức này nằm trong vùng thiên lệch của phương pháp (§5), nên không coi là bằng chứng e5-small tốt hơn.
- Cột "slice giảm nhiều nhất" luôn từ −8 đến −17 điểm, kể cả ở cặp TIE: mỗi slice chỉ có 5–18 câu, nên Δ theo slice dao động mạnh. Đây là lý do luật `max_slice_loss = 3` khó đạt với bộ câu nhỏ.

### 4.3 nDCG@10 theo slice (condensed-deep)

| Slice | n | e5-small | e5-base | GTE | BGE-M3 | e5-large |
|---|---:|---:|---:|---:|---:|---:|
| abbrev_typo | 12 | 0,431 | 0,415 | **0,480** | 0,450 | 0,361 |
| amenity_multi | 10 | 0,851 | 0,815 | 0,677 | **0,914** | 0,829 |
| amenity_negation | 5 | 0,445 | 0,429 | 0,535 | 0,543 | **0,594** |
| amenity_offtaxonomy | 5 | 0,632 | 0,557 | **0,672** | 0,606 | 0,619 |
| amenity_single | 13 | 0,830 | **0,923** | 0,874 | 0,903 | 0,894 |
| audience_style | 11 | 0,777 | **0,828** | 0,742 | 0,756 | 0,711 |
| cross_vertical | 10 | 0,796 | **0,932** | 0,809 | 0,848 | 0,819 |
| dest_type | 12 | **0,832** | 0,786 | 0,783 | 0,771 | 0,827 |
| multi_constraint | 9 | 0,856 | 0,835 | **0,864** | 0,755 | 0,737 |
| named_entity | 18 | **0,839** | 0,789 | 0,823 | 0,814 | 0,774 |
| no_diacritics | 12 | **0,366** | 0,217 | 0,301 | 0,307 | 0,214 |
| parent_child | 11 | 0,694 | 0,632 | 0,572 | **0,698** | 0,670 |

Không model nào thắng mọi slice. Hai điểm đáng chú ý:

- **Không dấu (`no_diacritics`) và viết tắt/lỗi gõ (`abbrev_typo`) là điểm yếu chung** của mọi model (0,21–0,48). Đây là vấn đề cần giải ở tầng normalize/hybrid, không giải được bằng đổi model. e5-small tốt nhất ở `no_diacritics` (0,366 so với 0,217 của e5-base).
- e5-base mạnh ở `cross_vertical`, `amenity_single` và `audience_style`. Nếu sau này các nhóm câu này quan trọng hơn trong sản phẩm, đó là lý do giữ e5-base làm dự phòng.

Mỗi slice chỉ có 5–18 câu, nên chênh lệch dưới khoảng 10 điểm ở cấp slice không đủ tin cậy.

## 5. Giới hạn và thiên lệch của condensed-deep

1. **Thiên lệch có lợi cho model ngoài pool.** Khi bỏ sản phẩm chưa nhãn, model "mượn" các sản phẩm đã nhãn mà model khác đã tìm ra, và các sản phẩm đó có xác suất liên quan cao hơn ngẫu nhiên (vì chúng được tìm thấy bởi một model tốt). e5-base không được hưởng lợi này vì top-10 của nó đã đủ nhãn. Mức thiên lệch chưa đo được, nhưng chênh lệch +1,3 đến +1,6 điểm của e5-small/BGE so với e5-base nằm trong vùng có thể do thiên lệch này. **Vì vậy kết luận là "hòa", không phải "e5-small/BGE thắng".**
2. **Không đo khả năng tìm sản phẩm mới.** Condensed-deep chỉ đo thứ tự trên tập đã có nhãn. Nếu một model tìm ra sản phẩm đúng mà chưa ai gán nhãn, nó không được cộng điểm.
3. **Tập ứng viên do pool quyết định.** Tập sản phẩm có nhãn được dựng chủ yếu từ Cohere v3 và e5-base (D4a không giới hạn) cùng một phần từ các model khác (D5a cap 700). Đây là cùng một tập cho mọi model — điều kiện bằng nhau — nhưng không phải mẫu đại diện của toàn catalog.
4. **Cỡ mẫu.** 128 câu cho tổng; 5–18 câu cho từng slice; 18 câu cho tập con kiểm chứng.
5. **Không thay thế gate độ phủ.** Condensed-deep không được dùng để tuyên bố một model PASS gate Judged; gate đó vẫn tính trên top-10 gốc.
6. **Chưa đo pipeline thật.** Như report Day 4–5: dense-only, không filter/cutoff/normalize, Weaviate `flat` 3.183 vector; chưa có HTTP end-to-end, HNSW, concurrency.

## 6. Chi phí vận hành (trích report Day 4–5, không đo lại)

| Model / dim | p95 tạo vector câu hỏi | Re-index 3.183 document | Vector float32 (3.183) | Cache model |
|---|---:|---:|---:|---:|
| e5-small / 384 | **11,4 ms** | **4m47s** | ~4,9 MB | ~471 MB |
| e5-base / 768 | 65,0 ms | 11m57s | ~9,8 MB | ~1,1 GB |
| GTE / 768 | 78,0 ms | 18m05s | ~9,8 MB | ~599 MB |
| BGE-M3 / 1024 | 245,8 ms | 34m17s | ~13 MB | ~4,3 GB |
| e5-large-instruct / 1024 | 284,2 ms | 34m33s | ~13 MB | RSS re-index ~4,16 GB |

Điều kiện đo: Intel Core i5-1145G7, CPU, 20 warm-up + 131 câu tuần tự, cache tắt. Đây là thời gian tạo vector câu hỏi, chưa phải latency API.

## 7. Xếp hạng khuyến nghị

Quy tắc: **chất lượng trước, nhưng chỉ khi chênh lệch có ý nghĩa thống kê; nếu hòa thì chọn theo chi phí.**

| Hạng | Model / dim | Chất lượng (condensed-deep) | Chi phí | Lý do |
|---:|---|---|---|---|
| **1** | **e5-small / 384** | nhóm đầu (hòa) | thấp nhất | Hòa với e5-base/BGE/GTE; nhanh nhất, nhẹ nhất; tốt nhất ở câu không dấu |
| **2** | **e5-base / 768** | nhóm đầu (hòa) | trung bình | Hòa; dự phòng nếu pipeline thật cho thấy thiếu chất lượng; mạnh ở cross_vertical/amenity_single |
| 3 | GTE / 768 | nhóm đầu (hòa) | trung bình | Hòa nhưng nDCG thấp nhất nhóm đầu và kém e5-small 2,43 điểm (CI chứa 0); không có lợi thế gì |
| 4 | BGE-M3 / 1024 | nhóm đầu (hòa) | cao | Hòa e5-small về chất lượng nhưng chậm hơn khoảng 22 lần, model 4,3 GB |
| 5 | e5-large-instruct / 1024 | **kém hơn có ý nghĩa** | cao nhất | Thua e5-small và BGE-M3; p95 tạo vector đã vượt 250 ms; loại |

**Về số chiều:** trên dữ liệu này, model 384 chiều không kém các model 768/1024 chiều. Ở 3.183 vector, khác biệt dung lượng không đáng kể (5 MB so với 10 MB); ở 1 triệu vector, 384 chiều chiếm ~1,5 GB so với ~3 GB của 768 chiều (float32, chưa gồm index).

## 8. Việc tiếp theo

1. Chạy **e5-small** (và e5-base để đối chứng) qua pipeline APP (hybrid + normalize, filter, cutoff) và HTTP end-to-end; đo p95 cache-miss trên máy gần production để đối chiếu NFR-PERF-01.
2. Xử lý câu không dấu và viết tắt ở tầng normalize/hybrid — điểm yếu chung của mọi model.
3. Nếu sau này cần chốt chênh lệch nhỏ giữa e5-small và e5-base bằng full thay vì condensed-deep: bù nhãn 277 hole của e5-small (`sb gold holes --arms E2.e5s`). Không bắt buộc cho quyết định hiện tại.
4. Muốn đổi model vận hành khỏi Cohere v3: viết đề xuất trong `docs/prd/update/` cho FR-SRC-02 và chờ chốt.

## 9. Cách tái sinh số

Từ thư mục `src/`, môi trường conda `vsf2`. Script chỉ đọc: `bench_out/search/data/vec_T3+R_<model>.npy` (vector document), `bench_out/search/cache/embeddings.sqlite` (vector câu hỏi, khoá `sha1(<hf_model>|query|<text>)`), `bench_out/search/runs/20261002-day5-local-ranking/<arm>/per_query.parquet` (đối chiếu top-10) và `gold/gold.jsonl`. Không gọi Weaviate, không gọi Cohere, không tải model.

```bash
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 python fair_eval.py
```

(`fair_eval.py` = nội dung Phụ lục A, lưu ở bất kỳ đâu ngoài repo.) Các artifact đầu vào nằm local, không commit; muốn tái tạo từ đầu thì chạy lại lệnh `embed` và `run` của report Day 4–5 §10 trước.

Kiểm tra tính đúng: dòng đầu output phải ghi `khop run goc 131/131` cho cả 5 model, và bảng FULL phải trùng report Day 4–5 §5.

## Phụ lục A — script tính lại

```python
import json, sqlite3, itertools, numpy as np, pandas as pd
from evaluation.search_bench import paths, metrics as M
from evaluation.search_bench.config import load_config
from evaluation.search_bench.gold_schema import read_gold_jsonl
from evaluation.search_bench.embed.cache import cache_key

cfg = load_config(); rule = cfg.metrics.win_rule
MODELS = {"E2.e5s": ("e5-small", "intfloat/multilingual-e5-small"),
          "E2.e5": ("e5-base", "intfloat/multilingual-e5-base"),
          "E2.gte": ("gte-mb", "Alibaba-NLP/gte-multilingual-base"),
          "E2.bge": ("bge-m3", "BAAI/bge-m3"),
          "E2.e5L": ("e5-large-instruct", "intfloat/multilingual-e5-large-instruct")}
RUN = "20261002-day5-local-ranking"; root = paths.repo_root(); data = root / "bench_out/search/data"
gold = [g for g in read_gold_jsonl(paths.GOLD_JSONL) if g.status == "active"]
db = sqlite3.connect(str(root / "bench_out/search/cache/embeddings.sqlite"))
def qv(name): return np.vstack([np.frombuffer(db.execute("SELECT vec FROM embeddings WHERE key=?", (cache_key(name, "query", g.text),)).fetchone()[0], dtype=np.float32) for g in gold])
nz = lambda x: x / np.linalg.norm(x, axis=1, keepdims=True)
J = {g.qid: {p: int(l) for p, l in g.judgments.items()} for g in gold}
print("so nhan active", sum(len(v) for v in J.values()), "| nhan/cau median", int(np.median([len(v) for v in J.values()])), "min", min(len(v) for v in J.values()))
full, fair, fulltop = {}, {}, {}
for arm, (mk, name) in MODELS.items():
    ids = json.loads((data / f"vec_T3+R_{mk}.ids.json").read_text())
    S = nz(qv(name)) @ nz(np.load(data / f"vec_T3+R_{mk}.npy")).T
    order = np.argsort(-S, axis=1)
    ref = pd.read_parquet(root / f"bench_out/search/runs/{RUN}/{arm}/per_query.parquet").set_index("qid")
    ok = 0; rf, rc = [], []; depth = []; short = 0; skipped = 0
    for i, g in enumerate(gold):
        ranked = [ids[j] for j in order[i]]; j = J[g.qid]
        ok += ranked[:10] == list(ref.loc[g.qid, "top_ids"])
        top10 = ranked[:10]; fulltop[(arm, g.qid)] = top10
        cond = []; d = 0
        for r, p in enumerate(ranked, 1):
            if p in j:
                cond.append(p)
                if len(cond) == 10: d = r; break
        if len(cond) < 10: short += 1
        else: depth.append(d)
        skipped += sum(p not in j for p in top10)
        for lst, out in ((top10, rf), (cond, rc)):
            out.append(dict(qid=g.qid, slice=g.slice, recall=M.recall_at_k(lst, j, 10, 1), ndcg=M.ndcg_at_k(lst, j, 10),
                            mrr=M.mrr_at_k(lst, j, 10, 2), judged=M.judged_at_k(lst, j, 10)))
    full[arm] = pd.DataFrame(rf); fair[arm] = pd.DataFrame(rc)
    print(f"{arm}: khop run goc {ok}/131 | ID chua nhan bi bo trong top-10: {skipped}/1310 | sau 10 ID co nhan o hang: median {np.median(depth):.0f}, p90 {np.percentile(depth,90):.0f}, max {max(depth)} | cau co <10 ID co nhan: {short}")
def table(dd, title):
    print(f"\n## {title}\n| Model | Recall@10 | nDCG@10 | MRR@10 | Judged@10 |")
    for a, df in dd.items():
        print(f"| {MODELS[a][0]} | {df.recall.mean():.6f} | {df.ndcg.mean():.6f} | {df.mrr.mean():.6f} | {df.judged.mean():.6f} |")
table(full, "FULL (unjudged=0)"); table(fair, "CONDENSED-DEEP")
def cmp(dd, a, b):
    da, db_ = dd[a].set_index("qid"), dd[b].set_index("qid")
    res = {m: M.paired_bootstrap(da[m].to_dict(), db_[m].to_dict(), n_boot=1000, seed=42) for m in ("recall", "ndcg", "mrr")}
    sl = M.slice_deltas(dd[a].to_dict("records"), dd[b].to_dict("records"), "ndcg")
    v, why = M.win_verdict(res["recall"], res["ndcg"], sl, rule)
    return res, v, min(sl.items(), key=lambda kv: kv[1])
print("\n## PAIRWISE condensed-deep (B-A)\n| A -> B | dR CI p | dnDCG CI p | dMRR CI | verdict | worst slice |")
for a, b in itertools.combinations(MODELS, 2):
    r, v, w = cmp(fair, a, b)
    f = lambda x: f"{x['delta']:+.2f} [{x['ci95'][0]:+.2f}; {x['ci95'][1]:+.2f}] p={x['p_one_sided']:.3f}"
    print(f"| {MODELS[a][0]} -> {MODELS[b][0]} | {f(r['recall'])} | {f(r['ndcg'])} | {f(r['mrr'])} | {v} | {w[0]} {w[1]:+.2f} |")
common = [g.qid for g in gold if all(all(p in J[g.qid] for p in fulltop[(a, g.qid)]) for a in MODELS)]
print(f"\n## Tap con 'ca 5 model deu du nhan top-10 goc': {len(common)} cau")
for a, df in full.items():
    d = df[df.qid.isin(common)]
    print(f"| {MODELS[a][0]} | R {d.recall.mean():.4f} | nDCG {d.ndcg.mean():.4f} | MRR {d.mrr.mean():.4f} | n={d.ndcg.notna().sum()}")
print("\n## slice nDCG condensed-deep")
t = pd.DataFrame({MODELS[a][0]: df.dropna(subset=["ndcg"]).groupby("slice").ndcg.mean() for a, df in fair.items()})
t["n"] = fair["E2.e5"].dropna(subset=["ndcg"]).groupby("slice").size(); print(t.round(3).to_string())
print("\nwin_rule:", rule)
```
