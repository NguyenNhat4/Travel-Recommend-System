# App gold: bộ 200 câu đã chọn + thay thế, bổ sung câu hỏi theo ý định, tra cứu catalog; sửa c0241 / c0503 / c0531

- Ngày: 2026-09-28
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu ngày 28/09:
1. Thêm các box để tự bổ sung câu hỏi cho từng slice, có hiện các ý định đã có.
2. Sửa c0241 / c0503 / c0531 theo phương án đã đề xuất (người dùng đồng ý).
3. Thêm dashboard cho biết điểm đến nào có dữ liệu, kèm chỗ tìm sản phẩm, để gán nhãn chính xác hơn.
4. (chiều) App phải hiện rõ 200 câu đã chọn và 42 câu `--fill`, cho chọn câu thay thế bằng dropdown.
5. (tối) Khi không có câu phù hợp trong danh sách, cho viết ngay câu thay thế. Giải thích source_refs là gì, và hiện thông tin sản phẩm để chọn source_refs cho case mới.

Phục vụ FR-SRC-01..04, AC-SRC-01. Không lệch PRD: đây là công cụ đánh giá offline.

## File thay đổi

- `src/evaluation/search_bench/gold/overrides.tsv` — sửa: thêm 3 dòng NEEDS_EDIT, mỗi dòng có note:
  - c0241 "không ghi nhận" → "không có";
  - c0503 và c0531 "0.5 triệu" → "500 nghìn"; filter giữ nguyên.
- `src/evaluation/search_bench/gold/drafts.txt` — sửa: 3 dòng tương ứng, giống hệt bản `gold drafts` sẽ sinh ra từ overrides. Máy này chưa có `labels.jsonl` nên không sinh lại được.
- `src/evaluation/search_bench/draft_authoring.py` — thêm:
  - trạng thái từng ý định theo slice: trong drafts.txt / đã loại / cùng khoá với ý định đã chọn / khoá đã bị loại / chưa dùng;
  - `slice_summary` đánh dấu slice mỏng;
  - `validate`, kiểm grounding: trùng câu, trùng khoá ý định, `source_refs`, `filter_json`, điểm đến ngoài catalog, quota;
  - `append_intent`: ghi `drafts_raw.tsv` với mã c0673… theo khối 3, và tuỳ chọn KEEP vào `overrides.tsv`.
- `src/evaluation/search_bench/catalog_lookup.py` — thêm:
  - `load_catalog` / `catalog_from`;
  - bảng điểm đến × loại;
  - tỷ lệ tiện ích theo điểm đến;
  - `criteria_filter`: đổi tiêu chí tìm kiếm thành filter AST;
  - `search`: bỏ dấu, mọi từ đều phải có, xếp theo số từ khớp trong tên;
  - `place_hits`: kiểm địa danh ngoài catalog theo nguyên cụm từ, xét tên, điểm đến, tỉnh, thành phố;
  - `known_refs`;
  - `describe` / `short_label` / `context_of`: thông tin sản phẩm cho bảng và ô chọn source_refs.
- `src/evaluation/search_bench/streamlit_app.py` — sửa:
  - thêm ô chọn chế độ: "Soát câu hỏi" (chế độ cũ, bọc vào `render_review`), "Bộ 200 câu đã chọn" (`render_selection`), "Bổ sung câu hỏi", "Tra cứu catalog";
  - ô tên người sửa dùng chung giữa các chế độ;
  - mục "✎ Viết câu thay thế" (cùng ý định / ý định mới), ô chọn source_refs có lọc, bảng source_refs kèm giải thích;
  - cache danh sách case khoá theo mtime + size của `drafts_raw.tsv`, sửa lỗi phải khởi động lại mới thấy dòng mới;
  - caption không còn ghi cứng số "600";
  - thêm `src` vào `sys.path` để import package;
  - thêm biến môi trường `SBENCH_GOLD_DIR` / `SBENCH_DATASET`;
  - kho nhãn mặc định là đường dẫn tuyệt đối `paths.sbench_home()/labels/labels.jsonl`, sidebar hiện đường dẫn này. Trước đây là đường dẫn tương đối theo thư mục chạy `streamlit run`: chạy từ `src/` sẽ đọc một kho trống và thấy "chưa gán gì".
