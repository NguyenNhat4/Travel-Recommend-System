# Gộp app gán nhãn draft gold (Người A) vào nhánh bench/embed-search

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Hai luồng việc của benchmark search nằm ở hai nhánh rời nhau, không nhánh nào chạy được trọn ngày 1: `codex/role-a-day1` (`e9fdc38`) có app Streamlit soát draft + `gold/drafts_raw.tsv` 600 case nhưng không có CLI `sb`; `bench/embed-search` có toàn bộ CLI `sb` nhưng không có draft và app. Ngày 2 của Người B (`sb gold pool`) cần `gold/drafts.txt` do Người A tạo từ app, nên hai phía phải nằm cùng một cây. Người dùng chốt: merge vào nhánh bench rồi mở PR vào `bench/embed-search`.

Phục vụ FR-SRC-01..04, NFR-PERF-01, NFR-PERF-03, AC-SRC-01.

## File thay đổi

Merge `e9fdc38` vào `bench/embed-search` (`2206f05`). Đúng 3 conflict, phần còn lại auto-merge.

Giải quyết conflict:

- `src/evaluation/search_bench/requirements.txt` — sửa (add/add): gộp danh sách bench của nhánh với `streamlit>=1.64,<2` của Người A; sửa pin `weaviate-client>=4.16,<5` → `>=4.23,<5`; thêm comment giải thích vì sao streamlit nằm cùng file.
- `docs/spec/bench/search-eval-checklist.md` — sửa: lấy khối "Trước ngày 1" và toàn bộ khối B của nhánh (đã tick kèm bằng chứng 23/09); lấy tick + đường dẫn + "13 slice" + `gold/drafts_raw.tsv` của Người A cho khối "Ngày 1 — A", ghép thêm hai mệnh đề trong ngoặc của nhánh (AGENTS.md §7 cho vị trí prompt; quy ước ghi **khoá** amenity trong `filter_json`).
- `docs/spec/bench/search-eval-local-spec.md` — sửa: lấy bản nhánh cho cả 5 hunk; ghép từ Người A dòng `Phục vụ` đầy đủ (giữ mệnh đề `; độ đo theo docs/prd/test-plan.md §2.5`), thay `SCHEMA.md` → `docs/spec/data-collection/schema.md` ở câu nguồn yêu cầu và ở Part 1 (đồng thời gỡ dòng map `SCHEMA.md` khỏi khối "Đối chiếu repo" vì không còn tham chiếu), thêm `drafts_raw.tsv` vào dòng cây `gold/` và bỏ `prompts/*.txt`; §1.6 thêm dòng `streamlit`.

Sửa hai chỗ trùng lặp mà git không báo (auto-merge tạo ra bản kép):

- `docs/spec/bench/arms.md` — sửa: gộp hai dòng `Phục vụ` thành một (giữ bản đầy đủ `FR-SRC-01..04 … AC-SRC-01`).
- `.gitignore` — sửa: gỡ dòng `bench_out/` trần, giữ khối có comment.

Merge đưa vào (không sửa nội dung): `src/evaluation/search_bench/labeling.py`, `streamlit_app.py`, `tests/test_labeling.py`, `gold/drafts_raw.tsv`, `gold/drafts_manifest.json`, `docs/spec/bench/gold-draft-prompt.md`, `docs/plan/2026-09-23-search-labeling-app.md`, `history/2026-09-23-sinh-600-search-cases.md`, `history/2026-09-23-streamlit-search-labeling.md`.

- `history/2026-09-24-gop-app-nhan-vao-bench-embed-search.md` — thêm: entry này.

## Quyết định

