# Search Day 4–5 — giải thích kết quả và xếp hạng model local ưu tiên miễn phí

- Ngày chạy: **01–02/10/2026**. Ngày viết lại và bổ sung local-only: **02/10/2026**.
- Phục vụ: **FR-SRC-01..04, AC-SRC-01, NFR-PERF-01**.
- Nhánh: `bench_search_recomSys`; run ID: `20261001-day4-local`, `20261002-day5-local-only`, `20261002-day5-e5-large`, `20261002-day5-local-ranking`.
- Commit lưu kết quả và tag `gold_v3`: `d1d52571c6ebb88d1a444fa1a1c4d3680fd84389`. Base lúc chạy retrieval: `b692047eb075327d86d95b048a229e2abf43b6d4`.
- Gold SHA-256: `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`.
- Snapshot catalog: `2026-09-23`; records SHA-256: `ad3f3be25647a44c027ab21592f4defc3740f247090a146ea3614eb83adff4ab`.
- Nguồn số: các thư mục run nói trên, mỗi arm dùng artifact có `gold_version=gold_v3`, `per_query*.parquet` và `latency-embed.json`. Artifact chạy nằm local, không commit; gold/config/report có trong Git.

## 1. Kết luận dành cho nhóm

**Trong nhóm model local đã đo, e5-base/768 đứng đầu và là model nên đưa vào bước thử production tiếp theo.** Nó có nDCG@10 cao nhất (**0,697**), Recall@10 cao nhất (**0,348**), đủ nhãn Judged@10 = **1,000**, query embedding p95 **65,0 ms**, và re-index 3.183 document mất **11 phút 57 giây** trên CPU laptop.

Xếp hạng khuyến nghị local-only: **(1) e5-base, (2) e5-small, (3) BGE-M3, (4) GTE multilingual-base, (5) e5-large-instruct**. Bảng và lý do chi tiết ở §8.

Các kết luận chính:

1. **E5-base là lựa chọn cân bằng nhất:** chất lượng local cao nhất; paired bootstrap cho thấy e5-small, BGE, GTE và e5-large đều thấp hơn e5-base trên cùng query/gold_v3. Nó chậm hơn e5-small nhưng vẫn còn ngân sách để toàn API hướng tới p95 ≤ 250 ms.
2. **E5-small là lựa chọn CPU nhẹ:** p95 tạo vector chỉ **11,369 ms**, vector 384 chiều và re-index **4 phút 47 giây**. Chất lượng full thấp hơn e5-base 6,24 điểm nDCG; coverage 0,789 còn thiếu nhãn nên mức chênh có thể thay đổi sau top-up.
3. **E5-large-instruct không thắng trên dữ liệu này:** nDCG full 0,610; query p95 284,2 ms chỉ riêng embedding đã vượt NFR toàn API 250 ms; re-index 34 phút 33 giây và vector 1024 chiều. Tên “large” không đảm bảo tốt hơn cho domain V-OTA.
4. **Chưa model nào được chứng nhận sẵn sàng production:** chưa đo HTTP end-to-end, concurrency, cache, HNSW/hfresh và resource trên máy triển khai. PASS độ phủ nhãn không phải PASS production.

PRD hiện vẫn quy định Cohere v3/1024 tại FR-SRC-02. Report chỉ đưa ra thứ tự đánh giá local; muốn thay model vận hành cần đề xuất thay đổi PRD và người dùng chốt trước khi triển khai.

## 2. Đã đo trên dữ liệu nào?

| Thành phần | Quy mô thực tế | Ý nghĩa |
|---|---:|---|
| Catalog gốc | 11.387 record | Gồm khách sạn, phòng, tuyến/chuyến bay và các loại khác |
| Sản phẩm được tìm kiếm bằng vector | **3.183 search unit / collection** | Chọn hotel_property, flight_route, attraction, combo, golf; không vector hóa riêng từng phòng/chuyến bay trong phép đo này |
| Cấu hình embedding | 10 | v3; e5-small; e5-base; e5-large-instruct; GTE; BGE; v4 ở 4 số chiều |
| Tổng vector document đã tạo | 10 × 3.183 = **31.830** | Tổng của mười bộ; **mỗi truy vấn chỉ tìm trong một bộ 3.183 vector**, không tìm trên 31.830 vector |
| Câu hỏi đánh giá | 131 active, 13 slice | 128 câu trong catalog và 3 câu mong đợi không có kết quả |
| Nhãn gold | 4.991 active; tổng 5.021 | Một nhãn thuộc một cặp câu hỏi–sản phẩm; 30 nhãn của 1 câu retired không tính điểm |
| K | 10 | Chấm tối đa 10 kết quả đầu của mỗi câu hỏi |
| Máy | Intel Core i5-1145G7, 8 logical CPU | Máy local đo ngày 01/10; chưa đại diện cho máy production |
| Vector DB | Weaviate 1.37.3 local | B0/E dùng cấu hình bench `flat`, cosine; đây không phải phép đo ANN production |

`Dimension` / `dim` / số chiều là số phần tử trong **một vector**: e5-small có 384, v4-512 có 512. Nó không phải số sản phẩm, số ảnh hay số kết quả trả về. Benchmark này dùng văn bản, không dùng ảnh sản phẩm.

