# Merge origin/release-mvp-v1 vào feat/booking

- Ngày: 2026-09-25
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: backend | frontend | contract | agent | evaluation | data | docs

## Mục tiêu

Người dùng yêu cầu lấy code mới nhất của `release-mvp-v1` (8 commit, tới `fe66851 Merge pull request #15 from Zeno2k3/feat/agent`) về `feat/booking`. Trong đó có thay đổi RecSys truy vấn Weaviate top-K mỗi request và bỏ GraphQL — cần cho cụm Weaviate Cloud đang tắt GraphQL API.

## File thay đổi

Toàn bộ đến từ `release-mvp-v1`, merge tự động không có conflict (62 file: 22 thêm, 39 sửa, 1 đổi tên). Chi tiết từng thay đổi nằm ở entry gốc của nhánh release, gồm `history/2026-09-24-weaviate-fetch-rest.md` và các entry `history/2026-09-24-*` đi kèm.

- `src/backend/app/infrastructure/vectors/weaviate_store.py`, `numpy_search.py`, `application/ports/vector_search.py`, `unit_index.py`, `vector_store.py`, `application/search/use_cases.py`, `application/recommendation/use_cases.py`, `domain/search/`, `main.py`, `core/config.py`, `jobs/embed_products.py`, `infrastructure/embeddings/cohere_embedder.py`, `infrastructure/vectors/postgres_store.py`, `api/v1/routes/search.py` — sửa/thêm: truy vấn top-K qua gRPC (`weaviate-client`), bỏ GraphQL, `WEAVIATE_GRPC_PORT`, `SEARCH_CANDIDATE_K`.
- `src/backend/requirements.txt` — sửa: thêm `weaviate-client>=4.9,<5`.
- `src/backend/tests/` (`conftest.py`, `fakes/in_memory_vector_store.py`, `unit/application/test_engines.py`, `unit/infrastructure/test_weaviate_store.py`) — sửa theo runtime mới.
- `src/shared/contracts/schemas/common.yaml`, `recommendations.yaml`, `search.yaml`, `src/frontend/src/types/api.gen.ts`, `src/frontend/src/services/search.ts`, `src/frontend/src/components/search/SearchView.tsx` — sửa.
- `src/evaluation/` (golden dataset Itinerary Agent, báo cáo, test), `src/data_collection/README.md` — sửa/thêm.
- `README.md`, `Makefile`, `.env.example`, `src/backend/README.md`, `src/frontend/README.md`, `docs/prd/deployment-plan.md`, `docs/prd/update-archive/2026-09-24-recsys-truy-van-weaviate-top-k.md`, `docs/prd/update/2026-09-24-them-thu-muc-docs-guide.md`, các file `docs/` khác — thêm/sửa theo merge.
- `history/2026-09-25-merge-release-mvp-v1-vao-feat-booking.md` — thêm: entry này.

## Quyết định

- Merge (`--no-ff`) thay vì rebase, theo tiền lệ `history/2026-09-24-merge-release-mvp-v1-vao-feat-auth.md`; không viết lại lịch sử đã có của `feat/booking`.
- Không sửa tay file nào sau merge: các file cả hai nhánh cùng đổi (`main.py`, `config.py`, `common.yaml`, `api.gen.ts`, README, `.env.example`, `deployment-plan.md`) Git tự gộp được và các kiểm tra dưới đều pass.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` (venv backend): PASS — 83 schemas, 60 fixtures; CDP clone 12 schemas, 7 fixtures.
- `python -m pytest -q src/backend/tests` (venv backend, đã cài lại `requirements.txt`): 366 passed, 15 skipped.
- Frontend: `npx tsc --noEmit` sạch; `npx vitest run` 97/97 passed (15 file).

## Còn lại / rủi ro

- `docs/prd/update/2026-09-24-them-thu-muc-docs-guide.md` (từ release) vẫn `chờ chốt`.
- Nghiệm thu Stripe test thật của booking vẫn dang dở như `history/2026-09-24-trien-khai-booking-thanh-toan-stripe.md`.
- Image backend Docker phải build lại vì `requirements.txt` có `weaviate-client` mới.
