# Chuyển tài liệu vbench từ docs/vector_bench vào docs/spec/vector-bench

- Ngày: 2026-09-23
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: docs, evaluation

## Mục tiêu

Merge `bench/vector-db` (`2026-09-23-merge-bench-vector-db.md`) đưa lại thư mục `docs/vector_bench/`, nằm ngoài các thư mục tài liệu `AGENTS.md` §7 cho phép, và tên file viết hoa. Người dùng chốt chuyển vào `docs/spec/vector-bench/`.

## File thay đổi

- `docs/vector_bench/spec.md` → `docs/spec/vector-bench/spec.md` — đổi tên; thêm dòng "Phục vụ"; `VECTOR_DB_SELECTION.md` → `vector-db-selection.md`.
- `docs/vector_bench/spec-fasttrack.md` → `docs/spec/vector-bench/spec-fasttrack.md` — đổi tên; thêm dòng "Phục vụ"; sửa tham chiếu như trên.
- `docs/vector_bench/VECTOR_DB_SELECTION.md` → `docs/spec/vector-bench/vector-db-selection.md` — đổi tên (chữ thường, gạch nối); thêm dòng "Phục vụ"; `VECTOR_DB_BENCH_SPEC.md` ghi rõ là `spec.md`.
- `src/evaluation/vector_bench/README.md` — sửa: đường dẫn spec mới, tên `vector-db-selection.md`.
- `src/evaluation/vector_bench/__init__.py` — sửa: docstring trỏ đường dẫn mới.
- `src/evaluation/vector_bench/config/vbench.yaml` — sửa: hai comment nhắc `VECTOR_DB_SELECTION` → `vector-db-selection.md`.
- `history/2026-09-23-chuyen-docs-vector-bench-vao-docs-spec.md` — thêm: entry này.

## Quyết định

- Chỉ đổi vị trí, tên file và tham chiếu; không sửa nội dung kỹ thuật.
- Thêm một dòng "Phục vụ: FR-SRC-02, NFR-PERF-01, NFR-PERF-03" ở đầu mỗi file vì `AGENTS.md` §7 yêu cầu mỗi spec ghi mã FR/NFR.
- Không sửa hai entry `history/2026-09-2{2,3}-vector-bench-*.md` còn trỏ `docs/vector_bench/…` (quy tắc không sửa entry cũ); đường dẫn đúng là `docs/spec/vector-bench/`.

## Kiểm tra

- `grep -rn "docs/vector_bench\|VECTOR_DB_SELECTION" docs src/evaluation/vector_bench`: không còn kết quả.

## Còn lại / rủi ro

- `vector-db-selection.md` §2 vẫn ghi "~5.000" search unit; số thật 2.897 (đã nêu ở hai entry vbench cũ) — chưa sửa vì không thuộc phạm vi việc chuyển thư mục.
- `vector-db-selection.md` nhắc `VECTOR_STORE_AND_ROBUSTNESS.md` — file này không có trong repo.
- vbench so sánh pgvector / Qdrant / pgvectorscale, trong khi PRD đã chốt Weaviate + Cohere ngày 22/09 (`2026-09-22-chuyen-vector-sang-weaviate-cohere.md`). Kết quả vbench chỉ để tham khảo; không đổi PRD.