- **Tên tài liệu bench giữ chữ thường.** Nhánh bench đã đổi `ARMS.md`/`SEARCH_EVAL_*.md` → `arms.md`/`search-eval-*.md`; Người A chỉ sửa nội dung bản UPPERCASE nên git giải là rename-một-phía và cây merge chỉ còn 4 tên chữ thường. Đúng AGENTS.md §7; không `git mv` về lại.
- **Bỏ hai sửa đổi của Người A trong spec §1.2 và `regression.watch_paths`.** Người A ghi `catalog.products_path: src/data_collection/data/products.jsonl` — file này không tồn tại trên đĩa; `config/sbench.yaml` thật dùng `src/data_collection/data/snapshots/2026-09-21/products.jsonl` (46 MB, đã kiểm) với `snapshot_path` là bản `.gz` đã commit. Spec §1.2 tự khai `sbench.yaml` là nguồn số duy nhất và AGENTS.md §2 đặt config trên spec prose, nên spec phải theo config. `watch_paths` giữ bản `.gz` vì bản bung bị gitignore, CI không theo dõi được.
- **Một `requirements.txt` duy nhất** thay vì tách file cho app nhãn: Streamlit Community Cloud chỉ tự nhận `requirements.txt` cạnh entrypoint hoặc ở gốc repo, mà entrypoint buộc ở `src/evaluation/search_bench/` (`streamlit_app.py` import `labeling` cùng thư mục và đọc `gold/drafts_raw.tsv` cạnh nó). Đánh đổi: Cloud sẽ cài thêm pandas/pyarrow/scipy/cohere/weaviate-client mà app không dùng — build lần đầu chậm hơn, toàn bộ là wheel. Nếu Cloud vượt giới hạn thời gian/kích thước thì tách entrypoint sang package riêng ở PR sau, không làm trước.
- **Pin `weaviate-client>=4.23`** cho khớp spec §1.6 và `doctor.check_ascii_fold` (cần `Configure.text_analyzer`); bản `>=4.16` cho phép cài bản thiếu API rồi `sb doctor` FAIL.
- Không tự chốt các giá trị đang *đề xuất* của nhánh (`stopwords_preset: none`, `max_tokens_per_min: 90000`, ngữ nghĩa `retry.max_attempts`).
- Không lệch PRD (AGENTS.md §8): `docs/prd/` không nói gì về kích thước gold, slice hay ngưỡng benchmark; `docs/prd/update/` rỗng → không cần đề xuất.

## Kiểm tra

- `git merge --no-ff e9fdc38`: đúng 3 conflict như dự đoán bằng `git merge-tree`, app nhãn được giữ nguyên (chỉ có ở một phía so với merge base `e8381d6`).
- `grep -rn "<<<<<<<\|>>>>>>>" docs/ src/`: 0 dòng.
- `git ls-files docs/spec/bench/` + `ls docs/spec/bench/`: đúng 4 tên chữ thường (`arms.md`, `gold-draft-prompt.md`, `search-eval-checklist.md`, `search-eval-local-spec.md`).
- `grep -c "^Phục vụ"` trên ba tài liệu bench: 1 / 1 / 1.
- `grep -c "^bench_out/" .gitignore`: 1.
- `grep -c "^- \[x\]" docs/spec/bench/search-eval-checklist.md`: 17.
- `git diff --check`: sạch (chỉ cảnh báo LF→CRLF của core.autocrlf).
- `git diff --cached --numstat HEAD`: diff tối thiểu (`.gitignore` 3/1, `arms.md` 1/1, checklist 6/6, spec 6/5, requirements 5/1) — không có thay đổi line-ending toàn file.
- Không chạy `validate_contract.py`: không đổi OpenAPI hay mock. Không chạy `db/verify.sql`: không đổi schema hay seed.
- Test và lệnh `sb` chạy ở entry riêng `history/2026-09-24-sbench-ngay-1-kiem-lai-tren-clone-moi.md` (sau khi dựng `.venv-sbench`).

## Còn lại / rủi ro

- `tests/test_labeling.py` chèn `src/evaluation/search_bench` vào `sys.path` (import `labeling` dạng top-level). Sau merge, pytest thu cả file này cùng các test dạng package; phải kiểm số test bench không tụt dưới mức của nhánh (125 passed / 9 skipped ở entry ngày 2). Nếu vỡ thì sửa bằng `conftest.py` hoặc `importlib`, không xoá test.
- Cloud build của app nhãn chưa thử với file requirements gộp; chưa deploy nên chưa có bằng chứng.
- Còn `[ ]`: mentor xác nhận văn bản 3 mục lệch handbook; Người A chọn 200 draft → `gold/drafts.txt`; Người A đưa file đó cho Người B.
- Catalog trên nhánh bench đã có Sa Pa (524 bản ghi) và `vocab.json` 35 điểm đến, trong khi `drafts_manifest.json` của Người A khoá checksum catalog 38 điểm đến. Trước khi chọn 200 draft, Người A phải đối chiếu lại grounding của slice `out_of_catalog` (xem "Còn lại" của `history/2026-09-24-search-bench-ngay-2-b0-filters-pool.md`).
