# Dòng tiêu đề in đậm cho mọi câu trả lời của trợ lý

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, frontend, contract, evaluation, docs

## Mục tiêu

Mở rộng dòng đầu `**Tiêu đề**` (tóm tắt cả câu) từ câu báo giá trị không hợp lệ sang các câu trả lời khác: hỏi thiếu thông tin, form gợi ý, mâu thuẫn, điều kiện không xác minh được / không có sản phẩm, ngoài phạm vi, bị guardrail chặn, `NO_RESULTS`, `FALLBACK`. Chào hỏi, cảm ơn không có tiêu đề. Áp dụng đề xuất `docs/prd/update-archive/2026-09-30-tieu-de-cho-moi-cau-tra-loi.md` (FR-AGT-01, FR-AGT-03), chốt bởi Nguyễn Minh Nhật ngày 2026-09-30 ("oke code di"), phạm vi mặc định (các dòng "Có").

## File thay đổi

- `src/backend/app/agents/steps/messages.py` — sửa: tiêu đề vi/en (`title_*`), `titled()`, `strip_title()`, `MAX_TITLE_CHARS`; `no_results`, `no_results_date`, `FALLBACK`, `REFUSAL`, `CLARIFY_CONSTRAINT` mang tiêu đề; thêm `REFUSAL_BLOCKED` (đầu vào bị guardrail chặn).
- `src/backend/app/agents/steps/conversation.py` — sửa: `reply_title()`; `conversational_update` và `clarification_fallback` ghép tiêu đề cho mọi câu hỏi/từ chối (bỏ qua chào hỏi); `conversational_fallback` chọn `REFUSAL_BLOCKED` khi bị guardrail chặn; `_invalid_input_question` chỉ còn phần thân.
- `src/backend/app/agents/steps/prompts.py` — sửa: luật `title` cho mọi lý do hỏi lại (3–8 từ, để trống với chào hỏi).
- `src/backend/app/agents/steps/history.py` — sửa: `llm_context` cắt dòng tiêu đề khỏi tin nhắn trợ lý cũ.
- `src/backend/app/agents/models.py` — sửa: `ConversationalAnswer.title` tối đa 200 ký tự (backend cắt còn 80 khi hiển thị thay vì làm hỏng cả câu).
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: mô tả `question`, `NO_RESULTS.message`, `FALLBACK.message` (dòng đầu là `**Tiêu đề**`). Không đổi field/enum.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract.
- `src/frontend/src/components/assistant/AssistantResultPanel.tsx` — sửa: thẻ `NO_RESULTS`/`FALLBACK` tách tiêu đề khỏi phần thân.
- `src/frontend/src/components/assistant/AssistantView.tsx` — sửa: tên khi chia sẻ/lưu lấy từ tiêu đề.
- `src/frontend/src/components/assistant/AssistantConversation.tsx`, `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: khung lỗi in đậm dòng đầu (`InlineBold`).
- `src/frontend/tests/unit/inlineBold.test.ts` — sửa: thêm 2 case (`NO_RESULTS`/`FALLBACK`, lỗi ngoài phạm vi).
- `src/evaluation/agent/golden.py` — sửa: khoá `titleFirstLine` (`answer_text`, `has_title_first_line`).
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: `titleFirstLine` ở G-063, G-064, G-065, G-073, G-075, G-077 (2 lượt), G-078; G-074 kỳ vọng `false`.
- `src/evaluation/tests/test_golden.py` — sửa: test `titleFirstLine`.
- `src/backend/tests/unit/agents/test_reply_titles.py` — thêm: 18 test (ghép/cắt tiêu đề, tiêu đề theo trường hợp vi/en, chào hỏi không tiêu đề, từ chối, guardrail, `NO_RESULTS`/`FALLBACK`, lịch sử).
- `src/backend/tests/unit/agents/test_itinerary_runtime.py`, `test_guardrails.py`, `test_suggestions.py` — sửa: kỳ vọng theo câu có tiêu đề.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.3), `docs/spec/agent/{langgraph-nodes,response-and-errors,golden-dataset-how-to-add-more-case}.md`, `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: bảng tiêu đề và quy tắc.
- `docs/prd/update-archive/2026-09-30-tieu-de-cho-moi-cau-tra-loi.md` — thêm (trạng thái `đã áp dụng`).
- `history/2026-09-30-de-xuat-tieu-de-cho-moi-cau-tra-loi.md`, `history/2026-09-30-tieu-de-cho-moi-cau-tra-loi.md` — thêm.

## Quyết định

- LLM viết `title` cùng `message`, backend ghép `**title**\nmessage`; có tiêu đề cố định làm dự phòng. Câu cố định (guardrail, điều kiện bắt buộc không có sản phẩm, `NO_RESULTS`, `FALLBACK`) mang tiêu đề ngay trong chuỗi. Không thêm field vào contract.
- Tiêu đề bị cắt khỏi lịch sử gửi lại LLM để mô hình không bắt chước hay trả lời tiêu đề; bản lưu giữ nguyên.
- B2 (ngoài phạm vi) và B3 (guardrail) vẫn là lỗi `VALIDATION_ERROR` 400; tiêu đề nằm trong `error.message`. Hai trường hợp có tiêu đề khác nhau nên tách `REFUSAL` / `REFUSAL_BLOCKED`.
- Không đặt `titleFirstLine` ở G-046 (LLM có thể xếp vào chào hỏi hoặc ngoài phạm vi) và các case `NO_RESULTS` (phụ thuộc dữ liệu).
- Không sửa `docs/prd/requirements.md` theo quyết định trước của người dùng.

## Kiểm tra

- `python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture src/backend/tests/contract src/evaluation/tests`: 331 passed, 4 failed.
  - 3 test `test_golden.py` fail sẵn từ trước (`test_has_exactly_one_case_per_category_with_unique_ids`, `test_clear_requests_state_their_start_date_with_a_placeholder_and_check_the_extraction`, `test_a_start_date_question_is_answered_before_the_expected_result`).
  - 1 test `test_itinerary_runtime.py::test_abbreviation_is_resolved_by_llm_from_catalog_names_only` fail do thay đổi ngoài task này trong working tree (`check_destination` chuẩn hoá điểm đến ngay ở `extract`, nên event của `tool` không còn "normalized destination"); chưa xử lý.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- Frontend: `npm run typecheck` pass; eslint các file đã sửa sạch; `npm test` 149 passed.
- Chưa chạy golden với LLM thật; chưa thử tay trên widget và `/assistant`.

## Còn lại / rủi ro

- Chạy golden và thử tay với LLM thật để đánh giá chất lượng tiêu đề LLM viết (có thể quá chung chung); tiêu đề cố định là dự phòng.
- Client khác đọc `error.message` (app Streamlit, curl) sẽ thấy dấu `**` ở B2/B3.
- Test `test_abbreviation_...` cần người sở hữu thay đổi `check_destination` cập nhật.
- Chưa commit.
