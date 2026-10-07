# RecSys với vector e5-small và e5-base — engine v5 + baseline, bảng thuật toán, so hai model (05/10)

- Phục vụ: FR-REC-01..04, FR-SRC-02 (model embedding dùng chung Search + RecSys), NFR-PERF-01; `docs/prd/test-plan.md` §2.5.
  Plan: `docs/plan/2026-10-05-bench-recsys-e5-small.md` (Day 6 → Day 8; chạy sớm, xong trong ngày 05/10). Harness và cách đọc cột:
  `docs/spec/bench/recsys-offline-eval.md`; thuật toán: `docs/spec/bench/recsys-algos-v1.md`. Mẫu: `eval-2026-10-01-recsys-algos-v1.md`.
- Commit: `bench_search_recomSys @ 942f5aa` + thay đổi chưa commit (`git describe gold_v3-20-g942f5aa-dirty`): chế độ `--vectors npy:<prefix>`
  (`recsys_bench/data_source.py`), `vectorsSource` trong `summary.json`, sửa import `Protocol` ở `src/backend/app/application/ports/unit_index.py`
  (`history/2026-10-05-recsys-bench-npy-vectors.md`). **Engine không đổi:** `configHash b0aee886` ở mọi run.
- Chạy lúc: 2026-10-05 10:17–11:30 (+07), máy dev Linux 8 core, chạy tuần tự. Python 3.11.16 · numpy 2.4.6 · scipy 1.17.1 · implicit 0.7.3 ·
  threadpoolctl 3.7.0 (khác Day 5 trên Windows; chỉ ảnh hưởng `ials` / `bpr`, và hai model chạy cùng môi trường).
- DB: Postgres riêng cho bench (cổng 55433), seed từ worktree sạch `942f5aa`: snapshot `2026-09-23`, `AS_OF=2026-09-24`, `SEED=42`;
  `db/verify.sql` + `db/verify_insider.sql` PASS; 7.145 event → 6.993 sau lọc; 3.183 search unit / 2.384 recommendable.
- Vector (không embed lại, không Weaviate, kNN chính xác bằng `NumpyVectorSearch`): `bench_out/search/data/vec_T3+R_e5-{small,base}`,
  3.183 unit, text `catalog-text-v2`, `items_sha256 90e9ae51…`, `text_sha256 8439c4b3…`, chuẩn hoá L2.

| Model | `modelVersion` | Chiều | `npySha256` |
|---|---|---:|---|
| e5-small | `intfloat/multilingual-e5-small:catalog-text-v2` | 384 | `2395208d04e130e5…` |
| e5-base | `intfloat/multilingual-e5-base:catalog-text-v2` | 768 | `8d465e83ed2702b6…` |

- Split đóng băng: `frozen/split-llbo-asof20260924.json` (`1c31d43cfc28…`, 1.016 khách) · `frozen/split-temporal-asof20260924.json`
  (`49727f856865…`, 98 khách, T = 2026-07-10T09:13Z). Mọi run `frozenSha256` khớp, `vectorsMissing 0`.
- Phạm vi (plan): không dùng Cohere, không so với `baseline_v1` (baseline đó gắn vector Cohere), không grid ADR 2, không đổi production.

> **Caveat bắt buộc (handbook §12):** lịch sử khách là dữ liệu sinh — số đo cho biết pipeline và so sánh tương đối chạy đúng, không nói gì
> về khách thật. Temporal chỉ có 98 khách: 1 khách = 1,02 điểm hit@k; mọi Δ temporal đọc kèm CI.

## Đọc nhanh

1. **Engine dùng e5-small vượt baseline rõ ở cả hai split.** LLBO: hit@20 0,860 vs `most_popular_in_destination` 0,602, Δ **+25,8**
   [+22,9; +28,6]; NDCG@10 Δ **+12,6** [+11,2; +14,0]. Temporal: Δ hit@20 **+8,2** [+2,0; +15,3], NDCG@10 **+4,6** [+1,2; +8,1].
   Availability 1,000; coverage 0,523 (LLBO) — đạt tiêu chí M5 (lịch 10 ngày).
2. **e5-small không thua e5-base.** Engine LLBO: Δ hit@20 +0,2 [−0,9; +1,3], NDCG@10 +0,4 [−0,2; +0,9]; temporal hit@20 +1,0 [0,0; +3,1],
   NDCG@10 −0,4 [−1,0; +0,04]. Không phân khúc n ≥ 20 nào thua quá 1 điểm (tệ nhất −0,9, attraction LLBO). → **Giữ e5-small** theo quy tắc
   ghi trước (mục 2).
