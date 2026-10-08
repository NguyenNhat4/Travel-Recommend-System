# RecSys bám sở thích — đo lại có thống kê: CI ghép cặp, nhiều seed, nhiễu cùng khách (WP2–WP3)

- Ngày chạy: 2026-10-08
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04 (`docs/prd/requirements.md` §1.3), AC-REC-02
- Plan: `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` WP2, WP3
- Mốc engine và parity: `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-moc-moi.md` (WP0)
- Phân tích và bảng quyết định: `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md`
- Kết quả gốc: `src/evaluation/recsys_bench/theme_study/results/2026-10-08-wp0-wp3/`

## 1. Lượt này khác lượt 08/10 ở đâu

| | Lượt 08/10 (báo cáo cuối) | Lượt này |
|---|---|---|
| Thống kê | z-test hai tỷ lệ **độc lập**, ước lượng thô | **Bootstrap ghép cặp** 2.000 lần trên cùng khách, CI 95 % |
| Cỡ mẫu split | 800 khách đầu theo id | **Toàn bộ**: LLBO 4.072 · temporal 775 · nexttrip 1.835 |
| Khách giả lập | 1 seed (7), 240 khách / kịch bản | **3 seed** (42, 7, 2026), 720 khách / kịch bản |
| Kịch bản nhiễu | cohort **độc lập** với `between` | thêm `noisy_paired`: **cùng khách** `between` + 5–8 lượt xem lệch chủ đề |
| Biến thể | F7, F12b, F13a/b, F14 | thêm F14 ở `W_POP` 0,25 / 0,35 / 0,45 và **độ bền calibration** qua 3 seed |
| Kết quả từng khách | không lưu | `--per-user-out` JSONL (38.248 + 19.124 dòng) |

Vì sao ghép cặp quan trọng: mọi cấu hình chấm **cùng** tập khách, nên phương sai của *chênh lệch* nhỏ hơn hẳn phương sai
của hai trung bình độc lập. Ba kết luận "chưa phân biệt được" của báo cáo cuối đổi thành "phân biệt được" ở đây (§4.3).

Môi trường, dữ liệu, vector, parity: giống hệt lượt WP0 — xem report WP0 §2–§3. `parity_mismatch_llbo200 = 0` ở mọi lượt.

## 2. Bảng chỉ số, toàn bộ khách mỗi split, khách giả lập 3 seed

<!-- python -m src.evaluation.recsys_bench.theme_study.tables metrics p2_a.json p2_b.json p4_bd.json p4_c.json -->

| Cấu hình | LLBO h@20 | LLBO nDCG@10 | LLBO h@4 | temp h@20 | temp nDCG@10 | temp h@4 | next h@20 | next nDCG@10 | next h@4 | theme between | theme noisy | theme noisy_paired | theme open |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P0+F0 (production) | 0.8084 | 0.4988 | 0.5329 | 0.1587 | 0.0954 | 0.1135 | 0.0785 | 0.0239 | 0.0256 | 0.439 | 0.377 | 0.376 | 0.800 |
| P0+F7 | 0.8084 | 0.4988 | 0.5329 | 0.1290 | 0.0895 | 0.1058 | 0.0458 | 0.0175 | 0.0174 | 0.787 | 0.465 | 0.493 | 0.800 |
| P2+F0 | 0.8084 | 0.4957 | 0.5324 | 0.1548 | 0.0929 | 0.1123 | 0.0757 | 0.0240 | 0.0267 | 0.431 | 0.405 | 0.397 | 0.800 |
| **P2+F7** | 0.8084 | 0.4957 | 0.5324 | 0.1303 | 0.0884 | 0.1058 | 0.0431 | 0.0178 | 0.0174 | 0.762 | 0.681 | 0.668 | 0.800 |
| P2+F13a | 0.8084 | 0.4957 | 0.5324 | 0.1213 | 0.0835 | 0.0994 | 0.0354 | 0.0137 | 0.0136 | 0.782 | 0.765 | 0.752 | 0.800 |
| **P2+F14** (pop 0,30) | 0.8084 | 0.4957 | 0.5324 | 0.1239 | 0.0874 | 0.1045 | 0.0354 | 0.0163 | 0.0174 | 0.785 | 0.737 | 0.724 | 0.800 |
| P2+F14b (pop 0,25) | 0.8084 | 0.4957 | 0.5324 | 0.1213 | 0.0873 | 0.1019 | 0.0338 | 0.0151 | 0.0158 | 0.785 | 0.739 | 0.739 | 0.800 |
| **P2+F14c** (pop 0,35) | 0.8084 | 0.4957 | 0.5324 | 0.1252 | 0.0874 | 0.1045 | 0.0403 | 0.0162 | 0.0185 | 0.769 | 0.711 | 0.703 | 0.800 |
| P2+F14d (pop 0,45) | 0.8084 | 0.4957 | 0.5324 | 0.1303 | 0.0892 | 0.1084 | 0.0469 | 0.0181 | 0.0202 | 0.583 | 0.496 | 0.491 | 0.800 |

