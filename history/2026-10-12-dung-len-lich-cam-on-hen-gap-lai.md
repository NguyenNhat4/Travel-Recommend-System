# Chốt và áp dụng đề xuất: không muốn đi nữa thì cảm ơn, hẹn gặp lại, không hiện form

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/agent-end (từ `release-mvp-v2` 0bb4a688)
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs

## Mục tiêu

Người dùng báo lỗi: nhắn "ko đi nữa", "ko đi du lịch nữa" hay câu cùng ý thì trợ lý lại hiện form lập kế hoạch. Mong muốn:
trợ lý cảm ơn và hẹn gặp lại. Phục vụ FR-AGT-01, AC-AGT-01.

Nguyên nhân, tái hiện bằng luật tất định (LLM giả gắn nhãn, `extract` rỗng) trên `release-mvp-v2`:
- `CLASSIFY_PROMPT` cố ý xếp "không đi nữa" vào `travel` (`history/2026-09-30-sua-prompt-classify.md`, để khỏi bị coi là
  ngoài phạm vi) nhưng chưa có cách trả lời riêng.
- Đã đồng ý lập lịch: `travel` → `extract` rỗng → thiếu trường → `suggest_form`; `vague` → `_vague_form` → form. Đủ bốn
  trường thì `extract` ra `tool` và lập lại lịch.
- Chưa đồng ý: `travel` → `extract` → `explore` (giới thiệu điểm đến, mời lập lịch).
- `reply_title`, `conversational_fallback`, `question_note` không có nhánh cho lời chào, đều rơi về câu hỏi thiếu trường.

Người dùng chốt trong chat (12/10): giữ chuyến đang lên để nối lại; lời chào do LLM viết, có câu cố định khi LLM lỗi; không
thêm lưới luật tất định; duyệt thay đổi PRD; làm từ `release-mvp-v2` trên nhánh mới `feat/agent-end`.

## File thay đổi

- `docs/prd/requirements.md` — sửa: AC-AGT-01 thêm ngoại lệ "form hiện ở mỗi lượt… trừ lượt người dùng nói không muốn đi hoặc
  không muốn lên lịch nữa" và câu mô tả hành vi cảm ơn, hẹn gặp lại, giữ chuyến.
- `docs/prd/architecture.md` — sửa: §3 thêm cạnh `ClassifyTurn --> Converse` cho người dùng không muốn đi nữa; `Converse --> [*]`
  thêm "chào tạm biệt".
- `docs/prd/user-flow.md` — sửa: đoạn "Form gợi ý thông tin chuyến đi" thêm ngoại lệ.
- `docs/prd/update-archive/2026-10-12-dung-len-lich-cam-on-hen-gap-lai.md` — thêm: đề xuất, trạng thái `đã áp dụng`, chốt bởi
  tqanh123 ngày 2026-10-12 (tạo thẳng trong archive vì đã chốt trong chat, như `history/2026-09-29-de-xuat-route-trang-danh-muc.md`).
- `src/backend/app/agents/models.py` — sửa: `TurnRoute.route` thêm nhãn `stop`.
- `src/backend/app/agents/steps/classification.py` — sửa: `route_result` đưa `stop` sang `converse` với `missing_fields=[]`,
  `clarification_reason=None`, `pending_offer=None`; không gộp `understood(route)`, không bật nút, không đụng intent và
  `plan_consent`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `CLASSIFY_PROMPT` bỏ "không đi nữa" khỏi `travel`, thêm "nối lại chuyến đã
  dừng" vào `travel`, thêm nhãn `stop` kèm các trường hợp không phải `stop`, câu đáp ngắn sau lời chào là `conversation`, "seven
  labels"; `CONVERSATION_PROMPT` không tiêu đề với `stop` và đoạn hướng dẫn lời chào.
- `src/backend/app/agents/steps/conversation.py` — sửa: `reply_title` trả `None` cho `stop`; `conversational_fallback` trả câu
  `farewell` cố định cho `stop` (cũng phủ đường guardrail đầu ra ở `finalize`).
