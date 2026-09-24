# Đóng vai người dùng test agent, bổ sung 25 case golden và 3 khoá chấm

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu đóng vai người dùng thật gọi endpoint agent, rồi đề xuất bổ sung case vào bộ golden
hoặc cải tiến khác; handbook là master requirement. Bộ golden cũ (50 case) chủ yếu là câu ngắn kiểu
"Nha Trang 2 ngày", chưa kiểm được lịch có đủ hoạt động không, `context.language=en`, và lượt sau có
giữ sản phẩm cũ không.

## Cách test

Backend chạy `ITINERARY_DATA_MODE=http`, catalog Postgres thật, `gpt-4o-mini`. Gửi khoảng 35 câu qua
`POST /api/v1/assistant/itineraries` và `/stream`: câu dài tự nhiên, viết tắt, số ngày và số người
kiểu lạ, ngân sách, tiếng Anh, đa lượt, ngoài phạm vi, chèn lệnh, mã lỗi. Kết quả lạ được soi
in-process để đọc `tool_plan`, `constraints`, `candidates`.

## Lỗi agent tìm thấy (chưa sửa, chờ người dùng quyết)

1. **Lịch gần như trống ở điểm đến nhiều sản phẩm.** "Nha Trang 3 ngày cho gia đình có trẻ nhỏ" (câu demo
   Thứ Sáu của handbook §11 Tuần 4) ra đúng 1 voucher golf và 2 ngày trống, dù Nha Trang có 63 điểm tham
   quan. Nguyên nhân: tool plan do LLM tự lập chỉ gọi `search_products(taxonomy=hotel)` +
   `get_recommendations(k=5)` (2 vé bay, 2 khách sạn, 1 golf), không tìm `attraction`. Handbook §9 ghi
   agent phải "chạy vài lượt tìm kiếm — lưu trú, điểm tham quan, ăn uống". Kể cả khi có tìm, `limit=5`
   không đủ cho lịch 3 ngày (tối đa 6 hoạt động). Case G-051, G-052, G-055, G-059.
2. **Lượt sau chỉ đổi ngân sách hoặc số người vẫn loại hết sản phẩm cũ.** LLM đưa toàn bộ
   `previous_selection` vào `exclude_products` dù người dùng không xin đổi món. Case G-058, G-059.
