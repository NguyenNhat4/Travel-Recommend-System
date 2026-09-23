-- 0002_drop_product_vectors — gỡ vector khỏi Postgres, chuyển sang Weaviate
--
-- Vector sản phẩm chuyển sang collection `Product` của Weaviate với model Cohere
-- embed-multilingual-v3.0 (1024 chiều). Lý do: database `vota` bị dựng lại mỗi vòng
-- `make demo-db`, nên vector nằm chung Postgres thì lần seed nào cũng phải embed lại
-- toàn bộ catalog. Weaviate có volume riêng nên vector sống độc lập với vòng seed.
-- Chi tiết: docs/prd/data-model.md §1 và §5, docs/prd/architecture.md §5.
--
-- Nội dung phải khớp db/init/01_vota.sql; khác biệt duy nhất là ở đây mọi lệnh đều
-- idempotent để chạy lại được.
--
-- KHÔNG viết BEGIN/COMMIT ở đây: run.py đã bọc mỗi file trong một transaction.

-- Bảng này là hộ dùng duy nhất của extension `vector`, nên gỡ được cả hai.
DROP TABLE IF EXISTS catalog.product_vectors;

-- Gỡ extension sau bảng. Nếu một object khác trong database còn dùng kiểu `vector`,
-- lệnh này sẽ lỗi (không có CASCADE) — đó là chủ ý: dừng lại để người chạy xem xét,
-- thay vì âm thầm xóa thứ mình không định xóa.
DROP EXTENSION IF EXISTS vector;
