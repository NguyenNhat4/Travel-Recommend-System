# Đánh giá Itinerary Agent qua Streamlit

Chạy từ repo root bằng môi trường có dependencies Backend và Streamlit:

```bash
.venv/bin/python -m pip install -r src/backend/requirements.txt -r src/evaluation/requirements.txt
.venv/bin/uvicorn src.backend.app.main:app --reload --port 8000
ASSISTANT_API_BASE_URL=http://127.0.0.1:8000/api/v1 .venv/bin/python -m streamlit run src/evaluation/agent/streamlit_app.py --server.port 8502
```

Cấu hình provider/key/model trong `.env` theo Backend README. UI chat chỉ gọi FastAPI và nhận trace LangGraph an toàn bằng SSE; không import graph trong process Streamlit. FastAPI chạy graph thật qua `get_llm`; ở development, `ITINERARY_DATA_MODE=fixture` dùng 50 sản phẩm trong fixture chung. Nút gửi có thể phát sinh request/chi phí LLM; không hiển thị hoặc lưu key/JWT.

Demo yêu cầu `destination` và `days`. Nếu thiếu, backend trả `NEEDS_CLARIFICATION`, lưu phần intent đã biết theo `conversationId` và chưa gọi tool. `context.language` hỗ trợ `vi`/`en`; khi vắng mặt backend mặc định tiếng Việt và lưu lựa chọn theo conversation.

Runner từng case/batch và custom chat chờ tối đa 30 giây cho mỗi lời gọi LLM (classify, planner, composition), để model thật có thời gian phản hồi. Timeout tool vẫn là 1 giây. Đây là cấu hình đánh giá offline; API giữ giới hạn classify/planner 2 giây và composition 3 giây. Không dùng kết quả này làm bằng chứng đạt SLA 5 giây của API.

## Đọc bảng LangGraph execution

Bảng bên phải là trace của **một lượt gọi API qua SSE**, theo đúng thứ tự event backend phát ra. Mỗi dòng cho biết một node đã kết thúc; bảng không hiển thị raw state, prompt, token, JWT hay payload nội bộ.

| Cột | Cách đọc |
|---|---|
| `sequence` | Thứ tự event trong lượt chạy, bắt đầu từ 1. Đây không phải số thứ tự cố định của node trong mọi luồng. |
| `nodeId` | Tên node LangGraph vừa hoàn tất. Node không đi qua trong lượt hiện tại sẽ không có dòng. |
| `outcome` | Trạng thái thực thi của node. `completed` chỉ có nghĩa node đã chạy xong; kết quả nghiệp vụ cuối cùng vẫn phải xem response và validation. |
| `message` | Tóm tắt quyết định hoặc công việc node vừa làm. Ví dụ `compose` ở node `evaluate` nghĩa là dữ liệu đủ điều kiện đi tiếp tới bước soạn lịch trình; việc soạn thực sự nằm ở `answer`. |
| `durationMs` | Thời gian quan sát từ event node trước đến event hiện tại tại biên SSE, gồm thời gian chạy node và overhead cập nhật/phát state. Đây không phải CPU profile chính xác bên trong node. Giá trị tối thiểu là 1 ms. |

Ví dụ trace `intake → classify → tool → evaluate → answer → finalize` là luồng lập lịch đầy đủ:

1. Request được chuẩn hóa trong `intake`.
2. `classify` mất nhiều thời gian để gọi LLM trích xuất intent.
3. `tool` lập kế hoạch tool rồi truy xuất sản phẩm thật.
4. `evaluate` kiểm tra kết quả retrieval và quyết định `compose`.
5. `answer` gọi LLM sắp xếp các candidate đã được grounding thành lịch trình.
6. `finalize` kiểm tra schema và grounding lần cuối trước khi trả response.

Tổng các dòng trong ví dụ là `10.867 ms`, tức xấp xỉ `10,9 giây`. Con số này giải thích thời gian quan sát theo node của trace đó, nhưng không thay thế latency đầu-cuối của HTTP request và không chứng minh SLA production.

## Chín node làm gì

