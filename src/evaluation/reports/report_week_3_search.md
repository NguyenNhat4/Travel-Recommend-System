# Báo cáo tuần 3 — Search: bộ gold, chọn model embedding, `/search` với e5-small

- Giai đoạn: tuần 3, 28/09–05/10/2026 (Day 1–6 của `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`). Phần RecSys ở `report_week_3.md`.
- Phục vụ: FR-SRC-01..04, AC-SRC-01, NFR-PERF-01 (`docs/prd/requirements.md`); `docs/prd/test-plan.md` §2.5.
- Báo cáo này **không chạy thêm thí nghiệm**: mọi số lấy từ các report đã chạy (mục 6). Người đọc: cả nhóm và mentor.

> **Đọc trước khi trích dẫn.** Gold có 131 câu; mỗi slice 3–18 câu nên chênh lệch theo slice chỉ là hướng. Nhãn được gán trên các kết quả mà
> Cohere + BM25 tìm ra (pooling), nên model khác Cohere có một phần kết quả chưa nhãn — luôn đọc số "condensed" (bỏ kết quả chưa nhãn) kèm số "full".

## Tóm tắt

1. **Có bộ gold để đo search.** 131 câu tìm kiếm tiếng Việt chia 13 nhóm (slice: gõ tắt, không dấu, tên riêng, tiện ích, câu ngoài catalog…),
   5.021 cặp (câu, sản phẩm) được hai người gán nhãn 0 / 1 / 2; độ đồng thuận κ = 0,692 (đạt ngưỡng 0,6). Bộ nhãn khoá theo phiên bản
   (`gold_v1` → `gold_v3`), chỉ được thêm, không sửa.
2. **Chọn model embedding e5-small (384 chiều, chạy local) thay Cohere v3.** Trên cùng thang đo, e5-small ngang e5-base, BGE-M3, GTE; e5-large
   kém hơn. e5-small rẻ nhất, nhanh nhất, không phụ thuộc API ngoài (05/10, nhóm chốt; cần đề xuất PRD FR-SRC-02).
3. **Code `/search` chạy trong benchmark với e5-small ngang Cohere** ở cấu hình đang chạy (hybrid + chuẩn hoá câu): nDCG@10 0,680 so với 0,684, khác biệt
   không có ý nghĩa thống kê. Nhưng **lệch mạnh theo nhóm câu**: e5-small tốt hơn rất nhiều ở câu gõ không dấu (+36 điểm), kém nhiều ở câu
   hỏi chéo loại sản phẩm `cross_vertical` (−26 điểm, 10 câu).
4. **Đổi model phải chỉnh lại ngưỡng cutoff.** Ngưỡng 0,62 đặt cho Cohere không lọc gì với e5 (mọi câu trả ~200 kết quả). Đo trên nửa gold (dev),
   kiểm trên nửa còn lại (test): đề xuất **0,85** — mất ~1 điểm nDCG, chỉ 1,6 % câu trong catalog bị trả rỗng (Cohere hiện 7,9 %).
5. **Độ trễ `/search` trên cloud là 4,0 s (p95)**, vượt xa mục tiêu 250 ms. Nguyên nhân là Weaviate Cloud đặt ở Frankfurt còn server ở
   Singapore, và hai truy vấn dense + BM25 chạy nối tiếp — không phải do model. Chưa có người nhận việc này.
6. **Số hybrid tuần trước bị đo sai và đã tìm ra nguyên nhân:** ~60 giây đầu sau khi nạp dữ liệu vào Weaviate, phần tìm theo từ khoá (BM25)
   xếp hạng sai; Day 4 đo đúng lúc đó. Đã thêm bước chờ khi nạp. Với số đúng, cấu hình production (hybrid + chuẩn hoá) tốt nhất cho cả hai model
   (Cohere +6,4 điểm so với chỉ dùng vector).
7. **Đã có công cụ chống tụt chất lượng:** bộ chia dev/test cố định, `baseline_v1` + lệnh `sb regress` (báo FAIL khi nDCG/Recall tụt > 1 điểm
   tổng hoặc > 3 điểm một nhóm), kiểm filter 439/439 kết quả đúng.

## 1. Đo search thế nào

