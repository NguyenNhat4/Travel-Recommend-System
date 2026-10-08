# RecSys bám sở thích — bảng quyết định chọn công thức (WP3)

- Ngày: 2026-10-08
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04 (`docs/prd/requirements.md` §1.3), AC-REC-02
- Plan: `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` WP3; gate G1–G4
- Nghiên cứu gốc: `docs/spec/bench/recsys-bam-so-thich-tong-hop.md`
- Số của tài liệu này: `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-ci.md` (CI ghép cặp, toàn bộ khách mỗi
  split, 3 seed khách giả lập) và `eval-2026-10-08-recsys-so-thich-moc-moi.md` (mốc engine)
- **Trạng thái: G1, G3, G4 đã chốt 08/10. G2 bị từ chối → có bằng chứng mới, cần chốt lại (§7). Chưa xong G2 thì không
  sửa engine (AGENTS.md §8).**

## 1. Hai câu hỏi tách rời nhau

Nghiên cứu 07–08/10 tìm ra hai nguyên nhân khác nhau; lượt đo WP2 cho thấy chúng có **chi phí rất khác nhau**, nên nên
quyết định riêng:

| | Sửa gì | Chi phí đo được | Lợi ích đo được |
|---|---|---|---|
| **P2** (cách dựng profile) | `u_long` nhân độ tin cậy chuyến `min(1, Σ W_TYPE)`, thay vì mọi chuyến nặng như nhau | **Không có** chi phí phân biệt được trên split thật: LLBO h@20 / h@4, temporal, nexttrip đều có CI chứa 0. Riêng LLBO nDCG@10 −0,0031 [−0,0043, −0,0019] (0,6 % tương đối) | **+0,175** theme ở khách có lịch sử lướt xem (`noisy_paired` 0,493 → 0,668 khi thêm P2 vào F7); mức mất vì nhiễu giảm từ −0,294 còn −0,093 |
| **Công thức** (khi không có chuyến mở) | Đưa cos về cùng thang với pop | temporal h@20 −0,028 … −0,037; nexttrip h@20 −0,032 … −0,045 — **đều có ý nghĩa thống kê** | +0,32 … +0,35 theme `between`; +0,29 … +0,38 theme `noisy_paired` |

Nói cách khác: **P2 gần như miễn phí, công thức thì phải trả giá.** Và hai thứ chỉ có tác dụng khi đi cùng nhau — xem §2.

## 2. Vì sao không thể chỉ sửa công thức

`noisy_paired` là **bản sao của cùng một khách** `between`, cộng 5–8 lượt xem ở điểm đến khác chủ đề. So trong cùng một
cấu hình là phép đo trực tiếp "lịch sử lướt xem lấn át sở thích bao nhiêu":

| Cấu hình | lịch sử sạch | + lướt xem nhiễu | mất | CI 95 % |
|---|---:|---:|---:|---|
| production (P0+F0) | 0.439 | 0.376 | −0,064 | [−0,074, −0,054] |
| **chỉ sửa công thức (P0+F7)** | **0.787** | **0.493** | **−0,294** | [−0,318, −0,269] |
| P2+F7 | 0.762 | 0.668 | −0,093 | [−0,109, −0,078] |
| P2+F14 | 0.785 | 0.724 | −0,061 | [−0,077, −0,045] |
| P2+F13a | 0.782 | 0.752 | −0,030 | [−0,043, −0,016] |

Sửa công thức một mình cho con số đẹp nhất trên lịch sử **sạch** (0,787) rồi mất gần hết ngay khi khách có vài lượt lướt
xem. Lịch sử production **không** sạch: trung bình mỗi khách 1,52 chuyến mua và 4,26 "chuyến" chỉ xem / thêm giỏ, 75 %
khách có nhiều chuyến xem hơn chuyến mua (báo cáo gốc §3.A). Vì vậy: **P2 không phải phần tuỳ chọn.**

## 3. Các công thức ứng viên

Mọi công thức chỉ áp **khi khách không có chuyến đang mở**; có chuyến mở giữ nguyên production (đã kiểm: `open` và cả ba
chỉ số LLBO lệch **đúng 0** ở từng khách).

