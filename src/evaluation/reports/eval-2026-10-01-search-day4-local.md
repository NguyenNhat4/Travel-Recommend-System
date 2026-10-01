# Search Day 4 — kết quả cuối sau D5a

- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01.
- Nhánh: `bench_search_recomSys`. Run ID: `20261001-day4-local`.
- Trạng thái: working tree chờ người dùng review; dự kiến tag `gold_v3` sau khi được đồng ý commit. Base của lượt chạy retrieval là `b692047eb075327d86d95b048a229e2abf43b6d4`.
- Gold cuối: 131 câu active / 13 slice / 4.991 nhãn active; 1 câu retired / 30 nhãn. Tổng 5.021 nhãn. SHA-256 `4d2ac02fa960ceaf2c9286bf546da1b77023435a9337ecadee22dd7cc62f5784`.
- Catalog snapshot `2026-09-23`: 11.387 record, 3.183 search unit; records SHA-256 `ad3f3be25647a44c027ab21592f4defc3740f247090a146ea3614eb83adff4ab`.
- Máy local: Intel Core i5-1145G7, 8 logical CPU; Weaviate 1.37.3. Rescore và condensed chỉ đọc top-k đã lưu, không gọi Cohere hay Weaviate.

## Việc đã hoàn thành

- S1: gold sanity PASS trên 131 câu active, 13 slice.
- S2: hồ sơ gold đã cập nhật đủ D4a, D4b và D5a.
- S3: `sb compare --gold` đọc đúng artifact rescore; thêm `--condensed` và coverage.
- S4: 8 bộ vector document × 3.183 = **25.464 vector**.
- S5: đánh giá dense, hybrid, hybrid+normalize; D4b 278/278 nhãn đã import.
- S6: đánh giá 7 arm E; D5a 700/700 nhãn người + 72 auto-OOC đã import và rescore.
- S7: latency query embedding có warm-up, cache off và điều kiện đo riêng.
- S8a: condensed evaluation hoàn thành, có test. S8b/c (stages và dev/test split) để Day 5 vì là mục tùy thời gian và 131 câu không đủ split 100/100.

## Cách so sánh công bằng

Mọi arm dùng cùng catalog, 131 query, text `T3+R`, `k=10`, filter và scorer. Pool D5a lấy hợp top-10 của cả 7 arm E, bỏ trùng, phân phối round-robin theo slice/query, rồi cap 700 theo plan. Sau cap vẫn còn kết quả chưa nhãn nên report giữ hai góc nhìn:

- **Full:** mọi kết quả chưa nhãn được tính relevance 0; `Judged@10` cho biết mức phủ.
- **Condensed:** bỏ kết quả chưa nhãn, dồn hạng rồi tính lại; luôn báo `retained ratio` cạnh số này.

Full là số chính. Condensed dùng để kiểm độ nhạy khi pool đã chạm cap, không che mức thiếu nhãn.

## Xếp hạng chất lượng sau D5a

Bảng này xếp theo nDCG@10 full. Đây là **xếp hạng điểm ước lượng**, không phải thứ tự chọn model: coverage khác nhau và chênh lệch nhỏ phải đọc cùng paired CI.

| Hạng điểm | Arm/model | Dim | Recall@10 full | nDCG@10 full | MRR@10 full | Judged@10 | nDCG@10 condensed | Gate |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | E2.v4-1536 | 1536 | 0,354631 | 0,718561 | 0,794922 | 0,912977 | 0,720852 | Chưa đạt: no_diacritics 0,658 |
| 2 | **E2.v4-1024** | **1024** | **0,352025** | **0,715580** | **0,800000** | **0,922901** | **0,718036** | **Đạt sau tolerance số thực** |
| 3 | **E2.v4-512** | **512** | **0,350643** | **0,708921** | **0,791174** | **0,898473** | **0,711304** | **Đạt** |
| 4 | B0 / Cohere v3 | 1024 | 0,350257 | 0,685006 | 0,757909 | 1,000000 | 0,685006 | Đạt; control production |
| 5 | E2.v4-256 | 256 | 0,321962 | 0,641191 | 0,740256 | 0,812977 | 0,652074 | Chưa đạt: no_diacritics 0,600 |
| 6 | E2.bge | 1024 | 0,322666 | 0,636094 | 0,738046 | 0,802290 | 0,648056 | Chưa đạt: no_diacritics 0,358 |
| 7 | E2.e5s | 384 | 0,317468 | 0,634556 | 0,727883 | 0,788550 | 0,647075 | Chưa đạt overall và 2 slice |
| 8 | E2.gte | 768 | 0,282691 | 0,582810 | 0,686620 | 0,722901 | 0,597945 | Chưa đạt overall và 3 slice |

