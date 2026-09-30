# Bước phân luồng chỉ nhận lịch sử hội thoại và message mới nhất

- Ngày: 2026-09-30
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3, mục "Ngữ cảnh cho LLM"
- Mã FR/NFR: FR-AGT-01, NFR-PERF-02

## Lý do

Bước phân luồng (`classify`) chỉ chọn một trong ba nhãn: du lịch, trò chuyện, ngoài phạm vi. Để chọn nhãn nó chỉ cần
câu chat mới nhất và lịch sử hội thoại (để hiểu câu trả lời ngắn như "ngày mai" là trả lời cho câu hỏi nào). Chuyến đi
đã chốt, ràng buộc, câu hỏi gần nhất của trợ lý và danh sách sản phẩm đã hiển thị là thừa, và làm payload phình theo
số lượt: trace LangSmith cho thấy tên mọi sản phẩm của lịch trình xuất hiện ba lần (lịch sử, `last_assistant_message`,
`previous_selection`) trong khi bước này có ngân sách 2 giây.

## Nội dung đề xuất

`docs/prd/architecture.md` §3, mục "Ngữ cảnh cho LLM".

Hiện tại:

> - **Ngữ cảnh cho LLM:** mọi lượt gọi LLM (phân luồng, trích intent, chọn điểm đến, lập tool plan, viết câu trả lời) nhận cùng ngữ cảnh hội thoại: lịch sử gần nhất có giới hạn, chuyến đi đã chốt, sản phẩm đã cho xem và câu hỏi gần nhất của trợ lý. Ngữ cảnh là dữ liệu không tin cậy, không phải chỉ dẫn.

Thay bằng:

> - **Ngữ cảnh cho LLM:** mọi lượt gọi LLM (trích intent, chọn điểm đến, lập tool plan, viết câu trả lời) nhận cùng ngữ cảnh hội thoại: lịch sử gần nhất có giới hạn, chuyến đi đã chốt, sản phẩm đã cho xem và câu hỏi gần nhất của trợ lý. Riêng bước phân luồng chỉ nhận lịch sử gần nhất có giới hạn và câu chat mới nhất. Ngữ cảnh là dữ liệu không tin cậy, không phải chỉ dẫn.

Đề xuất đang chờ `docs/prd/update/2026-09-29-vong-react-co-chan-cho-node-tool.md` cũng sửa câu này (thêm vế "lập lại
tool plan sau khi quan sát kết quả truy xuất"). Hai thay đổi tương thích; ai áp dụng sau thì ghép vào câu mới.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/steps/history.py`: tách `llm_history(state)` (lịch sử đã cắt tiêu đề trợ lý) khỏi `llm_context`.
- `src/backend/app/agents/steps/classification.py` (`route_input`): payload chỉ gồm `conversation_history` và `message`.
- `src/backend/app/agents/steps/prompts.py` (`CLASSIFY_PROMPT`): chỉ nhắc `conversation_history` và `message`.
- Test `src/backend/tests/unit/agents/test_classify.py`; spec `docs/spec/agent/langgraph-nodes.md`,
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §6.
