# Điểm không có giá là "tham quan tự do"; gói nhiều ngày tách khỏi lịch để người dùng cân nhắc riêng

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs

## Mục tiêu

Từ screenshot lịch Phú Quốc 5 ngày, 50 người (FR-AGT-03, FR-AGT-04):

1. "Thị trấn Hoàng Hôn - Sunset Town · giá đang cập nhật": người dùng chốt rằng điểm tham quan không có giá là nơi đến
   chơi được, nên ghi là tham quan tự do, không ghi "giá đang cập nhật". Lần trước
   (`history/2026-10-01-narrate-loi-dien-giai-lich-trinh-va-sua-doi-ngay.md`) chỉ coi `ticketed=false` là miễn phí,
   tức chưa làm theo ý người dùng.
2. Gói "[03 ngày không giới hạn] - VinWonders + Vinpearl Safari + Tour Grand World" bị xếp vào một buổi chiều. Người
   dùng: gói có thể kéo dài nhiều ngày thì phải hỏi người dùng cân nhắc riêng.

## File thay đổi

- `src/backend/app/domain/itinerary/planning.py` — sửa: `multi_day_span` (span từ `durationMinutes` ≥ 2 ngày hoặc tên "03 ngày", "2 Day", "4-Day", "4D3N", "3N2Đ"), `multi_day_offers`; `compose_plan` bỏ gói nhiều ngày khỏi slot.
- `src/backend/app/agents/steps/composition.py` — sửa: `COMPLETED` kèm `searchResults` chứa tối đa 2 gói nhiều ngày mỗi loại.
- `src/backend/app/agents/steps/validation.py` — sửa: đối chiếu grounding `searchResults` cho cả `COMPLETED` (trước chỉ `FALLBACK`).
- `src/backend/app/agents/steps/narration.py` — sửa: `_free_to_visit` gồm điểm tham quan/golf không có giá (khách sạn không có giá vẫn là "giá đang cập nhật"); `_offers`, `_offers_block`, `_with_offers`: mục cố định "Gói nhiều ngày để bạn cân nhắc riêng" kèm câu hỏi, chèn trước "Chi phí dự kiến" ở cả câu LLM lẫn bản dựng bằng luật; payload LLM có `consider_separately`; link tới gói được coi là hợp lệ.
- `src/backend/app/agents/steps/messages.py` — sửa: "tham quan tự do" (vi) / "visit at your own pace" (en); câu chi phí khi không có tổng; chuỗi của mục gói nhiều ngày.
- `src/backend/app/agents/steps/prompts.py` — sửa: `NARRATE_PROMPT` diễn giải điểm tham quan tự do, không nhắc gói nhiều ngày (backend tự thêm), luôn có mục "Chi phí dự kiến".
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: mô tả `ItineraryCompleted.searchResults` (chỉ mô tả, không đổi kiểu).
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: bấm link sản phẩm không nằm trong lịch (gói nhiều ngày) thì mở trang chi tiết sản phẩm.
- `src/frontend/src/components/assistant/inlineBold.tsx` — sửa: nút link căn trái (tên dài bị căn giữa khi xuống dòng).
- `src/backend/tests/unit/agents/test_multi_day_offers.py` — thêm: 7 test.
- `src/backend/tests/unit/agents/test_narration.py` — sửa: kỳ vọng "tham quan tự do", khách sạn không có giá, câu chi phí mới.
- `docs/spec/agent/langgraph-nodes.md` (§5 luật xếp lịch), `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.2) — sửa.
- `history/2026-10-01-tham-quan-tu-do-va-goi-nhieu-ngay.md` — thêm: entry này.

## Quyết định

- "Tham quan tự do" chỉ là cách diễn đạt. `estimatedTotal` vẫn là `null` khi thiếu giá, đúng `docs/prd/architecture.md`
  §3 ("không coi thiếu giá là 0"). Muốn cộng tổng mà coi điểm không có giá là 0 thì lệch PRD, cần đề xuất riêng.
- Dùng chữ "tham quan tự do" thay "miễn phí" để không khẳng định giá vé; người dùng có thể đổi chữ.
- Gói nhiều ngày đi qua `searchResults` (trường tuỳ chọn đã có trên `COMPLETED`), không thêm trường contract mới. Bấm link
  thì mở trang sản phẩm, vì khung lịch trình bên phải không có gói này.
- Mục hỏi về gói nhiều ngày do backend chèn, không để LLM viết. Đo với gpt-4o-mini: khi để LLM viết, mục có liệt kê gói
  nhưng không có câu hỏi và còn làm mất mục "Chi phí dự kiến".
- "[01 ngày]" và tour "Full Day" (1.440 phút) vẫn xếp được; ngưỡng là từ 2 ngày.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests src/evaluation/tests`: 1025 passed, 21 skipped, 5 failed — cùng 5 test `test_golden.py` đã fail sẵn.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- Frontend `npx vitest run`: 405 test pass; typecheck chỉ còn lỗi `.next/types` sẵn có.
- Chạy `multi_day_span` trên snapshot catalog `2026-09-30`: 24/616 sản phẩm attraction/golf bị coi là nhiều ngày; đã thử các mẫu tiêu biểu (vé "03 ngày không giới hạn", "(2 ngày)", "4D3N", thẻ hội viên 90 ngày).
- `narrate_node_async` với gpt-4o-mini thật, kịch bản Phú Quốc 5 ngày có gói 3 ngày, Sunset Town không giá và vé thuyền
  có ngoặc vuông trong tên: 4/4 lần `reason=llm`, có mục hỏi gói nhiều ngày trước mục chi phí, Sunset Town ghi "tham quan tự do".

## Còn lại / rủi ro

- Người dùng trả lời "thêm gói 3 ngày" thì chưa có luồng xếp gói vào nhiều ngày liên tiếp; hiện chỉ hỏi.
- Lịch có thể trống nhiều ngày khi catalog chỉ có ít hoạt động một ngày (screenshot cũ còn ngày 4–5 trống).
- Chưa thử tay trên trình duyệt.
- Chưa commit.