| Mã | Công thức (không có chuyến mở; `c` = cos(u_long, v), `pop` ∈ [0,1]) | Hằng phải nuôi |
|---|---|---|
| F7 | min-max `c` trong **không gian ứng viên của request** → `0,70·ĉ + 0,30·pop` | không có |
| F14b / F14 / F14c / F14d | `s = clip((c − q_low)/(q_high − q_low), 0, 1)` → `(1−W_POP)·s + W_POP·pop`, `W_POP` = 0,25 / 0,30 / 0,35 / 0,45 | `q_low`, `q_high` (2 số) |
| F13a | trừ vector trung bình catalog khỏi `v` và `u_long`, chuẩn hoá lại, rồi **giữ nguyên trọng số production**: `0,85·c_centered + 0,15·pop` | vector trung bình catalog (384 số) |

### 3.1 Chênh so với production, có CI ghép cặp

Toàn bộ khách mỗi split (LLBO 4.072 · temporal 775 · nexttrip 1.835); khách giả lập 720 / kịch bản (3 seed).

| Cấu hình | LLBO h@4 | temporal h@20 | nexttrip h@20 | theme between | theme noisy_paired |
|---|---|---|---|---|---|
| P2+F0 (chỉ profile) | −0,0005 [−0,0020, +0,0010] | −0,0039 [−0,0116, +0,0039] | −0,0027 [−0,0082, +0,0022] | −0,008 [−0,015, −0,001] | +0,022 [+0,014, +0,029] |
| P0+F7 (chỉ công thức) | +0,0000 [0, 0] | −0,0297 [−0,0452, −0,0155] | −0,0327 [−0,0425, −0,0229] | +0,348 [+0,316, +0,378] | +0,117 [+0,086, +0,146] |
| P2+F14d (pop 0,45) | −0,0005 [−0,0020, +0,0010] | −0,0284 [−0,0426, −0,0155] | −0,0316 [−0,0409, −0,0229] | +0,143 [+0,125, +0,161] | +0,116 [+0,102, +0,130] |
| **P2+F7** | −0,0005 [−0,0020, +0,0010] | −0,0284 [−0,0426, −0,0155] | −0,0354 [−0,0447, −0,0262] | +0,322 [+0,293, +0,351] | +0,293 [+0,262, +0,322] |
| **P2+F14c (pop 0,35)** | −0,0005 [−0,0020, +0,0010] | −0,0335 [−0,0490, −0,0194] | −0,0381 [−0,0480, −0,0289] | +0,330 [+0,300, +0,360] | +0,327 [+0,295, +0,358] |
| **P2+F14 (pop 0,30)** | −0,0005 [−0,0020, +0,0010] | −0,0348 [−0,0503, −0,0206] | −0,0431 [−0,0540, −0,0332] | +0,345 [+0,313, +0,377] | +0,348 [+0,314, +0,381] |
| P2+F14b (pop 0,25) | −0,0005 [−0,0020, +0,0010] | −0,0374 [−0,0529, −0,0232] | −0,0447 [−0,0556, −0,0343] | +0,346 [+0,314, +0,377] | +0,363 [+0,330, +0,397] |
| **P2+F13a** | −0,0005 [−0,0020, +0,0010] | −0,0374 [−0,0529, −0,0232] | −0,0431 [−0,0534, −0,0332] | +0,343 [+0,311, +0,373] | **+0,376** [+0,345, +0,406] |

### 3.2 So trực tiếp với P2+F7 (ứng viên dự phòng của báo cáo gốc)

| → | temporal h@20 | nexttrip h@20 | theme between | theme noisy_paired |
|---|---|---|---|---|
| P2+F14c (pop 0,35) | −0,0052 [−0,0116, **+0,0000**] | −0,0027 [−0,0065, **+0,0011**] | +0,008 [−0,003, +0,018] | **+0,035** [+0,022, +0,047] |
| P2+F14 (pop 0,30) | −0,0065 [−0,0129, **+0,0000**] | −0,0076 [−0,0125, −0,0027] | +0,023 [+0,011, +0,035] | **+0,056** [+0,042, +0,070] |
| P2+F13a | −0,0090 [−0,0181, −0,0013] | −0,0076 [−0,0136, −0,0016] | +0,021 [+0,007, +0,034] | **+0,084** [+0,067, +0,101] |