Chênh so với bảng 800 khách của WP0 **không phải** do engine mà do cỡ mẫu: 800 khách đầu theo id dễ hơn ở LLBO
(h@20 0,836 so với 0,808) và khó hơn ở nexttrip (h@20 0,025 so với 0,035 cho P2+F14). Đây là lý do WP2 dùng toàn bộ khách.

## 3. CI ghép cặp so với production (P0+F0)

### 3.1 Split thật — hit@20 và hit@4

| Cấu hình | LLBO h@20 | LLBO h@4 | temporal h@20 | temporal h@4 | nexttrip h@20 | nexttrip h@4 |
|---|---|---|---|---|---|---|
| P0+F7 | **+0,0000** [0, 0] | **+0,0000** [0, 0] | −0,0297 [−0,0452, −0,0155] | −0,0077 [−0,0155, +0,0000] | −0,0327 [−0,0425, −0,0229] | −0,0082 [−0,0136, −0,0033] |
| P2+F0 | +0,0000 [−0,0012, +0,0012] | −0,0005 [−0,0020, +0,0010] | −0,0039 [−0,0116, +0,0039] | −0,0013 [−0,0065, +0,0026] | −0,0027 [−0,0082, +0,0022] | +0,0011 [−0,0011, +0,0033] |
| P2+F7 | +0,0000 [−0,0012, +0,0012] | −0,0005 [−0,0020, +0,0010] | −0,0284 [−0,0426, −0,0155] | −0,0077 [−0,0155, +0,0000] | −0,0354 [−0,0447, −0,0262] | −0,0082 [−0,0136, −0,0033] |
| P2+F13a | +0,0000 [−0,0012, +0,0012] | −0,0005 [−0,0020, +0,0010] | −0,0374 [−0,0529, −0,0232] | −0,0142 [−0,0233, −0,0052] | −0,0431 [−0,0534, −0,0332] | −0,0120 [−0,0185, −0,0065] |
| P2+F14 | +0,0000 [−0,0012, +0,0012] | −0,0005 [−0,0020, +0,0010] | −0,0348 [−0,0503, −0,0206] | −0,0090 [−0,0168, −0,0013] | −0,0431 [−0,0540, −0,0332] | −0,0082 [−0,0142, −0,0027] |
| P2+F14b (pop 0,25) | +0,0000 [−0,0012, +0,0012] | −0,0005 [−0,0020, +0,0010] | −0,0374 [−0,0529, −0,0232] | — | −0,0447 [−0,0556, −0,0343] | — |
| P2+F14c (pop 0,35) | +0,0000 [−0,0012, +0,0012] | −0,0005 [−0,0020, +0,0010] | −0,0335 [−0,0490, −0,0194] | — | −0,0381 [−0,0480, −0,0289] | — |
| P2+F14d (pop 0,45) | +0,0000 [−0,0012, +0,0012] | −0,0005 [−0,0020, +0,0010] | −0,0284 [−0,0426, −0,0155] | — | −0,0316 [−0,0409, −0,0229] | — |

LLBO nDCG@10 là chỉ số LLBO **duy nhất** đổi, và chỉ do P2: −0,0031 [−0,0043, −0,0019] cho mọi cấu hình có P2 (0,6 %
tương đối); P0+F7 đúng 0.

### 3.2 Khách giả lập — tỷ lệ đúng chủ đề trong list 4 món

