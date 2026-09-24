# Thêm `agents/steps/` vào cây thư mục backend trong PRD

- Ngày: 2026-09-23
- Người đề xuất: người dùng (yêu cầu dọn `nodes.py`) / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-09-23
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §2 (cây thư mục `src/backend/app/`)
- Mã FR/NFR: FR-AGT-01…05 (không đổi hành vi, chỉ đổi chỗ đặt code)

## Lý do

`src/backend/app/agents/nodes.py` đã lên 709 dòng, gộp system prompt, bảng câu chữ song ngữ,
mười node và toàn bộ helper `_x` của chúng — đọc và sửa đều dễ chạm nhầm. Người dùng yêu cầu file
`nodes.py` chỉ còn các hàm node, mỗi node một docstring, và gom helper vào một thư mục.

Sau khi tách, `agents/` có thêm thư mục `steps/`, trong khi PRD §2 mô tả `agents/` là
"LangGraph: state, graph, node và tools/". Code không lệch ý đồ kiến trúc (vẫn chỉ là lớp agent,
vẫn chỉ gọi port của `application`), nhưng dòng mô tả trong PRD không còn liệt kê đủ.

## Nội dung đề xuất

`docs/prd/architecture.md` §2, dòng trong cây thư mục:

- Hiện tại: `├── agents/                  # LangGraph: state, graph, node và tools/; hiện thực port planner itinerary`
- Thay bằng: `├── agents/                  # LangGraph: state, graph, node, steps/ (luật của từng bước) và tools/; hiện thực port planner itinerary`

## Thay đổi source sau khi chốt

Đã thực hiện theo yêu cầu trực tiếp của người dùng, chờ chốt để hợp thức hoá dòng mô tả PRD:

- `src/backend/app/agents/nodes.py` — chỉ còn 15 hàm node (10 node, 5 node có thêm bản `_async`).
- `src/backend/app/agents/steps/` — `prompts`, `messages`, `classification`, `tool_planning`,
  `evaluation`, `conversation`, `composition`, `failures`, `validation`.
- `docs/spec/agent/working-context.md`, `state-fields.md`, `langgraph-nodes.md` — trỏ sang `steps/`.

Nếu bị từ chối: gộp `steps/` ngược lại thành các module phẳng trong `agents/` hoặc trả về một file.
