# Câu hỏi vé: hỏi lại khi mơ hồ, nhớ ngữ cảnh, rẻ nhất/đắt nhất, đã có lịch (lỗi C–F, chat thử 10/10)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Mã FR/NFR: FR-AGT-01, FR-AGT-06 (đề xuất `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md`, đã chốt), FR-AGT-05
  (phần hỏi giá vé của `docs/prd/update/2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md`, agent chốt theo uỷ quyền),
  NFR-REL-01, NFR-PERF-02
- Plan: `docs/plan/2026-10-10-sua-loi-chat-thu-tro-ly.md`, đơn vị 3

## Mục tiêu

Lỗi người dùng gặp (tái hiện trên backend local, LLM thật; lỗi E đối chiếu trace LangSmith `nhat-10-7`, thread
`e817a506…`):
- C: "giờ tao đi hà nội thì vé nào rẻ" → ra thẻ khám phá, không hỏi vé gì.
- D: "tao hỏi vé máy bay mà" → LLM trả lời "không có dữ liệu vé".
- E: "giá máy báy đó rẻ nhất chưa" chỉ báo đúng ngày đã chọn ("chưa có chuyến"), không so ngày khác; trên local khi đã có
  lịch thì lập lại cả lịch (25 giây). "đắt nhất thì soa" → lập lại cả lịch (trace: 26 giây).
- F: đang hỏi vé, "đi đâu cũng được, miễn đắt nhất" → khám phá Nha Trang.

Trace thật cho thấy lượt trước "đổi sang ngày 15" đã `COMPLETED` mà lượt hỏi vé vẫn đi luật giá vé (0,17 giây): điều kiện
chặn `previous_plan` không chắc chắn. Không cần biết vì sao nữa: luật mới bỏ điều kiện đó.

## File thay đổi

- `src/backend/app/agents/steps/fares.py` — sửa: `vague` (vé chưa rõ loại → hỏi lại kèm 3 nút), `asked` (nói rõ đang hỏi vé
  máy bay; câu hỏi tiếp sau khi trả lời; chỉ câu chọn vé máy bay mới tiếp sau khi hỏi loại vé; câu xin lập lịch/đặt/đổi
  không phải câu hỏi giá), `detected` bỏ chặn khi đã có lịch, `answer_text` (rẻ nhất hoặc đắt nhất; có ngày đi thì so với
  cả đợt mở bán), `anywhere_text`/`_origin_routes` (so các tuyến từ nơi đi), `answer` giữ `pending_fare` sau khi trả lời,
  không đổi `intent` khi đã có lịch.
- `src/backend/app/agents/steps/messages.py` — sửa: khoá `fare_*`, `chip_kind_*`, `chip_fare_*` mới (vi, en); bỏ `fare_on_day`,
  `fare_other_day` (thay bằng bản theo rẻ nhất/đắt nhất).
- `src/backend/tests/unit/agents/test_fares.py` — sửa 2 test theo hành vi mới (đã có lịch vẫn trả lời giá vé; sau khi trả lời
  `pending_fare` giữ tuyến).
- `src/backend/tests/unit/agents/test_fares_followups.py` — thêm: 14 test.
- `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md` — sửa: luật giá vé, các dạng `pending_fare`.
- `docs/prd/update/2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md` — sửa: ghi phần hỏi giá vé đã chốt và áp dụng.
- `history/2026-10-10-cau-hoi-ve-hoi-lai-va-nho-ngu-canh.md` — thêm: entry này.

## Quyết định

Người dùng giao agent tự chốt (chat 10/10):
- "vé" chưa rõ loại thì **hỏi lại** (không mặc định vé máy bay), theo ghi chú của người dùng.
- Câu **hỏi** giá vé sau khi có lịch trả lời bằng luật theo tuyến của chuyến, trả `NEEDS_CLARIFICATION`, lịch giữ nguyên;
  không làm node `follow_up` và không lưu dữ liệu đã tra như đề xuất đầy đủ (phần đó vẫn chờ chốt).
- Hỏi giá vé không bao giờ gọi LLM; trả lời 0,2–0,5 giây.

## Kiểm tra

- `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain`: 1932 passed.
- Backend local (`inprocess`, LLM thật, catalog snapshot 30/09, hôm nay 10/10):
  - "giờ tao đi hà nội thì vé nào rẻ" → hỏi "vé máy bay ra Hà Nội, phòng khách sạn hay vé tham quan ở Hà Nội?" + 3 nút;
    "tao hỏi vé máy bay mà" → hỏi nơi đi (0,5 giây); "từ Sài Gòn" → 630.000 ₫ ngày 03/11; "đắt nhất thì soa" → 2.385.000 ₫
    ngày 07/11 (0,2 giây); "đi đâu cũng được, miễn đắt nhất" → so tuyến từ TP. Hồ Chí Minh (Hà Nội, Hải Phòng, Nghệ An, Huế).
  - Đã có lịch Hà Nội 15/10: "giá máy báy đó rẻ nhất chưa" → "Ngày 15/10 chưa có chuyến… cả đợt (tới 07/11) rẻ nhất 630.000 ₫
    ngày 03/11" (0,2 giây, không lập lại lịch); "đắt nhất thì soa" → 2.385.000 ₫; "đổi khách sạn khác" sau đó vẫn dùng lịch cũ.

## Còn lại / rủi ro

- Chỉ vé một chiều; vé khứ hồi chưa nêu.
- Lỗi thấy khi chạy: "Lập lịch Hà Nội 3 ngày từ 16/10/2026…" trả `FALLBACK` vì `ValueError: full-day overlap` ở
  `domain/itinerary/planning.render_proposal` (không thuộc thay đổi này; ghi để sửa riêng).