| Cấu hình | between (n = 720) | noisy_paired (n = 720) | open (n = 720) |
|---|---|---|---|
| P0+F7 | +0,3475 [+0,3157, +0,3778] | +0,1170 [+0,0863, +0,1458] | **+0,0000** [0, 0] |
| P2+F0 | −0,0080 [−0,0149, −0,0014] | +0,0215 [+0,0142, +0,0292] | +0,0000 [0, 0] |
| P2+F7 | +0,3223 [+0,2925, +0,3509] | +0,2926 [+0,2616, +0,3216] | +0,0000 [0, 0] |
| P2+F13a | +0,3428 [+0,3109, +0,3728] | **+0,3763** [+0,3454, +0,4061] | +0,0000 [0, 0] |
| P2+F14 | **+0,3454** [+0,3128, +0,3765] | +0,3481 [+0,3142, +0,3806] | +0,0000 [0, 0] |
| P2+F14b (pop 0,25) | +0,3459 [+0,3138, +0,3767] | +0,3634 [+0,3296, +0,3972] | +0,0000 [0, 0] |
| P2+F14c (pop 0,35) | +0,3301 [+0,2997, +0,3596] | +0,3274 [+0,2948, +0,3582] | +0,0000 [0, 0] |

### 3.3 Ba điều chỉ ghép cặp mới thấy

1. **Nhánh có chuyến mở không hề bị động tới — chứng minh được, không phải "kỳ vọng".** `open` và cả ba chỉ số LLBO của
   P0+F7 so với P0+F0 lệch **đúng 0** ở từng khách (`nDiscordant = 0`), không chỉ bằng nhau ở trung bình. Mọi thay đổi
   LLBO còn lại đến từ P2.
2. **P2 không mất gì đo được trên split thật.** P2+F0 so với P0+F0: LLBO h@20 / h@4, temporal (cả hai), nexttrip (cả hai)
   đều có CI chứa 0. Thêm P2 vào F7 cũng vậy: P0+F7 → P2+F7 nexttrip h@20 −0,0027 [−0,0082, +0,0027], temporal h@20
   +0,0013 [−0,0052, +0,0077] — **không phân biệt được**. Nhưng P2 mua được +0,175 theme ở `noisy_paired`
   (0,493 → 0,668). Báo cáo cuối §4.5.1 đoán đúng hướng; ở đây nó thành kết luận có CI.
3. **F14 hơn F7 thật**, không còn "chưa phân biệt được" (§4.5.5 của báo cáo cuối): theme `between` +0,0230
   [+0,0110, +0,0350], `noisy` +0,0559 [+0,0412, +0,0697], `noisy_paired` +0,0556 [+0,0417, +0,0701]. Giá phải trả:
   nexttrip h@20 −0,0076 [−0,0125, −0,0027]; temporal h@20 −0,0065 [−0,0129, **+0,0000**] → chưa phân biệt được.

### 3.4 `W_POP` là núm vặn — và min-max hiệu quả hơn calibration ở mức pop cao

Quét `W_POP` của F14 trên toàn bộ khách mỗi split (WP3.1):

| | pop 0,25 | pop 0,30 | pop 0,35 | pop 0,45 | F7 (min-max, pop 0,30) |
|---|---:|---:|---:|---:|---:|
| temporal h@20 | 0.1213 | 0.1239 | 0.1252 | 0.1303 | 0.1303 |
| nexttrip h@20 | 0.0338 | 0.0354 | 0.0403 | 0.0469 | 0.0431 |
| theme between | 0.785 | 0.785 | 0.769 | 0.583 | 0.762 |
| theme noisy_paired | 0.739 | 0.724 | 0.703 | 0.491 | 0.668 |

Hai điều rút ra:

1. **pop 0,45 làm sụp theme** (between 0,583, chỉ +0,143 so với production → **không đạt** tiêu chí theme ≥ 0,15) nhưng chỉ
   lấy lại temporal về đúng mức của F7. Ở mức pop cao, **min-max theo request (F7) hiệu quả hơn calibration phân vị (F14)**:
   cùng temporal 0,1303 mà F7 cho theme 0,762 so với 0,583 của F14d.
2. **pop 0,25 không mua thêm gì** so với pop 0,30 ở `between` (0,785 cả hai) mà mất thêm temporal và nexttrip. Vùng hợp lý
   là **pop 0,30–0,35**.

