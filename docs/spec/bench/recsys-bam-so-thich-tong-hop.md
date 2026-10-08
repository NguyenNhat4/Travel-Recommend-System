# RecSys có bám sở thích khách không — báo cáo cuối điều tra 07–08/10/2026

- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04 (`docs/prd/requirements.md` §1.4), AC-REC-02.
- Trạng thái: **nghiên cứu xong bước 1 và bước 2; chưa chọn cấu hình, chưa sửa engine theo nghiên cứu, chưa có gì lên production.**
  Bàn giao cho tqanh123 trên nhánh `feat/recSys_update` theo plan `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md`.
- Số thô và lệnh tái sinh: `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md`.
  File kết quả gốc (JSON, kèm SHA-256): `src/evaluation/recsys_bench/theme_study/results/2026-10-08/`.
- Đề xuất PRD liên quan (chờ chốt, **nội dung đã cũ**, xem §7): `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md`.
- Bản này thay bản tổng hợp viết lúc bước 2 còn chạy. Số trong bảng sinh thẳng từ file JSON, không chép tay.
- **Đã có phần tiếp (08/10, WP0–WP3 của plan):** mốc đo lại trên engine production
  (`src/evaluation/reports/eval-2026-10-08-recsys-so-thich-moc-moi.md`), CI ghép cặp + nhiều seed + nhiễu cùng khách
  (`eval-2026-10-08-recsys-so-thich-ci.md`), và **bảng quyết định chọn công thức**
  (`docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md`). Ba kết luận "chưa phân biệt được" ở §2.4 và §4.5 của tài liệu
  này đã được giải quyết ở đó; §4.2 có hai cột cần đính chính — xem ghi chú ngay dưới bảng.

## 0. Tóm tắt

1. **Vấn đề có thật.** Khi khách **không có chuyến đang mở**, gợi ý gần như không theo sở thích: khách thích núi chỉ 17 % món đúng
   chủ đề, thích phố 23 %, chọn ngẫu nhiên đã được 33 %. Ai cũng nhận Nha Trang / Phan Thiết / Phú Quốc.
2. **Hai nguyên nhân, phải sửa cả hai:**
   - *Phối hợp điểm:* cos của e5-small dồn sát nhau (p90 − trung vị ≈ 0,012) nên `0,15 · pop` lấn át phần sở thích.
     Sửa bằng cách đưa cos về cùng thang với pop **chỉ khi không có chuyến mở** (F7, F14).
   - *Dựng profile:* mỗi sản phẩm chỉ xem là một "chuyến" riêng, nặng ngang một chuyến đã mua; 75 % khách có nhiều chuyến xem hơn
     chuyến mua. Sửa bằng trọng số độ tin cậy chuyến (P2).
3. **Kết quả tốt nhất đo được** (khách giả lập, không chuyến mở): đúng chủ đề 0,438 → 0,76–0,78; khách lướt xem nhiễu 0,373 → 0,67–0,74.
   LLBO (khách đang có chuyến mở) không đổi.
4. **Cái giá:** nexttrip hit@20 giảm thật (0,074 → 0,026–0,031, có ý nghĩa thống kê); temporal hit@20 giảm 0,016–0,037 (chưa có ý nghĩa
   thống kê). Gần như toàn bộ mức giảm do **hạ ảnh hưởng của pop**, không phải do P2. Event CDP là giả lập chọn điểm đến theo độ
   phổ biến, nên hai split này thưởng cho món bán chạy — mức giảm là cận trên của chi phí, nhưng không được bỏ qua.
5. **Khuyến nghị (chưa chốt):** P2 + công thức F14 (hoặc F7) chỉ áp khi không có chuyến mở; bỏ P3; phần còn lại của P1 là việc nhỏ.
   Trước khi chốt cần CI ghép cặp và nhiều seed (plan WP2–WP3).
6. **Đính chính quan trọng:** lỗi "giới hạn lặp làm mất purchase" **đã được sửa trên `origin/main` và `release-mvp-v2`**
   (commit `9b703ba`). Nhánh `bench_search_recomSys` còn code cũ; nhánh bàn giao `feat/recSys_update` dựng từ production nên đã có.
   Test `production-known-bug` của Codex viết khi chạy trên engine cũ; trên engine mới nó vẫn xfail vì một kiểm khác (§5.1).

## 1. Xuất phát

