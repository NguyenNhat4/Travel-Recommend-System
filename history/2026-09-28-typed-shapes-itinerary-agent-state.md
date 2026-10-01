# Thay dict[str, Any] bằng TypedDict có tên cho state/domain của Itinerary Agent

- Ngày: 2026-09-28
- Tác giả: Nguyễn Minh Nhật / Claude Opus 5.5
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent

## Mục tiêu

Người dùng nhận xét `dict[str, Any]` dùng tràn lan trong backend (chọn dòng ở
`src/backend/app/api/v1/routes/assistant.py:79`, `def _sse`). Rà lại thấy `dict[str, Any]` tập
trung nhiều nhất ở agent state, ports và domain planning của Itinerary Agent — nơi các dict này thực
ra có shape cố định (trip intent, product candidate, plan, tool call/result), không phải dữ liệu mở.
Không phải feature mới/thay đổi hành vi, nên không cần đối chiếu FR/NFR hay đề xuất PRD (AGENTS.md
§8: thay đổi không lệch phạm vi/hành vi thì không cần đề xuất) — refactor kiểu dữ liệu nội bộ, giữ
nguyên logic và không đổi API contract.

## File thay đổi

- `src/backend/app/domain/itinerary/types.py` — thêm mới: các TypedDict cho `TripIntent`, `Party`,
  `Constraints`, `Product`, `Candidates`/`Sources` (alias), `SlotItem`, `DayPlan`, `Stay`, `Plan`,
  `ProposedSlot`, `Proposal`, `ToolCall`, `ToolResult`, `ToolErrorPayload`, `PlanWarning`,
  `ToolDefinition`. Kèm docstring giải thích ranh giới: shape nào mirror contract
  (`TripIntent`/`Party`/`ItineraryPlan`/`ItineraryDay`/`ItineraryStay`/`ItinerarySlot`/
  `ItineraryWarning` trong `itinerary-agent.yaml`) nên model, shape nào (ProductSummary,
  ProductDetail, SearchResponse, RecommendationResponse, DestinationListResponse, ItineraryResponse
  envelope) cố tình để `dict[str, Any]` vì đã được `jsonschema` validate ở biên khác — model lại là
  trùng lặp nguồn sự thật (AGENTS.md §2).
- `src/backend/app/domain/itinerary/planning.py` — sửa: mọi hàm public/nội bộ dùng annotation từ
  `types.py` thay `dict[str, Any]`. Không đổi logic.
- `src/backend/app/application/itinerary/retrieval.py` — sửa: `_products`, `hydrate`, `_drop_reason`,
  `collect` dùng `ToolResult`/`Product`/`TripIntent`/`Constraints`/`Candidates`/`Sources`/
  `ToolErrorPayload`; `tools: Any` → `tools: CatalogPort`. Xoá import `Any` không còn dùng.
- `src/backend/app/application/ports/itinerary_tools.py` — sửa: `ToolError.as_dict()` trả
  `ToolErrorPayload`; `ToolExecutorPort.definitions/execute` dùng `ToolDefinition`/`ToolCall`/
  `ToolResult`. `SearchProductsPort`/`RecommendationPort`/`CatalogPort`/`ConversationStorePort` giữ
  `dict[str, Any]` có comment (payload contract-owned hoặc echo state đã serialize, application
  không được phép import `agents`).
- `src/backend/app/agents/state.py` — sửa: field của `AgentState` dùng type mới
  (`TripIntent`/`Constraints`/`Candidates`/`Sources`/`list[PlanWarning]`/`list[ToolCall]`/
  `list[ToolResult]`/`dict[str, Product]`/`dict[str, ToolErrorPayload]`/`list[Product]`). `response`
  giữ `dict[str, Any]` (envelope `ItineraryResponse`, contract-owned).
- `src/backend/app/agents/tools/itinerary_gateway.py` — sửa: `ItineraryToolGateway.definitions/
  execute` dùng `ToolDefinition`/`ToolCall`/`ToolResult`.

