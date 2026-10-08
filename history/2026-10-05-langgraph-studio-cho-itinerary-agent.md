# Chạy Itinerary Agent trong LangGraph Studio

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người phụ trách agent cần xem graph 12 node chạy từng bước (state sau mỗi node, sửa state rồi chạy lại từ một node) để hiểu code và debug, thay vì đọc từng file node. Công cụ dev, không đổi hành vi agent. Phục vụ FR-AGT-01..05 ở khâu phát triển.

## File thay đổi

- `src/backend/scripts/langgraph_studio.py` — thêm: `make_graph()` dựng graph bằng `build_graph`, LLM từ `build_chat_model(get_settings())`, store in-memory; tool theo `ITINERARY_DATA_MODE` (bỏ trống → `inprocess`: `build_recsys` + `build_catalog` của `main.py` bọc trong `InProcessItineraryTools`; `fixture`: 50 sản phẩm mẫu).
- `langgraph.json` — thêm: khai báo graph `itinerary` cho `langgraph dev`.
- `src/backend/README.md` — sửa: mục "Xem graph trong LangGraph Studio" (cài venv riêng, lệnh chạy, cách nhập lượt).
- `.gitignore` — sửa: bỏ qua `.venv-studio/` và `.langgraph_api/` (state cục bộ của dev server).
- `history/2026-10-05-langgraph-studio-cho-itinerary-agent.md` — thêm: entry này.

## Quyết định

- Entry đặt ở `src/backend/scripts/` (cạnh `push_prompts_to_langsmith.py`), không trong `app/agents/`: quy tắc 7 cấm `agents` import `infrastructure`, mà entry phải nối fixture client và LLM. `scripts/` nằm ngoài vùng quét của `tests/architecture`.
- Studio mặc định `inprocess` theo yêu cầu người dùng, để debug trên dữ liệu thật; chỉ áp cho script Studio. Mặc định của backend (`main.py`: `fixture` ở development/test, `disabled` nơi khác) **không đổi** vì `docs/prd/deployment-plan.md` §2 ghi hành vi đó — đổi phải qua đề xuất `docs/prd/update/`. Máy của người dùng đặt `ITINERARY_DATA_MODE=inprocess` trong `.env` (file không commit).
- `make_graph` là factory **async**, dựng engine bằng `asyncio.to_thread` (có lock): `langgraph dev` bật blockbuster, chặn `socket.connect` đồng bộ trên event loop nên `connect_weaviate` trong `build_recsys` lỗi `BlockingError` khi Studio mở graph. Không dùng `--allow-blocking` để khỏi che lời gọi chặn thật trong node.
- Engine dựng một lần theo tiến trình (cache `_CLIENTS`); không có `RecsysRefresher` nên giá/cửa sổ ngày không tự làm mới — khởi động lại `langgraph dev` để nạp catalog mới.
- Không khai báo `env` trong `langgraph.json`: nạp cả `.env` vào `os.environ` sẽ bật LangSmith ngầm, trái với `_forward_langsmith_env` trong `main.py`. `Settings` tự đọc `.env`.
- Venv riêng `.venv-studio`: `langgraph-api` 0.14 đòi `grpcio>=1.81.1`, `.venv` đang giữ `grpcio` 1.78 cho `weaviate-client` (ghi chú sẵn trong `requirements.txt`). Không đụng `.venv` của backend.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/architecture`: 8 passed.
- Gọi `make_graph()` trực tiếp, LLM thật: lượt 1 "Lên lịch 2 ngày ở Nha Trang cho 2 người lớn từ 2026-10-20" đi `intake → classify → extract → clarify → finalize` (hỏi ngân sách), 10,2 s; lượt 2 "Đổi thành 3 ngày" cùng `conversation_id` ra `compose`, `days = 3`, 12,7 s.
- `.venv-studio/bin/langgraph dev --no-browser`: `/ok` trả `{"ok":true}`, `/assistants/search` có `itinerary`; một run qua API server ra `decision = compose`. Chưa mở giao diện Studio trên trình duyệt (cần đăng nhập LangSmith).
- Lần chạy đầu bằng `.venv/bin/langgraph` lỗi `grpcio 1.78.0 ... depends on grpcio>=1.81.1` — lý do tách venv.
- Mode `inprocess` (Postgres/Weaviate local đang chạy): engine nạp 11,9 s, in `mode=inprocess`.
- Sau khi đổi factory sang async: `langgraph dev --port 2099`, mode `inprocess`, `GET /assistants/{id}/schemas` 200 (7,3 s, lần đầu có nạp engine), `/graph` 200, log không còn `BlockingError`; một run qua `/runs/wait` vẫn dừng ở `extract` timeout 30 s (lỗi treo LLM ở mục dưới).
- Lượt "Lên lịch 2 ngày ở Nha Trang cho 2 người lớn từ 2026-10-20, ngân sách 8 triệu": 3 lần `inprocess` đều dừng ở `extract` → `dead_letter` (LLM quá 30 s; đặt 150 s vẫn treo hết 150 s); 1 lần `fixture` qua đủ 8 node, 16,9 s. Gọi thẳng đúng input của `extract` bằng `with_structured_output(Extraction)`: lần không nạp engine treo quá 45 s, lần có nạp engine xong 4,1 s; lời gọi LLM ngắn khác 1,7–2,2 s; event loop không bị chặn (không trễ > 0,3 s). Kết luận: treo chập chờn ở chính lời gọi LLM của `extract`, không do mode tool.

## Còn lại / rủi ro

- Lời gọi LLM của `extract` treo chập chờn (đã thấy > 150 s), đủ để rơi `dead_letter` với timeout 30 s. Chưa tìm ra nguyên nhân (provider, model, hay timeout/retry của client OpenAI); cần đo tỉ lệ treo trên nhiều lượt trước khi sửa.
- Thời gian ở trên là một mẫu với tool fixture (gần như không tốn thời gian tool), nên ~10 s gần như toàn bộ là các node LLM. Đây là gợi ý cho việc đo latency theo node, chưa phải số đo.
- Lượt đầu không được tự đặt `conversation_id` (intake trả `CONVERSATION_NOT_FOUND`); đã ghi trong docstring và README.
- `langgraph-api` 0.14.3 báo đã sang "Critical support"; nâng cấp khi cần.
