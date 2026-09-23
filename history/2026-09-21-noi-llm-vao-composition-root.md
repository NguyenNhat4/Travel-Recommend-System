# Nối LLM của itinerary agent vào composition root

- Ngày: 2026-09-21
- Tác giả: Nguyễn Minh Nhật / Claude Opus 5
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, contract, docs

## Mục tiêu

Đánh giá code API chat agent phát hiện `app.state.itinerary_llm` **chưa bao giờ** được gán trong
`main.py`. Route đọc nó bằng `getattr(..., None)` (`assistant.py:38`) nên production luôn truyền
`llm=None` xuống graph, và mọi node rơi vào nhánh dự phòng `(llm or get_llm())` — 6 chỗ trong
`nodes.py`. Hệ quả: mỗi request dựng mới 2–3 client LangChain kèm bắt tay TCP/TLS riêng;
`ITINERARY_USE_LLM` và `ITINERARY_LLM_MODEL` là biến chết; `agents/llm.py` tự đọc `.env` rồi
`os.environ.setdefault` cho cả process lúc import, trái ARCHITECTURE.md §5 và §12.

## File thay đổi

- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: thêm field optional `llmMode`
  (enum `live`/`disabled`/`unavailable`) vào `AssistantStatus`; không đụng `required` và không đổi
  nghĩa `status`. Bundle `openapi.yaml` dùng `$ref` nên không cần sinh lại.
- `src/backend/app/core/config.py` — sửa: thêm `gemini_api_key`, `anthropic_api_key`,
  `itinerary_use_llm`, `itinerary_llm_model`, `itinerary_llm_temperature`; đổi `env_file` sang
  đường dẫn tuyệt đối tới `.env` ở gốc repo.
- `src/backend/app/infrastructure/llm/client.py` — sửa: thay `get_llm()` OpenAI-only (không ai
  import) bằng `build_chat_model(settings)` chọn provider Gemini → OpenAI → Anthropic.
- `src/backend/app/infrastructure/llm/__init__.py` — sửa: export `build_chat_model`, `LlmMode`.
- `src/backend/app/agents/llm.py` — sửa: xoá `_load_local_env()` và lời gọi lúc import; `get_llm`
  còn lại là lớp mỏng bọc `build_chat_model(get_settings())`.
- `src/backend/app/main.py` — sửa: dựng client trong `lifespan`, gán `app.state.itinerary_llm` và
  `app.state.itinerary_llm_mode`, bọc `try/except` để thiếu key không làm sập khởi động.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: `/assistant/status` trả thêm `llmMode`.
- `src/backend/app/agents/cli.py` — sửa: `run_itinerary` truyền `llm=` tường minh thay vì dựa vào
  nhánh dự phòng và side effect của `_load_local_env()`.
- `src/backend/tests/unit/test_llm_factory.py` — thêm: 7 test cho `build_chat_model`.
- `src/backend/tests/unit/test_backend_wiring.py` — sửa: thêm 3 test cho lifespan (disabled,
  unavailable, live + cùng một client qua nhiều `_runtime()`).
- `src/backend/tests/contract/test_assistant_contract.py` — sửa: thêm test `llmMode` hợp lệ với
  `AssistantStatus` và test 503 `LLM_UNAVAILABLE` khi tắt LLM; `post()` nhận `llm=None` thật sự.
- `.env.example` — sửa: gộp khối cấu hình bị lặp nguyên văn hai lần (dấu vết merge cũ), thêm
  `GEMINI_API_KEY`/`ANTHROPIC_API_KEY`/`ITINERARY_LLM_TEMPERATURE`, ghi rõ nghĩa của
  `ITINERARY_USE_LLM`.
- `docs/agent/README.md` — sửa: mô tả lại đường dựng LLM; bỏ câu "`ITINERARY_LLM_MODEL` không được
  `Settings` đọc".
- `docs/agent/evaluation-plan.md` — sửa: cập nhật hai chỗ nói `MODEL_NAME` là model thực tế; thêm
  `llmMode` vào bảng chứng cứ.
- `src/backend/README.md` — sửa: thêm mục "LLM của itinerary agent".

## Quyết định

