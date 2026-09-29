# Form gợi ý thông tin chuyến đi khi trợ lý hỏi lại không hiệu quả

- Ngày: 2026-09-29
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, frontend, docs, evaluation

## Mục tiêu

Người dùng gửi ảnh chụp widget: trả lời "bao nhiêu ngày cũng được" ba lần liên tiếp, trợ lý hỏi lại đúng một câu ba lần
— hội thoại kẹt vòng vì `days`/`destination` là bắt buộc và không có giới hạn số lần hỏi. Sau khi thảo luận
(`history/2026-09-29-de-xuat-so-ngay-mac-dinh.md`, bị thay thế), người dùng chốt hướng: sau một lượt hỏi bằng câu chữ mà
vẫn thiếu, trợ lý hiển thị ngay trong khung chat một **form đã điền sẵn giá trị gợi ý** cho mọi trường bắt buộc của
chuyến đi; ô điểm đến chỉ liệt kê vài lựa chọn tiêu biểu; bấm xác nhận thì câu yêu cầu hoàn chỉnh được **đặt vào ô nhập
tin nhắn, không tự gửi**, để người dùng đọc lại/sửa rồi mới gửi.

Đề xuất: `docs/prd/update-archive/2026-09-29-form-goi-y-thong-tin-chuyen-di.md` (đã áp dụng, chốt bởi Nguyễn Minh Nhật
ngày 2026-09-29). Phục vụ FR-AGT-01, FR-AGT-03, FR-AGT-05.

## File thay đổi

**PRD (theo AGENTS.md mục 8, áp dụng trước khi sửa source)**
- `docs/prd/requirements.md` — sửa AC-AGT-01: thêm đoạn hành vi hai lượt hỏi rồi chuyển sang form.
- `docs/prd/architecture.md` — sửa §3 sơ đồ: tách `CheckClarification --> AskUser` thành hai cạnh, thêm nhánh
  `SuggestForm` (nhánh trả về của `clarify`, không phải node mới — graph vẫn 11 node).
- `docs/prd/user-flow.md` — thêm ghi chú form gợi ý dưới wireframe màn `/assistant` §4.2.
- `docs/prd/update-archive/2026-09-29-form-goi-y-thong-tin-chuyen-di.md` — thêm: đề xuất đã cập nhật theo hai phản hồi
  bổ sung của người dùng (5–10 điểm đến; xác nhận đổ vào ô nhập chứ không tự gửi) và chuyển trạng thái `đã áp dụng`;
  `git mv` từ `docs/prd/update/`.

**Contract**
- `src/shared/contracts/schemas/itinerary-agent.yaml` — thêm field tuỳ chọn `clarificationForm`
  (`fields`, `defaults: TripIntent`, `startDateMin`) vào `ItineraryNeedsClarification`; tương thích ngược, giữ v1.
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `npm run generate:api-types`.

**Backend**
- `src/backend/app/agents/state.py` — thêm `clarification_rounds: int`.
- `src/backend/app/agents/nodes.py` — `intake`/`intake_node_async` khởi tạo và khôi phục `clarification_rounds` từ
  store; `finalize_node_async` lưu lại.
- `src/backend/app/agents/steps/classification.py` — `extract_result` đếm `clarification_rounds` khi còn thiếu
  `destination`/`days`; vòng ≥ 2 đặt `clarification_reason = "suggest_form"` thay vì `None`.
- `src/backend/app/agents/steps/conversation.py` — thêm `clarification_form()` dựng `clarificationForm` từ
  `state["intent"]`/`supported_destinations`/`vietnam_today()`; `_question_response` gắn field này khi
  `clarification_rounds >= 2` và còn thiếu `destination`/`days`; `clarification_fallback` xử lý câu cố định cho lý do
  `suggest_form`.