V4-1024 có `no_diacritics Judged@10 = 84/120 = 0,700` đúng ngưỡng. Giá trị float nội bộ nhỏ hơn 0,7 khoảng 1e-16 từng làm gate báo sai `0.700 < 0.7`. Gate nay dùng tolerance tuyệt đối 1e-12; test hồi quy xác nhận giá trị bằng ngưỡng PASS, thấp hơn 1e-6 vẫn FAIL.

`retained ratio` bằng `Judged@10` vì các arm trả tối đa 10 kết quả. Condensed có 1 query rỗng ở BGE và 3 query rỗng ở GTE; các arm còn lại không rỗng.

## So sánh trực tiếp các ứng viên v4

| A → B | Δ Recall@10 condensed | CI95 | Δ nDCG@10 condensed | CI95 | p nDCG | Kết luận |
|---|---:|---|---:|---|---:|---|
| v4-512 → v4-1024 | +0,14 điểm | [−0,62; +0,89] | +0,67 điểm | [−0,83; +2,05] | 0,184 | TIE |
| v4-512 → v4-1536 | +0,40 điểm | [−0,40; +1,22] | +0,95 điểm | [−0,66; +2,58] | 0,131 | TIE |

Điểm trung bình tăng theo chiều vector, nhưng cả hai CI đều cắt qua 0. Dữ liệu hiện tại không chứng minh 1024 hoặc 1536 tốt hơn 512 có ý nghĩa.

### V4-512 so với v4-1024

- 1024 nhỉnh +0,67 điểm nDCG condensed và +0,14 điểm Recall; chênh lệch là TIE.
- 1024 có coverage tốt hơn: 0,923 so với 0,898 và cả hai đạt gate.
- 1024 dùng **2 lần** số chiều và raw vector float32; truy xuất local p50/p95 8,20/9,98 ms so với 6,83/8,11 ms của 512.
- Chọn 1024 khi ưu tiên tối đa điểm chất lượng và chấp nhận thêm bộ nhớ/index. Chọn 512 khi ưu tiên hiệu quả vì chưa thấy lợi ích chất lượng có ý nghĩa từ 1024.

### V4-512 so với v4-1536

- 1536 có điểm cao nhất, nhưng chỉ hơn 512 +0,95 điểm nDCG condensed và vẫn là TIE.
- 1536 chưa đạt coverage ở `no_diacritics`: 0,658.
- 1536 dùng **3 lần** số chiều; truy xuất local p50/p95 9,84/11,57 ms.
- 1536 phù hợp làm upper-bound nghiên cứu. Không nên chọn làm mặc định ở vòng này.

### V4-512 so với B0/Cohere v3

- Recall gần như bằng nhau: v4-512 chỉ +0,04 điểm. Condensed nDCG nhỉnh +2,63 điểm nhưng CI [−1,46; +6,58] và có slice giảm mạnh.
- B0 có coverage 1,000, đang là production control và không cần migration.
- V4-512 dùng nửa số chiều và retrieval local nhanh hơn, nhưng vẫn cần API v4 và quy trình promote.
- Kết quả chưa đủ để đổi production trực tiếp. V4-512 nên đi tiếp như challenger Day 5.

## Bảng so sánh toàn diện cho production và scale dài hạn

### Giả định và phạm vi chi phí

