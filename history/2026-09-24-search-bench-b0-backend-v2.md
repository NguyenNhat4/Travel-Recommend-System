# Search bench: B0 = build_text backend v2, chuyển snapshot 2026-09-23

- Ngày: 2026-09-24
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs
- Tiếp nối: `2026-09-24-gop-checklist-rev3-va-config-test.md` — đóng ba việc dang dở ở đó (định nghĩa B0, snapshot, adapter `combo_items`)

## Mục tiêu

Merge `80c3611` (pull `release-mvp-v1`) đổi `build_text` của backend sang `catalog-text-v2` và thêm snapshot catalog `2026-09-23`. Việc này làm B0 cũ và làm đỏ test snapshot. Người dùng chốt ngày 24/09:
- **B0 = `build_text` backend v2**, truyền `combo_items` như production. Không dùng T3 từ tóm tắt LLM.
- **Chuyển bench sang snapshot `2026-09-23`.**
- **Push một lần** sau khi B0 đã dựng lại.

Phục vụ FR-SRC-02 (B0 là mốc của tìm kiếm ngữ nghĩa) và test-plan §2.5.

## File thay đổi

- `src/evaluation/search_bench/config/sbench.yaml` — sửa: `products_path` / `snapshot_path` trỏ `2026-09-23`.
- `src/evaluation/search_bench/catalog.py` — sửa:
  - `combo_enrichment` tính `combo_items` trong bộ nhớ bằng `data_collection.seed.parse_combos`, gộp dòng soát tay của `combo_items_manual.jsonl`, rồi thêm thuộc tính combo `priceBasis / nights / minPax` như `load_products`.
  - `source_manual_path` tìm file soát tay cạnh snapshot.
  - `stats.path` ghi dạng posix.
- `src/evaluation/search_bench/textbuild.py` — sửa:
  - `T3+R` gọi `build_text(product, children, combo_items=…)` đúng như `PostgresCatalogReader`, tức không truyền `max_desc_words`, không NFC; text không phải NFC chỉ log cảnh báo.
  - Thiếu backend thì báo lỗi, không có đường lùi.
  - Dataset `jsonl` thiếu file soát tay thì báo lỗi.
  - `builder_fingerprint` băm thêm `parse_combos.py`, `textutil.py`, `load_products.py`, `catalog_meta.py` và chính `catalog.py` / `textbuild.py` của bench.
  - Thêm `combo_manual_sha256` và `text_inputs`. `load_texts` dựng lại text khi bất kỳ giá trị nào của `text_inputs` đổi.
  - Meta ghi `text_builder_version` và số liệu `combo_items`.
- `src/evaluation/search_bench/store/weaviate_store.py` — sửa: `check_ready(…, expected)` từ chối collection dựng từ text cũ, tức khi `builder_fingerprint` hoặc `combo_manual_sha256` khác text hiện tại.
- `src/evaluation/search_bench/__main__.py` — sửa:
  - description của collection và meta vector ghi thêm `combo_manual_sha256`; meta vector ghi thêm `text_builder_version`;
  - `query` và `gold pool` gọi `check_ready` kèm `text_inputs` hiện tại.
- `src/evaluation/search_bench/requirements.txt` — sửa: thêm `beautifulsoup4`, vì `textutil` mà `parse_combos` dùng cần nó.
- `src/evaluation/search_bench/arms/B0.yaml` — sửa: description ghi `catalog-text-v2` có `combo_items`.
- `src/evaluation/search_bench/tests/fixtures/text_snapshot_T3+R.json` — sửa: sinh lại bằng `catalog-text-v2`, có khoá `text_builder_version`.
- `src/evaluation/search_bench/tests/test_textbuild.py` — sửa, cập nhật cho v2 và thêm:
  - `test_t3r_equals_production_path` — trên catalog mẫu, chạy `parse_combos.main` + `load_products.convert`, rồi dựng text như `PostgresCatalogReader` (JSONB round-trip, search unit theo view, `combo_items` theo `position`). Text của bench phải trùng khít, kể cả combo có dòng soát tay.
  - `test_manual_change_forces_rebuild` — đổi file soát tay thì text phải dựng lại.
  - `test_jsonl_without_manual_is_an_error`.
  - Snapshot test kiểm `text_builder_version == TEXT_BUILDER_VERSION` và `text_hash == sha1(text)`.
- `src/evaluation/search_bench/tests/test_weaviate_integration.py` — sửa: thêm `test_check_ready_rejects_stale_text`.
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.1 mô tả builder v2 và quyết định của người dùng; §1.2 snapshot `2026-09-23`; Part 1 "Done khi" thêm số 3.183.
- `docs/spec/bench/arms.md` — sửa: định nghĩa B0 ghi `catalog-text-v2`, chốt 24/09.
- `docs/spec/bench/search-eval-checklist.md` — sửa ghi chú, không đổi tick (vẫn 16 mục `[x]`):
  - điều kiện tiên quyết: đã chuyển snapshot;
  - ngày 1 A: dùng `vocab.json` mới;
  - ngày 1 B: `T1/T3/R` và `sb enrich summaries` chỉ còn phục vụ E1a;
  - ngày 2 A: soát tóm tắt không còn chặn B0;
  - ngày 2 B: ⚠ B0 đã xử lý, số embed mới, số `sb tokens` mới; `gold pool` chỉ còn chờ drafts;
  - ngày 4 B;
  - buffer "Tóm tắt LLM chưa xong": không áp dụng.
