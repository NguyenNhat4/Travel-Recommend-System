# Hỏi lại khi ngày khởi hành đã qua

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Bị thay thế một phần bởi: 2026-09-30-bao-loi-dau-vao-khong-hop-le.md
- Phạm vi: agent, evaluation, docs

## Mục tiêu

Người dùng nêu ngày khởi hành đã qua ("từ hôm qua", "20/9" khi hôm nay 30/9), chip sửa ngày về quá khứ, hoặc hội thoại mở lại khi ngày đã lưu đã qua: agent vẫn gọi tool rồi trả `NO_RESULTS` "chưa mở bán cho ngày …" — sai lý do. Nay agent hỏi lại ngày qua `clarify`, không gọi tool. Áp dụng đề xuất `docs/prd/update-archive/2026-09-30-hoi-lai-khi-ngay-di-da-qua.md` (FR-AGT-01), chốt bởi Nguyễn Minh Nhật ngày 2026-09-30.

## File thay đổi

- `src/backend/app/agents/steps/classification.py` — sửa: `extract_result` kiểm `startDate` < `vietnam_today()` sau nhánh thiếu điểm đến/số ngày; xoá ngày khỏi intent, `clarification_reason = "past_start_date"`, ghi `past_start_date`; hỏi gộp party/budget nếu chưa hỏi.
- `src/backend/app/agents/state.py` — sửa: thêm `past_start_date`.
- `src/backend/app/agents/nodes.py` — sửa: `intake` đặt `past_start_date = None`; docstring `extract`/`clarify`. Luồng không đổi (clarify vẫn gọi LLM).
- `src/backend/app/agents/steps/conversation.py` — sửa: `conversation_input` thêm `past_start_date`/`today` (dd/mm/yyyy) vào payload LLM cho lý do này; `clarification_fallback` có câu dự phòng.
- `src/backend/app/agents/steps/prompts.py` — sửa: luật `past_start_date` trong `CONVERSATION_PROMPT`.
- `src/backend/app/agents/steps/messages.py` — sửa: câu dự phòng `past_start_date` vi/en; thêm `display_date` (chuyển từ `composition._display_date`).
- `src/backend/app/agents/steps/composition.py` — sửa: dùng `messages.display_date`.
- `src/backend/tests/unit/agents/test_classify.py` — sửa: thêm `PastStartDateTests` (hôm qua, đã hỏi chi tiết, hôm nay hợp lệ, chip, ngày đã lưu); `DefaultYearTests` đổi mốc hôm nay/ngày lưu để vẫn kiểm đúng ý cũ; ngày cố định `2026-10-10` → `2999-10-10`.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: hai test qua graph (LLM viết câu, payload có hai ngày, không gọi tool; LLM lỗi thì câu cố định nêu hai ngày); ngày cố định 2026 sẽ thành ngày đã qua → năm 2999.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: thêm G-078 (ngày `{today-1}` → hỏi lại, lượt sau `{today+7}` → gọi tool); G-055 đổi "1/10 đến 3/10" sang placeholder.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.3), `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/response-and-errors.md`, `docs/spec/agent/state-fields.md` — sửa: ghi quy tắc.
- `docs/prd/update-archive/2026-09-30-hoi-lai-khi-ngay-di-da-qua.md` — thêm: đề xuất, trạng thái `đã áp dụng`.
- `history/2026-09-30-de-xuat-hoi-lai-khi-ngay-di-da-qua.md` — thêm: entry bước đề xuất.

## Quyết định

- Câu hỏi lại do LLM viết (người dùng yêu cầu), không bỏ qua LLM; backend đưa sẵn hai ngày đã định dạng để LLM chỉ chép lại. Câu cố định chỉ dùng khi LLM lỗi/timeout, như mọi lý do khác.
- Không sửa `docs/prd/requirements.md` theo quyết định của người dùng — lệch bước 3 của AGENTS.md §8 là có chủ ý; quy tắc chỉ ghi ở spec agent.
- `_this_year` giữ nguyên: ngày đã qua trong năm nay bị hỏi lại, không tự đẩy sang năm sau.
- Contract không đổi (`missingFields` enum đã có `startDate`). Frontend không đổi (form đã chặn `min={today}`).

## Kiểm tra

- `python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture`: 193 passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- `python -m pytest -q src/evaluation/tests`: 3 failed, 49 passed — cùng 3 test đã fail trước thay đổi (kiểm bằng `git stash`): `test_has_exactly_one_case_per_category_with_unique_ids`, `test_clear_requests_state_their_start_date_with_a_placeholder_and_check_the_extraction`, `test_a_start_date_question_is_answered_before_the_expected_result`; không phát sinh lỗi mới.
- Chưa chạy golden G-078 với LLM thật và chưa thử tay qua endpoint.

## Còn lại / rủi ro

- Chạy G-078 và thử "đi Nha Trang 3 ngày từ hôm qua" với LLM thật để xem câu LLM viết có nêu đúng hai ngày.
- 3 test `src/evaluation/tests/test_golden.py` fail sẵn từ trước, chưa xử lý.
- Hội thoại mở lại sang hôm sau mà ngày đã lưu đã qua sẽ bị hỏi lại ngày (có chủ ý).
