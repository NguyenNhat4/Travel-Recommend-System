# Áp dụng hai đề xuất đã chốt: embedding e5-small local (FR-SRC-02) và LLM fallback cho query plan; mặc định production F1, F2, F3, F5, F6 (F4 tắt); đo lại trên gold_v5

- Ngày: 2026-10-06
- Tác giả: tqanh123 (người dùng chốt) / Claude (Opus 5.5, orchestrator + 3 agent)
- Nhánh: feat/search-e5-prod-llm (tách từ `bench_search_recomSys` @ `295e621`)
- Trạng thái: hoàn thành code / tài liệu / bench (gồm đo LLM fallback); chưa deploy (cần quyền VM)
- Phạm vi: backend, contract, data, evaluation, docs, deploy

## Mục tiêu

Người dùng chốt 06/10: "đã chốt e5-small và enable F1–6 trừ F4 cho production config, re-measuring on gold_v5 and add LLM fallback".
Đề xuất `2026-10-05-fr-src-02-embedding-local-e5-small.md` và `2026-10-06-search-llm-fallback-query-plan.md` chuyển sang đã chốt → AGENTS §8
bước 3–4: sửa PRD trước, rồi source, rồi lưu trữ đề xuất. Phục vụ FR-SRC-01..04, NFR-PERF-01, NFR-PERF-03.

## File thay đổi

PRD và đề xuất
- `docs/prd/requirements.md` (FR-SRC-02, NFR-PERF-03), `architecture.md` (sơ đồ: collection e5 384, adapter `LocalE5Embedder`, cạnh LLM
  fallback; cây thư mục; bảng công nghệ; §5 mục 5 + đoạn query plan / LLM fallback), `data-model.md` (§1, ERD), `deployment-plan.md`
  (biến EMBED_*, WEAVIATE_COLLECTION, SEARCH_CUTOFF 0,84, SEARCH_LLM_FALLBACK_*; readiness), `implementation-plan.md`, `project-brief.md` — sửa.
- `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md`, `…/2026-10-06-search-llm-fallback-query-plan.md` → `git mv` sang
  `docs/prd/update-archive/`, trạng thái "đã áp dụng", chốt bởi tqanh123 06/10.

Backend — embedding e5-small
- thêm `src/backend/app/infrastructure/embeddings/local_e5_embedder.py` (transformers + torch CPU, mean pooling, L2, tiền tố
  `query: ` / `passage: `, revision pin `614241f622f53c4eeff9890bdc4f31cfecc418b3`), `…/embeddings/factory.py`, `src/backend/requirements-embed.txt`.
- sửa `core/config.py` (`embed_provider` local|cohere, model / revision / dimension 384 / threads / batch, `weaviate_collection` ProductE5,
  `search_cutoff` 0,84, `search_no_diacritics_cutoff` 0,80; rollback Cohere tự đổi các giá trị phụ thuộc provider), `main.py`
  (`build_query_embedder`, nạp model sau khi index Weaviate sẵn sàng, version 1.17.0), `jobs/embed_products.py` (`collection_guard`
  từ chối khác chiều / khác model), `infrastructure/vectors/{weaviate_store,postgres_store}.py`, `application/search/{prewarm,query_cache}.py`
  (lời), `Dockerfile.backend` (torch CPU, tải model lúc build, offline), `.env.example`, `src/backend/README.md`.
- test thêm `tests/unit/infrastructure/test_local_e5_embedder.py`, `test_embedding_settings.py`; sửa `test_embed_products_job.py`.

Backend — mặc định production + LLM fallback
- `core/config.py`: `search_dest_filter` true, `search_no_diacritics_mode` relax, `search_negation_filter` / `route_filter` /
  `numeric_filter` true, `search_taxonomy_filter` false (F4 tắt); `search_llm_fallback*` (off, 0,75, 1.500 ms, gpt-4o-mini, cache).
- thêm `domain/search/hypothesis.py` (giả thuyết, kiểm với catalog, merge chỉ chỗ trống), `application/ports/query_hypothesis.py`,
  `application/search/query_plan_llm.py` (mode off/shadow/on, cache LRU + JSONL, timeout, `llm_log_fields`, prewarm),
  `infrastructure/llm/query_hypothesis.py` (LangChain structured output, nhiệt độ 0), `jobs/prewarm_llm_hypotheses.py`.
- sửa `application/search/use_cases.py` (field `llm_fallback`, `llm_min_confidence`, `llm_timeout_ms`, `hypothesizer`), `main.py`
  (`search_hypothesizer`), `application/search/search_log.py` (`filters.llm`), `api/v1/routes/search.py` (cutoff dự phòng 0,84).
- contract `src/shared/contracts/openapi.yaml` 1.17.0, `schemas/search.yaml` (`queryPlan.llm`, `stageMs.llm`; lời embed không còn Cohere).
- test thêm `tests/unit/domain/test_search_hypothesis.py`, `tests/unit/application/test_search_llm_fallback.py`,
  `tests/unit/infrastructure/test_query_hypothesis_adapter.py`, `test_prewarm_llm_hypotheses_job.py`, `tests/contract/test_search_llm_contract.py`;
  sửa `tests/contract/test_search_contract.py`, `tests/unit/api/test_search_route.py`.

Crawler / data / deploy (index hằng ngày dùng cùng model)
- `Dockerfile.daily`, `Dockerfile.fresh-catalog` (torch CPU + model như backend), `docker-compose.yml` (WEAVIATE_COLLECTION ProductE5,
  EMBED_PROVIDER), `Makefile` (`make update` cài requirements-embed), `.github/workflows/crawler-ci-cd.yml` (path filter thêm embeddings /
  config / requirements-embed của backend).