- `history/2026-09-24-search-bench-b0-backend-v2.md` — thêm: entry này.

## Quyết định

- **B0 giống production từng byte.** Bench không đọc Postgres, nên dựng lại đúng đường production trong bộ nhớ: `parse_combos` + file soát tay + thuộc tính combo của loader, rồi gọi `build_text` với tham số mặc định. Không NFC, không cắt từ riêng; nếu bench tự chuẩn hoá thì B0 sẽ lệch production.
- **Mọi đầu vào của text đều đi vào fingerprint.** Gồm code builder, code dựng `combo_items` và file soát tay. Đổi bất kỳ thứ nào thì `sb text` dựng lại; `sb query` / `sb gold pool` từ chối collection cũ, thay vì chạy êm trên vector lệch text.
- **Chuyển snapshot kéo theo:** `amenity_vocab.json` và `vocab.json` dựng lại, id amenity `raw:*` đổi. A phải dùng `vocab.json` mới và ghi **khoá** amenity trong draft, không ghi id.
- **`T1` / `T3` / `R` của `textbuild.py` và `sb enrich summaries`** chuyển thành việc của cổng E1a (ngày 4), không chặn B0 hay pool.
- Không lệch PRD: FR-SRC-02 và `data-model.md` không quy định cách dựng text embed; B0 chỉ bám theo code production hiện có.

## Kiểm tra

- **So khớp với production**, workflow độc lập: chạy `parse_combos` + `load_products` trong thư mục tạm → **3.183/3.183** text của bench trùng khít text production trên snapshot 2026-09-23. Test `test_t3r_equals_production_path` giữ điều này trên catalog mẫu.
- `pytest evaluation/search_bench/tests`: **146 passed, 10 skipped**.
- `pytest -m integration`: **10 passed**, Weaviate local 1.37.3; gồm 50 filter ngẫu nhiên so với pandas và `check_ready` từ chối text cũ.
- `pyflakes evaluation/search_bench`: sạch.
- **Dựng lại B0** trên snapshot 2026-09-23 (11.387 dòng → 3.183 search unit):
  - `sb text`: 3.183 text, số từ p50 102 / max 197; 133 combo, 307 dòng `combo_items`, 64 dòng soát tay.
  - `sb tokens`: p50 142, p90 201, p99 234, max 299 — **qua gate**.
  - `sb embed --model cohere-v3`: 3.183 vector mới, **34 lượt gọi, 425.088 token, $0,0425, 304 s, 0 lượt 429** (mọi lượt thành công ngay lần đầu, pacer 90k token/phút).
  - `sb load`: `Products__T3_R__cohere_v3` 3.183 object, complete, stopwords none, fold analyzer.
- **Sample và fake:**
  - `Products__T3_R__cohere_v3__sample` nạp lại: 26 object, 12 text mới, 1 lượt gọi, $0,00015.
  - `Products__T3_R__fake` nạp lại: 3.183 object, embedder giả, không gọi API. Ba collection giờ cùng items `90e9ae5110`.
- **Truy vấn kiểm tra:**
  - `sb query "resort Nha Trang" --arm B0`: top-10 đều là khách sạn / resort Nha Trang; top-1 Nha Trang Marriott Resort & Spa (0,264).
  - `"combo Phu Quoc 3 ngay 2 dem"`: top-10 toàn Phú Quốc, có 3 combo.
  - `"da nang" --mode bm25`: khớp "Đà Nẵng" nhờ fold.
- **`sb gold pool` trên fixture 10 draft:** 255 dòng, p50 26 / max 30 doc/query, 0 query rỗng, mọi query embed lấy từ cache. `sb gold split --overlap 3`: A 7 query / 173 dòng, B 6 query / 161 dòng.
- **Chi phí Cohere** chiều 24/09: 36 lượt, 426.640 token, **$0,0427**; cộng dồn từ đầu $0,090.

## Còn lại / rủi ro

- `sb gold pool` / `split` thật vẫn chờ `gold/drafts.txt` của A. Draft phải dựng trên `vocab.json` mới (snapshot 2026-09-23).
- Kết quả demo `--dataset sample` ghi ở checklist ngày 1 (23/09) là của builder cũ; sample đã nạp lại bằng v2, nên top-k có thể khác.
- Backend đổi `build_text` hoặc `parse_combos` lần nữa thì fingerprint đổi: phải `sb text` → `sb tokens` → `sb embed` → `sb load` lại B0, và cập nhật snapshot test có chủ đích.
- Đề xuất `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` vẫn chờ chốt; không ảnh hưởng bench local (index flat).