## Quyết định

- **Sửa một lỗi annotation có sẵn:** `AgentState.sources` trước đây khai `dict[str, dict[str, Any]]`
  nhưng giá trị thật luôn là `str` (`"search"`/`"recommendation"`, xem
  `application/itinerary/retrieval.py::collect` và cách `planning.render_proposal`/`validate_plan`
  dùng nó) — sửa thành `Sources = dict[str, str]`. Không đổi runtime, chỉ sửa annotation sai.
- **`ToolCall` dùng `id`/`name`/`args`, không phải `tool_call_id`/`name`/`arguments`:** soát lại
  `agents/steps/tool_planning.py` (dòng xây `validated.append({"id": ..., "name": ..., "args": ...})`
  và `tools.execute(call)`) trước khi chốt shape — hai khái niệm khác nhau: entry của `tool_plan`
  (input của `execute`) và entry của `tool_results` (output, có thêm `tool_call_id`/`arguments`/
  `duration_ms`). Đây là kiểu bug lặng nếu không đối chiếu code thật; ghi chú luôn trong docstring
  của từng TypedDict để không lặp lại nhầm lẫn.
- **Không model toàn bộ `ItineraryResponse`/`SearchResponse`/`RecommendationResponse`/
  `ProductDetail`/`DestinationListResponse`:** các shape này thuộc `openapi.yaml`/`schemas/*.yaml`,
  đã được `application/itinerary/contracts.py` và `tool_contracts.py` validate bằng `jsonschema` lúc
  chạy. Model lại bằng TypedDict tay là tạo bản sao thứ hai của contract, dễ lệch — đúng điều
  AGENTS.md §2 cảnh báo. Giữ `dict[str, Any]` ở các điểm này, có comment trỏ tên schema.
- **Không thêm mypy/pyright vào CI trong lần này** — người dùng chọn phương án không làm việc đó
  ngay (câu hỏi `AskUserQuestion`), tách thành việc riêng nếu cần sau.
- **Không sửa `agents/steps/*.py`, `agents/nodes.py`:** các file này nhận `state: dict` chung chung
  và chỉ index theo key; TypedDict là dict lúc chạy nên không có gì hỏng, nhưng gõ lại type cho toàn
  bộ ~15 file `agents/steps/` là phạm vi lớn hơn nhiều so với yêu cầu — không làm trong lần này.

## Kiểm tra

- `python3 -m pytest src/backend/tests/unit/domain/test_itinerary_composition.py src/backend/tests/unit/agents/ src/backend/tests/architecture src/backend/tests/unit/application/test_hybrid_search.py src/backend/tests/contract/test_assistant_contract.py -q` → **165 passed** (baseline trước khi sửa: 40 passed trên tập con nhỏ hơn, cũng xanh).
- Không đổi contract/mock nên không chạy `validate_contract.py`.
- Không đổi schema/seed nên không chạy `db/verify.sql`.

## Còn lại / rủi ro

- `dict[str, Any]` vẫn còn ở nhiều nơi khác trong backend (ví dụ các domain khác ngoài itinerary,
  infrastructure/clients, conversation_store) — chưa đụng tới, ngoài phạm vi lần này.
- Không có type checker (mypy/pyright) chạy trong CI, nên các TypedDict mới chỉ có giá trị tài liệu +
  gợi ý IDE, chưa được một công cụ nào tự động xác nhận đúng — rủi ro annotation lệch dần theo thời
  gian nếu không có gate. Nếu muốn giá trị thực sự, cần việc riêng: thêm mypy/pyright vào CI.
- `agents/steps/*.py`, `agents/nodes.py` vẫn nhận `state: dict` không kiểu — muốn có lợi ích đầy đủ
  (IDE gợi ý đúng key tại nơi dùng) thì cần đổi các chữ ký đó sang `AgentState`, chưa làm.
