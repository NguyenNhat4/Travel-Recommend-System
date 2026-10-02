# Gold CLI (việc của máy 1): pool/split theo hợp đồng, gold-guide, kappa · merge · import · check

- Ngày: 2026-09-25
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Làm việc của máy 1 theo `docs/spec/bench/prompts/may1-gold-cli.md` ngay trên `bench/embed-search`. Người dùng chốt ngày 25/09: chưa chia 2 máy; luật destination theo đề xuất may1; chỉ commit local.

Bốn phần việc:
1. `sb gold pool` / `split` xuất đúng hợp đồng `gold_schema.py`.
2. Viết `gold-guide.md`.
3. Thêm bốn lệnh `kappa`, `merge`, `import`, `check`, ra đúng đáp án của fixture `gold_small/`.
4. Sửa tài liệu cho khớp.

Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5. Không lệch PRD, vì PRD không quy định định dạng gold. Việc tiếp nối entry `2026-09-25-gold-buoc-0-schema-fixtures.md`.

## File thay đổi

- `src/evaluation/search_bench/gold.py` — sửa, viết lại phần pool/split và thêm phần ngày 3–4; phần `sb gold drafts` giữ nguyên:
  - lỗi tách hai loại: `GoldError` → exit 2, `RuleViolation` → exit 1;
  - `qid_num`; `case_ids_for`: map drafts sang `case_id` qua `drafts_raw.tsv` và `overrides.tsv`;
  - `split_filter`: `unit_price_min` → `child_filter.unit_price`; kèm `validate_child_filter` và `render_filter_text`;
  - `PoolView`, `load_pool_view`, `pick_amenities`, `pool_rows` / `build_pool`: ghi `PoolRow` của schema;
  - `PoolBuild` (`pool.build.json`);
  - `split_pool`: câu riêng chia xen kẽ A/B trong từng slice, mỗi người một thứ tự xáo; `write_split` ghi `pool_meta.json`;
  - `load_pool_set`, `load_labels`, `cohen_kappa`, `overlap_pairs`, `merge_pair` / `merge_labels`, `read_catalog_parents`, `build_gold`, `write_gold_checked`, `check_gold`;
  - bỏ định dạng pool cũ: `POOL_COLUMNS`, `write_csv` / `read_pool` bằng pandas, cột `label`.
- `src/evaluation/search_bench/__main__.py` — sửa:
  - `gold pool` thêm `--qid case|line`, `--raw`, `--allow-empty`; ghi pool theo hợp đồng và kèm `pool.build.json`;
  - `gold split` thêm `--force`; kiểm sha pool; ghi `pool_meta.json`;
  - thêm lệnh `gold kappa`, `gold merge`, `gold import`, `gold check`;
  - thêm `_gold_errors()` để đổi lỗi thành mã thoát 0 / 1 / 2; ghi mã thoát vào help và docstring.
- `src/evaluation/search_bench/metrics.py` — sửa: `constraint_filter` đưa điều kiện `child_filter` `unit_price lte/lt` về `unit_price_min`, để constraint precision vẫn chấm được giá; `GoldQuery.child_filter`.
- `src/evaluation/search_bench/logsetup.py` — sửa: structlog lấy `sys.stderr` lúc ghi log, không phải lúc configure. `CliRunner` thay rồi đóng stderr sau mỗi lệnh; trước khi sửa, các test chạy sau đó lỗi "I/O operation on closed file".
- `src/evaluation/search_bench/tests/test_gold.py` — sửa, viết lại cho định dạng mới: parse, `case_id` (fixture và 200 draft thật), tách filter, `filter_text` so với c9003, tiện ích, `pool_rows` round-trip qua `read_pool_csv`, `build_pool` truy xuất với filter đầy đủ, split, `pool.build.json`, và integration pool trên collection tạm.
- `src/evaluation/search_bench/tests/test_gold_cli.py` — thêm: 27 test CLI bằng `CliRunner`:
  - đáp án fixture: κ, merge đúng từng byte, import bị từ chối rồi đúng từng byte, check;
  - ca âm của may1: κ thấp, thiếu nhãn, pool bị sửa, id lạ, cặp ngoài pool, câu không có nhãn 2, out_of_catalog có nhãn 2;
  - ca thêm: `pool_sha` cũ, file nhãn tráo A/B, con của sản phẩm khác, ghi đè gold, slice lạ, trùng qid, câu `retired`, split qua CLI.
