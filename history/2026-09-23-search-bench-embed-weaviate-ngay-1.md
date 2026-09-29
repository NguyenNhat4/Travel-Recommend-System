# sbench ngày 1 (Người B) — text T3+R, embed Cohere + cache, collection Weaviate, query B0

- Ngày: 2026-09-23
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Phần còn lại của ngày 1, vai Người B (`docs/spec/bench/search-eval-checklist.md`), nối tiếp `2026-09-23-search-bench-khung-va-catalog.md`:
- `sb collection create --variant T3+R --model cohere-v3`: named vector `content`, BM25 `word` + fold dấu, `amenity_ids[]`, `parent_product_id`.
- Cohere client: lô ≤ 96, `input_type` đúng chiều, `truncate=NONE`, retry 429 có backoff, log token và chi phí.
- Cache embedding theo `sha1(model|input_type|text)`.
- Chạy thử với sản phẩm mẫu: `sb embed --limit 50` → `sb load` → demo `sb query "resort Nha Trang" --arm B0`.

Phục vụ FR-SRC-01/02/03 và NFR-PERF-03 (cache vector truy vấn); NFR-SEC-01 (key không vào log/commit).

## File thay đổi

- `src/evaluation/search_bench/textbuild.py` — thêm: Part 2 lát ngày 1.
  - `normalize_variant`: base + modifier theo thứ tự chuẩn, bỏ `w60`, cấm `T1+wN`.
  - `T3+R` = `build_text` backend; lỗi cứng nếu không import được.
  - Dấu vân tay builder (`builder_fingerprint`); `load_texts` tự dựng lại khi items, builder hoặc config đổi.
- `src/evaluation/search_bench/tokens.py` — thêm: đếm token offline.
  - Tokenizer Cohere tải một lần; tắt padding/truncation của file tokenizer; không fallback API.
  - Có `token_stats` và `gate`.
- `src/evaluation/search_bench/embed/{__init__,base,cache,cohere_api,fake}.py` — thêm: Part 3.
  - `make_embedder` và `embedder_name` (tính tên embedder, không gọi API).
  - Cache sqlite ghi theo từng lô, đổi chỉ số lỗi về đúng vị trí của người gọi.
  - Cohere `ClientV2`: pacer, retry, ghi `cost.jsonl` cho mọi lượt gọi.
  - Embedder giả `fake` / `fake@noit`.
- `src/evaluation/search_bench/vectors.py` — thêm: file `vec_<V>_<M>[__query][__noit|__int8].npy/.ids.json/.meta.json`.
- `src/evaluation/search_bench/store/{__init__,weaviate_store}.py` — thêm: Part 4 lát ngày 1.
  - Tên logic ↔ vật lý; schema; nạp theo lô.
  - Cờ `complete` + `check_ready`; `dense` / `bm25` / `count` / `list` / `drop`.
- `src/evaluation/search_bench/arms.py`, `arms/B0.yaml` — thêm: nạp arm dạng đã giải; B0 theo `arms.md` §1. Tham chiếu `@` báo "ngày 4".
- `src/evaluation/search_bench/__main__.py` — sửa: thêm lệnh `text`, `tokens`, `embed`, `collection create|list|drop`, `load`, `query`.
- `src/evaluation/search_bench/config.py`, `config/sbench.yaml` — sửa: thêm `weaviate.bm25.stopwords_preset: none` (đề xuất).
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.2 thêm cùng khoá `stopwords_preset` vào khối config.
- `src/evaluation/search_bench/tests/test_{textbuild,embed,cohere_api,tokens,store_arms,weaviate_integration}.py`, `tests/fixtures/text_snapshot_T3+R.json` — thêm: test unit, integration và snapshot 5 text `T3+R`.
- `history/2026-09-23-search-bench-embed-weaviate-ngay-1.md` — thêm: entry này.

## Quyết định

- **`T3+R` = `build_text` của backend** (spec §1.1, `text_builder: app`). T0–T3 và các modifier khác để ngày 4.
- **Tên collection**: logic `products__T3+R__cohere_v3` ↔ vật lý `Products__T3_R__cohere_v3`, thêm `__<dataset>` nếu không phải jsonl (Weaviate cấm `+`).
- **Mô tả collection là JSON nguồn gốc**, ghi: dataset, `items_sha256`, `n`, `cache_model`, `ascii_fold_mode`, bm25, `builder_fingerprint`, `complete`.
  - `sb load` dựng lại collection. Nạp lỗi thì xoá collection; đủ `count` mới đặt `complete: true`.
  - `sb query` từ chối collection chưa `complete`, lệch `count`, dựng từ items cũ, hoặc do embedder khác sinh.
- **`stopwords_preset: none`** (khoá mới, *đề xuất*, cần Người A / mentor xem). Weaviate mặc định dùng preset `en`, bỏ các âm tiết Việt trùng stopword tiếng Anh. Đo trên 26 unit mẫu:
  - preset `en`: bm25 `"an"` ra **0 kết quả**;
  - preset `none`: ra toàn sản phẩm Hội An.
