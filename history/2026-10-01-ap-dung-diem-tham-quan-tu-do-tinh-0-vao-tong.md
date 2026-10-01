# Áp dụng: điểm tham quan tự do tính 0 đ vào tổng chi phí lịch trình

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs
- Thay thế: `history/2026-10-01-de-xuat-diem-tham-quan-tu-do-tinh-0-vao-tong.md` (đề xuất đã được chốt)

## Mục tiêu

Panel lịch trình ghi "Chi phí sản phẩm: Chưa tính được" khi lịch có điểm tham quan không có giá (FR-AGT-02). Trace LangSmith
`nhat-10-1`, thread `45befb6c-93d3-4c26-91eb-302df12381dc`, lượt "2 người lớn, 5 triệu": 3 bãi biển không giá làm
`estimatedTotal = null`. Người dùng xác nhận các điểm đó vào tự do và chốt đề xuất
`docs/prd/update-archive/2026-10-01-diem-tham-quan-tu-do-tinh-0-vao-tong.md` (nhatnm, 2026-10-01). Hai điểm cần chốt cùng
lấy theo phương án đề xuất: không loại trừ theo tag, thêm cảnh báo `FREE_ENTRY_ASSUMED`.

## File thay đổi

- `docs/prd/architecture.md` — sửa: §3 Tiêu chuẩn Grounding, điểm tham quan tự do tính 0 đ vào tổng.
- `docs/prd/update-archive/2026-10-01-diem-tham-quan-tu-do-tinh-0-vao-tong.md` — thêm (chuyển từ `docs/prd/update/`, file chưa từng commit nên dùng `mv`): trạng thái `đã áp dụng`.
- `src/backend/app/domain/itinerary/planning.py` — sửa: thêm `free_to_visit` (attraction/golf không có giá, hoặc `ticketed=false`); `_known_cost` trả 0 cho mục đó.
- `src/backend/app/agents/steps/narration.py` — sửa: bỏ `_free_to_visit` riêng, dùng `free_to_visit` của domain.
- `src/backend/app/agents/steps/composition.py` — sửa: cảnh báo `FREE_ENTRY_ASSUMED` khi tổng có điểm tham quan tự do.
- `src/backend/app/agents/steps/messages.py` — sửa: câu `cost_UNKNOWN` (vi, en) chỉ còn lý do "mục chưa có giá".
- `src/backend/app/agents/steps/prompts.py` — sửa: `NARRATE_PROMPT` nói điểm tham quan tự do không tốn gì trong [[total]]; lý do không có tổng chỉ còn "mục chưa có giá".
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: mô tả `estimatedTotal` (chỉ mô tả, không đổi kiểu).
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa: thêm `isFreeToVisit`, cùng luật với backend.
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — sửa: slot tham quan tự do ghi "Tham quan tự do".
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: tooltip "Chưa tính được" nói rõ là mục có vé thiếu giá.
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — sửa: thêm `TotalsTests` (4 test).
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm test bãi biển không giá → có tổng, có `FREE_ENTRY_ASSUMED`.
- `src/frontend/tests/unit/widgetPlan.test.ts` — sửa: thêm test `isFreeToVisit`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.2, quy tắc `estimatedTotal`), `docs/spec/hop-dong-tich-hop-frontend.md` (bảng trường `estimatedTotal`, `warnings[]`) — sửa.
- `history/2026-10-01-ap-dung-diem-tham-quan-tu-do-tinh-0-vao-tong.md` — thêm: entry này.

## Quyết định

- Một luật duy nhất trong domain (`free_to_visit`) cho cả tổng tiền lẫn lời diễn giải, để chữ "tham quan tự do" và con số
  không lệch nhau. Luật hẹp hơn bản cũ ở narration (`taxonomy != hotel`) thành attraction/golf; kết quả không đổi vì slot và
  gói nhiều ngày chỉ có attraction/golf.
- `unitPrice` của sản phẩm vẫn giữ `null` (không bịa giá 0 vào dữ liệu grounding); chỉ phép tính tổng coi là 0.
- Không đổi popup bản đồ (`components/assistant/ItineraryMap.tsx`): nó không hiện giá cho mục không giá sẵn rồi, và dùng
  `isFreeToVisit` ở đó sẽ bắt `components/` import từ `features/`.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- `.venv/bin/python -m pytest -q src/backend/tests src/evaluation/tests`: 1123 passed, 21 skipped, 5 failed — cùng 5 test
  `test_golden.py` đã fail sẵn (ghi ở `history/2026-10-01-tham-quan-tu-do-va-goi-nhieu-ngay.md`).
- Frontend `npx vitest run`: 49 file, 489 test pass; `npx tsc --noEmit`: chỉ 3 lỗi sẵn có trong `.next/types`.
- Tính lại `totals()` trên đúng lịch trong trace LangSmith: `(4260300, 'WITHIN_BUDGET')` (trước là `null`, `UNKNOWN`).

## Còn lại / rủi ro

- Backend local (uvicorn, không `--reload`) cần khởi động lại để có code mới; chưa thử tay trên trình duyệt.
- Một số điểm không có giá thực tế có thu phí (7 tour đi thuyền, 1 chèo bè, vài bảo tàng tỉnh); cảnh báo
  `FREE_ENTRY_ASSUMED` nói rõ điều này. Muốn loại trừ theo tag thì cần đề xuất mới.
- `docs/spec/data-collection/schema.md` §2 vẫn ghi `unitPrice = null` không phải miễn phí — đúng ở tầng dữ liệu; quy ước
  "tham quan tự do" là của tầng sản phẩm/agent.
- Chưa commit.