So trực tiếp từng ứng viên với P2+F7 (ghép cặp, cùng khách):

| → | temporal h@20 | nexttrip h@20 | theme between | theme noisy_paired |
|---|---|---|---|---|
| P2+F14c (pop 0,35) | −0,0052 [−0,0116, **+0,0000**] | −0,0027 [−0,0065, **+0,0011**] | +0,0078 [−0,0031, +0,0184] | **+0,0348** [+0,0223, +0,0468] |
| P2+F14 (pop 0,30) | −0,0065 [−0,0129, **+0,0000**] | −0,0076 [−0,0125, −0,0027] | +0,0230 [+0,0110, +0,0350] | **+0,0556** [+0,0417, +0,0701] |
| P2+F13a | −0,0090 [−0,0181, −0,0013] | −0,0076 [−0,0136, −0,0016] | +0,0205 [+0,0074, +0,0339] | **+0,0837** [+0,0669, +0,1010] |
| P2+F14 → P2+F13a | −0,0026 [−0,0090, +0,0026] | +0,0000 [−0,0049, +0,0049] | −0,0025 [−0,0149, +0,0105] | +0,0281 [+0,0125, +0,0437] |

**P2+F14c hơn P2+F7 ở theme mà không có chi phí nào phân biệt được.** Và ở cỡ mẫu đầy đủ, **F13a không còn thua F14** ở
temporal / nexttrip như báo cáo cuối kết luận trên 800 khách — hai cột đó có CI chứa 0, còn `noisy_paired` thì F13a hơn
+0,028. Lý do báo cáo cuối loại F13a ("temporal / nexttrip thấp nhất") không đứng được ở cỡ mẫu này.

## 4. Nhiễu làm mất bao nhiêu sở thích — trên cùng một khách

`noisy_paired` là **bản sao** của khách `between` cộng 5–8 lượt xem ở điểm đến khác chủ đề. So `between` → `noisy_paired`
trong **cùng một cấu hình** là phép đo trực tiếp "lượt xem lẻ lấn át sở thích dài hạn bao nhiêu" — kịch bản `noisy` cũ
không làm được vì nó là cohort khác (báo cáo cuối §2.2).

| Cấu hình | between | noisy_paired | chênh | CI 95 % |
|---|---:|---:|---:|---|
| P0+F0 (production) | 0.4392 | 0.3757 | −0,0635 | [−0,0736, −0,0542] |
| **P0+F7** | 0.7867 | 0.4927 | **−0,2940** | [−0,3179, −0,2694] |
| P2+F0 | 0.4313 | 0.3972 | −0,0340 | [−0,0417, −0,0267] |
| P2+F7 | 0.7616 | 0.6683 | −0,0933 | [−0,1091, −0,0780] |
| **P2+F13a** | 0.7821 | 0.7520 | **−0,0301** | [−0,0426, −0,0164] |
| P2+F14 | 0.7846 | 0.7238 | −0,0608 | [−0,0772, −0,0454] |
| P2+F14b (pop 0,25) | 0.7852 | 0.7391 | −0,0461 | [−0,0607, −0,0311] |
| P2+F14c (pop 0,35) | 0.7693 | 0.7031 | −0,0662 | [−0,0830, −0,0506] |
| P2+F14d (pop 0,45) | 0.5825 | 0.4912 | −0,0913 | [−0,1034, −0,0792] |

**Đây là bằng chứng rõ nhất cho việc phải sửa cả hai chỗ.** F7 một mình bám sở thích rất tốt khi lịch sử sạch (0,787) rồi
**sụp xuống 0,493 ngay khi khách có vài lượt lướt xem** — mất 0,294. Thêm P2 vào, mức mất còn 0,093. Sửa công thức mà
không sửa cách dựng profile là mua một cải thiện chỉ tồn tại trên lịch sử sạch, mà lịch sử production **không** sạch:
trung bình mỗi khách 1,52 chuyến mua và 4,26 "chuyến" chỉ xem (báo cáo cuối §3.A).

## 5. Độ ổn định giữa các seed khách giả lập (42 / 7 / 2026)

