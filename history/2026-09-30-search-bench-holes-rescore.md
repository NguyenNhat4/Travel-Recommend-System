# Search bench Part 11 (nửa sau): `gold holes`, `gold holes import`, `sb rescore`, kết quả theo gold_version

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Kế hoạch 3 ngày, mục P4: pool gold được dựng từ dense top-15 của B0 ∪ BM25 trên câu gốc, nên arm khác (e5, adapter
production) sẽ kéo lên top-10 những sản phẩm chưa có nhãn — metric tính chúng là 0 và `judged@10` tụt (spec Part 11).
Cần vòng holes → gán → import → tag → rescore để so arm công bằng. Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/holes.py` — sửa: thêm `Hole`, `find_holes` (top-`holes.k` chưa nhãn, tách hole của câu
  out_of_catalog, sắp câu theo số arm thấy), `hole_rows` (dựng `POOL_COLUMNS` từ gold record + `PoolView`), `write_holes`
  (thư mục hole: `pool_A.csv` [+ `pool_B.csv` khi `--split`], `pool_meta.json`, `meta.csv`, `auto_ooc.csv`, `holes.json`;
  xáo trong từng câu), `import_holes` (nhãn người + auto_ooc → gold, từ chối cặp đã có nhãn / sai luật / sha lệch /
  thiếu nhãn trừ `partial`), `read_holes_summary`.
- `src/evaluation/search_bench/runner.py` — sửa: `safe_version`, `available_versions`, `read_results_at`,
  `rescore_arm` (chấm lại từ `top_ids` + `applied_filter` đã lưu → `results@<gv>.json` + `per_query@<gv>.parquet`,
  `rescored_from`, `queries_missing_in_run`), `arms_in_run`.
- `src/evaluation/search_bench/__main__.py` — sửa: sub-typer `gold holes` (callback) và `gold holes import`; lệnh `rescore`.
- `src/evaluation/search_bench/tests/test_holes_import_rescore.py` — thêm: 4 test theo "Done khi" của Part 11 (3 cặp chưa
  gán, 1 thuộc câu ooc → file 2 dòng + 1 auto_ooc; import; verify-append xanh; sửa nhãn cũ → đỏ; import lần hai bị từ
  chối; partial; split xen kẽ; rescore đưa judged@10 về 1,0 và khớp chạy lại từ đầu; CLI trọn vòng run → holes → import →
  verify-append → rescore → compare).
- `docs/spec/bench/search-eval-local-spec.md` — sửa: ba dòng Part 11 (`holes`, `holes import`, `rescore`) theo cách cài.

## Quyết định

- **Thư mục hole thay cho một csv** để app gán nhãn hiện có mở được như pool thường (`pool_meta.json` + `pool_X.csv`,
  nhãn ghi `labels/labels_X.csv` cạnh meta, sha kiểm như pool) — không sửa app. `--split` chia câu xen kẽ hai người,
  không câu chung (không cần κ; kế hoạch 30/09: A1/A2 chia theo qid).
- `from` / `rank_dense` của dòng hole = hạng tốt nhất giữa các arm (PoolRow bắt buộc có rank khi `from = dense`); app ẩn
  hai cột này nên người gán không thấy arm hay hạng. Arm ghi ở `meta.csv` riêng.
- Hole của câu `expected_no_result` không vào file gán: `auto_ooc.csv`, import gán 0 với provenance `auto_ooc:<tag>@<ver>`.
- **Tên file rescore dùng version đã làm sạch** (`fixture:ab12` → `fixture_ab12`): dấu `:` trên Windows tạo NTFS
  alternate data stream, file "biến mất" khỏi glob — phát hiện nhờ test. `gold_version` thật đọc trong JSON.
- `sb compare` giữ nguyên: lấy bản version cao nhất của mỗi arm (`read_results_at`) — chưa tự rescore bản cũ như spec
  §1.5 mô tả; khác version thì báo và chỉ lệnh `sb rescore`.
- `import_holes` không kiểm `check_gold` (fixture `gold_small.jsonl` cũ vốn thiếu `expected_children`); người chạy vẫn
  chạy `sb gold check` sau import như quy trình.

## Kiểm tra

- `pytest evaluation/search_bench/tests -q -p no:cacheprovider`: **318 passed, 10 skipped**.
- Chưa chạy trên gold thật (chờ `gold_v1` sáng 01/10).

## Còn lại / rủi ro

- `--stage S` của `gold holes` chờ Part 12 (P7).
- `compare` tự rescore bản cũ (spec §1.5) chưa làm; quy trình hiện tại: `sb rescore` rồi `sb compare`.
- Nhãn hole do người gán (`holes.labeler: A`); Claude không gán máy cho hole (dựng arm).