Test production tối 07/10, tài khoản thật: xem 8 phòng ven biển (4 Nha Trang, 4 Vũng Tàu) → 4 gợi ý đều Vũng Tàu (`recent_activity`),
hỏi k = 8 nhận 4. Đúng thiết kế (có chuyến mở → khoá điểm đến, tối đa 2 món / loại). Câu hỏi mở rộng: khi **không** có chuyến mở,
gợi ý có theo sở thích không?

## 2. Dữ liệu, cách đo, nguồn gốc số

### 2.1 Dữ liệu

- **Bản sao production** `vota_prodcopy` (Postgres local, container `wt-seed-postgres-1` :55433, tải chỉ-đọc qua API GET của monitor
  lúc 08/10 01:49): 16.740 sản phẩm, 7.005 profile, 40.158 event, 3.991 search unit (= `ProductE5Small` production), 58 điểm đến.
- **Vector:** embed lại bằng `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`, `catalog-text-v2`,
  384 chiều (đúng job index production). File `.npy` 6 MB nằm ngoài repo; metadata ở `results/2026-10-08/vec_prodcopy_e5s.meta.json`.

### 2.2 Bộ đo

- **Split thật** (engine qua `OfflineEngine`, as_of 2026-10-08T00:00:00Z, 800 khách đầu theo id mỗi split, mọi cấu hình cùng tập):
  LLBO 800 (100 % đang có chuyến mở), temporal 775 (đủ), nexttrip 800. hit@20 / nDCG@10 trên list 20; hit@4 trên list 4 như trang chủ.
- **Khách giả lập theo chủ đề** (biển / núi / phố; nhãn 58 điểm đến gán tay, engine không đọc nhãn), 80 khách × 3 chủ đề × mỗi kịch bản:
  - `between`: 2–3 chuyến đã xong, không chuyến mở. Điểm đến mỗi chuyến **đúng chủ đề với xác suất 80 %** (`theme_exp.py:83`), không phải 100 %.
  - `open`: thêm 3 lượt xem trong 2 ngày (có chuyến mở). Mọi cấu hình đều 0,767 vì nhánh có chuyến mở giữ nguyên production.
  - `noisy`: như `between` + 5–8 lượt xem ở điểm đến khác chủ đề, 20–300 ngày trước (tỷ lệ xem / mua gần dữ liệu thật 4,26 / 1,52).
    **Là tập khách khác với `between`** (sinh tiếp từ cùng luồng random) — so `between` với `noisy` lẫn cả khác biệt lịch sử nền;
    so các cấu hình **trong cùng** `noisy` thì hợp lệ (cùng khách).
  - Chỉ số **theme** = tỷ lệ món trong list 4 thuộc đúng chủ đề khách (bỏ điểm đến "hỗn hợp"). Ngẫu nhiên ≈ 0,333.

### 2.3 Engine nào đã chạy (đọc kỹ trước khi trích số)

| Nhóm số | Engine | Ghi chú |
|---|---|---|
| F0–F12 (`formula_*`) | `release-mvp-v2 @ 85cea82`, worktree `test/newcrawl` | = production 08/10 (W 0,7/0,15/0,15, đã có sửa cap lặp, "hôm nay" theo giờ VN) |
| P0–P4, bước 2 (`profile_*`, `step2_*`) | working tree `bench_search_recomSys` (`c47fc35` + thay đổi chưa commit) | W 0,7/0,15/0,15 nhưng **chưa có** sửa cap lặp `9b703ba` và `local_today` |

Hai engine cho cùng số ở LLBO, temporal và theme (P0+F0 = F0). Khác duy nhất ở nexttrip nDCG@10 / hit@4 (0,0168 / 0,0163 so với
0,016 / 0,015) — khớp với việc sửa cap lặp chỉ chạm vài khách. Vì vậy "P0_prod" trong các bảng profile nghĩa là "engine của nhánh bench",
không phải production hiện tại. Sau khi merge `origin/main` phải đo lại mốc P0 (plan WP0).

### 2.4 Độ tin cậy thống kê

JSON chỉ lưu chỉ số tổng hợp, chưa lưu kết quả từng khách → **chưa có CI ghép cặp**. Ước lượng thô (z-test hai tỷ lệ độc lập; vì cùng
tập khách nên CI ghép cặp thật sẽ hẹp hơn — đây là ước lượng bảo thủ):

