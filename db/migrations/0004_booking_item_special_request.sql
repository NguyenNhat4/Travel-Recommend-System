-- 0004_booking_item_special_request — yêu cầu riêng của từng dòng đơn (contract BookingItem.specialRequest)
--
-- Contract đã có specialRequest theo từng dòng nhưng DDL chỉ có special_request ở cấp đơn. Thêm cột cho khớp.
-- Nội dung phải khớp db/init/01_vota.sql. KHÔNG viết BEGIN/COMMIT: run.py đã bọc mỗi file trong một transaction.

ALTER TABLE app.booking_items ADD COLUMN IF NOT EXISTS special_request text;
