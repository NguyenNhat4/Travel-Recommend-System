# Câu trả lời cụt, "không có ngân sách", "hn", nút chọn nơi, một ngày đi chung (chat thử 16 kiểu: M02, M09, M10, M13, M16)

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: fix/chat-messy
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Việc 3 và việc 4 của `docs/plan/2026-10-10-chia-viec-sua-loi-chat-thu-16-kieu.md` (FR-AGT-01, FR-AGT-06, AC-AGT-01). Làm theo
hướng người dùng chốt ngày 2026-10-11:
- LLM hiểu câu chữ, hạn chế luật tất định;
- test bằng hội thoại thật và xem trace LangSmith.

## Nguyên nhân (nhắn thẳng vào backend local, xem trace LangSmith `nhat-10-7`)

- M10 "2 ng": luật `gibberish` của bộ lọc tin rác chặn ngay, trước LLM, trả "Mình chưa hiểu ý bạn" (0,0 giây).
- M10 "ko có ngân sách, từ sg":
  - nơi đi được ghi, nhưng ngân sách vẫn bị coi là còn thiếu (`trip_details_missing`);
  - `trip_so_far` vẫn ghi "chưa có: ngân sách", nên câu hỏi tiếp tục đòi ngân sách.
- M13 "hn": trace cho thấy `extract` trả `destination: null`. Payload của `extract` không có danh sách điểm đến hay cách viết tắt, nên LLM không dám coi "hn" là Hà Nội.
- M02, M16: câu hỏi chọn điểm đến theo loại nơi (`destination_kind`) có nêu tên điểm đến nhưng không có nút bấm.
- M02: thẻ LLM bỏ sót chỉ còn lý do ("[Tháp Bà Ponagar]: cũng được nhiều người ghé", "[Blue Sea Hotel 2]: giá mềm").
- M09: ba câu gợi ý ngày tính riêng rẽ: vé máy bay từ `nearest_dates`, khách sạn từ `drop_summary`, vé tham quan từ `nearest_open_date`. Kết quả là 28/10, 05/11, 05/11.

## File thay đổi

- `src/backend/app/agents/steps/guardrails.py` — sửa: `input_quality(query, replying)`. Giữa hội thoại không xét `gibberish`, để LLM đọc câu trả lời cụt. Rác hiển nhiên và tục tĩu vẫn bị chặn.
- `src/backend/app/agents/nodes.py` — sửa: truyền `replying`; `CONVERSATION_PHASE` thêm `skipped_details`.
- `src/backend/app/agents/models.py` — sửa: `Extraction.skipped_details` (ngân sách, nơi đi mà người dùng nói rõ là không có hoặc sao cũng được).
- `src/backend/app/agents/state.py` — sửa: thêm `skipped_details`.
- `src/backend/app/agents/steps/classification.py` — sửa:
  - `trip_details_missing(intent, skipped)`; `_extract_update` gộp và nhớ `skipped_details`;
  - `extraction_input` thêm `catalog_destinations` và `destination_short_forms`, lấy từ `DESTINATION_ALIASES` của Search, là dữ liệu chuẩn hóa sẵn có.
- `src/backend/app/agents/steps/prompts.py` — sửa: `EXTRACT_PROMPT` dùng `destination_short_forms` ("hn" trả lời câu hỏi điểm đến → Hà Nội) và `skipped_details`.
- `src/backend/app/agents/steps/turn_notes.py` — sửa: `trip_summary` không ghi chi tiết đã bỏ qua là "chưa có".
- `src/backend/app/agents/steps/conversation.py` — sửa: `_with_destination_buttons`. Khi hỏi chọn điểm đến theo loại nơi, mỗi điểm đến của catalog mà câu hỏi nêu tên thành một nút, tối đa 3 theo contract.
- `src/backend/app/agents/steps/exploration.py` — sửa:
  - `_catalog_details`: dòng dự phòng của thẻ kể nhãn (điểm tham quan) hoặc tiện ích (khách sạn) của catalog;
  - không có cả nhãn thì nói nơi đó nằm ở đâu, lấy từ địa chỉ.