- `src/data_collection/{daily.py, fresh_catalog.py, fresh_settings.py, index_backlog.py, monitor.py, monitor_ui/index.html, local_crawl.sh,
  cron_daily.sh, .env.example, fresh-catalog.env.example, README.md}` — cổng theo provider (local không cần COHERE_API_KEY), monitor dùng
  `build_embedder`, chặn ghi `ProductE5` từ crawl local; test `src/data_collection/tests/{test_daily,test_fresh_catalog_job,test_live_monitor}.py`.

Tài liệu khác
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` (§2.2 LLM fallback, §2.4 mặc định production, cache, §7.1, §9, S7, S17),
  `docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` (§17), `docs/spec/bench/arms.md`, `docs/spec/{DATABASE_SCHEMA,MOCK_DATA_SPEC,PRODUCT_SCHEMA}.md`,
  `docs/guide/{doc-code-backend,ve-thuong-gia-va-index-cho,trien-khai-job-cao-du-lieu}.md`, `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`,
  `docs/plan/2026-10-01-chia-task-day4-search-rec.md`, `src/evaluation/reports/eval-2026-10-05-search-e5s-dest-nodia.md`,
  `eval-2026-10-06-recsys-search-tong-hop.md` (đường dẫn đề xuất đã lưu trữ).

Bench
- `src/evaluation/search_bench/app_adapter.py` (khối tuỳ chọn `app.llm` phát lại cache), `tests/test_app_adapter.py`; arm mới
  `arms/APP.e5s.prod_f12356{,_nocut,_llm,_llm100}.yaml`, cache `config/llm_hypotheses_gold_v5.jsonl`; `regression/baseline_v1.json` đặt lại = `APP.e5s.prod_f12356`;
  `src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md` thêm §9.

## Quyết định

- **Production = mặc định của `core/config.py`** (env thật ở `/etc/vota/backend.env` trên VM, ngoài repo): e5-small, cutoff 0,84 + câu không
  dấu 0,80 (theo đề xuất đã chốt), F1 + F2 relax + F3 + F5 + F6, F4 tắt, LLM fallback `off` (đề xuất: chỉ bật `on` sau khi bench chứng minh).
- **Collection mới `ProductE5`**, `Product` (Cohere 1024) giữ cho hoàn tác; job embed từ chối ghi khác chiều.
- **Crawler theo phương án A**: image crawler mang cùng model / revision, để `ProductE5` được cập nhật hằng ngày.
- **LLM chỉ điền chỗ luật để trống**, mọi giá trị kiểm với catalog và câu gốc, mỗi họ vẫn theo cờ của nó.
- **Không gán hole một cặp** của arm production (c0078 → khách sạn cho câu đường bay = 0 theo rubric v4 = như chưa nhãn), giữ `gold_v5`.

## Kiểm tra

- Backend `pytest src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract`: **1.498 passed, 1 skipped** (sau mọi sửa).
- `validate_contract.py`: PASS (1.17.0); pyc tracked đã `git checkout --`.
- Parity e5 backend ↔ bench (.venv-sbench, offline): max |cos − 1| 2,4e-07 trên 40 document và 20 câu; embed câu p95 8,4 ms (20 luồng) /
  10,8 ms (2 luồng) trên laptop.
- Data collection (Docker python:3.11, repo read-only): 480 passed / 9 failed / 21 skipped — 9 lỗi có sẵn trước (CRLF script, preview stream).
- Bench `pytest src/evaluation/search_bench/tests`: 54 lỗi có sẵn, cùng tập 6 file; test mới pass.
- `sb run` `APP.e5s.prod_f12356` (+ `_nocut`) trên `gold_v5`: nDCG@10 **0,798** vs 0,711 production cũ — **WIN** (Δrecall +3,82, p 0,003);
  F4 tắt → Forbidden@10 0,065, constraint precision 0,91 (FAIL ngưỡng đề xuất); có F4 thì TIE +1,9. `sb regress check` PASS sau khi đặt lại.
- `prewarm_llm_hypotheses --all` (gpt-4o-mini): lần đầu 155/155 lỗi 401 (key cũ); sau khi người dùng lưu key mới: 155/155 OK, 240 s →
  `src/evaluation/search_bench/config/llm_hypotheses_gold_v5.jsonl`. Arm `APP.e5s.prod_f12356_llm` (0,75: kích hoạt 10 câu) và
  `_llm100` (1,0: 59 câu): 0 trường nhận, top-10 đổi 0/154, nDCG@10 0,798 = production; LLM trùng luật (loại 59/59, điểm đến 58/59),
  kiểm catalog chặn đúng tiện ích bịa (c0214). Hole mới duy nhất c0078 → khách sạn (= 0 theo rubric v4) không nhập.

## Còn lại / rủi ro

- LLM fallback: giữ `off`; nếu bật thì `shadow` trước; siết trigger (bỏ `long_multi_constraint`) rồi đo lại trên câu thật / gold mới.
- Deploy (cần quyền VM): build image, chạy job embed vào `ProductE5` trên Weaviate Cloud bằng env VM (runbook trong `src/backend/README.md`
  và report agent), đổi `/etc/vota/backend.env`, `fresh-catalog.env`, `daily.env`; đo gate P (`sb latency http`, p95 ≤ 250 ms) và `sb parity`.
- F4 tắt làm hỏng hai guard Phase A — cần Web chốt cách đếm tab để bật F4.
- Image backend / crawler nặng thêm ~1,2 GB; monitor `--memory 1g` có thể chật với model.
- RecSys dùng chung vector: `modelVersion` đổi → `baseline` RecSys mới theo chính sách recsys.
