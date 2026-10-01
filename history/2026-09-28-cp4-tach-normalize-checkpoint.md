# CP4: tách normalize thành ánh xạ theo nguồn (checkpoint) + gộp

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

CP4 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`. Để chạy lại từng bước, và để phần theo nguồn chạy được
ngay khi nguồn đó cào xong (CP5). Trước đây `main()` là một khối; output trung gian chỉ là ảnh chụp để xem.
Phục vụ FR-CAT-01..04. Output phải giữ nguyên.

## File thay đổi

- `src/data_collection/normalise.py` — sửa:
  - `read_source` / `map_source`: ánh xạ interim của **một** nguồn, không phụ thuộc nguồn khác.
  - `write_checkpoint` / `load_checkpoints`: `<data-dir>/normalised/<nguồn>.jsonl` + `.meta.json` + `.errors.jsonl`, ghi tạm rồi đổi tên.
  - `merge_catalog`: phần sau ánh xạ, **giữ nguyên code** và dựng lại danh sách theo đúng thứ tự cũ (`HOTEL_SOURCES`).
  - CLI thêm `--only-source NGUỒN`, `--merge-only`, `--checkpoint-dir`. Chạy mặc định cũng đi qua checkpoint trên đĩa, nên đường chạy thường ngày và đường chạy từng nguồn là một.
  - Bước mới `đọc checkpoint` trong `steps.json`; `StageDump.add` nhận khoá bản ghi có sẵn; `RecordGuard.write_all`.
- `src/data_collection/tests/fixtures/normalise_sample/expected_products.jsonl` — thêm: 54 dòng do `normalise.py` ở HEAD (trước CP1–CP5) sinh ngày 2026-09-28 trên mẫu, chạy ngay trong `src/data_collection` để đọc đúng các file sửa tay (`destination_overrides.csv`…).
- `src/data_collection/tests/test_normalise_steps.py` — sửa: thêm 4 test CP4 (chạy mặc định trùng output trước khi tách; từng nguồn riêng rồi `--merge-only` trùng; `--merge-only` dựng lại khi đã xoá interim; thiếu đầu vào / nguồn hỏng chạy riêng); cập nhật tên bước CP1.
- `history/2026-09-28-cp4-tach-normalize-checkpoint.md` — thêm: entry này.

## Quyết định

- Chỉ tách **bước ánh xạ** (nặng nhất, ~6 s trên 49 MB). Các bước sau giữ nguyên thứ tự trong phần gộp vì nhiều bước làm giàu chạy trên dòng đã gộp; chuyển chúng lên trước gộp có thể đổi output.
- Checkpoint dạng JSON: đã kiểm 3.813 bản ghi đã ánh xạ ghi JSON rồi đọc lại mà giữ nguyên (không có tuple/date).
- Đọc checkpoint tách theo `"\n"`, không dùng `splitlines()`: mô tả có U+2028 (lỗi gặp khi chạy thử, đã sửa).
- Bản ghi agoda trình duyệt trùng khoá với agoda API vẫn được ánh xạ ở bước theo nguồn (nguồn không biết nhau), nhưng bị bỏ ở bước gộp như cũ; ảnh chụp `mapped` cũng bỏ chúng nên không đổi.
- Ngưỡng bản ghi lỗi (CP2) kiểm sau khi ánh xạ: chạy `--only-source` thì nguồn hỏng dừng riêng nguồn đó.

## Kiểm tra

- Interim 49 MB, chạy mặc định: `products.jsonl` `sha256` `bd4730abaf3bab71…`, 2.546 dòng, **trùng bản gốc**. `dedup_report.csv`, `products.csv` trùng từng byte; 5 ảnh chụp bước (mapped/merged/filtered/enriched/dropped) trùng `sha256`.
- Interim 49 MB, `--only-source` 7 nguồn song song (3,3 s) rồi `--merge-only` (5,2 s): `sha256` trùng.
- Mẫu nhỏ: code mới (`--today 2026-09-28`) trùng từng byte với code HEAD chạy cùng ngày.
- `pytest tests` (env `vsf`): **384 passed, 3 skipped** (thêm 4). `git diff --check`: sạch.

## Còn lại / rủi ro

- CP5: gọi `--only-source` khi từng site cào xong và `--merge-only` ở cuối lượt.
- Chưa commit.
