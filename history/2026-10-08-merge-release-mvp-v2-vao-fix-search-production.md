# Merge release-mvp-v2 vào fix/search-production (contract 1.20.0)

- Ngày: 2026-10-08
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: backend | contract | frontend

## Mục tiêu

Nhánh `fix/search-production` không auto-merge được vào `release-mvp-v2`: hai luồng Search chạy song song trên cùng bộ file. Phía nhánh này có `1eb7624` (LLM fallback, contract 1.17.0) và `17dfbb5` (thời lượng F7, POI gazetteer, entity gate, contract 1.18.0); phía release có `fcf2ead` (lọc ngày checkIn/checkOut, contract 1.19.0). Gộp `origin/release-mvp-v2` (tới `6f77e80`, 26 commit) vào nhánh này, giữ cả hai bộ tính năng.

## File thay đổi

Chỉ liệt kê file phải giải quyết conflict bằng tay; file khác git tự gộp.

- `src/shared/contracts/openapi.yaml` — sửa: version 1.18.0 / 1.19.0 → **1.20.0**.
- `src/shared/contracts/schemas/search.yaml` — sửa: gộp changelog 1.17.0 + 1.18.0 + 1.19.0, thêm dòng 1.20.0; `queryPlan` có đủ `date` / `duration` / `entity` / `location`; enum `applied` = [..., date, duration, entity]; enum `emptyReason` = [..., date, destination, param, entity, duration]; mô tả `appliedFilters.hard` giữ cả hai đoạn.
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `npm run generate:api-types`, không sửa tay.
- `src/backend/app/main.py` — sửa: `version="1.20.0"`.
- `src/backend/app/application/search/use_cases.py` — sửa: `__call__` nhận cả `check_in` / `check_out` (release) lẫn giữ luồng LLM fallback dựng plan trước embed (nhánh này); `PlanParams` nhận `stay=StayDates(...)`.
- `src/backend/app/domain/search/query_plan.py` — sửa: `QueryPlan` có cả `stay` (release) và `duration_* / entity_* / location / poi_destinations` (nhánh này); `to_dict` khai cả `date` lẫn `duration` / `entity` / `location`; hằng `APPLIED_DATE` + `APPLIED_DURATION` / `APPLIED_ENTITY`.
- `src/backend/app/domain/search/__init__.py` — sửa: export cả ba hằng trên.
- `src/backend/app/domain/catalog/unit_attributes.py` — sửa: `UnitAttributes` có cả `entities` lẫn `sale_from` / `sale_to` / `calendars`; kiểm tra chiều gộp cả hai nhóm.
- `src/backend/app/application/ports/unit_index.py` — sửa: `mask()` nhận cả `require_entities` lẫn `stay`; áp entity gate rồi stay mask / rooms_ok.
- `src/backend/tests/contract/test_search_contract.py` — sửa: assertion gộp khoá `date` (1.19.0) và nhóm khoá 1.18.0.
- `src/backend/tests/unit/domain/test_constraints.py` — sửa: giữ cả test `remove_spans` (release) lẫn bộ test F7 thời lượng.
- `src/backend/tests/contract/test_search_contract.py`, `src/backend/tests/contract/test_search_llm_contract.py` — sửa: assert version contract → 1.20.0 (bỏ dòng assert 1.19.0 trùng do gộp).

## Quyết định

- Merge (không rebase) vì nhánh đã push lên origin.
- Cả hai phía đều additive nên mọi hunk đều "giữ cả hai"; contract lên 1.20.0 không thêm field mới, chỉ gộp. Theo quy tắc AGENTS.md mục 3: không đổi/xóa field v1.
- Lần giải quyết tay đầu tiên trong `use_cases.py` và `test_search_contract.py` chỉ gỡ marker và giữ nguyên hai phía nên vỡ cú pháp; `query_plan.py` / `unit_attributes.py` / `unit_index.py` thì rơi dòng của cả hai phía (`QueryPlan.stay`, `UnitAttributes.entities`, `mask(require_entities=…)`). Đã `git checkout -m` để tạo lại marker cho 5 file đó rồi gộp lại từ đầu.

## Kiểm tra

- `python src/shared/contracts/tests/validate_contract.py`: PASS (117 schemas, 93 fixtures).
- `npm run generate:api-types`: sinh lại `api.gen.ts`, không còn marker; enum `applied` / `emptyReason` đúng như contract.
- `pytest tests/unit/domain tests/unit/application tests/architecture tests/unit/api/test_search_route.py` (bỏ `test_recommendation_cdp_fallback.py`): **1748 passed**.
- Trên Windows máy này `psycopg` binary bị Application Control chặn DLL (`libpq`, `libssl`, `libcrypto` đều chưa ký) nên mọi test import `app.main` không chạy được. Chạy toàn bộ `src/backend/tests` trong container tạm từ image `travel-recommendation-product-backend` (Linux, `--network none`, source copy vào bằng tar — bind mount ổ H: quá chậm): **2478 passed, 36 skipped**.
- Lần chạy container đầu tiên có thêm 1 fail chập chờn ở `test_engine_responses_with_every_knob_on_match_contract` (không thấy `hard.destinationSource.poi`); chạy lại riêng, theo 10 `PYTHONHASHSEED`, cùng thư mục contract và cả bộ đều pass, không tái hiện được.
- `tsc --noEmit` frontend: 0 lỗi liên quan search / `api.gen.ts`; 2 lỗi còn lại (`pino` chưa cài trong node_modules, kéo theo `WidgetProgress`) là môi trường, không do merge.
- `grep '^<<<<<<<'` trên `src db docs`: không còn marker.

## Còn lại / rủi ro

- `npm ci && tsc` để xác nhận hai lỗi tsc (`pino`) biến mất.
- Theo dõi fail chập chờn POI ở trên nếu CI gặp lại.
- Hai khối changelog trong `search.yaml` giữ nguyên ngày 2026-10-07 cho 1.18.0 và 1.19.0 (song song), 1.20.0 là bản gộp ngày 2026-10-08.
