# Báo lỗi đầu vào không hợp lệ: dòng đầu in đậm, lý do, gợi ý; câu LLM diễn giải hơn

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Thay thế một phần: 2026-09-30-hoi-lai-khi-ngay-di-da-qua.md (cơ chế `past_start_date` gộp vào `invalid_inputs`)
- Phạm vi: agent, frontend, contract, evaluation, docs

## Mục tiêu

Người dùng nhập giá trị không hợp lệ (ngày đi đã qua, điểm đến ngoài catalog, số ngày ngoài 1–7, số người/ngân sách ngoài giới hạn) nhận câu trả lời không thống nhất: lỗi 422/400 câu cố định, `LLM_UNAVAILABLE` (số người/ngân sách), hoặc không nhắc gì (ngày đã qua khi còn thiếu điểm đến/số ngày: "di ngay 28 thang9"). Nay mọi trường hợp là `NEEDS_CLARIFICATION` (200): dòng đầu in đậm nêu cái sai, bên dưới là lý do và gợi ý, do LLM viết. Đồng thời câu LLM viết diễn giải hơn (2–4 câu) thay vì cụt lủn. Áp dụng đề xuất `docs/prd/update-archive/2026-09-30-bao-loi-dau-vao-khong-hop-le.md` (FR-AGT-01, FR-AGT-02), chốt bởi Nguyễn Minh Nhật ngày 2026-09-30 bằng lệnh "go implement task" sau khi chọn các quyết định trong đề xuất.

## File thay đổi

- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: mô tả `question` (dòng đầu có thể là `**Tiêu đề**`). Không đổi field/enum.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract (thêm mô tả).
- `src/backend/app/agents/models.py` — sửa: bỏ giới hạn `adults`/`children`/`budget` ở model trích xuất (để báo lại thay vì `LLM_UNAVAILABLE`); `ConversationalAnswer` thêm `title`, `message` tối đa 1000 ký tự.
- `src/backend/app/agents/state.py` — sửa: `past_start_date` → `invalid_inputs`.
- `src/backend/app/agents/steps/classification.py` — sửa: `_invalid_inputs` (ngày đi < hôm nay, số ngày, số người, ngân sách theo `bounds` của contract) và `_ask_invalid`; bỏ trả 400 `INVALID_TRIP_DURATION`.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: điểm đến ngoài catalog thành `invalid_input` (xoá điểm đến khỏi intent, event `tool` mang `retrieval=False`) thay vì 422.
- `src/backend/app/agents/routing.py`, `nodes.py` — sửa: `evaluate` bỏ qua và route sang `clarify` khi `decision = "invalid_input"`; bỏ nhánh `resumable` của `finalize_node_async` (giờ là 200, lưu như lượt hỏi lại thường); `intake` đặt `invalid_inputs = []`; docstring.
- `src/backend/app/agents/steps/conversation.py` — sửa: payload LLM (`invalid_inputs`, `today`, `valid_ranges`, `form_shown`, `supported_destinations`), ghép `**title**` (tiêu đề dự phòng nếu LLM không đặt), câu dự phòng cùng dạng.
- `src/backend/app/agents/steps/messages.py` — sửa: tiêu đề và lý do từng loại không hợp lệ (vi/en); thêm `display_date`; bỏ `invalid_duration`, `unsupported`.
- `src/backend/app/agents/steps/prompts.py` — sửa: viết lại `CONVERSATION_PROMPT` (giọng ấm áp, 2–4 câu, nêu vì sao cần thông tin, ví dụ cách trả lời; luật `invalid_input`).
- `src/backend/app/agents/steps/composition.py` — sửa: dùng `messages.display_date`.
- `src/frontend/src/components/assistant/inlineBold.tsx` — thêm: `splitBoldTitle`, `InlineBold` (chữ đậm bằng React node, không HTML thô).
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, `components/assistant/AssistantConversation.tsx` — sửa: bong bóng trợ lý hiển thị `**…**` đậm.
- `src/frontend/src/components/assistant/AssistantResultPanel.tsx` — sửa: thẻ hỏi lại tách tiêu đề (h2) khỏi phần thân.
- `src/frontend/tests/unit/inlineBold.test.ts` — thêm.
- `src/backend/tests/unit/agents/test_classify.py` — sửa: `InvalidInputTests` thay `PastStartDateTests`; chỉnh `DefaultYearTests`; ngày cố định 2026-10-10 → 2999.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: viết lại test điểm đến ngoài catalog/số ngày thành hỏi lại; thêm test số người ngoài giới hạn, ngày đã qua ở vòng form, tiêu đề dự phòng; `ScriptedLlm` có `conversational_title`; ngày cố định → 2999.
- `src/backend/tests/unit/agents/test_contract_derived_models.py` — sửa: test theo mô hình mới.
- `src/backend/tests/contract/test_assistant_contract.py` — sửa: hai hàng lỗi 400/422 thành hỏi lại 200.
- `src/evaluation/agent/golden.py` — sửa: `retrieval_ran` (điểm đến ngoài catalog đi qua `tool` nhưng chưa Search thì không tính là gọi tool).
- `src/evaluation/tests/test_golden.py`, `check_real_data_grounding.py` — sửa.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: G-064, G-065, G-073 thành `NEEDS_CLARIFICATION`; G-055 dùng placeholder ngày; G-078 giữ.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.3, §4.6), `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/agent/{README,golden-dataset-how-to-add-more-case,golden-run,langgraph-nodes,presentation-script,response-and-errors,state-fields}.md` — sửa: quy tắc mới.
- `docs/prd/update-archive/2026-09-30-bao-loi-dau-vao-khong-hop-le.md`, `docs/prd/update-archive/2026-09-30-hoi-lai-khi-ngay-di-da-qua.md` — thêm (đề xuất, trạng thái `đã áp dụng`).
- `history/2026-09-30-hoi-lai-khi-ngay-di-da-qua.md`, `history/2026-09-30-de-xuat-hoi-lai-khi-ngay-di-da-qua.md` — thêm (entry của hai bước trước cùng ngày).