| Node | Trách nhiệm | Có gọi LLM/tool? | Kết quả/rẽ nhánh chính |
|---|---|---|---|
| `intake` | Chuẩn hóa message, tạo/đọc `conversationId`, khởi tạo state và nạp intent đã lưu của hội thoại. | Không gọi LLM; có thể đọc conversation store. | Luôn sang `classify`; hội thoại không tồn tại được đánh dấu lỗi để xử lý có kiểm soát. |
| `classify` | Dùng structured output để tách intent/constraints, nhận diện hội thoại chung, yêu cầu ngoài phạm vi/side effect, xung đột và các trường còn thiếu. | Có, một lời gọi LLM. | `tool` khi đủ `destination` + `days`; `answer` khi cần hội thoại/làm rõ; `dead_letter` khi request hoặc LLM lỗi. |
| `tool` | Chuẩn hóa điểm đến, để LLM lập tối đa 5 lời gọi read-only, validate arguments, gọi Search/Recommendation và hydrate ProductDetail khi cần. | Có thể gọi LLM để lập tool plan; gọi các tool read-only song song. | Luôn sang `evaluate`; lỗi được giữ trong `tool_results` để node sau quyết định retry hay dừng. |
| `evaluate` | Gom và lọc candidate theo intent/constraints, giữ nguồn grounding, loại sản phẩm không đủ căn cứ và phân loại lỗi tool. | Không. | Sang `answer`, `retry` hoặc `dead_letter`. Message có thể là `compose`, `no_results`, `fallback` hoặc `constraint_clarification`. |
| `answer` | Tạo câu hỏi/câu trả lời hội thoại, hoặc dùng LLM chọn các candidate thật để dựng lịch trình; khi không thể compose thì trả fallback/no-results có kiểm soát. | Có LLM cho hội thoại và composition; một số nhánh lỗi/no-results không cần gọi LLM. | Sang `finalize`. Không được tạo ID, tên hay giá ngoài candidate đã retrieval. |
| `clarify` | Dựng response `NEEDS_CLARIFICATION` theo rule cố định. | Không. | Sang `finalize`. Node vẫn nằm trong topology, nhưng routing hiện hành đưa trường hợp thiếu thông tin qua `answer` để LLM viết câu hỏi; vì vậy trace bình thường có thể không đi qua node này. |
| `retry` | Quyết định thử lại lỗi tool tạm thời, tối đa một lần; nếu hết lượt thì chọn fallback hoặc lỗi. | Không. | Quay lại `tool`, sang `answer` để fallback, hoặc sang `dead_letter`. |
| `dead_letter` | Chuyển lỗi auth, tool plan/argument hoặc upstream thành `ErrorResponse` chuẩn, không che lỗi thành thành công. | Không. | Sang `finalize`. |
| `finalize` | Validate `ItineraryResponse`/`ErrorResponse`, kiểm tra lại grounding và plan, tính latency, lưu conversation thành công rồi kết thúc graph. | Không gọi LLM; có thể ghi conversation store. | `END`; validation thất bại bị đổi thành `ITINERARY_VALIDATION_FAILED`. |

## Các luồng thực thi

```text
START → intake → classify
  ├─ đủ destination + days
  │    → tool → evaluate
  │       ├─ candidate hợp lệ → answer (compose) → finalize → END
  │       ├─ không có kết quả/vi phạm điều kiện → answer (no-results hoặc hỏi lại) → finalize → END
  │       ├─ lỗi tạm thời → retry → tool (tối đa một lần)
  │       └─ lỗi vĩnh viễn/auth → dead_letter → finalize → END
  ├─ chào hỏi, cảm ơn hoặc thiếu destination/days
  │    → answer (hội thoại/làm rõ, không gọi product tool) → finalize → END
  └─ request lỗi, LLM classify lỗi hoặc yêu cầu bị từ chối
       → dead_letter hoặc answer (refusal) → finalize → END
```

Các điểm cần nhớ khi đọc trace:

- Không thấy `tool` nghĩa là agent chưa truy xuất sản phẩm; thường do thiếu `destination`/`days`, hội thoại chung hoặc request bị từ chối.
- Có `retry` nghĩa là retrieval gặp lỗi tạm thời; graph chỉ cho phép retry một lần để tránh vòng lặp vô hạn.
- `answer` không đồng nghĩa luôn có `COMPLETED`: node này còn tạo `NEEDS_CLARIFICATION`, `NO_RESULTS`, `FALLBACK` hoặc response từ chối.
- Chỉ `run.completed.response` và kết quả ở `finalize` mới cho biết trạng thái API cuối cùng. Trace `completed` ở từng node không phải kết luận PASS của evaluation.
- Trace dùng fixture chỉ chứng minh luồng local và grounding vào fixture; không chứng minh availability, giá hiện tại, chất lượng Search hay latency production.

## Sinh fixture và expected bằng LLM

Chạy từ repo root, dùng provider/model/key trong `.env` như backend:

```bash
.venv/bin/python -m src.evaluation.agent.generate_fixtures
```