- Lượt benchmark dùng **Cohere trial key**, nên tiền bị trừ thực tế là **0 USD**. Trial key bị rate limit và không dùng cho production; lỗi 429 trong lượt đo v4 cho thấy rủi ro vận hành dù chưa phát sinh hóa đơn. [Trang giá Cohere](https://cohere.com/pricing) xác nhận trial miễn phí/rate-limited và production tính pay-as-you-go, nhưng hiện không công bố đơn giá Embed v3/v4 theo token trên trang này.
- Ước tính production dùng đúng working estimate đang khóa trong `docs/spec/bench/search-eval-local-spec.md`: v3 = **0,10 USD/1M input token**, v4 = **0,12 USD/1M input token**. Đây là số để so tương đối, **không phải báo giá chính thức**; phải xác nhận lại trong Cohere dashboard/hợp đồng trước khi lập ngân sách.
- Log benchmark ghi 997 API call, 2.170.114 input token, chi phí quy đổi **0,251771 USD**: v3 document 0,042661; v3 query 0,000554; v4 document 0,206932; v4 query 0,001624. Đây là số quy đổi theo cấu hình, không phải tiền trial bị trừ.
- Một lần embed lại 3.183 search unit ước tính: v3 khoảng **0,0425 USD**; mỗi cấu hình v4 khoảng **0,051–0,052 USD**. V4 256/512/1024/1536 có cùng lượng input, nên giảm chiều **không giảm phí Cohere**; lợi ích nằm ở RAM, disk, network, backup, replica và tốc độ vector search.
- Query benchmark trung bình khoảng 11–12 token. API estimate: v3 khoảng **1,14 / 11,35 / 113,52 USD** cho 1M/10M/100M query; v4 khoảng **1,40 / 13,97 / 139,72 USD**. Chưa gồm vector DB, network, replica, backup, monitoring và nhân công.
- Kịch bản scale trong bảng là **1 triệu sản phẩm + 100 triệu query/tháng**. Raw vector = `N × dimension × 4 byte`. HNSW, metadata, WAL, replica và backup làm dung lượng thật cao hơn; chưa đổi storage thành USD vì dự án chưa chốt nhà cung cấp/tier.
- CPU-hour local là nội suy tuyến tính từ i5-1145G7 và latency tuần tự p50, chỉ dùng để so tương đối. Production phải benchmark throughput theo batch, concurrency, CPU/GPU, SLO và autoscaling trước khi dự toán tiền.

| Phương án | Chất lượng full: R / nDCG / MRR | Coverage / gate | Latency đã đo | Scale 1M SP + 100M query/tháng | Chi phí và vận hành production | Ưu điểm | Nhược điểm / rủi ro dài hạn | Kết luận |
|---|---|---|---|---|---|---|---|---|
| **Cohere v4-512** | **0,3506 / 0,7089 / 0,7912** | 0,8985; **PASS** | Retrieval 6,83/8,11 ms. Query API: chưa có số sạch do 429 | Raw vector **2,048 GB**; API query estimate **139,72 USD/tháng**; reindex 1M SP xấp xỉ **16,3 USD/lần** nếu token/SP giữ nguyên | Phí API gần như bằng mọi chiều v4. Footprint bằng 1/2 v4-1024 và 1/3 v4-1536, nên có khả năng cần ít RAM/disk/replica bandwidth hơn | TIE với 1024/1536; đạt gate; footprint thấp; retrieval nhanh; dễ scale vector DB nhất trong nhóm chất lượng cao | Phụ thuộc Cohere, internet, quota và thay đổi giá/model; coverage thấp hơn 1024; chưa có latency API v4 end-to-end sạch; cần migration/promote | **Mặc định hiệu quả cho Day 5; ứng viên production tốt nhất hiện tại nếu SLO API đạt** |
| **Cohere v4-1024** | **0,3520 / 0,7156 / 0,8000** | **0,9229; PASS** sau tolerance | Retrieval 8,20/9,98 ms. Query API: chưa có số sạch do 429 | Raw vector **4,096 GB**; API query cũng **139,72 USD/tháng**; reindex xấp xỉ **16,3 USD/lần** | Hóa đơn Cohere gần như bằng v4-512, nhưng vector storage/RAM/backup/network khoảng **2×** ở phần vector thô; có thể đẩy hệ thống sang tier Weaviate cao hơn | Điểm và coverage cao nhất trong hai arm v4 đạt gate; thêm dư địa chất lượng | Chỉ hơn 512 +0,67 điểm nDCG condensed, CI cắt 0; retrieval chậm hơn; 2× footprint; vendor/network risk giống 512 | **Challenger quality-first; chỉ chọn khi Day 5 chứng minh lợi ích đủ bù 2× footprint** |
| Cohere v4-1536 | **0,3546 / 0,7186 / 0,7949** | 0,9130; **FAIL** `no_diacritics` 0,658 | Retrieval 9,84/11,57 ms. Query API chưa có số sạch | Raw vector **6,144 GB**; API query **139,72 USD/tháng**; reindex xấp xỉ **16,3 USD/lần** | Cohere cost gần như bằng v4-512, nhưng vector thô/traffic backup **3×**; xác suất cần tier RAM cao nhất | Điểm trung bình cao nhất; upper bound hữu ích | Không chứng minh hơn 512; fail slice gate; footprint, migration và retrieval cost cao nhất; lợi ích biên nhỏ | Upper bound nghiên cứu; **không hợp lý cho production hiện tại** |
| **B0 / Cohere v3-1024** | 0,3503 / 0,6850 / 0,7579 | **1,0000; PASS** | Retrieval 8,10/12,19 ms; query API 459,11/734,97 ms | Raw vector **4,096 GB**; API query estimate **113,52 USD/tháng**; reindex 1M SP xấp xỉ **13,4 USD/lần** | Token estimate thấp hơn v4 khoảng 19%; đang là production control nên migration cost gần 0. Vẫn cần external API, quota, retry/circuit breaker | Coverage hoàn chỉnh; ít rủi ro thay đổi; số latency API đã đo; rollback/control rõ | nDCG thấp hơn v4; p95 API cao; footprint 2× v4-512; model cũ có rủi ro vòng đời/deprecation dài hạn | **Control và phương án an toàn; không phải đích tối ưu nếu v4 qua SLO Day 5** |
| Cohere v4-256 | 0,3220 / 0,6412 / 0,7403 | 0,8130; **FAIL** `no_diacritics` 0,600 | Retrieval 6,86/11,61 ms; query API chưa có số sạch | Raw vector **1,024 GB**; API query vẫn **139,72 USD/tháng**; reindex vẫn xấp xỉ **16,3 USD/lần** | Vector DB rẻ nhất nhóm Cohere, nhưng phí API không giảm; p95 retrieval không tốt hơn 512 trong phép đo | Footprint nhỏ nhất; dễ chứa nhiều replica/cache | Mất chất lượng rõ, fail gate; tiết kiệm storage nhưng vẫn trả cùng phí query v4; có nguy cơ giảm conversion/search success | Không shortlist; chỉ xét nếu hạ tầng vector bị giới hạn cực chặt |
| **e5-small local-384** | 0,3175 / 0,6346 / 0,7279 | 0,7886; **FAIL** overall + 2 slice | Retrieval 5,97/7,23 ms; query CPU 9,19/11,37 ms | Raw vector **1,536 GB**. Reindex ~**25 CPUh/1M SP**. Nội suy tuần tự ~**255 CPUh/100M query** ở p50 | 0 phí API và không phụ thuộc internet. Chi phí chuyển sang máy inference, RAM, autoscaling, image/model distribution, monitoring và on-call. Có thể rẻ ở tải đều nếu tận dụng CPU sẵn có | Data ở local; không 429; query encode nhanh nhất; footprint nhỏ; kiểm soát version/rollback; tránh vendor lock-in | Chất lượng chưa đạt; phải tự bảo đảm HA/capacity; CPU estimate chưa gồm concurrency; patch bảo mật và model lifecycle do team chịu | **Fallback local tốt nhất; chưa đủ chất lượng làm primary** |
| BGE-M3 local-1024 | 0,3227 / 0,6361 / 0,7380 | 0,8023; **FAIL** `no_diacritics` 0,358 | Retrieval 5,71/8,78 ms; query CPU 148,78/245,81 ms | Raw vector **4,096 GB**. Reindex ~**179,5 CPUh/1M SP**. Nội suy ~**4.133 CPUh/100M query** | 0 phí API nhưng compute/replica/autoscale lớn; có thể cần GPU hoặc nhiều worker để giữ SLO | Local, kiểm soát dữ liệu; retrieval p50 thấp nhất | Query encode chậm nhất; footprint lớn; fail gate nặng; chất lượng chỉ nhỉnh e5 ít nhưng compute cao hơn nhiều | Không shortlist; bị e5 chi phối về cost/performance |
| GTE multilingual-base-768 | 0,2827 / 0,5828 / 0,6866 | 0,7229; **FAIL** overall + 3 slice | Retrieval 6,42/8,17 ms; query CPU 66,49/78,00 ms | Raw vector **3,072 GB**. Reindex ~**94,7 CPUh/1M SP**. Nội suy ~**1.847 CPUh/100M query** | 0 phí API, nhưng CPU và hạ tầng cao hơn e5; vẫn cần HA, rollout và monitoring model | Local/offline; footprint trung bình; không vendor API | Chất lượng/coverage thấp nhất; compute cao hơn e5; không có lợi thế bù lại | Không shortlist |

### Trade-off quyết định production

1. **Chất lượng trước, rồi mới tối ưu chi phí.** V4-256 và ba model local hiện fail gate; chi phí thấp không bù được rủi ro trả kết quả kém. Chúng chỉ phù hợp fallback hoặc nghiên cứu.
2. **V4-512 có cost/performance tốt nhất trong dữ liệu hiện tại.** So với v4-1024, Cohere API bill gần như bằng nhau nhưng footprint vector giảm 50%; đổi lại nDCG condensed thấp hơn 0,67 điểm và coverage thấp hơn 2,44 điểm phần trăm. Chênh chất lượng chưa có ý nghĩa thống kê.
3. **V4-1024 là khoản đầu tư vào chất lượng tiềm năng.** Chỉ nên trả 2× footprint nếu Day 5/A-B test chứng minh tăng search success, click hoặc conversion đủ lớn; Day 4 chưa chứng minh được.
4. **V4-1536 có lợi ích biên thấp.** 3× footprint của 512, fail một gate và vẫn TIE; không có business case production ở vòng này.
5. **B0/v3 giảm rủi ro migration nhưng có technical debt vòng đời model.** Nó phù hợp làm control/rollback trong giai đoạn chuyển đổi, không nên mặc định là phương án 3–5 năm nếu vendor công bố lộ trình thay thế.
6. **Local không đồng nghĩa miễn phí.** E5 bỏ hóa đơn API và rủi ro mạng nhưng cần capacity, HA, autoscaling, monitoring và người vận hành. E5 chỉ trở nên kinh tế hơn khi tổng chi phí CPU/hạ tầng/on-call thấp hơn API + vector DB và chất lượng được cải thiện đủ qua gate.
7. **Chi phí chính ở scale lớn chưa phải tiền reindex.** Với giả định hiện tại, 100M query/tháng tốn khoảng 113,52 USD ở v3 hoặc 139,72 USD ở v4 cho embedding query; vector DB, replica, RAM và vận hành có thể lớn hơn. Vì chưa có báo giá Weaviate/cloud và SLO tải, report không tự gán USD cho phần này.

### Quyết định đề xuất và điều kiện trước production

- Đưa **v4-512** và **v4-1024** sang Day 5; B0/v3 là control/rollback; e5-small là fallback local.
- Chưa đổi production từ Day 4. Day 5 cần đo end-to-end `/search` với concurrency/QPS mục tiêu, timeout/retry/circuit breaker, quota Cohere production, chi phí Weaviate thật theo 512 và 1024, và A/B metric gắn với business.
- Chọn **v4-512** nếu hai arm tiếp tục TIE hoặc v4-1024 không tạo uplift business đủ bù 2× footprint.
- Chọn **v4-1024** nếu kiểm thử độc lập chứng minh uplift ổn định và hạ tầng vẫn nằm trong cùng tier ngân sách.
- Duy trì khả năng rollback về B0 và fallback e5 khi Cohere/network lỗi; không xem trial key là cấu hình production.

## Ba arm Search v1 sau gold cuối

| Arm | Recall@10 | nDCG@10 | MRR@10 | Judged@10 | Zero in-catalog |
|---|---:|---:|---:|---:|---:|
| APP.dense | 0,305920 | 0,619530 | 0,693304 | 1,000000 | 0,164062 |
| APP.hybrid | 0,306081 | 0,596552 | 0,643083 | 1,000000 | 0,156250 |
| APP.hybrid_norm | 0,339702 | 0,647718 | 0,704021 | 1,000000 | 0,070312 |

Hybrid+normalize tăng Recall so với dense +3,38 điểm, CI95 [+1,33; +5,67], nhưng vẫn LOSE theo guard slice vì `dest_type` −13,19 điểm. Chưa thay dense bằng hybrid+normalize.

## Vector và latency

Có 8 bộ vector document hoàn chỉnh:

| Model | Dim | Số vector | Điều kiện query latency p50/p95 ms |
|---|---:|---:|---|
| Cohere v3 | 1024 | 3.183 | 459,105 / 734,967; Cohere API, nghỉ 1.000 ms ngoài khoảng đo |
| Cohere v4 | 1536 | 3.183 | API bị 429 giữa sweep; dùng Weaviate local 9,84 / 11,57 để so kích thước |
| Cohere v4 | 1024 | 3.183 | Weaviate local 8,20 / 9,98 |
| Cohere v4 | 512 | 3.183 | Weaviate local 6,83 / 8,11 |
| Cohere v4 | 256 | 3.183 | Weaviate local 6,86 / 11,61 |
| e5-small | 384 | 3.183 | local CPU 9,192 / 11,369 |
| GTE multilingual base | 768 | 3.183 | local CPU 66,487 / 78,001 |
| BGE-M3 | 1024 | 3.183 | local CPU fp32/safetensors 148,779 / 245,814 |

Cohere API và local CPU không cùng điều kiện nên không dùng bảng này để tuyên bố model nào nhanh hơn end-to-end. V4 API bị 429 đã được loại, không trộn retry vào percentile. Gate latency toàn `/search` thuộc Day 5.

## Dữ liệu nhãn D5a

Pool trước cap có 2.024 cặp người duyệt. Pool chính thức có 700 cặp / 128 câu; người dùng gán đủ 700/700 với phân bố: 190 nhãn 0, 170 nhãn 1, 340 nhãn 2. Thêm 72 cặp out-of-catalog tự gán 0. `gold check` và `gold verify-append gold_v2` PASS: +1.050 nhãn tính cả D4b + D5a, không đổi query/nhãn cũ.

Sau vòng này **không cần label thêm để hoàn thành Day 4**. V4-512 và v4-1024 đều đạt gate. Các arm còn lại được đọc bằng condensed theo cap đã quy định; muốn đưa một arm chưa đạt gate vào shortlist thì cần top-up riêng ở Day 5.

## Lệnh tái sinh số

Chạy từ `src/` trong conda `vsf2`:

```bash
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local rescore --allow-untagged
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local compare E2.v4-512 E2.v4-1024 --gold untagged --condensed
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local compare E2.v4-512 E2.v4-1536 --gold untagged --condensed
python -m evaluation.search_bench --dataset jsonl --run-id 20261001-day4-local compare APP.dense APP.hybrid_norm --gold untagged
```

Artifact run ở `bench_out/search/runs/20261001-day4-local/` không commit. Config, gold, pool, report và test đang ở working tree để người dùng review; chưa commit.