- `src/backend/app/agents/steps/turn_notes.py` — sửa: `question_note` ghi `note_stop` cho lượt `stop`.
- `src/backend/app/agents/steps/messages.py` — sửa: thêm `note_stop`, `farewell` (vi, en).
- `src/backend/app/agents/nodes.py` — sửa: docstring `classify_node`, `converse_node`.
- `src/backend/scripts/push_prompts_to_langsmith.py` — sửa: mô tả prompt `classify` liệt kê đủ nhãn.
- `src/backend/tests/unit/agents/test_classify.py` — sửa: test route `stop` (cả khi đã và chưa đồng ý lập lịch); viết lại test
  prompt cũ (khẳng định "không đi nữa" là `travel`) thành hai test: `travel` có "đổi ngày", "đi tiếp" và không còn "không đi
  nữa"; nhãn `stop` có ví dụ và phần loại trừ.
- `src/backend/tests/unit/agents/test_reply_titles.py` — sửa: thêm 3 test (không tiêu đề; lời chào không có trường thiếu, form,
  nút; câu cố định vi/en).
- `src/backend/tests/unit/agents/test_turn_context.py` — sửa: ghi chú lượt `stop` (`question_note`, `turn_note`).
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm 4 test cấp graph (dừng rồi nối lại tới `COMPLETED`; dừng
  khi chưa đồng ý bỏ lời mời, không `explore`; dừng sau lịch không tìm lại, giữ `previous_*`; LLM lỗi dùng câu cố định).
- `src/evaluation/datasets/agent_test_cases_nhat.yaml` — sửa: thêm TC-15 (4 lượt: lập lịch → "ko đi du lịch nữa" → nối lại →
  "thôi không đi nữa đâu").
- `src/evaluation/agent/agent-test-cases-nhat.md` — sửa: dòng danh mục và mục TC-15.
- `src/evaluation/tests/test_golden.py` — sửa: thêm `TC-15` vào danh sách id cố định.
- `docs/spec/agent/nghiep-vu/hieu-y-dinh-va-hoi-lai.md` — sửa: nhãn `stop`; bỏ câu "Không đi nữa… vẫn là `travel`".
- `docs/spec/agent/langgraph-nodes.md` — sửa: mục `converse`, dòng tiêu đề, đường đi `converse`, bảng node và bảng field.
- `docs/spec/agent/state-fields.md` — sửa: giá trị `interaction_type`, `missing_fields`, `pending_offer` với `stop`.
- `docs/spec/agent/nghiep-vu/vong-doi-mot-luot.md`, `docs/spec/agent/working-context.md` — sửa: sơ đồ nhánh `converse`.
- `docs/spec/agent/response-and-errors.md`, `docs/spec/agent/nghiep-vu/dien-giai-va-kiem-tra.md` — sửa: lời chào không tiêu đề.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: bảng tiêu đề §4.3 và mục trò chuyện/khám phá.
- `history/2026-10-12-dung-len-lich-cam-on-hen-gap-lai.md` — thêm: entry này.

## Quyết định

- Nhãn mới `stop` ở `classify` (LLM gắn), không thêm luật nhận câu (người dùng chốt). Không thêm node: `stop` đi `converse` như
  chào hỏi, cảm ơn.
- Contract và frontend không đổi: câu trả lời là `NEEDS_CLARIFICATION` chỉ có `question`, như câu chào hỏi, cảm ơn (mô tả `question`
  trong contract đã ghi "câu trả lời chào hỏi, cảm ơn không có tiêu đề"). Widget chỉ hiện form khi có `clarificationForm`.
- Giữ chuyến: intent, ràng buộc, `plan_consent`, bộ đếm hỏi, `previous_selection/options/plan` giữ nguyên; chỉ bỏ `pending_offer`
  để "ok" sau đó không bị coi là đồng ý lời mời cũ. "thôi đi tiếp" là `travel` trên chuyến đã giữ.