Script loop tuần tự từng scenario, gọi LLM chọn ID catalog và sinh request/route/tool mong đợi.
Python dựng Search/Recommendation/Detail/inventory từ `shared/mocks/itinerary-agent/products.json`,
validate bằng OpenAPI hiện hành và validate arguments tool. Không để model viết giá hoặc tạo sản phẩm mới.
Sau khi tất cả case hợp lệ, ghi `evaluation_suite.json`, giữ bản cũ tại `evaluation_suite.json.bak`.
Nếu đã có backup, script yêu cầu chọn output khác hoặc tự lưu trữ backup trước; không ghi đè backup.
Case lỗi sau 3 lần thử khiến cả lần sinh dừng và suite gốc giữ nguyên. Timeout mặc định 90 giây/call.
Mỗi attempt hiện bước lỗi `provider`, `parse` hoặc `validation`. Provider chỉ hiện loại exception/HTTP status;
validation hiện đường dẫn/rule hoặc nguyên nhân đã kiểm soát, không in key/payload. Retry nhận nguyên nhân
để sửa proposal. Parser hỗ trợ JSON thuần và một khối Markdown JSON hoàn chỉnh.

```bash
# Sinh riêng vài case để kiểm tra prompt, ghi ra file riêng
.venv/bin/python -m src.evaluation.agent.generate_fixtures --ids ITIN-001 ITIN-005 --output /tmp/suite-preview.json
# Đổi model nếu cần
.venv/bin/python -m src.evaluation.agent.generate_fixtures --model gpt-4o-mini
```

`execution` được đặt trong mỗi scenario: `turns`, `checks`, `blockers`, `reviewCriteria`.
Runner ưu tiên execution trong suite khi mọi case đều có; vẫn hỗ trợ sidecar cũ nếu tồn tại.
Sinh toàn bộ suite mặc định trước khi chạy UI để không thiếu execution.
Route chấm qua `state.route` từng lượt; tool chấm calls thực tế tại port, khớp tên/số lần/arguments,
không phụ thuộc thứ tự chạy song song. Arguments runtime có thể thêm default; các field expected phải khớp chính xác,
kể cả `query`. Người review có thể bỏ `query` trong expected tool check nếu muốn chỉ chấm bộ lọc thay vì câu chữ.

Expected do LLM đề xuất vẫn cần review với mô tả case, được đánh dấu `generation.oracleReviewed=false`.
Validator chứng minh hình dạng contract và ID có nguồn, không chứng minh expected nghiệp vụ đúng.
Thiếu booking/lịch sử/điều kiện nguồn hoặc fixture injection phải giữ BLOCKED; recommendation sinh mới chỉ popular + because rỗng.
Inventory là toàn bộ catalog sample offline, không phải danh sách điểm đến của service thật.
Script gửi mô tả case và catalog sample đến provider đã cấu hình và có chi phí LLM.
Lệnh sinh không chạy agent; sau đó dùng UI để chạy graph và kiểm tra Expected/Actual.

## Chạy case và batch

- **Chạy từng case:** chọn ITIN-001–025, xem request/expected/fixture, bấm **Chạy case**. Case luôn bắt đầu với store mới. **Chạy lượt tiếp theo** giữ conversation trong cùng case, hữu ích cho ITIN-025; **Reset case** xóa tiến độ case.
- **Chạy tất cả:** chạy tuần tự 25 case, hiển thị tiến độ/bảng kết quả; lỗi một case không ngăn case tiếp theo. Chọn **Xem lại kết quả đã chạy** để xem response, graph và bảng Expected/Actual của lần chạy đó, không gọi lại model.

Graph lấy topology từ `build_graph().get_graph()`, gồm 9 node và START/END. **Chạy từng case** hiển thị sơ đồ ngay dưới nút Run trước khi chạy và cập nhật sau mỗi node được stream. Khi hoàn tất, graph hiện trực tiếp phía trên bảng Expected/Actual, không cần mở tab. Node/cạnh đã chạy tô xanh; node báo lỗi như `classify: LLM_UNAVAILABLE` tô đỏ; đường lặp retry giữ đúng thứ tự events.

Chọn **Lượt hội thoại** và **State sau node** để xem lại graph tại bước tương ứng, mặc định là bước cuối; tab **State từng node** hiển thị đúng snapshot đã chọn. Trong **Mermaid từ LangGraph**, mã sơ đồ và file `.mmd` được sinh bằng `graph.get_graph().draw_mermaid()` theo skill mastering-langgraph; UI dùng Graphviz để tô đường thực thi trực tiếp. Tool calls lấy tại port gồm cả detail/destinations. Chạy batch độc lập với case/hội thoại đang mở. Custom query vẫn là chat nhiều lượt với catalog fixture chung, dùng graph hiện tại và LLM thật.

## Dữ liệu và cách chấm

