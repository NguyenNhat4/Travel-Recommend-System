# Thêm tool "sản phẩm tương tự" cho Itinerary Agent khi người dùng đổi món

- Ngày: 2026-09-28
- Người đề xuất: tqanh123 / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: tqanh123 (người dùng), 2026-09-29 (PRD áp dụng cùng ngày, sau đề xuất `2026-09-28-agent-goi-engine-trong-tien-trinh.md`; source: history `2026-09-29-tool-similar-cho-agent.md`)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-02, FR-AGT-05), `docs/prd/architecture.md` §3 (sơ đồ trạng thái, Tiêu chuẩn Grounding)
- Mã FR/NFR: FR-AGT-02, FR-AGT-05, FR-SRC-04, FR-AGT-04, NFR-REL-01, NFR-PERF-03

## Lý do

- **Lượt đổi món hiện chỉ tìm lại được.** FR-AGT-05 cho người dùng đổi phòng hay điểm tham quan qua hội thoại. Hôm
  nay planner của agent chỉ có hai tool `search_products` và `get_recommendations`, nên lượt "đổi khách sạn khác giống cái này" chỉ tìm lại
  bằng câu truy vấn. Kết quả dễ ra lại đúng món cũ, hoặc món không giống món người dùng muốn thay.
- **Engine đã có sẵn.** `GET /products/{productId}/similar` (`getSimilarProducts`) tìm theo vector của chính sản phẩm
  gốc qua chỉ mục ANN của Weaviate (NFR-PERF-03), cùng taxonomy, loại chính nó và các sản phẩm anh em cùng cha. Đây
  cũng là loại "sản phẩm tương đồng gần nhất" mà FR-SRC-04 nhắc tới.
- **PRD chưa cho agent dùng.** FR-AGT-02 không liệt kê công cụ này, và §3 chỉ cho lấy dữ liệu sản phẩm từ
  `ToolCatalogSearch`. Thêm một tool mới cho LLM là thêm hành vi, nên cần chốt trước khi code.

## Nội dung đề xuất

### 1. `requirements.md` §1.4, FR-AGT-02

- Hiện tại: **FR-AGT-02 (Gọi công cụ nghiệp vụ - Tool Calling):** Trợ lý tương tác trực tiếp với API hệ thống thông
  qua các công cụ: tìm kiếm sản phẩm, kiểm tra lịch trống, tính toán chi phí dự kiến.
- Thay bằng: **FR-AGT-02 (Gọi công cụ nghiệp vụ - Tool Calling):** Trợ lý tương tác trực tiếp với API hệ thống thông
  qua các công cụ: tìm kiếm sản phẩm, tìm sản phẩm tương tự một sản phẩm đã đề xuất (khi đổi món, FR-AGT-05), kiểm
  tra lịch trống, tính toán chi phí dự kiến.
- Nếu đề xuất `2026-09-28-agent-goi-engine-trong-tien-trinh.md` được áp dụng trước thì "hiện tại" là câu mới của đề
  xuất đó; chèn cùng cụm "tìm sản phẩm tương tự một sản phẩm đã đề xuất (khi đổi món, FR-AGT-05)" ngay sau
  "gợi ý cá nhân hoá".

### 2. `requirements.md` §1.4, FR-AGT-05

- Hiện tại: **FR-AGT-05 (Điều chỉnh linh hoạt):** Người dùng có thể yêu cầu đổi phòng, đổi điểm tham quan hoặc rút
  ngắn/kéo dài số ngày trong lịch trình qua hội thoại tiếp theo.
- Thay bằng: giữ câu trên, thêm: "Khi người dùng muốn đổi một sản phẩm đã hiển thị mà không nêu tên thay thế, trợ lý
  có thể tìm sản phẩm tương tự sản phẩm đó: sản phẩm gốc chỉ lấy từ lịch trình lượt trước, kết quả cùng loại
  (taxonomy)."

### 3. `architecture.md` §3, sơ đồ trạng thái (chỉ đổi nhãn chuyển; id `ToolCatalogSearch` giữ nguyên)

- Hiện tại: `SearchCandidates --> ToolCatalogSearch: Gọi Tool tìm kiếm phòng & tour thật`
- Thay bằng: `SearchCandidates --> ToolCatalogSearch: Gọi Tool tìm kiếm phòng & tour thật (và Similar khi đổi món)`

### 4. `architecture.md` §3, Tiêu chuẩn Grounding, gạch đầu dòng đầu

- Hiện tại: "…Mọi thông tin về `productId`, `title`, `price`, `imageUrl` bắt buộc phải được lấy nguyên trạng từ kết
  quả trả về của `ToolCatalogSearch`."
- Thay bằng: "…Mọi thông tin về `productId`, `title`, `price`, `imageUrl` bắt buộc phải được lấy nguyên trạng từ kết
  quả trả về của công cụ truy xuất (`ToolCatalogSearch`): Search, Recommendation, hoặc Similar (`getSimilarProducts`)
  khi đổi một sản phẩm đã hiển thị."

### 5. Quy tắc của tool (ghi vào spec itinerary, không đưa vào PRD)

- **Tên và nguồn:** `get_similar_products(productId, limit)`, schema lấy từ `GET /products/{productId}/similar`. Chỉ
  `same_taxonomy`. Route cũ `/similar/{id}` không đổi.
- **Sản phẩm gốc:** chỉ nhận `productId` có trong `previous_selection` (danh sách đã hiển thị lượt trước, lưu phía
  server). Id khác bị loại; log không ghi id.
- **Chỉ mời khi có sản phẩm gốc:** tool và gợi ý prompt chỉ đưa cho LLM khi lượt có `previous_selection`. Lượt đầu giữ
  nguyên bộ tool và prompt như hôm nay.
