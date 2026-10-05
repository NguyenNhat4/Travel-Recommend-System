# Instant search: gợi ý tức thì khi gõ ở ô tìm kiếm

- Ngày: 2026-10-05
- Tác giả: mihhquan / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: frontend | backend | contract | docs

## Mục tiêu

Ô tìm kiếm ở hero Home và đầu `/search` chỉ tìm khi nhấn Enter. Thêm gợi ý tức thì khi gõ (FR-SRC-05, AC-SRC-02): chia theo loại, icon, in đậm chữ khớp, nút "Xem tất cả kết quả cho …", kiểm soát số lượt gọi (≥ 2 ký tự, huỷ lượt cũ, cache, bỏ chuỗi không hợp lệ, giới hạn kết quả), ô rỗng hiện tìm kiếm gần đây và từ khoá phổ biến. Đề xuất `update-archive/2026-10-05-goi-y-tuc-thi-o-tim-kiem.md` do mihhquan chốt ngày 2026-10-05, thay thế `2026-10-05-de-xuat-goi-y-tuc-thi-o-tim-kiem.md`.

## File thay đổi

PRD và spec (PRD cập nhật trước, theo đề xuất đã chốt):
- `docs/prd/requirements.md` — sửa: thêm FR-SRC-05 và AC-SRC-02.
- `docs/prd/user-flow.md` — sửa: §2 hai dòng route `/` và `/search`; §3.1 nhánh gợi ý trong sơ đồ.
- `docs/prd/api-contract.md` — sửa: §2.3 ví dụ `GET /search/suggestions`.
- `docs/prd/update/2026-10-05-goi-y-tuc-thi-o-tim-kiem.md` → `docs/prd/update-archive/…` — chuyển: trạng thái `đã áp dụng`, thêm ghi chú 422.
- `docs/spec/product.md` — sửa: §4.2.1 bỏ "MVP: không autocomplete", mô tả gợi ý và ô rỗng.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.1 thêm dòng gợi ý, §4.2 ghi ô đầu trang.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa: thêm §3.7.
- `src/backend/README.md` — sửa: danh sách endpoint.

Contract:
- `src/shared/contracts/openapi.yaml` — sửa: 1.13.0 → 1.14.0, thêm path và hai schema.
- `src/shared/contracts/paths/search.yaml`, `schemas/search.yaml` — sửa: `GET /search/suggestions`, `SearchSuggestion`, `SearchSuggestionResponse` (chỉ thêm).
- `src/shared/mocks/index.json` — sửa; `src/shared/mocks/search/suggestSearch.200-default.json`, `suggestSearch.200-empty.json` — thêm.
- `src/frontend/src/types/api.gen.ts` — sửa: tái sinh bằng `openapi-typescript`.

Backend:
- `src/backend/app/domain/search/suggest.py` — thêm: khớp đầu từ theo `fold`, ba hạng, chia chỗ theo vòng giữa các nhóm.
- `src/backend/app/domain/search/__init__.py` — sửa: export.
- `src/backend/app/application/search/suggest.py` — thêm: `SuggestProducts` trên `UnitIndex`, LRU 512 khoá; `__init__.py` — sửa: export.
- `src/backend/app/api/deps.py`, `app/api/v1/routes/search.py` — sửa: `get_suggest`, route `GET /search/suggestions` (`Cache-Control: public, max-age=300`).
- `src/backend/app/main.py` — sửa: dựng `suggest` cùng RecSys, đưa vào danh sách dịch vụ bị tắt khi RecSys tắt.
- Test: `tests/unit/domain/test_suggest.py`, `tests/unit/application/test_search_suggest.py`, `tests/contract/test_search_suggest_contract.py` — thêm.

Frontend:
- `src/frontend/src/services/suggest.ts` — thêm: `fetchSuggestions` qua `apiFetch`, kiểm hình dạng payload.
- `src/frontend/src/features/search/instant/` — thêm: `useInstantSearch.ts` (debounce 200 ms, huỷ, cache 50 khoá/5 phút), `useInstantSearchBox.ts` (mở/đóng, phím, lịch sử), `InstantSearchPanel.tsx`, `highlight.ts`, `recentSearches.ts`.
- `src/frontend/src/components/home/HomeView.tsx`, `src/frontend/src/components/common/SearchBox.tsx` — sửa: gắn hook và panel; Enter, chip, mic giữ nguyên hành vi, nay ghi vào lịch sử tìm kiếm.
- Test: `tests/unit/suggestService.test.ts`, `highlight.test.ts`, `useInstantSearch.test.tsx`, `instantSearchPanel.test.tsx` — thêm; `homeView.test.tsx`, `searchView.test.tsx` — sửa.

## Quyết định

- Endpoint riêng khớp chữ trên `UnitIndex` thay vì `POST /search`: search gọi Cohere + Weaviate (p95 4,0 s trên VM) và ghi event `search` vào CDP.
- Không gợi ý vé máy bay, hạng phòng, chuyến bay, unit hết bán; điểm đến lấy từ cùng nguồn với `/destinations`.
- Tham số sai trả `422 VALIDATION_ERROR` (handler chung của repo), `q` quá ngắn trả `200` rỗng; contract khai 422 thay vì 400.
- Lịch sử tìm kiếm dùng lại `useRecentPlaces` với khoá `vota_recent_searches`; chỉ ở trình duyệt. Từ khoá phổ biến là danh sách cố định; số liệu thật từ `app.search_logs` để sau.
- Hook giữ phần tử bao ô bằng state (callback ref) vì quy tắc `react-hooks/refs` cấm đọc `ref.current` lúc render.

## Kiểm tra

- `validate_contract.py` (bằng `.venv`): PASS, 109 schemas, 87 fixture.
- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/contract src/backend/tests/architecture`: 1158 passed.
- Frontend (`src/frontend`): `tsc --noEmit` exit 0; `eslint .` 0 lỗi (2 cảnh báo cũ ở `ItineraryMap.tsx`); `vitest run` 60 file, 598 test pass.
- Đo `suggest()` trên 3.110 mục tổng hợp (cỡ catalog thật), 240 lượt, không cache: p50 3,4 ms, p95 4,4 ms, lớn nhất 7,3 ms. Chưa đo qua HTTP trên backend thật.
- Chưa chạy trên trình duyệt với backend và Weaviate thật; chưa chạy e2e Playwright. Giao diện đã được duyệt qua bản xem trước tương tác (artifact) nhưng chưa so với trang thật.

## Còn lại / rủi ro

- Chưa commit.
- `src/frontend/src/components/common/Footer.tsx` đang sửa dở trong working tree từ trước, không thuộc task này, không đưa vào commit của task.
- Hoãn theo đề xuất: từ khoá phổ biến theo số liệu thật, giới hạn tần suất phía server, sửa chính tả trong gợi ý.
- Panel dùng `z-30` trong vùng `z-20` của hero Home để nằm trên dải danh mục; cần nhìn bằng mắt trên trang thật, đặc biệt ở màn hình hẹp.