**P2+F14c hơn P2+F7 ở theme (+0,035, có ý nghĩa) mà không có chi phí nào phân biệt được** — cả temporal lẫn nexttrip đều
có CI chứa 0. Đây là ứng viên "không mất gì so với F7".

### 3.3 Biên hiệu quả và hai biến thể bị loại

Xếp theo chi phí tăng dần, mỗi dòng mua thêm theme bằng cách trả thêm độ chính xác:

```
production  →  P2+F7  →  P2+F14c  →  P2+F14  →  P2+F13a
temporal Δ     −0,028    −0,034     −0,035     −0,037
nexttrip Δ     −0,035    −0,038     −0,043     −0,043
theme noisy    +0,293    +0,327     +0,348     +0,376
```

- **F14b (pop 0,25) bị F13a trội hoàn toàn**: cùng temporal (−0,0374), nexttrip tệ hơn (−0,0447 so với −0,0431), theme
  thấp hơn (+0,363 so với +0,376). Loại.
- **F14d (pop 0,45) bị F7 trội gần hoàn toàn**: cùng temporal (−0,0284), nexttrip tốt hơn chút (−0,0316 so với −0,0354)
  nhưng theme thấp hơn rất nhiều (+0,143 so với +0,322 ở `between`; +0,116 so với +0,293 ở `noisy_paired`), và **không
  đạt** tiêu chí theme ≥ 0,15. Loại. Kết luận phụ: ở mức pop cao, min-max theo request (F7) hiệu quả hơn calibration
  phân vị (F14).

### 3.4 Những gì đổi so với khuyến nghị của báo cáo gốc

| Báo cáo gốc §6 / §4.5 | Lượt WP2–WP3 |
|---|---|
| "F7 / F13a / F14 chưa phân biệt được" | **Phân biệt được** khi ghép cặp: F14 > F7 ở theme (+0,023 / +0,056) với giá 0,0076 nexttrip; F13a > F14 ở `noisy_paired` (+0,028) |
| "Không chọn F13a trừ khi thử centering toàn phần" — vì F13a temporal / nexttrip **thấp nhất** | Ở **toàn bộ** khách, F13a **bằng** F14 ở nexttrip (0,0354, chênh 0,0000 [−0,0049, +0,0049]) và chênh temporal so với F14 không phân biệt được (−0,0026 [−0,0090, +0,0026]). Lý do loại F13a không còn đứng được |
| "F14 nhược: phải calibrate lại khi đổi model / text builder" | Đúng, nhưng **không nhạy**: 3 seed calibration cho `q` lệch ±0,3 % và kết quả lệch ≤ 0,006 |
| "P2 là cải thiện chắc nhất" | Xác nhận, và mạnh hơn: P2 **không có chi phí phân biệt được** trên split thật |
| Mẫu 800 khách đầu theo id | Mẫu đó lệch (LLBO h@20 0,836 so với 0,808; nexttrip 0,025 so với 0,035). Số ở đây dùng toàn bộ khách |

## 4. Đối chiếu với tiêu chí nghiệm thu **đề nghị** (báo cáo gốc §6)

Tiêu chí này **chưa được chốt** — đây là G1. Bảng dưới áp dụng nguyên văn để thấy nó phân loại ra sao:

| Tiêu chí đề nghị | P2+F7 | P2+F14c | P2+F14 | P2+F13a |
|---|---|---|---|---|
| LLBO h@4 không giảm quá 0,01, CI chứa 0 | ✅ −0,0005, CI chứa 0 | ✅ | ✅ | ✅ |
| theme `between` tăng ≥ 0,15, cận dưới CI > 0,10 | ✅ +0,322 (cận dưới 0,293) | ✅ +0,330 | ✅ +0,345 | ✅ +0,343 |
| theme `noisy` tăng ≥ 0,15, cận dưới CI > 0,10 | ✅ +0,293 | ✅ +0,327 | ✅ +0,348 | ✅ +0,376 |
| temporal h@20 giảm ≤ 0,03 | ⚠️ −0,0284 | ❌ −0,0335 | ❌ −0,0348 | ❌ −0,0374 |
| `open` không đổi | ✅ đúng 0 ở từng khách | ✅ | ✅ | ✅ |
| nexttrip h@20 | −0,0354 (−45 %) | −0,0381 (−49 %) | −0,0431 (−55 %) | −0,0431 (−55 %) |
| latency p95 không tăng quá 50 ms | **chưa đo** (WP4.3) | chưa đo | chưa đo | chưa đo |

**Phải đọc kỹ ngưỡng temporal 0,03 trước khi dùng nó để loại ai.** temporal chỉ có 775 khách nên CI rộng ±0,015, và chênh
lệch temporal **giữa** các ứng viên không phân biệt được (F7 → F14c −0,0052 CI chứa 0; F7 → F14 −0,0065 CI chứa 0). Dùng
0,03 làm ngưỡng cứng thì việc "F7 đạt, F14c không đạt" là **sản phẩm của điểm ước lượng, không phải của dữ liệu**. Hai
cách xử lý, cần người dùng chọn:

- **(a)** Đặt ngưỡng theo cận dưới CI thay vì điểm ước lượng (ví dụ "cận dưới CI không dưới −0,05"): cả bốn ứng viên đạt.
- **(b)** Giữ ngưỡng điểm ước lượng nhưng nới lên 0,04: F7, F14c, F14, F13a đều đạt; F14b / F13a sát mép.

Thêm một điều phải cân: **temporal và nexttrip đo trên event CDP giả lập chọn điểm đến theo độ phổ biến**, nên hai split
đó thưởng cho món bán chạy và **không** đo được lợi ích của việc bám sở thích. Mức giảm là **cận trên** của chi phí thật
(báo cáo gốc §9.1, report CI §7.1). Đổi bộ sinh event là gate G6.

## 5. Gate chờ người dùng chốt

| Gate | Câu hỏi | Dữ liệu đã có | Khuyến nghị (người dùng quyết định) |
|---|---|---|---|
| **G1** | Tiêu chí nghiệm thu: ngưỡng LLBO / theme / temporal / latency | §4 | Giữ LLBO, theme, `open` như đề nghị; đổi ngưỡng temporal sang cách (a) hoặc (b) ở §4 vì ngưỡng 0,03 không phân biệt được bằng dữ liệu hiện có. Tiêu chí latency để WP4.3 đo rồi áp |
| **G2** | Mức giảm nexttrip có chấp nhận được không | −0,032 … −0,045 tuyệt đối, tức −41 % … −55 % tương đối; **là cận trên** vì event giả lập thưởng pop | Cần quyết định của người dùng. Nếu không chấp nhận mức này thì chỉ còn đường "sửa dữ liệu trước" (G6 / WP6) rồi đo lại |
| **G3** | Chọn công thức | §3.1–3.3 | **P2 + F14c (pop 0,35)** nếu muốn chắc: hơn F7 ở theme (+0,035) mà không có chi phí nào phân biệt được. **P2 + F13a** nếu ưu tiên bền với nhiễu (mất vì nhiễu chỉ −0,030, theme `noisy` cao nhất) và chấp nhận temporal −0,037. **P2 + F7** nếu muốn phương án không có hằng nào phải nuôi |
| **G4** | Có làm ô khám phá B không (đổi hành vi FR-REC-02) | Chỉ có số của profile production + F0 (báo cáo gốc §4.4: lấp ô trống, LLBO h@4 và temporal h@4 **không đổi**, thêm món ở điểm đến khác cho 29 % khách, đúng chủ đề 0,79) | Cần đo lại trên tổ hợp đã chọn ở G3 trước khi chốt — `eval_slots.py` đã có `--profile` và F13/F14, chạy được ngay sau G3 (WP4.1) |

