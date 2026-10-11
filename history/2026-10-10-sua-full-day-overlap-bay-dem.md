# Tour cả ngày sau chuyến bay đêm không còn làm lịch thành FALLBACK ("full-day overlap")

- Ngày: 2026-10-10
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent (domain)
- Mã FR/NFR: FR-AGT-03, AC-AGT-02
- Liên quan: lỗi ghi ở `history/2026-10-10-cau-hoi-ve-hoi-lai-va-nho-ngu-canh.md` mục "Còn lại"

## Mục tiêu

"Lập lịch Hà Nội 3 ngày từ 16/10/2026, 2 người lớn, bay từ TP. Hồ Chí Minh, ngân sách 15 triệu" trả `FALLBACK` "Bước xếp
lịch gặp lỗi hệ thống" (`ValueError: full-day overlap` ở `render_proposal`).

Nguyên nhân (log tạm của slot ngày lỗi, đã gỡ): chuyến bay 22:55 ngày 1 hạ cánh rạng sáng ngày 2, nên `day_windows` ghi
ngày 2 còn trọn ngày (`full_day = true`) kèm dòng `ARRIVAL` buổi sáng. `compose_plan` vì vậy xếp tour Ninh Bình 600 phút vào
ngày 2; `_layout` đặt dòng đến nơi trước tour (cùng buổi sáng), và `render_proposal` coi dòng di chuyển là "ngày đã có hoạt
động" nên ném lỗi.

## File thay đổi

- `src/backend/app/domain/itinerary/planning.py` — sửa: `render_proposal` chỉ đếm slot có sản phẩm khi kiểm luật hoạt động
  cả ngày; dòng di chuyển (đến nơi, ra sân bay, đổi khách sạn) không tính.
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — thêm: 2 test (tour cả ngày sau dòng đến nơi dựng được và
  qua `validate_plan`; tour cả ngày vẫn không chung ngày với hoạt động khác).
- `history/2026-10-10-sua-full-day-overlap-bay-dem.md` — thêm: entry này.

## Quyết định

- Sửa ở bước kiểm (`render_proposal`) cho khớp bước xếp (`compose_plan` đã cho phép tour cả ngày ở ngày còn trọn ngày dù có
  dòng đến nơi), không đổi bước xếp.

## Kiểm tra

- Test mới fail trên code cũ, pass sau khi sửa. `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain`: pass.
- Backend local, LLM thật: đúng câu trên → `COMPLETED` (vé khứ hồi VJ1140/VJ165, ngày 2: "Di chuyển từ sân bay" rồi tour Ninh
  Bình), log không còn `itinerary.composition_failed`.

## Còn lại / rủi ro

- Không có.