3. **Đường nạp vector đúng.** Gate trong run G1 / G2 / `star_blend_a1` 100 % ở 4 run gate; scorer CF (`itemknn`, `ease`, `ials`, `cooc_trip`,
   `rp3beta`) trùng ids **100 %** giữa run e5-small và e5-base — đổi vector chỉ đổi phần dùng vector.
4. **Kết luận bảng thuật toán Day 5 giữ nguyên với e5:** CF thuần ≈ `pop_funnel`; funnel đóng góp nhiều nhất (content LLBO funnel 0,871 vs raw
   0,596); không scorer nào thắng content trên temporal. Ceiling không đổi theo model (0,988 / 0,918).
5. **e5-small nhanh hơn ở engine offline:** p95 `engine` 106 vs 125 ms (LLBO), 182 vs 226 ms (temporal). Số offline trên máy dev, không thay
   số đo HTTP (mục 8).

## 0. Giải thích cho người đọc: đo cái gì, đo thế nào, số nghĩa là gì

### 0.1 Câu hỏi cần trả lời

Engine gợi ý (`/recommendations`) dùng **vector sản phẩm**: mỗi sản phẩm được model embedding biến thành một dãy số thể hiện ý nghĩa
của mô tả sản phẩm; hai sản phẩm có vector gần nhau là hai sản phẩm giống nhau. Engine dựng "sở thích" của khách từ vector các sản
phẩm khách đã xem / mua, rồi tìm sản phẩm gần sở thích đó. Nhóm đổi model tạo vector từ Cohere sang e5-small, nên phải kiểm:

1. Engine dùng vector e5-small có còn gợi ý tốt hơn các cách gợi ý đơn giản không?
2. e5-small (nhỏ, 384 số mỗi sản phẩm) có kém e5-base (lớn hơn, 768 số) không?

### 0.2 Đo thế nào — "giấu món đã mua rồi xem engine có đoán ra không"

Không có khách thật, nên dùng **lịch sử khách sinh** trong database seed (2.000 khách, 7.145 hành vi xem / thêm giỏ / mua / tìm kiếm
trong 2 năm, sinh cố định bằng `SEED=42`). Với mỗi khách:

1. **Giấu** một lần mua (gọi là *target*).
2. Đưa cho engine **chỉ phần lịch sử trước lúc mua đó**, như thể đang đứng ở thời điểm trước khi khách mua.
3. Engine trả về **20 sản phẩm** gợi ý.
4. Xem target có nằm trong 20 món đó không, và nằm ở vị trí thứ mấy.

Phòng khách sạn và chuyến bay được quy về sản phẩm cha (khách sạn, tuyến bay), vì engine gợi ý ở cấp đó. Làm cho mọi khách rồi lấy
trung bình.

**Ví dụ minh hoạ (không phải khách cụ thể trong dữ liệu).** Khách đã đặt khách sạn ở Nha Trang, sau đó mua vé VinWonders Nha Trang. Ta giấu vé VinWonders. Engine thấy khách
vừa đặt khách sạn Nha Trang nên gợi ý các món khác loại ở Nha Trang; vé VinWonders đứng thứ 3 → khách này **trúng** (tính vào
Recall@20), điểm NDCG@10 của khách = 1 / log₂(3 + 1) = **0,5**.

**Hai cách chọn món để giấu (hai "split"):**

| Split | Cách giấu | Số khách | Độ khó |
|---|---|---:|---|
| **LLBO** (leave-last-booking-out) | Mỗi khách có ≥ 2 lần mua: giấu **lần mua cuối** | 1.016 | Dễ hơn: món cuối thường là món tiếp theo trong **cùng chuyến** (đặt khách sạn rồi mua vé), đúng tình huống engine được thiết kế |
| **Temporal** | Cắt mọi khách ở **một mốc thời gian chung** (10/07/2026): chỉ thấy lịch sử trước mốc, target = món mua đầu tiên sau mốc | 98 | Khó hơn nhiều: thường là **chuyến mới**, nơi khác, sau nhiều tuần; giống thực tế "khách quay lại" |

Danh sách khách và món bị giấu của hai split đã **đóng băng** thành file (`frozen/split-*-asof20260924.json`, có mã sha256). Mỗi run tự kiểm
dữ liệu khớp file đó, nên e5-small và e5-base được chấm trên **đúng cùng một đề thi**.

**Đối thủ để so** (không dùng vector, không "thông minh"):