Sau khi chốt G1–G4: WP4 (đo đúng tổ hợp + latency) → WP5.1 viết lại đề xuất PRD
`docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` (hiện vẫn `chờ chốt` với **nội dung cũ**: chỉ có F7 và
ô B, chưa có P2, chưa có F13a/F14, chưa có tiêu chí) → G5 → PRD → engine.

## 7. Chốt của người dùng 08/10 và điều tra G2

| Gate | Chốt | Hệ quả |
|---|---|---|
| **G1** | Giữ ngưỡng **điểm ước lượng 0,04** (cách (b) ở §4) | Cả bốn ứng viên đạt tiêu chí temporal: F7 −0,0284 · F14c −0,0335 · F14 −0,0348 · F13a −0,0374 |
| **G2** | **Chưa chấp nhận được** | Xung đột với G3: F14c có nexttrip h@20 −0,0381. Đã điều tra, xem dưới |
| **G3** | **P2 + F14c** (pop 0,35) | Khớp khuyến nghị "chắc nhất" của §5 |
| **G4** | **Có làm ô khám phá B** | Đã đo lại trên đúng tổ hợp P2 + F14c: ô B **miễn phí** (§7.3) |

Số và chi tiết: `src/evaluation/reports/eval-2026-10-08-recsys-g2-va-wp4.md`.

### 7.1 Mức giảm nexttrip không nhắm được vào nhóm nào — nhưng split thật cũng không đo được lợi ích

Ba giả thuyết "chỉ mất ở nhóm X nên bật / tắt công thức theo X" đều **sai**:

| Giả thuyết | Kết quả |
|---|---|
| Chỉ mất ở target bán chạy (artefact độ phổ biến) | **Sai.** 84 % mức mất ở target thuộc nửa dưới độ phổ biến; tỷ lệ mất tương đối gần như nhau (−48 % so với −52 %) |
| Mất tập trung ở khách ít lịch sử | **Sai.** Mức mất *tăng* theo lịch sử: −0,016 (<3 event) → −0,042 (≥12 event) |
| Mất tập trung ở khách có lịch sử tản mát | **Sai.** Đều khắp −0,032 … −0,046 theo `coherence` (phải tính trong không gian đã center; trong không gian thô của e5-small cả 1.835 khách đều ≥ 0,8 nên vô dụng) |

Đúng một điều: **100 % khách bị lật hit → miss đều không có chuyến mở**, đúng thiết kế.

**Nhưng** đọc bộ sinh event (`src/data_collection/seed/seed_histories.py` dòng 344–346 và 160–161): điểm đến mỗi chuyến
được bốc từ phân phối **toàn cục** theo cỡ điểm đến, `plan_trip(w, rng, home)` chỉ dùng `home` để kiểm tra tuyến bay —
**không có tham số khách nào khác**. Điểm đến chuyến sau của một khách **độc lập thống kê** với lịch sử của họ. Do đó:

- Bộ dự đoán tối ưu của nexttrip / temporal trên dữ liệu này **chính là** độ phổ biến toàn cục.
- Mọi dịch chuyến trọng số về phía sở thích **bắt buộc** làm hai chỉ số đó giảm, bất kể thuật toán tốt đến đâu.
- Lợi ích của việc bám sở thích **không thể xuất hiện** ở hai split này.

Nói cách khác: −0,0381 không phải giá của việc bám sở thích; nó là hình phạt cho việc rời khỏi bộ dự đoán tối ưu **trên dữ
liệu mà sở thích được định nghĩa là nhiễu**. Vì vậy **gate G6 (đổi bộ sinh event) là điều kiện tiên quyết của G2**, không
phải việc làm sau — khác với thứ tự trong plan.

### 7.2 Đo trên dữ liệu **có** sở thích: cơ chế là độ phủ điểm đến

Khách giả lập có sở thích thật và đã ghi sẵn chuyến kế tiếp (`target`, `next`). Thêm `eval_profile --syn-target`:

| | đoán đúng **món** chuyến sau (tgtHit@20) | đoán đúng **điểm đến** chuyến sau (nextDestHit@20) | themePrec |
|---|---|---|---:|
| production | 0.0000 | 0.4667 | 0.439 |
| P2+F14c | **+0,0125** [+0,0056, +0,0222] | **−0,2958** [−0,3306, −0,2583] | 0.769 |

Production **chưa bao giờ** đoán đúng món sẽ mua (0 / 720 khách); mọi ứng viên đạt 1,1–1,25 %. Nhưng ứng viên mất rất
nhiều độ phủ điểm đến, vì các món gần `u_long` nhất dồn vào ít điểm đến. **Đây là vấn đề của bước chọn danh sách, không
phải của trọng số** — vặn `W_POP` không sửa được (§3.4 report CI: pop 0,45 lấy lại temporal nhưng theme tụt còn 0,583).

### 7.3 Giải pháp: giới hạn 2 món / điểm đến khi không có chuyến mở

Giữ nguyên F14c, thêm giới hạn cứng vào bước MMR, chỉ ở nhánh không có chuyến mở
(`src/evaluation/recsys_bench/theme_study/dest_diversity.py`):

| Cấu hình | LLBO h@4 | temp h@20 | next h@20 | next h@4 | theme between | theme noisy_paired | nextDestHit@20 |
|---|---:|---:|---:|---:|---:|---:|---:|
| production | 0.5329 | 0.1587 | 0.0785 | 0.0256 | 0.439 | 0.376 | 0.4667 |
| P2+F14c | 0.5324 | 0.1252 | 0.0403 | 0.0185 | 0.769 | 0.703 | 0.1708 |
| P2+F14c + destCap1 | 0.5324 | 0.1226 | 0.0403 | 0.0185 | 0.717 | 0.670 | 0.5333 |
| **P2+F14c + destCap2** | 0.5324 | **0.1277** | **0.0469** | **0.0202** | 0.756 | 0.698 | **0.4181** |

destCap2 so với F14c: nextDestHit@20 **+0,2472** [+0,2153, +0,2792] (`between`) và **+0,1833** (`noisy_paired`), trả lại
0,013 theme; nexttrip +0,0065 [+0,0000, +0,0136] và temporal +0,0026 [−0,0065, +0,0129] — **hai cái sau chưa đạt ý nghĩa
thống kê**, đừng quảng cáo. So với production, khoảng cách độ phủ điểm đến còn **−0,0486** [−0,0889, −0,0056] thay vì
−0,2958.

Ô khám phá B (G4) trên đúng tổ hợp này: hit@4 **giống base đến bốn chữ số** ở cả LLBO (0,5324) và temporal (0,1045), thêm
món ở điểm đến khác cho 29,2 % khách có chuyến mở. Thay hẳn ô 4 thì mất 0,033 LLBO h@4 → giữ luật chỉ lấp ô trống. Ẩn món
đã xem vẫn rất tệ (0,5324 → 0,3986).

Thời gian xếp hạng (ranking-only, không phải API đầu-cuối): p95 38,63 ms → 38,54 ms (F14c) → 39,26 ms (destCap2), tức
**+0,63 ms**. Tiêu chí latency của G1 vẫn cần đo đầu-cuối trước deploy.

### 7.4 G2 cần chốt lại — ba lựa chọn

| | Nội dung | Đánh đổi |
|---|---|---|
| **(1)** | Chấp nhận **P2 + F14c + destCap2 + ô B** với nexttrip h@20 −0,0316 [−0,0409, −0,0218], temporal −0,0310, hiểu rằng hai chỉ số đó **không đo được lợi ích** trên dữ liệu seed hiện tại | Đi tiếp WP5 ngay. Rủi ro: con số thật chỉ biết khi có A/B hoặc sau khi sửa bộ sinh event |
| **(2)** | Làm **G6 / WP6 trước** (bộ sinh event có sở thích chủ đề: `seed_histories.py`, `docs/spec/MOCK_DATA_SPEC.md`), rồi đo lại và chốt G2 trên số mới | Đúng về phương pháp nhất. Chậm hơn. *(Đính chính 08/10: PRD không mô tả bộ sinh event; tiền lệ eval-v2 / append-v1 là profile opt-in + `MOCK_DATA_SPEC` §4.x + history, demo không đổi byte — **không** cần đề xuất PRD riêng.)* |
| **(3)** | Giữ nguyên production ở nhánh không có chuyến mở, chỉ triển khai phần **miễn phí**: P2 (không có chi phí nào phân biệt được) + ô khám phá B (hit@4 không đổi) | Không có rủi ro đo được, nhưng chỉ được +0,022 theme — gần như không giải quyết vấn đề gốc |

