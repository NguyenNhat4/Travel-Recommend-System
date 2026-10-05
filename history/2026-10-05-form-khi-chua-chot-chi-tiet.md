# Form gợi ý khi người dùng không trả lời được ngày đi, số người, ngân sách

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent

## Mục tiêu

Áp dụng đề xuất `docs/prd/update/2026-10-05-form-khi-chua-chot-chi-tiet.md` (chốt bởi Nguyễn Minh Nhật, 2026-10-05). Thay thế: `2026-10-05-de-xuat-form-khi-chua-chot-chi-tiet.md`.

Hội thoại "Đi Đà Nẵng → 3 ngày → không biết" phải hiện form điền sẵn ở lượt 3 thay vì lập lịch ngay.

## File thay đổi

- `docs/prd/requirements.md` — sửa AC-AGT-01: câu trả lời không thêm được ngày đi, số người, ngân sách thì hiện form; form này chỉ hiện một lần mỗi hội thoại.
- `docs/prd/user-flow.md` — sửa đoạn "Form gợi ý thông tin chuyến đi": thêm điều kiện mới.
- `docs/prd/architecture.md` — sửa §3, cạnh `AskUser --> SuggestForm`.
- `docs/prd/update/2026-10-05-form-khi-chua-chot-chi-tiet.md` — sửa trạng thái: đã chốt.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — thêm `test_dont_know_after_the_trip_details_question_shows_the_prefilled_form` (3 lượt, Extraction lượt 3 lấy nguyên giá trị thô từ trace LangSmith); sửa `test_missing_trip_details_are_asked_once_in_one_question_then_the_trip_is_planned` theo AC mới (lượt 2 ra form, lượt 3 mới lập lịch).
- `src/evaluation/datasets/agent_test_cases_nhat.yaml` — thêm TC-10 (4 lượt: Đi Đà Nẵng → 3 ngày → không biết → không biết) để chạy với LLM thật và xem trace LangSmith.
- `src/evaluation/tests/test_golden.py` — sửa danh sách id bộ TC thêm `TC-10`.

## Quyết định

- Người dùng yêu cầu sửa PRD trực tiếp, tính là chốt đề xuất.
- Test chạy cả graph qua `InMemoryConversationStore` thay vì gọi `extract_result` với state dựng tay, để không phụ thuộc tên cờ state sẽ thêm khi sửa code.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_itinerary_runtime.py -k "dont_know_after_the_trip_details or missing_trip_details_are_asked_once"`: 2 failed trên code cũ (đúng mong đợi). Test mới fail ở lượt 3: `'COMPLETED' != 'NEEDS_CLARIFICATION'`; lượt 1–2 pass.
- `.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py`: 62 passed, 3 failed. Ba test fail (`test_has_exactly_one_case_per_category_with_unique_ids`, `test_a_start_date_question_is_answered_before_the_expected_result`, `test_clear_requests_state_their_start_date_with_a_placeholder_and_check_the_extraction`) fail y hệt khi stash thay đổi này, tức có sẵn trên bộ golden đầy đủ, không do TC-10.
- Chưa chạy TC-10 với LLM thật: backend không chạy lúc viết entry; người dùng tự chạy baseline.

## Còn lại / rủi ro

- Chưa sửa backend (`classification.py`, `conversation.py`, `state.py`, `nodes.py` lưu cờ mới qua lượt).
- `test_classify.py::StartDateQuestionTests::test_does_not_ask_again_after_it_has_asked` mã hoá hành vi cũ (đã hỏi + không nêu gì → `tool`); xem lại khi sửa code.
- Chưa đồng bộ spec (`docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/field-review.md`), đề xuất chưa chuyển sang `update-archive/`.
- `--sweep` của golden dùng lượt 2 "chưa chốt ngày đi"; theo AC mới lượt đó ra form thay vì lập lịch, nên sweep không còn kiểm lịch trình từng điểm đến. Cần đổi câu sweep (ví dụ thêm số người) khi sửa code.
- Lỗi riêng `get_recommendations` trả `INVALID_TOOL_RESPONSE` chưa điều tra.
