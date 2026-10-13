# Sửa test checkout lỗi ngẫu nhiên do UUID chứa chuỗi "2019"

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude Code (agent, Auto-fix PR #187)
- Nhánh: khoa/on-dinh-cd-staging-ha
- Trạng thái: hoàn thành
- Phạm vi: src/backend (test)

## Lý do

CI của PR #187 fail ở `test_personal_data_is_never_logged_and_never_sent_to_stripe_or_cdp`: assertion `"2019" not in repr(p)` sai khi `booking_item_id` (UUID ngẫu nhiên) tình cờ chứa `2019` (ví dụ `9102019f-…`). Lỗi không liên quan thay đổi CD của PR.

## File thay đổi

- `src/backend/tests/unit/application/booking/test_checkout_travelers.py` dòng 371: kiểm `"2019-05-12"` và `"2019, 5, 12"` thay vì `"2019"`.

## Kiểm tra

- Môi trường local thiếu pydantic nên không chạy được pytest; kiểm logic assertion bằng script độc lập (repr có UUID chứa "2019" không còn khớp; `date(2019, 5, 12)` vẫn bị bắt). Kết quả thật do CI của PR.
- Assertion kiểm cả `2019-05-12` và `2019, 5, 12` để vẫn bắt ngày sinh lọt vào dạng `date` repr.
