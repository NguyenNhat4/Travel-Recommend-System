# Tiếp nhận bàn giao RecSys bám sở thích: WP0–WP3 (mốc mới, test purchase, CI ghép cặp, chọn công thức)

- Ngày: 2026-10-08
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Nhận gói bàn giao `recsys-theme-2026-10-08-ban-giao.zip` (phần ngoài git: dump `vota_prodcopy`, vector `.npy`, log) và làm
WP0–WP3 của `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md`: dựng môi trường, đo lại mốc trên engine production, tách
test mất purchase, đo lại **có thống kê** (CI ghép cặp, nhiều seed, kịch bản nhiễu cùng khách), và dựng bảng quyết định chọn
công thức. FR-REC-01, FR-REC-02, FR-REC-04, AC-REC-02.

Không sửa engine (`src/backend`), không sửa PRD, không chốt đề xuất: WP4–WP5 chờ gate G1–G5 của người dùng (AGENTS.md §8).

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/profile_variants.py` — sửa: viết lại theo `build_profile` của nhánh này (dict
  `every`): tuổi chuyến, `ends_on`, `purchased_taxonomies`, `bought_units` tính trên **mọi** event, cap chỉ giới hạn trọng số
  vector. Bản cũ tính trên event còn lại sau cap = luật trước `9b703ba`.
- `src/evaluation/recsys_bench/theme_study/eval_profile.py` — sửa: parity mở rộng từ 3 lên 8 phép so (thêm `bought_units`,
  `n_events`, `strategy`, mọi trường của `Trip`, vector từng chuyến) và trả thêm `parity_mismatch_by_field`; thêm
  `--per-user-out` (JSONL mỗi khách), `--scenarios`, `--syn-seeds`, `--f14-cal-profile`, `--f14-cal-seed`; `F14_WEIGHTS` cho
  bốn mức `W_POP` (0,25 / 0,30 / 0,35 / 0,45); lọc khách giả lập theo `scenario` thay vì tiền tố uid; calibration F14 gọi helper dùng chung.
- `src/evaluation/recsys_bench/theme_study/theme_exp.py` — sửa: tách `add_noise_views` khỏi nhánh `noisy` của `make_user`
  (giữ nguyên từng lời gọi rng), thêm `with_noise` dựng kịch bản `noisy_paired` (bản sao khách `between` + lượt xem nhiễu),
  `make_user` trả thêm `scenario`.
- `src/evaluation/recsys_bench/theme_study/step2_scorers.py` — sửa: thêm `calibrate_quantile` (ngưỡng q của F14) để
  `eval_profile` và `eval_slots` dùng cùng một bản; trả q đủ độ chính xác kèm `q_display` 4 chữ số.
- `src/evaluation/recsys_bench/theme_study/eval_slots.py` — sửa: thêm `--profile` và `--f14-cal-seed`, dựng được scorer
  F13 / F14 (chuẩn bị WP4.1: ô khám phá phải đo trên đúng tổ hợp sẽ triển khai, không phải profile production + F0).
- `src/evaluation/recsys_bench/theme_study/paired_ci.py` — thêm: bootstrap ghép cặp 2.000 lần, CI 95 %, `noise_effect`
  (ghép `noisy_paired` về khách `between` qua `baseUid`), `seed_spread`.
- `src/evaluation/recsys_bench/theme_study/tables.py` — thêm: dựng bảng Markdown từ JSON kết quả (bảng trong report sinh
  bằng script, không chép tay như bàn giao trước).
- `src/evaluation/recsys_bench/theme_study/eval_formula.py` — sửa: `eval_split` nhận `sink` / `row_base` để ghi kết quả
  từng khách; mặc định không đổi hành vi.
- `src/evaluation/recsys_bench/tests/test_profile_variants.py` — sửa: tách ca `production-known-bug` thành
  `test_purchase_state_survives_repeat_cap` (production **pass**, bỏ xfail) và `test_strong_events_weight_trip_vector`
  (production + P2 xfail strict tới WP5.3; P1 / P4 pass); thêm P2 vào bộ builder; docstring ghi rõ "production" là
  `build_profile` của `src/backend` trên nhánh này.
- `src/evaluation/recsys_bench/tests/test_paired_ci.py` — thêm: 14 test cho `paired_ci` (chênh hằng số, hai cấu hình giống
  nhau, ghép cặp hẹp hơn độc lập, chỉ ghép khách có ở cả hai, tái lập theo seed, `noise_effect`, `seed_spread`).
- `src/evaluation/recsys_bench/theme_study/results/2026-10-08-wp0-wp3/` — thêm: 13 file JSON (10 kết quả đo + 3 `ci_*`)
  + `SHA256SUMS`.
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-moc-moi.md` — thêm: report WP0 (mốc mới so bảng cũ).
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-ci.md` — thêm: report WP2–WP3 (CI ghép cặp, nhiều seed, nhiễu
  cùng khách, biến thể F14, độ bền calibration).
- `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` — thêm: bảng quyết định chọn công thức + khuyến nghị + 4 gate chờ chốt.
- `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` — sửa: thêm dòng trỏ sang hai report mới và tài liệu quyết định; đính
  chính hai cột nexttrip của §4.2.
- `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` — sửa: tích checklist WP0–WP3, ghi quyết định cỡ mẫu và lệch nhỏ
  so với plan ở WP2.3.
- `history/2026-10-08-wp0-wp3-recsys-bam-so-thich.md` — thêm: entry này.

Không commit: `recsys-theme-2026-10-08-ban-giao.zip` và mọi thứ bung ra từ nó (dump 19 MB, `.npy` 6 MB, log), file JSONL
kết quả từng khách (~15 MB tổng). Theo yêu cầu người dùng và tiền lệ bàn giao trước (§2.3 của plan).

## Quyết định

- **Giữ nguyên tên kịch bản `noisy`** cho cohort độc lập cũ và thêm `noisy_paired`, thay vì đổi tên cohort cũ như plan WP2.3
  ghi. Lý do: khách giả lập sinh tuần tự từ một `rng`, nên đổi tên / đổi thứ tự là đổi luôn bộ khách và số cũ không tái sinh
  được. Cách này giữ `noisy` byte-exact (đã kiểm) và vẫn có cohort ghép cặp.
- **Dùng toàn bộ khách mỗi split** cho WP2 (LLBO 4.072 / temporal 775 / nexttrip 1.835) chứ không phải 800: trên máy này một
  cấu hình đủ ba split mất ~4 phút, và mẫu "800 khách đầu theo id" lệch thật (LLBO h@20 0,836 so với 0,808; nexttrip h@20
  0,025 so với 0,035). Riêng lượt WP0 vẫn chạy ở 800 để so được với bảng cũ.
- **Độ tin cậy chuyến của P2 vẫn tính trên event sau cap** (không đổi sang "mọi event") để P2 không đổi nghĩa giữa hai lượt
  đo; đã ghi chú trong code.
- **F14 giữ ngưỡng q chưa làm tròn** (như lượt 08/10); `q_display` 4 chữ số chỉ để in và để khớp công thức trong báo cáo.
- Không chạy `embed_prodcopy.py`: dùng `.npy` của gói bàn giao, `meta.json` khớp revision `614241f…`.
- Không sửa `docs/prd/`, không sửa đề xuất `2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` (vẫn `chờ chốt`, nội dung cũ):
  viết lại nó là WP5.1, sau khi người dùng chốt G1–G4.
- Không xử lý WP7.1 (`askpass.cmd` chứa mật khẩu trên `origin/fix/search-production`): việc đổi mật khẩu và sửa lịch sử
  nhánh khác là của chủ nhánh, không tự làm.

## Kiểm tra

- `sha256sum -c SHA256SUMS` trên gói bàn giao: **18/18 OK**.
- `pg_restore` vào container `vota-prodcopy-pg` (postgres:16.15, 127.0.0.1:55433): `cdp.products` 16.740 · `cdp.events`
  40.158 · `cdp.profiles` 7.005 · `catalog.combo_items` 442 · `catalog.product_meta` 3.991 search unit / 3.254
  recommendable — khớp `HUONG-DAN.txt`.
- `parity_mismatch_llbo200 = 0` và `parity_mismatch_by_field = {}` ở **mọi** lượt đo (8 phép so).
- Hồi quy số cũ: mọi chỉ số theme của bản 08/10 ra **y nguyên** sau khi viết lại `profile_variants` và tách
  `add_noise_views` — P0+F0 between 0,438 / noisy 0,373; P2+F0 0,431 / 0,404; P0+F7 0,776 / 0,447; P2+F7 0,763 / 0,666;
  P2+F13a 0,772 / 0,744; P2+F14 0,782 / 0,723. Calibration F14 trên P2 ra đúng `q = 0,8529 / 0,9387` như báo cáo cuối.
- `pytest src/evaluation/recsys_bench/tests`: **160 passed, 4 xfailed** (bàn giao: 138 passed, 2 xfailed; chênh là 17 test
  `paired_ci` + các ca tách ra của WP1).
- `pytest src/evaluation/recsys_bench/tests/test_profile_variants.py`: 15 passed, 4 xfailed.
- `pytest src/backend/tests/architecture`: 8 passed.
- `PYTHONUTF8=1 pytest src/backend/tests/unit -k "recommend or profile"`: 52 passed. **Cần `PYTHONUTF8=1` trên Windows**:
  không có nó thì pytest lỗi collection `UnicodeDecodeError: 'charmap' codec` ở 17 file — lỗi môi trường có sẵn, không do
  thay đổi của task này (task không chạm `src/backend`). Cùng lý do, mọi lệnh đo cần `PYTHONIOENCODING=utf-8`.
- Không chạy `validate_contract.py`: task không chạm contract hay mock (AGENTS.md §4).
- Thời gian chạy (máy người nhận, tối đa 2 tiến trình song song): 800 khách × 4 cấu hình 643 s; 800 × 2 cấu hình 327 s;
  toàn bộ khách × 4 cấu hình 1.892 s, × 2 cấu hình 981 s / 955 s, × 1 cấu hình 499 s; khách giả lập 3 seed × 4 cấu hình 70 s.
- Không gọi Weaviate ở bất kỳ lượt nào (`--vec npy:`, `WEAVIATE_URL` trỏ `127.0.0.1:59999`).

## Kết quả chính (chi tiết ở hai report và tài liệu quyết định)

- **WP0:** bảng §4.2 của báo cáo cuối đúng trên engine production, trừ hai cột `next nDCG@10` / `next h@4` (lệch
  +0,0008 … +0,0013, engine mới tốt hơn). Không cần đo lại nghiên cứu.
- **P2 gần như miễn phí:** trên split thật mọi chênh so với production có CI chứa 0, trừ LLBO nDCG@10 −0,0031
  [−0,0043, −0,0019]. Nhưng P2 mua +0,175 theme ở khách có lịch sử lướt xem.
- **Không thể chỉ sửa công thức:** đo trên **cùng một khách**, thêm 5–8 lượt xem lệch chủ đề làm F7-không-P2 mất 0,294
  theme (0,787 → 0,493); có P2 thì chỉ mất 0,093. Lịch sử production không sạch (4,26 chuyến chỉ xem / 1,52 chuyến mua).
- **Nhánh có chuyến mở không bị động tới** — chứng minh ở mức từng khách: `open` và cả ba chỉ số LLBO của P0+F7 lệch
  đúng 0, `nDiscordant = 0`.
- **Hai kết luận của báo cáo cuối đổi:** (1) F14 hơn F7 thật (theme +0,023 / +0,056) với giá 0,0076 nexttrip h@20;
  (2) ở cỡ mẫu đầy đủ F13a **không** còn thua F14 ở temporal / nexttrip (CI chứa 0) và hơn ở `noisy_paired` (+0,028),
  nên lý do loại F13a ở §6 báo cáo cuối không còn đứng được.
- **P2+F14c (pop 0,35) hơn P2+F7 ở theme (+0,035) mà không có chi phí nào phân biệt được.** F14b (pop 0,25) bị F13a
  trội; F14d (pop 0,45) bị F7 trội và không đạt tiêu chí theme ≥ 0,15.
- **F14 không nhạy với tập calibration:** 3 seed → `q` lệch ±0,3 %, kết quả lệch ≤ 0,006.
- Ngưỡng temporal 0,03 của tiêu chí đề nghị **không phân biệt được** bằng dữ liệu hiện có (temporal chỉ 775 khách, CI
  ±0,015; chênh temporal giữa các ứng viên có CI chứa 0) — đã nêu hai cách xử lý để người dùng chọn ở G1.

## Còn lại / rủi ro

- **Chờ người dùng chốt G1–G4** (`docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §5). Chưa chốt thì không sửa engine.
- Chưa đo **latency** (WP4.3): cần `recsys_bench http_latency` hoặc API local, nên tiêu chí "p95 không tăng quá 50 ms" của
  G1 còn trống.
- Chưa chạy ô khám phá B trên tổ hợp P2 + công thức đã chọn (WP4.1): `eval_slots.py` đã có `--profile` và F13/F14 nhưng
  chưa chạy vì còn chờ G3 / G4.
- JSONL kết quả từng khách không nằm trong git; muốn dựng lại bảng CI thì chạy lại hai lệnh ghi trong report (khoảng 25 phút).
- Bản sao production chụp 08/10 01:49, có event thật của người bàn giao — không chia sẻ rộng, không commit.
- WP0.6 (chốt nhánh đích PR, đưa W 0,7/0,15/0,15 lên `main`) chưa làm: cần người dùng quyết định nhánh đích.
- `src/evaluation/README.md` vẫn là README của Streamlit lab, chưa nói gì về `recsys_bench/theme_study`; không sửa trong
  task này.
