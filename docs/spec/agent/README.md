# Tài liệu Itinerary Agent

Tài liệu về agent lập lịch trình (LangGraph trong `src/backend/app/agents`) và bộ đánh giá qua Streamlit (`src/evaluation/agent`).

Nếu cần sửa, tune hoặc đánh giá Agent, bắt đầu từ [working-context.md](working-context.md). File này
chỉ dẫn thứ tự đọc tối thiểu và chọn thêm tài liệu/source theo đúng loại task để tránh nạp context thừa.

| File | Nội dung |
|---|---|
| [working-context.md](working-context.md) | Context tối thiểu, bản đồ module và nhánh đọc riêng cho tune/eval/debug |
| [langgraph-nodes.md](langgraph-nodes.md) | Vì sao graph chia thành mười node, vì sao mọi nhánh qua `finalize`, cách đọc bảng trace |
| [state-fields.md](state-fields.md) | Tra theo từng field của `AgentState`: node nào ghi, node nào đọc, dùng để làm gì |
| [field-review.md](field-review.md) | Review field của request/response và `AgentState`: đề xuất giữ, bỏ, gộp — đã chốt và áp dụng 2026-09-28 |
| [response-and-errors.md](response-and-errors.md) | `status` so với `error.code`, luồng sau khi nhập giá trị không hợp lệ |
| [golden-run.md](golden-run.md) | Chạy bộ golden: chuẩn bị Postgres/backend, các cờ của runner, đọc kết quả, luật chấm, ngưỡng kết luận, lỗi thường gặp |
| [golden-dataset-how-to-add-more-case.md](golden-dataset-how-to-add-more-case.md) | Cấu trúc bộ golden 14 case (mỗi category một case khó nhất), các khoá `expect`, cách thêm case và xử lý khi case fail |
| [presentation-slides.html](presentation-slides.html) | Bộ 14 slide giới thiệu agent (mở bằng trình duyệt, phím ←/→); số liệu golden ngày 2026-09-24 |
| [presentation-script.md](presentation-script.md) | Kịch bản nói theo từng slide, phần demo trực tiếp và câu hỏi dễ gặp |

## Chạy demo

Chạy từ repo root bằng môi trường có dependencies Backend và Streamlit:

```bash
.venv/bin/python -m pip install -r src/backend/requirements.txt -r src/evaluation/requirements.txt
.venv/bin/uvicorn src.backend.app.main:app --reload --port 8000
ASSISTANT_API_BASE_URL=http://127.0.0.1:8000/api/v1 .venv/bin/python -m streamlit run src/evaluation/agent/streamlit_app.py --server.port 8502
```

Cấu hình provider/key/model trong `.env` theo Backend README. UI chat chỉ gọi FastAPI và nhận trace LangGraph an toàn bằng SSE; không import graph trong process Streamlit. FastAPI dựng **một** client LLM dùng chung trong `lifespan` (`infrastructure/llm/build_chat_model`) và tiêm vào graph qua `app.state.itinerary_llm`; provider chọn theo key có mặt, thứ tự Gemini → OpenAI → Anthropic. `ITINERARY_USE_LLM=false` thì không client nào được dựng: app vẫn khởi động không cần API key, `/assistant/status` trả `llmMode=disabled` và mọi request itinerary trả 503 `LLM_UNAVAILABLE`. Ở development, `ITINERARY_DATA_MODE=fixture` dùng 50 sản phẩm trong fixture chung; chạy với dữ liệu thật (Postgres đã seed, Weaviate, Cohere) thì đặt `ITINERARY_DATA_MODE=inprocess` để tool gọi engine Search/Recommendation trong cùng tiến trình (Backend README mục "LLM của itinerary agent"). Nút gửi có thể phát sinh request/chi phí LLM; không hiển thị hoặc lưu key/JWT.

Demo yêu cầu `destination` và `days`. Nếu thiếu, backend trả `NEEDS_CLARIFICATION`, lưu phần intent đã biết cùng lịch sử chat user/assistant gần đây theo `conversationId` và chưa gọi tool. Lịch sử được giới hạn ở 20 message/8.000 ký tự và chỉ dùng để hiểu tham chiếu; giá/availability vẫn tải lại từ tool. `context.language` hỗ trợ `vi`/`en`; khi vắng mặt backend mặc định tiếng Việt và lưu lựa chọn theo conversation. Store hiện tại nằm trong memory của process nên restart backend sẽ mất conversation.

