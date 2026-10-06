# FALLBACK nêu lý do thật và hiện thẻ ứng viên

- Ngày: 2026-10-02
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, frontend, docs

## Mục tiêu

Người dùng báo: chat "đi đà nẵng 3 ngày" → "ngày 15/10, 2 người lớn, 5 triệu" ra "Chưa dựng được lịch trình hoàn chỉnh"
mà không nói vì sao, và câu trả lời mời "xem các sản phẩm dưới đây" nhưng không có sản phẩm nào. Phục vụ FR-AGT-03,
AC-AGT-01, NFR-REL-01.

**Bằng chứng.** Trace LangSmith `01a0fa0c-f5f8-75d0-afbc-aa93bfbd3857` (project `nhat-10-1`):

- `search_products` hotel ra 1 khách sạn (Serenity Retreat); attraction và golf ra 0.
- `get_recommendations` báo `INVALID_TOOL_RESPONSE`, không thử lại được.
- `evaluate` vì có lỗi vĩnh viễn nên trả `fallback`.
- Câu FALLBACK là câu cố định.

Gọi lại recommendations khi đăng nhập P1 thì thấy contract của tool từ chối `attributes.returnDate = "15/10"` (format
`date`). Snapshot 2026-09-30 có 33 combo (collector `trip_combos`) ghi `returnDate` dạng `dd/mm`. Khách chưa đăng nhập đi
nhánh `popular` nên không gặp.

## File thay đổi

- `src/backend/app/agents/steps/composition.py` — sửa:
  - thêm `fallback_message(state, compose_failed=)`, dựng bằng luật: tool nào lỗi, không có gì xếp được lịch, lỗi bước
    xếp lịch, và đếm những gì đã tìm được;
  - `fallback()` dùng câu này; `compose_or_fallback` truyền `compose_failed=True`.
- `src/backend/app/agents/steps/messages.py` — sửa: thêm khoá `fallback_*` (vi/en); bỏ hằng `FALLBACK` cố định.
- `src/backend/tests/unit/agents/test_fallback_reason.py` — thêm: 4 test theo đúng ca của trace (fail trên code cũ).
- `src/backend/tests/unit/agents/test_reply_titles.py` — sửa: kiểm tiêu đề qua `fallback_title`.
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — sửa: `narrationProducts` nhận cả `FALLBACK`.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: tin nhắn `FALLBACK` có `products` từ `searchResults`.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — sửa: sản phẩm không được nhắc trong chữ có thẻ ở
  cuối bong bóng.
- `src/frontend/tests/unit/widgetNarration.test.tsx` — sửa: thêm test thẻ ứng viên FALLBACK.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa §4.5: câu FALLBACK nêu lý do thật, Web hiện thẻ ứng viên.
- `history/2026-10-02-fallback-neu-ly-do-that.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD.** PRD không quy định câu FALLBACK; tiêu đề vẫn cố định như spec §4.3.
- **Câu dựng bằng luật, không qua LLM**, để lý do luôn đúng với dữ liệu của lượt (cùng cách với `NO_RESULTS`).
- **Chưa sửa gốc lỗi dữ liệu** (`returnDate` của `trip_combos`, phạm vi data).
- **Chưa đổi luật `evaluate`** (gợi ý lỗi thì vẫn dựng lịch từ Search). Việc này đổi hành vi trong spec itinerary nên
  cần đề xuất riêng.

## Kiểm tra

- `pytest src/backend/tests/contract src/backend/tests/unit/agents src/backend/tests/unit/domain`: 686 passed.
- `vitest run` (src/frontend): 52 file, 516 test PASS; `tsc --noEmit` không có lỗi ngoài `.next/`; eslint widget sạch.

## Còn lại / rủi ro

- Backend đang chạy không có `--reload`, phải khởi động lại mới thấy câu mới.
- Gốc lỗi vẫn còn: 33 combo có `returnDate` sai định dạng, nên người dùng đăng nhập ở các điểm đến có combo này vẫn ra
  FALLBACK (nay có nêu lý do).
- Đề xuất cho bước sau: chuẩn hoá ngày ở collector `trip_combos` và cho gợi ý cá nhân hoá là best-effort.