- `evaluation_suite.json`: 25 case, mô tả nghiệp vụ và fixture; script sinh bổ sung execution trong từng case. Không sửa các expected nghiệp vụ để giúp agent PASS.
- `evaluation_execution.json`: sidecar cũ được hỗ trợ nếu chưa có execution trong toàn bộ suite; file này có thể chưa tồn tại trong checkout. Expected không được đưa vào model đang được đánh giá hoặc dùng làm model output. Fixture injection còn thiếu phải BLOCKED.
- `suite_fixtures.py`: cô lập fixture từng case, giữ dữ liệu sản phẩm. Search thêm `score=1.0` khi thiếu để đáp ứng `ScoredProduct` (metadata đánh giá, không đo chất lượng ranking). Lọc theo destination/taxonomy/giá/sao/snapshot/phân trang; không giả semantic ranking theo query. ProductDetail từ projection thiếu description dùng `""`, thiếu attributes dùng `{}`, ngày dùng null; không bổ sung policy/quyền lợi/giá. `list_destinations` chỉ trả khi có fixture inventory rõ ràng, không suy inventory từ Search rỗng.
- `assertions.py`: kiểm tra response theo OpenAPI, grounding bằng retrieval thực tế cùng lượt, số/ngày, giá và đơn vị, stay/thuộc tính, hoạt động/nghỉ, tool policy, continuation và các field intent/constraints. Grounding không có sản phẩm là NOT_APPLICABLE, không phải PASS.

| Kết quả | Ý nghĩa |
| --- | --- |
| PASS | Assertion tự động đạt và tiêu chí nghiệp vụ đã được người dùng review đạt |
| FAIL | Có tiêu chí sai; xem Expected/Actual và trace |
| ERROR | Runner/model/upstream/validation lỗi; xem runtime error và các assertion riêng |
| BLOCKED | Thiếu context/fixture/handler hoặc fixture trái contract; vẫn hiện kết quả phần đã chạy và số lỗi tự động |
| REVIEW | Assertion tự động đạt, còn tiêu chí nghiệp vụ cần đọc response/trace |
| PARTIAL | Chưa chạy hết lượt hội thoại |

Trong **Review tiêu chí nghiệp vụ**, chọn kết luận và lưu nhận xét. Review không ghi đè lỗi tự động, ERROR hoặc BLOCKED. Báo cáo ghi thời điểm review; batch được tính lại summary và lưu thành report mới có `reviewOfRunId`, không sửa report cũ. Một quyết định review áp dụng cho mọi dòng REVIEW của case.

`passRate` = PASS / (PASS + FAIL + ERROR + REVIEW); BLOCKED/PARTIAL nằm riêng và không tính PASS. `automatedCheckPassRate` chỉ đo assertion tự động PASS/FAIL, không gồm review, grounding không áp dụng hay assertion bị chặn. p95 đo thời gian case (ITIN-025 gồm hai lượt), không chứng minh SLA HTTP request/production.

Report mới lưu tại `src/evaluation/reports/eval-<timestamp>-<id>.json`, không ghi đè report cũ; có model, timestamp, suite fingerprint, checks, calls, node snapshots và response. UI có nút tải JSON; không tự đọc report cũ như kết quả mới. Nếu đổi suite/execution, reset session case để tránh dùng request cũ. Batch đã chạy giữ fingerprint trong report.

## Fixture còn thiếu

Các blocker được ghi ngay trong execution/UI. Đáng chú ý: case 9 thiếu inventory điểm đến; 12–13 thiếu conversation trước; 14–16 thiếu booking/lịch sử hợp lệ; case 14 còn có `because.event=booked` ngoài enum OpenAPI. Các case 3, 7, 18, 22, 23, 25 mô tả sản phẩm/thiếu giá/injection nhưng fixture rỗng. Giữ nguyên dữ liệu và báo thiếu, không tạo catalog/booking mới để giúp case đạt.

Bộ đánh giá này chứng minh hành vi graph với LLM và fixture được cung cấp, không chứng minh Search/Recommendation thật, booking thật hoặc tồn kho. Các module demo/scenario test cũ dùng interface trước graph 9 node không còn là runner của UI này.

## Kiểm tra local

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest src.evaluation.tests.test_evaluation_runner src.evaluation.tests.test_streamlit_custom_query -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py
```

Test runner và Streamlit AppTest dùng LLM stub, graph thật và fixture; không gọi provider thật và không ghi report ra repository. AppTest không thay bằng chứng browser/model thật. Kiểm tra browser trong task triển khai đã dùng Chrome headless, UI thật và model stub; lần chạy provider thật cần báo riêng.