- `random`: chọn bừa 20 món, chạy 3 lần lấy trung bình — mức sàn.
- `most_popular`: 20 món bán chạy nhất toàn hệ thống.
- `most_popular_in_destination` (**mpd**): 20 món bán chạy nhất **tại điểm đến** khách đang quan tâm. Đây là đối thủ khó nhất và là
  mốc chính: nếu engine không hơn được nó thì không đáng dùng engine.

### 0.3 Các con số nghĩa là gì

| Chỉ số | Cách tính | Ví dụ đọc |
|---|---|---|
| **Recall@20** (= hit@20) | Tỉ lệ khách có target nằm trong 20 món gợi ý | 0,860 = 874 / 1.016 khách LLBO được gợi đúng món họ sẽ mua |
| **Recall@10, @5** | Như trên nhưng chỉ xét 10 / 5 món đầu | Danh sách trên trang chủ chỉ hiện 5 món nên @5 gần trải nghiệm thật hơn |
| **NDCG@10** | Thưởng theo vị trí: target đứng thứ r (r ≤ 10) được 1 / log₂(r + 1) — thứ 1 = 1,0; thứ 3 = 0,5; thứ 10 ≈ 0,29; ngoài top 10 = 0. Trung bình trên mọi khách | 0,506: trung bình target đứng khá cao; cùng Recall mà NDCG cao hơn nghĩa là món đúng được đẩy lên trên |
| **Coverage** | Tỉ lệ sản phẩm có thể gợi ý (2.384 món) xuất hiện ít nhất một lần trong gợi ý của mọi khách | 0,523 = hơn nửa catalog được gợi ở đâu đó; `most_popular` chỉ 0,069 vì ai cũng nhận cùng 20 món |
| **Gini** | Mức dồn: 0 = mọi món được gợi đều nhau, gần 1 = vài món chiếm hết | Đọc cùng Coverage |
| **Availability** | Tỉ lệ món được gợi đang mở bán theo catalog (cửa sổ đặt chỗ 30 ngày từ ngày nạp dữ liệu) | 1,000 = không gợi món hết chỗ |
| **Cross-cat chuyến mở, có mua** | Với khách đang có chuyến (đã đặt ≥ 1 món): tỉ lệ món gợi ý **khác loại** với món đã đặt trong chuyến | 1,000 = vừa đặt khách sạn thì engine chỉ gợi vé / tour / bay, không gợi thêm khách sạn (đúng FR-REC-02) |
| **p50 / p95 / p99 ms** | Thời gian engine xếp hạng cho một khách, đo trong tiến trình bench | Chỉ để so tương đối hai model; **không** phải độ trễ API |
| **Ceiling** | Tỉ lệ khách mà target còn nằm trong tập ứng viên sau khi engine áp luật lọc cứng (đã mua rồi, sai điểm đến, cùng loại với món đã đặt trong chuyến) | 0,988 = bộ lọc chỉ chặn 12 / 1.016 khách; nếu engine trượt thì do xếp hạng, không phải do lọc |

### 0.4 Chênh lệch và "khoảng tin cậy" (CI95)

So hai bên (engine với mpd, hoặc e5-small với e5-base) luôn **ghép theo từng khách**: cùng khách, cùng món bị giấu, chỉ khác bên gợi ý.
Chênh lệch ghi bằng **điểm phần trăm**: 0,860 so với 0,602 là +25,8 điểm.

Để biết chênh lệch đó là thật hay do may rủi, dùng **paired bootstrap**: rút ngẫu nhiên có lặp lại 1.016 khách (hoặc 98) từ chính danh sách
khách, tính lại chênh lệch, lặp 10.000 lần. 95 % kết quả nằm trong khoảng **CI95**:

- CI **không chứa 0** (ví dụ [+22,9; +28,6]) → chênh lệch chắc chắn, không phải may rủi.
- CI **chứa 0** (ví dụ [−0,9; +1,3]) → không phân biệt được hai bên → coi là **hoà**.
- Temporal chỉ 98 khách: mỗi khách = 1,02 điểm, nên chênh 1–3 điểm thường chỉ là 1–3 khách; luôn đọc kèm CI.

### 0.5 Các kiểm tra để tin được con số