`Arm` là một cấu hình thử nghiệm. `T3+R` là biến thể text builder dùng chung (`catalog-text-v2`, có thông tin phòng/combo theo builder); đổi arm E chủ yếu là đổi model và input/prefix thích hợp. B0/E đều dense-only, không normalize, không filter và không cutoff. Cùng dữ liệu, K và cách chấm để so model.

`Slice` là nhóm câu hỏi để tránh điểm tổng che lỗi cục bộ: `no_diacritics` = không dấu; `abbrev_typo` = viết tắt/lỗi gõ; `dest_type` = điểm đến + loại sản phẩm; `amenity_negation` = phủ định tiện ích; `cross_vertical` = nhiều loại sản phẩm. Một số nhóm chỉ có 3–5 câu nên độ bất định lớn.

## 3. Giải thích các chỉ số và cách tính

Gold gán độ liên quan `rel` bằng **0 / 1 / 2**: không liên quan / liên quan một phần / phù hợp cao. Runner chấm từng câu hỏi rồi lấy **trung bình theo câu**, không gộp tất cả sản phẩm thành một mẫu lớn.

| Chỉ số trong bảng | Đo điều gì? | Cách tính đúng trong code | Cách đọc |
|---|---|---|---|
| **Recall@10**, `R`, `full R` | Tìm được bao nhiêu trong số sản phẩm liên quan đã biết? | Số ID top-10 có rel ≥ 1 / tổng ID có rel ≥ 1 trong gold của câu đó | Gold có 20 sản phẩm liên quan, lấy được 7 → 0,35. Không có nghĩa 35% kết quả đúng; đó là khái niệm precision |
| **nDCG@10** | Có xếp sản phẩm phù hợp lên đầu không? | DCG = tổng `(2^rel − 1) / log2(rank + 1)`; chia cho DCG của top-10 lý tưởng từ gold | Rel 2 được gain 3, rel 1 được gain 1. Sản phẩm tốt ở hạng 1 có giá trị hơn hạng 10. 0,709 không phải accuracy 70,9% |
| **MRR@10** | Người dùng gặp kết quả phù hợp cao sớm đến đâu? | `1 / rank` của kết quả đầu có **rel ≥ 2** trong top-10; không gặp thì 0 | Hạng 1 → 1; hạng 2 → 0,5; hạng 5 → 0,2. MRR dùng ngưỡng nhãn cao hơn Recall |
| **Judged@10** | Đã chấm nhãn đủ chưa? | Số kết quả top-10 có nhãn / số kết quả thực trả về trong top-10, rồi trung bình theo câu | 0,80 nghĩa khoảng 80% kết quả đã có nhãn, **không phải 80% kết quả đúng**. Nhãn 0 vẫn là đã chấm |
| **Zero in-catalog** | Có bỏ người dùng lại với kết quả rỗng không? | Số câu trong catalog trả 0 kết quả / 128 | Càng thấp càng tốt; không gộp 3 câu cố ý ngoài catalog vào mẫu số |
| **Retained ratio** | Condensed giữ lại bao nhiêu kết quả? | Tổng kết quả có nhãn / tổng kết quả trả về | Đây là tỷ lệ gộp; chỉ bằng Judged trung bình khi mọi câu có cùng số kết quả như B0/E ở lượt này |
| **p50 / p95 latency** | Thời gian điển hình / phần đuôi chậm | Percentile 50/95 của các mẫu thời gian, bằng NumPy | p95 = 11 ms nghĩa khoảng 95% mẫu không vượt 11 ms; không phải thời gian tệ nhất |

Recall, nDCG và MRR ở bảng model có **n = 128 câu xác định**. Ba câu ngoài catalog không có nhãn liên quan nên metric này không xác định và bị loại khỏi trung bình, không ép thành 0. Judged có n = 131 với B0/E. Câu trả rỗng không có Judged xác định; vì vậy Judged cao không bảo đảm ít kết quả rỗng.

Recall dùng các sản phẩm liên quan **đã biết trong pool nhãn**, không biết hết mọi sản phẩm liên quan trong toàn catalog. Khi thêm nhãn gold, mẫu số Recall có thể tăng và Recall giảm dù top-10 không đổi. Chỉ so các arm trên cùng gold version.

### Full và condensed khác nhau thế nào?

- **Full:** giữ nguyên top-10; sản phẩm chưa có nhãn được tính rel = 0. Đây là số chính, nhưng có thể phạt model mới do pool chưa phủ các kết quả nó tìm được.
- **Condensed:** lấy đúng top-10 đã lưu, bỏ sản phẩm chưa nhãn rồi dồn hạng. Không lấy thêm hạng 11 trở đi để lấp chỗ. Giữ nguyên gold và mẫu số Recall/IDCG.
- Ví dụ top-3 là `[chưa nhãn, rel 2, rel 0]`: full tính kết quả rel 2 ở hạng 2; condensed tính nó ở hạng 1. MRR tăng từ 0,5 lên 1 trong ví dụ này mà hệ thống không thay đổi.
- Trong cách cài đặt này, **Recall@10 full = Recall@10 condensed** vì chỉ bỏ ID chưa nhãn, không bỏ ID đã biết liên quan và không bổ sung kết quả. nDCG/MRR có thể tăng nhờ dồn hạng.
- Condensed dùng để kiểm độ nhạy với thiếu nhãn; không được dùng nó để tự công bố model vượt gate độ phủ. Với BGE có 1 câu, GTE có 3 câu không còn kết quả sau khi bỏ chưa nhãn.

