# Ngày đi ngoài cửa sổ mở bán: lịch tham khảo thay cho "không có sản phẩm" (lỗi H, chat thử 10/10)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Mã FR/NFR: FR-AGT-03, FR-AGT-04 + NFR-REL-01 (grounding), FR-AGT-06
- Plan: `docs/plan/2026-10-10-sua-loi-chat-thu-tro-ly.md`, đơn vị 5

## Mục tiêu

"Lên lịch Hà Nội 3 ngày cho 2 người lớn" → "khởi hành 12/11, ngân sách 15 triệu, từ Đà Nẵng" trả `NO_RESULTS` "Chưa có sản
phẩm mở bán cho ngày này" (catalog mở bán 30 ngày từ ngày nạp, tới 08/11). Người dùng: trợ lý không bao giờ được chỉ nói
không có sản phẩm; phải nói "mình chưa tìm thấy, nhưng có những nơi sau…" rồi dẫn chuyện, lấy các điểm đến nổi tiếng (điểm
có giá cào về được tính là vé tham quan; điểm tự do cũng dùng được).

## File thay đổi

- `src/backend/app/application/itinerary/retrieval.py` — sửa: `collect` giữ tạm điểm tham quan/golf chỉ vướng ngày, gắn cờ
  `NOT_ON_SALE`; thêm `reference_only` (còn điểm mở bán thì loại các điểm gắn cờ như cũ; không còn thì giữ tối đa 8 điểm nhiều
  lượt đánh giá nhất), `MAX_REFERENCE_PLACES`, `MIN_REFERENCE_PLACES`.
- `src/backend/app/agents/steps/evaluation.py` — sửa: gọi `reference_only` sau `collect`; tính `nearest_open_date` cho lịch
  tham khảo.
- `src/backend/app/agents/steps/composition.py` — sửa: `_not_on_sale` (bớt `bookableCount`, cảnh báo
  `PRODUCT_NOT_ON_SALE_FOR_DATE` nêu cửa sổ mở bán; điểm tự do không cảnh báo), `_sale_window`.
- `src/backend/app/agents/steps/narration.py` — sửa: `reference_note` (câu mở đầu do code viết, kèm câu đặt lại ngày gần
  nhất), chèn ở bản LLM và bản dự phòng; payload `reference_only` và `about` từng nơi cho LLM.
- `src/backend/app/agents/steps/prompts.py` — sửa: `NARRATE_PROMPT` luật `reference_only`.
- `src/backend/app/agents/steps/messages.py` — sửa: `not_on_sale_item`, `sale_window`, `sale_window_unknown`,
  `reference_note`, `reference_nearest` (vi, en).
- `src/backend/tests/unit/agents/test_out_of_window_dates.py` — thêm: 6 test.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa 3 test theo hành vi mới: hai test `NO_RESULTS` do ngày giờ
  dùng catalog chỉ có khách sạn (nhánh `NO_RESULTS` vẫn được kiểm); test catalog fixture (ngày 2999 ngoài cửa sổ mọi điểm
  tham quan) nay kiểm cảnh báo lịch tham khảo thay cho "khách sạn rẻ nhất" (chỉ đúng khi lịch không có hoạt động nào).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §4.3 bảng tiêu đề, §4.4 lịch tham khảo.
- `history/2026-10-10-lich-tham-khao-ngoai-cua-so-mo-ban.md` — thêm: entry này.

## Quyết định

Người dùng giao agent tự chốt (chat 10/10):
- Không lệch PRD `architecture.md` §3 "không lấp bằng sản phẩm do LLM tạo": mọi điểm vẫn là sản phẩm Search thật; chỉ thêm
  trường hợp dựng lịch tham khảo. Contract không đổi (cảnh báo là chuỗi tự do; `COMPLETED` không có `suggestions` nên ngày
  gần nhất nằm trong câu mở đầu, dạng gửi được nguyên văn).
- Chỉ bật khi ngày đi không còn điểm tham quan nào mở bán, để lịch bình thường không đổi (thử bật luôn thì test catalog
  fixture đổi khách sạn được chọn).
- Khách sạn, vé máy bay vướng ngày vẫn bị loại: đặt khách sạn/vé cho ngày chưa mở bán không có nghĩa.
- Chọn nơi theo lượt đánh giá (điểm nổi tiếng); lần chạy đầu không lọc thì ra vé hạng Vinpalace không ai đánh giá.

## Kiểm tra

- `pytest src/backend/tests` (bỏ `AUTH_REDIS_URL` và `ITINERARY_LLM_REASONING_EFFORT` của container): 2739 passed, 36 skipped.
  Chạy với hai biến đó: test contract gặp 429 do dùng chung Redis local với các lượt chat live, `test_llm_factory` lỗi do
  `ITINERARY_LLM_REASONING_EFFORT=none` — cả hai là môi trường, lỗi y hệt trên code trước thay đổi (đã thử bằng `git stash`).
- Backend local (`inprocess`, LLM thật, catalog snapshot 30/09, nạp ngày 10/10): đúng hai câu của người dùng → `COMPLETED`,
  câu mở "Mình chưa tìm thấy vé mở bán cho ngày 12/11/2026 (vé tham quan ở Hà Nội đang mở bán đến 08/11/2026), nhưng Hà Nội
  vẫn có những nơi rất đáng đến…", lịch Văn Miếu, Hoàng Thành Thăng Long, Lotte World Aquarium, Hanoi Sightseeing Bus, mỗi nơi
  một câu kể từ mô tả; mục "Chưa có khách sạn" và vé máy bay nêu ngày gần nhất như cũ. Trước sửa: `NO_RESULTS`.

## Còn lại / rủi ro

- `planning` vẫn đếm điểm tham quan tự do vào `bookableCount` (contract nói loại `ticketed=false`): có từ trước, chưa sửa.
- Tổng tiền của lịch tham khảo dùng giá niêm yết hiện có; giá cho ngày đi có thể khác khi mở bán.
