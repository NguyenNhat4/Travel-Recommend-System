# Thiết kế schema ba service: Backend, CDP clone, Insider clone

- Ngày: 2026-09-17
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: data
- Trạng thái: hoàn thành
- Phạm vi: docs
- Thay thế: `2026-09-17-bao-cao-schema-catalog.md` (phần CDP clone một database)
- Bị thay thế bởi: `2026-09-20-database-mock-data-tuan-1.md` (phần "ba service, mỗi service một database"; CDP clone nay là schema `cdp` trong database `vota`)

## Mục tiêu

Vẽ lại schema theo các hợp đồng trên `origin/data_contract` (`0f630a2`), với Backend, CDP clone và Insider clone là
ba service riêng, mỗi service một database.

## File thay đổi

- `docs/spec/thiet-ke-schema-3-service.md` — thêm: dữ liệu thuộc service nào, ERD và từ điển bảng cho database `app`, `cdp`, `insider`; quan hệ xuyên service; luồng checkout; kế hoạch chuyển code `src/data_collection/cdp`; 10 câu hỏi chờ xác nhận.
- `src/data_collection/docs/bao-cao-schema.md` — sửa: thêm ghi chú đầu file trỏ sang thiết kế mới và nêu phần nào bị thay.

## Quyết định

- Giữ quy tắc tạm của `hop-dong-tich-hop-cdp.md` §11: `products`, `users`, `bookings`, `product_vectors` ở database Backend; CDP clone chỉ có `events`, `profiles` đúng như `src/cdp_clone` revision `0001`.
- Không outbox, không transaction xuyên service; `purchase` ghi đồng bộ trước commit và huỷ bù trừ khi commit lỗi (`hop-dong-tich-hop-cdp.md` §5, §13).
- Đề xuất `uuid` cho ID gửi sang service khác: `purchase:{bookingItemId}` bị trùng sau khi reset database Backend sẽ bị CDP trả `duplicate`, booking vẫn commit nhưng event mới không được ghi.
- Đề xuất xoá mềm `products` (`deleted_at`) để `because[].productName` còn tên khi sản phẩm rời catalog, vì event CDP không mang tên sản phẩm.
- Schema Insider clone là đề xuất vì chưa có hợp đồng: bảng theo handbook §6, tên trường theo API Insider thật (Upsert User Data, Update Identifiers, Get User Profiles, Export Raw User Data).
- Không đổi OpenAPI, mock hay code.

## Kiểm tra

- Render 5 sơ đồ Mermaid (flowchart, 3 ERD, sequence) bằng mermaid@11: pass.
- Soát số cột của 15 bảng markdown: pass.
- `validate_contract.py`: không chạy, vì không đổi contract hay mock; script cũng chưa có trên nhánh `data`.

## Còn lại / rủi ro

- Q1–Q10 ở §8 chờ Backend, CDP, Agent, Integration trả lời. Q1 và Q3 cần thêm endpoint vào `cdp-clone.openapi.yaml` trước khi code.
- Chưa sửa code: `src/data_collection/cdp/` vẫn là thiết kế một database. Cần merge `data_contract` vào `data` trước khi chuyển (§7 của thiết kế).
- Các thay đổi chưa commit khác trên nhánh `data` (`src/data_collection/cdp/*`, `expand_catalog.py`, `docs/EXPAND_CATALOG.md`, `cdp/seed_demo.py`, `tests/test_expand_catalog.py`, `README.md`, `docs/SCHEMA.md`) chưa có entry `history/`.
