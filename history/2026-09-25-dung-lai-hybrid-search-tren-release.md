# Dựng lại feat/hybrid-search trên release-mvp-v1 (bỏ merge dev)

- Ngày: 2026-09-25
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/hybrid-search
- Trạng thái: hoàn thành
- Phạm vi: backend | docs (thay đổi của nhánh chỉ thuộc search; phần còn lại đến từ release)

## Mục tiêu

PR của `feat/hybrid-search` vào `release-mvp-v1`, không vào `dev`. Nhánh cũ (`e14cf16` → merge dev `6b1d5cb` → merge release `fe1305f` → fix `ce85f54`) kéo cả thay đổi riêng của `dev` vào release. Gồm: public monitor `f3f7795` (`src/data_collection/monitor.py`, `run_daily_docker.sh`, README, `test_monitor_public.py`), hai lần sửa `.github/workflows/*` và entry lịch sử của `dev`. Ngoài ra, sau PR #25 (`ef6aa80`), nhánh cũ conflict với release ở `src/data_collection/README.md`, `monitor.py`, `run_daily_docker.sh`. Người dùng chọn: nhánh không sửa phần data; dựng lại từ hai commit search và force push.

## File thay đổi

Dựng lại từ `e14cf16` (hai commit search `c5489d8`, `e14cf16`), rồi merge `origin/release-mvp-v1` tại `ef6aa80`. Bốn file conflict và hai file test giải bằng đúng nội dung đã kiểm ở `ce85f54`: release + thay đổi search, không có gì của `dev`. Release từ `0a9bc66` tới `ef6aa80` chỉ đổi `src/data_collection/` và tài liệu, không chạm các file này.

- `src/backend/app/core/config.py` — conflict: giữ `weaviate_vector_index_type`, `catalog_refresh_seconds` của release, bỏ khối khai báo trùng như release, thêm các trường `search_*` của nhánh.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — conflict: giữ `normalize_weaviate_url`, `logger`, cảnh báo `vectorIndexType`, `metadata()`/kiểm đồng bộ của release; thêm property BM25, `_ensure_lexical_properties`, `patch_properties`, `bm25()` của nhánh.
- `src/backend/jobs/embed_products.py` — conflict: `run(*, dry_run, backfill_lexical, settings=None)` gộp hai phía (`src/data_collection/fresh_catalog.py:298` gọi `run(settings=settings)`).
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — conflict: bản release + fake/test BM25 và lexical của nhánh. Test cảnh báo index type thêm property BM25 vào schema giả vì `ensure_collection` của nhánh POST property còn thiếu.
- `src/backend/tests/unit/infrastructure/test_embed_products_job.py` — sửa: `SimpleNamespace` settings thêm `search_bm25_k1`/`search_bm25_b`.
- `src/backend/tests/unit/api/test_recsys_refresher.py` — sửa: thêm test `Settings` thật có `catalog_refresh_seconds`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa §2.2: từ vựng sửa chính tả và danh sách điểm đến dựng lại mỗi lần nạp lại catalog (`CATALOG_REFRESH_SECONDS`, §2.4).
- Toàn bộ file khác của `ef6aa80` (frontend trip starter, `src/data_collection/` fresh catalog/monitor, `docs/plan/`, `docs/prd/update-archive/`, các entry `history/` của release…) — vào qua merge, không sửa tay.
- `history/2026-09-25-dung-lai-hybrid-search-tren-release.md` — thêm: entry này.

## Quyết định

- Force push `feat/hybrid-search`, thay `6b1d5cb`, `fe1305f`, `ce85f54`. Entry `2026-09-25-merge-dev-vao-feat-hybrid-search.md` và `2026-09-25-sua-merge-release-mvp-v1-vao-hybrid-search.md` chỉ nằm trong các commit bị thay, nên không còn trên nhánh; entry này thay cả hai. Bản cũ giữ ở nhánh local `backup/feat-hybrid-search-ce85f54`.
- Không merge `dev` để commit public monitor của `dev` không bị coi là đã vào release. Sau này merge `dev` vào release vẫn mang đủ thay đổi đó.
- Nội dung PR so với `release-mvp-v1` (`git diff origin/release-mvp-v1`): 29 file, đều thuộc search (contract `search.yaml`/`common.yaml`, `api.gen.ts`, `search.ts`, backend search/vector/job, test, spec, `.env.example`, 2 entry lịch sử search). Không file nào trong `src/data_collection/` hay `.github/`.

## Kiểm tra

- `python -m pytest -q src/backend/tests` (venv backend): 495 passed, 19 skipped.
- `validate_contract.py`: PASS (83 schemas, 62 fixtures; CDP clone 12 schemas, 7 fixtures).
- `python -m compileall -q src/backend src/data_collection`: pass. `bash -n scripts/check-db-tunnel.sh scripts/deploy-backend-vm.sh scripts/install-vota-cron.sh`: pass.
- Frontend: `npm run generate:api-types` không lệch, lint 0 lỗi (4 warning có sẵn), typecheck pass, `npm run test` 119/119.
- Kiểm máy móc 7 file hai phía cùng sửa (base `bcc8a95`, nhánh `e14cf16`, release `ef6aa80`): mọi dòng một phía thêm đều có trong bản merge, trừ chữ ký `run()`/`_Obj` đã gộp và câu spec đã sửa.

## Còn lại / rủi ro

- Ai đã kéo `feat/hybrid-search` cũ về máy cần `git fetch` rồi `git reset --hard origin/feat/hybrid-search`.
- Xoá nhánh local `backup/feat-hybrid-search-ce85f54` khi PR vào release đã merge.