- `src/backend/app/domain/itinerary/flights.py` — sửa: `joint_start`, ngày đi gần nhất mà mọi phần đang thiếu vì ngày cùng có (chuyến hai chiều, cửa sổ khách sạn, cửa sổ vé tham quan).
- `src/backend/app/agents/steps/composition.py` — sửa:
  - `_joint_date` tính ngày đi chung, ghi vào `nearest_open_date`;
  - câu "ngày gần nhất có vé" đưa ngày đó lên đầu và lấy làm ví dụ "đổi sang".
- `src/backend/app/agents/steps/explanations.py` — sửa: mục "Chưa có khách sạn" gợi ý ngày đi chung.
- `src/backend/tests/unit/agents/test_messy_replies.py` — thêm: luật cấu trúc mới (bộ lọc giữa hội thoại, chi tiết bỏ qua, nút chọn nơi, dòng dự phòng, ngày đi chung).
- `src/backend/tests/unit/agents/test_out_of_window_dates.py` — sửa: gợi ý đặt lại thành 23/10. Chuyến 2 ngày phải về trước khi hết cửa sổ bán 24/10; trước đây gợi ý 24/10, tức ngày về đã ngoài cửa sổ.
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md` — sửa theo các mục trên.

## Quyết định

- Bộ lọc tin rác chỉ xét "không giống từ nào" ở tin nhắn đầu. Giữa hội thoại, câu cụt thường là câu trả lời ("2 ng", "3n", "t7"), nên để LLM đọc.
- "Không có ngân sách" do LLM nhận ra (`skipped_details`), không dùng từ khoá. Trường bắt buộc (ngày đi, số người) không bỏ qua được.
- Ngày đi chung chỉ dùng dữ liệu đã tải trong lượt; không phần nào thiếu vì ngày thì không gợi ý gì.
- Việc 5 (Search lọc khách sạn theo ngày đi, M11) không tái hiện được trên catalog hiện tại: "lập lịch Hà Nội 2 ngày từ 24/10…" ra lịch có khách sạn. Search vẫn chưa nhận ngày của `travelContext` (`engine_tools.py`), nhưng đó là phần của team Search, nên không sửa.

## Kiểm tra (hội thoại thật, LLM thật, backend local `inprocess`)

| Ca | Kết quả |
|---|---|
| M10 | "lên lịch đi hà nội giúp t" → "3 ngày" → "2 ng" (ghi 2 người, không còn "chưa hiểu ý bạn") → "thứ 7 tuần sau" (đủ trường bắt buộc, ra lịch) → "ko có ngân sách, từ sg" (lịch có vé từ TP. Hồ Chí Minh, "chưa có ngân sách để đối chiếu", không đòi ngân sách). **Tốt.** |
| M13 | "đm hỏi lắm thế" → "lên lịch đi vl" → "hn" → "Còn thiếu số ngày cho chuyến đi Hà Nội". **Tốt.** |
| M02 | Lượt 3 "chỗ nào mát mát" → nút "Đà Lạt · Sa Pa · Mộc Châu". Thẻ thiếu mô tả: "ở Grand World, khu Bãi Dài…", "khách sạn có chỗ ngồi ngoài trời, lễ tân 24 giờ…". **Tạm**: chưa tự chọn luôn một nơi mát khi đã chê hai lần. |
| M16 | Nút "Nha Trang · Phú Quốc · Đà Nẵng"; "nha trang" được ghi nhận. **Tốt.** |
| M09 | Câu mở đầu, mục vé máy bay và mục khách sạn cùng gợi ý 28/10/2026 ("Muốn đặt được ngay thì bạn nhắn 'Đi Phú Quốc 3 ngày từ ngày 28/10/2026'"). **Tốt.** |

- Lần đầu nhắn M16 bị 500 (`ITINERARY_VALIDATION_FAILED`) vì cho tới 4 nút trong khi contract cho tối đa 3. Đã sửa và nhắn lại thì đạt.
- `pytest src/backend/tests src/evaluation/tests/test_golden.py` (chạy một lần trước commit): 2845 passed, 36 skipped.

## Còn lại / rủi ro

- Nút ghi "Thứ 7 tuần sau (24/10)", nhưng người dùng gõ "thứ 7 tuần sau" vào Chủ nhật 11/10 thì LLM hiểu là 17/10. Lỗi có từ trước (`date_suggestions`), chưa sửa.
- M02: sau hai lần chê, trợ lý vẫn hỏi chọn nơi mát thay vì tự chọn một nơi và hiện thẻ.
- Việc 5: chờ team Search nếu lỗi xuất hiện lại.