- **Retry**: `max_attempts: 6` hiểu là **số lần thử lại sau lượt đầu**, để dùng đủ 6 mức backoff 1…32 s (tổng 63 s, dài hơn cửa sổ rate limit 60 s). Header `Retry-After` được ưu tiên. Lượt gọi lỗi cũng ghi `cost.jsonl` (`failed: true`), vì quota key trial tính theo lượt.
- **Cache**:
  - ghi sau mỗi lô API, lô lỗi không làm mất lô đã trả tiền;
  - vector sai số chiều coi như chưa có;
  - khoá model gồm `@int8`, `@d<dim>`, `@noit`.
  - File vector của chế độ không mặc định (`__noit`, `__int8`) không đè file mặc định; `sb load` chỉ nạp vector của đúng embedder mặc định.
- **Đếm token offline**: tính cả 2 token đặc biệt/text, khớp số tính tiền của Cohere sau khi trừ 2/text (3.706 − 52 = 3.654 billed). Gate vì thế chặt hơn 2 token.
- **Review đối kháng** (workflow 33 agent, 4 chiều × kiểm chứng): 25 phát hiện được xác nhận, gộp thành 14 lỗi riêng, đã sửa hết trước commit, mỗi lỗi có test hồi quy. 4 phát hiện bị bác (xem "Kiểm tra").

## Kiểm tra

- `pytest evaluation/search_bench/tests` (từ `src/`, `.venv-sbench`): **97 passed, 6 skipped** (integration).
- `pytest -m integration evaluation/search_bench/tests`: **6 passed** — nạp 26 unit mẫu vào collection tạm, gồm các test:
  - count, dense tự khớp top-1, bm25 `"da nang"` ra Đà Nẵng;
  - bm25 `"an"` ra Hội An với stopwords `none`;
  - `check_ready`, chặn tạo đè.
- `pyflakes evaluation/search_bench`: sạch (trừ import cố ý `authlib.deprecate`).
- **Chạy thật Cohere trên 26 unit mẫu** (`--dataset sample`):
  - `embed --limit 50`: mới 26, 1 lượt gọi, 3.654 token, $0,000365.
  - Chạy lại: 0 lượt gọi, 26 từ cache.
  - `load`: 26 object, ascii_fold analyzer, stopwords none.
  - `query "resort Nha Trang" --arm B0`: top-1 Vinpearl Resort & Spa Nha Trang Bay (distance 0,3230), top-2 Vinpearl Beachfront Nha Trang (0,3620).
- **Catalog thật (2.897 unit)**:
  - `sb text --variant T3+R`: 2.897 text, số từ p50 126 / max 240.
  - `sb tokens`: p50 174, p90 224, p99 276, max 379 → **gate qua**.
  - `embed --model fake`: 0,47 s (Done < 10 s); `load --model fake`: 2.897 object trong 7,3–7,9 s (Done < 1 phút); bm25 `"da nang"` top-5 đều Đà Nẵng.
  - `embed --model cohere-v3 --limit 96`: 1 lượt gọi (19.781 token, $0,001978); chạy lại: 0 lượt (Done Part 3).
- `sb cost` tổng đến giờ: 5 lượt gọi (2 embed document, 1 embed query, 1 models.get, 1 tokenize), 23.440 token, **$0,002344**.
- Sau khi sửa: `query` trên collection nạp bằng code cũ bị từ chối (exit 1); nạp lại thì chạy.
- Phát hiện review bị bác:
  - exit 1 thay vì 2 cho model chưa cài;
  - hằng `"1.37"` trong code;
  - snapshot tự so với chính builder (đã thêm snapshot cố định);
  - thiếu test CLI `--limit 96` (đã thêm test tương đương ở tầng embedder).

## Còn lại / rủi ro

- **Người A / mentor**:
  - xác nhận `stopwords_preset: none` (khoá mới, spec §1.2 đã ghi *đề xuất*);
  - xác nhận cách hiểu `retry.max_attempts` = số lần thử lại.
- **Ngày 2 (Người B)**: `sb embed --variant T3+R --model cohere-v3` toàn catalog (~31 lô, ~$0,06 theo token đo được) → `sb load` → B0 = `Products__T3_R__cohere_v3`; `sb gold pool` (cần `hybrid`/filter AST → `store/filters.py`, nhận cả khoá amenity); test Part 4 "50 filter ngẫu nhiên so với pandas" chưa làm.
- `bench_out/search/data/vec_T3+R_cohere-v3.npy` hiện chỉ có 96 vector (lần kiểm Part 3); ngày 2 embed toàn bộ sẽ ghi đè — 96 vector đó đã nằm trong cache nên không tốn lại.
- Collection đang có trên Weaviate sbench:
  - `Products__T3_R__cohere_v3__sample` (26, Cohere thật) — dùng cho demo;
  - `Products__T3_R__fake` (2.897, vector giả) — chỉ để thử khung, xoá lúc nào cũng được.
- `T3+R` là `build_text` production: luôn nối ≤ 60 từ description kể cả mô tả tự sinh, dùng ≤ 10 amenity thô, và description chuyến bay chứa giá.
  - T0–T3 của `textbuild.py` (ngày 4) sẽ khác kiểu viết so với B0.
  - 8.668/10.320 bản ghi dùng dấu kiểu cũ ("Hòa") mà builder không chuẩn hoá — cần xem khi so E1a với B0.
- `text_analyzer` (ascii_fold) của Weaviate 1.37 đang ở mức preview và không đổi được sau khi tạo property; đường lùi là `weaviate.ascii_fold: shadow`.
