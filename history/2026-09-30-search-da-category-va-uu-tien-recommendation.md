# Tool node search mặc định hotel+attraction+golf; ưu tiên Search trước Recommendation trong lịch trình

- Ngày: 2026-09-30
- Tác giả: NhatNM / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người dùng yêu cầu hai thay đổi cho itinerary agent:

1. `search_products` hiện có xu hướng chỉ tìm `hotel` do `TOOL_PLAN_PROMPT` chỉ nhắc riêng hotel. Cần mặc định tìm cả `hotel` + `attraction` (tour) + `golf`, chỉ loại một category khi người dùng chủ động yêu cầu loại trừ (`constraints.exclude_taxonomies`).
2. `get_recommendations` vẫn được gọi ở mọi lượt có JWT như hợp đồng hiện tại (giữ nguyên, không đổi trigger — người dùng xác nhận trong phiên trao đổi). Thay đổi nằm ở cách dùng kết quả: khi build lịch trình, ưu tiên sản phẩm từ Search cho mỗi stay/slot; chỉ dùng sản phẩm từ Recommendation khi Search không có ứng viên phù hợp, và phải acknowledge rõ với người dùng đây là gợi ý (qua warning), không phải kết quả tìm kiếm.

Đánh giá lệch PRD (AGENTS.md mục 8): xác nhận với người dùng cả hai thay đổi không đảo ngược quy tắc "chèn `get_recommendations` mọi lượt có JWT" và không mâu thuẫn PRD (taxonomy enum đã có hotel/attraction/golf; `architecture.md` đã mô tả "tìm Tool tìm kiếm phòng & tour") — không cần đề xuất `docs/prd/update/`, chỉ cập nhật spec + code trực tiếp.

## File thay đổi

- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: thêm §2.6 (phạm vi search mặc định theo category) và mục 12 ở §5 (ưu tiên Search trước Recommendation + warning `RECOMMENDATION_FALLBACK`).
- `src/backend/app/agents/steps/prompts.py` — sửa: `TOOL_PLAN_PROMPT` yêu cầu mặc định search cả hotel/attraction/golf thay vì chỉ nhắc hotel.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: `validated_plan()` thêm lưới an toàn tất định lấp category mặc định (hotel/attraction/golf) sau lưới an toàn Similar hiện có; best-effort theo `MAX_CALLS`, bỏ qua nếu không còn điểm đến chuẩn hóa.
- `src/backend/app/domain/itinerary/planning.py` — sửa: `compose_plan()` nhận thêm `sources`; `_stay_order`/`_activity_order` ưu tiên nguồn `search` trước `recommendation` cùng vị trí.
- `src/backend/app/agents/steps/composition.py` — sửa: `composed()` gọi `compose_plan` với `sources`; thêm warning `RECOMMENDATION_FALLBACK` khi lịch trình có mục nguồn Recommendation.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — sửa: cập nhật các test pin số lượng/loại tool call bị ảnh hưởng bởi lưới an toàn category mặc định; thêm `DefaultCategoryFillTests`.
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — sửa: cập nhật chữ ký `compose_plan(candidates, sources, intent)`; thêm test ưu tiên Search trước Recommendation cho cả stay và activity.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: `Clients` thêm `search_error`; cập nhật `test_all_transient_failures_terminate_without_fake_results` để search cũng lỗi tạm thời (nếu không, search mặc định mới trả kết quả thật, biến 503 lỗi thành FALLBACK 200 — không còn đúng ý test cũ).
- `src/backend/tests/unit/agents/test_composition_recommendation_warning.py` — thêm: test cho warning `RECOMMENDATION_FALLBACK` ở `composition.composed()`.

## Quyết định

- Coi một `search_products` không lọc `taxonomy` (giá trị `None`) là đã phủ mọi category mặc định, vì search không lọc loại trả kết quả hỗn hợp — theo đúng quy ước đã dùng ở lưới an toàn Similar hiện có (`tool_planning.py` dòng ~279 cũ).
- Lưới an toàn category mặc định đặt sau lưới an toàn Similar và sau khối `require_recommendations`, best-effort giống Similar: hết trần `MAX_CALLS=5` thì bỏ qua phần còn thiếu, không huỷ lượt, không lỗi.
- Bỏ qua lưới an toàn khi `intent.destination` trống, để không vỡ các state thử nghiệm/luồng chưa có điểm đến chuẩn hóa (tránh `ToolError` không cần thiết).
- Ưu tiên Search/Similar trước Recommendation thực hiện ở tầng chọn ứng viên (`compose_plan`), không đổi `RecommendForUser`/`BuildPopularity`/`strategy` — personalize theo user ID hay fallback theo popularity vẫn do engine RecSys quyết định như cũ.
- Disclosure "đây là gợi ý" thể hiện qua warning mới `RECOMMENDATION_FALLBACK` (nhất quán với cơ chế `warnings[]` sẵn có, vì response `COMPLETED` không có trường message dạng chat), không thêm câu trả lời LLM riêng.
- `warnings[].code` trong `itinerary-agent.yaml` là `type: string` tự do, không phải enum đóng — không cần sửa OpenAPI cho warning mới.

## Kiểm tra

- `python3 -m pytest src/backend/tests -q`: 892 passed, 21 skipped (đã sửa 1 test pin hành vi cũ ở `test_itinerary_runtime.py`).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (97 schemas, 50 grounded products, ...).

## Còn lại / rủi ro

- `_validated_args` chưa dịch constraint riêng cho `attraction`/`golf` (chỉ hotel có price/star translation) — ngoài phạm vi yêu cầu lần này, có thể cần xem xét sau nếu người dùng muốn ràng buộc giá/đánh giá cho tour/golf.
- Lưới an toàn category mặc định làm tăng số lời gọi search trong nhiều kịch bản (tối đa +2 mỗi lượt) — cần theo dõi ngân sách độ trễ p95 5s (NFR-AGT) và tỷ lệ `NO_RESULTS` như đã lưu ý ở `history/2026-09-30-co-dinh-limit-search-va-k-recommendations.md`.