- **Giữ đa provider nhưng chuyển vào `infrastructure/`.** ARCHITECTURE.md §5 ("chỉ composition root
  được quyền nối implementation") và §12 ("đặt SDK trong infrastructure") không cho `agents/` đọc env
  và dựng SDK. `docs/agent/README.md` đã ghi hành vi đa provider nên không thu về OpenAI-only.
- **`ITINERARY_USE_LLM=false` = không dựng client, request trả 503 `LLM_UNAVAILABLE`.** Node
  `classify` không có đường rule-based nào (mọi trích xuất intent đều qua LLM), nên "chạy không cần
  LLM" chỉ có thể nghĩa là hỏng có kiểm soát, đúng bảng lỗi spec §5.9. Viết bộ tách intent bằng luật
  là feature riêng, không gộp vào bản sửa này.
- **`itinerary_llm_temperature` là field mới, không tái dùng `llm_temperature`** (đang là 0.7): mọi
  lời gọi của agent là structured output hoặc tool calling, và `agents/llm.py` cũ hardcode 0.0. Tái
  dùng sẽ âm thầm đổi hành vi agent.
- **Lifespan không được raise khi thiếu API key**, theo đúng mẫu `try/except` quanh `build_recsys`:
  contract test chạy lifespan thật rồi mới override `app.state.itinerary_llm`.
- **Route vẫn đọc `app.state.itinerary_llm` tại thời điểm request**, không hoist lên startup, để
  override của test còn tác dụng.
- **`env_file` đổi sang đường dẫn tuyệt đối**: `_load_local_env()` cũ giải theo `__file__` nên chạy
  từ thư mục nào cũng thấy `.env`; `env_file=".env"` giải theo CWD nên bỏ nó đi mà không đổi sẽ làm
  mất cấu hình khi chạy CLI ngoài gốc repo.
- **Một client dùng chung cho nhiều request là an toàn**: các lớp chat model của LangChain chỉ giữ
  cấu hình bất biến cộng client httpx có connection pool, còn `with_structured_output()` và
  `bind_tools()` trả về object mới chứ không sửa model gốc.
- **`run_scenarios` trong `cli.py` để nguyên** (vẫn dùng nhánh dự phòng `get_llm()`) — nó là lệnh
  chạy kịch bản lab, không nằm trong đường phục vụ request.
- `.env.example` bị lặp nguyên văn khối đầu ở cuối file; bản lặp phía sau đặt
  `DATABASE_URL=sqlite:///./data/app.db`, ghi đè DSN Postgres ở giữa file. Đã xoá bản lặp.
- Không sửa `history/2026-09-20-evaluation-plan-for-itinerary-agent.md`; entry này thay thế phần
  "biến chết `ITINERARY_LLM_MODEL`/`ITINERARY_USE_LLM`" còn dang dở ở đó.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → PASS
  (70 schemas, all local refs, 50 grounded products, 4 itinerary statuses…).
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q src/backend/tests` → **137 passed, 2 skipped**
  (trước thay đổi: 125 passed, 2 skipped; 12 test mới, không có test cũ phải sửa nội dung kỳ vọng).
- Chạy thật `ITINERARY_USE_LLM=false uvicorn src.backend.app.main:app`:
  - log khởi động `Itinerary LLM: disabled`, app lên bình thường, không cần API key.
  - `GET /api/v1/assistant/status` → `{"status":"ready","dataMode":"fixture","llmMode":"disabled","productCount":50}`.
  - `POST /api/v1/assistant/itineraries {"message":"3 ngày Nha Trang"}` → HTTP 503,
    `error.code = "LLM_UNAVAILABLE"`, `retryable: true`.
- Chạy thật với `.env` hiện có (có `OPENAI_API_KEY`): log `Itinerary LLM: live`,
  `status.llmMode = "live"`. Không gửi request tốn phí lên provider.
- Test integration Postgres vẫn skip (không đặt `RUN_POSTGRES_INTEGRATION=1`).

## Còn lại / rủi ro

- **Chưa đo lại latency thật.** Lợi ích chính của bản sửa là bỏ 2–3 lần dựng client mỗi request,
  nhưng chưa có số đo trước/sau với provider thật. Cần đo trước khi dùng làm bằng chứng cho spec §7.2.
- Hai lỗi khác phát hiện cùng đợt đánh giá **chưa sửa**:
  1. `.env` bật LangSmith tracing, mọi prompt và dữ liệu người dùng được gửi lên
     `api.smith.langchain.com` cả khi chạy test.
  2. `InMemoryConversationStore` không giới hạn số entry và chỉ dọn entry hết hạn khi có ai load
     đúng key đó — phình bộ nhớ vô hạn trên một endpoint không xác thực.
- Ngân sách timeout vẫn không cộng lại được: `ITINERARY_REQUEST_TIMEOUT_SECONDS` mặc định 5 s trong
  khi các bước con cộng lại tới 8 s.
- Node `clarify` vẫn là code chết (`route_after_classify` ánh xạ `missing_info` → `answer`).
