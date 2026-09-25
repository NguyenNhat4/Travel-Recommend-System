# Lấy giá trị hợp lệ từ catalog và contract thay vì hardcode

- Ngày: 2026-09-20
- Tác giả: người dùng / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, docs

## Mục tiêu

LLM ở `classify` tự đoán tên điểm đến (`tphcm` → ?), còn `tool` chỉ so khớp `casefold` với danh sách catalog nên `Sài Gòn` hoặc `Ho Chi Minh` bị `UNSUPPORTED_DESTINATION` dù catalog có `TP. Hồ Chí Minh`. Yêu cầu: không hardcode alias, lấy đúng giá trị có sẵn trong catalog, gộp vào node `tool` thay vì thêm node, và áp dụng cùng nguyên tắc cho các trường bắt buộc khác: giá trị hợp lệ phải đến từ nguồn có sẵn (catalog hoặc OpenAPI) chứ không chép tay trong code.

## File thay đổi

- `src/backend/app/domain/itinerary/normalization.py` — thêm: `fold`, `match_destination` (khớp tên catalog không phân biệt dấu/hoa thường/dấu câu), `clean_interests`, `normalize_party`, `normalize_intent`. Không có bảng alias.
- `src/backend/app/domain/itinerary/planning.py` — sửa: `normalized()` bỏ dấu tiếng Việt; bỏ cận trên 7 chép tay khỏi `render_proposal` (domain không import application; cận trên do `TripIntent` kiểm tra trước khi lập kế hoạch).
- `src/backend/app/application/itinerary/contracts.py` — sửa: thêm `enum_values` và `bounds` đọc enum/khoảng giá trị từ OpenAPI đã bundle.
- `src/backend/app/agents/models.py` — sửa: thêm `DestinationChoice`; enum (`PartyType`, `Pace`, `Taxonomy`, `priceUnit`, `SlotTime`, `ActivityType`) và các khoảng giá trị (`days`, `adults`, `children`, `budget`, `starRatingMin`) lấy từ contract thay vì chép tay; bỏ trần `le=100` của số người vì contract không có.
- `src/backend/app/agents/nodes.py` — sửa: khoảng số ngày và thông báo lỗi/hỏi lại lấy từ contract (`{min_days}`/`{max_days}`); `tool_node` khớp destination với `list_destinations()`; nếu không khớp thì `_choose_destination` cho LLM chọn trong chính danh sách catalog và kiểm tra kết quả có nằm trong danh sách; dọn intent/constraints; message trace ghi `normalized <trường>`.
- `src/backend/tests/unit/agents/test_contract_derived_models.py` — thêm: enum/khoảng giá trị/thông báo của model LLM bằng đúng contract.
- `src/backend/tests/unit/agents/test_normalization.py` — thêm: test khớp không dấu, không alias cứng, tên trùng khóa, interests, party.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: test LLM chọn từ danh sách catalog, biến thể dấu/hoa không gọi LLM, LLM trả tên ngoài catalog bị từ chối, lỗi LLM là `LLM_UNAVAILABLE`, party do model đoán.
- `src/evaluation/agent/README.md` — sửa: mô tả `tool` và message trace.
- `history/2026-09-20-resolve-destination-from-catalog.md` — thêm: entry này.

## Quyết định

- Không thêm node và không thêm bảng alias: điểm đến chỉ đến từ danh sách catalog; LLM chỉ được chọn trong danh sách đó và mọi kết quả được kiểm tra `in supported` trước khi dùng (grounding). Graph giữ nguyên 9 node.
- LLM chỉ được gọi khi so khớp xác định thất bại, nên biến thể dấu/hoa thường không tốn thêm lời gọi.
- Không có kết quả khớp → `UNSUPPORTED_DESTINATION` kèm `supportedDestinations` trước khi gọi Search; LLM lỗi/timeout ở bước này → `LLM_UNAVAILABLE` (503, retryable), không kết luận sai là điểm đến không hỗ trợ.
- Listing lỗi vẫn giữ hành vi cũ: bỏ qua bước này để Search quyết định.
- Bỏ nhánh hỏi lại khi điểm đến mơ hồ: LLM chọn một tên hoặc null; null trả lỗi kèm danh sách điểm đến hỗ trợ.
- Không đổi OpenAPI/contract; không chạy `validate_contract.py`.
- Trường bắt buộc khác không có danh sách catalog: nguồn giá trị hợp lệ là OpenAPI. Enum `party.type`, `pace`, taxonomy, `priceUnit`, slot time, activity type và các cận `days`/`adults`/`children`/`budget`/`starRatingMin` được đọc từ contract lúc import, nên đổi contract thì model LLM đổi theo và structured output đưa đúng giá trị đó cho model.
- Vẫn còn là quy tắc nghiệp vụ nêu trong spec, không suy ra từ schema: `destination` và `days` là điều kiện bắt buộc để gọi tool (spec §4.1); `specific_hotel/specific_activity` so khớp chứa (đã bỏ dấu) với tên sản phẩm thật sau retrieval.

## Kiểm tra

- `pytest src/backend/tests` với `LANGSMITH_TRACING=false`: 92 passed.
- Chạy thật với model + fixture 50 sản phẩm: `tphcm` và `sài gòn` → `TP. Hồ Chí Minh`, `pq` → `Phú Quốc`, `da nang` → `Đà Nẵng`, `Paris` → 422 `UNSUPPORTED_DESTINATION`; trace `tool(retrieval completed (normalized destination))`.
- `grep` không còn alias trong `src/backend/app`.
- Chạy thật: `Nha Trang 10 ngày` → 400 `INVALID_TRIP_DURATION`; `xin chào` → `NEEDS_CLARIFICATION`; `cặp đôi` + `thong thả` giữ đúng enum.

## Còn lại / rủi ro

- Điểm đến mơ hồ (ví dụ `Hà`) không còn hỏi lại mà trả `UNSUPPORTED_DESTINATION`.
- Thêm một lời gọi LLM (khoảng 1–3 giây) khi tên không khớp trực tiếp; chưa đo latency.
- Unit test chạy graph gửi trace lên LangSmith khi `.env` bật tracing; nên thêm `conftest.py` đặt `LANGSMITH_TRACING=false`.
- Lỗi combo và số người do model đoán khi `children > 0` vẫn còn.