- `src/backend/app/agents/steps/messages.py` — thêm khoá `suggest_form` (câu mời tinh chỉnh, vi/en).
- `src/backend/app/agents/steps/prompts.py` — `CONVERSATION_PROMPT` thêm hướng dẫn cho `clarification_reason =
  "suggest_form"` (mời tinh chỉnh, không lặp câu hỏi, không nêu giá trị cụ thể vì form đã hiện sẵn).

**Frontend**
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — mới: form gợi ý (chip điểm đến tối đa 8 mục theo
  `productCount`, stepper số ngày chặn 1–7, `<input type="date" min={startDateMin}>`, stepper người lớn/trẻ em, ô ngân
  sách tuỳ chọn); export `tripDetailsPrompt()` dựng câu yêu cầu hoàn chỉnh từ `TripIntent`.
- `src/frontend/src/features/itinerary/widget/widgetTypes.ts` — `WidgetChatMessage` thêm `clarificationForm`.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — derive `clarificationForm` từ
  `item.response`; thêm `handleConfirmTripDetails` (đặt prompt vào `inputVal`, không gửi).
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — render `TripDetailsForm` dưới bubble có
  `clarificationForm`, chỉ ở tin nhắn cuối cùng.
- `src/frontend/src/components/assistant/AssistantConversation.tsx` — render `TripDetailsForm` inline trong
  transcript (trước đây `NEEDS_CLARIFICATION` bị loại khỏi `AssistantResultPanel` ở cả hai điểm gọi trên `/assistant`,
  nên form phải nằm ngay trong bubble chat, dùng `setInput` cục bộ để đặt vào ô nhập).

**Test**
- `src/backend/tests/unit/agents/test_classify.py` — 2 test mới: lượt 1 thiếu field → `clarification_reason=None`,
  `clarification_rounds=1`; lượt 2 vẫn thiếu → `clarification_reason="suggest_form"`, `clarification_rounds=2`.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — 1 test tích hợp qua graph thật: lượt 1 hỏi chữ (không
  có `clarificationForm`) → lượt 2 có `clarificationForm` đúng field/defaults, `toolCalled=False` → lượt 3 (câu hoàn
  chỉnh) `COMPLETED`.
- `src/frontend/tests/unit/tripDetailsForm.test.tsx` — mới: giới hạn 5–10 điểm đến, chặn ngày > 7/< hôm nay, xác nhận
  chỉ gọi `onConfirm` (không tự gửi), `tripDetailsPrompt()` dựng đúng câu.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — thêm case `G-077` (đánh số lại từ `G-076` khi merge `release-mvp-v2` — id đó đã bị case Similar-tool của upstream dùng trước) (category `multi_turn`): "hà nội" → hỏi
  chữ; "bao nhiêu ngày cũng được" → vẫn `NEEDS_CLARIFICATION`, `toolCalled: false` (không lặp vô hạn); câu hoàn chỉnh
  mô phỏng từ form → `COMPLETED`.

**Tài liệu**
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3 — thêm mô tả hai lượt hỏi rồi chuyển form, ví dụ JSON
  `clarificationForm`.
- `docs/spec/hop-dong-tich-hop-frontend.md` — thêm mô tả `clarificationForm` và cách Web render/xác nhận.
- `docs/spec/agent/state-fields.md` — thêm `clarification_rounds`; cập nhật `clarification_reason` (thêm
  `suggest_form`).
- `docs/spec/agent/langgraph-nodes.md` — thêm mục "Form gợi ý" ở giai đoạn 3; cập nhật input/output của `extract` và
  `clarify` trong bảng chi tiết.
