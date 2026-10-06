# Báo cáo tuần 3 — Đánh giá offline Recommendation Engine: chọn thuật toán và hướng cải thiện tuần 4

- Giai đoạn: tuần 3, 28/09–02/10/2026 (Day 1–5 của `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`).
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-03, FR-REC-04, NFR-PERF-01 (`docs/prd/requirements.md` §1.3, §2.1); `docs/prd/test-plan.md` §2.5.
- Báo cáo này **không chạy thêm thí nghiệm**. Mọi con số lấy từ các report đã chạy (mục 8) và được sắp lại thành các bảng nhỏ, mỗi bảng trả
  lời một câu hỏi. Vài chênh lệch không kèm CI là phép trừ trực tiếp giữa hai số trong bảng nguồn.
- Người đọc: cả nhóm và mentor, kể cả người không làm recommendation. Thuật ngữ giải thích ở mục 2 và phụ lục.

> **Đọc trước khi trích dẫn.** Lịch sử khách hàng là **dữ liệu sinh** (seed). Số đo cho biết pipeline chạy đúng và thuật toán nào hơn
> thuật toán nào **trên cùng dữ liệu**, không nói engine sẽ đạt bao nhiêu trên khách thật.

---

## Tóm tắt

Tuần này nhóm so 11 thuật toán gợi ý với 3 mốc tham chiếu: bốc ngẫu nhiên, bán chạy nhất toàn sàn, và bán chạy nhất trong điểm đến (mpd).
Trong 11 thuật toán có 8 thuật toán chính (Tier 1) và 3 thuật toán bổ sung, chạy khi còn thời gian (Tier 2). Mỗi khách test bị giấu một món
đã mua; thuật toán đưa được món đó vào 20 gợi ý thì tính là trúng (Hit@20). Dữ liệu được chia theo hai cách: **LLBO** (1.016 khách, đoán món
tiếp theo của chuyến đang đi) và **temporal** (98 khách, đoán món mua đầu tiên sau mốc T). Mọi thuật toán qua cùng một bộ lọc ứng viên.

Kết quả chính:

1. **Thuật toán lõi được chọn là Content-based** (tên trong code `content_profile`) — engine hiện tại, gợi ý theo độ giống nội dung giữa
   sản phẩm và lịch sử của khách.
   Không thuật toán nào thắng nó trên temporal. Ba thuật toán nhỉnh hơn ở một chỉ số trên LLBO đều thua nó trên temporal.
2. **Với khách đang có chuyến mở (LLBO), bộ lọc cứng đóng góp nhiều hơn thuật toán.** Cùng thuật toán Content-based, Hit@20 trên LLBO đạt 0,875
   khi có lọc (chỉ giữ món ở điểm đến của chuyến đang mở, bỏ loại sản phẩm đã mua trong chuyến), không lọc chỉ đạt 0,433. Content-based một mình
   hay gợi "thêm một khách sạn nữa", bộ lọc biến nó thành "vé máy bay và vé tham quan cho chuyến này". Trên temporal, nơi phần lớn khách không
   có chuyến mở, bộ lọc chỉ thêm 1,0 điểm; ở đó phần Content-based hơn mpd đến từ thuật toán.
3. **Lọc cộng tác (CF, kiểu "khách giống bạn đã mua gì") không hơn mpd + bộ lọc, tức "bán chạy trong điểm đến" xếp trên cùng tập ứng
   viên.** Các thuật toán CF đã thử: Item-based CF, ItemKNN, EASE, RP3beta, iALS, BPR-MF. Dữ liệu
   có quá ít lượt mua chung: trên LLBO chỉ 10 % sản phẩm từng được mua cùng chuyến với ít nhất một sản phẩm khác, nên CF gần như không có gì
   để học.
