# Chọn phương án khách sạn bị chặn khi đoàn cần nhiều phòng

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Hội thoại "Lên lịch trình 3 ngày tại Phú Quốc, bắt đầu từ ngày 2026-10-15, cho 4 người lớn, ngân sách khoảng 0,5 triệu."
(LangSmith `nhat-10-7`, conversation `e7fb8709-8a23-4791-87a4-7de79851f21e` và `a00c4505-c4a7-4693-a75f-6efc27836476`):
bấm thẻ phương án nào widget cũng báo "Chưa đổi được khách sạn, bạn thử lại nhé." Cả 15 lượt `apply_option` đều bị
`finalize` chặn với `validation_issues = ["stays", "option_grounding", "option_grounding"]`; backend trả "Lịch trình chưa
vượt qua kiểm tra dữ liệu."

Nguyên nhân: từ `history/2026-10-09-ap-dung-khach-san-theo-so-phong.md`, `compose` tính `rooms = ceil(adults /
attributes.priceAdults)` trên candidate đầy đủ (4 người lớn → 2 phòng). Lượt chọn phương án dựng `candidates` từ các lịch
đã lưu (`option_swap.stored_products`), mà sản phẩm trong lịch chỉ là `summary`. `SUMMARY_ATTRIBUTE_KEYS` không có
`priceAdults`, nên `validate_plan` tính lại 1 phòng, khác `rooms: 2` đã lưu. Trace xác nhận: cùng khách sạn Sicily Hotel lúc
compose có 33 khoá `attributes`, lúc chọn chỉ còn 4. Đoàn 1–2 người lớn không bị vì cả hai phía đều là 1 phòng.

Phục vụ FR-AGT-03, AC-AGT-04, NFR-REL-01. Đây là sửa bug theo luật đã chốt, không lệch PRD.

## File thay đổi

- `src/backend/app/agents/steps/composition.py` — sửa: thêm `_stored_stay`; khách sạn lưu kèm lịch (`current_plan.stays`,
  `stay_options[i].stays`) giữ `priceAdults` của candidate.
- `src/backend/app/agents/steps/option_swap.py` — sửa: `stored_products` gắn lại `priceAdults` vào `attributes` của khách
  sạn trong `candidates` dựng từ lịch đã lưu.
- `src/backend/tests/unit/agents/test_option_swap.py` — sửa: thêm `test_a_group_needing_several_rooms_can_swap_and_swap_back`.
- `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md` — sửa: ghi chú grounding của lượt chọn giữ `priceAdults`.

## Quyết định

- Lưu `priceAdults` trong phần lịch lưu phía server (`stays` nội bộ), không thêm vào `summary`. Thêm vào `summary` sẽ làm
  response có thêm trường, tức đổi contract. `stay_options_payload` chỉ xuất `index`, `kmDelta`, `moneyDelta`,
  `overBudget`, `itinerary`, nên response không đổi.
- Không nới bước kiểm tra: `finalize` vẫn tính lại số phòng từ `priceAdults`, không tin `rooms` trong lịch.

## Kiểm tra

- Test mới chạy trên code cũ: fail với `(500, ['stays', 'option_grounding'])`, đúng như trace.
- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_option_swap.py`: 12 passed.
- `.venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests`: 2609 passed, 36 skipped.
- Tầng bằng chứng: fixture/tất định. Chưa chạy lại trên backend local với LLM thật.

## Còn lại / rủi ro

- Phải khởi động lại backend để nhận code mới.
- Hội thoại lưu trước bản sửa (lịch đã lưu không có `priceAdults`) vẫn không đổi được; cần mở hội thoại mới.
- Chạy lại câu 4 người lớn ở Phú Quốc trên web, bấm đổi rồi đổi lại, xem trace `apply_option` → `finalize` không còn
  `validation failed`.
