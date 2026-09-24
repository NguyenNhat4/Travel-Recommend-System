# Gộp checklist search bench (rev 3) và config riêng cho test

- Ngày: 2026-09-24
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: dang dở
- Phạm vi: docs, evaluation

## Mục tiêu

Người dùng yêu cầu hai việc:
1. **Dùng config riêng cho test.** Đây là đề xuất từ entry `2026-09-24-search-bench-metrics-bootstrap.md`: `gold check` (spec Part 5) phải xanh trên `gold_small.jsonl`, trong khi fixture chỉ có 10 query cho 9 slice và config thật yêu cầu `min_per_slice: 10`.
2. **Gộp hai file checklist làm một.** Người dùng đưa vào bản sửa `docs/spec/bench/SEARCH_EVAL_CHECKLIST.md` (chưa track). Lấy file đã tick (`search-eval-checklist.md`) làm chuẩn, bổ sung những gì mới từ file kia.

## File thay đổi

- `src/evaluation/search_bench/config.py` — sửa: thêm `deep_merge`; `load_config(…, overrides_path=…)` gộp đè một phần config (chỉ dùng cho test).
- `src/evaluation/search_bench/tests/fixtures/config_test_overrides.yaml` — thêm: config riêng cho test, `gold.min_per_slice: 1`.
- `src/evaluation/search_bench/tests/conftest.py` — sửa: fixture `test_cfg`.
- `src/evaluation/search_bench/tests/test_config.py` — sửa: thêm 4 test:
  - config test chỉ đổi khoá được liệt kê;
  - `deep_merge` không sửa bản gốc;
  - phần ghi đè vẫn được validate;
  - `gold_small.jsonl` đạt config test nhưng không đạt config thật.
- `docs/spec/bench/search-eval-local-spec.md` — sửa: dòng "Done khi" của Part 5 ghi rõ `gold check` trên fixture dùng config riêng cho test.
- `docs/spec/bench/search-eval-checklist.md` — sửa: gộp rev 3 và sửa ghi chú (chi tiết ở "Quyết định").
- `docs/spec/bench/SEARCH_EVAL_CHECKLIST.md` — xoá: file chưa track, đã gộp hết nội dung. Không khôi phục được từ git; bản sao nằm trong scratchpad của phiên làm việc.
- `history/2026-09-24-gop-checklist-rev3-va-config-test.md` — thêm: entry này.

## Quyết định

**Nội dung lấy từ bản sửa.** So từng dòng hai chiều: có 6 thay đổi thật, đều xoay quanh tóm tắt LLM (T3).
- Ngày 1 B, thêm hai mục:
  - "Text builder tối thiểu cho B0: base T1, T3 + R";
  - `sb enrich summaries` chạy nền, dời từ ngày 4 lên. Giữ quy tắc "A soát, B không tự soát".
- Ngày 2 A, thêm mục: soát `summaries_review.csv` trước khi B embed toàn catalog.
- Ngày 4 B:
  - mục text builder đổi thành "phần còn lại: T0, T2, DF, KV, NUM, w30/w150/wfull";
  - bỏ mục enrich cũ.
- Buffer, thêm dòng: "Tóm tắt LLM chưa xong cuối ngày 1".
- Mọi chỗ lệch khác của bản sửa là tên và đường dẫn cũ mà file chuẩn đã sửa từ trước, nên giữ bản của file chuẩn:
  - `SEARCH_EVAL_LOCAL_SPEC.md`, `ARMS.md`, `SCHEMA.md`, `gold/GUIDE.md`, `gold/prompts/draft.md`;
  - nhánh `eval/search-bench`, `docker/compose.yml`;
  - "50 sản phẩm", "qid 1–100".

