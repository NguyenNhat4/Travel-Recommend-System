# RecSys bám sở thích — bảng quyết định chọn công thức (WP3)

- Ngày: 2026-10-08
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04 (`docs/prd/requirements.md` §1.3), AC-REC-02
- Plan: `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` WP3; gate G1–G4
- Nghiên cứu gốc: `docs/spec/bench/recsys-bam-so-thich-tong-hop.md`
- Số của tài liệu này: `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-ci.md` (CI ghép cặp, toàn bộ khách mỗi
  split, 3 seed khách giả lập) và `eval-2026-10-08-recsys-so-thich-moc-moi.md` (mốc engine)
- **Trạng thái: chờ người dùng chốt G1–G4. Chưa chốt thì không sửa engine (AGENTS.md §8).**

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

## 6. Nếu chốt: những gì phải sửa trong engine (WP5.3, chưa làm)

Chỉ ghi để lượng hoá công việc; **không sửa trước khi có G5**.

- `src/backend/app/domain/recommendation/profile.py`
  - `build_profile`: `u_long` nhân độ tin cậy chuyến; cap lặp không bỏ purchase / add_to_cart khỏi `trip.events`
    (ca xfail `test_strong_events_weight_trip_vector` trong `src/evaluation/recsys_bench/tests/test_profile_variants.py`).
  - `score_candidates`: nhánh `profile.active_trip is None` theo công thức đã chọn; hằng mới (`W_*_BETWEEN`, và `Q_LOW` /
    `Q_HIGH` nếu chọn F14, hoặc vector trung bình catalog nếu chọn F13a) — cả hai gắn với model + `TEXT_BUILDER_VERSION`.
  - Tăng `ENGINE_RULES_VERSION`.
- `src/backend/app/application/recommendation/use_cases.py`: ô khám phá B sau `mmr_select`, nếu G4 đồng ý.
- `explain()`: cân nhắc đồng bộ `because[]` với điểm thật (báo cáo gốc §3.D).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4 / §4.7; contract OpenAPI không đổi field.
- Unit test `domain` / `application` ≥ 80 % (DoD `docs/prd/implementation-plan.md` §4).
