# Bật entity gate làm mặc định production cho /search

- Ngày: 2026-10-14
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/search-evidence-gate
- Trạng thái: hoàn thành
- Phạm vi: backend, docs

## Mục tiêu

Team Web đã chốt (14/10) cho bật `SEARCH_ENTITY_FILTER` — điều kiện plan `docs/plan/2026-10-07-search-duration-entity-poi.md` đặt ra vì cờ đổi số đếm tab.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: `search_entity_filter` mặc định `true`.
- `src/backend/tests/unit/api/test_search_settings_wiring.py` — sửa: ghim mặc định mới.
- `docs/prd/deployment-plan.md` — sửa: ghi mặc định mới của `SEARCH_ENTITY_FILTER`.

## Quyết định

- Bench gold_v7 arm `_all` (đã gồm entity): xem `src/evaluation/reports/eval-2026-10-14-search-evidence-gate-gold-v7.md`.

## Kiểm tra

- `pytest src/backend/tests/unit/api src/backend/tests/contract src/backend/tests/unit/agents src/backend/tests/unit/application`: 1402 passed, 3 xfailed.

## Còn lại / rủi ro

- Không có.
