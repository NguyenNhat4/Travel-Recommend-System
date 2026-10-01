# NO_RESULTS không còn ngõ cụt: message nêu lý do ngày, chip gợi ý bấm được

- Ngày: 2026-09-29
- Tác giả: Nguyễn Minh Nhật / Claude Sonnet 5.5
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, docs, contract (mock)

## Mục tiêu

Người dùng hỏi: khi không tìm thấy sản phẩm thì làm gì để họ không bỏ đi. Trước đó `NO_RESULTS` luôn trả một
câu chung ("Chưa tìm thấy sản phẩm phù hợp… Bạn có thể điều chỉnh yêu cầu.") kèm một gợi ý dạng lời khuyên, và
UI không hiện gợi ý nào (chỉ một bong bóng chữ). Phục vụ `docs/prd/user-flow.md` §3.2 (nhánh "Thiếu → mở rộng
điều kiện hoặc hỏi thêm"), FR-SRC-04 (gợi ý điều chỉnh), FR-AGT-02, FR-AGT-04. Plan đã duyệt:
`/home/nhatnm/.claude/plans/what-should-we-do-cheerful-balloon.md`.

Đã đọc trước khi code: `docs/prd/README.md`, `docs/prd/architecture.md` §3, `docs/prd/requirements.md`
(FR-AGT), `docs/prd/user-flow.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.4,
`docs/spec/agent/*`, `docs/spec/hop-dong-tich-hop-frontend.md`, hai đề xuất đang chờ chốt trong
`docs/prd/update/` (không đụng tới), `history/README.md` và 10 entry mới nhất.

## File thay đổi

- `src/backend/app/application/itinerary/retrieval.py` — sửa: thêm `nearest_open_date` (ngày khởi hành gần `startDate` nhất mà có sản phẩm đúng điểm đến bị loại chỉ vì ngày; dùng lại `_drop_reason`).
- `src/backend/app/agents/steps/evaluation.py` — sửa: khi `decision = no_results` ghi `nearest_open_date` (phải tính trước khi xoá `details`).
- `src/backend/app/agents/state.py` — sửa: thêm field `nearest_open_date`.
- `src/backend/app/agents/steps/composition.py` — sửa: `_no_results_message` (nêu ngày khi `PRODUCT_DROPPED_DATE` là lý do phổ biến nhất), `_no_results_suggestions` thêm chip ngày gần nhất và tối đa 2 điểm đến khác.
- `src/backend/app/agents/steps/messages.py` — sửa: thêm `no_results`, `no_results_date`, `suggestion_trip`, `suggestion_trip_date` (vi/en); bỏ hằng `NO_RESULTS` (chỉ vi) để câu theo ngôn ngữ hội thoại.
- `src/backend/app/agents/steps/tool_planning.py` — sửa: `catalog_destinations` xếp theo `productCount` giảm dần rồi theo tên (trước là theo tên).
- `src/backend/tests/unit/agents/test_suggestions.py`, `test_itinerary_runtime.py`, `src/backend/tests/unit/application/test_itinerary_retrieval.py` — sửa/thêm test.
- `src/frontend/src/components/assistant/SuggestionChips.tsx` — thêm: chip gợi ý dùng chung.
- `src/frontend/src/components/assistant/AssistantConversation.tsx`, `src/frontend/src/features/itinerary/widget/WidgetChat.tsx`, `useFloatingWidget.ts`, `widgetTypes.ts` — sửa: mang `suggestions` của `NO_RESULTS` vào tin nhắn và hiện chip ở tin nhắn mới nhất; bấm chip gửi ngay câu đó.
- `src/frontend/tests/unit/floatingWidgetOpening.test.tsx`, `assistantConversationStarter.test.tsx` — sửa: thêm test chip.
- `src/shared/mocks/itinerary-agent/no-results.json`, `src/shared/mocks/assistant/createItinerary.200-no-results.json` — sửa: khớp hành vi thật.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.4, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/agent/field-review.md`, `langgraph-nodes.md`, `state-fields.md` — sửa: mô tả quy tắc message/gợi ý và chip.
- `history/2026-09-29-no-results-goi-y-bam-duoc.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD, không đổi OpenAPI.** `message` là string, `suggestions` là mảng string, không thêm node hay lượt LLM; nên không cần đề xuất `docs/prd/update/`.
- **Bỏ hai bước của plan sau khi lấy bằng chứng:**
  - *Nới ràng buộc mềm (giá/sao/thuộc tính) khi rỗng* — bỏ. `NO_RESULTS` chỉ xảy ra khi cả attraction/combo cũng rỗng, mà các loại đó không bị lọc giá hay sao, nên nới không bao giờ kích hoạt; còn mở rộng sang nhánh `require_hotel` sẽ đảo hành vi có chủ đích "điều kiện cứng chưa đáp ứng thì hỏi lại, không tự vượt giá" mà `test_hotel_price_boundary_unit_and_required_stay_are_enforced` và `test_unmet_required_condition_is_asked_by_clarify_without_calling_the_model` đang khoá.
  - *Thêm `get_recommendations` cho khách chưa đăng nhập* — bỏ. Nguyên nhân thật (xem dưới) là lọc theo ngày, kết quả recommendation cũng bị lọc như vậy; thêm lời gọi chỉ đổi hành vi mọi request ẩn danh mà không giúp gì.
- **Nguyên nhân các NO_RESULTS trong báo cáo golden 2026-09-24** (Hà Nội, Côn Đảo): không phải lỗi code. Catalog hiện có Hà Nội đủ 4 loại, Côn Đảo có hotel/flight, cửa sổ bán 24/09–24/10; chạy lại đúng các câu đó (đủ ngày, số người, ngân sách) ra `COMPLETED`. Báo cáo cũ chạy lúc cửa sổ bán còn lệch (đề xuất `2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` cũng nêu rủi ro này). `NO_RESULTS` thật vẫn tái hiện khi ngày đi ngoài cửa sổ bán, nên phần sửa nhắm vào đó.
- **Gợi ý là câu gửi được nguyên văn**, mọi giá trị lấy từ dữ liệu thật (ngày mở bán của sản phẩm, danh sách điểm đến catalog), không có chuỗi nào do LLM viết → grounding không đổi.
- **Không tự đổi điểm đến** thay người dùng; chỉ đưa thành chip.
- **Đổi thứ tự `supported_destinations`** sang nhiều sản phẩm nhất trước: ảnh hưởng phụ tới `suggestedValues.destination` của `NEEDS_CLARIFICATION` và `details.supportedDestinations` của lỗi `UNSUPPORTED_DESTINATION` (contract không quy định thứ tự). Test hiện có không phụ thuộc thứ tự cũ.
- **Thay một phần quyết định** ở `history/2026-09-24-form-mo-dau-tro-ly.md` ("`NO_RESULTS` chỉ một bong bóng, không render thêm card"): vẫn không có card, nhưng chip gợi ý nay nằm trong chính bong bóng, khớp `hop-dong-tich-hop-frontend.md` §NO_RESULTS.

## Kiểm tra

- `.venv/bin/python -m pytest src/backend/tests/unit src/backend/tests/architecture -q`: 630 passed.
- `src/frontend`: `npx tsc --noEmit` sạch; `npx eslint` các file đổi sạch; `npm test`: 144 passed (24 file).
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- Chạy thật: backend cổng riêng 8010 (code mới, LLM thật, Postgres/Weaviate demo). "Hà Nội 3 ngày, đi từ 2026-12-01…" → `NO_RESULTS`, message nêu 01/12/2026, chip `Đi Hà Nội 3 ngày từ ngày 24/10/2026`, `Đi Phú Quốc 3 ngày`, `Đi Nha Trang 3 ngày`; câu đối chứng đi từ 2026-10-01 vẫn `COMPLETED`. Đã tắt instance sau khi thử; backend demo cổng 8000 của người dùng không bị đụng (vẫn chạy code cũ tới khi khởi động lại).
- `.venv/bin/python -m pytest src/evaluation/tests -q`: 3 failed, 49 passed. Ba test fail (`test_golden.py`: số case 76 so với giả định 14) đã fail y hệt trước thay đổi này (kiểm bằng `git stash`), đã ghi ở `history/2026-09-29-merge-release-mvp-v2-vao-guardrails.md`.
- Chưa chạy: golden runner đầy đủ (tốn LLM, sinh file báo cáo), kiểm thủ công trên trình duyệt.

## Còn lại / rủi ro

- Backend demo đang chạy (cổng 8000) cần khởi động lại để nhận code mới; frontend dev tự nạp.
- Chip "từ ngày dd/mm/yyyy" phụ thuộc LLM trích đúng ngày từ câu người dùng bấm; đã thử một câu ở cửa sổ bán, chưa chạy vòng hai (bấm chip) end-to-end trên trình duyệt.
- Ngày gợi ý là ngày mở bán của *một* sản phẩm bị loại; chưa đảm bảo ngày đó đủ hotel + hoạt động cho cả chuyến, nên có thể ra `FALLBACK`/ít mục hơn.
- Nếu muốn giảm hẳn `NO_RESULTS` do ngày: dữ liệu cần nạp lại theo `--as-of` trước demo (AGENTS.md §6.2) — việc của Data, không đổi ở đây.
