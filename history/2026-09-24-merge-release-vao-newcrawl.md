# Gộp release-mvp-v1 mới nhất vào test/newcrawl

- Ngày: 2026-09-24
- Tác giả: người dùng / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend, frontend, data, contract, docs, evaluation

## Mục tiêu

Kiểm tra cập nhật trên `origin/release-mvp-v1` và kéo vào nhánh crawler mới mà không mất các thay đổi Docker/crawler. Remote ở commit `fe66851`; trước merge, nhánh này đi trước 5 commit và đi sau 13 commit.

## File thay đổi

Các file dưới đây là phần nhận từ release trong merge; chi tiết nghiệp vụ từng thay đổi đã có trong history của các commit upstream. Không đổi code crawler của `test/newcrawl`.

- `.env.example` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `AGENTS.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `Makefile` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docker-compose.yml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/guide/doc-code-backend.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/plan/2026-09-23-auth-p0.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/api-contract.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/architecture.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/data-model.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/deployment-plan.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/implementation-plan.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/requirements.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/test-plan.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update-archive/2026-09-23-auth-hybrid-session.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update-archive/2026-09-24-go-bo-chon-tai-khoan-demo.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update/2026-09-23-weaviate-cloud-index-hfresh.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/update/2026-09-24-them-thu-muc-docs-guide.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/prd/user-flow.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/DATABASE_SCHEMA.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/agent/README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/agent/evaluation-plan.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/agent/field-review.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/agent/golden-dataset.md` → `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — đổi tên từ `origin/release-mvp-v1`.
- `docs/spec/agent/golden-run.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/agent/presentation-script.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/agent/presentation-slides.html` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/auth/so-do-luong-xac-thuc.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-auth.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `docs/spec/product.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-ap-dung-de-xuat-auth-hybrid-session.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-dung-lai-db-local-sua-seed-sau-bo-product-vectors.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-job-embed-products-weaviate-cohere.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-ke-hoach-auth-p0.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-seed-mat-khau-argon2id.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-so-do-luong-xac-thuc.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-sua-bff-khong-tao-sid.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-23-trien-khai-auth-p0.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-bo-sung-golden-tu-test-nguoi-dung.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-cap-nhat-bao-cao-golden-va-seed-report.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-de-xuat-recsys-weaviate-top-k.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-embed-job-chiu-429.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-go-bo-tai-khoan-demo.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-guide-doc-code-backend.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-makefile-toi-gian-va-make-update.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-merge-release-mvp-v1-vao-feat-auth.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-readme-goc-la-huong-dan-setup-duy-nhat.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-recsys-weaviate-top-k.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-review-field-agent.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-slide-agent-canh-converse.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-slide-agent-chi-route-chinh.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-slide-thuyet-trinh-agent.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-sua-nut-dang-ky.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `history/2026-09-24-weaviate-fetch-rest.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/deps.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/errors.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/router.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/routes/auth.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/routes/recommendations.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/routes/search.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/api/v1/schemas/auth.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/auth/errors.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/auth/principal.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/auth/use_cases.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/__init__.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/auth.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/unit_index.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/vector_search.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/ports/vector_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/recommendation/use_cases.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/application/search/use_cases.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/core/config.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/core/security.py` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/auth/privacy.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/auth/rate_limits.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/auth/session.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/search/__init__.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/domain/search/scoring.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/auth/jwt_issuer.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/auth/keys.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/auth/postgres_login_attempts.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/auth/postgres_refresh_tokens.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/auth/postgres_user_repository.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/auth/rate_limiter.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/auth/revoked_tokens.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/embeddings/cohere_embedder.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/vectors/numpy_search.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/vectors/postgres_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/infrastructure/vectors/weaviate_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/app/main.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/jobs/embed_products.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/requirements.txt` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/conftest.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/contract/test_auth_contract.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/fakes/auth.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/fakes/auth_app.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/fakes/in_memory_vector_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/integration/test_auth_postgres.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/integration/test_auth_redis.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/agents/test_recsys_agent_integration.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/api/test_security.py` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/application/test_auth_use_cases.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/application/test_engines.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/domain/test_auth_domain.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/infrastructure/test_auth_infrastructure.py` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/backend/tests/unit/infrastructure/test_weaviate_store.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/README.md` — sửa: gộp tự động phần hướng dẫn từ release với hướng dẫn Docker của nhánh này.
- `src/data_collection/seed/config.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/seed/requirements.txt` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/seed/seed_histories.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/data_collection/tests/test_seed_histories.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/evaluation/agent/golden.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/evaluation/reports/eval-2026-09-24-golden.md` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/evaluation/tests/test_golden.py` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/.env.example` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/README.md` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/package-lock.json` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/package.json` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/(storefront)/register/page.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/api/[...path]/route.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/api/auth/login/route.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/api/auth/logout/route.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/api/auth/refresh/route.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/api/auth/register/route.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/app/api/auth/session/route.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/auth/LoginView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/common/DemoAccountSwitcher.tsx` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/common/Header.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`; bỏ một dấu cách cuối dòng.
- `src/frontend/src/components/common/LoginModal.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/home/HomeView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/components/search/SearchView.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/context/TravelContext.tsx` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/data/personas.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/assistantStream.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/auth.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/http.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/recsys.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/search.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/server/authRoutes.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/server/bffSession.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/server/proxy.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/server/sessionStore.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/services/shareService.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/src/types/api.gen.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/api/bff-auth.test.ts` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/api/proxy-stream.test.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/assistantStream.test.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/recsysService.test.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/frontend/tests/unit/searchService.test.ts` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/openapi.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/paths/auth.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/paths/recommendations.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/auth.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/common.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/recommendations.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/contracts/schemas/search.yaml` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/auth/getJwks.200-default.json` — thêm: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/auth/listDemoAccounts.200-default.json` — xóa: nhận thay đổi từ `origin/release-mvp-v1`.
- `src/shared/mocks/index.json` — sửa: nhận thay đổi từ `origin/release-mvp-v1`.

- `history/2026-09-24-merge-release-vao-newcrawl.md` — thêm: entry này.

## Quyết định

- Merge nguyên lịch sử release thay vì chép file riêng lẻ, giữ các commit auth, recommendation/Weaviate, seed, frontend, contract và docs của team.
- `src/data_collection/README.md` tự merge sạch: giữ hướng dẫn image Docker của nhánh này và nhận cập nhật hướng dẫn snapshot/seed từ release. Không có conflict Git.
- Không tự áp dụng hai đề xuất đang chờ trong `docs/prd/update/`. Không push branch; người dùng tự push.

## Kiểm tra

- `git merge --no-commit --no-ff origin/release-mvp-v1`: tự merge, không có conflict.
- `docker build -f Dockerfile.fresh-catalog -t vota-fresh-catalog:merge-check .`: pass.
- Test trong image mới: `test_fresh_trip.py` 6 pass, `test_trip_hotels.py` 13 pass; `run_fresh_catalog_container.sh status` pass.
- `/usr/bin/python3 src/shared/contracts/tests/validate_contract.py`: pass, 77 schema và 53 fixture hiện hành; Python Anaconda mặc định thiếu `jsonschema` nên dùng Python hệ thống.
- `bash -n` cho ba runner script: pass; `git diff --cached --check`: pass sau khi bỏ dấu cách thừa upstream.

## Còn lại / rủi ro

- Chưa chạy full backend/frontend/integration hoặc cào và nạp DB trên VM thật trong lượt merge này. Những thay đổi sản phẩm từ release cần team của chúng theo dõi test/deploy riêng.