- **Cùng đề thi:** mọi run kiểm mã sha256 của split đóng băng; database seed lại từ commit sạch với đúng ngày dữ liệu (`AS_OF=2026-09-24`).
- **Đủ vector:** `vectorsMissing 0` — cả 3.183 sản phẩm tìm kiếm đều có vector ở cả hai model.
- **Gate G1 / G2:** bench có hai đường tính engine (gọi engine trực tiếp, và dựng lại engine từ các khối của bảng thuật toán). Hai đường
  phải ra **y hệt** 20 món cho từng khách → 1016/1016 và 98/98, nghĩa là bench không tự sinh sai lệch.
- **Kiểm chéo:** các thuật toán **không dùng vector** (`itemknn`, `ease`, `ials`…) phải ra kết quả y hệt nhau dù chạy với e5-small hay
  e5-base → trùng 100 %, nghĩa là đổi model chỉ ảnh hưởng đúng phần dùng vector.
- **Không rò rỉ:** `leak 0` — món bị giấu không lọt vào dữ liệu huấn luyện của các thuật toán học từ dữ liệu.

### 0.6 Giới hạn — không được hiểu quá

- Khách là **dữ liệu sinh**: con số cho biết engine chạy đúng thiết kế và so sánh tương đối giữa các cách gợi ý, **không** dự đoán tỉ lệ
  trúng trên khách thật.
- Số LLBO cao một phần vì 441 / 1.016 khách đã **thêm đúng món đó vào giỏ** trước khi mua — engine thấy tín hiệu này.
- Không so với Cohere (phạm vi plan), nên không kết luận e5 "tốt hơn" hay "kém hơn" hệ thống đang chạy; chỉ kết luận e5-small đạt yêu cầu
  và ngang e5-base.
- Thời gian đo trên máy dev, tìm vector bằng cách quét toàn bộ trong RAM; production dùng Weaviate nên phải đo lại độ trễ API khi đổi model.

## 1. Gate và điều kiện công bố

| Kiểm tra | e5-small | e5-base |
|---|---|---|
| `frozenSha256` khớp, `vectorsMissing 0`, `configHash b0aee886` (16 run) | ✅ | ✅ |
| G1 `content_profile+mmr` ≡ `engine` (ids[:20]) — LLBO / temporal | 1016/1016 · 98/98 | 1016/1016 · 98/98 |
| G2 `content_profile` ≡ `engine_nommr[:20]` — LLBO / temporal | 1016/1016 · 98/98 | 1016/1016 · 98/98 |
| `star_blend_a1` ≡ `content_profile` (`expectations`, funnel + gate) | 100 % | 100 % |
| `expectFailed []`, leak `targetCellInTripRow 0` (8 run algos + gate) | ✅ | ✅ |
| Availability `engine` | 1,000 | 1,000 |

**Kiểm chéo phần không đổi theo vector (plan 7.4)** — `regress --run-id …-e5s --ref-run-id …-e5b --base X --ref X`, khớp thứ tự ids[:20]:

| Run | `itemknn` | `ease` | `ials-s42` | `cooc_trip` | `rp3beta` |
|---|---|---|---|---|---|
| LLBO funnel | 1016/1016 | 1016/1016 | 1016/1016 | 1016/1016 | 1016/1016 |
| LLBO raw | 1016/1016 | 1016/1016 | 1016/1016 | — | — |
| Temporal funnel | 98/98 | 98/98 | 98/98 | 98/98 | 98/98 |

## 2. Quy tắc đọc — ghi trong plan trước khi chạy

- Engine e5-small phải thắng `most_popular_in_destination` ở hit@20 và NDCG@10 trên LLBO với CI95 nằm hẳn trên 0; availability ≥ 95 %,
  coverage > 20 %. → **Đạt** (mục 3, 4).
- e5-small được giữ nếu `engine` không thua e5-base quá **1,0 điểm** hit@20 hoặc NDCG@10 với CI95 nằm hẳn dưới 0, và không phân khúc n ≥ 20
  thua quá **3,0 điểm** hit@20. → **Đạt**: không Δ nào âm có ý nghĩa ở engine; phân khúc tệ nhất −0,9 (mục 5, 6).
- Temporal: chênh 1–3 khách là nhiễu, chỉ đọc kèm CI. LLBO: 441/1.016 khách đã `add_to_cart` đúng target trước khi mua (spec §4.17) → số
  LLBO cao một phần vì tín hiệu này.

## 3. Engine + baseline (run `2026-10-05-{llbo,temporal}-v5-{e5s,e5b}`, k = 20)