| So sánh | Chênh | SE | z | Kết luận |
|---|---:|---:|---:|---|
| nexttrip h@20: P0+F0 → P0+F7 | −0,035 | 0,012 | 3,0 | giảm thật |
| nexttrip h@20: P0+F0 → P2+F7 | −0,046 | 0,011 | 4,2 | giảm thật |
| nexttrip h@20: P0+F7 → P2+F7 | −0,011 | 0,009 | 1,3 | chưa phân biệt được |
| nexttrip h@20: P0+F0 → P0+F9 (pop 0,45) | −0,028 | 0,012 | 2,3 | giảm thật |
| temporal h@20: P0+F0 → P2+F7 | −0,028 | 0,018 | 1,6 | chưa phân biệt được |
| temporal h@20: P2+F7 → P2+F14 / F13a | −0,006 / −0,009 | 0,017 | ≤ 0,5 | như nhau |
| LLBO h@4: P0+F0 → P2+F7 | −0,001 | 0,025 | 0,0 | như nhau |

Theme: SE ≤ 0,032 cho 240 khách / kịch bản, ≤ 0,056 cho 80 khách / chủ đề (cận trên Bernoulli, một seed). Chênh ≥ 0,1 (F0 → F7,
P0 → P2 trong `noisy`) chắc chắn thật; chênh 0,02–0,08 giữa F7 / F13a / F14 **chưa kết luận được**.

## 3. Phát hiện

### A. Dựng profile — lượt xem lẻ lấn át sở thích dài hạn

- `build_profile`: event không có `eventGroupId` → chuyến riêng `_solo_<sản phẩm>`; mỗi vector chuyến chuẩn hoá về độ dài 1 rồi cộng
  vào `u_long`. Một sản phẩm chỉ xem nặng ngang một chuyến đã mua.
- Production: view và add_to_cart **không** có `eventGroupId` (0 / 15.476 view, 0 / 8.125 cart). Trung bình mỗi khách 1,52 chuyến mua và
  4,26 "chuyến" chỉ xem / thêm giỏ; 75 % khách có nhiều chuyến xem hơn chuyến mua. Trung vị 4 chuyến / khách, 63,5 % chuyến không có lần mua.
- Bằng chứng: trong `noisy`, cùng công thức F7, P0 0,447 → P2 0,666 (cùng khách, chênh 0,22 ≫ sai số).

### B. Phối hợp điểm — pop lấn át phần sở thích khi không có chuyến mở

- Đo trên đúng ma trận engine chấm mỗi request (`component_stats.json`, khách không chuyến mở, 150 request): cos 0,823–0,944,
  p90 − trung vị **0,012**; pop 0–1 (chia cho món bán chạy nhất), 60 % bằng 0, p90 0,282.
- Sau trọng số 0,7/0,15/0,15: món hợp gu hơn trung bình +0,010 điểm; món khá phổ biến +0,042; món bán chạy nhất +0,15.
- Có chuyến mở thì nhẹ hơn nhiều (cos ngắn hạn trải 0,030, pop p90 0,073) và mọi món cùng một điểm đến.

### C. Embedding và text

- **Cos dồn là đặc tính của e5**, không do text builder: cùng text, cos trung vị 2 món ngẫu nhiên — Cohere v3 0,49, bge-m3 0,50,
  gte-mb 0,61, eg2 0,71, e5-small 0,81.
- 6 cách dựng text (giữ e5-small, 1.200 khách sạn) đều cos 0,80–0,90. Builder hiện tại phân biệt điểm đến tốt nhất (AUC 0,94);
  **phân biệt chủ đề yếu ở mọi cách** (AUC 0,55–0,57, kể cả mô tả gốc) → mô tả khách sạn thiếu tín hiệu chủ đề (vấn đề dữ liệu).
  Chưa có ablation đủ để loại trừ hoàn toàn ảnh hưởng của text.
- Rà 3.991 text: không rỗng, không vượt 512 token (max 301). 21 % điểm tham quan chỉ còn tiêu đề; 33 % text tham quan chủ yếu tiếng Anh;
  10–13 % đoạn trích bị `_clip` cắt giữa câu; 253 khách sạn loại "cơ sở lưu trú"; combo tách thành phần sai ở `parse_combos`.
- Centering giãn thang (0,025 → 0,144) nhưng AUC chủ đề chỉ 0,563 → 0,574: sửa thang đo, không thêm thông tin.

### D. Các nhận định khác

