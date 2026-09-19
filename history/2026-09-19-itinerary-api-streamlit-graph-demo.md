# Nối Streamlit với FastAPI và hiển thị LangGraph runtime

- Ngày: 2026-09-19
- Tác giả: người dùng / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, contract, evaluation, docs

## Mục tiêu

Chuyển UI Streamlit từ gọi graph trực tiếp sang gọi FastAPI, dùng graph agent hiện có, dùng fixture sản phẩm cho tool trong môi trường development/test và hiển thị node thực tế đi qua. Bắt buộc Agent hỏi lại trước khi lập kế hoạch nếu thiếu `destination` hoặc `days`; `context.language` được backend dùng và mặc định tiếng Việt.

## File thay đổi

- `.env.example` — sửa: thêm cấu hình data mode, upstream, timeout, TTL conversation và URL API cho UI.
- `src/backend/app/agents/nodes.py` — sửa: dùng/lưu language, giữ intent nhiều lượt và trả câu hỏi thiếu destination/days theo ngôn ngữ.
- `src/backend/app/agents/state.py` — sửa: thêm language vào graph state.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: nối runtime dependencies, thêm SSE stream và status endpoint.
- `src/backend/app/application/itinerary/retrieval.py` — sửa: hydrate/filter ứng viên có giới hạn song song và giữ grounding nguồn.
- `src/backend/app/core/config.py` — sửa: thêm cấu hình runtime itinerary.
- `src/backend/app/domain/itinerary/planning.py` — sửa: dựng và kiểm tra kế hoạch xác định, tính tổng an toàn, giữ grounding.
- `src/backend/app/domain/itinerary/schemas.py` — sửa: khai báo context language vi/en, mặc định vi.
- `src/backend/app/infrastructure/clients/itinerary_conversation_store.py` — thêm: store conversation theo owner có TTL.
- `src/backend/app/infrastructure/clients/itinerary_fixture_clients.py` — thêm: adapter Search/Recommendation/Catalog từ fixture 50 sản phẩm.
- `src/backend/app/infrastructure/clients/itinerary_http_clients.py` — thêm: adapter HTTP cho upstream thật.
- `src/backend/app/main.py` — sửa: inject store/data adapter theo môi trường và chuẩn hóa validation error.
- `src/evaluation/agent/README.md` — sửa: hướng dẫn chạy FastAPI cùng Streamlit và mô tả clarification/language.
- `src/evaluation/agent/streamlit_app.py` — sửa: chỉ gọi API/SSE, chat nhiều lượt và visualize topology/node trace.
- `src/evaluation/requirements.txt` — sửa: khai báo httpx cho API client.
- `src/shared/contracts/openapi.yaml` — sửa: nâng contract lên 1.4.0 và công bố stream/status.
- `src/shared/contracts/paths/itinerary-agent.yaml` — sửa: định nghĩa endpoint thường, SSE và status.
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: chốt language default và schema status/stream.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: đồng bộ language, clarification gate, SSE và mock-mode boundary.
- `docs/spec/recsys-internship-handbook-v3-vi.md` — sửa: đồng bộ flow clarification, conversation scope và kiến trúc demo qua API.

## Quyết định

- OpenAPI 1.4.0 là nguồn sự thật; Streamlit không import graph hoặc mock port.
- `destination` và `days` là điều kiện để gọi tool, không phải field bắt buộc ngay ở request đầu; thiếu thì Agent hỏi tiếp và giữ conversation.
- Language ưu tiên request tường minh, sau đó conversation, cuối cùng `vi`; MVP không tự nhận diện ngôn ngữ.
- SSE chỉ phát topology, sự kiện node đã làm sạch và response công khai; không phát prompt, token, credential hoặc raw state.
- Fixture chỉ mặc định ở development/test. Production không tự dùng mock và phải cấu hình HTTP upstream.

## Kiểm tra

- `python3 -m py_compile ...`: pass cho route, Streamlit, planning và retrieval.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: pass 63 schema, 50 grounded products, 50 fixture và các negative checks.
- `_topology(build_graph())`: pass, trả 9 node và các cạnh điều kiện/thường của graph hiện hành.
- Streamlit `AppTest`: pass, không có exception, có title và chat input.
- Uvicorn startup: pass, application startup hoàn tất với fixture development; sandbox không cho mở socket từ process kiểm tra thứ hai nên chưa smoke HTTP bằng curl.
- Unit test clarification riêng: assertion pass (`ok`), nhưng process unittest không tự thoát trước timeout 30 giây sau khi test kết thúc; xem rủi ro bên dưới.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Chưa coi smoke test provider thật hoặc browser thật là đã chạy; demo cần key/model hợp lệ và hai process FastAPI/Streamlit.
- Runner `unittest` với LangGraph đã in `ok` nhưng còn giữ thread/task lúc teardown trong môi trường hiện tại; cần điều tra riêng để bộ test kết thúc sạch, không dùng kết quả timeout làm bằng chứng toàn suite pass.
- Fixture chứng minh tích hợp local và grounding vào 50 sản phẩm, không chứng minh giá, availability hoặc latency của upstream thật.