- `src/evaluation/search_bench/gold.py` — sửa: `write_drafts` ghi LF bằng `write_bytes`. Trước đây `write_text` trên Windows ghi CRLF, nên `gold drafts` biến cả 200 dòng `drafts.txt` thành diff và làm đổi `drafts_sha256`.
- `src/evaluation/search_bench/tests/test_gold_drafts.py` — sửa: thêm `test_write_drafts_uses_lf`.
- `src/evaluation/search_bench/draft_selection.py` — thêm:
  - `compute`: tính lại bộ câu như `gold drafts --fill`;
  - `selected_table`: nguồn từng câu;
  - `alternatives`: cách nói khác, ý định khác;
  - `decision_rows`: thao tác replace / keep / drop;
  - `upsert_overrides`: thay tại chỗ theo `case_id`, kiểm cả file trước khi ghi;
  - `diff_with_file`, `write_drafts`;
  - `check_rewrite`, cùng hai thao tác `rewrite` (NEEDS_EDIT, cùng ý định) và `replace_new` (REJECT câu cũ khi đã tạo case mới).
- `src/evaluation/search_bench/gold.py` — sửa thêm: `make_fill_guard(items)` (tách từ `__main__._fill_guard`), `drafts_lines(rows)` (tách từ `write_drafts`).
- `src/evaluation/search_bench/__main__.py` — sửa: `_fill_guard` gọi `gold.make_fill_guard`.
- `src/evaluation/search_bench/tests/test_draft_selection.py` — thêm: 6 test: nguồn và `--fill`, lựa chọn thay thế, thay bằng ý định khác, thay cách nói / giữ / loại, giữ NEEDS_EDIT, từ chối override sai.
- `src/evaluation/search_bench/tests/test_catalog_lookup.py` — thêm: 6 test.
- `src/evaluation/search_bench/tests/test_draft_authoring.py` — thêm: 6 test, gồm cả việc ý định tự thêm có KEEP được `select_drafts` chọn khi quota còn chỗ.
- `src/evaluation/search_bench/tests/test_streamlit_app.py` — thêm: 3 AppTest:
  - render các chế độ;
  - lưu một ý định qua form;
  - chế độ "Bộ 200 câu đã chọn": thay một câu bằng dropdown, rồi ghi `drafts.txt` (trên bản sao `gold/` trong tmp).
- `docs/plan/2026-09-23-search-labeling-app.md` — sửa: thêm mục mô tả hai chế độ mới.
- `docs/spec/bench/README.md` — sửa: ghi chú tiến độ ở hai mục "Còn phải làm tay".
- `history/2026-09-28-app-bo-sung-cau-hoi-va-tra-cuu-catalog.md` — thêm: entry này.

Ngoài repo: cài `streamlit 1.64.0` (đã pin trong `requirements.txt`) vào `.venv-sbench`.

## Quyết định

**Luồng ghi.**
- Ý định tự thêm đi đúng luồng sẵn có, không tạo file mới: `drafts_raw.tsv` + `overrides.tsv` (KEEP, note ghi tên người thêm), rồi `gold drafts --fill`.
- Mã case cấp theo khối 3, vì `gold.intent_key` coi 3 mã liền nhau là 1 ý định. Cấp mã nối tiếp sẽ gộp nhầm hai ý định khác nhau.

**Không đổi quota.**
- Câu dự phòng chỉ vào `drafts.txt` khi nâng `gold.slices`.
- Người dùng chưa chốt tổng 210 hay giữ 200, nên app chỉ cảnh báo, không sửa config.

**Slice mỏng** = quota ≤ `min_per_slice` và hết ý định dự phòng.
- Với dữ liệu hiện tại, 4 slice bị đánh dấu: `amenity_multi`, `amenity_negation`, `amenity_offtaxonomy`, `cross_vertical`.
- `out_of_catalog` còn 6 ý định trông như "chưa dùng" (Tam Đảo, Lạng Sơn). Người soát đã loại hai điểm đến này trong app, nhưng `labels.jsonl` không có trên máy này. Giao diện có ghi chú rằng trạng thái chỉ dựa trên `drafts.txt` + `overrides.tsv`.