| Nhận định | Kết quả kiểm |
|---|---|
| Giới hạn lặp 3 event làm mất purchase / ngày sử dụng | Lỗi có thật trong logic cũ, **đã sửa trên `origin/main` / `release-mvp-v2`** (`9b703ba`: tuổi, `ends_on`, món đã mua tính trên mọi event; cap chỉ giới hạn trọng số vector). Còn lại: purchase thứ 4+ vẫn không vào **vector** chuyến. Bản sao production: 10 event bị cap (7 view, 3 cart, 0 purchase), 8 / 5.599 khách — ảnh hưởng số liệu không đáng kể |
| Thiếu vector làm mất lịch sử | Cơ chế đúng; chưa đo tỷ lệ |
| `because[]` không khớp điểm thật | Đúng: `explain()` không tính chuẩn hoá từng chuyến, pop, MMR |
| Ứng viên cắt còn 200 trước MMR | Đúng; chưa đo độ phủ |
| 384 chiều quá nhỏ | Không có bằng chứng (bench Search cùng text: e5-small 0,615 vs eg2 768 chiều 0,613) |

## 4. Kết quả

Mã: **P** = cách dựng profile, **F** = công thức điểm khi không chuyến mở (có chuyến mở luôn chấm như production).

| Mã | Ý nghĩa |
|---|---|
| P0 | engine nhánh bench (xem §2.3) |
| P1 `capFix` | cap lặp giữ event **mới** nhất, không bao giờ bỏ purchase / add_to_cart |
| P2 `confidence` | `u_long` nhân độ tin cậy chuyến `min(1, Σ W_TYPE)` (1 view 0,2 · 1 cart 0,5 · 1 mua 1,0) |
| P3 `session` | gom event lẻ theo điểm đến, cách ≤ 14 ngày, thành một phiên |
| P4 | P1 + P2 + P3 |
| F0 | production `0,7·cos_s + 0,15·pop + 0,15·cos_l` |
| F7 | min-max cos trong request, `0,55 / 0,30 / 0,15` |
| F9 | như F7, pop 0,45 (bản thận trọng) |
| F12b | cos thô, `0,80 / 0,05 / 0,15` |
| F13a / F13b | trừ vector trung bình catalog khỏi vector món và khách (chỉ ở bước chấm), `0,7/0,15/0,15` · `0,55/0,30/0,15` |
| F14 | calibration phân vị cố định: `clip((cos − 0,8529) / (0,9387 − 0,8529), 0, 1)`, `0,55 / 0,30 / 0,15`; ngưỡng lấy từ tập calibration riêng (seed 99, 120 request) |

### 4.1 Công thức điểm, profile P0 (engine `85cea82`)

| Biến thể | LLBO h@4 | temp h@20 | temp h@4 | next h@20 | between (biển / núi / phố) |
|---|---:|---:|---:|---:|---|
| F0 production | 0.5737 | 0.1587 | 0.1135 | 0.0737 | 0.438 (0.91 / 0.17 / 0.23) |
| F1 min-max mọi lúc | 0.4188 | 0.1226 | 0.0942 | 0.025 | 0.782 |
| F4 min-max mọi lúc, pop 0,30 | 0.54 | 0.1316 | 0.1084 | 0.0338 | 0.776 |
| **F7** | **0.5737** | 0.129 | 0.1058 | 0.0387 | **0.776 (0.77 / 0.75 / 0.80)** |
| F8 (pop 0,25) | 0.5737 | 0.1277 | 0.1032 | 0.035 | 0.783 |
| F9 (pop 0,45) | 0.5737 | 0.1381 | 0.1135 | 0.0462 | 0.556 (0.89 / 0.28 / 0.50) |
| F10 (pop 0,60) | 0.5737 | 0.1561 | 0.1135 | 0.0712 | 0.391 |
| F11 (giãn cả pop) | 0.5737 | 0.129 | 0.1058 | 0.0387 | 0.776 (≡ F7) |
| F12b | 0.5737 | 0.1355 | 0.1071 | 0.0375 | 0.739 |

- Chuẩn hoá mọi lúc (F1–F6) làm hỏng LLBO; chỉ áp khi không chuyến mở (F7–F12) thì LLBO giữ nguyên tuyệt đối.
- `W_POP` là núm vặn giữa "bám sở thích" và "món bán chạy": 0,30 → 0,78; 0,45 → 0,56; 0,60 → như production.

### 4.2 Profile × công thức, split thật + khách giả lập (đủ chỉ số)

