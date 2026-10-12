# Lane B2: DB nghiên cứu G6 và đo lại RecSys trên dữ liệu event có sở thích chủ đề

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update
- Trạng thái: hoàn thành (phần đo); G2 **chờ người dùng chốt lại**
- Phạm vi: evaluation, docs
- Tiếp theo: `history/2026-10-08-seed-profile-g6-so-thich-chu-de.md`, `history/2026-10-09-recsys-lane-a-latency-coldstart-ac-baseline.md`

## Mục tiêu

Lane B2 của `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md`: dựng DB nghiên cứu với lịch sử sinh bởi profile
`g6-pref-v1` (sở thích chủ đề ẩn), đo lại production / P2 / P2+F14c / P2+F14c+destCap2 (+ 2 tune) với CI ghép cặp, để người
dùng chốt lại G2 trên dữ liệu **có** tín hiệu sở thích. FR-REC-01/02/04.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/eval_profile.py` — sửa: cờ `--f14-q` ghim ngưỡng F14 (hằng sẽ ship) thay vì q
  calibrate trên DB đang đo; calibration vẫn ghi vào JSON.
- `src/evaluation/recsys_bench/frozen/split-{llbo,temporal,nexttrip,coldstart}-g6pref-v1-asof20261008.json` — thêm.
- `src/evaluation/recsys_bench/theme_study/results/2026-10-09-g6-pref-v1/` — thêm: JSON 6 cấu hình, `ci_vs_prod.json`,
  `ci_tune.json`, `append_receipt.json`, `themes.json` (nhãn ẩn), `prodcopy_prod_desthit.json`, `SHA256SUMS`.
- `src/evaluation/reports/eval-2026-10-09-recsys-g6-so-thich-do-lai.md` — thêm.
- `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` — sửa: §7.6 kết quả G6 + ba lựa chọn chốt lại G2.
- `docs/prd/update/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md` — sửa: bảng tiêu chí thêm số G6, ghi D1 không đạt.
- `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` — sửa: tick A1–A3, B1, B2; G2 chờ chốt lại.
- `history/2026-10-09-recsys-g6-do-lai-tren-du-lieu-co-so-thich.md` — thêm: entry này.

Không commit: DB `vota_g6pref_v1`, artifact `batch.json` / `catalog.json` (80 MB), JSONL từng khách.

## Quyết định

- DB G6 dựng bằng `pg_restore` từ dump bàn giao (không `createdb -T`: backend và gate đang giữ kết nối tới template), rồi
  `TRUNCATE cdp.events` + `DELETE FROM cdp.profiles` theo MOCK_DATA_SPEC §4.3; catalog giữ nguyên nên `.npy` vẫn hợp lệ.
- Ghim q = 0,8529 / 0,9387 (hằng sẽ ship) ở mọi lượt; q calibrate trên G6 (0,8588 / 0,9391) chỉ ghi để đối chiếu.
- Tham số G6 (p 0,8; 30 % không sở thích; mix theo khối lượng) dùng mặc định của spec; người dùng chốt sau — kết quả đổi
  chiều không phụ thuộc chúng (C2 → C3 cùng chiều trên cả hai DB).
- Thêm hai cấu hình tune (F7 + destCap2, F14d pop 0,45 + destCap2) vì D1 không đạt ở C3 — để người dùng thấy cả đường đánh
  đổi chứ không chỉ một điểm.
- Không đo lại ô khám phá B trên G6 (chỉ chạm nhánh chuyến mở, G6 không đổi nhánh đó).
- Không tự chốt G2 (AGENTS.md §2, §8); ba lựa chọn ở `quyet-dinh.md` §7.6.

## Kiểm tra

- DB: 16.740 products, 442 combo_items, 5.000 profiles, 32.747 events (receipt `60d77c38…`), 3.496 khách có chủ đề.
- Tín hiệu: hai chuyến liên tiếp cùng chủ đề 0,820 biển / 0,810 phố / 0,633 núi so với 0,378 không sở thích.
- `parity_mismatch_llbo200 = 0` ở mọi lượt; thời gian: C0 578 s, C1+C2 1.180 s, C3 554 s, T1 554 s, T2 557 s.
- C3 so production (G6): nexttrip destHit@20 **+0,0425** [+0,0213, +0,0631]; nexttrip hit@20 **−0,0322** [−0,0425, −0,0219];
  hit@4 −0,0039 [−0,0097, +0,0019]; temporal h@20 −0,0227 [−0,0364, −0,0091]; LLBO h@4 −0,0020; coldstart h@4 −0,0008 (CI
  chứa 0); theme +0,309 / +0,363. Khách có chủ đề: destHit +0,0494, hit@20 −0,0401.
- T2 (pop 0,45 + destCap2): destHit +0,0702, temporal −0,0121 (CI chạm 0), nexttrip hit@20 −0,0238, theme +0,135 / +0,200.
- Luật D1–D5: D2, D4 đạt; D3 trong dung sai; D5 nửa; **D1 không đạt** mọi cấu hình.
- `pytest src/evaluation/recsys_bench/tests`: 160 passed, 3 skipped, 4 xfailed (không đổi).

## Còn lại / rủi ro

- **G2 chốt lại** theo (a)/(b)/(c) ở `quyet-dinh.md` §7.6 → G5b → PR-B; hoặc dừng ở PR-A.
- G6 chỉ có sở thích mức điểm đến; muốn đo "đúng món" cần G6 v2 (sở thích mức thuộc tính sản phẩm) — việc mới, cần chốt.
- Tham số G6 chưa chốt chính thức.
- Hai DB nghiên cứu và backend local vẫn chạy trong container `vota-prodcopy-pg`; tắt khi xong PR-A / PR-B.