| Split | Arm | Model | Recall@10 | Recall@20 | NDCG@10 | Coverage | Availability | Gini | Cross-cat chuyến mở, có mua | p50 ms | p95 ms | p99 ms |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LLBO | most_popular_in_destination | e5s | 0.549 | 0.602 | 0.380 | 0.400 | 1.000 | 0.819 | 0.400 | 7.4 | 13.1 | 49.8 |
| LLBO | most_popular_in_destination | e5b | 0.549 | 0.602 | 0.380 | 0.400 | 1.000 | 0.819 | 0.400 | 12.0 | 27.6 | 72.3 |
| LLBO | engine | e5s | 0.762 | 0.860 | 0.506 | 0.523 | 1.000 | 0.840 | 1.000 | 35.1 | 105.9 | 148.2 |
| LLBO | engine | e5b | 0.760 | 0.858 | 0.502 | 0.521 | 1.000 | 0.839 | 1.000 | 43.8 | 125.0 | 180.1 |
| LLBO | engine_nommr | e5s | 0.770 | 0.871 | 0.513 | 0.518 | 1.000 | 0.833 | 1.000 | 23.0 | 40.2 | 102.0 |
| LLBO | engine_nommr | e5b | 0.766 | 0.872 | 0.509 | 0.515 | 1.000 | 0.833 | 1.000 | 30.2 | 64.3 | 134.7 |
| Temporal | most_popular_in_destination | e5s | 0.092 | 0.102 | 0.038 | 0.133 | 1.000 | 0.921 | 0.350 | 0.2 | 0.8 | 1.0 |
| Temporal | most_popular_in_destination | e5b | 0.092 | 0.102 | 0.038 | 0.133 | 1.000 | 0.921 | 0.350 | 0.2 | 0.6 | 0.6 |
| Temporal | engine | e5s | 0.163 | 0.184 | 0.083 | 0.161 | 1.000 | 0.957 | 1.000 | 126.4 | 182.4 | 196.9 |
| Temporal | engine | e5b | 0.163 | 0.173 | 0.087 | 0.164 | 1.000 | 0.955 | 1.000 | 132.0 | 226.0 | 258.6 |
| Temporal | engine_nommr | e5s | 0.173 | 0.184 | 0.087 | 0.162 | 1.000 | 0.956 | 1.000 | 15.3 | 26.9 | 46.8 |
| Temporal | engine_nommr | e5b | 0.173 | 0.173 | 0.089 | 0.170 | 1.000 | 0.953 | 1.000 | 17.9 | 54.7 | 68.8 |

Baseline không dùng vector nên giống nhau giữa hai model (chỉ thời gian chạy khác). LLBO e5-small, các arm khác: `random` (3 seed) Recall@20
0,0066 ± 0,0023 · `most_popular` 0,2530. Temporal: `random` 0,0034 ± 0,0048 · `most_popular` 0,0408. Bảng đầy đủ mọi cột (Recall@5,
NDCG@5, diversity, cross-category…) nằm trong `summary.json` / `report` của từng run.

## 4. Engine so với baseline trong cùng run (`compare`, paired bootstrap 10.000 lượt, seed 42; Δ điểm phần trăm)

| Split | Model | Chỉ số | engine | mpd | Δ | CI95 | p một phía |
|---|---|---|---:|---:|---:|---|---:|
| LLBO | e5s | hit@20 | 0.8602 | 0.6024 | +25.79 | [+22.93; +28.64] | 0.0000 |
| LLBO | e5s | ndcg@10 | 0.5060 | 0.3803 | +12.57 | [+11.19; +13.98] | 0.0000 |
| LLBO | e5b | hit@20 | 0.8583 | 0.6024 | +25.59 | [+22.83; +28.54] | 0.0000 |
| LLBO | e5b | ndcg@10 | 0.5024 | 0.3803 | +12.21 | [+10.79; +13.62] | 0.0000 |
| Temporal | e5s | hit@20 | 0.1837 | 0.1020 | +8.16 | [+2.04; +15.31] | 0.0072 |
| Temporal | e5s | ndcg@10 | 0.0831 | 0.0376 | +4.55 | [+1.19; +8.12] | 0.0037 |
| Temporal | e5b | hit@20 | 0.1735 | 0.1020 | +7.14 | [+0.00; +14.29] | 0.0228 |
| Temporal | e5b | ndcg@10 | 0.0871 | 0.0376 | +4.94 | [+1.43; +8.69] | 0.0028 |

## 5. e5-small so với e5-base (plan 7.6; script phụ lục; Δ = e5s − e5b, điểm phần trăm)

