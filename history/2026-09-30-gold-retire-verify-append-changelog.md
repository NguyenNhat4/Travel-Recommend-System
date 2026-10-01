# Gold append-only (Part 11, nửa đầu): `gold retire`, `gold verify-append`, `changelog.yaml`, version theo tag git

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Kế hoạch 3 ngày sau khi gán nhãn xong (30/09 → 02/10), mục P1: mở khoá tag `gold_v1`. Mô phỏng `merge → import → check`
trên nhãn thật cho 6 câu không có nhãn 2; 5 câu là lỗi gán / thiếu quy ước (A1, A2 sửa trong app hoặc `merged.csv`), riêng
c0463 ("ve may bay SG di DN") không thể có nhãn 2 vì sản phẩm đúng `5d210e58` (vé HCM → Đà Nẵng) không nằm trong pool
depth 15. Người dùng chốt: **retire c0463 trước tag** thay vì dựng lại pool (làm hỏng sha của 3.999 nhãn). Cần lệnh
`sb gold retire` (spec Part 11 có tên lệnh nhưng chưa cài), cùng `verify-append` và `changelog.yaml` để mọi thay đổi gold
từ đây đều truy vết được. Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/holes.py` — thêm: version gold theo tag git (`list_gold_tags`, `next_version`,
  `gold_version_of` so blob `git hash-object` với `gold_vN:<path>`, `gold_at(ref)` đọc tag/commit/file), changelog
  (`read_changelog`, `append_changelog`, `changelog_entry`), `retire`, `verify_append`. Nửa sau (holes, rescore) làm ở P4.
- `src/evaluation/search_bench/paths.py` — sửa: thêm `GOLD_JSONL`, `GOLD_CHANGELOG`, `HOLES_DIR`.
- `src/evaluation/search_bench/__main__.py` — sửa: `gold import` ghi một mục `import` vào `changelog.yaml` cạnh file đầu
  ra khi nội dung đổi (thêm `--version`); thêm `gold retire <qid> --reason [--gold] [--version]` và
  `gold verify-append <old> [<new>]`.
- `src/evaluation/search_bench/tests/test_holes.py` — thêm: 15 test (hàm retire / verify-append, version helper, repo git
  tạm với tag `gold_v1`, CLI retire / verify-append / import + changelog).
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.3 dòng Part 11 (tuỳ chọn mới); Part 11: định dạng
  `changelog.yaml`, cách xác định version bằng git, `retire` trước tag cho `pool_miss`, `verify-append` nhận tag / commit /
  đường dẫn và kiểm cả provenance + `expected_children`.

## Quyết định

- **Version của gold = tag git**, không ghi trong file: `gold.jsonl` khớp blob của tag `gold_vN` thì là `gold_vN`; không
  khớp tag nào thì chưa có version (spec §1.5: `sb run` sẽ từ chối — P2). Không cần cột version trong `GoldRecord`, hợp
  đồng `gold_schema.py` giữ nguyên.
- **Mục changelog theo hành động, không theo version:** trước khi tag, `import` rồi `retire` cùng thuộc `gold_v1`; mỗi
  lệnh một mục, `version` = tag mới nhất + 1 (chưa có tag → `gold_v1`) hoặc `--version`. Changelog nằm cạnh file gold đầu
  ra (`-o` vào thư mục tạm thì changelog cũng ở đó) để test không ghi vào `gold/` thật.
- **`retire` ghi thẳng `gold.jsonl`** qua `write_gold_jsonl` (đầu ra ổn định, sắp theo qid như `import`), không qua
  `write_gold_checked` vì đây là một trong ba lệnh được phép đổi gold (spec §1.7 #4). Chỉ đổi `status`, giữ nhãn.
- **`retire` trước tag cho `pool_miss`** là mở rộng spec Part 11 (trước chỉ nói trường hợp catalog đổi); người dùng ký khi
  duyệt kế hoạch 30/09. Không lệch PRD.
- `verify-append` kiểm thêm provenance và `expected_children` của nhãn cũ (spec chỉ nói "nhãn cũ giữ nguyên giá trị");
  hai trường này đổi cũng là sửa gold cũ, nên tính là vi phạm.
- `import` không ghi changelog khi nội dung không đổi (chạy lại y hệt), để changelog không phình vì thao tác lặp.

## Kiểm tra

- `cd src && PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 ../.venv-sbench/Scripts/python -m pytest evaluation/search_bench/tests -q -p no:cacheprovider`: **297 passed, 10 skipped** (trước: 282 passed, 10 skipped; 15 test mới).
- Chưa chạy trên gold thật: `gold/gold.jsonl` chưa có (A1, A2 merge / import sáng 01/10). Mô phỏng trong bộ nhớ ngày
  30/09: merge 3.359 cặp, 12 `needs_discussion`, check đỏ 6 câu như ghi ở mục tiêu.

## Còn lại / rủi ro

- P2 (runner `sb run --arm`, `sb compare`) dùng `holes.gold_version_of` để từ chối gold chưa tag; P4 thêm `gold holes`,
  `holes import`, `rescore` vào cùng module.
- Sau `retire`, chạy lại `gold import --overwrite` sẽ đặt c0463 về `active` (import dựng lại từ merged.csv). Đã ghi trong
  spec; nếu cần import lại sau tag thì phải retire lại hoặc thêm cơ chế giữ status (chưa làm).
- Kế hoạch 3 ngày và các quyết định 30/09 sẽ ghi thành `docs/plan/2026-09-30-bench-search-recsys-3-ngay.md` ở bước tài
  liệu tiếp theo.