- **Giới hạn:** tối đa 2 lời gọi similar mỗi lượt, khử trùng sản phẩm gốc; `limit` do server cố định. Vẫn trong trần
  5 lời gọi mỗi lượt; khi phải chèn lời gọi gợi ý mà đã đủ 5 thì bỏ bớt một lời gọi similar.
- **Lưới an toàn:** plan luôn giữ một lời gọi `search_products` cho loại đang đổi. Plan chỉ còn sản phẩm gốc bịa thì
  thay bằng một lời gọi search theo điểm đến.
- **Lỗi mềm:** `PRODUCT_NOT_FOUND` (404) và `PRODUCT_NOT_INDEXED` (409) nghĩa là "không có phương án", luôn mềm.
  `SEARCH_UNAVAILABLE` (503) và timeout mềm nếu có lời gọi search đã trả dữ liệu. Nhờ vậy similar hỏng không đẩy lượt
  đổi món sang thử lại rồi `FALLBACK`.
- **Kết quả:** gắn nhãn `ItemSource.SEARCH`, không thêm giá trị enum. Kết quả lệch điểm đến bị bỏ qua. Tên, giá,
  `productId` vẫn lấy nguyên từ kết quả engine (FR-AGT-04, NFR-REL-01 100%).
- **Contract:** không đổi schema. Chỉ khai báo thêm `400`, `409`, `503` cho `/products/{productId}/similar` (route đã
  trả các mã này nhưng contract mới khai 200/404/500), tăng minor version.

## Thay đổi source sau khi chốt

1. **PRD trước:** sửa `docs/prd/requirements.md` và `docs/prd/architecture.md` theo mục 1–4. Đổi trạng thái đề xuất
   sang `đã áp dụng`, ghi người chốt và ngày, `git mv` sang `docs/prd/update-archive/`, ghi entry `history/`.
2. **Contract:** `src/shared/contracts/paths/catalog.yaml` (400/409/503); tăng minor version ở
   `src/shared/contracts/openapi.yaml` và `src/backend/app/main.py`; chạy `validate_contract.py`, sinh lại
   `src/frontend/src/types/api.gen.ts`.
3. **Tool contract và port:** `src/backend/app/application/itinerary/tool_contracts.py` (thêm `get_similar_products`,
   nhận tham số `path`), `src/backend/app/application/ports/itinerary_tools.py` (thêm `SimilarProductsPort`).
4. **Adapter:** `src/backend/app/application/itinerary/engine_tools.py` (in-process),
   `src/backend/app/infrastructure/clients/itinerary_http_clients.py` (HTTP, không gửi Authorization),
   `src/backend/app/infrastructure/clients/itinerary_fixture_clients.py` (cùng taxonomy, id lạ trả 404).
5. **Gateway:** `src/backend/app/agents/tools/itinerary_gateway.py` dispatch theo bảng handler; tool chưa cấu hình trả
   `TOOL_NOT_ALLOWED`.
6. **Nối dây:** `src/backend/app/main.py`, `src/evaluation/agent/golden.py`, `src/evaluation/agent/cli.py`.
7. **Planner:** `src/backend/app/agents/steps/tool_planning.py`, `src/backend/app/agents/steps/prompts.py` (quy tắc
   mục 5).
8. **Retrieval và đánh giá:** `src/backend/app/application/itinerary/retrieval.py` (bỏ kết quả lệch điểm đến),
   `src/backend/app/agents/steps/evaluation.py` (lỗi mềm).
9. **Test:** `src/backend/tests/unit/agents/test_itinerary_tools.py`, `test_itinerary_runtime.py`, test adapter
   in-process và fixture, `src/backend/tests/unit/application/test_itinerary_retrieval.py` (mới),
   `src/backend/tests/contract/test_catalog_contract.py`; thêm một case đổi món vào
   `src/evaluation/datasets/itinerary_agent_golden.yaml`.
10. **Spec:** `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (mục tool mới, nguồn grounding),
    `docs/spec/hop-dong-tich-hop-search-recommendation.md` (agent dùng similar `same_taxonomy` khi đổi món),
    `docs/spec/agent/langgraph-nodes.md`, `state-fields.md`, `working-context.md`.

## Câu hỏi mở

Khi chốt (2026-09-29), người chốt không chọn phương án riêng cho ba câu dưới, nên áp dụng mặc định của đề xuất: câu 1 và 2 để sau (không làm trong đợt này); câu 3 thêm tool theo cấu trúc `tool_contracts.py` hiện tại, hướng (a)/(b) vẫn là việc dang dở của history `2026-09-23-tai-thiet-lap-cau-truc-backend.md`.

1. Compose hiện chọn sản phẩm theo luật cố định (chỗ ở: rẻ nhất trước, `domain/itinerary/planning.py`), nên kết quả
   similar vào tập ứng viên nhưng chưa chắc thay được món đang đổi. Có muốn compose ưu tiên kết quả similar cho đúng ô đang đổi không? Đề xuất
   này chưa làm; case golden đổi món sẽ đo mức ảnh hưởng.
2. Về sau có thêm tham số `destination` hoặc chế độ `cross_taxonomy` cho similar không? Đề xuất này chỉ làm
   `same_taxonomy`.
3. Thêm tool vào `tool_contracts.py` nối dài chỗ lệch đang mở về vị trí code kiểm contract của itinerary (history
   `2026-09-23-tai-thiet-lap-cau-truc-backend.md`, hướng (a)/(b)). Chọn hướng trước, hay thêm theo cấu trúc hiện tại?