| Split | Arm | Chỉ số | e5s | e5b | Δ | CI95 | p (e5s ≤ e5b) |
|---|---|---|---:|---:|---:|---|---:|
| LLBO | engine | hit@20 | 0.8602 | 0.8583 | +0.20 | [−0.89; +1.28] | 0.354 |
| LLBO | engine | ndcg@10 | 0.5060 | 0.5024 | +0.37 | [−0.19; +0.90] | 0.100 |
| LLBO | engine_nommr = content_profile = star_blend_a1 | hit@20 | 0.8711 | 0.8720 | −0.10 | [−1.28; +1.08] | 0.564 |
| LLBO | engine_nommr = content_profile = star_blend_a1 | ndcg@10 | 0.5134 | 0.5086 | +0.47 | [−0.07; +1.02] | 0.045 |
| LLBO | star_blend (a = 0,5) | hit@20 | 0.8789 | 0.8868 | −0.79 | [−1.97; +0.39] | 0.899 |
| LLBO | star_blend (a = 0,5) | ndcg@10 | 0.5087 | 0.5047 | +0.40 | [−0.19; +0.98] | 0.093 |
| Temporal | engine | hit@20 | 0.1837 | 0.1735 | +1.02 | [+0.00; +3.06] | 0.186 |
| Temporal | engine | ndcg@10 | 0.0831 | 0.0871 | −0.39 | [−0.96; +0.04] | 0.952 |
| Temporal | engine_nommr = content_profile | hit@20 | 0.1837 | 0.1735 | +1.02 | [+0.00; +3.06] | 0.186 |
| Temporal | engine_nommr = content_profile | ndcg@10 | 0.0868 | 0.0886 | −0.18 | [−0.51; +0.02] | 0.932 |
| Temporal | star_blend (a = 0,5) | hit@20 | 0.1735 | 0.1735 | +0.00 | [+0.00; +0.00] | 0.500 |
| Temporal | star_blend (a = 0,5) | ndcg@10 | 0.0664 | 0.0705 | −0.40 | [−1.10; −0.01] | 0.991 |

Đọc: mọi Δ của engine nằm trong ±1 điểm, CI chứa 0 → hoà. Δ hit@20 temporal +1,02 = đúng 1 khách. Δ NDCG@10 `star_blend` temporal −0,40 có
CI vừa chạm dưới 0 nhưng nhỏ hơn ngưỡng 1,0 điểm và `star_blend` không phải arm production.

## 6. Phân khúc — engine hit@20, e5-small so với e5-base (`analyze`, chỉ phân khúc n ≥ 20)

| Split | Phân khúc tệ nhất cho e5s | n | Δ hit@20 (e5s − e5b) | Phân khúc tốt nhất cho e5s | n | Δ |
|---|---|---:|---:|---|---:|---:|
| LLBO | targetTaxonomy = attraction | 330 | −0.91 | targetTaxonomy = flight | 433 | +1.39 |
| LLBO | targetTaxonomy = combo | 123 | −0.81 | coldStart = False | 678 | +0.59 |
| LLBO | coldStart = True | 338 | −0.59 | | | |
| Temporal | coldStart = True / active / long_term | 24 / 68 / 57 | 0.00 | coldStart = False | 74 | +1.35 |

Không phân khúc n ≥ 20 nào thua quá 3 điểm (ngưỡng plan). Bảng phân khúc đầy đủ (strategy, coldStart, lifecycle, taxonomy, trip, persona)
cho từng run: `bench_out/recsys/runs/2026-10-05-{split}-v5-{m}/segments.md`. Engine e5-small LLBO theo taxonomy target: flight 0,859 ·
attraction 0,836 · combo 0,837 · hotel 0,912 · golf 1,000; cold-start 0,858 (n = 338) ≈ khách có lịch sử 0,861.

## 7. Bảng thuật toán (run `…-algos-{funnel,raw}-{m}`, pool mask, `--max-tier 2`; `algosHash` funnel `9f92c041`, raw `dfce4eb7`)

Recall@20 / NDCG@10, rerank none (thêm hai dòng `+mmr` cho content và star_blend); p95 ms của run e5s / e5b. `ials`, `bpr` là mean 3 seed.