Không tự chọn thay người dùng (AGENTS.md §2, §8).

### 7.5 Lộ trình đã chọn (người dùng chốt 08/10)

**Làm theo giai đoạn — gộp cả ba lựa chọn:** (3) ship phần miễn phí trước (P2 + ô B + loại combo hai chiều, phạm vi mọi lần mua)
→ (2) G6 đổi bộ sinh event cho có sở thích, đo lại → (1) chốt lại G2 cho F14c + destCap2 trên số mới. Kèm: latency đầu-cuối là
điều kiện trước deploy ở mọi giai đoạn (tiêu chí: Δp95 `diagnostics.latencyMs` ≤ 50 ms, local, tổng và theo `strategy`);
coldstart + AC-REC-01/02 phải đo; PR đích `release-mvp-v2`. Kế hoạch chi tiết, gate và PR:
`docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md`. Ba đề xuất PRD: [C] loại sản phẩm đã mua + combo, [A] ô khám phá,
[B] F14c + destCap2 (chờ G6/G2) — xem §2 của plan đó.

### 7.6 Kết quả G6 — đầu vào để chốt lại G2 (09/10)

Dữ liệu event có sở thích chủ đề (profile seed `g6-pref-v1`, 5.000 khách, 70 % có chủ đề ẩn; chuyến liên tiếp cùng chủ đề
0,63–0,82 so với 0,38 ở khách không sở thích). Số đầy đủ: `src/evaluation/reports/eval-2026-10-09-recsys-g6-so-thich-do-lai.md`.

| C3 = P2 + F14c + destCap2 so với production | Kết quả | Luật đề nghị §7.4 / 7.5 |
|---|---|---|
| nexttrip **destHit@20** (đúng điểm đến chuyến sau) | **+0,0425** [+0,0213, +0,0631]; khách có chủ đề +0,0494 | D2 **đạt** |
| nexttrip hit@20 (đúng món, list 20) | **−0,0322** [−0,0425, −0,0219] — y hệt prodcopy | D1 **không đạt** (cận dưới ≤ −0,01) |
| nexttrip hit@4 (list 4 như trang chủ) | −0,0039 [−0,0097, +0,0019] | chưa phân biệt được |
| temporal h@20 / h@4 | −0,0227 [−0,0364, −0,0091] / −0,0061 (CI chứa 0) | D4 đạt |
| LLBO h@4 · coldstart h@4 | −0,0020 [−0,0040, −0,0003] · −0,0008 (CI chứa 0) | D3 đạt trong dung sai 0,01 |
| theme `between` / `noisy_paired` | +0,309 / +0,363 | đạt |
| tgtHit@20 / nextDestHit@20 giả lập | +0,0083 [+0,0014, +0,0167] / +0,017 (CI chứa 0) | D5 nửa đạt |

**Vì sao hit@20 món không hồi phục dù dữ liệu có sở thích:** G6 chỉ gắn sở thích ở mức *điểm đến*; *khách sạn nào* trong điểm
đến vẫn bốc theo độ phổ biến (Zipf). Công thức nào hạ pop cũng thua ở bước chọn món trong điểm đến — và thua *nhiều hơn* ở
khách có chủ đề (−0,040) dù đúng điểm đến hơn. Tune: T2 (pop 0,45 + destCap2) destHit +0,070, temporal trong nhiễu, nhưng
theme chỉ +0,135 / +0,200 (không đạt ≥ 0,15 ở `between`); T1 (F7 + destCap2) ≈ C3. **Không điểm nào trên đường đánh đổi đạt
cả D1 lẫn theme.**