- `src/evaluation/search_bench/tests/test_metrics.py` — sửa: thêm `test_constraint_filter_folds_child_price`.
- `docs/spec/bench/gold-guide.md` — thêm: hướng dẫn gán nhãn một trang, gồm:
  - luật destination đã chốt;
  - parent_child, tiện ích, out_of_catalog;
  - 7 ví dụ khó lấy từ fixture;
  - cách sửa dòng `needs_discussion`.
- `docs/spec/bench/search-eval-local-spec.md` — sửa:
  - §1.1: thư mục `gold/`;
  - §1.3: chữ ký lệnh;
  - Part 5: định nghĩa nhãn trỏ sang guide, dẫn chiếu hợp đồng, mã thoát, bảng lệnh pool / split / kappa / merge / import / check, "Done khi" theo `gold_small/`;
  - Part 11: holes dùng `POOL_COLUMNS`.
- `docs/spec/bench/search-eval-checklist.md` — sửa:
  - tick mục viết `gold-guide.md`;
  - ghi chú pool/split;
  - sửa lệnh cũ ở ngày 3–4: `kappa`, `merge`, `import`;
  - dòng buffer về định nghĩa nhãn 1.
- `history/2026-09-25-gold-cli-pool-kappa-merge-import-check.md` — thêm: entry này.

## Quyết định

**qid = `case_id`.**
- `drafts.txt` không có cột case_id, nhưng 200/200 dòng map được qua `drafts_raw.tsv`; 8 dòng trong số đó cần thêm `edited_query` của `overrides.tsv`.
- qid theo thứ tự dòng (`q001…`) sẽ dịch chuyển khi `sb gold drafts` chạy lại, ví dụ lúc soát 42 câu `--fill` hay thêm câu dự phòng. qid lại là khoá vĩnh viễn sau `gold_v1`. Fixture cũng dùng kiểu `c9001`.
- `--qid line` vẫn còn cho fixture 10 draft.

**Filter.**
- Điều kiện giá của drafts (`unit_price_min`) chuyển sang `child_filter_json` với tên `unit_price`, đúng theo may1.
- Truy xuất Weaviate vẫn dùng filter đầy đủ: `unit_price_min ≤ X` là điều kiện cần của "có phòng ≤ X", nên pool không bị lấp bởi khách sạn vượt giá, mà người gán lại được dặn không chấm giá.
- Metrics chuyển ngược `unit_price ≤ X` về `unit_price_min ≤ X` khi chấm constraint precision.
- `max_occupancy` / `departure_date` chưa chấm được, vì items không có cột tương ứng.

**Split.**
- Câu riêng chia xen kẽ A/B trong từng slice, thay cho lẻ/chẵn: chẵn/lẻ theo case_id bị lệch theo slice (audience_style 13/7).
- Mỗi người thấy ứng viên theo một thứ tự xáo riêng, giống fixture.
- Nếu `gold/labels/` đã có nhãn thì không ghi đè meta, trừ khi có `--force`.

**Merge.**
- Cả hai gán 2 mà phần giao hạng phòng rỗng: chỉ tính `needs_discussion` ở slice parent_child. Làm khác thì các cặp 2/2 không có hạng phòng của fixture sẽ bị đánh dấu nhầm.
- Note của người gán được nối vào sau (` | A: …`); fixture không có note nên vẫn khớp từng byte.
- Kappa và merge kiểm `pool_sha` của từng nhãn, và kiểm file nhãn có đúng người gán ở đúng vị trí không.

**Import.**
- Gom đủ mọi lỗi rồi mới từ chối, và không ghi file khi có lỗi.
- Catalog mặc định là `products.jsonl` của config (tự bung snapshot nếu thiếu). `parentProductId` đọc ở cấp đầu hoặc trong `attributes`.
- File `-o` đã có mà khác nội dung → exit 2, trừ khi có `--overwrite` (Part 11: gold chỉ thêm).

