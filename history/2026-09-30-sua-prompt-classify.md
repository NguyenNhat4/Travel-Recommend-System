# Sửa prompt classify: tách travel khỏi out_of_scope, đúng tên key payload

- Ngày: 2026-09-30
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs

## Mục tiêu

Kiểm input/output của node `classify` (trace LangSmith + payload dựng lại bằng `route_input`) cho thấy khung
structured output `TurnRoute` đúng, nhưng `CLASSIFY_PROMPT` có ba chỗ chưa chuẩn: (1) `travel` ("changes … anything
about a trip") chồng với `out_of_scope` ("cancellation actions"), nên "không đi nữa" có thể bị xếp nhầm là ngoài phạm
vi (400); (2) prompt gọi "known trip"/"last assistant question" trong khi payload dùng `known_intent`/
`last_assistant_message`; (3) "Return only the label" mâu thuẫn với output là object `{route: ...}`. Phục vụ
FR-AGT-01, FR-AGT-03. Không đổi hành vi ngoài nhãn phân luồng, không đổi contract, không lệch PRD.

## File thay đổi

- `src/backend/app/agents/steps/prompts.py` — sửa: `CLASSIFY_PROMPT` gọi đúng key payload; `travel` nêu rõ đổi mơ hồ, trả lời linh hoạt, bỏ chuyến đang lên kế hoạch; `out_of_scope` chỉ huỷ/đổi đơn hoặc booking đã có; thay "Return only the label" bằng "Set `route` to exactly one of the three labels".
- `src/backend/tests/unit/agents/test_classify.py` — sửa: thêm `ClassifyPromptTests` (4 test tất định trên chuỗi prompt và payload).
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: thêm G-079 (đa lượt: lập lịch Nha Trang → "không đi nữa" → "đổi ngày"; kỳ vọng `extract` chạy, `converse` không chạy, HTTP 200).
- `docs/spec/agent/langgraph-nodes.md` — sửa: ghi ranh giới `travel`/`out_of_scope` và tên key payload trong mục `classify`.
- `history/2026-09-30-sua-prompt-classify.md` — thêm.

## Quyết định

- Chỉ sửa prompt và test; không rút gọn payload của `classify` (sẽ đảo quyết định dùng chung `llm_context` cho mọi lượt LLM, cần người dùng đồng ý riêng).
- G-079 chỉ kiểm nhãn phân luồng (`nodesInclude: [extract]`, `nodesExclude: [converse]`), không ghi `status`, vì cách agent trả lời các câu này chưa được sửa.
- Test prompt là test chuỗi; LLM giả trả nhãn cố định nên không chứng minh được hành vi của model thật.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/architecture src/evaluation/tests`: 282 passed, 5 failed. Cả 5 fail có sẵn trước thay đổi (kiểm bằng `git stash`): 3 test `DatasetTests` (`test_a_start_date_question_is_answered_before_the_expected_result`, `test_clear_requests_state_their_start_date_with_a_placeholder_and_check_the_extraction`, `test_has_exactly_one_case_per_category_with_unique_ids`) và 2 test `ScheduleFindingsTests` (`test_cheapest_hotel_*`, `TypeError` ở `_stay_order` trong `src/evaluation/agent/golden.py:317`).
- Không đổi contract nên không chạy `validate_contract.py`.
- Chưa chạy G-079 với LLM thật.

## Còn lại / rủi ro

- Chạy G-079 với LLM thật và xem trace `classify_node` để xác nhận "không đi nữa" ra `travel`.
- Lỗi gốc trong ảnh chưa xử lý: `extract_result` ([classification.py](src/backend/app/agents/steps/classification.py)) luôn trả `tool` khi lượt không đổi gì nên vẫn lập lịch lại; `COMPLETED` luôn hiện câu cố định vì `itinerary.title` để trống. Hướng sửa đã đề xuất (hỏi lại `no_change` + title tất định), chờ người dùng chốt đề xuất PRD.
- 5 test fail có sẵn ở `src/evaluation/tests/test_golden.py` chưa xử lý.
- Chưa commit.