**Cần người dùng chốt lại G2 với ba lựa chọn (không tự chọn):**

| | Nội dung | Căn cứ |
|---|---|---|
| **(a)** | Chấp nhận C3 với D1 định nghĩa lại trên **hit@4** (list khách thật nhìn thấy): −0,0039, CI chứa 0; bám sở thích hiện ở mức điểm đến (+0,043) và theme (+0,31 / +0,36) | Chi phí món ở list 20 là −0,032 nhưng bộ sinh chọn món theo pop nên chưa biết dữ liệu thật có vậy không |
| **(b)** | Chọn T2 (P2 + F14d pop 0,45 + destCap2): destHit +0,070, temporal không phân biệt được, nexttrip hit@20 −0,024; đổi lại theme chỉ +0,135 / +0,200 | Thận trọng hơn; phải nới tiêu chí theme ≥ 0,15 xuống ≈ 0,13 |
| **(c)** | Giữ production ở nhánh không chuyến mở; chỉ ship PR-A (P2 + ô B + loại combo); mở nghiên cứu G6 phiên bản 2 (sở thích ở mức thuộc tính sản phẩm) rồi quay lại | Đúng phương pháp nhất, chậm nhất |

### 7.7 Chốt của người dùng 09/10

- **G2 = (a)**: chấp nhận C3 (P2 + F14c + destCap2) với D1 định nghĩa lại trên nexttrip **hit@4** (CI chứa 0). Chi phí hit@20 món
  (−0,032) được ghi nhận là chưa phân biệt được giữa "bộ sinh chọn món theo pop" và dữ liệu thật; theo dõi sau deploy bằng
  `recommendation_logs` (đơn mua trùng list gợi ý) và G6 v2 nếu cần.
- **G5a**: chốt cả [A] (ô khám phá khi có chuyến mở) và [C] (không gợi lại món đã mua; combo ↔ thành phần). PRD
  `requirements.md` FR-REC-02, AC-REC-02, AC-REC-03 đã cập nhật cùng ngày; hai đề xuất chuyển sang `update-archive/`.
- Hệ quả: PR-A (P2 + loại combo + ô B) làm ngay; [B] trình chốt G5b với D1 trên hit@4 → PR-B.

## 6. Nếu chốt: những gì phải sửa trong engine (WP5.3, chưa làm)

Chỉ ghi để lượng hoá công việc; **không sửa trước khi có G5**.

- `src/backend/app/domain/recommendation/profile.py`
  - `build_profile`: `u_long` nhân độ tin cậy chuyến; cap lặp không bỏ purchase / add_to_cart khỏi `trip.events`
    (ca xfail `test_strong_events_weight_trip_vector` trong `src/evaluation/recsys_bench/tests/test_profile_variants.py`).
  - `score_candidates`: nhánh `profile.active_trip is None` theo công thức đã chọn; hằng mới (`W_*_BETWEEN`, và `Q_LOW` /
    `Q_HIGH` nếu chọn F14, hoặc vector trung bình catalog nếu chọn F13a) — cả hai gắn với model + `TEXT_BUILDER_VERSION`.
  - Tăng `ENGINE_RULES_VERSION`.
- `src/backend/app/application/recommendation/use_cases.py`: ô khám phá B sau `mmr_select` (G4 **đã chốt**).
- `mmr_select` cần nhận thêm mảng điểm đến để áp giới hạn `MAX_PER_DESTINATION` khi `profile.active_trip is None`
  (bản đo hiện monkeypatch `mmr_select` + `_LocalSpace`; production phải truyền `space.destination` vào hàm domain).
  Lưu ý `_LocalSpace` **lớn dần trong một request**: `build_profile` chạy khi không gian chỉ có unit của event, ứng viên
  được thêm sau — nên phải lấy mảng điểm đến ở thời điểm MMR, không phải lúc dựng profile.
- `explain()`: cân nhắc đồng bộ `because[]` với điểm thật (báo cáo gốc §3.D).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4 / §4.7; contract OpenAPI không đổi field.
- Unit test `domain` / `application` ≥ 80 % (DoD `docs/prd/implementation-plan.md` §4).
