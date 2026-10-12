# Lời dẫn khám phá kể chuyện, đủ ý, không lặp cụm khen (lỗi A, chat thử 10/10)

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent
- Mã FR/NFR: FR-AGT-06 (đề xuất `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md`, đã chốt), NFR-REL-01
- Plan: `docs/plan/2026-10-10-sua-loi-chat-thu-tro-ly.md`, đơn vị 1

## Mục tiêu

Người dùng: mô tả thẻ khám phá (vd. sau "không thích đi Nha Trang") ngắn, khô, lặp "được khen nhiều"/"nhiều người ghé",
không có câu chuyện. Tái hiện trên backend local: hai dòng liền nhau cùng kết bằng "nhiều người ghé"; dòng khách sạn chỉ
còn "giá mềm".

## File thay đổi

- `src/backend/app/agents/steps/prompts.py` — sửa: `EXPLORE_PROMPT` viết như người bạn địa phương kể chuyện: câu mở đầu
  tạo không khí; mỗi thẻ 2–3 câu (nơi đó là gì, khoảnh khắc đáng trải nghiệm, hợp với ai, mẹo nhỏ); khách sạn kể về kỳ nghỉ
  từ `highlights`; cụm khen tối đa một lần; thẻ ít dữ liệu viết một câu, không than thiếu dữ liệu; không nghi ngờ vị trí thẻ.
- `src/backend/app/agents/steps/exploration.py` — sửa: `ABOUT_CHARS` 360 → 700; thẻ có `highlights` (tiện ích thật); tên
  thẻ bỏ dấu cách thừa; `once_praise` giữ mỗi cụm khen lần đầu, bỏ các lần sau (luật, sau LLM); gộp dòng trống; câu mô tả
  chỉ nhắc lại tên ("Bảo tàng Gấu Teddy tại An Giang") không dùng làm dòng dự phòng.
- `src/backend/tests/unit/agents/test_explore_storytelling.py` — thêm: 11 test.
- `history/2026-10-10-loi-dan-kham-pha-ke-chuyen.md` — thêm: entry này.

## Quyết định

- Không lặp cụm khen được chặn bằng luật (`once_praise`) chứ không chỉ dặn prompt: LLM thật vẫn lặp khi chỉ có lời dặn.
- Vẫn cấm số, giờ, điểm đánh giá trong câu chat (trừ thẻ `asked`, `price_asked`) như đã chốt ở
  `history/2026-10-10-loi-dan-kham-pha-va-hoi-gia-ve.md`.

## Kiểm tra

- `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain`: 1918 passed.
- Backend local (`inprocess`, LLM thật `gpt-6-luna`, catalog snapshot 30/09): "Cứ chọn đại một nơi đi" → "không thích, chỗ
  khác đi", "Đà Nẵng có gì chơi?", "Phú Quốc có gì chơi?" ×3, "Nha Trang có gì hay?" → "không thích đi Nha Trang": mỗi thẻ
  2–3 câu có cảnh, thời điểm, đối tượng; không còn cụm khen lặp; khách sạn kể về hồ bơi, spa, bữa sáng. Thời gian 4,7–7,5
  giây (lượt đầu sau khởi động 19–22 giây).

## Còn lại / rủi ro

- Mô tả catalog của vài điểm rất mỏng (hòn Thơm chỉ có nhãn "cảnh đêm"), nên đoạn của chúng vẫn ngắn.
- Catalog ghi Bảo tàng Gấu Teddy "tại An Giang" (tỉnh mới của Phú Quốc): dữ liệu, không sửa ở agent.
