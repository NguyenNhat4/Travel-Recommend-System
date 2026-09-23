# Thêm sơ đồ mermaid cho LangGraph itinerary agent

- Ngày: 2026-09-23
- Tác giả: nhatutc2@gmail.com / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng cần sơ đồ đầy đủ dạng mermaid cho graph mười node của itinerary agent để dễ xem trực quan, thay vì chỉ có sơ đồ ASCII trong `docs/spec/agent/langgraph-nodes.md`.

## File thay đổi

- `docs/spec/agent/langgraph-nodes.md` — sửa: thêm mục 3.1 "Sơ đồ mermaid" ngay sau sơ đồ ASCII ở mục 3, vẽ lại đúng các cạnh và điều kiện routing hiện có trong `src/backend/app/agents/graph.py` và `src/backend/app/agents/routing.py`, đánh dấu bốn node có gọi LLM (`classify`, `tool`, `converse`, `clarify`).

## Quyết định

- Không đổi nội dung sơ đồ ASCII hiện có (mục 3), chỉ bổ sung bản mermaid bên dưới — đúng lựa chọn người dùng đã chọn (thêm bên cạnh, không thay thế).
- Nội dung sơ đồ chỉ mô tả lại hành vi code hiện tại, không thêm/bớt route hay node nào — không phải thay đổi lệch PRD nên không cần đề xuất trong `docs/prd/update/`.
- Đối chiếu trực tiếp `graph.py` (cạnh cố định + `add_conditional_edges`) và `routing.py` (`route_after_classify/evaluate/retry`) để đảm bảo mermaid khớp code, không suy đoán từ tài liệu cũ.
- Theo yêu cầu tiếp theo của người dùng, bỏ subgraph theo giai đoạn và nhãn text trên từng cạnh (điều kiện route), chỉ giữ node và mũi tên thẳng để dễ nhìn; bốn node gọi LLM vẫn giữ style viền đậm qua `classDef llm`. Đoạn văn giải thích ngay trên code block giữ nguyên để không mất thông tin điều kiện route.

## Kiểm tra

- Không có thay đổi contract/schema/seed nên không cần chạy `validate_contract.py` hay `db/verify.sql`.
- Kiểm tra thủ công cú pháp mermaid bằng mắt (subgraph, classDef, nhãn cạnh có escape đúng); chưa render qua công cụ mermaid CLI.

## Còn lại / rủi ro

- Sơ đồ mermaid là bản chụp tại thời điểm viết; khi `graph.py`/`routing.py` đổi cạnh hoặc thêm node phải cập nhật lại cả sơ đồ ASCII lẫn mermaid trong cùng thay đổi.
