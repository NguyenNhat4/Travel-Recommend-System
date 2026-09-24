# Bảng field-level cho mười node LangGraph

- Ngày: 2026-09-23
- Tác giả: người dùng (yêu cầu qua chat) / Claude Sonnet 5
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng muốn biết mỗi node trong itinerary agent đọc field nào của state, ghi field nào, trình bày
dạng bảng để dễ đọc, thay vì mô tả bằng lời như bảng cũ ở `langgraph-nodes.md` mục 6. Chỉ mô tả lại
đúng hành vi code hiện có (FR-AGT-01..05), không đổi hành vi.

## File thay đổi

- `docs/spec/agent/langgraph-nodes.md` — sửa: thêm mục 6.1 "Field-level: từng node đọc field nào, ghi
  field nào", bảng 10 node × (đọc `state.*`, có gọi LLM không, ghi field nào, routing tiếp theo), đối
  chiếu trực tiếp `src/backend/app/agents/{state.py,nodes.py,routing.py,graph.py}`. Giữ nguyên bảng mô
  tả bằng lời ở mục 6 cũ, chỉ thêm ghi chú "khớp code tại thời điểm viết, git log mới là nguồn xác thực
  khi code đã đổi".

## Quyết định

- Không tạo đề xuất `docs/prd/update/`: đây là mô tả chính xác hơn hành vi hiện có của agent
  (`docs/prd/architecture.md` §3, `docs/prd/requirements.md` §1.4 FR-AGT), không thêm/bớt/đổi phạm vi,
  hành vi hay contract.
- Đặt bảng mới làm mục con (6.1) của bảng cũ (mục 6) thay vì file riêng, vì cùng thuộc "tra cứu node"
  và `README.md` đã trỏ tới đúng file này.

## Kiểm tra

- Không đổi code/contract/schema nên không chạy `validate_contract.py` hay test.
- Đối chiếu thủ công từng dòng bảng với `nodes.py` (đọc toàn bộ 673 dòng), `state.py`, `routing.py`,
  `graph.py` trong phiên làm việc.

## Còn lại / rủi ro

- Bảng field-level sẽ lệch nếu `nodes.py`/`state.py` đổi mà không cập nhật lại tài liệu; không có cơ
  chế tự động đối chiếu.