| Scorer | LLBO funnel R@20 e5s / e5b | NDCG@10 e5s / e5b | Temporal funnel R@20 e5s / e5b | NDCG@10 e5s / e5b | LLBO raw R@20 e5s / e5b | Temporal raw R@20 e5s / e5b |
|---|---|---|---|---|---|---|
| `content_profile` (= `engine_nommr`) | 0.871 / 0.872 | 0.513 / 0.509 | 0.184 / 0.173 | 0.087 / 0.089 | 0.596 / 0.594 | 0.173 / 0.163 |
| `content_profile+mmr` (= `engine`) | 0.860 / 0.858 | 0.506 / 0.502 | 0.184 / 0.173 | 0.083 / 0.087 | 0.598 / 0.599 | 0.173 / 0.163 |
| `star_blend` (a = 0,5) | 0.879 / 0.887 | 0.509 / 0.505 | 0.173 / 0.173 | 0.066 / 0.070 | 0.620 / 0.626 | 0.163 / 0.163 |
| `star_blend+mmr` | 0.865 / 0.860 | 0.500 / 0.498 | 0.173 / 0.173 | 0.064 / 0.061 | 0.623 / 0.627 | 0.173 / 0.163 |
| `pop_funnel` | 0.820 | 0.482 | 0.102 | 0.024 | 0.604 | 0.082 |
| `cooc_trip` | 0.820 | 0.466 | 0.112 | 0.028 | 0.610 | 0.092 |
| `itemknn` | 0.820 | 0.466 | 0.112 | 0.028 | 0.610 | 0.092 |
| `rp3beta` | 0.820 | 0.464 | 0.112 | 0.027 | 0.610 | 0.092 |
| `ease` | 0.811 | 0.466 | 0.102 | 0.028 | 0.602 | 0.082 |
| `ials` | 0.835 | 0.605 | 0.088 | 0.023 | 0.504 | 0.051 |
| `bpr` | 0.717 | 0.333 | 0.085 | 0.019 | 0.035 | 0.044 |
| `bpr_numpy` | 0.712 | 0.327 | 0.092 | 0.019 | 0.045 | 0.037 |
| `bpr_dest` | 0.899 | 0.564 | 0.085 | 0.021 | 0.319 | 0.048 |

Scorer không dùng vector cho cùng số ở hai model nên ghi một giá trị. Đọc giống report Day 5 (mục 4–9 của `eval-2026-10-01-recsys-algos-v1.md`):
`bpr_dest` / `ials` cao ở LLBO nhờ tín hiệu giỏ hàng (441 khách), kém hẳn trên temporal; `star_blend` không thắng content trên temporal.
Bảng nguyên văn mọi cột (coverage, Gini, collab cov., pool cắt, fit s) và mọi arm `+mmr`: `report` của từng run (lệnh ở mục 10).

## 8. Ceiling và tốc độ

| Split | Ceiling (target tới được mask engine) | Lý do không tới được |
|---|---|---|
| LLBO | 0,988 (1004/1016) — **cả hai model** | `already_bought` 10, `destination_mismatch` 2 |
| Temporal | 0,918 (90/98) — **cả hai model** | `taxonomy_excluded` 4, `destination_mismatch` 7 (3 là lý do đầu), `already_bought` 1 |

Ceiling không phụ thuộc vector (mask engine) nên trùng giữa hai model, như kỳ vọng.

Tốc độ offline của `engine` (mục 3): e5-small p95 105,9 ms (LLBO) / 182,4 ms (temporal), e5-base 125,0 / 226,0 ms — vector 384 chiều rẻ hơn 768
chiều ở bước kNN chính xác trên 3.183 unit. **Không phải số NFR-PERF-01**: đo trong tiến trình harness, chạy tuần tự trên máy dev, gồm cả
phần Python của harness; p95 HTTP `/recommendations` phải đo lại khi production đổi model.

## 9. Caveat khi trích dẫn

- Dữ liệu sinh (handbook §12). Temporal 98 khách → 1 khách = 1,02 điểm.
- **Không có mốc Cohere** trong report này (phạm vi plan): kết luận chỉ là "e5-small đủ tốt so với baseline và so với e5-base", không phải
  "e5 hơn / kém hệ thống đang chạy".
- Vector e5 tra bằng kNN chính xác trong RAM; production sẽ dùng Weaviate HNSW → cần parity offline = HTTP sau khi index e5 (ngoài phạm vi).
- Thư viện và hệ điều hành khác Day 5 (Linux, numpy 2.4.6 / scipy 1.17.1 so với Windows numpy 2.5.3 / scipy 1.18.1): không so chữ số `ials`
  / `bpr` với report Day 5.
- Lúc chạy cây làm việc có thay đổi chưa commit của người khác ở `src/data_collection/` và `src/evaluation/search_bench/`; DB bench seed từ
  worktree sạch nên các thay đổi đó không vào dữ liệu.

## 10. Lệnh tái sinh

