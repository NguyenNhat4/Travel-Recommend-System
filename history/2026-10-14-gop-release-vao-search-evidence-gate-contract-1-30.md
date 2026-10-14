# Gộp release-mvp-v2 vào feat/search-evidence-gate; contract search lên 1.30.0

- Ngày: 2026-10-14
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-evidence-gate
- Trạng thái: hoàn thành
- Phạm vi: contract, backend, docs

## Mục tiêu

Chuẩn bị PR vào `release-mvp-v2` (Bước 13, plan `docs/plan/2026-10-13-search-evidence-gate-no-answer.md`). Release đã dùng 1.28.0 và 1.29.0 cho thay đổi khác.

## File thay đổi

- Gộp 71 commit của `release-mvp-v2`. Xung đột: `src/backend/app/api/v1/routes/catalog.py`, `src/backend/app/domain/catalog/listing.py` (lấy bản release: `free_only`); `src/backend/app/main.py`, `src/shared/contracts/openapi.yaml`, `src/backend/tests/contract/test_search_contract.py`, `src/backend/tests/contract/test_search_llm_contract.py` (version 1.30.0, giữ test 1.30.0 của search).
- Đổi nhãn 1.28.0 → 1.30.0 trong phần search: `schemas/search.yaml` (changelog ghi lý do), `schemas/common.yaml`, `docs/spec/hop-dong-tich-hop-search-recommendation.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, plan + hai đề xuất search, `config.py`, `use_cases.py`, `query_plan.py`, test search, bench adapter/arm, `src/frontend/src/services/search.ts` + test; regen `src/frontend/src/types/api.gen.ts`.

## Quyết định

- Theo plan §2.8: lấy minor kế tiếp còn trống khi nhánh khác đã chiếm số. Mục 1.28.0 của agent (itinerary-agent.yaml, product.md, mocks) giữ nguyên.

## Kiểm tra

- `validate_contract.py`: PASS (130 schemas). Test contract + search v1.30 + explain + settings wiring + catalog listing + architecture: 209 passed. Frontend `searchService.test.ts` 20/20, `tsc --noEmit` sạch.

## Còn lại / rủi ro

- Merge PR → CD deploy VM staging: chờ người dùng đồng ý.
