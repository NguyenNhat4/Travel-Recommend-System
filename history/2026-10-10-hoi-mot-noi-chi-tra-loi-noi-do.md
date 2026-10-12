# Hỏi về một nơi cụ thể chỉ trả lời nơi đó (lỗi B, chat thử 10/10)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent
- Mã FR/NFR: FR-AGT-06 (đề xuất `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md`, đã chốt), NFR-REL-01
- Plan: `docs/plan/2026-10-10-sua-loi-chat-thu-tro-ly.md`, đơn vị 2

## Mục tiêu

"Văn Miếu buổi tối có mở không?" trả thẻ Văn Miếu kèm Hồ Hoàn Kiếm và hai khách sạn (tái hiện trên backend local, LLM
thật, catalog thật). Kịch bản bản 5 cảnh 9: chỉ trả lời về Văn Miếu.

## File thay đổi

- `src/backend/app/agents/steps/exploration.py` — sửa: `pick` trả mỗi thẻ `asked` khi câu hỏi về chính nơi đó; câu hỏi
  quanh nơi đó ("gần Văn Miếu có gì nữa?") trả các điểm tham quan gần nhất; `asked_only` vào payload LLM; nút dẫn tiếp
  "Gần <nơi> có gì nữa?", "<điểm đến> còn gì đáng đi?".
- `src/backend/app/domain/itinerary/exploration.py` — sửa: thêm `short_name`, `near_cards`, lý do `near`, `NEAR_KM = 3`.
- `src/backend/app/agents/steps/prompts.py` — sửa: `EXPLORE_PROMPT` thêm luật `asked_only` (trả lời thẳng trước, không
  câu mở đầu về thành phố) và lý do `near`.
- `src/backend/app/agents/steps/messages.py` — sửa: `chip_near`, `chip_more_sights`, `reason_near` (vi, en).
- `src/backend/tests/unit/agents/test_explore_asked_place.py` — thêm: 8 test.
- `history/2026-10-10-hoi-mot-noi-chi-tra-loi-noi-do.md` — thêm: entry này.

## Quyết định

- Nhận "câu hỏi về chính một nơi" bằng luật: có thẻ `asked`, không hỏi chỗ ở, không có từ "gần/quanh/cạnh". Hỏi khách sạn
  gần một nơi vẫn đi nhánh khách sạn như cũ.
- "Gần" = đường chim bay ≤ 3 km theo toạ độ catalog; thiếu toạ độ thì không đoán, rơi về cách chọn thẻ cũ.
- Người dùng giao agent tự chốt các điểm mở của đợt sửa này (chat 10/10).

## Kiểm tra

- `pytest src/backend/tests/unit/agents/test_explore_asked_place.py test_exploration.py`: 65 passed.
- Backend local (`inprocess`, Postgres + Weaviate local, e5-small local, LLM thật `gpt-6-luna`):
  - "Văn Miếu buổi tối có mở không?" 4/4 lần: một thẻ Văn Miếu, câu đầu "Có, … mở buổi tối 18:00–22:00"; trước sửa: 4 thẻ
    (Văn Miếu, Hồ Hoàn Kiếm, 2 khách sạn).
  - "Gần Văn Miếu có gì nữa?": Phố Đường Tàu, Hoàng Thành Thăng Long, Lăng Bác; không lặp Văn Miếu, không khách sạn.

## Còn lại / rủi ro

- Lời dẫn còn lặp "ngay gần đó" ở mỗi dòng: xử lý ở lỗi A (lời dẫn kể chuyện, không lặp).