## 4. PASS / NEEDS_LABELS / WIN / LOSE dựa trên gì?

### 4.1 Gate độ phủ nhãn — áp dụng cho bảng model bên dưới

Nguồn: `config/sbench.yaml: gold`, hàm `runner.judged_gate`.

- **PASS độ phủ:** Judged@10 tổng ≥ **0,80**, và ở **từng slice có metric xác định** ≥ **0,70**.
- **NEEDS_LABELS:** ít nhất một điều kiện trên chưa đạt. Report cũ gọi đây là FAIL; cách ghi đó dễ nhầm với chất lượng kém nên bản này ghi đúng tên trạng thái.
- Giá trị bằng ngưỡng được chấp nhận; code dùng tolerance tuyệt đối `1e-12` để tránh sai số float. V4-1024 có slice không dấu 84/120 = 0,700, nên PASS.
- Gate này không đo độ chính xác. Model đạt 100% Judged vẫn có thể trả nhiều kết quả nhãn 0.

### 4.2 WIN / TIE / LOSE — so hai arm, không phải gate độ phủ

Nguồn: `metrics.win_rule`, `metrics.win_verdict`.

1. **WIN:** ΔRecall@10 ≥ **+2 điểm phần trăm**, bootstrap p một phía < **0,05**, và không slice nào giảm nDCG quá **3 điểm**.
2. Nếu chưa WIN, **TIE** khi `|ΔnDCG@10| < 2 điểm`.
3. Còn lại là **LOSE** theo quy tắc chọn. LOSE có thể xảy ra dù điểm tổng tăng, vì một slice giảm mạnh; không đồng nghĩa mọi chỉ số đều kém hơn.

Δ luôn là `(B − A) × 100`. Ví dụ 0,65 − 0,62 = +3 điểm, không phải tăng tương đối 3%.

Paired bootstrap lấy lại mẫu **các cặp điểm cùng câu hỏi** 1.000 lần, seed 42. CI95 lấy percentile 2,5 và 97,5 của các Δ trung bình. CI chứa 0 nghĩa chưa chứng minh được hướng chênh lệch ở mức này, không chứng minh hai model tương đương. Code tính p một phía bằng tỷ lệ Δ bootstrap < 0 cộng nửa tỷ lệ Δ = 0. Nhãn TIE của CLI dựa trên ngưỡng 2 điểm ở trên, không chỉ dựa vào CI.

### 4.3 Gate vận hành và production — phải kiểm riêng

Theo spec Part 10: constraint precision ≥ 0,95 (tỷ lệ kết quả thỏa filter), trung bình số kết quả dư cùng cha ≤ 1, zero-result trong catalog ≤ 0,02, zero-result ngoài catalog = 1, và p95 cache-miss ≤ 250 ms. Cấu hình còn có hub guard 3,0 cho stage áp dụng: hub score là số lần một item xuất hiện so với kỳ vọng xuất hiện đều, không phải phần trăm.

**NFR-PERF-01 quy định toàn API Search p95 ≤ 250 ms.** Con số 300 ms trong plan cũ không thay thế PRD. Bảng ngày 01/10 chưa có đo HTTP end-to-end đầy đủ để xác nhận gate này. B0/E không filter/cutoff nên không dùng PASS độ phủ của chúng để chứng nhận filter hay hành vi ngoài catalog. Ngưỡng filter smoke 100% trong plan là phép kiểm riêng, không nhầm với guard tổng hợp 95%.

## 5. Kết quả chất lượng — cùng gold_v3

Các số dưới đây giữ 6 chữ số thập phân từ artifact cuối. `Full R` = Recall@10 full; `Full nDCG` = nDCG@10 full; `Full MRR` = MRR@10 full. Các cột điểm càng cao càng tốt, nhưng phải đọc cùng độ phủ nhãn.

| Arm | Chiều | Full R | Full nDCG | Full MRR | Judged@10 | nDCG condensed | Gate độ phủ |
|---|---:|---:|---:|---:|---:|---:|---|
| B0 | 1024 | 0,350257 | 0,685006 | 0,757909 | 1,000000 | 0,685006 | PASS độ phủ |
| E2.e5s | 384 | 0,317468 | 0,634556 | 0,727883 | 0,788550 | 0,647075 | NEEDS_LABELS |
| E2.e5 | 768 | 0,347525 | 0,696969 | 0,756830 | 1,000000 | 0,696969 | PASS độ phủ |
| E2.e5L | 1024 | 0,304645 | 0,610243 | 0,695799 | 0,793130 | 0,618387 | NEEDS_LABELS |
| E2.gte | 768 | 0,282691 | 0,582810 | 0,686620 | 0,722901 | 0,597945 | NEEDS_LABELS |
| E2.bge | 1024 | 0,322666 | 0,636094 | 0,738046 | 0,802290 | 0,648056 | NEEDS_LABELS |
| E2.v4-256 | 256 | 0,321962 | 0,641191 | 0,740256 | 0,812977 | 0,652074 | NEEDS_LABELS |
| E2.v4-512 | 512 | 0,350643 | 0,708921 | 0,791174 | 0,898473 | 0,711304 | PASS độ phủ |
| E2.v4-1024 | 1024 | 0,352025 | 0,715580 | 0,800000 | 0,922901 | 0,718036 | NEEDS_LABELS |
| E2.v4-1536 | 1536 | 0,354631 | 0,718561 | 0,794922 | 0,912977 | 0,720852 | NEEDS_LABELS |

