# Gộp release-mvp-v1 mới nhất vào feat/agent

- Ngày: 2026-09-25
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, frontend, data, contract, db, docs, deployment

## Mục tiêu

Người dùng yêu cầu kéo code về, merge và tạo PR `feat/agent → release-mvp-v1`. `origin/release-mvp-v1` (commit `9790616`)
có 9 commit feat/agent chưa có: tìm kiếm hybrid BM25 + RRF, chuẩn hoá truy vấn search, monitor và job cào catalog mới,
CD backend, deploy frontend Vercel, sinh lại `api.gen.ts`. Chi tiết nghiệp vụ nằm trong các entry history mà release mang
theo (`history/2026-09-25-*` do release thêm vào). Không có xung đột; kiểm bằng `git merge-tree` trước khi merge.

## File thay đổi

- `.env.example` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `.github/workflows/backend-ci-cd.yml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `.github/workflows/frontend-ci.yml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `Dockerfile.fresh-catalog` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `Dockerfile.fresh-catalog.dockerignore` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docker-compose.yml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/guide/doc-code-backend.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/plan/2026-09-25-ban-giao-fresh-catalog-vm.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/architecture.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/data-model.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/deployment-plan.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/requirements.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update-archive/2026-09-23-weaviate-cloud-index-hfresh.md` — đổi tên: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-dong-goi-fresh-catalog-docker.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-luong-cao-index-backend-sau-audit.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-merge-release-vao-newcrawl.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-rename-newcrawl-branch.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-trip-catalog-fresh-release-mvp-v1.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-trip-catalog-single-repo.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-xoay-vong-id-trip-tren-vm.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-ban-giao-env-va-dong-bo-release.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-cao-song-song-va-lenh-theo-doi.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-dung-lai-hybrid-search-tren-release.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-frontend-vercel-shared-deploy.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-hoan-thien-monitor-fresh-catalog.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-merge-release-mvp-v1-vao-newcrawl.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-public-monitor-dashboard.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-remove-frontend-preview-deploy.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-search-chuan-hoa-truy-van.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-search-hybrid-bm25-rrf.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-sinh-lai-api-gen-ts-tren-dev.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-sync-backend-cd-runtime.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-tach-lenh-fresh-run.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `ops/docker-compose.backend-vm.yml` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `scripts/deploy-backend-vm.sh` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `scripts/tests/test-backend-vm-cd-sync.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/__init__.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/vector_search.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/search/use_cases.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/core/config.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/search/__init__.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/search/hybrid.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/search/lexical.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/search/normalize.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/vectors/numpy_search.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/main.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/jobs/embed_products.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/jobs/requirements.txt` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/fakes/in_memory_vector_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/api/test_recsys_refresher.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/application/test_hybrid_search.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/application/test_search_normalization.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/domain/test_hybrid.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/domain/test_lexical.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/domain/test_normalize.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/infrastructure/test_embed_products_job.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/.env.example` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/collectors/common.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/collectors/trip_hotels.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/collectors/trip_live.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/crawl.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/cron_hotels_daily.sh` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/daily_api.py` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/deepen_jobs.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/fresh-catalog-runner.env.example` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/fresh-catalog.env.example` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/fresh_catalog.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/fresh_catalog_db.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/fresh_catalog_schedule.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/fresh_run_log.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/fresh_settings.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/monitor.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/monitor_ui/daily.html` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/monitor_ui/index.html` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/monitor_ui/pipeline.html` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/normalise.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/requirements.txt` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/run_daily_docker.sh` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/run_fresh_catalog_container.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/run_fresh_catalog_vm.sh` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_api_sources.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_fresh_catalog_job.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_fresh_monitor.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_fresh_trip.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_monitor_public.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_pipeline_demo.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_trip_hotels.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/search.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/types/api.gen.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/common.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/search.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-25-merge-release-mvp-v1-vao-feat-agent.md` — thêm: entry này.

## Quyết định

- Merge (không rebase) để giữ lịch sử, đúng cách các PR feat/agent → release-mvp-v1 trước đó (#15, #19).
- Không gỡ xung đột nào; không sửa code của hai phía.
- Các file người dùng đang sửa dở (`docs/spec/agent/presentation-slides.*`, entry history về slide) không nằm trong
  commit merge và không đưa vào PR này.

## Kiểm tra

- `validate_contract.py`: PASS (88 schema, 62 fixture).
- Test backend, data_collection và frontend: **chưa chạy** theo yêu cầu của người dùng (bỏ qua test trước khi push).

## Còn lại / rủi ro

- Chưa có kết quả test sau merge; nên xem CI của PR trước khi merge vào release-mvp-v1.
