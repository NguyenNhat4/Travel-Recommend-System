# Đo duration node trong SSE trace

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, evaluation

## Mục tiêu

Thay giá trị `durationMs=0` cố định trong bảng LangGraph execution bằng thời gian quan sát thực tế của từng node trong luồng SSE.

## File thay đổi

- `src/backend/app/api/v1/routes/assistant.py` — sửa: đo bằng monotonic high-resolution clock giữa các state update và phát giá trị vào `node.completed`/diagnostic log.

## Quyết định

- Đo tại SSE boundary phản ánh thời gian người dùng thực sự chờ từ node trước tới node hiện tại, gồm execution và overhead phát state.
- Nếu node hoàn thành dưới độ phân giải một mili-giây, hiển thị tối thiểu 1 ms thay vì 0 để tránh hiểu nhầm là chưa đo.
- Nếu một state chứa nhiều event, event đầu nhận khoảng thời gian quan sát; event bổ sung dùng tối thiểu 1 ms vì không thể tách chính xác từ state tổng hợp.

## Kiểm tra

- Python compile cho API route: pass.
- Unit test clock xác nhận duration node tối thiểu 1 ms và tăng theo thời gian quan sát: pass.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Đây là latency quan sát tại SSE boundary, không phải CPU profiling chính xác bên trong từng node.
