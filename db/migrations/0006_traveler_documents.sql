-- 0006_traveler_documents — giấy tờ hành khách cho vé máy bay (FR-BKG-13)
--
-- Áp lên database ĐÃ CÓ DỮ LIỆU. Nội dung phải khớp db/init/01_vota.sql; mọi lệnh đều idempotent.
-- KHÔNG viết BEGIN/COMMIT ở đây: run.py đã bọc mỗi file trong một transaction.

-- Khối {title, nationality, docType, docNumber, docExpiry, escortTravelerRef}; chỉ có khi đơn có vé bay.
-- Số giấy tờ không ra khỏi database ở dạng đầy đủ (API trả 4 số cuối), không gửi CDP, Insider, Stripe.
ALTER TABLE app.booking_travelers ADD COLUMN IF NOT EXISTS documents jsonb;