- **Gold:** mỗi câu có danh sách sản phẩm đã chấm 2 = đúng ý, 1 = gần đúng, 0 = sai. Search trả 10 kết quả đầu, đem so với nhãn.
- **Chỉ số chính:** **nDCG@10** — thưởng khi sản phẩm đúng đứng cao (đúng ở hạng 1 được nhiều điểm hơn hạng 10); **Recall@10** — tỉ lệ sản
  phẩm liên quan lọt vào top 10; **zero-result** — tỉ lệ câu không trả gì (câu có trong catalog thì phải thấp, câu ngoài catalog thì nên cao).
- **So hai cấu hình:** ghép theo từng câu, bootstrap 1.000 lần → khoảng tin cậy CI95; CI chứa 0 thì coi là hoà. Luật thắng còn đòi không nhóm
  câu nào tụt quá 3 điểm.
- **Cổng APP:** chạy đúng code `/search` của backend (`SearchProducts`) trên collection Weaviate cùng hình dạng production, chỉ thay kho dữ liệu.

## 2. Bộ gold (Day 1–4)

| Mốc | Nội dung |
|---|---|
| Câu hỏi | 132 câu / 13 slice (đóng băng 29/09); 1 câu loại trước `gold_v1` vì pool sót sản phẩm đúng → 131 câu |
| Gán nhãn | Hai người, A 1.999 + B 2.000 cặp, 640 cặp chung để tính κ; 7 quy ước chốt sau khi gán |
| Đồng thuận | κ = 0,692 (0,661 sau rà slice) — đạt ≥ 0,6 |
| Phiên bản | `gold_v1` 3.359 nhãn → `gold_v2` (+612, lấp kết quả mới của e5-base) → `gold_v3` 5.021 nhãn |

Chi tiết: `docs/spec/bench/search-gold-summary.md`.

## 3. Chọn model embedding (Day 4–5)

So 5 model local trên cùng thang đo "condensed-deep" (mỗi model xếp hạng cả catalog, chỉ chấm sản phẩm đã có nhãn — không model nào bị thiệt vì
chưa được gán nhãn):

| Model / chiều | nDCG@10 | Recall@10 | Ghi chú |
|---|---:|---:|---|
| e5-small / 384 | 0,712 | 0,363 | rẻ nhất, nhanh nhất |
| BGE-M3 / 1024 | 0,710 | 0,364 | |
| e5-base / 768 | 0,697 | 0,348 | |
| GTE / 768 | 0,688 | 0,353 | |
| e5-large-instruct / 1024 | 0,678 | 0,347 | kém có ý nghĩa so với e5-small, BGE |

Bốn model đầu hoà thống kê → chọn e5-small theo quy tắc "hoà thì ưu tiên local, rẻ" (`eval-2026-10-02-search-local-fair.md`). RecSys đo lại bằng
vector e5-small: engine vẫn thắng mốc "bán chạy tại điểm đến" +25,8 điểm Hit@20, e5-small ngang e5-base (`eval-2026-10-05-recsys-e5-small-vs-e5-base.md`).

## 4. `/search` production với e5-small (Day 5–6)

| Cấu hình `/search` | Cohere v3 nDCG@10 | e5-small nDCG@10 | e5-small condensed | Kết luận |
|---|---:|---:|---:|---|
| dense (chỉ vector) | 0,620 | 0,635 | 0,647 | hoà tổng, `cross_vertical` −12,7 |
| hybrid (vector + BM25) | 0,623 | 0,655 | 0,665 | hơn tổng (CI chứa 0), `cross_vertical` −26 |
| hybrid + chuẩn hoá câu (**production**) | 0,684 | 0,680 | 0,690 | **hoà** |

Nhóm câu, cấu hình production (condensed): e5-small hơn ở không dấu +35,8, tên riêng +7,7; kém ở `cross_vertical` −26,0, `dest_type` −6,3,
`abbrev_typo` −5,7, `audience_style` −5,0.