Timeout LLM của graph lấy từ `ITINERARY_LLM_TIMEOUT_SECONDS`, áp dụng cho cả `classify`, `extract`, chọn điểm đến trong `tool`, `clarify` và `converse`; timeout tool lấy từ `ITINERARY_TOOL_TIMEOUT_SECONDS`. `.env.example` đặt 30 giây và 1 giây để model thật có thời gian phản hồi khi demo. Đây là cấu hình đánh giá offline và **vượt** ngân sách của spec §7.2 (classify 2 giây, composition 3 giây, toàn request mục tiêu 5 giây), nên không dùng số đo ở chế độ này làm bằng chứng đạt SLA. `ITINERARY_LLM_MODEL` và `ITINERARY_USE_LLM` nay **được** `Settings` đọc; đây là biến model duy nhất (`MODEL_NAME` đã bỏ, 2026-10-05); bỏ trống thì mỗi provider dùng mặc định của mình (OpenAI `gpt-4o-mini`). Nhiệt độ của agent lấy từ `ITINERARY_LLM_TEMPERATURE` (mặc định 0), không dùng chung `LLM_TEMPERATURE`.

## Chạy đánh giá tự động (golden dataset)

Hướng dẫn đầy đủ: [golden-run.md](golden-run.md). Bộ 76 case cố định, chấm tự động theo `docs/prd/test-plan.md` §2.4 (Grounding Rate, Structured Output
Integrity, Tool Calling Accuracy). Chi tiết luật chấm: [golden-run.md](golden-run.md) mục 4. Cần Postgres đã seed và backend đã nạp RecSys, chạy `ITINERARY_DATA_MODE=inprocess`
(hoặc `http`, không để `fixture`):

```bash
docker compose up -d --wait postgres
ITINERARY_DATA_MODE=inprocess .venv/bin/uvicorn src.backend.app.main:app --port 8000 &
.venv/bin/python -m src.evaluation.agent.golden
```

Runner dựng graph trong tiến trình của nó và luôn gọi Search/Recommendation của backend qua HTTP
(`ItineraryHttpClients`, `--api-base-url`), bất kể mode của backend; mode đó chỉ quyết định `productCount` trong biên
bản (golden-run.md). Staging/production chạy `ITINERARY_DATA_MODE=inprocess`, nên golden không đo đường gọi engine
trong tiến trình; hai đường được đối chiếu output bằng test parity trong `src/backend/tests`.

Ghi `src/evaluation/reports/eval-YYYY-MM-DD-golden.md` (commit được) và `.json` cùng tên (gitignored).
`--only G-051,G-062` chạy một phần; `--sweep` thêm một lượt cho mọi điểm đến thật hiện có trong catalog;
`--repeat N` chạy lại để soi độ ổn định của bước `classify`; `--trace-project <tên>` gửi trace từng
lượt lên LangSmith project đó (key lấy từ `.env`), tên trace dạng `G-059#3 <câu nhập>`, tag `golden`,
id case và category. Runner không qua `lifespan` nên không bật cờ này thì không có trace nào.

## Đọc input/output từng node bằng LangSmith

Bảng trace trong Streamlit chỉ cho biết node nào đã chạy và mất bao lâu; nó **không** hiển thị state, prompt hay payload nội bộ. Muốn xem input/output thật của từng node thì bật LangSmith trong `.env` (`LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY`) rồi chạy demo như thường. Lưu ý: bật là gửi prompt và dữ liệu người dùng lên `LANGSMITH_ENDPOINT`, chỉ dùng ở môi trường dev cá nhân.

Mỗi lượt sinh ra một trace **đặt tên theo chính câu bạn gõ**, nên tìm lại đúng lượt vừa chạy trong danh sách là được ngay:

```text
đi Nha Trang 2 ngày            ← trace gốc, metadata: request_id, conversation_id, transport, run_id
  intake → intake_node
  classify → classify_node     ← run con là lời gọi LLM thật (chỉ phân luồng)
  extract → extract_node       ← trích intent
  tool
  evaluate → evaluate_node
  compose → compose_node
  finalize → finalize_node
```

Cách đọc:

- **Mở run ở tầng ngoài** (`classify`, `compose`...) để xem input/output của node. `input` là toàn bộ state tại thời điểm đó; `output` chỉ là **phần node đó thay đổi**, nên nhìn output là biết ngay node vừa làm gì.
- **Run con cùng tên hàm** (`classify_node`) là lớp bọc sync/async, nội dung trùng với run cha. Dưới nó mới là lời gọi model thật khi node có dùng LLM.
- `route_after_classify`, `route_after_extract` và `route_after_evaluate` là hàm chọn nhánh, không phải node; bỏ qua khi đọc.
- **Lọc theo `request_id`** để nối trace với log backend — mọi dòng log của lượt đó đều ghi `requestId=`. Metadata này có ở mọi run con, nên lọc được tới từng node.

`transport` trong metadata cho biết lượt đó đi đường nào: `sse` là Streamlit, `json` là gọi thẳng `POST /assistant/itineraries`.