```bash
# DB bench (worktree sạch của commit đang đo, cổng riêng để không đụng DB demo)
git worktree add --detach <wt> HEAD && cd <wt>
make demo-db POSTGRES_HOST_PORT=55433 CATALOG_SNAPSHOT=data_collection/snapshots/2026-09-23/products.jsonl.gz AS_OF=2026-09-24 SEED=42
# từ gốc repo; DSN local theo .env.example nhưng cổng 55433 (DATABASE_URL, EVAL_DATABASE_URL) — không ghi ở đây
python -m src.evaluation.recsys_bench doctor     # 3.183 search unit · 2.384 recommendable · as_of 2026-09-24
V=npy:bench_out/search/data/vec_T3+R_e5-small    # hoặc …_e5-base; m = e5s | e5b
for sp in llbo temporal; do SF=src/evaluation/recsys_bench/frozen/split-$sp-asof20260924.json
  python -m src.evaluation.recsys_bench run --arm random --arm most_popular --arm most_popular_in_destination --arm engine --arm engine_nommr \
    --split $sp --vectors $V --split-file $SF --run-id 2026-10-05-$sp-v5-$m
  python -m src.evaluation.recsys_bench run --arm engine --arm engine_nommr --arm most_popular_in_destination \
    --algos src/evaluation/recsys_bench/algos_v1.yaml --only content_profile --only star_blend_a1 --funnel-pool engine --mode funnel \
    --split $sp --vectors $V --split-file $SF --run-id 2026-10-05-$sp-gate-$m
  for mode in funnel raw; do
    python -m src.evaluation.recsys_bench run --algos src/evaluation/recsys_bench/algos_v1.yaml --mode $mode --funnel-pool mask \
      --funnel-rerank none --funnel-rerank mmr --max-tier 2 --split $sp --vectors $V --split-file $SF --run-id 2026-10-05-$sp-algos-$mode-$m
  done
  python -m src.evaluation.recsys_bench regress --run-id 2026-10-05-$sp-gate-$m --base content_profile+mmr --ref engine
  python -m src.evaluation.recsys_bench regress --run-id 2026-10-05-$sp-gate-$m --base content_profile --ref engine_nommr
  python -m src.evaluation.recsys_bench compare --run-id 2026-10-05-$sp-v5-$m --base engine --ref most_popular_in_destination
  python -m src.evaluation.recsys_bench analyze --run-id 2026-10-05-$sp-v5-$m
done
# kiểm chéo 7.4 (mọi scorer CF): regress --run-id …-algos-funnel-e5s --ref-run-id …-algos-funnel-e5b --base itemknn --ref itemknn
# so hai model 7.6: script phụ lục, vd python cross_model.py 2026-10-05-llbo-v5-e5s 2026-10-05-llbo-v5-e5b engine engine_nommr
```

## Phụ lục — script so hai model (`cross_model.py`, chạy từ gốc repo)

```python
"""Δ e5-small − e5-base theo khách giữa hai run (cùng split đóng băng), paired bootstrap 10.000 lượt, seed 42 — dùng nguyên
`compare.compare_arms` (cùng công thức `compare` trong run). Dùng: python cross_model.py <run e5s> <run e5b> <arm> [<arm> ...]"""
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

from src.evaluation.recsys_bench.compare import compare_arms, compare_markdown  # noqa: E402

RUNS = ROOT / "bench_out" / "recsys" / "runs"


def rows(run_id: str) -> tuple[dict, dict]:
    d = RUNS / run_id
    summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict]] = {}
    with open(d / "per_user.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                out.setdefault(r["arm"], {})[r["user"]] = r
    return summary, out


def main() -> None:
    run_s, run_b, *arms = sys.argv[1:]
    sa, ra = rows(run_s)
    sb, rb = rows(run_b)
    for key in ("configHash", "k"):
        assert sa.get(key) == sb.get(key), f"{key} khác: {sa.get(key)} vs {sb.get(key)}"
    assert sa["split"]["frozenSha256"] == sb["split"]["frozenSha256"], "split đóng băng khác"
    print(f"e5s `{run_s}` ({sa['modelVersion']}) vs e5b `{run_b}` ({sb['modelVersion']}) · split {sa['split']['frozenSha256'][:12]}\n")
    for arm in arms:
        c = compare_arms({f"{arm}@e5s": ra[arm], f"{arm}@e5b": rb[arm]}, f"{arm}@e5s", f"{arm}@e5b")
        print(f"#### {arm}\n\n{compare_markdown(c)}\n")


if __name__ == "__main__":
    main()
```
