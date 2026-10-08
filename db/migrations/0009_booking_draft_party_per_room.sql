-- Khách sạn tối đa 9 khách mỗi phòng và 9 phòng mỗi mục, nên một mục của đơn nháp có thể tới 81 khách
-- và đoàn khai ở checkout tới 81 người (docs/prd/requirements.md FR-BKG-08). Giỏ không nhận khách sạn nên
-- app.cart_items giữ trần 9.
-- Idempotent: bỏ ràng buộc cũ rồi thêm ràng buộc mới, chạy lại không đổi gì.
ALTER TABLE app.booking_draft_items DROP CONSTRAINT IF EXISTS booking_draft_items_party_size;
ALTER TABLE app.booking_draft_items ADD CONSTRAINT booking_draft_items_party_size CHECK (adults + children <= 81);

ALTER TABLE app.booking_travelers DROP CONSTRAINT IF EXISTS booking_travelers_position_check;
ALTER TABLE app.booking_travelers DROP CONSTRAINT IF EXISTS booking_travelers_position_range;
ALTER TABLE app.booking_travelers ADD CONSTRAINT booking_travelers_position_range CHECK (position BETWEEN 1 AND 81);