- `docs/spec/agent/field-review.md` — thêm dòng `clarificationForm` vào bảng field mới ở §2.2.
- `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — thêm mục hướng dẫn viết case cho luồng form gợi ý.

## Quyết định

- Ngưỡng hiện form: đếm theo hội thoại (`clarification_rounds`), chỉ tăng khi còn thiếu `destination`/`days`; lượt 1
  hỏi chữ, từ lượt 2 trả form — theo đúng yêu cầu "chỉ sau một lượt".
- Form phủ mọi trường bắt buộc (không chỉ trường thiếu), để người dùng sửa lại cả phần đã nói nếu muốn.
- Điểm đến: chỉ 8 lựa chọn (top theo `productCount`), không đổ hết catalog — theo phản hồi bổ sung của người dùng.
- Xác nhận form **không gửi ngay**: đặt câu hoàn chỉnh vào ô nhập để người dùng tự gửi/sửa — theo phản hồi bổ sung thứ
  hai. Không dùng `intentOverride` vì nó là chip sửa từng field và đang bị loại khỏi luật hỏi chi tiết
  (`classification.py`, dòng gần `if details and not asked and not state.get("intent_override")`).
- Vì `AssistantResultPanel`'s amber card (`NEEDS_CLARIFICATION`) hoá ra là dead code ở cả hai điểm gọi hiện có (widget
  nổi và `/assistant`, xác nhận qua khảo sát Explore agent), form được gắn trực tiếp vào bubble chat của
  `WidgetChat.tsx`/`AssistantConversation.tsx` thay vì tái dùng nhánh đó.
- Ràng buộc `startDate ≥ startDateMin` chỉ áp cho form (chặn UI), không đổi hành vi ngày quá khứ của câu chat tự do —
  spec §4.3 vẫn ghi ngày quá khứ không bị từ chối cho luồng chat, để không phá golden case cũ.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (88 schema).
- `.venv/bin/pytest src/backend/tests/unit/agents src/backend/tests/contract src/backend/tests/architecture`:
  201 passed (198 gốc + 3 mới).
- `npx tsc --noEmit` (src/frontend): pass, không lỗi.
- `npx vitest run tests/unit` (src/frontend): 103 passed (97 gốc + 6 mới).
- YAML dataset: `python3 -c "import yaml; yaml.safe_load(...)"` — 76 case, không lỗi cú pháp.
- `PYTHONPATH=. .venv/bin/pytest src/evaluation/tests/test_golden.py`: 47 passed, **3 failed — tồn tại từ trước, xác
  nhận bằng `git stash` (baseline không có thay đổi của task này cũng fail đúng 3 test này, chỉ khác số đếm case 75
  thay vì 76)**. Không thuộc phạm vi sửa của task này; ghi lại để người sau biết đây không phải hồi quy mới.
- Chưa chạy golden thật (cần LLM + Postgres catalog thật) và E2E Playwright của widget.

## Còn lại / rủi ro

- `test_has_exactly_one_case_per_category_with_unique_ids`,
  `test_a_start_date_question_is_answered_before_the_expected_result`,
  `test_clear_requests_state_their_start_date_with_a_placeholder_and_check_the_extraction` trong
  `src/evaluation/tests/test_golden.py` đang fail từ trước nhánh này (dataset đã lớn hơn giả định "14 case, mỗi
  category một case" và một số case cũ chưa dùng placeholder `{today+N}`). Cần người phụ trách evaluation xử lý riêng,
  không thuộc phạm vi đề xuất này.
- Đề xuất `docs/prd/update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` vẫn chờ chốt và chồng lấn phần
  `startDate` (cùng khuôn "gợi ý → mặc định có thông báo" nhưng riêng, không gộp). Nên xử lý sớm để hai quy tắc về
  ngày đi không đá nhau.
- Chưa kiểm tay qua trình duyệt thật (dev server) theo kịch bản trong plan; chỉ kiểm bằng unit/contract test.
- Widget nổi trước đây không có UI cấu trúc nào cho `NEEDS_CLARIFICATION` ngoài `question` dạng text — đã vá bằng thay
  đổi này, nhưng chưa kiểm tra tương tác với tính năng lưu/tải lại hội thoại (`loadConversation`) khi tin nhắn cũ có
  `clarificationForm`.
