# Áp dụng đề xuất sửa `catalog.products` thành `cdp.products`

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất `docs/prd/update-archive/2026-09-24-sua-catalog-products-thanh-cdp-products.md`. Entry này áp dụng đề xuất đó và làm nốt phần "Còn lại" của `history/2026-09-24-de-xuat-sua-catalog-products.md`. Mục đích: PRD và sơ đồ spec booking gọi bảng sản phẩm là `cdp.products`, khớp ERD `data-model.md` §2.1 và DDL. Trước đó ba chỗ trong PRD và một nút trong spec booking vẫn ghi `catalog.products`, một bảng không tồn tại.

## File thay đổi

- `docs/prd/data-model.md` — sửa: §1 sơ đồ lưu trữ chuyển `products` từ cột `catalog` sang cột `cdp`; §2.2 chú thích `APP_BOOKING_ITEMS.product_id` thành "Tham chiếu logic tới cdp.products".
- `docs/prd/test-plan.md` — sửa: §2.4 Grounding Rate kiểm ID sản phẩm trong `cdp.products`.
- `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` — sửa:
  - §3: nút `P` thêm dòng "+ đọc cdp.products".
  - §6.1: bước đọc tách rõ phần `app.*` và phần `cdp.products` chỉ đọc.
  - §6.2: nút `D2` thành `cdp.products` chỉ đọc; thêm cạnh `F6 -.-> D2` và `F7 -.-> D2`.
- `docs/prd/update/2026-09-24-sua-catalog-products-thanh-cdp-products.md` → `docs/prd/update-archive/2026-09-24-sua-catalog-products-thanh-cdp-products.md` — đổi tên: trạng thái `đã áp dụng`, chốt bởi mihhquan ngày 2026-09-24. File chưa được git theo dõi nên dùng `mv` thay cho `git mv`.

## Quyết định

- Sửa đúng nội dung đã chốt, theo thứ tự AGENTS.md §8: PRD trước, spec sau. Không sửa code, contract hay DDL, vì các chỗ này đã dùng `cdp.products`.
- Các mục "Ngoài phạm vi" của đề xuất chưa làm và cần đề xuất riêng nếu muốn xử lý:
  - FK thật `app.*.product_id → cdp.products` trong bản clone.
  - Tiêu đề quy tắc cấm FK chéo schema ở `data-model.md` §1.
  - Các bảng thiếu hoặc sai tên trong sơ đồ §1.

## Kiểm tra

- `grep -rn "catalog\.products"` toàn repo (trừ `history/`, `docs/prd/update-archive/`, `node_modules`, `.git`): không còn kết quả.
- Chưa kiểm render mermaid: máy không có `mmdc`. Các sửa đổi chỉ đổi nhãn và thêm hai cạnh giữa các nút đã có.
- Không chạy `validate_contract.py`: không đổi contract hay mock.

## Còn lại / rủi ro

- Không có.
