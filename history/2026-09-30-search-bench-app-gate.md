# Search bench: cổng APP — chạy `SearchProducts` production trên gold (dense / hybrid / hybrid + normalize)

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Kế hoạch 3 ngày, mục P5 (người dùng chốt 30/09: đo hybrid / hybrid + normalize bằng **`SearchProducts` thật**). Lịch 10
ngày M2 cần ba dòng dense-only / hybrid / hybrid + normalize đúng như production, nhưng arm S2.* của spec dùng `hybrid()`
của Weaviate mà production không dùng (RRF + luật vớt ở app, `history/2026-09-25-search-hybrid-bm25-rrf.md`). Phục vụ
FR-SRC-01..04, AC-SRC-01; contract §10 S1 / S9 / S10.

## File thay đổi

- `src/evaluation/search_bench/app_adapter.py` — thêm: `build_app_catalog` (UnitIndex của backend từ catalog snapshot,
  `Product.from_cdp` + attributes combo như `load_products`, text = T3+R của bench), `product_bench_status` /
  `load_product_bench` (collection `ProductBench` dựng bằng `WeaviateClient` của backend, vector từ
  `vec_T3+R_cohere-v3.npy`, textHash sha256 như job index; đủ và đúng thì bỏ qua), `BenchQueryEmbedder`
  (EmbedderPort bọc cache Cohere của bench), `AppContext` / `AppSearch` / `retrieve_app` (dựng `SearchProducts` từ khối
  `app` của arm, gọi `sp(q, limit=k)`, giữ diagnostics).
- `src/evaluation/search_bench/arms.py` — sửa: `Arm` thêm `engine: bench | app`, `app: dict`.
- `src/evaluation/search_bench/runner.py` — sửa: `BEHAVIOUR_FIELDS` thêm `engine`, `app`; `retrieve` / `run_arm` nhận
  `app_ctx`; per_query ghi cột `extra` (diagnostics: normalizedQuery, lexicalCount, total, topScore…).
- `src/evaluation/search_bench/__main__.py` — sửa: `sb run` mở `AppContext` khi có arm APP (collection `app:ProductBench`,
  bỏ `check_ready` của store bench); thêm `sb app-load [--recreate]`.
- `src/evaluation/search_bench/arms/APP.dense.yaml`, `APP.dense_nocut.yaml`, `APP.hybrid.yaml`, `APP.hybrid_nocut.yaml`,
  `APP.hybrid_norm.yaml`, `APP.hybrid_norm_nocut.yaml` — thêm.
- `src/evaluation/search_bench/tests/test_app_adapter.py` — thêm: 5 test unit (arm nạp / hash theo tham số, UnitIndex +
  text trùng bench, AppSearch / retrieve_app với engine giả, BenchQueryEmbedder, runner đòi AppContext) + 1 integration.
- `docs/spec/bench/arms.md` — sửa: 6 dòng APP trong bảng §1 (50 arm), mục "Cổng APP" ở §2 (lý do, adapter, caveat).
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.3 thêm `sb app-load`.

## Quyết định

- **Gọi đúng lớp production**, không dựng lại RRF / luật vớt trong bench: chỉ thay UnitIndex (snapshot thay Postgres),
  kho vector (`ProductBench` thay `Product`) và embedder (cache bench). Import qua `src.backend.*` như use case tự
  import; không trộn tiền tố `backend.` của `textbuild`.
- **`ProductBench` là hnsw** (backend chỉ nhận hnsw / hfresh): nhiễu ANN có thể có; kiểm parity trên fixture cho thấy
  `APP.dense_nocut` trùng top-10 với B0 (flat) ở 10/10 câu.
- Tham số production ghi trong YAML (`app: {...}`), thiếu khoá là lỗi (spec §1.5: không mặc định ngầm). Cutoff mốc
  0,62 (contract, `.env`); mỗi arm có bản `_nocut` (cutoff −1) để tách hiệu ứng ngưỡng khỏi xếp hạng.
- `lexical_cutoff = min(lexical_cutoff, cutoff)` như `build_recsys`.
- `multi_constraint` trên cổng APP báo riêng: `/search` không có filter sao / giá.
- Không dùng Weaviate của app (`Product`, 2.897 object của snapshot 09-21) để đo chất lượng: lệch catalog với gold.

## Kiểm tra

- `pytest evaluation/search_bench/tests -q -p no:cacheprovider`: **323 passed, 11 skipped**.
- `sb app-load`: ProductBench 3.183 object, khớp textHash 3.183, nạp mới 3.183, 17 s, 0 Cohere.
- Smoke `sb run --run-id smoke-fixture --arm APP.dense_nocut --arm APP.hybrid_norm --gold tests/fixtures/gold_small.jsonl`:
  chạy hết 10 câu; `APP.dense_nocut` overlap@10 với B0 = 10/10 mọi câu, top-1 trùng 10/10; `APP.hybrid_norm`: normalize
  đúng ("ve may bay di DN" → "ve may bay di Đà Nẵng", "KS 5 sao HL" → "khách sạn 5 sao Hạ Long"), cutoff 0,62 cho
  zero-result 1/9 câu trong catalog, `lexicalCount` 0 (không hit nào được vớt trên 10 câu này); weaviate p50 70–150 ms
  (filter ~3.182 uuid mỗi truy vấn như production).

## Còn lại / rủi ro

- Chưa chạy trên gold thật (chờ `gold_v1`); các arm APP sẽ kéo hole (normalize, không filter) → gán → `gold_v2/3`.
- Filter `allowed` gửi ~3.182 uuid mỗi truy vấn (production làm vậy vì 1 unit `available=false`): chậm nhưng đúng.
- Số normalize trên `abbrev_typo` là số đo trong mẫu (15 câu gold đã dùng để viết `QueryNormalizer`) — ghi caveat.