Ví dụ e5-small: full R 0,317468 là trung bình thu hồi khoảng 31,75% sản phẩm liên quan đã biết; nDCG 0,634556 là điểm thứ hạng, không phải 63,46% truy vấn thành công; Judged 0,788550 cho thấy còn thiếu nhãn. So với B0, nDCG full thấp hơn khoảng 5,05 điểm; chưa thể quy toàn bộ mức giảm đó cho model.

Lý do thiếu nhãn cụ thể từ `needs_labels`:

- **E2.e5s:** judged@10 0.789 < 0.8; slice abbrev_typo: judged@10 0.692 < 0.7; slice no_diacritics: judged@10 0.367 < 0.7.
- **E2.e5:** PASS tổng và tất cả slice; 1.310/1.310 kết quả top-10 đã có nhãn.
- **E2.e5L:** judged@10 0.793 < 0.8; slice no_diacritics: judged@10 0.417 < 0.7.
- **E2.gte:** judged@10 0.723 < 0.8; slice abbrev_typo: judged@10 0.633 < 0.7; slice amenity_offtaxonomy: judged@10 0.680 < 0.7; slice no_diacritics: judged@10 0.208 < 0.7.
- **E2.bge:** slice no_diacritics: judged@10 0.358 < 0.7.
- **E2.v4-256:** slice no_diacritics: judged@10 0.600 < 0.7.
- **E2.v4-1024:** slice no_diacritics: judged@10 0.700 < 0.7.
- **E2.v4-1536:** slice no_diacritics: judged@10 0.658 < 0.7.

### So sánh các số chiều v4

| A → B | Δ Recall condensed | CI95 | Δ nDCG condensed | CI95 | p nDCG | Verdict |
|---|---:|---|---:|---|---:|---|
| v4-512 → v4-1024 | +0,14 điểm | [−0,62; +0,89] | +0,67 điểm | [−0,83; +2,05] | 0,184 | TIE |
| v4-512 → v4-1536 | +0,40 điểm | [−0,40; +1,22] | +0,95 điểm | [−0,66; +2,58] | 0,131 | TIE |

Điểm tăng nhẹ theo chiều nhưng CI đều chứa 0. V4-1536 còn thiếu nhãn ở slice không dấu. So với B0, v4-512 có ΔnDCG condensed +2,63 điểm, CI [−1,46; +6,58], nên chưa chứng minh thắng. Các số này không phải lý do bắt buộc nhóm chuyển sang API trả phí.

## 6. Latency: đo bước nào, trên bao nhiêu vector?

Một lượt search thường gồm: **câu hỏi → chuẩn hóa → tạo vector câu hỏi → truy xuất vector/từ khóa → lọc, xếp hạng, lấy thông tin sản phẩm → trả API**. Các phép đo dưới chỉ bao phủ những đoạn khác nhau trong chuỗi đó.

### 6.1 Tạo vector câu hỏi — chưa tìm kiếm trong catalog

Nguồn: `latency-embed.json`, hàm `latency.measure_embed_queries`. Mỗi model chạy 20 lượt warm-up trước, rồi đo **toàn bộ 131 câu**, mỗi lần một câu, tuần tự, cache tắt. 20 lượt warm-up không tính vào 131 mẫu. Đồng hồ wall-clock bọc lệnh `embed([text], "query")`, không gồm thời gian tải model ban đầu. Cohere có mạng/API trong phép đo; model local chạy CPU.

Artifact Day 4 ghi gold_v2 vì được đo trước top-up; gold_v3 chỉ bổ sung nhãn và giữ nguyên các câu hỏi. Hai lượt e5-base/e5-large ngày 02/10 ghi trực tiếp gold_v3. Rescore chất lượng không tự chạy lại latency.

| Model | p50 tạo vector (ms) | p95 tạo vector (ms) | Số mẫu | Điều kiện |
|---|---:|---:|---:|---|
| e5-small / 384 | 9,192 | 11,369 | 131 | Local CPU |
| e5-base / 768 | 39,835 | 64,990 | 131 | Local CPU |
| GTE multilingual-base / 768 | 66,487 | 78,001 | 131 | Local CPU |
| BGE-M3 / 1024 | 148,779 | 245,814 | 131 | Local CPU, fp32/safetensors; không gọi là kết quả int8 |
| e5-large-instruct / 1024 | 257,675 | 284,236 | 131 | Local CPU; query dùng instruction chính thức của model |
| Cohere v3 / 1024 | 459,105 | 734,967 | 131 | API; nghỉ 1.000 ms giữa request, khoảng nghỉ nằm ngoài đồng hồ |
| Cohere v4 | — | — | Không có lượt hợp lệ hoàn chỉnh | Gặp 429 (rate limit); không công bố percentile từ lượt lỗi |