**Đính chính số tuần trước:** số hybrid trong `eval-2026-10-01-search-v1-3arm.md` (Cohere hybrid 0,597, hybrid + chuẩn hoá 0,648) không tái lập
được; hôm nay hai lượt lặp ra 0,623 / 0,684 và trùng nhau 100 %. Lượt đo ngay sau khi nạp collection cho số lệch — có thể BM25 của Weaviate
chưa sẵn sàng. Kết luận cũ "giữ dense làm mốc vì hybrid + chuẩn hoá thua" cần xét lại: với số mới, hybrid + chuẩn hoá là cấu hình tốt nhất
cho cả hai model.

**Cutoff:** xem tóm tắt #4; bảng sweep ở `eval-2026-10-05-search-day5-e5s-app.md` §3. Không ngưỡng nào vừa làm câu ngoài catalog trả rỗng vừa
giữ câu trong catalog — với cả Cohere lẫn e5 (gold chỉ có 3 câu ngoài catalog).

**Khi embed hỏng:** `/search` hiện không có chế độ dự phòng. Nếu chỉ còn BM25, nDCG@10 mất 9,1 điểm (0,589 so với 0,680).

## 5. Quyết định và việc tuần 4

| # | Việc | Trạng thái |
|---|---|---|
| 1 | Đề xuất PRD FR-SRC-02: Cohere v3 / 1024 → e5-small / 384, kèm cutoff 0,85 và `lexical_cutoff` cần chỉnh | chờ (tqanh xem) |
| 2 | Phân tích `cross_vertical` −26 điểm với e5-small trước khi đổi production | mở |
| 3 | Guard đo: chờ BM25 sẵn sàng sau khi nạp collection | **xong** (05/10) — kiểm thêm production sau job index |
| 3b | Gán nhãn D6a (466 cặp, 2 người) → `gold_v4` → rescore, đặt lại baseline | mở |
| 4 | Gate P: p95 `/search` cloud < 250 ms — Weaviate cùng vùng với server, dense ∥ BM25, bỏ mask id khi mask ≈ toàn catalog | chưa có owner |
| 5 | Sau khi đổi production: đo lại p95 cloud, đặt lại `baseline_v1` | sau #1 |

**Kiểm thêm (05/10):** e5-small không có vấn đề "sản phẩm hút mọi câu" (hub) nặng hơn Cohere; GTE cắt 768 → 128 chiều không mất chất lượng; 3
câu `cross_vertical` kéo tụt e5-small vì model khớp **điểm đi** trong tên combo "vé máy bay khứ hồi Hà Nội – …" thay vì điểm đến — hướng sửa là
tách điểm đến thành filter. 466 cặp kết quả của e5-small chưa có nhãn đã được đóng gói để gán (`gold_v3__D6a`).

Không làm tuần này: các arm cải tiến S0–S9 (QU, amenity filter, SymSpell, rerank…) — chỉ làm phần cần cho việc đổi model.

## 6. Nguồn số

| Report | Nội dung |
|---|---|
| `docs/spec/bench/search-gold-summary.md` | gold: câu, nhãn, κ, phiên bản |
| `eval-2026-10-01-search-bench-gold-v2.md` | B0 (Cohere) so e5-base trên gold_v2 |
| `eval-2026-10-01-search-day4-local.md` | 8 model, full + condensed, latency embed |
| `eval-2026-10-01-search-v1-3arm.md` | 3 arm APP Cohere (số hybrid đã đính chính ở mục 4) |
| `eval-2026-10-01-search-cloud-latency.md` | p95 `/search` cloud 4,0 s, từng bước |
| `eval-2026-10-02-search-local-fair.md` | 5 model trên cùng thang đo → chọn e5-small |
| `eval-2026-10-05-search-day5-e5s-app.md` | `/search` với e5-small, cutoff, regression, F1 |
| `eval-2026-10-05-recsys-e5-small-vs-e5-base.md` | RecSys với vector e5 |

## 7. Giới hạn

- 131 câu, 3 câu ngoài catalog: số "trả rỗng khi không có trong catalog" gần như không đo được.
- Gold thiên về Cohere (pooling); e5-small có 15–21 % kết quả top-10 chưa nhãn.
- Latency trong report local là Weaviate local; số cloud chỉ có cho Cohere (01/10).
- 15 câu `abbrev_typo` đã được dùng khi viết bộ chuẩn hoá câu → số slice này là số đo trong mẫu.
