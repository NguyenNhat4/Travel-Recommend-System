# Loại trừ đúng sản phẩm cũ khi user xin đổi mà không nêu tên thay thế

- Ngày: 2026-09-23
- Tác giả: nhatutc2@gmail.com / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Gap phát hiện khi rà FR-AGT-05 (`docs/prd/requirements.md` §1.4, "đổi phòng, đổi điểm tham quan"): khi user nói "đổi hoạt động khác" mà không nêu tên cụ thể, hệ thống không có cách nào loại trừ đúng sản phẩm vừa bị từ chối — `specific_activity`/`specific_hotel` chỉ là bộ lọc dương (bắt buộc có), `exclude_taxonomies` chỉ loại cả nhóm. Kết quả: `compose_plan` chọn giá thấp nhất trước nên rất có thể chọn lại đúng sản phẩm user vừa từ chối. Vì FR-AGT-05 đã có sẵn trong PRD, đây là fix để code khớp đúng yêu cầu đã ghi, không phải thay đổi lệch PRD — không cần đề xuất trong `docs/prd/update/` (mục 8 AGENTS.md, đoạn "Thay đổi chỉ hiện thực đúng điều PRD đã ghi thì không cần đề xuất").

## File thay đổi

- `src/backend/app/agents/state.py` — sửa: thêm field `previous_selection: list[dict]` vào `AgentState`.
- `src/backend/app/agents/models.py` — sửa: thêm `exclude_products: list[str] | None` vào `ConstraintUpdate`, thêm `"exclude_products"` vào enum `clear_fields`.
- `src/backend/app/agents/nodes.py` — sửa:
  - `EXTRACT_PROMPT`: dạy LLM dùng `previous_selection` để khớp câu nói mơ hồ ra đúng `productId`, chỉ được copy id có sẵn, không tự bịa.
  - `intake_node`/`intake_node_async`: khởi tạo và khôi phục `previous_selection` từ `ConversationStore` giống `intent`/`constraints`.
  - `_extraction_input`: đưa `previous_selection` vào payload JSON gửi LLM.
  - `_classify_result`: merge `exclude_products` — lọc bỏ mọi id không có trong `previous_selection` (chặn LLM bịa), cộng dồn với danh sách loại trừ cũ thay vì ghi đè.
  - Thêm `_selection_snapshot(response)`: rút gọn itinerary `COMPLETED` thành danh sách `{productId, name, taxonomy}`.
  - `finalize_node_async`: lưu `previous_selection` (từ `_selection_snapshot`) vào store khi response `COMPLETED`; các trạng thái khác giữ nguyên bản cũ thay vì xóa.
- `src/backend/app/application/itinerary/retrieval.py` — sửa: `_drop_reason` thêm check đầu tiên `productId in constraints.exclude_products` → `PRODUCT_DROPPED_EXCLUDED`.
- `src/backend/tests/unit/agents/test_classify.py` — thêm: 2 test cho `_classify_result` — lọc id lạ khỏi `exclude_products`, cộng dồn qua nhiều lượt.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — thêm: test 2 lượt đầy đủ qua `build_graph` — lượt 1 chọn sản phẩm rẻ nhất, lượt 2 loại đúng sản phẩm đó không nêu tên thay thế, xác nhận sản phẩm khác được chọn.
- `docs/spec/agent/state-fields.md` — sửa: thêm dòng `previous_selection`, ghi chú `exclude_products` vào dòng `constraints`.
- `docs/spec/agent/langgraph-nodes.md` — sửa: mục 6.1 cập nhật `intake`/`classify`/`finalize` đọc/ghi `previous_selection`.

## Quyết định

- Dùng `productId` để loại trừ, không dùng so khớp tên như `specific_hotel`/`specific_activity`: tên có thể trùng/lệch, loại trừ sai hướng (loại nhầm hoặc không loại được) nguy hiểm hơn nhiều so với yêu cầu bắt buộc có (sai thì chỉ lọc hơi rộng). `productId` đã là khóa chuẩn của `candidates`/`sources` trong `collect()`.
- Whitelist `exclude_products` theo đúng `previous_selection` hiện tại trong `_classify_result`, không tin thẳng output LLM — giữ đúng cam kết grounding 100% (FR-AGT-04): không cho LLM loại trừ một id nó tự nghĩ ra.
- Lưu `previous_selection` dạng snapshot gọn (`productId`/`name`/`taxonomy`) trong `ConversationStore`, không lưu cả `itinerary` — nhất quán với quy tắc "không dùng trạng thái hội thoại làm nguồn chính thức cho giá/availability" (`hop-dong-tich-hop-itinerary-assistant.md` §6): giá/availability lượt sau vẫn luôn lấy lại từ Search/Recommendation.
- Không đổi OpenAPI: `previous_selection`/`exclude_products` thuần nội bộ agent, không lộ ra request/response client. Mã cảnh báo mới `PRODUCT_DROPPED_EXCLUDED` hợp lệ vì `ItineraryWarning.code` là `string` tự do trong contract, không phải enum đóng.
- `finalize_node_async` chỉ ghi đè `previous_selection` khi response `COMPLETED`; các lượt `NEEDS_CLARIFICATION`/`FALLBACK`/lỗi giữ nguyên bản cũ để không mất tín hiệu loại trừ đã tích lũy.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests/unit/agents/test_classify.py src/backend/tests/unit/agents/test_itinerary_runtime.py` → **48 passed**.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests` (toàn bộ) → **178 passed, 2 skipped** (2 skip là integration Postgres, `RUN_POSTGRES_INTEGRATION` chưa bật — không liên quan thay đổi này).
- Không đổi contract/schema/seed nên không cần `validate_contract.py` hay `db/verify.sql`.

## Còn lại / rủi ro

- Chưa test được khả năng LLM thật (Gemini/OpenAI/Anthropic) tự khớp đúng câu nói mơ hồ ("cái đó", "chỗ vừa rồi") ra đúng phần tử trong `previous_selection` — test hiện tại script hóa `Extraction` để kiểm chứng phần merge/validate/lọc candidate, không kiểm chứng chất lượng suy luận ngôn ngữ tự nhiên của model thật. Nên thêm case này vào bộ 12 case chạy tay ở `evaluation-plan.md`.
- `previous_selection` chỉ ghi nhận sản phẩm ở lượt `COMPLETED` gần nhất; nếu user tham chiếu một sản phẩm đã bị đổi từ 2+ lượt trước (không còn trong `previous_selection` hiện tại), hệ thống sẽ không nhận diện được — chấp nhận được cho phạm vi fix này (giải quyết đúng ca "vừa cho xem, xin đổi ngay").
- Có `history/2026-09-23-tai-thiet-lap-cau-truc-backend.md` (trạng thái ghi "dang dở", nhánh `feat/auth`) từng đổi cùng `agents/nodes.py`; kiểm tra thực tế cho thấy cấu trúc mới đã nằm sẵn trong `feat/agent` (đã merge qua `release-mvp-v1`), nên không có xung đột đường dẫn khi sửa lần này.