| Cấu hình | LLBO h@20 | LLBO nDCG@10 | LLBO h@4 | temp h@20 | temp nDCG@10 | temp h@4 | next h@20 | next nDCG@10 | next h@4 | between | noisy | open | nguồn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| P0+F0 | 0.8363 | 0.525 | 0.5737 | 0.1587 | 0.0954 | 0.1135 | 0.0737 | 0.016 | 0.015 | 0.438 | 0.373 | 0.767 | `profile_a.json` |
| P1+F0 | 0.8363 | 0.525 | 0.5737 | 0.1587 | 0.0954 | 0.1135 | 0.0737 | 0.016 | 0.015 | 0.438 | 0.373 | 0.767 | `profile_a.json` |
| P2+F0 | 0.8363 | 0.5221 | 0.5725 | 0.1548 | 0.0929 | 0.1123 | 0.0675 | 0.0151 | 0.0175 | 0.431 | 0.404 | 0.767 | `profile_b.json` |
| P3+F0 | 0.8375 | 0.5249 | 0.57 | 0.1652 | 0.0962 | 0.1148 | 0.0688 | 0.0176 | 0.02 | 0.43 | 0.357 | 0.767 | `profile_b.json` |
| P4+F0 | 0.8387 | 0.521 | 0.57 | 0.1652 | 0.0956 | 0.1161 | 0.0688 | 0.0173 | 0.0213 | 0.432 | 0.403 | 0.767 | `profile_c.json` |
| P0+F7 ¹ | 0.8363 | 0.525 | 0.5737 | 0.129 | 0.0895 | 0.1058 | 0.0387 | 0.01 | 0.0075 | 0.776 | 0.447 | 0.767 | `formula_prod_F7_F10.json` |
| **P2+F7** | 0.8363 | 0.5221 | 0.5725 | 0.1303 | 0.0884 | 0.1058 | 0.0275 | 0.0083 | 0.0063 | 0.763 | 0.666 | 0.767 | `profile_p2f7.json` |
| P4+F7 | 0.8387 | 0.521 | 0.57 | 0.1406 | 0.0912 | 0.1097 | 0.03 | 0.0101 | 0.01 | 0.763 | 0.674 | 0.767 | `profile_c.json` |
| P2+F12b | 0.8363 | 0.5221 | 0.5725 | 0.1329 | 0.0887 | 0.1058 | 0.03 | 0.0089 | 0.0063 | 0.717 | 0.603 | 0.767 | `step2_x.json` |
| P2+F13a | 0.8363 | 0.5221 | 0.5725 | 0.1213 | 0.0835 | 0.0994 | 0.025 | 0.0071 | 0.0063 | 0.772 | **0.744** | 0.767 | `step2_x.json` |
| P2+F13b | 0.8363 | 0.5221 | 0.5725 | 0.1277 | 0.0863 | 0.1045 | 0.0312 | 0.0089 | 0.0063 | 0.691 | 0.661 | 0.767 | `step2_y.json` |
| **P2+F14** | 0.8363 | 0.5221 | 0.5725 | 0.1239 | 0.0874 | 0.1045 | 0.0262 | 0.0073 | 0.0063 | **0.782** | 0.723 | 0.767 | `step2_y.json` |

¹ Split thật của P0+F7 từ engine `85cea82`; cột `noisy` từ `profile_noisy.json`. Mọi lượt bước 1–2 kiểm khớp bản viết lại với
`build_profile` của nhánh: `parity_mismatch_llbo200 = 0`.

**Đính chính 08/10 (WP0 — đo lại trên engine production của `feat/recSys_update`, cùng cỡ mẫu 800 khách):** 58 / 60 ô có số
ở cả hai engine khớp đến chữ số cuối; **hai cột `next nDCG@10` và `next h@4` phải thay** bằng số của engine production,
cao hơn đều +0,0008 … +0,0009 và +0,0012 … +0,0013 (= 1 khách / 800):

| Cấu hình | next nDCG@10 (bảng trên → engine production) | next h@4 (bảng trên → engine production) |
|---|---|---|
| P0+F0 | 0,016 → **0,0168** | 0,015 → **0,0163** |
| P2+F0 | 0,0151 → **0,016** | 0,0175 → **0,0187** |
| P2+F7 | 0,0083 → **0,0091** | 0,0063 → **0,0075** |
| P2+F13a | 0,0071 → **0,0079** | 0,0063 → **0,0075** |
| P2+F14 | 0,0073 → **0,0081** | 0,0063 → **0,0075** |

Chi tiết, parity mở rộng và lệnh tái sinh: `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-moc-moi.md`.

Thêm một cảnh báo về chính bảng này: cỡ mẫu "800 khách đầu theo id" **lệch** so với toàn bộ khách của mỗi split (LLBO h@20
0,836 so với 0,808; nexttrip h@20 của P2+F14 0,025 so với 0,035). Số dùng để quyết định nằm ở report CI
(`eval-2026-10-08-recsys-so-thich-ci.md`, toàn bộ khách), không ở bảng này.

### 4.3 Khách giả lập theo chủ đề (chi tiết)

