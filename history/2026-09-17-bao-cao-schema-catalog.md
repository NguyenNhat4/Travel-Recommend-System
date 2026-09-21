# Báo cáo schema thống nhất catalog, CDP clone và API

- Ngày: 2026-09-17
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: data
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người yêu cầu cần một báo cáo đầy đủ về schema và quan hệ giữa `products.jsonl`, CDP clone (bản một database trên
nhánh `data`), `CdpClient` và OpenAPI 1.2.0, kèm các chỗ các tầng đang lệch nhau để thống nhất.

## File thay đổi

- `src/data_collection/docs/bao-cao-schema.md` — thêm: sơ đồ tầng, định danh, ERD và 15 quan hệ, từ điển 11 bảng, ánh xạ catalog ↔ database ↔ API, 23 chỗ lệch X1–X23, ma trận 121 khoá `attributes`, enum, lệnh tái tạo số liệu.

## Quyết định

- Số liệu đếm trực tiếp trên `data/recsys/products.jsonl` (10.000 dòng), không lấy từ `SCHEMA.md` vốn viết cho 2.216 dòng.
- Đề xuất thứ tự ưu tiên khi mâu thuẫn: handbook §6 → OpenAPI → baseline 1.1 / MVP 1.2 → hợp đồng Backend → `SCHEMA.md`.
- Phần coi CDP clone là một database chung đã bị thay bởi `2026-09-17-thiet-ke-schema-3-service.md`; phần catalog vẫn dùng được.

## Kiểm tra

- Render 3 sơ đồ Mermaid bằng mermaid@11: pass.
- Soát số cột của 32 bảng markdown: pass.
- Chạy đoạn Python ở Phụ lục C trên `data/recsys/products.jsonl`: 10.000 dòng đủ 13 khoá, 10.000 `productId` khớp UUIDv5 của `sourceRef`, 0 bản ghi con mồ côi.
- `python3 -m unittest discover -s tests -p 'test_expand_catalog.py'` (trong `src/data_collection`): 19 test pass. `test_overnight` và `test_quality` không import được vì Python hệ thống thiếu `bs4`.

## Còn lại / rủi ro

- X2–X13 (phần catalog) chờ Backend, Search, Web chốt; chưa sửa `normalise.py`, `expand_catalog.py`, `SCHEMA.md`.