- `route_result` trả `stop` trước bước đồng ý lập lịch, nên chuyến không bị đổi bởi luật chê nơi hay "cứ chọn đại"; không gộp
  `understood(route)` vì `explore_place` làm `conversational_update` thay câu bằng "chưa tìm thấy <nơi>".
- Ranh giới trong prompt: rút lại thay đổi ("không đổi nữa"), chê một nơi ("không đi Đà Nẵng nữa"), "để sau" trả lời lời mời
  lập lịch (AC-AGT-06 của đề xuất `goi-y-truoc-khi-lap-lich`), huỷ đơn đã có vẫn giữ nhãn cũ.
- PRD: cạnh mới ở §3 là một dòng riêng, không sửa dòng `ClassifyTurn --> Converse` hiện có mà đề xuất đang chờ
  `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` cũng sửa.

## Kiểm tra

Tầng tất định (fixture, LLM giả), Windows, `.venv` của repo:
- 12 test mới chạy trên code chưa sửa: 12 failed (đúng kỳ vọng); sau khi sửa: 12 passed.
- `pytest -q -p no:cacheprovider src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/architecture`:
  2004 passed, 1 failed. Test fail là `test_itinerary_runtime.py::RuntimeTests::test_catalog_hydration_is_concurrent_and_bounded`
  (đo thời gian: tool timeout 1 giây khi máy bận). Có sẵn trên nhánh gốc: cùng lệnh trên bản `release-mvp-v2` chưa sửa (giải
  nén bằng `git archive` ra thư mục tạm) cho 1 failed, 1994 passed, đúng test đó. Chạy riêng file: 75 passed; chạy riêng test:
  2/3 lần pass.
- `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false pytest -q -p no:cacheprovider src/backend/tests`: 2824 passed, 36 skipped,
  0 failed (315 giây).
- `pytest -q -p no:cacheprovider src/evaluation/tests/test_golden.py`: 79 passed.
- Mô phỏng `route_result` với nhãn `stop` ở bốn trạng thái (đã đồng ý: thiếu số ngày / thiếu chi tiết / đủ bốn trường; chưa đồng
  ý, đang mời): cả bốn `decision=simple`, `missing_fields=[]`, không form, không tiêu đề, `pending_offer=None`. Trước khi sửa
  (nhãn `travel`/`vague`): ba trạng thái đầu ra form hoặc lập lại lịch, trạng thái thứ tư đi `explore`.
- Không đổi contract hay mock nên không chạy `validate_contract.py`.
- **Chưa chạy với LLM thật:** máy này không có API key LLM (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` đều trống
  trong `.env`). Chưa đo được model thật có gắn `stop` đúng không.

## Còn lại / rủi ro

- Đo nhãn với LLM thật (chạy ở nhiệt độ 1): `python -m src.evaluation.agent.golden --only TC-04,TC-10,TC-12,TC-15 --repeat 3`
  (backend local, `docs/spec/agent/golden-run.md`). Chú ý các câu sát ranh giới: "không đổi nữa" (TC-04), "không biết" (TC-10),
  "ok" sau lời mời (TC-12), "để sau" sau lời mời, "chán, Đà Nẵng đi rồi", "ok"/"cảm ơn" ngay sau lời chào. Nhãn lệch thì sửa
  prompt.
- Lỗi có sẵn, ngoài phạm vi: `intake_node` không reset `clarification_reason` (chỉ lộ trong LangGraph Studio có checkpointer;
  `stop` tự đặt `None`); câu dự phòng của nhánh `conversation` khi LLM lỗi hỏi "mấy ngày" nếu chuyến đã đủ; câu có "phương án N"
  đi tắt `apply_option` trước `classify` nên "thôi không lấy phương án 2 nữa" vẫn áp phương án 2;
  `test_catalog_hydration_is_concurrent_and_bounded` chập chờn khi chạy cả bộ.
- Khi áp `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` vào PRD, giữ câu và cạnh mới của đề xuất này.
- Commit trên `feat/agent-end`, merge vào `release-mvp-v2` ở local theo yêu cầu người dùng để chạy thử; chưa push.