| Cấu hình | between (biển / núi / phố) | noisy (biển / núi / phố) | số điểm đến (noisy) | top-3 điểm đến (noisy) |
|---|---|---|---:|---|
| P0+F0 | 0.438 (0.909 / 0.169 / 0.234) | 0.373 (0.85 / 0.113 / 0.156) | 13 | Nha Trang 243, Phan Thiết 241, Phú Quốc 237 |
| P0+F7 | 0.776 (0.773 / 0.752 / 0.803) | 0.447 (0.597 / 0.362 / 0.38) | 43 | Nha Trang 142, Cao Bằng 46, Hội An 27 |
| P1+F7 | 0.776 (0.773 / 0.752 / 0.803) | 0.447 (0.597 / 0.362 / 0.38) | 43 | như P0+F7 |
| P2+F0 | 0.431 (0.912 / 0.163 / 0.219) | 0.404 (0.875 / 0.15 / 0.188) | 16 | Nha Trang 244, Phan Thiết 240, Phú Quốc 238 |
| P2+F7 | 0.763 (0.817 / 0.735 / 0.738) | 0.666 (0.815 / 0.528 / 0.654) | 42 | Nha Trang 129, Hội An 39, TP. Hồ Chí Minh 33 |
| P3+F7 | 0.778 (0.804 / 0.768 / 0.762) | 0.287 (0.438 / 0.225 / 0.2) | 42 | Nha Trang 148, Cao Bằng 58, Mỹ Tho 23 |
| P4+F7 | 0.763 (0.824 / 0.726 / 0.74) | 0.674 (0.818 / 0.545 / 0.658) | 42 | Nha Trang 129, Hội An 39, TP. Hồ Chí Minh 33 |
| P2+F12b | 0.717 (0.804 / 0.68 / 0.668) | 0.603 (0.782 / 0.476 / 0.551) | 39 | Nha Trang 176, TP. Hồ Chí Minh 45, Phú Quốc 28 |
| P2+F13a | 0.772 (0.791 / 0.772 / 0.753) | 0.744 (0.832 / 0.688 / 0.714) | 42 | Phú Quốc 66, Phan Thiết 60, Sa Pa 57 |
| P2+F13b | 0.691 (0.866 / 0.571 / 0.637) | 0.661 (0.88 / 0.501 / 0.603) | 40 | Phú Quốc 188, Đà Nẵng 76, Phan Thiết 70 |
| P2+F14 | 0.782 (0.793 / 0.794 / 0.76) | 0.723 (0.79 / 0.684 / 0.695) | 43 | Nha Trang 56, Hội An 37, Phú Quốc 31 |

### 4.4 Ô khám phá khi đang có chuyến mở (profile production, F0)

- Chọn món ở điểm đến khác theo `cos(u_long, v)`: đúng chủ đề 0,792 (ngẫu nhiên 0,333; theo món vừa xem 0,462).
- **Lấp ô trống** (list có chuyến mở trung bình 3,44 món vì giới hạn 2 món / loại): LLBO h@4 0,574 và temporal h@4 0,114 **không đổi**;
  thêm món ở điểm đến khác cho 29 % khách. Thay hẳn ô 4: LLBO h@4 −0,03 — không khuyến nghị.
- **Không ẩn món đã xem:** 29,2 % mục tiêu LLBO đã được xem trước; ẩn → LLBO h@4 0,574 → 0,463, temporal h@4 0,114 → 0,039.

### 4.5 Đọc kết quả

1. **Cái giá về độ chính xác đến từ công thức, không từ P2.** Cùng F0, P2 chỉ đổi temporal −0,004, nexttrip −0,006. Đổi F0 → F7 trên P0:
   temporal −0,030, nexttrip −0,035. P0+F7 → P2+F7: nexttrip −0,011 (z 1,3, chưa phân biệt được).
2. **P2 là cải thiện chắc nhất:** `noisy` +0,22 với F7, +0,28 với F14 (so P0+F7). Nhưng P2 **chỉ có tác dụng khi đi cùng** F7 / F13 / F14;
   với F0 pop vẫn lấn át (`noisy` 0,373 → 0,404).
3. **P3 có hại** (`noisy` 0,447 → 0,287): gom các lượt xem đúng gu trước khi mua thành một phiên làm giảm số "chuyến" đúng gu, còn lượt
   xem nhiễu ở nhiều điểm đến vẫn tách riêng. Giảm số chuyến 4 → 2 chỉ chứng minh thuật toán có gom, không chứng minh gom tốt. Loại P3.
   P4 − P2 = +0,008 ở `noisy`, không có ý nghĩa.
