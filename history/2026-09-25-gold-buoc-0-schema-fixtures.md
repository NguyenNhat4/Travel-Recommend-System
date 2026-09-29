# Gold bước 0: hợp đồng dữ liệu, fixture và sửa line ending

- Ngày: 2026-09-25
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Commit `38ad63c` ("spec gold") đưa vào bước 0 của quy trình gán nhãn gold: hợp đồng file giữa CLI `sb gold` và app gán nhãn, fixture 7 câu kèm đáp án, và prompt việc cho hai máy. Commit đó thiếu entry `history/` và có ba chỗ chưa đúng. Entry này ghi lại bước 0 và các chỗ sửa.

Người dùng chốt ngày 25/09:
- chưa chia 2 máy, làm luôn trên `bench/embed-search`;
- sửa bước 0 trên nhánh này;
- bỏ qua `src/evaluation/README.md`.

## File thay đổi

Trong `38ad63c` (17 file, ghi bù):
- `src/evaluation/search_bench/gold_schema.py` — thêm: hợp đồng pool / nhãn / merged / meta / `gold.jsonl` (pydantic), cùng các hàm đọc và ghi.
- `src/evaluation/search_bench/tests/test_gold_fixtures.py` — thêm: 11 test kiểm hợp đồng và fixture.
- `src/evaluation/search_bench/tests/fixtures/gold_small/` — thêm 12 file:
  - `README.md`, `catalog_small.jsonl`, `expected.json`, `gold_expected.jsonl`;
  - `labels_A.csv`, `labels_B.csv`;
  - `make_fixtures.py`;
  - `merged_expected.csv`, `merged_resolved.csv`;
  - `pool_A.csv`, `pool_B.csv`, `pool_meta.json`.
- `docs/spec/bench/README.md`, `docs/spec/bench/prompts/may1-gold-cli.md`, `docs/spec/bench/prompts/may2-label-app.md` — thêm: hướng dẫn bước 0 và việc của máy 1 / máy 2.

Sửa trong entry này:
- `.gitattributes` — sửa: thêm `src/evaluation/search_bench/gold/** -text` và `src/evaluation/search_bench/tests/fixtures/gold_small/** -text`.
- `.gitignore` — sửa: bỏ qua `src/evaluation/search_bench/gold/**/.*.tmp`, là file tạm của `atomic_write_text`.
- `docs/spec/bench/README.md` — sửa:
  - thêm dòng FR/NFR;
  - ghi trạng thái "chưa chia máy, bước 0 ở `bench/embed-search`";
  - sửa khối `.gitattributes` về đúng đường dẫn.
- `docs/spec/bench/prompts/may1-gold-cli.md` — sửa: thêm dòng FR/NFR và ghi chú về nhánh.
- `docs/spec/bench/prompts/may2-label-app.md` — sửa: thêm dòng FR/NFR, ghi chú về nhánh, sửa "~125 câu × 26 ≈ 3.200 cặp" thành "≈112 câu ≈ 2.900 cặp".
- `history/2026-09-25-gold-buoc-0-schema-fixtures.md` — thêm: entry này.

## Quyết định

**Line ending**
- Máy này đặt `core.autocrlf=true`. Các file trong `src/evaluation/search_bench/gold/` đang ở dạng `i/lf w/crlf`. Fixture còn ở dạng `w/lf` chỉ vì chưa bị checkout lại.
- Trước khi sửa, bản checkout của `pool_A.csv` băm ra `e8904f22…`, trong khi meta ghi `6d32e824…`. Vì vậy test bước 0 sẽ đỏ trên máy clone mới, và app sẽ chặn không cho gán nhãn.
- Các pattern README gợi ý (`gold/pool_*.csv` …) chứa `/`, nên git neo chúng ở gốc repo và không khớp thư mục thật. Dùng `src/evaluation/search_bench/gold/**` để phủ drafts, pool, meta, nhãn và `gold.jsonl`.
- Sau khi thêm luật, checkout lại 4 file gold đang track (lúc đó `git diff` sạch) để working tree về LF.

**Nhánh**
- `origin/main` chưa có `src/evaluation/search_bench/`, nên hai máy nếu chia sau này phải tách từ `bench/embed-search`.

## Kiểm tra

- `git check-attr text`: trả về `unset` cho drafts, pool, meta, nhãn và fixture.
- `git ls-files --eol`: các file gold giờ là `i/lf w/lf`.
- `git cat-file --filters HEAD:…/pool_A.csv | sha256sum` = `6d32e824…` và pool_B = `40fc9e92…`, đúng như `pool_meta.json`.
- `pytest evaluation/search_bench/tests/test_gold_fixtures.py`: **11 passed**.

## Còn lại / rủi ro

- Máy khác đã clone trước commit này mà thấy fixture ở dạng CRLF thì chạy `git rm --cached -r src/evaluation/search_bench/gold src/evaluation/search_bench/tests/fixtures/gold_small && git checkout -- .` (hoặc xoá các file đó rồi checkout lại).
- `README.md` trong thư mục fixture nằm dưới `src/`. AGENTS §7 chỉ cho phép README của workstream ở đó, nên nếu cần thì chuyển nội dung sang `docs/`. Lần này chưa đụng, vì fixture là hợp đồng không được sửa.
