# sbench ngày 2 (Người B) — B0 toàn catalog, pacer theo token, filter AST, `gold pool` / `gold split`

- Ngày: 2026-09-24
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu chạy các việc ngày 2 của Người B trong `docs/spec/bench/search-eval-checklist.md` mà không phụ thuộc phần ngày 1 còn chưa tick (mentor xác nhận, mọi việc draft gold của Người A, `gold/drafts.txt`).

- **Chạy được:** embed toàn catalog và load B0.
- **Bị chặn chờ `gold/drafts.txt`:** `sb gold pool` và chia pool. Mình làm sẵn công cụ, thử trên 10 draft fixture, không tạo file nào trong `gold/` (thư mục của A).

Phục vụ FR-SRC-02, FR-SRC-03 (filter), NFR-PERF-03; `docs/prd/test-plan.md` §2.5.

## File thay đổi

- `src/evaluation/search_bench/embed/cohere_api.py` — sửa:
  - `Pacer` giới hạn cả input/phút và token/phút; lô to hơn giới hạn vẫn được gửi khi cửa sổ trống.
  - `preflight` trả số token từng text; `embed` truyền token của mỗi lô cho pacer.
  - Bỏ cảnh báo khi embed query không dùng bộ đếm (cố ý).
- `src/evaluation/search_bench/embed/__init__.py` — sửa: nội dung cảnh báo thiếu tokenizer.
- `src/evaluation/search_bench/config.py`, `config/sbench.yaml` — sửa: thêm `embedding.max_tokens_per_min: 90000` (đề xuất).
- `src/evaluation/search_bench/store/filters.py` — thêm: filter AST của spec Part 4, gồm `validate`, `parse`, `resolve` (khoá amenity → id), `to_weaviate` và `mask` (evaluator pandas).
- `src/evaluation/search_bench/store/weaviate_store.py` — sửa: bật `index_null_state`; `count(filters)`; thêm `fetch_ids`.
- `src/evaluation/search_bench/gold.py` — thêm: `parse_drafts`, `pool_rows`, `build_pool`, `pool_summary`, `split_pool`, `overlap_quota`, `read_pool` / `write_csv` (utf-8-sig).
- `src/evaluation/search_bench/paths.py` — sửa: `GOLD_DIR`.
- `src/evaluation/search_bench/__main__.py` — sửa: lệnh `sb gold pool`, `sb gold split`.
- `src/evaluation/search_bench/tests/test_filters.py`, `tests/test_gold.py`, `tests/fixtures/drafts_small.txt` — thêm.
- `src/evaluation/search_bench/tests/test_cohere_api.py` — sửa: test pacer theo token.
- `docs/spec/bench/search-eval-local-spec.md` — sửa:
  - §1.2 thêm `max_tokens_per_min`;
  - Part 4 ghi chú phần cài filter, `index_null_state`, kết quả 50 filter.
- `docs/spec/bench/search-eval-checklist.md` — sửa:
  - tick "embed + load B0";
  - dòng pool/split ghi "công cụ sẵn sàng, chờ drafts";
  - dòng chia pool sửa theo spec: lẻ/chẵn + stratified.
- `history/2026-09-24-search-bench-ngay-2-b0-filters-pool.md` — thêm: entry này.

## Quyết định

Người dùng chốt ngày 24/09:
- **Chia pool theo spec Part 5**: qid lẻ → A, chẵn → B, 25 query chung chọn stratified theo slice (largest remainder). Checklist cũ ghi 1–100 / 101–200, đã sửa cho khớp.
- **Thêm `max_tokens_per_min: 90000`**. Lý do: embed toàn catalog gặp 22 lượt 429, thành 4 đợt, mỗi đợt sau khoảng 5 lượt × ~18k token. Key trial giới hạn khoảng 90–100k token/phút, không phải 2.000 input/phút.
  - Pacer đếm bằng tokenizer offline (tính cả 2 token đặc biệt/text, nên chặt hơn mức tính tiền).
- **Commit + push** sau khi xong.

Mình tự quyết:
- **`not` trong filter** chỉ bọc `eq` trên trường không bao giờ null hoặc `contains_any` trên `amenity_ids` (cùng quy tắc với `vector_bench/filters.py`). `not contains_any` dịch thành `contains_none`.
  - Kiểm trên Weaviate: sản phẩm có mảng amenity rỗng vẫn thoả, đúng ý "không ghi nhận" ở `arms.md`.
- **Pool:**
  - Embed mọi query trong một lượt gom qua cache.
  - Dense và BM25 cùng filter của draft.
  - Cột đúng spec; nhãn để trống; xáo trong mỗi qid bằng seed `run.seed` + số qid.
  - CSV `utf-8-sig` để Excel hiện đúng tiếng Việt.
  - Draft trùng (query, slice) bị từ chối.

## Kiểm tra

- **Embed toàn catalog** (chạy trước khi viết plan):
  - `sb embed --variant T3+R --model cohere-v3`: 2.897 vector, mới 2.788, từ cache 109.
  - 30 lượt gọi, 451.021 token, **$0,045**, 262 s.
  - 22 lượt 429 được retry thành công và ghi `failed: true` trong `cost.jsonl`.
- **`sb load --variant T3+R --model cohere-v3`**: `Products__T3_R__cohere_v3` có 2.897 object, complete, stopwords none, 5,5 s.
  - `sb query "resort Nha Trang" --arm B0`: top-10 toàn khách sạn/resort ở Nha Trang.
  - `sb query "villa hồ bơi riêng Phú Quốc"`: top-5 resort/villa ở Phú Quốc.
- **Test:**
  - `pytest evaluation/search_bench/tests` (từ `src/`): **125 passed, 9 skipped**.
  - `pytest -m integration`: **9 passed**. Trong đó **50 filter ngẫu nhiên khớp evaluator pandas 100%** (Done của Part 4) và test phủ định giữ sản phẩm không có amenity.
  - `pyflakes`: sạch.
- **Pool thật trên B0 với fixture** (`tests/fixtures/drafts_small.txt`, 10 draft, xuất ra `bench_out/`):
  - 258 dòng, doc/query p50 26, max 30; from: dense 108 · lexical 108 · both 42.
  - Embed query: 9 mới, 1 từ cache (1 lượt gọi).
- **`sb gold split --overlap 3`** trên pool fixture: A có 7 query, B có 6, 3 query chung.
- **`sb cost`** tổng: 59 dòng gọi (gồm 22 lượt 429), 474.535 token, **$0,0475**.

## Còn lại / rủi ro

- **Người A:** giao `gold/drafts.txt`, rồi Người B chạy `sb gold pool` → `sb gold split --overlap 25`. Mỗi lệnh chạy một lần; 200 query tốn khoảng 3 lượt gọi.
- **Người A:** catalog có Sa Pa (524 bản ghi), nên ví dụ out_of_catalog "resort ở Sapa" trong `arms.md` / spec không còn đúng. Chọn query out_of_catalog ngoài 35 điểm đến trong `vocab.json`.
- **Người A / mentor:** xác nhận các giá trị *đề xuất*: `max_tokens_per_min: 90000`, `stopwords_preset: none`, `retry.max_attempts` = số lần thử lại.
- **Chưa làm (ngày 3–4 của A theo checklist):** `sb gold kappa / merge / import / check`. `hybrid` và các arm S* làm ở ngày 6.
- Collection `Products__T3_R__fake` (vector giả) chỉ để thử khung, xoá lúc nào cũng được.
