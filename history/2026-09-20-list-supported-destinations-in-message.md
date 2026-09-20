# Liệt kê điểm đến hỗ trợ khi điểm đến ngoài catalog

- Ngày: 2026-09-20
- Tác giả: người dùng / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation

## Mục tiêu

Khi điểm đến không có trong catalog, agent chỉ trả câu cụt "Điểm đến chưa có trong danh sách catalog hiện tại." Người dùng không biết có thể đi đâu. Cần một thông báo đúng giọng trợ lý lập kế hoạch du lịch, nêu điểm đến đã nhập và liệt kê các điểm đến hiện có.

## File thay đổi

- `src/backend/app/agents/nodes.py` — sửa: thông báo `unsupported` (vi/en) có `{destination}` và `{destinations}` kèm lời mời chọn lại; `_message` nhận thêm tham số; `tool_node` truyền tên người dùng nhập và danh sách catalog.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm test message vi/en nêu điểm đến đã nhập và có tên điểm đến catalog.
- `src/evaluation/agent/README.md` — sửa: mô tả message của `UNSUPPORTED_DESTINATION` trong bảng node `tool`.
- `history/2026-09-20-list-supported-destinations-in-message.md` — thêm: entry này.

## Quyết định

- Danh sách nằm trong `error.message` (viết cho người dùng, theo `common.yaml`) nên mọi client, gồm Streamlit demo, hiển thị được mà không đổi code UI. `details.supportedDestinations` giữ nguyên để frontend dựng chip theo `hop-dong-tich-hop-frontend.md` §8.
- Message dựng bằng template cố định, danh sách lấy từ `list_destinations()`; không gọi thêm LLM nên không thể bịa điểm đến (grounding).
- Không đổi OpenAPI/contract; không chạy `validate_contract.py`.
- `src/evaluation/agent/streamlit_app.py` không đổi.

## Kiểm tra

- `LANGSMITH_TRACING=false pytest src/backend/tests`: 93 passed.

## Còn lại / rủi ro

- Catalog nhiều điểm đến sẽ làm message dài (hiện fixture có 9); khi lớn hơn nên giới hạn số tên trong message và để UI dùng `details.supportedDestinations`.
- Catalog rỗng vẫn sinh "Các điểm đến mình đang hỗ trợ: ." nhưng chưa xử lý riêng.
- Chưa chạy thật với model/UI.
