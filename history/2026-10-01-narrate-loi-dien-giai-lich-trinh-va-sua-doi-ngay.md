# Node `narrate` viết lời diễn giải lịch trình và sửa lỗi đổi ngày không ăn

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, contract, docs

## Mục tiêu

Hai lỗi người dùng báo (phục vụ FR-AGT-01, FR-AGT-03, FR-AGT-04, FR-AGT-05, NFR-REL-01):

1. **Đổi ngày không ăn.** T1 lên lịch Hà Nội 02/10, T2 "Đổi ngày", T3 "Ngày 14 tháng 10", T4 "À nhầm ngày 15 tháng 10". Trace LangSmith
   (project `nhat-10-1`): ở T4 `extract` (gpt-4o-mini) chép nguyên intent đã lưu vào `patch`, trong đó `startDate` vẫn là 14/10, kèm
   `change_without_value = ["startDate"]`; `_supplies_a_change` thấy ngày không đổi nên hỏi lại. Lượt "1410" bị hỏi lại và lặp nguyên văn câu trước.
2. **Câu trả lời `COMPLETED` không có lời nào.** `compose` dựng lịch bằng luật, contract không có trường text, nên chat hiện "Lịch trình đã được hoàn tất.".
   Người dùng muốn câu mở đầu ghi nhận thay đổi ("Mình ghi nhận đổi ngày đi thành 15/10. Lịch trình mình gợi ý như sau") rồi một bài có các mục
   in đậm, diễn giải như người lập kế hoạch du lịch; tên sản phẩm trong chat bấm được để focus sản phẩm ở khung lịch trình bên phải.
   Người dùng chốt: LLM viết tự do; link sản phẩm trong chat focus panel; giá `UNKNOWN` chỉ là "đang cập nhật", điểm công cộng mới là miễn phí tham quan; giọng văn hay.

## File thay đổi

