# Search bench: tag `gold_v5`, chấm lại run r1/r2 trên gold đã duyệt + chiếu rubric v4, đặt lại `baseline_v1`, rà `allowed_variants`

- Ngày: 2026-10-06
- Tác giả: người dùng ("run the first group") / Claude (Opus 5.5)
- Nhánh: fix/search-gold-v4
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Sau khi QAnh duyệt hết nhãn máy hole D9a–D9e và bật chiếu rubric v4 lúc chấm (`ca9fb88`,
`history/2026-10-06-gold-v5-hole-d9-rubric-v4-nhan-1.md`), mọi số của report 06/10 sáng đã cũ (tính trên nhãn chưa duyệt, chưa chiếu).
Bốn việc: tag `gold_v5`; rescore run r1/r2 (chỉ có trên máy này) và cập nhật report, verdict, kiến trúc §17, spec §10; đặt lại
`baseline_v1`; rà `allowed_variants`. Phục vụ FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01.

## File thay đổi

- Tag git `gold_v5` → `ca9fb88` (lightweight như `gold_v1`–`gold_v4`), đã push.
- `src/evaluation/search_bench/regression/baseline_v1.json` — sửa: đặt lại (`sb regress baseline --force`) từ run
  `2026-10-06-gold-v4-r2`, arm `APP.e5s.hybrid_norm`, `gold_v5`, catalog bench hiện tại; nDCG@10 0,711, recall@10 0,352.
- `src/evaluation/search_bench/config/query_annotations.yaml` — sửa: `allowed_variants` của c0078, c0724 bỏ `attraction`.
- `src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md` — sửa: toàn bộ số chuyển sang `gold_v5` + chiếu rubric v4 (bảng,
  verdict, §1, §5, §6, §7, độ tin cậy router); ghi chú đầu report giữ số bản sáng để đối chiếu.
- `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` — sửa: số §17 + dòng checklist hole.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: §10 S12, S13, S15 theo `gold_v5`.
- `docs/spec/bench/arms.md` — sửa: hàng `_f1f6` (+10,7).
- `docs/prd/update/2026-10-06-search-llm-fallback-query-plan.md` — sửa: số nhóm độ tin cậy thấp trên `gold_v5` (0,770 so 0,850).
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: thêm dòng log Day 7 chiều.

## Quyết định

- **Tag trước, chấm sau**: kiểm `sb gold check` xanh, `verify-append gold_v4` xanh (+1.924 nhãn), 0 `machine_unreviewed`, sha
  `gold.jsonl` ở `ca9fb88` = bản làm việc (`1f903132…d7b0`) rồi mới tag; `rescore` không còn cần `--allow-untagged`.
- **Arm của `baseline_v1` = `APP.e5s.hybrid_norm`** (cấu hình production hôm nay: hybrid + normalize, cờ query plan tắt, cutoff 0,62 không
  lọc gì với e5) — cùng arm với baseline cũ; regression phải canh hành vi đang chạy, không phải ứng viên. Đặt lại sang `_f1f6` khi người
  dùng bật cờ. `sb regress check` cùng arm: PASS, top-10 đổi 0/154.
- **`allowed_variants`**: rà 147 câu — 11 tổ hợp loại; 35 câu bị chiếu (164 cặp) khớp entry của QAnh. Lỗi duy nhất: hai câu vé máy bay
  (c0078 "đường bay tới Huế", c0724 "các chuyến bay xuất phát từ Cần Thơ") có `attraction` — bộ sinh áp nối hai luật (#8d cho combo, rồi
  #10 chiều ngược cho vé lẻ vì combo đã có), trái mô tả đầu file (câu vé máy bay chỉ nhận combo khứ hồi). Bỏ `attraction`; hôm nay không
  có nhãn ≥ 1 nào của attraction ở hai câu này nên số không đổi (chiếu vẫn 164 cặp / 35 câu), nhưng tránh lọt khi gán hole sau. Câu golf
  (c0085, c0088, c0367) chỉ nhận `golf` là đúng: sản phẩm bị chiếu là vé VinWonders / điểm tham quan, không phải combo có golf.

## Kiểm tra

- `sb --run-id 2026-10-06-gold-v4-r1 rescore`, `… r2 rescore` (`gold_v5`): log `chiếu rubric v4 annotated=147 pairs=164 queries=35`;
  Judged@10 = 1,000 mọi arm.
- 65 cặp `sb compare` (toàn bộ, `--split dev`, `--split test`). Số chính: A 0,711; `_f1f6` **0,818 WIN** (Δrecall +4,79); dev WIN; test
  +11,4 nDCG nhưng `flight_direction` −6,0; `_f1f6_rr` 0,857; ALL 0,803; bỏ F4 khỏi ALL nay LOSE (−2,1).
- `sb guards` A / `_f1f6` / ALL / `_f1f6_rr`: như bản sáng (guard không phụ thuộc nhãn); parse accuracy không đổi.
- `pytest test_annotations.py test_metrics_phase_a.py test_blocks_guards.py` (.venv-sbench): 79 passed.
- `sb regress baseline … --force` rồi `sb regress check --arm APP.e5s.hybrid_norm`: PASS.

## Còn lại / rủi ro

- `allowed_variants` vẫn là chú giải máy; mới rà theo luật, chưa soát nghĩa từng câu.
- Bật cờ F1–F6 (F4 cần Web), chốt FR-SRC-02 e5-small để deploy và đo gate P — xem report §5.