**Phép đo này không truy xuất trên bất kỳ vector catalog nào.** Nó chỉ biến một câu hỏi thành một vector. Số 3.183 không phải mẫu số của bảng này. Chưa đo batch throughput, tải nhiều người dùng hoặc thời gian khởi động lạnh. Không tự coi model local đã đo là bản lượng tử hóa nếu metadata không chứng minh điều đó.

### 6.2 Truy xuất vector — mỗi collection chứa đúng 3.183 vector

Nguồn: `results@gold_v3.json: latency_ms`; hàm `runner.retrieve`. Runner tạo/lấy cache vector của 131 câu **trước** khi bắt đầu đồng hồ truy xuất. Mỗi câu gọi `store.dense` top-10 một lần; đo wall-clock phía runner gồm gọi local Weaviate và chuyển kết quả sang ID/score. Không gồm tạo embedding, không qua HTTP `/search`. Không có bước loại 20 warm-up được cài cho phép đo retrieval này.

B0/E dùng cấu hình bench `flat` cosine (tìm chính xác) ở quy mô nhỏ. Production theo NFR-PERF-03 dùng ANN HNSW/hfresh; không ngoại suy những con số này sang production hoặc một triệu vector.

| Arm | Vector trong collection | Số query đo | p50 truy xuất (ms) | p95 truy xuất (ms) |
|---|---:|---:|---:|---:|
| B0 | 3,183 | 131 | 8.098 | 12.191 |
| E2.e5s | 3,183 | 131 | 3.582 | 6.270 |
| E2.e5 | 3,183 | 131 | 6.828 | 8.247 |
| E2.e5L | 3,183 | 131 | 5.172 | 8.593 |
| E2.gte | 3,183 | 131 | 6.339 | 8.933 |
| E2.bge | 3,183 | 131 | 6.305 | 9.577 |
| E2.v4-256 | 3,183 | 131 | 6.863 | 11.613 |
| E2.v4-512 | 3,183 | 131 | 6.832 | 8.111 |
| E2.v4-1024 | 3,183 | 131 | 8.200 | 9.985 |
| E2.v4-1536 | 3,183 | 131 | 9.837 | 11.574 |

Ví dụ **e5-small p95 tạo vector 11,369 ms** và **p95 truy xuất 7,233 ms** là hai phép đo tách biệt. Không cộng hai p95 để khẳng định p95 API = 18,602 ms: percentile của tổng cần đo trên cùng request, còn các bước khác chưa được tính. Tương tự, 8,11 ms của v4-512 là retrieval, không phải tốc độ gọi Cohere v4.

### 6.3 Ba arm chạy logic SearchProducts — không phải HTTP production

APP.dense/hybrid/hybrid_norm chạy use case thật qua adapter local, có BenchQueryEmbedder/cache, candidate và cutoff. Đồng hồ trong `app_adapter.retrieve_app` bọc lời gọi use case; trường artifact vẫn mang tên `weaviate_p50/p95` nhưng phạm vi thực tế rộng hơn truy xuất thuần ở §6.2. Không dùng tên trường đó để gọi đây là thời gian riêng Weaviate hoặc toàn API.

| Arm | p50 use case local (ms) | p95 use case local (ms) |
|---|---:|---:|
| APP.dense | 75,180 | 99,976 |
| APP.hybrid | 163,421 | 195,559 |
| APP.hybrid_norm | 171,994 | 694,708 |

Các số này chưa tách hit/miss theo HTTP và chưa có load test. Cần đo lại trên máy triển khai với cache hit/miss, QPS và concurrency cụ thể trước khi đánh giá NFR-PERF-01.

## 7. Dense, hybrid và normalize thay đổi chất lượng ra sao?

- **Dense:** tìm theo vector ngữ nghĩa.
- **Hybrid:** kết hợp dense với tìm từ khóa BM25.
- **Normalize:** chuẩn hóa câu hỏi trước tìm kiếm, ví dụ xử lý các dạng viết khác nhau theo normalizer hiện có.

Bảng APP chạy cùng Cohere v3, collection `ProductBench` 3.183 object. APP.dense lấy candidate top-200 và cutoff cosine 0,62; B0 lấy top-10 trực tiếp không cutoff. Vì vậy **B0 và APP.dense không phải cùng cấu hình**, dù cùng model: không đối chiếu hai điểm như thể chỉ khác do nhiễu đo.

| Arm | Recall@10 full | nDCG@10 full | MRR@10 full | Judged@10 | Zero in-catalog |
|---|---:|---:|---:|---:|---:|
| APP.dense | 0,305920 | 0,619530 | 0,693304 | 1,000000 | 0,164062 |
| APP.hybrid | 0,306081 | 0,596552 | 0,643083 | 1,000000 | 0,156250 |
| APP.hybrid_norm | 0,339702 | 0,647718 | 0,704021 | 1,000000 | 0,070312 |

Hybrid+normalize so với dense: Recall +3,38 điểm, CI95 [+1,33; +5,67]; nDCG +2,82 điểm, CI95 [−1,21; +7,00]. Tuy nhiên slice `dest_type` giảm nDCG **13,19 điểm**, vượt guard 3 điểm, nên verdict **LOSE**. Zero-result giảm từ 21/128 xuống 9/128, nhưng 7,03% vẫn trên guard 2%.