3. **LLM tự gán `startDate` = hôm nay** khi người dùng không nói ngày, trái `EXTRACT_PROMPT` ("Only extract
   fields explicitly stated"). Hệ quả: `PRODUCT_DROPPED_DATE` và check-in khách sạn đặt hôm nay. Case G-053.
4. **`context.language=en` chỉ đổi câu hội thoại**; note của slot (`planning.py` `VISIT`) và message của
   warning (`composition.py`) vẫn là câu cố định tiếng Việt. Case G-062.
5. **"Mũi Né" trả 422** dù catalog có Phan Thiết; `DESTINATION_PROMPT` cho phép tên gọi khác. "Tràng An"
   (Ninh Bình) cũng 422. Case G-072.
6. **"Cần Thơ cuối tuần này"** (hôm nay thứ Năm 24/09) ra `startDate=2026-09-30` là thứ Tư, rồi hỏi lại vì
   mâu thuẫn. LLM chỉ nhận `today` dạng ISO, không biết thứ trong tuần. Chưa thêm case vì ngày kỳ vọng
   phụ thuộc hôm chạy.

Hành vi đúng đã được khoá thành case pass: 0 ngày / 30 ngày → 400 `INVALID_TRIP_DURATION`;
`conversationId` lạ → 404; huỷ đơn, đòi thanh toán, chèn lệnh in system prompt → 400 không gọi tool;
tên khách sạn bịa ở lượt 1 và lượt 2 không xuất hiện; "Nhật Bản" → 422 rồi "vậy thì Đà Nẵng" giữ 5 ngày;
đổi điểm đến qua lại ba lượt; "không cần khách sạn" → không có chỗ ở.

## File thay đổi

- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: thêm G-051..G-075 (25 case, 32 lượt), ba
  nhóm mới `language_en`, `invalid_duration`, `invalid_request`.
- `src/evaluation/agent/golden.py` — sửa: lượt nhận `language` và `conversationId`; khoá `expect` mới
  `minActivities`, `hasStay`, `warningsExclude`; `load_dataset` từ chối khoá lạ (`TURN_KEYS`, `EXPECT_KEYS`).
- `src/evaluation/tests/test_golden.py` — sửa: đếm 75 case; test khoá mới, khoá lạ, `language`/`conversationId`.
- `src/evaluation/reports/eval-2026-09-24-golden.md` — thêm: biên bản chạy toàn bộ kèm sweep.
- `docs/spec/agent/golden-dataset.md` — sửa: khoá mới ở §3–4, bảng nhóm §5, bỏ hai giới hạn đã gỡ ở §9.
- `docs/spec/agent/golden-run.md`, `docs/spec/agent/README.md`, `docs/spec/agent/evaluation-plan.md` — sửa:
  số case/lượt; evaluation-plan ghi các nhánh golden đã phủ.
- `history/2026-09-24-bo-sung-golden-tu-test-nguoi-dung.md` — thêm: entry này.

## Quyết định

- Tám case lộ lỗi agent giữ kỳ vọng đúng handbook/PRD và để FAIL (golden-dataset.md §8 "Lỗi agent"), mỗi
  case có comment YAML ghi lỗi. Không sửa agent trong task này: người dùng chỉ yêu cầu test và đề xuất.
- `minActivities` chỉ dùng cho Nha Trang, Hà Nội, Đà Nẵng — catalog có hàng chục điểm tham quan nên ngày
  trống không thể do thiếu dữ liệu. Ngưỡng = số ngày (1 hoạt động mỗi ngày), thấp hơn trần 2.
- G-072 (Mũi Né → Phan Thiết) là phán đoán: PRD không liệt kê tên gọi khác, nhưng `DESTINATION_PROMPT` cho
  phép và người dùng thật gõ "Mũi Né" nhiều hơn "Phan Thiết". Người dùng có thể bỏ case nếu không đồng ý.
- Runner từ chối khoá lạ thay vì bỏ qua, vì golden-dataset.md §4 đã ghi đây là rủi ro làm case PASS giả.
- Không thêm case "cuối tuần này": ngày kỳ vọng đổi theo hôm chạy, vi phạm nguyên tắc §1.

## Kiểm tra

- `.venv/bin/python -m pytest src/evaluation/tests/test_golden.py -q`: 42 passed.
- `--only G-051..G-075 --repeat 2`: PASS 48/64; 8 case fail cả 2/2 lần (G-051, G-052, G-053, G-055, G-058,
  G-059, G-062, G-072) — lỗi tất định, không phải nhiễu LLM. 17 case còn lại pass 2/2.
- Toàn bộ `--sweep` (75 case + 35 điểm đến, 124 lượt): PASS 113/124; Grounding Rate 100%, Structured
  Output Integrity 100%, Tool Calling Accuracy 100% (110 lượt); p50=3810ms, p95=5296ms. Ngoài 8 case lỗi
  agent ở trên còn 3 lượt fail do nhiễu LLM: G-013 và G-047 (đã biết), G-056 (pass 7/8 lần: 2/2 +
  `--repeat 5` 5/5, fail 1 lần trong lượt chạy đầy đủ do trả `NEEDS_CLARIFICATION`).
- Mọi lượt sweep đều pass.

## Còn lại / rủi ro

- Sửa 6 lỗi agent ở trên; lỗi 1 ảnh hưởng thẳng demo handbook. Hướng đề xuất: `validated_plan` tự thêm lời
  gọi `search_products(taxonomy=attraction, limit ≥ 2×days)` khi plan thiếu, giống cách nó đang tự thêm
  `get_recommendations`; ràng buộc `exclude_products` chỉ khi câu có ý đổi/bỏ; truyền thứ trong tuần cùng
  `today`; dịch câu cố định theo `language`.
- Handbook §12 đặt latency p95 trợ lý < 5s; biên bản 23/09 đo p95 = 5,56s, lần này 5,30s — vẫn vượt.