4. **Lợi thế của iALS là ảo.** 43 % khách LLBO (441/1.016; temporal chỉ 2/98) đã có sẵn món đáp án trong lịch sử, gần như toàn bộ vì đã
   bỏ món đó vào giỏ. iALS đọc thẳng giỏ hàng nên thắng ở nhóm này và thua ở nhóm còn lại. Tín hiệu "đã bỏ giỏ, chưa mua" có thật trong dữ
   liệu sinh và đáng nghiên cứu (việc #6 tuần 4; nếu có ích thì soạn đề xuất PRD).
5. **Phần lớn điểm bị mất nằm ở các bước sau thuật toán.** Luật "tối đa 2 món mỗi loại" của danh sách production tốn 5,8 điểm Hit@5 trên
   LLBO và làm danh sách này không còn hơn mpd về Hit@20. MMR (đa dạng hoá) tốn 2,7 điểm Hit@20 trên LLBO.
6. **Engine mạnh ở khách mới và khách đang trong chuyến, yếu ở "chuyến kế tiếp".** Với khách đã mua một món trong chuyến, phần mạnh là nhờ bộ
   lọc: Content-based chỉ ngang mpd + bộ lọc (0,872 so với 0,870). Với khách không có chuyến đang mở, engine chỉ ngang "bán chạy trong điểm đến".

Tuần 4 không đổi thuật toán. Việc làm theo thứ tự: sửa harness để bỏ tín hiệu giỏ hàng khỏi số đo, đề xuất đổi luật cap, dò trọng số
engine trên split temporal, nghiên cứu tín hiệu giỏ hàng (mục 6).

---

## 1. Câu hỏi nghiên cứu

| # | Câu hỏi | Trả lời ngắn | Mục |
|---|---|---|---|
| Q1 | Bench có đáng tin không? | Có. Bốc ngẫu nhiên ra gần 0; bench tái tạo đúng engine và đúng API | 2.6 |
| Q2 | Thuật toán nào làm lõi? | Content-based | 3.2 |
| Q3 | Bộ lọc cứng đóng góp bao nhiêu? | +44 điểm trên LLBO, +1 điểm trên temporal | 3.3 |
| Q4 | CF có học được gì trên dữ liệu này? | Không hơn độ phổ biến | 3.4 |
| Q5 | Vì sao iALS thắng ở một chỉ số? | Nhờ tín hiệu giỏ hàng, không nhờ CF | 3.5 |
| Q6 | Khách mới, khách đang trong chuyến, chuyến kế tiếp thì sao? | Mạnh ở khách mới; trong chuyến thì bộ lọc làm phần chính; yếu ở chuyến kế | 3.6 |
| Q7 | Mất điểm ở đâu sau thuật toán? | Cap 2 món/loại tốn 5,8 điểm Hit@5; MMR tốn 2,7 điểm Hit@20 | 3.7, 3.8 |
| Q8 | Có giải thích được gợi ý không? | Content-based 100 %; BPR-MF 0 % | 3.9 |
| Q9 | Tuần 4 làm gì? | 9 việc theo thứ tự ở ADR 2 | 6 |

---

## 2. Thiết lập thí nghiệm

### 2.1 Dữ liệu

| Mục | Giá trị |
|---|---|
| Database | Postgres local, seed 23/09, `as_of` 24/09/2026 |
| Sự kiện hành vi | 7.145 thô, 6.993 sau lọc (bỏ 152 đơn mua: 63 trỏ sản phẩm không tồn tại, 94 thiếu mã chuyến, hai nhóm trùng nhau 5 đơn) |
| Sản phẩm | 3.183 đơn vị tìm kiếm, trong đó 2.384 được phép gợi ý |
| Vector sản phẩm | Cohere `embed-multilingual-v3.0`, 1024 chiều, `modelVersion embed-multilingual-v3.0:catalog-text-v2` |
| Kiểm tra dữ liệu seed | PASS 6/6 kiểm tra cứng |

### 2.2 Hai cách chia dữ liệu — hai câu hỏi khác nhau

Mỗi khách test có **đúng một món đáp án** bị giấu đi. Bench hỏi: trong 20 món engine gợi ý, có món đáp án không?

| | LLBO (giấu đơn mua cuối) | Temporal (cắt theo thời gian) |
|---|---|---|
| Câu hỏi | Khách đang ở giữa chuyến, món tiếp theo họ mua là gì? | Sau mốc T, khách mua gì đầu tiên? |
| Ví dụ đời | Vừa đặt khách sạn Nha Trang, giờ đoán họ mua vé máy bay hay vé VinWonders | Tháng trước đi Nha Trang, tháng này họ đặt gì cho chuyến sau |
| Số khách | **1.016** | **98** (T = 10/07/2026) |
| Món đáp án | flight 433 · attraction 330 · combo 123 · hotel 80 · golf 50 | hotel 93 · attraction 4 · combo 1 |
| Điểm mạnh | Mẫu lớn, CI hẹp | Thời gian trung thực: không ai được "nhìn trước tương lai" |
| Điểm yếu | Dữ liệu train có sự kiện của khách khác xảy ra **sau** thời điểm đoán; 43 % khách đã có món đáp án trong giỏ | Mẫu nhỏ: 1 khách = 1,02 điểm; 95 % đáp án (93/98) là khách sạn; 73/98 khách không có chuyến đang mở ¹ |

¹ 73 = 57 khách `long_term` + 16 khách `dormant`, khớp với 98 − 25 khách có chuyến mở. Report `eval-2026-10-01-recsys-algos-v1.md` mục 8
ghi "72/98" — đó là lỗi cộng của report nguồn.

**Quy tắc đọc.** Theo quy ước của spec bench (`docs/spec/bench/recsys-offline-eval.md` §3.1, quy ước B10), so thuật toán và dò tham số làm trên
temporal vì thời gian trung thực; LLBO là bảng tham chiếu và không dùng để chọn tham số. Báo cáo này thêm một tiêu chí riêng: một kết luận
chỉ coi là **vững** khi hai cách chia cùng hướng, hoặc khi trên temporal khoảng tin cậy 95 % (CI) của chênh lệch không chứa 0 (dấu `*`,
mục 2.3).

### 2.3 Chỉ số

| Chỉ số | Nghĩa dễ hiểu | Tốt khi |
|---|---|---|
| Hit@20 (= Recall@20) | Tỉ lệ khách có món đáp án nằm trong 20 gợi ý. Mỗi khách một đáp án nên Recall = Hit | Cao |
| Hit@5 | Như trên, chỉ xét 5 món đầu — đúng số món trang chủ hiển thị | Cao |
| NDCG@10 | Như Hit@10 nhưng thưởng thêm khi đáp án đứng **gần đầu** | Cao |
| Coverage | Tỉ lệ sản phẩm được gợi ý ít nhất một lần cho ai đó | Cao |
| Gini | Mức dồn lượt hiển thị vào ít sản phẩm: 0 là chia đều, gần 1 là vài món chiếm hết | Thấp hơn là đa dạng hơn |
| Diversity@10 | Độ khác nhau giữa 10 món đầu trong cùng một danh sách | Cao |
| Cross-cat có mua | Trong chuyến khách đã mua một loại, tỉ lệ gợi ý thuộc **loại khác** (cross-sell) | Cao |
| Because@K | Tỉ lệ món trong top-K có lý do giải thích (FR-REC-03) | 1,0 |
| Δ [CI95] | Chênh lệch tính bằng **điểm phần trăm**, kèm khoảng tin cậy 95 % từ paired bootstrap 10.000 lượt | Dấu `*` = CI không chứa 0, tức khác biệt thật |

Mọi Hit trong báo cáo tính kiểu **lenient**. Với flight và hotel, đáp án là chuyến bay hoặc phòng cụ thể, còn engine chỉ gợi ở cấp tuyến
bay hoặc khách sạn; gợi đúng tuyến hoặc khách sạn cha là tính trúng. Nếu đo kiểu strict (đúng chuyến, đúng phòng) thì 513/1.016 đáp án LLBO
và 93/98 đáp án temporal luôn bằng 0 theo cấu trúc. Với attraction, combo, golf thì hai cách đo như nhau.

### 2.4 Thuật toán được so

Báo cáo dùng **tên gốc** của thuật toán trong tài liệu nghiên cứu. Report nguồn và `src/evaluation/recsys_bench/algos_v1.yaml` dùng **tên
trong code**; cột thứ ba để tra ngược. Cài đặt trong bench theo spec `docs/spec/bench/recsys-algos-v1.md`, có chỗ rút gọn so với bài báo gốc
(cột "Nguồn gốc" ghi rõ).

| Nhóm | Tên gốc | Tên trong code | Nguồn gốc | Ý tưởng một câu | Ví dụ đời |
|---|---|---|---|---|---|
| Mốc | Random | `random` | — | Bốc ngẫu nhiên | Sàn: dưới mức này là bench hỏng |
| Mốc | MostPop | `most_popular` | — | Bán chạy nhất toàn hệ thống, cửa sổ 90 ngày | Top 10 tuần của cả sàn |
| Mốc | MostPop theo điểm đến (mpd) | `most_popular_in_destination` | — | Bán chạy nhất tại điểm đến của khách | Top 10 ở Nha Trang |
| Tier 1 | **Content-based** | `content_profile` | Pazzani & Billsus, 2007. Đây là engine production v5 | Trộn vector nội dung của các món khách đã xem, bỏ giỏ, mua thành "khẩu vị", rồi tìm món giống khẩu vị đó, cộng một phần độ phổ biến | Netflix gợi phim cùng chất với phim bạn vừa xem |
| Tier 1 | mpd + bộ lọc | `pop_funnel` | — | mpd chạy qua cùng bộ lọc với mọi thuật toán khác | Đối chứng: "CF có hơn bán chạy không?" |
| Tier 1 | Item-based CF | `Item-base CF` | Sarwar và cộng sự, 2001; hệ số co theo Koren, 2008. Bảng tính theo **chuyến** × món thay vì khách × món | Món nào hay được mua **cùng chuyến** với món khách đã mua, độ giống cosine có hệ số co (shrinkage) | "Người đặt khách sạn này thường mua thêm vé này" |
| Tier 1 | STAR | `star_blend` | Lee và cộng sự, 2024. Chỉ cài tầng retrieval, không có bước xếp hạng lại bằng LLM | Trong vế "khẩu vị gần đây" của Content-based, thay độ giống nội dung bằng 50 % nội dung + 50 % điểm cùng chuyến | Kết hợp hai câu trên |
| Tier 1 | ItemKNN | `itemknn` | Sarwar và cộng sự, 2001; cài bằng thư viện `implicit` | Như Item-based CF (cùng bảng chuyến × món) nhưng bỏ hệ số co | Đối chứng: hệ số co của Item-based CF có tác dụng không |
| Tier 1 | EASE | `ease` | Steck, 2019 | Học trọng số giữa mọi cặp món bằng một công thức tuyến tính có lời giải trực tiếp | Phiên bản "học" của "mua cùng chuyến" |
| Tier 1 | iALS | `ials` | Hu, Koren & Volinsky, 2008; cài bằng thư viện `implicit` | Phân rã bảng khách × món thành vài "sở thích ẩn" của mỗi khách và mỗi món | Người bán lâu năm đoán "khách này mê nghỉ dưỡng biển" dù khách chưa nói ra |
| Tier 1 | BPR-MF | `bpr` | Rendle và cộng sự, 2009; cài bằng thư viện `implicit` | Như iALS nhưng học thẳng thứ tự: món khách đã mua hoặc đã bỏ giỏ phải xếp trên món chưa tương tác | Hỏi đi hỏi lại: giữa hai món này, khách chọn món nào? |
| Tier 2 | RP3beta | `rp3beta` | Paudel và cộng sự, 2016 | Đi vòng món → chuyến → món trên bảng chuyến × món, rồi giảm điểm món quá phổ biến | "Món hay đi cùng chuyến với món này", nhưng bớt món ai cũng mua |
| Tier 2 | BPR-MF (numpy) | `bpr_numpy` | Rendle và cộng sự, 2009; nhóm tự viết bằng numpy | BPR-MF tự viết lại để đổi được cách chọn "món khách không mua" dùng khi học | Đối chứng của BPR-MF bản `implicit` |
| Tier 2 | BPR-MF-Dest | `bpr_dest` | Biến thể của nhóm, không phải thuật toán riêng trong tài liệu | BPR-MF (numpy), "món khách không mua" lấy **trong cùng điểm đến** | Học "trong Nha Trang, khách chọn món này chứ không chọn món kia" |

Không chạy: two-tower, Mult-VAE, SASRec, LightGCN. Lý do là dữ liệu dưới sàn cho mô hình sâu (khoảng 7.000 sự kiện, 1.486 khách có tương
tác), không phải thiếu thời gian.

### 2.5 Hai chế độ chạy và những dòng đã bỏ khỏi bảng

- **`funnel`** — mọi thuật toán chấm trên cùng tập ứng viên của engine: nếu khách có chuyến đang mở thì chỉ lấy món ở điểm đến của chuyến đó,
  bỏ loại sản phẩm đã mua trong chuyến; luôn chỉ lấy món được phép gợi ý, còn chỗ, chưa từng mua.
- **`raw`** — không lọc điểm đến, không loại theo loại sản phẩm; chỉ bỏ món không được phép gợi ý, món hết chỗ và món đã mua.
- **MMR** — bước sắp lại để 10 món đầu bớt giống nhau, λ = 0,7. Engine có MMR, nên Content-based + MMR **chính là** engine ở chế độ đánh
  giá (arm `engine`, trả đủ 20 món). Danh sách production mà khách thật nhìn thấy (`engine_prod`) còn qua thêm luật "tối đa 2 món mỗi loại"
  (mục 3.8).

Bảng gốc chế độ funnel có 25 dòng mỗi split (6 dòng mốc và engine, 19 dòng thuật toán), chế độ raw có 23 dòng. Báo cáo này **bỏ** các dòng
sau vì không mang thông tin xếp hạng:

| Dòng bỏ | Lý do |
|---|---|
| Item-based CF + MMR, ItemKNN + MMR, EASE + MMR, RP3beta + MMR, iALS + MMR, BPR-MF + MMR | λ của MMR chỉnh cho thang điểm của Content-based (khoảng 0,3–0,8). Các thuật toán này có thang điểm khác: đồng mua chỉ 0–0,3, MF là tích vô hướng không chuẩn hoá. Vế "đa dạng" vì vậy lấn át vế "liên quan"; nhóm đồng mua tụt 14–15 điểm Hit@20 do cấu hình, không do thuật toán |
| STAR + MMR | Chỉ nhắc ở mục 3.7 |
| STAR với a = 1 | Kiểm tra hồi quy: với a = 1 phải ra **đúng** Content-based. Đã khớp 1016/1016 và 98/98 |
| `engine_nommr` | Trùng mọi chỉ số chất lượng với Content-based; chỉ khác số món trả về và thời gian chạy |

### 2.6 Bench có đáng tin không

| Kiểm tra | LLBO | Temporal | Ý nghĩa |
|---|---:|---:|---|
| Random Hit@20 | 0,0066 | 0,0034 | Sàn gần 0 như kỳ vọng |
| Content-based + MMR khớp đúng thứ tự top-20 của arm `engine` (cổng kiểm tra, chấm trên pool của engine) | 1016/1016 | 98/98 | Bench tái tạo đúng engine (chế độ đánh giá). Bảng thuật toán chấm toàn tập ứng viên: temporal khớp thứ tự 81/98 khách, Hit@20 và NDCG@10 không đổi |
| Rò rỉ dữ liệu (ô đáp án lọt vào dữ liệu train theo chuyến) | 0 | 0 | Không gian lận |
| Availability của mọi thuật toán | 1,000 | 1,000 | Không gợi món hết chỗ |
| Số offline = số qua HTTP (60 khách `users60.json`, DB seed 21/09, engine chế độ production, top-5) | 60/60 (bộ khách riêng, không phải split LLBO) | — | Bench đo đúng thứ API trả về |
| Ceiling: tỉ lệ khách mà đáp án còn trong tập ứng viên sau lọc | 0,988 | 0,918 | Bộ lọc gần như không chặn nhầm đáp án |
| Mốc hồi quy `baseline_v1` (`frozen/baseline_v1-{llbo,temporal}-asof20260924.json`): ảnh chụp top-20 của engine v5 cho từng khách | PASS | PASS | Sau mọi thay đổi code recommendation phải chạy `make recsys-regress`. Nếu danh sách đổi có chủ đích thì đề xuất phải được chốt rồi mới ghi mốc mới |

---

## 3. Kết quả — mỗi mục một phát hiện

### 3.1 Bức tranh chung: từ sàn tới trần

Chế độ `funnel`, không MMR trừ dòng engine.

| Mốc | LLBO Hit@20 | LLBO NDCG@10 | Temporal Hit@20 | Temporal NDCG@10 |
|---|---:|---:|---:|---:|
| Random | 0,0066 | 0,0018 | 0,0034 | 0,0034 |
| MostPop | 0,2530 | 0,0769 | 0,0408 | 0,0031 |
| mpd (bán chạy trong điểm đến) | 0,6024 | 0,3803 | 0,1020 | 0,0376 |
| Engine (Content-based + MMR, chưa áp luật tối đa 2 món/loại) | 0,8484 | 0,5169 | 0,1939 | 0,1505 |
| Content-based không MMR | 0,8750 | 0,5462 | 0,1939 | 0,1581 |
| **Trần (ceiling)** | 0,988 | — | 0,918 | — |

Đọc bảng:

- Engine (chế độ đánh giá, chưa cap) hơn mpd **+24,6 điểm** Hit@20 trên LLBO và **+9,2 điểm** trên temporal, CI đều không chứa 0. Danh sách
  production thật (`engine_prod`, có cap) chỉ hơn mpd +1,7 và +3,1 điểm Hit@20, CI chứa 0 (mục 3.8).
- Khoảng trống tới trần còn **14 điểm** trên LLBO và **72 điểm** trên temporal. Ở temporal, đáp án nằm trong tập ứng viên nhưng bị xếp
  dưới hạng 20 — đây là chỗ cần cải thiện nhất.
- Temporal thấp hơn LLBO nhiều vì đoán "chuyến kế tiếp" khó hơn đoán "món tiếp theo của chuyến đang đi".

### 3.2 Phát hiện 1 — "Vua" là Content-based: không thắng mọi ô, nhưng không ai thắng nó trên temporal

Content-based đọc **nội dung** sản phẩm qua vector Cohere sinh từ văn bản mô tả sản phẩm. Nó trộn vector của các món khách đã xem, bỏ giỏ, mua
(món mua nặng ký hơn, món gần đây nặng ký hơn) thành một vector "khẩu vị", rồi tìm món gần khẩu vị nhất. Phần cá nhân hoá không cần biết
người khác mua gì; người khác chỉ góp vào qua một vế độ phổ biến nhỏ.

**Bảng 3.2a — điểm từng thuật toán** (funnel, không MMR; iALS, BPR-MF, BPR-MF (numpy), BPR-MF-Dest là trung bình 3 lần chạy với 3 hạt giống
ngẫu nhiên; in đậm = cao nhất cột)

| Thuật toán | LLBO Hit@20 | LLBO NDCG@10 | Temporal Hit@20 | Temporal NDCG@10 |
|---|---:|---:|---:|---:|
| **Content-based** | 0,8750 | 0,5462 | **0,1939** | **0,1581** |
| STAR | 0,8957 | 0,5344 | **0,1939** | 0,1043 |
| BPR-MF-Dest (Tier 2) | **0,8986** | 0,5638 | 0,0850 | 0,0210 |
| iALS | 0,8346 | **0,6053** | 0,0884 | 0,0232 |
| mpd + bộ lọc | 0,8199 | 0,4823 | 0,1020 | 0,0243 |
| Item-based CF | 0,8199 | 0,4660 | 0,1122 | 0,0284 |
| ItemKNN | 0,8199 | 0,4658 | 0,1122 | 0,0284 |
| RP3beta (Tier 2) | 0,8199 | 0,4640 | 0,1122 | 0,0270 |
| EASE | 0,8110 | 0,4657 | 0,1020 | 0,0278 |
| BPR-MF | 0,7169 | 0,3333 | 0,0850 | 0,0192 |
| BPR-MF (numpy, Tier 2) | 0,7119 | 0,3272 | 0,0918 | 0,0186 |

**Bảng 3.2b — chênh so với Content-based** (điểm phần trăm, `*` = CI95 không chứa 0). iALS, BPR-MF, BPR-MF-Dest có yếu tố ngẫu nhiên khi
học. Để so cặp từng khách, bảng này dùng một lần chạy với hạt giống ngẫu nhiên 42, nên chênh lệch có thể khác hiệu hai số trung bình ở bảng
3.2a (ví dụ BPR-MF: −19,8 ở đây, −15,8 nếu trừ hai số ở bảng 3.2a).

| Thuật toán | LLBO ΔHit@20 | LLBO ΔNDCG@10 | Temporal ΔHit@20 | Temporal ΔNDCG@10 |
|---|---|---|---|---|
| STAR | +2,1 [+1,3; +3,0] * | −1,2 [−2,0; −0,4] * | +0,0 [+0,0; +0,0] | −5,4 [−8,2; −2,7] * |
| BPR-MF-Dest | +2,3 [+0,0; +4,5] | +1,7 [−0,5; +3,9] | −10,2 [−16,3; −5,1] * | −13,9 [−20,5; −7,8] * |
| iALS | −3,0 [−5,6; −0,3] * | +6,7 [+3,6; +10,0] * | −10,2 [−17,3; −4,1] * | −13,4 [−20,2; −7,3] * |
| mpd + bộ lọc | −5,5 [−7,7; −3,4] * | −6,4 [−8,1; −4,7] * | −9,2 [−16,3; −3,1] * | −13,4 [−19,8; −7,5] * |
| Item-based CF | −5,5 [−7,7; −3,3] * | −8,0 [−9,9; −6,1] * | −8,2 [−14,3; −2,0] * | −13,0 [−19,5; −7,2] * |
| ItemKNN | −5,5 [−7,7; −3,3] * | −8,0 [−9,9; −6,2] * | −8,2 [−14,3; −2,0] * | −13,0 [−19,5; −7,2] * |
| RP3beta | −5,5 [−7,7; −3,3] * | −8,2 [−10,1; −6,4] * | −8,2 [−14,3; −2,0] * | −13,1 [−19,6; −7,3] * |
| EASE | −6,4 [−8,7; −4,1] * | −8,0 [−10,0; −6,1] * | −9,2 [−16,3; −3,1] * | −13,0 [−19,6; −7,2] * |
| BPR-MF | −19,8 [−22,8; −16,6] * | −24,9 [−27,6; −22,0] * | −10,2 [−18,4; −2,0] * | −13,5 [−20,7; −6,7] * |

**Bảng 3.2c — độ phủ và độ dồn** (funnel, không MMR; iALS, BPR-MF-Dest trung bình 3 lần chạy)

| Thuật toán | LLBO Coverage | LLBO Gini | Temporal Coverage | Temporal Gini |
|---|---:|---:|---:|---:|
| Content-based | 0,564 | 0,822 | 0,342 | 0,820 |
| STAR | 0,538 | 0,827 | 0,249 | 0,904 |
| iALS | 0,473 | 0,844 | 0,341 | 0,773 |
| mpd + bộ lọc | 0,409 | 0,864 | 0,126 | 0,970 |
| BPR-MF-Dest | 0,275 | 0,888 | 0,137 | 0,967 |
| mpd | 0,400 | 0,819 | 0,133 | 0,921 |

Đọc bảng:

- **Trên temporal, không thuật toán nào thắng Content-based** ở cả hai chỉ số. Mọi thuật toán CF và MF thua 8–10 điểm Hit@20, CI không chứa 0.
- **Trên LLBO có ba ngoại lệ, cả ba đều không lặp lại trên temporal:**
  - STAR nhỉnh +2,1 điểm Hit@20 nhưng đẩy đáp án xuống thấp hơn (NDCG −1,2), và trên temporal mất 5,4 điểm NDCG.
  - iALS thắng +6,7 điểm NDCG@10 nhờ tín hiệu giỏ hàng (mục 3.5), nhưng trên temporal thua 10,2 điểm Hit@20 và 13,4 điểm NDCG@10.
  - BPR-MF-Dest nhỉnh +2,3 điểm nhưng CI chạm 0, trên temporal thua 10,2 điểm.
- **Content-based phủ nhiều sản phẩm nhất** trong các thuật toán (trên temporal ngang iALS), gấp đôi BPR-MF-Dest. Điểm +2,3 của BPR-MF-Dest trên LLBO
  đi kèm độ phủ chỉ 0,275: mẫu "món khách không mua" trong cùng điểm đến gồm cả món chưa ai tương tác, nên mô hình học thêm "phổ biến trong
  điểm đến" (AUC train 0,90).
- Gini của engine (0,834) vẫn ngang mpd (0,819): engine chạm nhiều món hơn, nhưng lượt hiển thị vẫn dồn vào ít món.
- Vì vậy "Content-based luôn đứng đầu" là nói quá. Nói đúng là: **không thuật toán nào thắng Content-based trên temporal** (cách chia ưu tiên khi so
  thuật toán). Trên LLBO, Content-based chỉ bị vượt ở một chỉ số (STAR ở Hit@20, iALS ở NDCG@10), và cả hai lợi thế đó không lặp lại trên
  temporal.

### 3.3 Phát hiện 2 — Bộ lọc cứng là "cỗ tăng năng suất" khi khách đang có chuyến mở

**Bảng 3.3a — có lọc và không lọc** (Hit@20, không MMR)

| Thuật toán | LLBO raw | LLBO funnel | Δ LLBO | Temporal raw | Temporal funnel | Δ Temporal |
|---|---:|---:|---:|---:|---:|---:|
| Content-based | 0,4331 | 0,8750 | **+44,2** | 0,1837 | 0,1939 | +1,0 |
| STAR | 0,5482 | 0,8957 | +34,8 | 0,1837 | 0,1939 | +1,0 |
| mpd + bộ lọc | 0,6043 | 0,8199 | +21,6 | 0,0816 | 0,1020 | +2,0 |
| iALS | 0,5043 | 0,8346 | +33,0 | 0,0510 | 0,0884 | +3,7 |

**Bảng 3.3b — vì sao Content-based cần bộ lọc** (chế độ raw, LLBO; cột "Cross-cat có mua" = tỉ lệ gợi ý thuộc loại khách **chưa** mua trong chuyến)

| Thuật toán | Hit@20 raw | Cross-cat có mua |
|---|---:|---:|
| Random | 0,0066 | 0,233 |
| Content-based | 0,4331 | **0,083** |
| STAR | 0,5482 | 0,130 |
| mpd + bộ lọc | 0,6043 | 0,313 |

Đọc bảng:

- **Content-based một mình gợi "thêm món giống món đã mua".** Khi không lọc, chỉ 8,3 % gợi ý của Content-based thuộc loại khách chưa mua trong chuyến
  (92 % còn lại trùng loại đã mua). Tỉ lệ này thấp hơn cả bốc ngẫu nhiên (23,3 %). Khách vừa đặt khách sạn Nha Trang thì Content-based gợi thêm khách
  sạn Nha Trang.
- **Bộ lọc biến "giống" thành "bổ sung".** Bỏ loại đã mua và khoá điểm đến của chuyến, Content-based nhảy từ 0,433 lên 0,875. Không lọc, Content-based
  còn thua cả mpd (0,433 so với 0,602; −16,9 [−20,1; −13,8] *).
- **Bộ lọc không chặn nhầm.** Ceiling 0,988 trên LLBO: 98,8 % đáp án vẫn nằm trong tập ứng viên sau lọc.
- **Trên temporal bộ lọc gần như không tác dụng** (+1,0 điểm) vì 73/98 khách không có chuyến đang mở, nên tập ứng viên gần bằng toàn
  catalog.
- Kết luận: với khách đang có chuyến mở (LLBO), phần lớn khoảng cách giữa engine và mpd nằm ở **luật nghiệp vụ FR-REC-02** (loại theo chuyến):
  mpd + bộ lọc hơn mpd 21,8 điểm trong tổng 27,3 điểm Content-based hơn mpd. Với khách không có chuyến mở (phần lớn temporal), bộ lọc gần như không
  tác dụng: mpd + bộ lọc ngang mpd (+0,0), còn Content-based hơn mpd 9,2 điểm nhờ thuật toán.

### 3.4 Phát hiện 3 — Lọc cộng tác ≈ bán chạy nhất

Ý tưởng của CF: khách A mua món B, khách C cũng mua món B và món D, vậy gợi D cho khách A. Muốn vậy cần nhiều khách mua chung món.

**Bảng 3.4a — CF so với mpd + bộ lọc** (ΔHit@20, funnel; `*` = CI không chứa 0)

| Thuật toán | LLBO | Temporal |
|---|---|---|
| Item-based CF | +0,0 [−0,4; +0,4] | +1,0 [+0,0; +3,1] |
| ItemKNN | +0,0 [−0,4; +0,4] | +1,0 [+0,0; +3,1] |
| RP3beta | +0,0 [−0,4; +0,4] | +1,0 [+0,0; +3,1] |
| EASE | −0,9 [−1,8; −0,1] * | +0,0 [−4,1; +4,1] |
| iALS (seed 42) | +2,6 [+0,0; +5,2] | −1,0 [−6,1; +3,1] |
| BPR-MF (seed 42) | −14,3 [−17,3; −11,3] * | −1,0 [−6,1; +4,1] |

**Bảng 3.4b — dữ liệu CF được học**

| | LLBO | Temporal |
|---|---:|---:|
| Sự kiện dùng để học | 5.966 | 5.562 |
| Bảng chuyến × món | 1.710 chuyến, 1.985 ô khác 0 | 1.444 chuyến, 2.400 ô khác 0 |
| Bảng khách × món | 1.486 khách, 2.468 ô khác 0 | 1.212 khách, 2.442 ô khác 0 |
| Món có ít nhất 1 "hàng xóm" (món khác từng mua cùng chuyến) | **10,3 %** | 23,8 % |
| Tỉ lệ món trong top-20 có điểm CF > 0 (Item-based CF) | **0,039** | 0,398 |

Đọc bảng:

- Ba thuật toán Item-based CF, ItemKNN, RP3beta **không khác** mpd + bộ lọc về Hit@20 trên cả hai split (CI chứa hoặc chạm 0). Cả ba cho
  cùng một con số 0,8199 trên LLBO, bằng đúng mpd + bộ lọc. EASE còn kém mpd + bộ lọc 0,9 điểm trên LLBO (CI không chứa 0), ngang trên
  temporal. Không thuật toán CF nào hơn mpd + bộ lọc về Hit@20 với CI không chứa 0.
- Lý do trên LLBO: chỉ 3,9 % món trong top-20 có điểm CF > 0. 96 % còn lại hoà điểm 0 và được xếp theo độ phổ biến — tức thành mpd + bộ lọc.
- Gốc rễ ở dữ liệu seed: chỉ đơn mua có mã chuyến (`eventGroupId`), sự kiện bỏ giỏ thì không. Vì vậy bảng "cùng chuyến" chỉ có đơn mua, rất
  thưa.
- Trên temporal, 40 % món có điểm CF nhưng vẫn không hơn popularity: món hay mua cùng chuyến **này** không đoán được món của chuyến **sau**.
- BPR-MF còn thua cả popularity trên LLBO (−14,3 điểm). Mô hình chưa hội tụ: bản tái lập BPR-MF (numpy) có AUC train ở vòng cuối chỉ khoảng
  0,52, gần đoán mò.

### 3.5 Phát hiện 4 — Lợi thế của iALS đến từ giỏ hàng, không từ "học cộng tác"

Ở LLBO, **441/1.016 khách (43 %)** đã có sẵn món đáp án trong lịch sử của chính mình trước khi mua, gần như toàn bộ (438 khách) vì đã bỏ món
đó vào giỏ. Đây không phải rò rỉ dữ liệu: sự kiện bỏ giỏ xảy ra trước thời điểm đoán. iALS và BPR-MF-Dest đọc thẳng bảng "khách × món" nên
thấy ngay ô giỏ hàng đó.

**Bảng 3.5 — tách theo "đáp án đã có sẵn trong lịch sử"** (nhãn `targetInOwnHistory`; LLBO, Hit@20; iALS lấy seed 42)

| Nhóm khách | n | Content-based | iALS | Δ iALS − Content-based | Δ BPR-MF-Dest − Content-based |
|---|---:|---:|---:|---|---|
| Đáp án đã có sẵn (chủ yếu trong giỏ) | 441 | 0,873 | **0,977** | +10,4 [+7,7; +13,4] * | +6,8 [+3,6; +10,0] * |
| Đáp án chưa từng xuất hiện | 575 | 0,877 | 0,744 | −13,2 [−17,2; −9,4] * | −1,2 [−4,3; +1,9] |

Đọc bảng:

- iALS thắng 10,4 điểm ở nhóm có giỏ và **thua 13,2 điểm** ở nhóm không có giỏ. Temporal chỉ có 2/98 khách thuộc nhóm có giỏ, nên ở
  temporal iALS thua.
- BPR-MF-Dest là thuật toán CF **đầu tiên** không thua Content-based ở nhóm không có giỏ (−1,2 [−4,3; +1,9], CI chứa 0). Đáng xem lại khi harness có
  split loại bỏ tín hiệu giỏ.
- **Hai hệ quả:**
  1. Số LLBO của các thuật toán đọc thẳng giỏ hàng (iALS, BPR-MF-Dest) bị đội lên nhờ tín hiệu giỏ. Số của Content-based thì không: 0,873 ở nhóm
     có giỏ, 0,877 ở nhóm không giỏ. Cần split biến thể bỏ tín hiệu giỏ để so công bằng (việc #2 tuần 4).
  2. Trên dữ liệu sinh, tín hiệu "đã bỏ giỏ, chưa mua" dự đoán được món sẽ mua (iALS 0,977 ở nhóm có giỏ). Việc #6 tuần 4 là **nghiên cứu**
     xem có nên khai thác nó không, ví dụ nhắc lại món còn trong giỏ; nếu có ích thì soạn đề xuất PRD để Lead quyết. Đây chưa phải quyết
     định đổi engine.

### 3.6 Phát hiện 5 — Mạnh ở khách mới, trong chuyến thì bộ lọc làm phần chính, yếu ở chuyến kế tiếp

**Bảng 3.6a — khách mới** (cold start = dưới 3 sự kiện dùng được; Hit@20, funnel; iALS lấy seed 42)

| Split | Nhóm | n | Content-based | mpd | mpd + bộ lọc | iALS | Δ Content-based − mpd |
|---|---|---:|---:|---:|---:|---:|---|
| LLBO | Cold start | 338 | 0,867 | 0,657 | 0,870 | 0,781 | +21,0 [+16,6; +25,7] * |
| LLBO | Có lịch sử | 678 | 0,879 | 0,575 | 0,795 | 0,878 | +30,4 [+26,7; +34,1] * |
| Temporal | Cold start | 24 | **0,500** | 0,167 | 0,250 | 0,250 | **+33,3 [+16,7; +54,2] *** |
| Temporal | Có lịch sử | 74 | 0,095 | 0,081 | 0,054 | 0,041 | +1,4 [−2,7; +6,8] |

**Bảng 3.6b — 19 khách temporal mà Content-based đoán trúng đến từ đâu** (Hit@20 theo chiến lược engine chọn; n < 20 là nhóm nhỏ, chỉ đọc hướng)

| Chiến lược engine | n | Hit@20 | Số khách trúng |
|---|---:|---:|---:|
| `cold_start_content` — có chuyến mở, ít sự kiện, chưa mua trong chuyến | 10 | 1,000 | 10 |
| `recent_activity` — có chuyến mở, chưa mua trong chuyến, đủ sự kiện | 6 | 0,833 | 5 |
| `cross_vertical` — đang trong chuyến, đã mua 1 loại | 9 | 0,111 | 1 |
| `dormant` — lâu không quay lại | 16 | 0,062 | 1 |
| `long_term` — có lịch sử, không có chuyến mở | 57 | 0,035 | 2 |

**Bảng 3.6c — LLBO theo chiến lược engine** (Hit@20, funnel, không MMR; iALS lấy seed 42)

| Chiến lược engine | n | Content-based | mpd + bộ lọc | mpd | STAR | iALS | Δ Content-based − mpd |
|---|---:|---:|---:|---:|---:|---:|---|
| `cross_vertical` — đang trong chuyến, đã mua ≥ 1 loại | 923 | 0,872 | 0,870 | 0,634 | 0,894 | 0,878 | +23,8 [+20,9; +26,7] * |
| `recent_activity` — chuyến đang mở chưa mua gì | 93 | 0,903 | 0,323 | 0,290 | 0,914 | 0,527 | +61,3 [+49,5; +72,0] * |

Đọc bảng:

- Content-based thắng popularity **rõ nhất ở khách mới**: +33,3 điểm trên temporal. Nhưng 10/12 khách trúng thuộc chiến lược `cold_start_content`
  (trúng 10/10, NDCG@10 0,963: đáp án gần như luôn ở hạng 1). Seed chỉ gắn mã chuyến cho đơn mua, nên chuyến mở của nhóm này là một lượt xem
  hoặc bỏ giỏ lẻ ngay trước lúc mua, và nhiều khả năng engine gợi lại đúng món đó. Đây là mẫu "xem rồi mua" do seed tạo ra, phản ánh cấu trúc
  dữ liệu sinh hơn là chất lượng xếp hạng. Chưa nên coi đây là thế mạnh của thuật toán.
- Trên LLBO, Content-based ở nhóm cold start **ngang** mpd + bộ lọc (0,867 so với 0,870): khi bộ lọc đã khoá điểm đến, món bán chạy trong điểm đến
  đã là lựa chọn tốt.
- Ở 923 khách đã mua ít nhất một món trong chuyến, Content-based cũng chỉ **ngang** mpd + bộ lọc (0,872 so với 0,870). Với nhóm này, sức mạnh đến từ
  bộ lọc, không từ thuật toán.
- Trên toàn LLBO, Content-based hơn mpd + bộ lọc 5,5 điểm (889 so với 833 khách trúng). Khoảng 5,3 điểm trong đó đến từ 93 khách `recent_activity`
  (84 so với 30 khách trúng). Nhóm này phản ánh cấu trúc seed (mục 7), nên không đọc là ưu thế chung của Content-based.
- **Điểm yếu:** 57 khách `long_term` — có lịch sử nhưng không có chuyến mở — Content-based chỉ trúng 2 khách, bằng đúng mpd (0,035). Gợi ý cho
  chuyến kế tiếp hiện **không hơn** "bán chạy trong điểm đến". Đây là phần lớn khoảng trống 72 điểm tới trần ở mục 3.1.

### 3.7 Phát hiện 6 — MMR có giá khoảng 3 điểm, đổi lấy danh sách đa dạng hơn

MMR sắp lại danh sách để 10 món đầu không phải 10 khách sạn giống hệt nhau. Engine bật MMR với λ = 0,7 theo hợp đồng search–rec §4.7.

**Bảng 3.7 — Content-based không MMR so với có MMR (= arm `engine`: engine ở chế độ đánh giá, chưa áp cap 2 món/loại)**

| Chỉ số | LLBO không MMR | LLBO có MMR | Δ LLBO [CI95] | Temporal không MMR | Temporal có MMR | Δ Temporal [CI95] |
|---|---:|---:|---|---:|---:|---|
| Hit@5 | 0,6742 | 0,6398 | −3,4 [−5,4; −1,5] * | 0,1735 | 0,1735 | +0,0 [+0,0; +0,0] |
| Hit@20 | 0,8750 | 0,8484 | −2,7 [−4,3; −1,0] * | 0,1939 | 0,1939 | +0,0 [−3,1; +3,1] |
| NDCG@10 | 0,5462 | 0,5169 | −2,9 [−3,8; −2,1] * | 0,1581 | 0,1505 | −0,8 [−1,7; −0,1] * |
| Diversity@10 | 0,532 | 0,560 | | 0,449 | 0,629 | |

Đọc bảng:

- MMR tốn **2,7 điểm** Hit@20 trên LLBO (0,875 xuống 0,848), đổi lấy Diversity@10 tăng từ 0,532 lên 0,560. Trên temporal, Hit@20 không đổi,
  NDCG giảm 0,8 điểm.
- Với STAR, MMR tốn 4,7 điểm Hit@20 trên LLBO.
- **Không bỏ MMR vội.** Độ đa dạng là yêu cầu của hợp đồng search–rec §4.7 và là một độ đo ở `docs/prd/test-plan.md` §2.5: không có nó, top-5
  hay là 5 biến thể của cùng một resort. Bench offline chỉ đo "có trúng món khách mua", không đo được giá trị của việc cho khách thấy nhiều
  lựa chọn. Việc đúng là **dò λ** (0,7 / 0,85 / 1,0; λ = 1,0 tương đương tắt MMR) trên temporal ở tuần 4.

### 3.8 Phát hiện 7 — Luật "tối đa 2 món mỗi loại" là chỗ mất nhiều nhất của danh sách production

Danh sách khách thật nhìn thấy (`engine_prod`) có thêm một luật: tối đa 2 món mỗi loại sản phẩm (taxonomy). Hợp đồng search–rec §4.7 ghi
"tối đa 2 món mỗi **sản phẩm cha**" (`parentProductId`) — code đang làm khác hợp đồng (lệch I-5).

**Bảng 3.8a — engine (chế độ đánh giá) so với danh sách production**

| Chỉ số | LLBO engine | LLBO production | Temporal engine | Temporal production |
|---|---:|---:|---:|---:|
| Số món trả về (trung bình) | 16,3 | **5,3** | 19,7 | **7,4** |
| Hit@5 | 0,6398 | 0,5817 | 0,1735 | 0,1327 |
| NDCG@5 | 0,4843 | 0,4588 | 0,1505 | 0,1327 |
| Hit@20 | 0,8484 | 0,6191 | 0,1939 | 0,1327 |
| Coverage | 0,565 | 0,207 | 0,317 | 0,083 |

**Bảng 3.8b — production so với mpd** (Δ điểm phần trăm)

| Split | ΔHit@5 | ΔHit@20 | ΔNDCG@10 |
|---|---|---|---|
| LLBO | +9,8 [+7,0; +12,7] * | +1,7 [−1,1; +4,4] — **không khác** | +9,2 [+7,2; +11,2] * |
| Temporal | +8,2 [+1,0; +15,3] * | +3,1 [−3,1; +9,2] — **không khác** | +9,5 [+3,6; +16,0] * |

**Bảng 3.8c — mất ở loại sản phẩm nào** (LLBO, Hit@20 theo loại của đáp án)

| Loại đáp án | n | Engine | Production |
|---|---:|---:|---:|
| attraction | 330 | 0,845 | **0,500** |
| combo | 123 | 0,829 | **0,447** |
| flight | 433 | 0,827 | 0,679 |
| hotel | 80 | 0,912 | 0,812 |
| golf | 50 | 1,000 | 1,000 |

Đọc bảng:

- Luật cap cắt danh sách xuống còn khoảng 5 món. Hit@20 giảm 23 điểm, nhưng phần lớn là do danh sách ngắn hơn. **So công bằng ở cùng 5 món
  đầu**, cap tốn 5,8 điểm Hit@5 trên LLBO và 4,1 điểm trên temporal.
- Hệ quả đáng lo: ở Hit@20, danh sách production **không còn khác mpd** trên cả hai split (CI chứa 0), một phần vì production chỉ trả 5–7 món
  còn mpd trả 20. Ở 5 món đầu, đúng số món trang chủ hiển thị, production vẫn hơn mpd: Hit@5 +9,8 điểm trên LLBO và +8,2 điểm trên temporal,
  NDCG@10 +9,2 và +9,5 điểm, CI đều không chứa 0.
- Mất nhiều nhất ở attraction (0,845 → 0,500) và combo (0,829 → 0,447); hotel mất ít hơn (0,912 → 0,812), golf không mất. Report nguồn chưa
  đo nguyên nhân. Coverage production chỉ 0,083 trên temporal, dưới ngưỡng 20 % của lịch 10 ngày (mốc M5).
- Đổi luật cap sang theo sản phẩm cha là thay đổi hành vi production nên phải đi qua đề xuất PRD (việc #3 tuần 4).

### 3.9 Phát hiện 8 — Giải thích được gợi ý là điều kiện loại thẳng

FR-REC-03 yêu cầu mọi gợi ý cá nhân hoá có lý do (`because`), ví dụ "vì bạn vừa xem resort ở Phú Quốc".

**Bảng 3.9a — tỉ lệ món có lý do** (funnel, không MMR; iALS, BPR-MF trung bình 3 lần chạy; càng gần 1,000 càng tốt)

| Thuật toán | LLBO Because@5 | LLBO Because@20 | Temporal Because@5 |
|---|---:|---:|---:|
| Content-based | 1,000 | 1,000 | 1,000 |
| STAR | 1,000 | 1,000 | 1,000 |
| iALS | 0,938 | 0,617 | 0,880 |
| EASE | 0,194 | 0,068 | 0,771 |
| Item-based CF | 0,108 | 0,039 | 0,625 |
| BPR-MF | **0,000** | **0,000** | **0,000** |

**Bảng 3.9b — tỉ lệ khách vi phạm luật `because` của hợp đồng search–rec §4.4** (ràng buộc 2–4: khách mới và gợi ý phổ biến phải không có
lý do; khách lâu không quay lại phải có lý do từ sự kiện cũ hơn 90 ngày; càng thấp càng tốt)

| Thuật toán | LLBO | Temporal |
|---|---:|---:|
| Content-based | 0,333 | 0,245 |
| STAR | 0,333 | 0,245 |
| iALS | 0,327 | 0,133 |
| EASE | 0,096 | 0,163 |
| Item-based CF | 0,096 | 0,163 |
| BPR-MF | 0,000 | 0,163 |

Đọc bảng:

- Content-based và STAR có lý do cho **mọi** món ở mọi K. BPR-MF không giải thích được món nào (Because@K = 0), lại còn thua cả mpd + bộ lọc
  14,3 điểm Hit@20 trên LLBO, nên không đưa được vào production.
- Vi phạm của Content-based đúng bằng nhóm cold start (338/1.016 LLBO, 24/98 temporal). Engine vẫn sinh `because` cho khách có dưới 3 sự kiện,
  trái ràng buộc 4 của hợp đồng search–rec §4.4. Lệch này đã biết từ trước, nay có số đo; ghi cho Lead, chưa sửa engine trong tuần 3.
- BPR-MF bằng 0 ở LLBO chỉ vì nó không sinh lý do nào. Con số 0,163 ở temporal là 16 khách lâu không quay lại mà thiếu lý do cũ hơn 90 ngày.

### 3.10 Phát hiện 9 — Những thứ không tạo khác biệt, và một thay đổi có tác dụng

**Bảng 3.10a — grid lần 1 và tắt suy giảm: tham số nào đổi kết quả**

| Thử nghiệm | Split | Kết quả |
|---|---|---|
| Tắt suy giảm theo thời gian (`H_SHORT_DAYS`, `H_LONG_DAYS` = 10⁶ ngày) | LLBO, temporal 24/09 | Hit@20 đổi dưới 0,2 điểm |
| Đổi trọng số mua / bỏ giỏ / xem từ 1 / 0,5 / 0,2 thành 5 / 3 / 1 (`W_TYPE`) | temporal 22/09 | Không đổi |
| Sức nặng của một sự kiện giảm một nửa sau 60 ngày thay vì 30 (`H_SHORT_DAYS` = 60) | temporal 22/09 | Không đổi |
| Coi khách là "lâu không quay lại" sau 90 ngày thay vì 180 (`DORMANT_AFTER_DAYS` = 90) | temporal 22/09 | Không đổi |
| MMR λ = 0,85 / 1,0 thay vì 0,7 | temporal 22/09 | NDCG@10 −0,6 / −0,8 điểm |
| Khẩu vị gần đây / độ phổ biến = 0,7 / 0,15 thay vì 0,6 / 0,25 (`W_SHORT`, `W_POP`) | temporal 22/09 | NDCG@10 +0,6 điểm; NDCG@5 production +2,6 điểm |
| Khẩu vị gần đây / độ phổ biến = 0,5 / 0,35 | temporal 22/09 | NDCG@10 −4,6 điểm |

Grid lần 1 chạy trên split temporal 22/09 (102 khách) với engine v3. Chênh 1–3 khách nên chỉ là hướng dò, chưa phải quyết định.

**Bảng 3.10b — thay đổi đã áp dụng trong tuần: luật "chuyến đang mở" theo FR-REC-02** (split 22/09, chốt 02/10)

| Phiên bản engine | Temporal Hit@20 | Temporal NDCG@10 | Temporal ceiling | LLBO Hit@20 |
|---|---:|---:|---:|---:|
| v3 — chuyến mở nếu sự kiện gần nhất trong 60 ngày | 0,1961 | 0,1438 | 0,784 | 0,8510 |
| v5 — chuyến mở theo ngày sử dụng; chuyến chưa có ngày sử dụng mở 14 ngày | **0,2157** | **0,1542** | **0,892** | 0,8510 |

Đọc bảng:

- Suy giảm thời gian và trọng số loại sự kiện **không đáng dò** trên dữ liệu này: bỏ `H_*` khỏi grid tuần 4.
- Hướng duy nhất có tín hiệu là cân bằng giữa "khẩu vị gần đây" (`W_SHORT`) và "độ phổ biến" (`W_POP`) — vào grid tuần 4.
- Thay đổi có tác dụng nhất trong tuần là **sửa luật nghiệp vụ**, không phải chỉnh thuật toán: ceiling temporal tăng từ 0,784 lên 0,892.

### 3.11 Tốc độ

| Đo | Kết quả | So với NFR-PERF-01 (p95 ≤ 250 ms) |
|---|---|---|
| Thời gian train mọi thuật toán Tier 1 | Khoảng 1 giây trở xuống (chậm nhất là EASE, 0,9–1,1 s) | Không phải nút thắt |
| Thời gian train BPR-MF (numpy), BPR-MF-Dest | Khoảng 5–6 giây | Không phải nút thắt |
| HTTP local, 60 khách mẫu (14 khách chưa có sự kiện), máy rảnh, 01/10 | p50 93 ms · p95 134 ms (24/09: p50 127 · p95 143) | Đạt |
| Cloud, khách vãng lai, thời gian server (01/10) | p50 9 ms · p95 10 ms | Đạt |
| Cloud, khách vãng lai, thời gian phía client (01/10) | p50 141 ms · p95 391 ms | Gồm mạng, BFF, TLS — không phải engine |

Chưa đo được đường có đăng nhập trên cloud: `/internal/recommendations` cần IAP và `X-Service-Token`, đang chờ ops mở.

### 3.12 Kết luận nào vững qua cả hai cách chia

| Kết luận | LLBO | Temporal | Vững? |
|---|---|---|---|
| Engine (chế độ đánh giá) hơn mpd | +24,6 điểm * | +9,2 điểm * | **Vững** |
| Không thuật toán nào hơn Content-based | 3 ngoại lệ, mỗi cái ở một chỉ số | Không ai thắng | **Vững trên temporal** (cách chia ưu tiên) |
| CF ≈ popularity (Hit@20) | Item-based CF, ItemKNN, RP3beta CI chứa 0; iALS CI chạm 0; EASE −0,9 *, BPR-MF −14,3 * (thua) | CI chứa 0 hoặc chạm 0 | **Vững** — không thuật toán CF nào hơn popularity về Hit@20 |
| Content-based thắng ở khách mới | Hơn mpd, ngang mpd + bộ lọc | +33,3 điểm *, phần lớn do mẫu "xem rồi mua" của seed | Vững so với mpd |
| Content-based hơn mpd + bộ lọc khi khách đã mua trong chuyến | Ngang (0,872 so với 0,870) | Ngang (0,111 so với 0,111; 9 khách, ồn) | **Không** — bộ lọc làm phần chính |
| MMR tốn điểm | −2,7 * | +0,0 Hit@20; −0,8 NDCG * | Vững về hướng, nhỏ |
| Cap 2 món/loại làm production không hơn mpd ở Hit@20 | CI chứa 0; Hit@5 vẫn hơn * | CI chứa 0; Hit@5 vẫn hơn * | **Vững** |
| iALS / BPR-MF-Dest hơn Content-based | iALS: NDCG@10 +6,7 *; BPR-MF-Dest: Hit@20 +2,3 nhưng CI chạm 0 | Thua 10,2 điểm * | **Không vững**: do tín hiệu giỏ và bất đối xứng thời gian của LLBO |
| Bộ lọc đóng góp lớn | +44,2 | +1,0 | Chỉ khi khách có chuyến mở |

---

## 4. Quyết định

| # | Quyết định | Bằng chứng | Trạng thái |
|---|---|---|---|
| D1 | **Thuật toán lõi: Content-based** (engine v5, tên trong code `content_profile`) | Mục 3.2, 3.6, 3.9: không thuật toán nào thắng nó trên temporal; ba thuật toán nhỉnh hơn trên LLBO đều thua trên temporal; hơn mpd rõ nhất ở khách mới (+33,3 điểm temporal); giải thích được 100 % | Đã xác nhận ở ADR 2, 02/10 |
| D2 | Không đưa CF, MF vào engine (Item-based CF, ItemKNN, EASE, RP3beta, iALS, BPR-MF) | Mục 3.4, 3.5: không hơn popularity; lợi thế của iALS đến từ giỏ hàng | Đã xác nhận |
| D3 | STAR không vào engine; chỉ dò a = 0,8 / 0,9, ưu tiên thấp | Mục 3.2: NDCG −1,2 LLBO, −5,4 temporal | Đã xác nhận |
| D4 | BPR-MF-Dest chưa vào grid; xem lại khi có split không có tín hiệu giỏ | Mục 3.5: không thua ở nhóm không giỏ trên LLBO, thua 10,2 điểm trên temporal | Đã xác nhận |
| D5 | Dò λ MMR ∈ {0,7; 0,85; 1,0} trên temporal (λ = 1,0 tương đương tắt MMR); λ hiện hành 0,7 theo hợp đồng §4.7 | Mục 3.7: MMR tốn khoảng 3 điểm, đổi lấy danh sách đa dạng hơn | Đã xác nhận (việc #5 của ADR 2) |
| D6 | Không chạy mô hình sâu (two-tower, SASRec, LightGCN, Mult-VAE) | Mục 3.4: dữ liệu dưới sàn; CF đơn giản còn chưa hơn popularity | Đã xác nhận |
| D7 | Bỏ `H_SHORT_DAYS`, `H_LONG_DAYS` khỏi grid | Mục 3.10: tắt hẳn suy giảm chỉ đổi dưới 0,2 điểm | Đã xác nhận |
| D8 | **Model embedding:** recsys tiếp tục dùng vector đang có (Cohere v3, 1024 chiều). Bench recsys tuần 3 chưa đo vector nào khác | Search bench đưa Cohere v4-512 và v4-1024 vào shortlist, nhưng quyết định model và số chiều chưa chốt | Chờ quyết định model của track search. Nếu đổi model thì phải chạy lại bench recsys và so với `baseline_v1` trước khi deploy |

---

## 5. Lệch đã đo được giữa code, hợp đồng và PRD

Các lệch này đều đổi hành vi production. Theo quy trình của repo, mỗi lệch phải có đề xuất trong `docs/prd/update/` được chốt trước khi sửa
code.

| Mã | Lệch | Số đo | Việc |
|---|---|---|---|
| I-5 | Cap 2 món mỗi **loại** (code) so với 2 món mỗi **sản phẩm cha** (hợp đồng §4.7) | Production không hơn mpd ở Hit@20; tốn 5,8 điểm Hit@5 LLBO | Đề xuất PRD — việc #3 |
| I-8 | Ngưỡng "lâu không quay lại" 90 ngày (hợp đồng) so với 180 ngày (code) | Nhóm `dormant` temporal chỉ 16 khách, chưa đủ để kết luận | Đề xuất PRD — việc #9 |
| Ràng buộc 4 | Khách cold start vẫn nhận `because` | 33 % khách LLBO, 24 % khách temporal | Ghi cho Lead |
| `tripFactor` | Hợp đồng §4.3 có hệ số 0,2 cho chuyến đã kết thúc, engine chưa có | Chưa đo | Ghi tồn đọng |

---

### 6.3 Rủi ro cần theo dõi

- Grid trên temporal 98 khách: chênh 1–3 khách là nhiễu, kết quả grid chỉ là hướng dò. Theo quy ước B10, không chọn tham số theo LLBO. Muốn
  áp dụng một giá trị vào engine thì phải chạy lại LLBO và đi qua đề xuất PRD (M6), như spec bench §4.13.
- Nếu track search chốt đổi model embedding, mọi số ở báo cáo này phải đo lại (D8).
- Chưa đo latency đường có đăng nhập trên cloud.

---

## 7. Giới hạn của nghiên cứu

- **Dữ liệu sinh.** Hành vi khách do seed tạo ra; nhóm `recent_activity` LLBO đạt 0,892 (engine) và nhóm `cold_start_content` temporal trúng
  10/10 phản ánh cấu trúc seed hơn là hành vi thật.
- **Temporal nhỏ và lệch.** 98 khách, 95 % đáp án (93/98) là khách sạn, mọi nhóm con dưới 20 khách chỉ đọc hướng.
- **LLBO bất đối xứng thời gian.** Bảng CF học trên sự kiện của khách khác xảy ra sau thời điểm đoán (2.408/5.966 sự kiện sau trung vị thời
  điểm đoán), trong khi độ phổ biến của engine cắt đúng thời điểm. Đây là lý do ưu tiên temporal khi so thuật toán.
- **Split temporal hỏi "mua gì sau T", không hỏi "gợi gì ngay trước lúc mua chuyến kế".** 8 khách temporal có đáp án ngoài tập ứng viên;
  7 trong số đó vì chuyến đang mở tại T chưa đi nên engine khoá điểm đến hoặc loại theo loại sản phẩm, 1 khách mua lại đúng món đã mua.
  Cần split "next trip" (việc #2).
- **Hit là lenient.** Với flight và hotel, bench chỉ đo trúng tuyến hoặc khách sạn cha, chưa đo được đúng chuyến, đúng phòng.
- **Bench offline không đo giá trị của sự đa dạng.** MMR luôn trông như "tốn điểm" trong bench.
- **Thời gian ms trong bảng offline** là thời gian xếp hạng trên máy dev, không thay số đo HTTP.
- **Bảng cùng chuyến chỉ có đơn mua** vì seed không gắn mã chuyến cho bỏ giỏ; CF trên dữ liệu thật có thể khá hơn.

---