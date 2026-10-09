# Merge release-mvp-v2 vào feat/agent

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: frontend | backend | contract | data | docs

## Mục tiêu

Kéo 19 commit mới của `origin/release-mvp-v2` (đến PR #129) về `feat/agent` trước khi tạo PR của agent vào release.

## File thay đổi

Merge commit, ~256 file từ release (tìm kiếm theo ngày, khách sạn 9 khách/phòng, bộ đặt khách sạn, thang màu thương hiệu, cào full catalog...). Chỉ liệt kê 9 file xung đột đã giải quyết tay:

- `src/shared/contracts/openapi.yaml`, `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py` — giữ version `1.21.0` (feat/agent) vì phiên bản 1.19.0 của release đã nằm trong lịch sử 1.20/1.21 cộng thêm; thay đổi 1.19.0 (filter ngày) vẫn vào qua `schemas/search.yaml`.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts`, `WidgetPlanPanel.tsx` — theo release: bỏ "Thanh toán tất cả", `useBookItinerary` nhận một mục; giữ phần xem trước/chọn khách sạn và `bookPlanItem` của feat/agent.
- `src/frontend/src/components/assistant/AssistantResultPanel.tsx`, `ItineraryMap.tsx` — giữ nhiều khách sạn + loại điểm sân bay của feat/agent, đổi màu indigo/blue sang `brand` theo release.
- `src/data_collection/fresh_catalog_db.py` — import cả `fold` và `trip_combo_dates`.
- `docs/spec/hop-dong-tich-hop-frontend.md` — dòng "Đặt ngay" theo release (không còn thanh toán tất cả).

## Quyết định

- Bỏ "Thanh toán tất cả" ở widget trợ lý theo release (2026-10-08); không chạm PRD.

## Kiểm tra

- `validate_contract.py`: PASS.
- `tsc --noEmit` frontend: sạch. `vitest run tests/unit`: 749/749 pass.
- Backend `tests/contract tests/architecture tests/unit`: 1970 passed, 2 skipped.
- `data_collection/tests/test_fresh_catalog_job.py`: chưa chạy được, venv thiếu `curl_cffi`.

## Còn lại / rủi ro

- Chưa chạy e2e Playwright; `widget-opening.spec.ts` có kỳ vọng không còn nút "Thanh toán tất cả".
- Test data_collection cần môi trường có `curl_cffi`.