| Cấu hình | between (theo seed) | sd | noisy_paired (theo seed) | sd |
|---|---|---:|---|---:|
| P0+F0 | 0.4375 / 0.4448 / 0.4354 | 0.0049 | 0.3583 / 0.3833 / 0.3854 | 0.0151 |
| P0+F7 | 0.7760 / 0.7774 / 0.8066 | 0.0173 | 0.4615 / 0.4965 / 0.5201 | 0.0295 |
| P2+F0 | 0.4312 / 0.4354 / 0.4271 | 0.0042 | 0.3927 / 0.3979 / 0.4010 | 0.0042 |
| P2+F7 | 0.7632 / 0.7326 / 0.7889 | 0.0282 | 0.6483 / 0.6573 / 0.6993 | 0.0272 |
| P2+F13a | 0.7719 / 0.7743 / 0.8000 | 0.0156 | 0.7399 / 0.7462 / 0.7698 | 0.0157 |
| P2+F14 | 0.7823 / 0.7625 / 0.8090 | 0.0234 | 0.7062 / 0.7146 / 0.7507 | 0.0236 |
| P2+F14b | 0.7858 / 0.7667 / 0.8031 | 0.0182 | 0.7281 / 0.7285 / 0.7608 | 0.0187 |
| P2+F14c | 0.7806 / 0.7427 / 0.7847 | 0.0231 | 0.6875 / 0.6944 / 0.7274 | 0.0213 |

Thứ tự các cấu hình **giống nhau ở cả ba seed**. Nhưng sd giữa seed (0,016–0,030) cùng cỡ với chênh lệch giữa F13a và
F14 trên `noisy_paired` (0,028): chênh đó phân biệt được khi ghép cặp **trên cùng bộ khách**, nhưng không nên coi là bền
qua mọi cách sinh khách giả lập. Chênh lệch so với production (0,29–0,38) thì lớn hơn sd giữa seed cả chục lần.

## 6. Độ bền calibration của F14 (WP3.1)

Ngưỡng `q` của F14 lấy từ một tập calibration riêng. Nếu `q` nhạy với tập đó thì F14 không dùng được trong production.
Đo lại với ba seed calibration, cùng profile P2, cùng 120 request:

| Seed calibration | q_low (p10) | q_high (p99) | span | between | noisy | noisy_paired | open |
|---|---:|---:|---:|---:|---:|---:|---:|
| 99 (bản 08/10) | 0.85294 | 0.93870 | 0.08576 | 0.785 | 0.737 | 0.724 | 0.800 |
| 7 | 0.85102 | 0.94034 | 0.08932 | 0.788 | 0.738 | 0.722 | 0.800 |
| 2026 | 0.85443 | 0.93788 | 0.08345 | 0.784 | 0.739 | 0.728 | 0.800 |
| **biên độ** | 0.0034 | 0.0025 | 0.0059 (±3,4 %) | 0.004 | 0.002 | 0.006 | 0 |

**F14 không nhạy với tập calibration.** Kết quả lệch tối đa 0,006 — nhỏ hơn sd giữa seed khách (0,019–0,024) và nhỏ hơn
chênh lệch giữa các công thức cả chục lần. Nhược điểm còn lại của F14 vẫn đúng nhưng khác loại: `q` gắn với **model +
`TEXT_BUILDER_VERSION` + tầng lấy ứng viên**, nên đổi một trong ba là phải calibrate lại; đó là việc của job index, không
phải rủi ro số học.

## 7. Caveat khi trích dẫn

1. **Event CDP là giả lập chọn điểm đến theo độ phổ biến.** temporal và nexttrip vì thế thưởng món bán chạy và **không**
   đo được lợi ích của việc bám sở thích. Mức giảm ở hai cột đó là **cận trên** của chi phí thật. Đổi bộ sinh event là
   WP6 / gate G6.
2. Khách giả lập cũng là giả lập: nhãn chủ đề 58 điểm đến gán tay, 10 điểm "hỗn hợp" không chấm, điểm đến mỗi chuyến đúng
   chủ đề với xác suất 80 % (`theme_exp.py:83`). Chủ đề của lượt xem nhiễu là ngẫu nhiên đều.