4. **P1 không đổi số nào** — bộ đo không chứa tình huống kích hoạt lỗi, và phần quan trọng của lỗi đã sửa trên main (§3.D).
5. **Bước 2:**
   - **F14** — `between` cao nhất (0,782), `noisy` 0,723, phân bố điểm đến đều nhất (Nha Trang 56 lượt so với 129 của F7), ngưỡng cố định nên
     không phụ thuộc tập ứng viên của request (min-max theo request của F7 có thể kéo nhiễu khi ứng viên sát nhau). Nhược: phải calibrate lại
     khi đổi model / text builder.
   - **F13a** — `noisy` cao nhất (0,744) nhưng temporal / nexttrip thấp nhất (0,121 / 0,025). Chỉ center ở **bước chấm**: lấy ứng viên
     (Weaviate) và MMR vẫn ở không gian cũ, profile không dựng lại từ vector đã center. Thua ở đây không có nghĩa centering nói chung kém.
   - **F12b, F13b** kém F7 → loại.
   - F7 / F13a / F14 **chưa phân biệt được** về temporal / nexttrip (z ≤ 0,5) và chênh theme 0,02–0,08 chưa có CI.

## 5. Kiểm định chéo và đính chính

### 5.1 Test "mất purchase" (`src/evaluation/recsys_bench/tests/test_profile_variants.py`, do Codex thêm)

- Chạy lại 08/10 16:30 (env `vsf2`): cùng `test_parity.py`, `test_engine_no_leak.py` → **20 passed, 2 xfailed**.
- Ca xfail `production-known-bug` gọi `build_profile` **của nhánh bench** (chưa có `9b703ba`). Chạy cùng kịch bản (3 view rồi purchase cùng
  chuyến, cả hai thứ tự đầu vào) với `build_profile` của `origin/main`:

  | Kiểm | nhánh bench | `origin/main` |
  |---|---|---|
  | `bought_units`, `purchased_taxonomies` | rỗng (lỗi) | đúng |
  | `ends_on`, `active_trip`, `strategy` | None / không / `long_term` (lỗi) | 20/10 / có / `cross_vertical` |
  | purchase nằm trong `trip.events` (vào vector chuyến) | không | **không** |

  → Production đã đúng về nghiệp vụ; chỉ còn việc purchase thứ 4+ không góp vào vector chuyến. Test hiện gộp cả hai kiểm vào một ca nên
  sau khi merge main vẫn xfail vì lý do khác — cần tách (plan WP1).

### 5.2 Nhận xét của reviewer (Codex) — đã đối chiếu

| Nhận xét | Đánh giá |
|---|---|
| P1 không đổi số ≠ đã kiểm chứng lỗi | Đúng; bổ sung: lỗi nghiệp vụ đã sửa trên main |
| `between` và `noisy` là khách khác nhau | Đúng (`eval_profile.py` sinh nối tiếp từ một `rng`); so cấu hình trong cùng kịch bản vẫn hợp lệ |
| Xác suất đúng chủ đề 80 % chứ không phải "mua hoàn toàn đúng gu" | Đúng (`theme_exp.py:83`) |
| Giảm số chuyến 4 → 2 không chứng minh gom phiên tốt | Đúng, P3 thua |
| F13 chỉ center ở bước chấm | Đúng |
| "Nằm trong sai số" chưa có cơ sở thống kê | Đúng; §2.4 thêm ước lượng thô, CI ghép cặp vẫn là việc phải làm |
| "P2+F7 giảm khả năng đoán mua" | Đúng về số; bổ sung: phần lớn do công thức (§4.5.1) |

## 6. Phương án khuyến nghị (chưa chốt)

1. **Profile:** P2. Phần còn lại của P1 (purchase / cart luôn vào vector chuyến) làm cùng vì đúng logic, không kỳ vọng đổi số.
2. **Công thức khi không chuyến mở:** ứng viên chính **F14**, dự phòng **F7**. Có chuyến mở giữ nguyên production. Không chọn F13a trừ khi
   thử centering toàn phần (ứng viên + profile + MMR) và thắng.
3. **Ô khám phá B** (đổi hành vi FR-REC-02): lấp ô trống bằng món ở điểm đến khác theo `u_long`, mỗi điểm đến 1 món, xếp sau món tại X.
4. Giữ việc hiện lại món đã xem.

**Tiêu chí nghiệm thu đề nghị (người dùng chốt trước khi chọn):**

