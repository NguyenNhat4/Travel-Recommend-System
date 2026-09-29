# Merge bench/vector-db vào bench/embed-search

- Ngày: 2026-09-23
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Bench embedding + search (`docs/spec/bench/`, Weaviate + Cohere) phải dùng lại code của vbench (`lexical.fold`, `dataset/amenities.py`, `dataset/catalog.py`, `dataset/fake.py`, `paths`, `config.read_env_file`) theo quy tắc "import dùng lại, không chép" của spec §1.1. Code đó chỉ có trên nhánh `bench/vector-db` (commit `8901451`), chưa merge vào nhánh nào. Người dùng chọn merge nhánh này trước thay vì chép từng module.

## File thay đổi

Ngoài nội dung merge từ `bench/vector-db` (package `src/evaluation/vector_bench/`, `docs/vector_bench/*`, hai entry `history/2026-09-2{2,3}-vector-bench-*.md`, một dòng trong `src/data_collection/README.md`):

- `.gitignore` — sửa: giải xung đột, giữ cả `bench_out/` (từ nhánh vector-db) lẫn khối `secrets/` (từ release-mvp-v1).
- `history/2026-09-23-merge-bench-vector-db.md` — thêm: entry này.

`src/data_collection/README.md` tự merge được (hai bên sửa cùng một dòng giống hệt nhau).

## Quyết định

- Merge `--no-ff` để giữ ranh giới nhánh vbench.
- Không sửa nội dung vbench trong commit merge. `docs/vector_bench/` nằm ngoài các thư mục `AGENTS.md` §7 cho phép — chuyển sang `docs/spec/vector-bench/` ở commit riêng ngay sau (người dùng đã chốt).

## Kiểm tra

- `git merge-tree` trước khi merge: chỉ `.gitignore` xung đột.
- `PYTHONUTF8=1 .venv-vbench/Scripts/python -m pytest src/evaluation/vector_bench/tests`: 60 passed, 3 skipped (integration cần engine) — khớp số trong `2026-09-22-vector-bench-fasttrack.md`.

## Còn lại / rủi ro

- Kết quả vbench vẫn "CHƯA CHỐT" (xem `2026-09-23-vector-bench-ket-qua-fast-track.md`); merge không đổi điều đó.
- Hai entry vbench cũ trỏ tới `docs/vector_bench/…`; sau khi chuyển thư mục, các đường dẫn đó thành cũ (không sửa entry cũ theo `history/README.md`).
