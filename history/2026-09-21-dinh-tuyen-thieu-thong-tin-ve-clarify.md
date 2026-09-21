# Định tuyến yêu cầu du lịch thiếu thông tin về `clarify` thay vì `converse`

- Ngày: 2026-09-21
- Tác giả: nhatutc2@gmail.com / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, docs
- Thay thế: một phần `2026-09-19-route-conversation-through-llm-answer.md` (quyết định coi "broad requests for travel suggestions without trip details" là `conversation`)

## Mục tiêu

Người dùng quan sát trên demo: khi nhận yêu cầu thiếu thông tin, graph đi vào `converse` thay vì `clarify`.
Tài liệu `docs/agent/langgraph-nodes.md` (§1, §3) đã ghi rõ thiếu `destination`/`days` thì phải đi `clarify`,
còn `converse` chỉ lo chào hỏi, cảm ơn và từ chối — code là chỗ lệch, không phải tài liệu.

## Nguyên nhân

Hai chỗ nối nhau trong `src/backend/app/agents/nodes.py`:

1. `EXTRACT_PROMPT` dạy model rằng "broad requests for travel suggestions without trip details are
   conversation", nên "gợi ý cho tôi một chuyến đi" bị gán `domain=conversation`.
2. `_classify_result` route mọi `domain != "travel"` sang `simple` → `converse`, bỏ qua `missing_fields`.

Quyết định (1) đến từ entry 2026-09-19, khi `clarify` còn là code chết và `answer` gánh cả việc hỏi lại.
Sau `2026-09-21-tach-clarify-khoi-answer.md` và `2026-09-21-tach-converse-compose.md`, ranh giới đã đổi
nhưng prompt phân loại thì chưa.

Response vẫn là `NEEDS_CLARIFICATION` nên contract không vỡ; cái sai là node chịu trách nhiệm, nên
trace đọc ra sai và câu hỏi do prompt hội thoại viết chứ không phải đường `clarify`.

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: `EXTRACT_PROMPT` tách lại ranh giới (`conversation` chỉ còn chào
  hỏi/cảm ơn/tán gẫu; yêu cầu lập hoặc gợi ý chuyến đi là `travel` kể cả khi chưa nói điểm đến/số ngày);
  `_classify_result` thêm biến `domain` nâng `conversation` → `travel` khi message có nêu bất kỳ chi tiết
  chuyến đi nào (`any(patch.values())`), và dùng `domain` cho cả `interaction_type` lẫn nhánh `simple`.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: `test_broad_suggestion_uses_llm_answer_without_catalog_claims`
  → `test_broad_suggestion_is_asked_by_clarify_without_catalog_claims`, kỳ vọng đường đi qua `clarify` và có
  `missingFields`; thêm: `test_trip_details_labelled_conversation_still_reach_clarify`.
- `docs/agent/langgraph-nodes.md` — sửa: §1 ghi rõ yêu cầu du lịch thiếu chi tiết không thuộc `converse`;
  §3 "Sáu ví dụ" → "Bảy ví dụ", thêm dòng "gợi ý cho tôi một chuyến đi"; chú thích trong sơ đồ luồng.

## Quyết định

- **Sửa ranh giới phân loại, không thêm điều kiện ở routing.** `route_after_classify` đã ánh xạ
  `missing_info` → `clarify` đúng từ entry 2026-09-21; chỉ `classify` gán sai nhãn. Thêm điều kiện ở routing
  sẽ tạo nguồn sự thật thứ hai cho cùng một quyết định — đúng lỗi mà `2026-09-21-tach-converse-compose.md`
  đã gỡ khi xoá `_needs_conversational_answer`.
- **Thêm một chốt xác định bên cạnh prompt.** Prompt là hướng dẫn cho model, không phải bảo đảm. Nếu model
  vẫn gán `conversation` cho câu có nêu chi tiết (ví dụ "đi 3 ngày"), `any(patch.values())` kéo nó về `travel`.
  Không dùng `missing_fields` làm điều kiện vì lời chào cũng luôn thiếu cả hai trường.
- **Chào hỏi, cảm ơn, `out_of_domain` và `side_effect` giữ nguyên đường `converse`.** Case 06 và 12 của
  `docs/agent/evaluation-plan.md` không đổi kỳ vọng.
- **`interaction_type` nay là domain sau khi nâng**, không phải nhãn thô của model, vì nó được đưa vào
  prompt hội thoại và phải khớp với node đang chạy.
- **Không đổi contract.** `Extraction` là model nội bộ của LLM (`models.py`: "Restricted LLM outputs,
  distinct from the shared HTTP response contract"); enum `domain`, tên node và hình dạng response đều
  giữ nguyên. Hình dạng `NEEDS_CLARIFICATION` vẫn đúng spec §4.3.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests`: **148 passed, 2 skipped**.
- `validate_contract.py`: **không chạy** — không thay đổi file contract hay mock (lý do ở mục Quyết định).
- **Chưa smoke test bằng LLM thật qua Streamlit.** Chưa xác nhận bằng mắt rằng câu "gợi ý cho tôi một
  chuyến đi" gõ vào demo cho ra trace `intake → classify → clarify → finalize`; test hiện dùng
  `ScriptedLlm`, tức kiểm routing chứ không kiểm model thật gán nhãn thế nào sau khi đổi prompt.

## Còn lại / rủi ro

- Phần prompt phụ thuộc model: cần smoke test với key thật để biết model có còn gán `conversation` cho các
  câu xin gợi ý chung không. Chốt `any(patch.values())` chỉ cứu được câu có nêu chi tiết.
- Ranh giới `conversation` với `travel` vẫn do model quyết ở các câu nửa vời ("chán quá, đi đâu chơi giờ").
  Chưa có case nào trong `evaluation-plan.md` phủ vùng xám này.
- Các việc còn lại từ `2026-09-21-tach-converse-compose.md` vẫn chưa làm: bản sync/async của `converse` và
  `clarify` còn lặp code; `InMemoryConversationStore` phình không giới hạn; ngân sách timeout chưa cộng lại được.
