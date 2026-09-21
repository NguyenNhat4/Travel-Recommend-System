# Khôi phục file và cấu hình Streamlit Agent Demo

- Ngày: 2026-09-18
- Tác giả: USER / AI Agent
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation / agent

## Mục tiêu

Sửa lỗi ModuleNotFoundError khi chạy UI Streamlit và khắc phục các file bị thiếu trong quá trình người dùng chuyển đổi nhánh/revert code để Agent Graph có thể compile thành công.

## File thay đổi

- `src/evaluation/agent/streamlit_app.py` — sửa: Cập nhật đường dẫn sys.path, kết nối UI vào Graph agent thật và gọi Fake Tools thay vì parse text.
- `src/backend/app/application/itinerary/retrieval.py` — thêm: Khôi phục file bị mất chứa hàm collect và hydrate (stubs) để graph compile.
- `src/backend/app/domain/itinerary/planning.py` — thêm: Khôi phục file bị mất chứa các hàm giả lập nghiệp vụ planning (stubs) phục vụ việc chạy graph.

## Quyết định

- Đã đưa Project Root vào sys.path ở đầu file `streamlit_app.py` để khắc phục lỗi Python Path không nhận diện `src`.
- Các file nghiệp vụ bị thiếu như `planning.py` và `retrieval.py` được tạo lại dạng stubs vì mục tiêu chính là thử nghiệm Streamlit UI (mô phỏng) thay vì thực thi 100% logic nghiệp vụ chuẩn. 

## Kiểm tra

- Đã test nội bộ lệnh `python -c "from src.backend.app.agents.graph import build_graph"` chạy thành công.
- Đã giả lập test qua `test_runner.py`, xác nhận các nhánh logic của Graph chạy tốt và trả về Status của Agent.

## Còn lại / rủi ro

- `planning.py` và `retrieval.py` hiện tại là dummy code (stubs), chỉ đáp ứng yêu cầu compile cho giao diện test UI. Khi tích hợp toàn diện cần bổ sung logic thật theo đúng schema.
- Agent LLM thực sự cần `OPENAI_API_KEY` (hoặc Gemini) trong file `.env` để không bị `503 Unavailable`.