**Ghi chú trạng thái.** Các mục mới đều chưa tick và đều có ghi chú ngày 24/09. Sau khi kiểm độc lập, thêm hoặc sửa các ghi chú sau:
- Điều kiện tiên quyết: snapshot `2026-09-23` (11.387 dòng) nay là mặc định của repo; `config/sbench.yaml` vẫn trỏ 2026-09-21.
- Ngày 2 B, embed B0 — ⚠ B0 đã cũ:
  - merge `80c3611` đổi `build_text` backend sang `catalog-text-v2`, nên builder_fingerprint khác;
  - adapter của bench chưa truyền `combo_items` như production;
  - spec §1.1 còn mô tả builder cũ.
- Ngày 2 B, `sb tokens`: số đo có từ trước v2.
- Ngày 2 B, `gold pool`: chờ thêm B0 dựng lại, vì hiện chỉ kiểm items, chưa kiểm builder.
- Ngày 4 B: mang sang T1 / T3 / R nếu mục ngày 1 chưa xong.
- Buffer: dòng mới chỉ áp dụng nếu chốt B0 = T3 từ tóm tắt LLM.
- Định nghĩa T3 ghi đúng spec Part 2: tóm tắt LLM chỉ khi description tự sinh.
- Dọn tên cũ có từ trước khi gộp: `SCHEMA.md` → `docs/spec/data-collection/schema.md`, `GUIDE` → `gold-guide.md`.

**Config riêng cho test** là file ghi đè nhỏ, gộp đè lên `config/sbench.yaml` rồi validate như config thật. Không có file config thứ hai đầy đủ, để tránh hai bản lệch nhau theo thời gian.

## Kiểm tra

- Workflow kiểm độc lập bản gộp, 3 agent chỉ đọc:
  - Độ đầy đủ: OK. Mọi thứ của bản sửa đã có; 16 mục tick và mọi ghi chú giữ nguyên; không trùng; đúng thứ tự.
  - Độ chính xác: OK. Mọi số khớp history; các ghi chú đánh dấu "dễ gây hiểu lầm" đã sửa như trên.
  - Quy tắc repo: yêu cầu entry history (entry này) và chốt định nghĩa B0. Không lệch PRD, vì FR-SRC-02 và data-model không quy định cách dựng text.
- Sau khi sửa: 16 mục `[x]`, không còn `GUIDE` hay `SCHEMA.md` trong checklist.
- `pytest evaluation/search_bench/tests`: **141 passed, 1 failed, 9 skipped**.
  - Test đỏ là `test_textbuild.py::test_t3r_snapshot`.
  - Nguyên nhân là merge `80c3611` (pull `release-mvp-v1`, 24/09 12:36) đổi `src/backend/app/domain/catalog/text_builder.py` sang `catalog-text-v2`. Test snapshot bắt đúng thay đổi này, như thiết kế.
  - Không tự cập nhật snapshot: chờ người dùng chốt định nghĩa B0.
- `test_config.py`: 11 passed. `pyflakes`: sạch.

## Còn lại / rủi ro

Người dùng cần chốt, nên entry để **dang dở**:
1. **B0 là gì.**
   - (a) Giữ `build_text` backend, giờ là catalog-text-v2, như production. Khi đó mục ngày 1 "text builder tối thiểu cho B0" và dòng buffer phải viết lại: T1 / T3 / R phục vụ E1a, không phải B0.
   - (b) B0 = `T3+R` của `textbuild.py` với tóm tắt LLM. Khi đó phải sửa spec §1.1, `textbuild.py`, `arms.md`, và B0 không còn giống production.
   - Chọn cách nào thì cũng phải cập nhật snapshot `T3+R`, embed và load lại B0 (~30 lượt gọi, ~$0,05).
2. **Snapshot catalog.** Chuyển bench sang `2026-09-23` (mặc định mới của repo) hay giữ `2026-09-21`. Chuyển thì phải dựng lại catalog, vocab và B0, và A phải dùng `vocab.json` mới cho draft.
3. **Adapter text builder của bench** chưa truyền `combo_items` như production (`postgres_store.py`). Cần làm nếu chọn (a).
4. Đề xuất đang chờ chốt `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` (index `hfresh` trên Weaviate Cloud) không ảnh hưởng bench, vì bench chạy local với index flat. Cần tính đến khi đưa luồng thắng vào backend ở ngày 8.
