# Tư vấn vé máy bay, thẻ ngày–giá, và các lỗi còn sót sau chat thử lần 2

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, frontend, docs

## Mục tiêu

Người dùng review lại sau khi agent local sửa xong `docs/plan/2026-10-10-chia-viec-sua-loi-chat-thu-16-kieu.md`. Họ gửi danh
sách lỗi còn sót và giao agent tự quyết phần PRD kỹ thuật ("về phần technical PRD mình cho bạn quyết định mọi thứ xong
update docs cho mình").

Lỗi còn sót:
- "đổi sang chỗ khác" ra form điền sẵn Hà Nội kèm "còn thiếu số ngày". Phải hỏi đổi sang đâu.
- M05 (vé máy bay):
  - Nút "Từ TP. Hồ Chí Minh" bị hiểu là hỏi Sài Gòn có gì chơi.
  - Chưa tư vấn được giờ đi sớm/muộn, ngày có/không có chuyến, "tại sao đắt" (trợ lý lặp lại câu báo giá rẻ nhất).
  - Câu trả lời nhiều chữ, không có link sang trang vé đúng ngày.
- M03 biến thể: "chùa thiên mậu ở đâu" ra danh sách khách sạn.
- M04:
  - Chưa tìm được khách sạn rẻ nhất/đắt nhất.
  - Việc không làm được thì phải nói rõ, không lặp một câu cố định.
- "cho mình cái form" bị trợ lý hỏi lại bằng chữ.
- M06: câu nói "vé" không rõ loại vẫn được trả lời như vé máy bay.
- M09: lịch tham khảo không có nút bấm.

Phục vụ FR-AGT-01, FR-AGT-04, FR-AGT-06 và FR-AGT-07 mới (tư vấn vé máy bay), NFR-REL-01.

## File thay đổi

Contract và mock (1.25.0, chỉ thêm):
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa:
  - `ItineraryCompleted.suggestions` (≤ 3).
  - Mô tả `ItineraryNeedsClarification.searchResults` thêm `flight` cho câu trả lời vé.
- `src/shared/contracts/openapi.yaml`, `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py`, `src/backend/tests/contract/test_search_llm_contract.py` — sửa: version 1.25.0.
- `src/shared/mocks/assistant/createItinerary.200-needs-clarification-fare.json` — thêm: câu trả lời vé mẫu có `searchResults.flight`.
- `src/shared/mocks/index.json` — sửa: đăng ký mock trên.

Agent:
- `src/backend/app/agents/models.py` — sửa:
  - `FareQuestion` thêm `day`, `time_of_day`, `why`, `availability`.
  - `TurnRoute` thêm `form_request`.
  - `price` thêm `dear`.
- `src/backend/app/agents/steps/fares.py` — sửa:
  - `answer_text` dựng câu gọn và trả các chuyến làm thẻ: rẻ/đắt nhất, đúng ngày hỏi (không có thì ngày gần nhất), khung giờ, ngày có/không có chuyến, ngày khác.
  - `why_text` cho "tại sao đắt".
  - `_response` thêm `searchResults.flight` và `candidates`.
  - Nút của câu trả lời lưu trong `pending_fare.chips`; `chip_reply` đi thẳng nhánh vé khi bấm nút.
  - Câu chưa rõ loại vé kèm "đi đâu cũng được" giữ nơi đi và "đi đâu cũng được" cho nút vé máy bay.
  - Kiểu rẻ/đắt chỉ giữ từ lượt trước với "ngày khác", "tại sao".
- `src/backend/app/agents/nodes.py` — sửa:
  - `classify` gọi `fares.chip_reply` trước LLM.
  - `intake` reset `form_request`.
- `src/backend/app/agents/state.py` — sửa: thêm `form_request`.
- `src/backend/app/agents/steps/classification.py` — sửa:
  - `route_input` có `today` để LLM đổi ngày bay.
  - `fare_ask` lưu dạng JSON.
  - `form_request` đi thẳng `clarify` kèm form.
  - Câu xin đổi chưa nêu giá trị mới hỏi trước mọi câu hỏi phần còn thiếu.
- `src/backend/app/agents/steps/conversation.py` — sửa:
  - `destination_choices`: 3 nút "Đổi sang <nơi>", chữ nêu cùng các nơi, không form khi hỏi đổi.
  - `_form_shown` nhận `form_request`.
  - Nơi không tra ra: LLM tự nói không kiểm được (`place_not_found`); câu có giờ/giá, hoặc nói giờ/giá/vé mà không nhận là không kiểm được, thì thay bằng câu cố định (`_claims_a_fact`).
- `src/backend/app/agents/steps/exploration.py` — sửa:
  - "ở đâu" chỉ là hỏi chỗ ở khi câu không nêu nơi nào.
  - `facts.address` cho nơi được hỏi.
  - `price_listing`: khách sạn rẻ/đắt nhất cả điểm đến theo catalog xếp giá.
  - `price_scope` và `place_not_found` vào payload LLM.
- `src/backend/app/agents/steps/narration.py` — sửa: `reference_chip`, tức nút "Đi <nơi> <n> ngày từ ngày <ngày gần nhất>" dưới lịch tham khảo.
- `src/backend/app/agents/steps/messages.py` — sửa: câu và nút vé mới (vi, en), `chip_change_destination`, `chip_reference_nearest`, `reason_dearest`, `reason_high_price`; bỏ dòng "Ngày khác: …" khỏi câu trả lời vé.
- `src/backend/app/agents/steps/prompts.py` — sửa:
  - `CLASSIFY_PROMPT`: các trường vé mới, "vé" không rõ loại, `form_request`, `price` dear.
  - `CONVERSATION_PROMPT`: `destination_choices`, `place_not_found`.
  - `EXPLORE_PROMPT`: `facts.address`, `price_scope`, lý do dearest, nút không hứa nhà hàng/giờ mở cửa, `place_not_found`.
- `src/backend/app/domain/itinerary/exploration.py` — sửa: `dearest_cards`, lý do `DEAREST`, `HIGH_PRICE`.
- Test:
  - `src/backend/tests/unit/agents/test_fares.py`, `test_fares_followups.py`, `test_fares_messy.py` — sửa theo dạng câu mới, thêm test ngày cụ thể, khung giờ, ngày có/không có chuyến, "tại sao đắt", bấm nút nơi đi.
  - `test_exploration.py`, `test_place_facts.py`, `test_out_of_window_dates.py` — sửa/thêm: khách sạn đắt nhất, danh sách theo giá, câu không kiểm được tự viết, nút lịch tham khảo.

Frontend (widget):
- `src/frontend/src/features/itinerary/widget/WidgetFareDays.tsx` — thêm: hàng thẻ ngày–giá. Mỗi thẻ ghi thứ, ngày, giá/khách, giờ, hãng, kèm "Đi <nơi>" khi thẻ thuộc nhiều tuyến; link `flightProductHref` → `/flights?origin&destination&checkIn`.
- `src/frontend/src/features/itinerary/widget/WidgetNarration.tsx` — sửa: gom chuyến của câu trả lời vé thành một khối `fares` ở dòng đầu tiên nhắc chuyến.
- `src/frontend/src/features/itinerary/widget/widgetFlight.ts` — sửa: `flightShortDay`.
- `src/frontend/src/features/itinerary/widget/WidgetChat.tsx` — sửa: bấm thẻ vé thì đóng widget.
- `src/frontend/src/features/itinerary/widget/useFloatingWidget.ts` — sửa: hiện `suggestions` của `COMPLETED`.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract 1.25.0.
- `src/frontend/tests/unit/widgetNarration.test.tsx`, `floatingWidgetOpening.test.tsx` — sửa: test thẻ ngày–giá, nút của `COMPLETED`.

Tài liệu và đánh giá:
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md` — sửa: tư vấn vé, xin form, đổi điểm đến, khách sạn theo giá, nơi không tra ra; field `form_request`, `price_scope`, `pending_fare.chips/shown/kind`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §4.3 tư vấn vé, các nút 1.25.0.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.8 thẻ ngày–giá, nút dưới lịch trình.
- `src/evaluation/datasets/chat_review_v1.json` — thêm: 8 hội thoại theo đúng các ca người dùng review (R01–R08).

## Quyết định

- **Câu trả lời vé gọn:** chỉ nêu chuyến trả lời câu hỏi. Các ngày, chuyến khác thành tối đa 4 thẻ thật của catalog (`searchResults.flight`), kiểm grounding như lượt khám phá. Đây là yêu cầu "text nhiều quá, làm giao diện để nổi bật ngày, số".
- **Link sang trang vé đúng ngày** dùng `/flights?origin&destination&checkIn`, vì vé không có trang chi tiết riêng (`flightProductHref` đã có).
- **"Tại sao đắt" không đoán lý do.** Catalog không có hạng vé, hành lý, ghế còn lại; câu nói rõ điều đó, rồi chỉ nêu số liệu so sánh và đưa thẻ vé để người dùng tự xem.
- **Nút của trợ lý đi bằng luật.** Đây là đối chiếu nút do chính code tạo, không dò câu chữ, nên không đi ngược hướng "LLM hiểu, code đối chiếu" của `history/2026-10-11-llm-hieu-cau-chu-thay-tu-khoa.md`.
- **Khách sạn rẻ/đắt nhất:** không kèm "gần <nơi>" thì dùng danh sách catalog xếp theo giá của mọi khách sạn còn phòng. Kết quả Search ("khách sạn được đánh giá tốt") không phải rẻ/đắt nhất thành phố.
- **Nơi không tra ra:** bỏ câu cố định cho mọi trường hợp. LLM tự viết, code chỉ chặn câu tự nói giờ/giá; câu cố định chỉ còn là dự phòng.
- **Contract 1.25.0 chỉ thêm field tuỳ chọn, client cũ không hỏng.** Người dùng uỷ quyền quyết phần kỹ thuật; đề xuất PRD đi cùng đợt này.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (120 schemas, 96 fixtures).
- `pytest src/backend/tests src/evaluation/tests/test_golden.py` (bỏ `ITINERARY_LLM_REASONING_EFFORT`, `AUTH_REDIS_URL` của môi trường container): 2851 passed, 36 skipped. Lần chạy riêng `tests/unit/agents` + `tests/unit/domain` sau các sửa cuối: 1981 passed; `test_exploration.py`: 60 passed.
- Frontend:
  - `npx vitest run tests/unit`: 71 files, 762 passed.
  - `npx tsc --noEmit -p .`: sạch.
  - `npm run lint`: 0 lỗi, 3 cảnh báo có từ trước.
- Hội thoại thật (backend local `inprocess`, LLM thật), nhắn qua API:
  - "Lên lịch Hà Nội cho mình" → "đổi sang chỗ khác": hỏi đổi sang đâu, nút "Đổi sang Phú Quốc/Nha Trang/TP. Hồ Chí Minh", chữ nêu đúng ba nơi đó, không form.
  - "có vé nào rẻ đi hn ko bạn":
    - hỏi loại vé, rồi nút "Vé máy bay ra Hà Nội rẻ nhất" → hỏi nơi bay;
    - nút "Từ TP. Hồ Chí Minh" → báo giá 0,2 giây (đi bằng nút), kèm 4 thẻ;
    - "thế ngày khác thì sao" → 4 ngày kế tiếp; "Đắt nhất thì sao?" → 2.385.000 ₫;
    - "tại sao đắt" → nói rõ không khẳng định được lý do, gấp 4 lần vé rẻ nhất, cao hơn 86% giá phổ biến, thẻ của vé đó.
  - "mình muốn đi sớm, ngày 20/10 có chuyến nào không" → ngày 20/10 chưa có chuyến trước 09:00, ngày gần nhất 12/10, 13/10; "tối thì sao" → khung tối.
  - "tao ở sài gòn, đi đâu cũng đc miễn vé rẻ" → hỏi loại vé (2/2 lần); "Vé máy bay rẻ nhất" → so tuyến từ TP. Hồ Chí Minh, rẻ nhất Đà Nẵng 407.000 ₫. "vé đi đà nẵng bao nhiêu" → hỏi loại vé.
  - "chùa thiên mậu ở đâu" → thẻ Chùa Thiên Mụ, "ở Kim Long, Huế…".
  - "chùa trấn quốc mấy giờ đóng cửa" (không có trong catalog) → LLM tự nói chưa tìm thấy, không nêu giờ.
  - "khách sạn ở hà nội" → "rẻ nhất là chỗ nào" (Hanoi Backpackers Lodge 221.000 ₫, đúng rẻ nhất catalog) → "còn đắt nhất" (L7 West Lake 5.634.875 ₫).
  - "Lên lịch Sầm Sơn cho mình" → "cho mình cái form" → có form điền sẵn Sầm Sơn.
  - "đi phú quốc 3 ngày từ 20/11, …" → lịch tham khảo kèm nút "Đi Phú Quốc 3 ngày từ ngày 15/10/2026".
- Chạy lại 16 hội thoại cũ và 8 hội thoại R01–R08 bằng `chat_replay`: kết quả ghi ở báo cáo chat thử lần 3 trong commit sau.

## Còn lại / rủi ro

- `classify` chạy ở nhiệt độ 1, nên câu tự gõ (không bấm nút) vẫn có thể bị hiểu lệch. Nút do trợ lý tạo thì đã ổn định.
- Câu "trong cả đợt" của vé dựa trên cửa sổ bán 30 ngày của catalog, không phải lịch bay thật của hãng.
- Search vẫn chưa lọc khách sạn theo ngày đi (việc 5 của plan 10/10).
