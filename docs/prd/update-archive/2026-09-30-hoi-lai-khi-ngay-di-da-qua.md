# Hỏi lại khi ngày khởi hành đã qua

- Ngày: 2026-09-30
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-30
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01), **không sửa câu chữ** theo yêu cầu người đề xuất (khi áp dụng cũng bỏ qua bước cập nhật PRD theo quyết định này); quy tắc chỉ ghi ở spec agent
- Mã FR/NFR: FR-AGT-01

## Lý do

AC-AGT-01 đã coi ngày khởi hành trước hôm nay là không hợp lệ, nhưng chỉ ghi cho **form** gợi ý ("Form chặn giá trị không hợp lệ: … ngày khởi hành không trước ngày hôm nay"). Đường chat và chip sửa tay (`intentOverride`) không có luật này:

- Người dùng gõ "đi Nha Trang 3 ngày từ hôm qua" (hoặc một ngày đã qua như "20/9" khi hôm nay là 30/9), agent nhận `startDate` trong quá khứ, gọi tool, sản phẩm bị loại vì sai ngày và trả `NO_RESULTS` "chưa mở bán cho ngày …" — sai lý do, người dùng không biết mình nhập ngày đã qua.
- Chip sửa `startDate` về ngày đã qua cũng đi thẳng tới tool.

## Nội dung đề xuất

Không đổi câu chữ `docs/prd/requirements.md`. Thêm quy tắc hành vi ở spec agent, áp dụng cùng chuẩn "không trước ngày hôm nay" của form cho mọi nguồn ngày:

- Sau khi gộp intent (câu chat, chip, ngày đã lưu từ lượt trước) và đã đủ điểm đến + số ngày: nếu `startDate` < hôm nay theo giờ Việt Nam (`vietnam_today`) thì **không gọi tool**, trả `NEEDS_CLARIFICATION`:
  - `missingFields` có `startDate`; `knownIntent.startDate = null` (ngày đã qua bị xoá khỏi intent).
  - Câu hỏi do **LLM viết** qua node `clarify` như mọi lượt hỏi khác. Backend đưa sẵn ngày đã qua và ngày hôm nay (đã định dạng dd/mm/yyyy) vào payload để LLM chép lại, không tự tính ngày. LLM lỗi hoặc quá thời gian thì dùng câu cố định vi/en, ví dụ: "Ngày khởi hành 29/09/2026 đã qua. Bạn chọn một ngày từ hôm nay (30/09/2026) trở đi giúp mình nhé."
  - Nếu số người/ngân sách còn thiếu và chưa từng hỏi, hỏi gộp trong cùng câu (giữ quy tắc "hỏi gộp một lần" của AC-AGT-01), rồi đánh dấu đã hỏi.
- Lượt sau người dùng nêu ngày hợp lệ thì lập lịch bình thường; nói chưa chốt ngày thì lập lịch không kèm ngày như hiện nay.
- Kiểm tra đứng sau các nhánh hiện có (lỗi số ngày, mâu thuẫn, thiếu điểm đến/số ngày), nên không đổi thứ tự hỏi đã có.
- Contract không đổi: `NEEDS_CLARIFICATION`, `missingFields` enum đã có `startDate`.

## Ảnh hưởng và rủi ro

- Ngày đã lưu từ lượt trước cũng bị kiểm: hội thoại mở lại sang ngày hôm sau mà ngày đi đã qua thì lượt kế tiếp sẽ hỏi lại ngày thay vì lập lịch với ngày cũ.
- `_this_year` giữ nguyên: "20/9" khi hôm nay 30/9 vẫn hiểu là 20/09 năm nay (đã qua) và rơi vào câu hỏi lại, **không** tự đẩy sang năm sau.
- Liên quan đề xuất đang chờ `2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md`: nếu đề xuất đó được chốt, câu hỏi lại ở đây vẫn giữ nguyên; hai luật không chồng nhau (một luật cho ngày đã qua, một luật cho chưa có ngày).

## Thay đổi source sau khi chốt

- `src/backend/app/agents/steps/classification.py` (`extract_result`): kiểm `startDate` < `vietnam_today()` sau nhánh thiếu điểm đến/số ngày; xoá ngày khỏi intent, `decision = "missing_info"`, `clarification_reason = "past_start_date"`, ghi ngày đã qua vào state `past_start_date`.
- `src/backend/app/agents/state.py`: thêm `past_start_date` (tạm thời, không lưu theo hội thoại).
- `src/backend/app/agents/steps/conversation.py` (`conversation_input`): với lý do `past_start_date`, thêm `past_start_date` và `today` (dd/mm/yyyy) vào payload cho LLM; `clarification_fallback`: câu cố định khi LLM lỗi.
- `src/backend/app/agents/steps/prompts.py` (`CONVERSATION_PROMPT`): luật cho lý do `past_start_date`.
- `src/backend/app/agents/steps/messages.py`: câu dự phòng `past_start_date` vi/en; chuyển helper định dạng ngày `display_date` từ `composition.py` sang đây.
- `src/backend/app/agents/nodes.py`: không đổi luồng (node `clarify` vẫn gọi LLM), chỉ cập nhật docstring.
- Test: `src/backend/tests/unit/agents/test_classify.py` (hôm qua, hôm nay, chip ngày đã qua, ngày đã lưu đã qua; sửa `DefaultYearTests`), `test_itinerary_runtime.py` (qua graph: không gọi tool, LLM được gọi với payload có hai ngày; LLM lỗi thì câu cố định; đổi ngày cố định đã qua `2026-09-21` sang ngày tương lai).
- `src/evaluation/datasets/itinerary_agent_golden.yaml`: thêm G-078 "từ `{today-1}`" kỳ vọng `NEEDS_CLARIFICATION`, `missingFieldsInclude: [startDate]`, `toolCalled: false`; đổi ngày cứng của G-055 sang placeholder.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/response-and-errors.md`, `docs/spec/agent/state-fields.md`: ghi quy tắc.