3. `themePrec` đo trên **list 4 món** của trang chủ (`mode="prod"`, cap 2 món / taxonomy); `hit@20` / `nDCG@10` đo trên
   list 20 (`mode="eval"`, không cap) — hai chế độ khác nhau, không so trực tiếp với nhau được.
4. **Chưa đo latency.** Tiêu chí "p95 `/recommendations` không tăng quá 50 ms" của G1 còn trống (WP4.3).
5. Chưa đo ô khám phá B trên tổ hợp P2 + công thức (WP4.1); số ô khám phá duy nhất đang có là của profile production + F0
   (báo cáo cuối §4.4).
6. Bootstrap ghép cặp dùng seed cố định `20261008`, 2.000 lần rút; chạy lại cùng dữ liệu cho cùng CI.
7. Bản sao production chụp 08/10 01:49; catalog và event sẽ lệch dần so với production thật.
8. Tất cả là offline trên bản sao. Chưa có A/B, chưa có log impression thật.

## 8. Lệnh tái sinh

Môi trường: xem report WP0 §6 (nạp DB, env). Sau đó:

```bash
VEC=npy:/đường/dẫn/vectors/vec_prodcopy_e5s
AS_OF=2026-10-08T00:00:00+00:00
SYN="--n-syn 80 --scenarios between,open,noisy,noisy_paired --syn-seeds 42,7,2026"

# A: P0/P2 × F0/F7, toàn bộ khách mỗi split  (1892 s)
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
  --profiles P0_prod,P2_confidence --scorers F0_prod,F7_betweenMinmaxPop30 --max-users 0 $SYN \
  --per-user-out p2_a.jsonl --out p2_a.json

# B: P2 × F13a/F14, toàn bộ khách mỗi split  (981 s)
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
  --profiles P2_confidence --scorers F13a_betweenCenter,F14_betweenQuantilePop30 \
  --f14-cal-profile P2_confidence --max-users 0 $SYN --per-user-out p2_b.jsonl --out p2_b.json

# C: biến thể W_POP của F14, toàn bộ khách mỗi split
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
  --profiles P2_confidence --scorers F14b_betweenQuantilePop25,F14d_betweenQuantilePop45 \
  --f14-cal-profile P2_confidence --max-users 0 $SYN --per-user-out p4_bd.jsonl --out p4_bd.json
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
  --profiles P2_confidence --scorers F14c_betweenQuantilePop35 \
  --f14-cal-profile P2_confidence --max-users 0 $SYN --per-user-out p4_c.jsonl --out p4_c.json

# D: độ bền calibration — cùng công thức, ba seed calibration (chỉ khách giả lập, ~30 s mỗi lượt)
for S in 7 2026; do
  python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec $VEC --as-of $AS_OF \
    --profiles P2_confidence --scorers F14_betweenQuantilePop30 --f14-cal-profile P2_confidence \
    --f14-cal-seed $S --splits "" $SYN --out p3_cal$S.json
done

# E: CI ghép cặp + nhiễu cùng khách + độ lệch giữa seed
python -m src.evaluation.recsys_bench.theme_study.paired_ci --per-user p2_a.jsonl p2_b.jsonl p4_bd.jsonl p4_c.jsonl \
  --baseline P0_prod+F0_prod --out ci_full.json
python -m src.evaluation.recsys_bench.theme_study.paired_ci --per-user p2_a.jsonl p2_b.jsonl \
  --compare "P2_confidence+F7_betweenMinmaxPop30:P2_confidence+F14_betweenQuantilePop30,P2_confidence+F14_betweenQuantilePop30:P2_confidence+F13a_betweenCenter" \
  --out ci_head.json

# Bảng
python -m src.evaluation.recsys_bench.theme_study.tables metrics p2_a.json p2_b.json p4_bd.json p4_c.json
python -m src.evaluation.recsys_bench.theme_study.tables ci ci_full.json --strata llbo,temporal,nexttrip
python -m src.evaluation.recsys_bench.theme_study.tables seeds ci_full.json
```

File JSONL kết quả từng khách (~15 MB) **không** nằm trong git; chạy lại các lệnh trên để dựng lại (khoảng 50 phút trên
máy chạy 2 tiến trình song song). File JSON tổng hợp và `ci*.json` thì có trong
`src/evaluation/recsys_bench/theme_study/results/2026-10-08-wp0-wp3/`.