**Kiểm grounding lấy từ bài học phản biện 24/09:**
- điểm đến ngoài catalog phải không bị bất kỳ tên, điểm đến, tỉnh hay thành phố nào nhắc tới (c0571 "Ha Giang Loop Office", c0581);
- filter multi_constraint nên khớp 5–40 sản phẩm;
- tiện ích phủ trên 80% thì câu hỏi không lọc được gì (c0430).

**Tra cứu catalog chỉ đọc dữ liệu bench** (`items.parquet`, `amenity_vocab.json`), không gọi Weaviate hay Cohere. Filter dựng ở tab tìm sản phẩm có đúng định dạng của drafts (khoá amenity), và mang sang được box multi_constraint.

**App chỉ nghe ở `127.0.0.1`** khi chạy thử trên máy này: chưa có mật khẩu (`.streamlit/secrets.toml`), mà chế độ bổ sung ghi thẳng vào file của repo.

## Kiểm tra

- `pytest evaluation/search_bench/tests`: **245 passed, 10 skipped** (trước đó 218, thêm 27). Riêng AppTest có:
  - viết lại cùng ý định;
  - viết ý định mới có chọn source_refs, ghi đúng c0673 KEEP cộng REJECT câu cũ.
  - Lưu ý với AppTest: giá trị multiselect có `format_func` phải nằm trong danh sách lựa chọn; nếu không, AppTest lưu chuỗi nhãn thay vì product_id.
- AppTest chế độ "Bộ 200 câu đã chọn" trên dữ liệu thật (không ghi file):
  - 200/200 câu: người soát 140 · `overrides.tsv` 18 · `--fill` 42;
  - "gold/drafts.txt khớp lựa chọn hiện tại";
  - câu đầu tiên đang xem là c0025 (`--fill`), có 8 lựa chọn trong dropdown.
- Kho nhãn có trên máy này (`bench_out/search/labels/labels.jsonl`, chép vào 28/09):
  - 546 event, 512 case; qanh 278, khoi 242.
  - `gold drafts --fill --dry-run`: lấp 42 ý định (35 chưa gán, 7 bị loại vì cách nói). Báo cáo lưu ở `bench_out/search/fill_dry_run.txt`.
  - `drafts.txt` sinh lại từ kho nhãn + `overrides.tsv` **trùng từng byte** với file đang sửa, tức 3 câu c0241 / c0503 / c0531 sửa tay đúng như pipeline tạo ra.
- `pyflakes evaluation/search_bench`: sạch, trừ cảnh báo có sẵn về lượt import `authlib.deprecate`.
- AppTest trên dữ liệu thật (catalog `jsonl`, `gold/` của repo, không ghi file):
  - "Tra cứu catalog": 3 bảng, không lỗi;
  - "Bổ sung câu hỏi": 13 box, 14 bảng, không lỗi.
- Số liệu thật:
  - 38 điểm đến / 3.183 search unit;
  - "vinpearl nha trang" ra 4 khách sạn Vinpearl Nha Trang đầu tiên;
  - `place_hits`: "Cà Mau" 0, "Mộc Châu" 0, "Hà Giang" 1 (Hostel … Ha Giang Loop Office);
  - Đà Nẵng: wifi phủ 91%;
  - `next_block_start` = 673.
- `streamlit run … --server.address 127.0.0.1 --server.port 8501`: `/_stcore/health` = ok.

## Còn lại / rủi ro

- **Soát 42 câu `--fill`:** danh sách ở `bench_out/search/fill_dry_run.txt`; soát trong chế độ "Soát câu hỏi" rồi chạy `gold drafts --fill`.
- **Chốt quota** để câu dự phòng vào `drafts.txt`: tổng 210, hay giữ 200 bằng cách giảm slice lớn.
- **Chưa commit:** chờ người dùng yêu cầu.