**Check.**
- Chỉ xét slice có mặt, vì fixture có 7/13 slice mà phải xanh với N = 1. Slice cấu hình mà vắng thì chỉ cảnh báo.
- Không thêm `--catalog`, vì Part 11 đã dành cờ đó cho nghĩa khác.

**B0 được nạp lại.**
- Merge `318f91a` (release-mvp-v1) sửa `backend/.../catalog/models.py`, là một trong các file tạo `builder_fingerprint`. Vì vậy `check_ready` chặn `gold pool`, đúng như thiết kế.
- `sb text` dựng lại ra 3.183 text trùng khít bản đã embed (`texts_digest` = `text_sha256` trong meta vector).
- `sb embed` lấy toàn bộ từ cache (0 lượt gọi, $0); `sb load` nạp 3.183 object.

## Kiểm tra

**Test**
- `pytest evaluation/search_bench/tests` (unit): **218 passed, 10 skipped**. Gồm 11 test bước 0, 27 test CLI và 22 test trong `test_gold.py`.
- `pytest -m integration`: **10 passed** trên Weaviate local 1.37.3, cả trước lẫn sau khi sửa `logsetup.py` (lần sau mất 53 s). Bộ này gồm pool trên collection tạm với view thật của sample.
- `pyflakes evaluation/search_bench`: sạch, trừ cảnh báo có sẵn về lượt import `authlib.deprecate` có chủ đích.

**Đáp án fixture** (thư viện và CLI):
- κ n = 12, ma trận nhầm `[[3,0,0],[1,3,0],[1,0,4]]`;
- κ: không trọng số 0,752577 · **linear 0,731343** · quadratic 0,711538;
- `merge` trùng từng byte `merged_expected.csv`;
- `import merged_expected.csv` bị từ chối vì còn c9007/P003 `needs_discussion`;
- `import merged_resolved.csv --catalog catalog_small.jsonl` trùng từng byte `gold_expected.jsonl`;
- `check --min-per-slice 1` xanh, mặc định 10 thì đỏ.

**Chạy thật trên B0 local**
- 10 draft fixture (`--qid line`):
  - `pool`: 280 dòng, 26–30 ứng viên/câu (p50 28), 10/10 query lấy từ cache;
  - `split --overlap 3`: A 7 câu / 195 dòng, B 6 câu / 170 dòng;
  - `load_pool_set` đọc được cả hai file, sha trong meta khớp.
- 200 draft hiện tại (thử, ghi vào `bench_out/search/gold_trial/`, không vào `gold/`):
  - `pool`: 5.046 dòng, 6–30 ứng viên/câu (p50 26), không câu nào rỗng;
  - `split`: A 113 câu / 2.871 cặp, B 112 câu / 2.830 cặp, 25 câu chung trải đủ 13 slice.
- Chi phí Cohere thêm khoảng $0,0002 (200 lượt embed câu hỏi); tổng cộng dồn $0,0903.

## Còn lại / rủi ro

- **Pool thật vào `gold/`** chỉ chạy sau khi đóng băng `drafts.txt`, tức đã soát 42 câu `--fill`, sửa c0241 / c0503 / c0531, và thêm câu dự phòng cho 5 slice mỏng (README bước 0). Khi đó chạy `sb gold pool` → `sb gold split` và commit `pool.csv`, `pool.build.json`, `pool_A.csv`, `pool_B.csv`, `pool_meta.json`.
- **Mốc 1:** hai người đọc `gold-guide.md` và thống nhất các ví dụ khó.
- **Mốc 2:** app gán nhãn (máy 2) xuất nhãn trên fixture, rồi `kappa` / `merge` ra đúng đáp án. Phần kiểm bằng CLI trên file fixture đã xanh.
- **Metrics** chưa chấm `max_occupancy` / `departure_date` trong `child_filter`.
- **Entry `history/2026-09-25-bo-sung-summary-tien-do.md` (chưa track)** ghi về `src/evaluation/reports/summary.md`, nhưng file đó đã bị xoá khỏi working tree, nên entry này không được đưa vào commit nào.
