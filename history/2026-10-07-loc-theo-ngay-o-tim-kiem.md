# Lọc theo ngày ở tìm kiếm (contract 1.19.0)

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành (backend chưa chạy trong container đang phục vụ; xem "Còn lại")
- Phạm vi: backend, contract, frontend, docs

## Mục tiêu

Ô ngày ở tấm tìm kiếm của `/hotels`, `/experiences`, `/combos` phải là tiêu chí tìm thật (cùng với số khách, xem `history/2026-10-07-loc-so-khach-o-trang-danh-muc.md`). Đề xuất đã chốt 2026-10-07: `docs/prd/update-archive/2026-10-07-loc-theo-ngay-o-tim-kiem.md` (FR-SRC-03, FR-CAT-03, AC-SRC-03). Thay entry đề xuất `2026-10-07-de-xuat-loc-theo-ngay-o-tim-kiem.md`.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-SRC-03 (bộ lọc ngày), FR-CAT-03 (lịch dùng cho tìm kiếm, vẫn không chặn đặt chỗ), thêm AC-SRC-03.
- `docs/prd/update-archive/2026-10-07-loc-theo-ngay-o-tim-kiem.md` — thêm (chuyển từ `update/`): đề xuất, trạng thái đã áp dụng.
- `src/shared/contracts/schemas/search.yaml`, `paths/search.yaml`, `openapi.yaml` — sửa: 1.19.0 additive, `TravelContext.checkIn/checkOut` có hiệu lực, `appliedFilters.hard.checkIn/checkOut/dateSource`, `queryPlan.date`, `date` trong `applied` và `emptyReason`.
- `src/backend/app/domain/catalog/stay_dates.py` — thêm: `StayDates`, `hotel_booking_window` (chuyển từ `pricing.py`), `parse_calendar`, `calendar_open`, `stay_calendars_open`.
- `src/backend/app/domain/booking/pricing.py` — sửa: import luật cửa sổ từ `stay_dates` (tên cũ vẫn import được từ `pricing`).
- `src/backend/app/domain/catalog/unit_attributes.py`, `__init__.py` — sửa: `sale_from`, `sale_to`, `calendars` theo unit.
- `src/backend/app/application/ports/unit_index.py` — sửa: `mask(stay=…)`, `_stay_mask`.
- `src/backend/app/domain/search/query_plan.py`, `__init__.py` — sửa: `PlanParams.stay`, `APPLIED_DATE`, `QueryPlan.stay`, `mask_kwargs`, `families_in_order`, `applied_filters`, `as_diagnostics`.
- `src/backend/app/application/search/use_cases.py` — sửa: `check_in`/`check_out`, `today` (giờ Việt Nam, tiêm được), `appliedFilters` khi có ngày.
- `src/backend/app/api/v1/routes/search.py` — sửa: `checkIn`/`checkOut` trong `TravelContextPayload`, `_dates`, 400 khi `checkOut <= checkIn`.
- `src/backend/app/main.py` — sửa: version 1.19.0.
- `src/backend/tests/unit/domain/test_stay_dates.py`, `unit/application/test_search_stay_dates.py` — thêm; `unit/api/test_search_route.py`, `contract/test_search_contract.py` — sửa.
- `src/frontend/src/services/search.ts`, `components/search/GroupResults.tsx`, `features/catalog/landing/LandingResults.tsx` — sửa: gửi `travelContext.checkIn/checkOut` (`stayOf`), vào khóa bộ đệm.
- `src/frontend/src/types/api.gen.ts` — sinh lại từ contract.
- `src/frontend/src/features/catalog/landing/LandingSearchSheet.tsx`, `features/search/tripContext.ts` — sửa: chú thích.
- `src/frontend/tests/unit/{landingResults,searchService}.test.*` — sửa.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` (§2.5, §2.7), `hop-dong-tich-hop-frontend.md` (§4.1a), `hop-dong-tich-hop-backend.md` (`DATE_OUT_OF_RANGE`), `product.md`, `src/frontend/README.md` — sửa.
- `history/2026-10-07-loc-theo-ngay-o-tim-kiem.md` — thêm: entry này.

## Quyết định

- Khách sạn: theo luật đặt phòng (hôm nay đến +3 tháng, 1–30 đêm) và loại khi mọi hạng phòng đang bán đều có lịch và đều kín ít nhất một đêm; hạng phòng ngừng bán không tính (lịch của chúng toàn `0`). Không có hạng phòng, hạng phòng chưa có lịch, hoặc đêm ngoài khoảng lịch 30 ngày → giữ.
- Vé tham quan, golf: cửa sổ mở bán và ký tự lịch của `checkIn`. Combo: cửa sổ. Route bay: không lọc.
- Ngày là tham số request nên luôn áp, không có cờ cấu hình mới.
- Không kiểm "cùng một hạng phòng" giữa ngày với giá/số khách (xấp xỉ, ghi ở spec §2.5); `matchedChildren` không xét ngày.
- Tìm kiếm và đặt phòng không cùng luật (lịch chỉ loại ở tìm kiếm), theo đúng đề xuất đã chốt.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract`: 1758 passed, 2 skipped (trước đó 1739 passed; thêm 19 test).
- `.venv/bin/python src/shared/contracts/tests/validate_contract.py`: PASS (115 schemas, 93 fixtures).
- Frontend (từ `src/frontend`): `vitest run tests/unit` 62 file, 663 test pass; `tsc --noEmit` sạch; `eslint` 0 lỗi, 2 cảnh báo cũ ở `ItineraryMap.tsx`. Playwright `navigation.spec.ts -g hotels`: 3 pass.
- Catalog thật trong Postgres (nạp bằng `PostgresCatalogReader`, `UnitIndex.mask(stay=…)`, hôm nay 2026-10-07): khách sạn Nha Trang 133 còn bán; ở 12→14/10 giữ 34, loại 99; 20→25/10 giữ 30; 15→17/11 giữ 133 (ngoài khoảng lịch nên không biết); 6→8/10 hoặc 1→3/2/2027 giữ 0 (ngoài luật đặt phòng). Vé tham quan 12/10 giữ 593/609; golf 6/6; combo 128/133; từ 30/10 mọi vé và combo bị loại vì cửa sổ mở bán kết thúc 28/10 (catalog nạp ngày 29/09).
- Chưa chạy: `RUN_POSTGRES_INTEGRATION=1` đầy đủ; kiểm trên giao diện với backend mới (container :8000 chạy code cũ, chưa dựng lại).

## Còn lại / rủi ro

- Container backend :8000 đang chạy code cũ: cần dựng lại (build image mới) thì tấm tìm kiếm mới lọc ngày thật; frontend gửi `travelContext` vẫn an toàn với backend cũ (bỏ qua).
- Lọc khách sạn theo lịch loại nhiều: 99/133 ở Nha Trang cho 2 đêm 12→14/10, vì `0` trong lịch phòng thường là "nguồn không có giá ngày đó" (đã nêu ở đề xuất). Cần xem lại sau khi demo, nếu quá gắt thì đổi sang đề xuất khác (chỉ loại theo luật đặt phòng).
- Kết quả không đơn điệu theo ngày: ngày ngoài 30 ngày lịch ra nhiều khách sạn hơn ngày trong lịch (không biết thì giữ).
- Catalog nạp 29/09: hết cửa sổ mở bán 28/10; chạy lại loader trước demo (`AGENTS.md` mục 6.2).
- Test dùng hôm nay giả định 2026-10-07 qua `today` tiêm; bộ test contract dùng `date.today()` nên chỉ kiểm schema, không kiểm số lượng.
