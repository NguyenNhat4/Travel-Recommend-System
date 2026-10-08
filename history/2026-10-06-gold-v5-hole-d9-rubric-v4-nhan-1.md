# Rubric v4 cho mọi nhãn mới: gán lại hole D9a–D9c (sai loại / dưới sao = 0), QAnh duyệt hết, chiếu rubric v4 lúc chấm (phương án b)

- Ngày: 2026-10-06
- Tác giả: tqanh123 / Claude Code
- Nhánh: `fix/search-gold-v4`
- Trạng thái: hoàn thành (gold chưa tag `gold_v5`; mọi nhãn máy D9a–D9e đã được QAnh duyệt — chờ commit + tag)
- Phạm vi: evaluation, docs
- Phục vụ: FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01, test-plan §2.5
- Thay thế một phần: `history/2026-10-06-search-gold-v5-hole-d9a-va-chu-giai-cau.md` (nhãn 1 của hole D9a–D9c trên câu v3 gán theo quy ước v3 #2 và "sao dưới ngưỡng = 1"; nhãn máy chưa duyệt)

## Mục tiêu

Người dùng soát hole D9a và thấy nhãn 1 chưa theo rubric v4 (`docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md` §4.1–4.2): hole của câu cũ vẫn gán "đúng nơi nhưng sai loại → 1" (v3 #2) và "sao dưới ngưỡng → 1". Ba yêu cầu: (1) sửa lại theo đề xuất v4 — loại sản phẩm cốt lõi và sao là ràng buộc cứng → 0; (2) mọi nhãn máy D9a–D9e coi như QAnh đã duyệt; (3) với 161 nhãn 1 cũ của câu v3 ở cùng tình huống (gold chỉ thêm, không sửa được) chọn **phương án b**: chiếu rubric v4 lúc chấm, không sửa gold.

## File thay đổi

- `src/evaluation/search_bench/gold/holes/gold_v4__D9a/labels/labels_A.csv`, `labels/provenance_A.csv` — sửa: 51 nhãn 1 → 0 (41 sai loại, 10 dưới sao); note ghi lý do + nhãn cũ, `model` nối `; rubric-v4 pass 2026-10-06`. Mọi dòng máy đánh dấu `review=accepted`, `reviewed_by=QAnh` (273 dòng QAnh đã duyệt trong app giữ nguyên dấu).
- `src/evaluation/search_bench/gold/holes/untagged__D9b/labels/labels_A.csv`, `labels/provenance_A.csv` — sửa: 93 nhãn 1 → 0 (83 sai loại, 10 dưới sao); đánh dấu duyệt 871 dòng.
- `src/evaluation/search_bench/gold/holes/untagged__D9c/labels/labels_A.csv`, `labels/provenance_A.csv` — sửa: 6 nhãn 1 → 0 (5 sai loại, 1 dưới sao); đánh dấu duyệt 69 dòng.
- `src/evaluation/search_bench/gold/holes/untagged__D9d/labels/provenance_A.csv`, `untagged__D9e/labels/provenance_A.csv` — sửa: chỉ đánh dấu duyệt (14 + 16 dòng); không cặp nào thuộc diện sửa nhãn.
- `src/evaluation/search_bench/gold/gold.jsonl` — dựng lại: đặt về blob `gold_v4` rồi `holes import` D9a–D9e (gold_v5 chưa tag nên làm lại được). Vẫn 7.590 nhãn, 0 `machine_unreviewed`; provenance D9 là `holes:D9x:machine@gold_v5`; nhãn D9 0 / 1 / 2 = 896 / 446 / 582 (trước: 746 / 596 / 582).
- `src/evaluation/search_bench/gold/changelog.yaml` — dựng lại: 5 mục `gold_v5` (`machine` thay `machine_unreviewed`).
- `src/evaluation/search_bench/config/query_annotations.yaml` — sửa: thêm khoá `allowed_variants` cho 147 câu active trong catalog (7 câu `expected_no_result` không cần); 1 dòng chú thích về hai rubric; mô tả khoá ở đầu file.
- `src/evaluation/search_bench/metrics.py` — sửa: `GoldQuery.allowed_variants` / `v4_projected`; `UNIT_VARIANTS`; `load_annotations` nhận + kiểm `allowed_variants`; `apply_annotations` gắn; **`project_rubric_v4`** (nhãn ≥ 1 của sản phẩm có variant ngoài danh sách → 0, sửa `judgments` tại chỗ); per_query thêm `v4_projected_n`.
- `src/evaluation/search_bench/runner.py` — sửa: `RunEnv.projection`; `load_env` chiếu sau khi gắn chú giải khi `metrics.rubric_v4_projection`, log số cặp / câu; results.json (`run` và `rescore`) ghi `rubric_v4_projection {enabled, pairs, queries, annotated_queries}`.
- `src/evaluation/search_bench/config.py`, `config/sbench.yaml` — sửa: `metrics.rubric_v4_projection: true` (người dùng chốt 06/10).
- `src/evaluation/search_bench/tests/test_annotations.py` — sửa: test nạp / từ chối `allowed_variants`, `project_rubric_v4`, cờ config, file chú giải phủ mọi câu active trong catalog.
- `docs/spec/bench/gold-guide.md` — sửa mục "Rubric v4": phạm vi = mọi nhãn gán từ gold_v4 trở đi (câu mới **và** hole câu cũ); loại cốt lõi = `variant` catalog, subtype cùng variant = 1; phương án thay thế cho 1 (#10 hai chiều, #8d); sao dưới ngưỡng = 0; hợp nhất nhãn cũ bằng chiếu rubric v4 (b).
- `docs/spec/bench/search-eval-local-spec.md` — sửa Part 8: đoạn "Chiếu rubric v4 lúc chấm".
- `docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md` — sửa dòng trạng thái D1 theo phạm vi mới.
- `docs/plan/2026-10-05-gold-v4a-mo-rong.md` — sửa: thêm dòng D13 (06/10) vào bảng quyết định.
- `history/2026-10-06-gold-v5-hole-d9-rubric-v4-nhan-1.md` — entry này.

## Quyết định

- **Luật gán lại (cơ học, đề xuất v4 §4.1–4.2):** tập loại hợp lệ A(q) của mỗi câu = `expected_parse.taxonomy` của chú giải (hotel → `hotel_property` …); `cross_vertical` = mọi ngành dọc nêu trong câu; câu tên POI / không có từ ngành dọc = loại của nhãn 2 cũ do người gán. Hole nhãn 1 có `variant ∉ A(q)` → 0, trừ phương án thay thế rubric cho 1: combo có kèm vé cho câu hỏi vé **và** vé lẻ cho câu hỏi combo (#10 hai chiều — bản chạy đầu chỉ xét một chiều, 2 cặp vé lẻ của c0056 bị hạ nhầm đã hoàn lại 1; combo vé máy bay + KS như c0706 vẫn cho 0 theo chính sách câu), combo khứ hồi cho câu vé máy bay (#8d). `multi_constraint` "N sao": sao < N → 0; không khai sao → giữ 1. Khác subtype cùng variant (resort / KS / homestay; thương hiệu khác) giữ 1. Chỉ nhãn 1 đổi (không nhãn 2 nào của D9 vi phạm).
- **6 câu có nhãn 2 cũ ngoài A(q)** (c0253 combo bay + phòng cho câu KS; c0336 voucher golf cho câu hạng phòng; c0433 / c0456 / c0475 attraction cho câu KS; c0460 KS cho câu combo): bản chạy đầu bỏ qua các câu này để không cãi người gán cũ (danh sách bị `tail` cắt khỏi màn hình nên báo nhầm "không có mâu thuẫn"); xem lại từng cặp thì đều là nhãn lỏng theo v3 hoặc sai → giữ A(q), chiếu rubric v4 hạ chúng về 0 lúc chấm, và sửa nốt 3 hole nhãn 1 của c0433 / c0456 trong D9b (Chợ Đêm Pleiku, 2 Nha Trang Passport) cho nhất quán.
- **Duyệt:** theo yêu cầu người dùng, mọi dòng máy chưa duyệt trong 5 đợt được ghi `accepted` bởi QAnh (06/10). Các dòng do pass này đổi nhãn vẫn được QAnh duyệt (note bắt đầu `rubric v4:` để truy lại).
- **Phương án b:** `allowed_variants` = variant **không** vi phạm loại cốt lõi, gồm cả phương án thay thế rubric cho 1 (combo cho câu hỏi vé / vé máy bay; vé lẻ cho câu hỏi combo), bỏ `must_not_taxonomies`; sinh cùng luật với pass. Evaluator hạ nhãn ≥ 1 ngoài danh sách về 0 **lúc chấm** (`load_env`), áp cả nhãn cũ v1–v3; gold.jsonl không đổi nên `verify-append` các tag cũ vẫn xanh. Trên gold hiện tại: **164 cặp / 35 câu** bị chiếu (toàn bộ là nhãn cũ v1–v3: 158 nhãn 1 + 6 nhãn 2 kể trên), toàn bộ ở khối v3 — nhiều nhất `dest_type` 91, `named_entity` 26, `abbrev_typo` 24. Tắt bằng `metrics.rubric_v4_projection: false` để so với số cũ.
- Run `2026-10-06-gold-v4-r1` / `r2` không có trên máy này → chưa `rescore`; số trong `src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md` tính trên nhãn trước khi sửa và chưa chiếu.

## Kiểm tra

- `sb gold holes import` ×5 (`--version gold_v5`, không cần `--accept-unreviewed`): D9a +829 máy đã duyệt +56 auto_ooc; D9b +871 +60; D9c +69 +9; D9d +14; D9e +16. `sb gold check` xanh (154 câu, 15 slice). `sb gold verify-append gold_v4` xanh (+0 câu, +1.924 nhãn, +0 retired).
- `pytest test_annotations.py test_metrics_phase_a.py test_blocks_guards.py test_holes_import_rescore.py test_config.py` (.venv-sbench): 98 passed. Không chạy cả bộ: nhánh này có 54 test đỏ sẵn (CRLF fixture, sha pool, streamlit — `history/2026-10-06-search-bench-ablation-gold-v5.md`).
- `runner.load_env` trên gold thật: `projection {enabled: True, pairs: 164, queries: 35, annotated_queries: 147}`; c0056 "tìm combo du lịch Quy Nhơn" nhãn 1 từ 33 còn 5 (5 vé lẻ, #10); tắt cờ → nguyên nhãn gold.
- Không đổi contract, DDL, backend.

## Còn lại / rủi ro

- Commit rồi `git tag gold_v5` (mọi nhãn máy đã duyệt). Lệnh ghi tag chạy trên commit có gold.jsonl này.
- Rescore run r1 / r2 trên máy giữ run (`sb rescore --allow-untagged` — phép chiếu áp tự động) và cập nhật report query plan; số nDCG của `dest_type` / `named_entity` / `multi_constraint` sẽ giảm cho arm kéo sản phẩm sai loại lên — đúng ý rubric v4. Baseline regression (`regression/baseline_v1.json`) đặt lại sau đó.
- `allowed_variants` là chú giải máy (cùng file với `expected_parse`); người duyệt sửa trực tiếp trong yaml nếu một câu bị suy sai loại — test `test_shipped_allowed_variants_cover_every_active_query` chỉ kiểm phủ, không kiểm nghĩa.
- Judged@10 không đổi (nhãn chiếu về 0 vẫn là nhãn); Recall@10 mẫu số giảm ở câu bị chiếu.