## Quyết định

- Ngày đã qua: dừng ở `extract`, không gọi Search; gợi ý "từ hôm nay trở đi" (người dùng chọn). Ngày quá xa vẫn đi `NO_RESULTS` kèm gợi ý ngày gần nhất.
- Điểm đến ngoài catalog: chuyển từ 422 sang hỏi lại (người dùng chọn). Mã `UNSUPPORTED_DESTINATION`, `INVALID_TRIP_DURATION` giữ trong enum (không xoá ở v1), trợ lý thôi không trả.
- Số người/ngân sách hợp lệ theo contract (người lớn ≥ 1, trẻ em ≥ 0, ngân sách ≥ 0), không thêm ngưỡng mới; "100 người" vẫn lập lịch.
- Tiêu đề in đậm do backend ghép (`**title**\n message`) để mọi câu báo có cùng dạng, LLM chỉ viết `title` và `message`.
- Không sửa `docs/prd/requirements.md` theo yêu cầu người dùng: lệch bước 3 của AGENTS.md §8 có chủ ý; quy tắc ở spec agent.
- Chốt đề xuất bằng lệnh "go implement task" (không có câu "chốt" riêng): ghi rõ ở đề xuất.

## Kiểm tra

- `python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture src/backend/tests/contract src/evaluation/tests`: 312 passed, 3 failed. 3 test fail (`test_golden.py`: `test_has_exactly_one_case_per_category_with_unique_ids`, `test_clear_requests_state_their_start_date_with_a_placeholder_and_check_the_extraction`, `test_a_start_date_question_is_answered_before_the_expected_result`) đã fail sẵn từ trước thay đổi (kiểm bằng `git stash`).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- Frontend `npm run typecheck`: pass; `npx eslint` các file đã sửa: sạch; `npm test`: 147 passed.
- Chưa chạy golden (G-064, G-065, G-073, G-078) với LLM thật; chưa thử tay trên widget và `/assistant`.

## Còn lại / rủi ro

- Chạy golden với LLM thật và thử tay: "di ngay 28 thang9", "đi Nha Trang 3 ngày từ hôm qua", "đi vũng tàu 1 ngày", "Nha Trang 10 ngày", "chao", "di du lich" để xem giọng văn mới và tiêu đề đậm.
- `assistantState.ts` (frontend) còn nhánh xử lý `UNSUPPORTED_DESTINATION`: không còn được kích hoạt, để lại vì vô hại.
- 3 test `test_golden.py` fail sẵn từ trước, chưa xử lý.
- Câu dài hơn tốn thêm token LLM mỗi lượt hỏi lại.
- Chưa commit.
