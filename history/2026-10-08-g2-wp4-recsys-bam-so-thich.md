# Điều tra gate G2 và đo tổ hợp triển khai RecSys bám sở thích (WP4)

- Ngày: 2026-10-08
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs
- Tiếp theo: `history/2026-10-08-wp0-wp3-recsys-bam-so-thich.md`

## Mục tiêu

Người dùng chốt G1 = giữ ngưỡng điểm ước lượng 0,04 · G3 = P2 + F14c (pop 0,35) · G4 = có làm ô khám phá B ·
**G2 = chưa chấp nhận được** (mức giảm nexttrip). G2 và G3 xung đột: F14c có nexttrip h@20 −0,0381. Nhiệm vụ: tìm hiểu mức
giảm đó là chi phí thật hay hệ quả của dữ liệu, tìm cách giảm nó mà vẫn giữ F14c, và đo đúng tổ hợp sẽ triển khai (ô B,
latency). FR-REC-01, FR-REC-02, FR-REC-04, AC-REC-02.

Không sửa engine, không sửa PRD, không viết đề xuất: G2 chưa xong (AGENTS.md §8).

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/loss_analysis.py` — thêm: khách nào mất hit khi đổi công thức, chia theo độ phổ
  biến của target / số event / độ nhất quán hướng lịch sử (`trip_coherence`), và phân bố `strategy` của nhóm bị lật.
- `src/evaluation/recsys_bench/theme_study/dest_diversity.py` — thêm: giới hạn số món mỗi điểm đến ở bước MMR, chỉ khi
  không có chuyến mở (monkeypatch `mmr_select` + `_LocalSpace` trong tiến trình đo).
- `src/evaluation/recsys_bench/theme_study/rank_latency.py` — thêm: p50/p95/p99 thời gian xếp hạng một request cho từng
  cấu hình (ranking-only, không phải API đầu-cuối).
- `src/evaluation/recsys_bench/theme_study/eval_profile.py` — sửa: thêm `--syn-target` (đo dự đoán chuyến kế tiếp của
  khách giả lập: `tgtHit@4/@20`, `nextDestHit@4/@20`) và `--dest-cap N`; tên cấu hình thêm hậu tố `+destCapN`.
- `src/evaluation/recsys_bench/theme_study/eval_slots.py` — sửa: thêm `--profile` và dựng được scorer F13 / F14 (đã làm ở
  task trước, lượt này mới dùng).
- `src/evaluation/recsys_bench/theme_study/paired_ci.py` — sửa: `SYN_METRICS` thêm `tgtHit@*` / `nextDestHit@*`.
- `src/evaluation/recsys_bench/theme_study/results/2026-10-08-g2-wp4/` — thêm: 14 file JSON + `SHA256SUMS`.
- `src/evaluation/reports/eval-2026-10-08-recsys-g2-va-wp4.md` — thêm: report của lượt này.
- `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` — sửa: §7 mới (chốt của người dùng, điều tra G2, giải pháp
  destCap2, ô B, latency, ba lựa chọn để chốt lại G2); §6 thêm việc phải sửa `mmr_select`.
- `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` — sửa: trạng thái gate, WP4 đã làm, G6 thành điều kiện tiên quyết
  của G2.
- `history/2026-10-08-g2-wp4-recsys-bam-so-thich.md` — thêm: entry này.

Không commit: JSONL kết quả từng khách (~40 MB tổng), gói bàn giao và mọi thứ bung ra từ nó.

## Quyết định

- **Không tự chốt lại G2.** Đã trình ba lựa chọn (chấp nhận destCap2 / làm G6 trước / chỉ triển khai phần miễn phí) ở §7.4
  của tài liệu quyết định; người dùng chọn (AGENTS.md §2, §8).
- **Không cài `destCap` vào engine.** Bản hiện tại chỉ là monkeypatch trong tiến trình đo; muốn lên production thì
  `mmr_select` phải nhận mảng điểm đến — đó là WP5.3, sau khi chốt.
- Đo `nextDestHit` / `tgtHit` trên **khách giả lập** vì split thật không chứa tín hiệu sở thích (xem Kiểm tra); không sửa
  bộ sinh event (`seed_histories.py`) vì đó là thay đổi lệch PRD, cần gate G6 riêng.
- `trip_coherence` phải tính **sau khi trừ vector trung bình catalog**: trong không gian thô của e5-small cả 1.835 khách
  nexttrip đều ≥ 0,8, thước đo vô dụng. Ghi lại trong docstring để người sau không lặp lại.
- Latency đo ranking-only và nói rõ điều đó; tiêu chí latency của G1 vẫn còn trống vì cần đo đầu-cuối.
- `dest_diversity.install` giữ **đối tượng** `space` chứ không chụp `space.destination`: `_LocalSpace` lớn dần trong một
  request (ứng viên được thêm sau khi `build_profile` chạy), chụp sớm thì mảng quá ngắn → IndexError. Đã gặp và sửa.

## Kiểm tra

- **G2 — ba giả thuyết nhắm nhóm đều sai:** (a) 84 % mức mất nexttrip ở target thuộc nửa dưới độ phổ biến, tỷ lệ mất
  tương đối gần như nhau (−48 % so với −52 %); (b) mức mất *tăng* theo lịch sử (−0,016 ở <3 event → −0,042 ở ≥12 event);
  (c) đều khắp theo `coherence` (−0,032 … −0,046). 100 % khách bị lật hit → miss không có chuyến mở (đúng thiết kế).
- **Split thật không đo được lợi ích:** `seed_histories.py` dòng 344–346 gọi `plan_trip(w, rng, home)` cho từng chuyến, và
  dòng 160–161 `destination(self, rng)` bốc từ phân phối toàn cục theo cỡ điểm đến — **không có tham số khách**. Điểm đến
  chuyến sau độc lập với lịch sử khách, nên bộ dự đoán tối ưu là độ phổ biến toàn cục. Đây là kết luận đọc code, không
  phải đo.
- **Trên dữ liệu có sở thích (720 khách × 3 seed, CI ghép cặp):** production đoán đúng món chuyến sau **0,0 %** (0/720);
  mọi ứng viên 1,1–1,25 % (+0,0111 … +0,0125, có ý nghĩa). Nhưng nextDestHit@20 giảm −0,286 … −0,332 (có ý nghĩa) → cơ chế
  là mất **độ phủ điểm đến**.
- **destCap2 (toàn bộ khách mỗi split):** nextDestHit@20 +0,2472 [+0,2153, +0,2792] so với F14c, trả 0,013 theme; so với
  production khoảng cách còn −0,0486 thay vì −0,2958. nexttrip h@20 0,0403 → 0,0469 và temporal 0,1252 → 0,1277 —
  **CI chạm 0, chưa phân biệt được**, đã ghi rõ trong report. LLBO lệch đúng 0.
- **Ô khám phá B trên P2+F14c (G4):** hit@4 giống base đến bốn chữ số ở cả LLBO (0,5324) và temporal (0,1045); thêm món ở
  điểm đến khác cho 29,2 % khách có chuyến mở. Thay hẳn ô 4 mất 0,033 LLBO h@4. Ẩn món đã xem: 0,5324 → 0,3986.
- **Latency (ranking-only, máy không chạy job khác, 400 khách nexttrip, 3 lượt):** p95 38,63 ms (production) → 38,54 ms
  (F14c) → 39,26 ms (destCap2), Δp95 +0,63 ms.
- `parity_mismatch_llbo200 = 0` ở mọi lượt đo.
- `pytest src/evaluation/recsys_bench/tests`: 160 passed, 4 xfailed. `pytest src/backend/tests/architecture`: 8 passed.
- Thời gian chạy: `--syn-target` 270 s / 200 s; destCap1 477 s, destCap2 496 s; `eval_slots` toàn bộ khách; latency 3 arm.

## Còn lại / rủi ro

- **G2 chờ chốt lại** theo ba lựa chọn ở `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7.4. Chưa xong thì không sửa
  engine, không viết lại đề xuất PRD (WP5.1).
- `destCap` chưa có trong engine; nếu chốt thì `mmr_select` phải nhận mảng điểm đến (hằng mới `MAX_PER_DESTINATION`).
- Tiêu chí latency của G1 vẫn trống: cần `recsys_bench http_latency` hoặc API local (WP4.3 phần còn lại).
- `nextDestHit` của bộ sinh khách giả lập **vẫn** thưởng độ phổ biến, chỉ là trong phạm vi chủ đề — nên nó là bộ đo tốt
  nhất đang có, không phải bộ đo đúng thực tế.
- Nếu chọn lựa chọn (2) ở §7.4 thì phải tạo đề xuất PRD cho việc đổi bộ sinh event (gate G6) trước khi sửa
  `seed_histories.py` / `MOCK_DATA_SPEC.md`.
- `tgtHit@20` 1,1–1,25 % là 8–9 khách / 720 — tuyệt đối nhỏ dù CI loại trừ 0.
