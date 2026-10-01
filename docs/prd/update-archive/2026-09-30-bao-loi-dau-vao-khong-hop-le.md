# Báo lỗi đầu vào không hợp lệ: dòng đầu in đậm, lý do, gợi ý; câu LLM diễn giải hơn

- Ngày: 2026-09-30
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-30 (bằng lệnh "go implement task" sau khi xem plan và tự chọn các quyết định bên dưới)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01) — **không sửa câu chữ** theo yêu cầu người đề xuất; quy tắc ghi ở spec agent. Thay một phần `docs/prd/update-archive/2026-09-30-hoi-lai-khi-ngay-di-da-qua.md`.
- Mã FR/NFR: FR-AGT-01, FR-AGT-02

## Lý do

Khi người dùng nhập giá trị không hợp lệ, câu trả lời không thống nhất và thường không nói rõ sai ở đâu:

| Trường hợp | Hiện nay |
|---|---|
| Ngày đi đã qua (đủ điểm đến + số ngày) | LLM hỏi lại bằng một câu thường |
| Ngày đi đã qua khi còn thiếu điểm đến/số ngày ("di ngay 28 thang9") | Không nhắc tới; form lặng lẽ điền hôm nay |
| Điểm đến ngoài catalog | Lỗi 422 `UNSUPPORTED_DESTINATION`, câu cố định |
| Số ngày ngoài 1–7 | Lỗi 400 `INVALID_TRIP_DURATION`, câu cố định, không lưu hội thoại |
| 0 người lớn, số âm (trẻ em, ngân sách) | Trích xuất hỏng → lỗi `LLM_UNAVAILABLE` |

Ngoài ra câu LLM viết (hỏi thiếu thông tin, form gợi ý, trò chuyện, từ chối) quá cụt lủn: prompt yêu cầu "concise" / "one short sentence" và giới hạn 500 ký tự.

## Quyết định người dùng đã đưa ra

| Câu hỏi | Chọn |
|---|---|
| Ngày đã qua có gợi ý ngày còn bán (gọi Search) không? | Không, dừng ở `extract`; gợi ý "từ hôm nay trở đi" |
| Điểm đến ngoài catalog? | Chuyển từ lỗi 422 sang hỏi lại |
| Số người, ngân sách hợp lệ thế nào? | Theo contract (người lớn ≥ 1, trẻ em ≥ 0, ngân sách ≥ 0); không thêm ngưỡng mới |
| Diễn giải hơn áp dụng cho câu nào? | Mọi câu LLM viết (`clarify`, `converse`); câu của `compose` giữ nguyên |

## Nội dung đề xuất

Không đổi câu chữ `docs/prd/requirements.md`. Quy tắc hành vi ghi ở spec agent:

1. **Trường hợp không hợp lệ:** ngày đi trước hôm nay (giờ Việt Nam), điểm đến ngoài catalog, số ngày ngoài 1–7, người lớn < 1, trẻ em < 0, ngân sách < 0. Mọi trường hợp trả `NEEDS_CLARIFICATION` (HTTP 200); không còn lỗi 400/422 cho các trường hợp này. Trường sai bị xoá khỏi `knownIntent` và có trong `missingFields`; các trường hợp lệ khác được giữ cho lượt sau. Ngày đi quá xa (ngoài cửa sổ mở bán) không phải không hợp lệ, vẫn đi luồng `NO_RESULTS` hiện có.
2. **Không gọi tool thêm** để kiểm hợp lệ. Ngày, số ngày, số người, ngân sách kiểm ngay ở `extract`; điểm đến kiểm ở `tool` bằng danh sách điểm đến catalog như hiện nay.
3. **Dạng câu trả lời:** `question` có dòng đầu `**<tiêu đề>**` nêu cái gì sai, các dòng sau nêu lý do và một gợi ý cụ thể, rồi mời người dùng trả lời. Nhiều trường sai thì một tiêu đề chung, mỗi trường một dòng.
4. **LLM viết câu** (node `clarify`); backend đưa sẵn dữ liệu (giá trị sai, lý do, hôm nay dạng dd/mm/yyyy, khoảng hợp lệ, danh sách điểm đến) để LLM chỉ chép lại, không tự nghĩ ra ngày hay điểm đến. LLM lỗi hoặc quá thời gian thì dùng câu cố định cùng dạng.
5. **Gợi ý theo trường:** ngày đi → "chọn từ hôm nay (dd/mm/yyyy) trở đi"; điểm đến → danh sách điểm đến hỗ trợ (kèm `suggestedValues.destination`); số ngày → khoảng 1–7; số người/ngân sách → giá trị tối thiểu hợp lệ.
6. **Ngày đã qua khi còn thiếu điểm đến/số ngày:** câu vẫn nêu ngày đã qua; form gợi ý (AC-AGT-01) vẫn hiện đúng vòng.
7. **Giọng văn:** mọi câu LLM viết của `clarify` và `converse` ấm áp, 2–4 câu, nói ngắn vì sao cần thông tin và cho một ví dụ cách trả lời; không văn vẻ thừa, không nêu tên sản phẩm. Giới hạn `message` nâng từ 500 lên 1000 ký tự.
8. **Frontend** hiển thị `**…**` thành chữ đậm trong khung chat (màn `/assistant` và widget nổi).
9. **Contract:** không thêm field, chỉ ghi chú ở mô tả `question` rằng dòng đầu có thể là `**…**`. `UNSUPPORTED_DESTINATION`, `INVALID_TRIP_DURATION` vẫn ở enum (không xoá ở v1); trợ lý thôi không trả chúng.

Thay phần của đề xuất `2026-09-30-hoi-lai-khi-ngay-di-da-qua.md`: cơ chế riêng `past_start_date` gộp vào cơ chế chung `invalid_input`; ngày đã qua được nêu cả khi còn thiếu điểm đến/số ngày.

## Ảnh hưởng và rủi ro

- **Đổi hành vi đã khoá:** 422 `UNSUPPORTED_DESTINATION` (spec `response-and-errors.md`, golden G-073, `check_real_data_grounding.py`) và 400 `INVALID_TRIP_DURATION` (2 case golden, contract test) chuyển sang `NEEDS_CLARIFICATION`. Client dùng `conversationId` từ response 200 nên vẫn tiếp tục được hội thoại.
- Câu dài hơn: tốn thêm token LLM cho mỗi lượt hỏi lại; widget nổi cần hiển thị được nhiều dòng (đã `whitespace-pre-wrap`).
- Tiêu đề in đậm là markdown trong chuỗi `question`: client hiển thị chữ thô sẽ thấy dấu `**`.
- Số người lớn rất lớn (ví dụ 100) vẫn hợp lệ theo contract và vẫn lập lịch.

## Thay đổi source sau khi chốt

- Contract: `src/shared/contracts/schemas/itinerary-agent.yaml` (mô tả `question`).
- Backend `src/backend/app/agents/`: `models.py`, `state.py`, `steps/classification.py`, `steps/tool_planning.py`, `steps/evaluation.py`/`nodes.py` (evaluate bỏ qua khi `invalid_input`), `routing.py`, `steps/conversation.py`, `steps/messages.py`, `steps/prompts.py`.
- Frontend: helper chữ đậm dùng chung; `features/itinerary/widget/WidgetChat.tsx`, `components/assistant/AssistantConversation.tsx`, `AssistantResultPanel.tsx`.
- Test: `src/backend/tests/unit/agents/test_classify.py`, `test_itinerary_runtime.py`, `src/backend/tests/contract/test_assistant_contract.py`; golden `src/evaluation/datasets/itinerary_agent_golden.yaml`, `src/evaluation/tests/check_real_data_grounding.py`.
- Spec: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3/§4.6, `docs/spec/agent/response-and-errors.md`, `langgraph-nodes.md`, `state-fields.md`, `docs/spec/hop-dong-tich-hop-frontend.md`.