| Chỉ số | Ngưỡng đề nghị |
|---|---|
| LLBO h@4 | không giảm quá 0,01 (CI ghép cặp chứa 0) |
| theme `between` và `noisy` | tăng ≥ 0,15 so với production, cận dưới CI > 0,10 |
| temporal h@20 | giảm ≤ 0,03 |
| nexttrip h@20 | báo riêng, ghi rõ là cận trên do dữ liệu giả lập; cần người dùng chấp nhận mức giảm |
| `open` | không đổi |
| latency p95 `/recommendations` | không tăng quá 50 ms |

## 7. Trạng thái code, nhánh, tài liệu (08/10, sau khi push)

- Bàn giao nằm trên **`feat/recSys_update`**, tạo từ `release-mvp-v2` @ `6f77e80` (= code production 08/10). Bản cùng nội dung trên
  `bench_search_recomSys` (`0ccc948`) chạy engine cũ — không làm tiếp ở đó.
- Engine của `feat/recSys_update` **đã có** `9b703ba` (sửa cap lặp, "hôm nay" theo giờ VN), trọng số 0,7/0,15/0,15 và `LocalE5Embedder`
  (`embed_prodcopy.py` chạy được). Test `recsys_bench` trên nhánh: 138 passed, 2 xfailed.
- Số bước 1–2 trong báo cáo này chạy trên engine cũ của `bench_search_recomSys` (§2.3) → phải đo lại mốc trên engine này (plan WP0).
  Kiểm nhanh 08/10: `profile_variants` khớp `build_profile` của nhánh này 0/200 khách LLBO (parity chỉ so một số trường).
- `origin/main` vẫn 0,6/0,25/0,15 và khác `release-mvp-v2` ở phần recommendation.
- Đề xuất PRD `2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` (chờ chốt) chỉ có F7 + ô B; chưa có P2, F14, tiêu chí §6. Phải viết lại
  trước khi trình chốt.
- Engine production: chưa sửa theo nghiên cứu này. Không có gì deploy.

## 8. Việc còn lại

Chi tiết, thứ tự, checklist: `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md`. Tóm tắt:

1. Đồng bộ nhánh, đo lại mốc trên engine mới (WP0). 2. Tách test purchase (WP1). 3. Lưu kết quả từng khách, CI ghép cặp, nhiều seed,
`noisy` cùng khách (WP2). 4. Chọn công thức theo tiêu chí đã chốt (WP3). 5. Đo đúng tổ hợp sẽ triển khai + latency (WP4).
6. Viết lại đề xuất PRD → người dùng chốt → PRD → engine / spec / test (WP5). 7. Bước 3 dữ liệu và tracking (WP6).

## 9. Caveat

1. Event CDP là giả lập, chọn điểm đến theo độ phổ biến; temporal / nexttrip không đo được lợi ích bám sở thích.
2. Nhãn chủ đề 58 điểm đến gán tay; 10 điểm "hỗn hợp" không chấm; Hội An / Hạ Long / Ninh Bình có thể tranh cãi.
3. Kịch bản `noisy` giả lập, chủ đề lượt xem nhiễu ngẫu nhiên; một seed.
4. Mẫu 800 khách / split (LLBO đủ 4.072, nexttrip 1.835).
5. Chưa đo latency các biến thể.
6. Tất cả offline trên bản sao; chưa có A/B hay log impression thật.

## 10. File

| Loại | Đường dẫn |
|---|---|
| Script đo | `src/evaluation/recsys_bench/theme_study/` — `theme_exp.py` (khách giả lập, nhãn, ô khám phá), `eval_formula.py` (F0–F12), `eval_profile.py` (P × F, bước 2), `profile_variants.py`, `step2_scorers.py` (F13, F14), `eval_slots.py`, `component_stats.py`, `dump_prod.py`, `embed_prodcopy.py` |
| Test | `src/evaluation/recsys_bench/tests/test_profile_variants.py` |
| Kết quả gốc | `src/evaluation/recsys_bench/theme_study/results/2026-10-08/` (+ `SHA256SUMS`; `formula_prod_F7_F10.json` trích nguyên văn từ log vì script cũ crash sau khi in số) |
| Ngoài repo (máy người chạy) | `~/code/recsys-theme-2026-10-08/`: vector `vec_prodcopy_e5s.npy` + `.ids.json`, log gốc, `prodcopy.env` (DSN — không chia sẻ qua git); DB `vota_prodcopy` trong `wt-seed-postgres-1` :55433 |
| Report số thô | `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` |
| Đề xuất PRD | `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` |
| Plan bàn giao | `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` |
| History | `history/2026-10-08-*` (9 entry trước + `bao-cao-cuoi-va-ban-giao-recsys-so-thich`) |