- `src/backend/app/domain/itinerary/dates.py` — thêm: `explicit_dates` (đọc ngày tường minh bằng luật: `15/10`, `15-10`, `15.10.2026`, `2026-10-15`, `ngày 15 tháng 10`, `15 thg 10`; không nhận `1410`, `3-4 người`, `2.5 triệu`) và `this_year`.
- `src/backend/app/agents/steps/classification.py` — sửa: lưới an toàn `_date_from_message` (đúng một ngày tường minh, không phải `end_date`, mà `patch.startDate` trống hoặc bằng ngày đã lưu thì dùng ngày đọc được và bỏ `startDate` khỏi `change_without_value`); `_this_year` chuyển sang `dates.this_year`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `CONVERSATION_PROMPT` (câu trả lời không đọc được như "1410" thì không lặp, hỏi xác nhận "Ý bạn là 14/10/2026?"); thêm `NARRATE_PROMPT`.
- `src/backend/app/agents/steps/conversation.py` — sửa: payload `change_without_value` mang `today`.
- `src/backend/app/agents/steps/narration.py` — thêm: `trip_changes`, `changes_sentence`, `narration_input`, `render` (kiểm link/placeholder/số tiền, thay tên canonical, điền giá), `fallback_message` (cùng bố cục, dựng bằng luật), `narrated`, `unknown_links`.
- `src/backend/app/agents/models.py` — sửa: thêm `ItineraryNarration`.
- `src/backend/app/agents/nodes.py`, `graph.py` — sửa: node `narrate` (`compose → narrate → finalize`, sync + async, timeout mặc định 3 giây); `intake` ghi `previous_intent`; `finalize` thay `message` bằng bản dựng bằng luật khi guardrail bắt, giữ nguyên `COMPLETED`.
- `src/backend/app/agents/state.py` — sửa: thêm `previous_intent`.
- `src/backend/app/agents/steps/messages.py` — sửa: chuỗi vi/en cho lời diễn giải dự phòng; `PRODUCT_LINK`, `plain_links`.
- `src/backend/app/agents/steps/guardrails.py` — sửa: quét thêm `message` của `COMPLETED`.
- `src/backend/app/agents/steps/validation.py` — sửa: `response_issues` coi link lạ trong `message` là lỗi grounding; `answer_text` trả `message` của `COMPLETED` (nên mở lại hội thoại vẫn thấy lời diễn giải).
- `src/backend/app/agents/steps/history.py` — sửa: `llm_context` đổi `[Tên](product:id)` thành `Tên` khi đưa lịch sử lại cho LLM.
- `src/backend/app/agents/steps/__init__.py` — sửa: mô tả module.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: `ItineraryCompleted.message` (tuỳ chọn, thêm trường, tương thích ngược v1).
- `src/shared/mocks/itinerary-agent/completed.json` — sửa: thêm `message` mẫu.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract (`npm run generate:api-types`).
- `src/frontend/src/context/assistantState.ts` — sửa: `responseText` ưu tiên `message`.
- `src/frontend/src/components/assistant/inlineBold.tsx` — sửa: `parseAssistantText`, `AssistantText` (chỉ `**đậm**` và link sản phẩm, không chèn HTML).
- `src/frontend/src/components/assistant/assistantLabels.ts` — sửa: nhãn node `narrate`.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, `useFloatingWidget.ts`, `WidgetDays.tsx`, `widgetPlan.ts` — sửa: bấm tên sản phẩm trong chat thì mở rộng widget, chọn tab ngày, focus bản đồ, cuộn và tô viền thẻ (`focusProduct`, `locateProduct`, `data-product-id`).
- `src/backend/tests/unit/agents/test_dates.py`, `test_narration.py` — thêm: 12 + 22 test.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py`, `test_lab_copy.py` — sửa: fake LLM có `ItineraryNarration`, danh sách node có `narrate`, `message` còn nguyên sau `finalize`; topology mười hai node.
- `src/frontend/tests/unit/inlineBold.test.ts`, `assistantState.test.ts`, `widgetPlan.test.ts` — sửa/thêm.
- `docs/spec/agent/langgraph-nodes.md`, `state-fields.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.2, §4.3, §7.2), `docs/spec/hop-dong-tich-hop-frontend.md` (§9.3) — sửa.
- `history/2026-10-01-narrate-loi-dien-giai-lich-trinh-va-sua-doi-ngay.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD:** `architecture.md` §3 đã có bước `SynthesizeResponse … Tạo lời thoại`; spec §7.2 đã có "LLM trình bày lịch trình 3 giây". Thêm trường `message` là thêm tuỳ chọn trong v1. Dòng "C4 COMPLETED: không có văn bản message" trong đề xuất đã lưu `update-archive/2026-09-30-tieu-de-cho-moi-cau-tra-loi.md` bị thay bởi entry này (không sửa file archive).
- **Grounding giữ 100% dù LLM viết tự do:** LLM chỉ nhắc sản phẩm bằng link `[Tên](product:id)` và giá bằng placeholder `[[price:id]]`/`[[total]]`/`[[budget]]` (không dùng `{{…}}` vì script đẩy prompt lên LangSmith dùng mustache). Backend chặn `productId` lạ, số tiền tự viết, placeholder lạ; thay tên bằng tên canonical; sản phẩm LLM quên nhắc được thêm vào mục "Ngoài ra trong lịch trình" để vẫn bấm được. Vi phạm thì dùng bản dựng bằng luật, không trả lỗi.
- Câu ghi nhận thay đổi do backend chèn (so `previous_intent` với `intent`), không để LLM tự viết nên luôn đúng. Chỉ tính trường đã có giá trị trước đó.
- Giá: `attributes.ticketed = false` mới là "miễn phí tham quan"; giá vắng mặt là "giá đang cập nhật" (theo `docs/spec/data-collection/schema.md`: trip.com không hiện giá vẫn có thể bán vé). Tổng không cộng được thì nói mềm, không ghi 0.
- Lưới an toàn ngày chỉ chạy khi có đúng một ngày tường minh, để LLM tự xử lý câu nhiều ngày hoặc ngày tương đối.
- Mỗi lượt `COMPLETED` thêm một lượt LLM; timeout theo `ITINERARY_LLM_TIMEOUT_SECONDS` của runtime (hiện 30 giây trong `.env`), quá hạn thì dùng bản dựng bằng luật.
- Không sửa `src/backend/scripts/push_prompts_to_langsmith.py` và đề xuất langsmith đang chờ chốt: `NARRATE_PROMPT` là prompt thứ 7, cần thêm `vota-itinerary-narrate` khi đề xuất được chốt.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- `.venv/bin/python -m pytest -q src/backend/tests src/evaluation/tests`: 1016 passed, 21 skipped, 5 failed. 5 fail đều ở `src/evaluation/tests/test_golden.py` (3 `DatasetTests`, 2 `ScheduleFindingsTests`), đúng 5 test đã ghi là fail sẵn từ trước ở `history/2026-09-30-sua-prompt-classify.md`; chưa chạy lại trên bản gốc để đối chiếu.
- Frontend: `npx vitest run`: 44 file, 404 test pass; `npm run typecheck` chỉ còn lỗi `.next/types` sẵn có; eslint các file đã sửa: 0 lỗi (2 warning `ItineraryMap.tsx` sẵn có).
- **Chạy `narrate_node_async` với gpt-4o-mini thật** (nhiệt độ 0, lịch Hà Nội mẫu): 15/15 lần (5 với prompt đầu, 10 với prompt cuối) qua kiểm grounding, không lần nào rơi vào bản dựng bằng luật. Bản prompt đầu nói "không tính được tổng" dù tổng đã có và không nêu giá từng mục; sửa prompt (thêm `total_known`, khung mẫu, bắt buộc ghi giá) thì tổng và so ngân sách đúng, ca điểm miễn phí + giá chưa rõ + không đổi gì ra đúng "miễn phí tham quan" / "giá đang cập nhật" và không có câu ghi nhận.

## Còn lại / rủi ro

- Chưa thử tay trên trình duyệt (bấm link sản phẩm, cuộn, tô viền, bản đồ) và chưa chạy lại đúng kịch bản T1→T4 qua backend + widget thật; `extract` chập chờn nên nên chạy kịch bản vài lần và xem trace LangSmith có node `narrate`.
- LLM vẫn có thể nhắc một địa danh công cộng bằng chữ thường không có link; prompt cấm nhưng regex không chặn tuyệt đối. Link và giá thì luôn được kiểm.
- Ca "1410" chỉ được sửa bằng prompt (hỏi xác nhận), chưa đo bằng LLM thật.
- Golden dataset (`src/evaluation/datasets/itinerary_agent_golden.yaml`) chưa có ca kiểm `COMPLETED.message`.
- Chưa commit.