Ở slice không dấu, dense/hybrid rỗng 12/12 câu; hybrid+normalize còn rỗng 8/12. Đây là vấn đề hành vi cần xử lý dù Judged của các kết quả đã trả là 1,0. Chi tiết CI nằm ở [report ba arm](eval-2026-10-01-search-v1-3arm.md).

## 8. Xếp hạng local-only, ưu tiên miễn phí

Trong phần này, **miễn phí = tự chạy model, không trả tiền embedding API theo request/token**. Máy chủ, RAM, điện, vector DB và công vận hành vẫn là chi phí. Cohere bị loại khỏi bảng xếp hạng; các dòng Cohere ở §5–7 chỉ giữ lại để giải thích lịch sử Day 4 và không ảnh hưởng quyết định local.

### 8.1 Điều kiện so sánh đã khóa

Năm model local đều dùng cùng một phép thử:

| Điều kiện | Giá trị dùng chung |
|---|---|
| Gold | `gold_v3`, SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784` |
| Query | 131 active; metric chất lượng xác định trên 128 query in-catalog |
| Catalog | Cùng snapshot; 3.183 search unit trong mỗi collection |
| Text | `T3+R`, builder `catalog-text-v2` |
| Retrieval | Dense-only, cosine, top-10, Weaviate local `flat`; không filter, cutoff hay normalize |
| Latency query | Cùng máy CPU; 20 warm-up + 131 query tuần tự, từng query một, cache tắt |
| Chi phí API | 0 USD cho cả năm model local |

Prefix/instruction là phần bắt buộc của từng model, nên được áp dụng đúng model thay vì ép chuỗi đầu vào giống từng ký tự. E5-small/e5-base dùng prefix `query:` và `passage:`; e5-large-instruct dùng `Instruct: ...\nQuery:` cho query và không thêm instruction cho document theo model card. Các yếu tố còn lại được giữ nguyên.

### 8.2 Bảng xếp hạng khuyến nghị

| Hạng | Model | Full R | Full nDCG | Judged@10 | p95 embed query | p95 retrieval / 3.183 vector | Re-index document | Tài nguyên chính |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| **1** | **e5-base / 768** | **0,3475** | **0,6970** | **1,000** | **65,0 ms** | 8,2 ms | 11m57s | vector ~9,4 MB; cache model ~1,1 GB |
| **2** | **e5-small / 384** | 0,3175 | 0,6346 | 0,789 | **11,4 ms** | **6,3 ms** | **4m47s** | vector ~4,7 MB; cache model ~471 MB |
| **3** | **BGE-M3 / 1024** | 0,3227 | 0,6361 | 0,802 | 245,8 ms | 9,6 ms | 34m17s | vector ~13 MB; cache model ~4,3 GB |
| **4** | **GTE multilingual-base / 768** | 0,2827 | 0,5828 | 0,723 | 78,0 ms | 8,9 ms | 18m05s | vector ~9,4 MB; cache model ~599 MB |
| **5** | **e5-large-instruct / 1024** | 0,3046 | 0,6102 | 0,793 | 284,2 ms | 8,6 ms | 34m33s | vector ~13 MB; peak re-index RSS ~4,16 GB |

Re-index là wall-clock cho 3.183 document trên máy local. Lượt BGE có 2.991 vector mới và 192 cache hit, nên con số của nó có lợi nhẹ so với một lượt hoàn toàn không cache. Dung lượng vector là file float32 xấp xỉ; cache model không phải RAM phục vụ thực tế.

**1 — e5-base:** đứng đầu vì có Recall và nDCG local cao nhất, đồng thời 1.310/1.310 kết quả top-10 đã được chấm. So với từng model còn lại, paired bootstrap đều cho khoảng tin cậy của ΔnDCG `(model kia − e5-base)` nằm hoàn toàn dưới 0. p95 embedding 65 ms vẫn để lại ngân sách cho retrieval, business logic và HTTP, dù cần đo end-to-end mới biết có đạt NFR hay không.

**2 — e5-small:** là phương án tiết kiệm CPU/RAM tốt nhất. Nó nhanh hơn e5-base khoảng 5,7 lần ở p95 query, vector nhỏ bằng một nửa và re-index nhanh hơn khoảng 2,5 lần. Full nDCG thấp hơn e5-base 6,24 điểm. Hạng 2 là khuyến nghị vận hành: coverage chưa đạt gate, nên cần top-up nhãn nếu muốn chốt chính xác khoảng cách chất lượng.

**3 — BGE-M3:** nDCG chỉ hơn e5-small 0,15 điểm và paired bootstrap kết luận TIE; lợi ích chất lượng chưa bù p95 query 245,8 ms, cache model lớn và re-index lâu. Vì vậy BGE đứng sau e5-small dù điểm full nhỉnh hơn rất ít.

**4 — GTE multilingual-base:** p95 query 78 ms chấp nhận được hơn BGE, nhưng Recall/nDCG thấp rõ rệt và coverage chỉ 0,723. Nó không có bằng chứng chất lượng để ưu tiên trước hai model e5 nhỏ hơn.

**5 — e5-large-instruct:** kích thước lớn không tạo chất lượng tốt hơn trên V-OTA. Full nDCG chỉ 0,610; p95 embedding 284,2 ms đã vượt NFR toàn API 250 ms trước khi cộng retrieval và HTTP; re-index lâu nhất nhóm. Nó cần thêm ít nhất 34 nhãn trong slice `no_diacritics` để gate slice đạt 0,70; việc top-up này không giải quyết điểm latency.

### 8.3 Bằng chứng thống kê

Các dòng dưới dùng paired bootstrap 1.000 lần, seed 42, trên cùng query. Δ là `(model B − model A) × 100`; CI âm hoàn toàn nghĩa model B thấp hơn A ở phép đo này.

| A → B | Δ Recall | CI95 | Δ nDCG | CI95 | Diễn giải |
|---|---:|---|---:|---|---|
| e5-base → e5-small | −3,01 điểm | [−4,50; −1,53] | −6,24 điểm | [−10,13; −2,52] | e5-small thấp hơn |
| e5-base → BGE-M3 | −2,49 điểm | [−4,07; −1,08] | −6,09 điểm | [−9,71; −2,39] | BGE thấp hơn |
| e5-base → GTE | −6,48 điểm | [−8,98; −4,34] | −11,42 điểm | [−15,31; −7,53] | GTE thấp hơn |
| e5-base → e5-large | −4,29 điểm | [−6,26; −2,39] | −8,67 điểm | [−12,50; −5,09] | e5-large thấp hơn |
| e5-small → BGE-M3 | +0,52 điểm | [−0,74; +1,80] | +0,15 điểm | [−2,56; +3,10] | Chưa phân biệt được; TIE |

Nếu chỉ sắp theo **full nDCG thô**, thứ tự là e5-base > BGE-M3 > e5-small > e5-large > GTE. Bảng khuyến nghị đổi e5-small lên trên BGE vì hai model hòa về mặt thống kê, trong khi e5-small nhẹ và nhanh hơn nhiều. Hạng 2–5 vẫn là thứ tự tạm thời do coverage khác nhau; e5-base là model duy nhất trong năm model có Judged@10 = 1,000.

License công bố bởi chủ model: [e5-small — MIT](https://huggingface.co/intfloat/multilingual-e5-small/blob/main/README.md), [e5-base — MIT](https://huggingface.co/intfloat/multilingual-e5-base), [e5-large-instruct — MIT](https://huggingface.co/intfloat/multilingual-e5-large-instruct), [BGE-M3 — MIT](https://huggingface.co/BAAI/bge-m3), [GTE — Apache-2.0](https://huggingface.co/Alibaba-NLP/gte-multilingual-base). Giữ license/notice tương ứng khi phân phối.

### 8.4 Số chiều và dung lượng

Ước tính **vector thô float32** = số vector × số chiều × 4 byte. Bảng này là phép tính dung lượng, không phải RAM thực đo hay benchmark một triệu sản phẩm. Chưa gồm model weights, metadata, index, WAL, replica và backup.

| Số chiều | 3.183 vector, MB thập phân | 1 triệu vector, GB thập phân |
|---:|---:|---:|
| 256 | 3.259 | 1.024 |
| 384 | 4.889 | 1.536 |
| 512 | 6.519 | 2.048 |
| 768 | 9.778 | 3.072 |
| 1024 | 13.038 | 4.096 |
| 1536 | 19.556 | 6.144 |

Với model local, ngoài vector còn phải tính RAM, CPU và thời gian khởi động model. Chưa có dữ liệu tải để quy số ms/query thành số máy production: wall-clock không phải CPU-time, và inference có thể dùng nhiều thread.

## 9. Việc đã xong và bằng chứng còn thiếu

Đã hoàn thành Day 4 và lượt bổ sung Day 5 local-only: e5-base và e5-large-instruct đã qua token gate, embed 3.183 document, load collection, chạy chất lượng, đo latency query và sanity 4/4 trên `gold_v3`. Run `20261002-day5-local-ranking` chạy cả năm model local trong cùng một run; query vector đều cache hit 131/131, không gọi Cohere. Năm phép compare paired bootstrap ở §8.3 được sinh trực tiếp từ run này.

Lịch sử ngày 01/10 ghi Search suite 346 passed, 11 skipped, 1 deselected. Phần bổ sung ngày 02/10 có test cấu hình/arm **15 passed**; sanity e5-base và e5-large đều **4/4 PASS**. Artifact benchmark nằm local và không được commit.

Các giới hạn khi dùng báo cáo để quyết định:

- Pool nhãn chưa đầy đủ và có ảnh hưởng của các model dùng dựng pool. D4a ở lineage gold gồm nhãn máy: 93 cặp được duyệt tay, phần còn lại duyệt hàng loạt; không coi toàn gold là đánh giá độc lập hai người.
- Một số câu typo từng dùng xây normalizer; đây chưa phải test set hoàn toàn độc lập. Slice nhỏ có CI rộng.
- PASS coverage không phải PASS production. Chưa có HTTP load test; bench flat 3.183 vector không chứng minh tốc độ ANN ở catalog lớn.
- S8 stages/regression và split dev/test còn lại; 131 câu không đủ split 100/100 theo plan cũ.

Bước tiếp theo theo ưu tiên miễn phí: chạy e5-base qua pipeline APP và HTTP end-to-end; đo cache hit/miss, concurrency, RAM và HNSW trên máy gần production; bổ sung nhãn có mục tiêu cho các hạng 2–5 nếu nhóm cần chốt thứ tự phụ; hoàn thiện baseline/regression. Chỉ sau các bước đó mới lập đề xuất đổi model trong PRD. Report này chưa thay đổi engine hoặc hạ ngưỡng nghiệm thu.

## 10. Cách tái sinh và kiểm tra số

Từ thư mục `src/`, dùng môi trường bench hiện có (lượt này dùng conda `vsf2`). `tokens/embed/load/run` dùng model và Weaviate local; không gọi Cohere. `compare` chỉ đọc artifact trong cùng run. Muốn tái đo thời gian re-index từ đầu phải dùng cache rỗng; chạy lại trên cache nóng sẽ nhanh hơn và không tái sinh wall-clock ở §8.

```bash
python -m evaluation.search_bench gold check
python -m evaluation.search_bench tokens --variant T3+R --model e5-base
python -m evaluation.search_bench tokens --variant T3+R --model e5-large-instruct
python -m evaluation.search_bench embed --variant T3+R --model e5-base
python -m evaluation.search_bench embed --variant T3+R --model e5-large-instruct
python -m evaluation.search_bench load --variant T3+R --model e5-base
python -m evaluation.search_bench load --variant T3+R --model e5-large-instruct
python -m evaluation.search_bench --dataset jsonl --run-id 20261002-day5-local-ranking run --arm E2.e5 --arm E2.e5s --arm E2.bge --arm E2.gte --arm E2.e5L
python -m evaluation.search_bench --dataset jsonl --run-id 20261002-day5-local-ranking compare E2.e5 E2.e5s --gold gold_v3
python -m evaluation.search_bench --dataset jsonl --run-id 20261002-day5-local-ranking compare E2.e5 E2.bge --gold gold_v3
python -m evaluation.search_bench --dataset jsonl --run-id 20261002-day5-local-ranking compare E2.e5 E2.gte --gold gold_v3
python -m evaluation.search_bench --dataset jsonl --run-id 20261002-day5-local-ranking compare E2.e5 E2.e5L --gold gold_v3
python -m evaluation.search_bench --dataset jsonl --run-id 20261002-day5-local-ranking compare E2.e5s E2.bge --gold gold_v3
python -m evaluation.search_bench --run-id 20261002-day5-local-only latency embed --models e5-base --warmup 20
python -m evaluation.search_bench --run-id 20261002-day5-e5-large latency embed --models e5-large-instruct --warmup 20
```

### Hash cấu hình của các arm

Hash dưới đây lấy từ artifact, giúp phát hiện so nhầm cấu hình giữa các lượt chạy.

| Arm | resolved_config_hash |
|---|---|
| B0 | `9b08fb796dd62a1146126d86051a2c998316c54b` |
| E2.e5s | `57f52b431dde153fadc24fc2f1f6c45e788fe250` |
| E2.e5 | `b08fc11d0f795139c8179708f03779bec4b7fa63` |
| E2.e5L | `58335f4870d829c3afc9cfc65a87e365211400c3` |
| E2.gte | `6954d71cfd23bb63152ba631a73c5cd166aff592` |
| E2.bge | `149251b5a16194fce8af1df43be8e8c1aa9bb831` |
| E2.v4-256 | `003f86735027db47d446c2d0b494e436cca9d889` |
| E2.v4-512 | `0b9b6be1ea72e34fdcdb51134decdf6ecffb3c84` |
| E2.v4-1024 | `4c681c65fba4f90890de5f1f9c9356281eeff35f` |
| E2.v4-1536 | `8261bbd3abb23d1b8c6e06f0236a016cd554759c` |
| APP.dense | `9b5603cb85c0a5b39714d15d7d75b9efcefa9b3d` |
| APP.hybrid | `154339f447230ab37195c8e61f4a989db080d886` |
| APP.hybrid_norm | `b7c0f98691338a5f59bec8726020b49d5a3fd6a8` |

Với run Day 4, đọc đúng `results@gold_v3.json` vì `results.json` gốc có thể vẫn ghi gold_v2. Run `20261002-day5-local-ranking` sinh trực tiếp `results.json` trên gold_v3. Rescore chỉ tính lại điểm theo nhãn mới, giữ nguyên top-k và thời gian cũ, không tái đo latency. Muốn đo embedding mới dùng `python -m evaluation.search_bench latency embed --help` để chọn model/warm-up; muốn đo HTTP dùng `python -m evaluation.search_bench latency http --help`. Hai phép đo đó là lượt chạy mới, phải lưu run ID và cấu hình riêng.

Nguồn kiểm chứng trong repo: `search_bench/metrics.py` (công thức, bootstrap, verdict), `runner.py` (đồng hồ retrieval, judged gate), `latency.py` (đo embedding/HTTP), `app_adapter.py` (phạm vi đo APP), `config/sbench.yaml` (ngưỡng), `arms/*.yaml` (cấu hình từng arm), `docs/prd/requirements.md` (NFR/FR), `docs/spec/bench/search-eval-local-spec.md` Part 8–10 (metric và chọn cấu hình).
