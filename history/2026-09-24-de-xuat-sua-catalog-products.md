# Đề xuất sửa `catalog.products` thành `cdp.products` trong PRD

- Ngày: 2026-09-24
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: dang dở
- Phạm vi: docs

## Mục tiêu

Người yêu cầu phát hiện schema database lệch với PRD. Khi đối chiếu thì thấy PRD tự mâu thuẫn. ERD `data-model.md` §2.1, `architecture.md` §2 và `deployment-plan.md` §2 đặt bảng sản phẩm ở `cdp.products`, khớp DDL. Ba chỗ khác lại nhắc tới `catalog.products`, một bảng không tồn tại:

- `data-model.md` §1, sơ đồ ASCII
- `data-model.md` §2.2, chú thích `APP_BOOKING_ITEMS.product_id`
- `test-plan.md` §2.4, tiêu chí Grounding Rate

Người yêu cầu bảo soạn đề xuất sửa ba chỗ này thành `cdp.products`.

## File thay đổi

- `docs/prd/update/2026-09-24-sua-catalog-products-thanh-cdp-products.md` — thêm: đề xuất sửa ba chỗ trên, trạng thái `chờ chốt`. Theo yêu cầu bổ sung, mục "Thay đổi source sau khi chốt" liệt kê cả các sơ đồ spec có nhắc bảng sản phẩm: §3, §6.1 và §6.2 của spec booking; spec auth không có sơ đồ nào như vậy.

## Quyết định

- Đề xuất chỉ sửa chữ cho khớp ERD §2.1 và DDL. Không đổi thiết kế: `cdp.products` là mirror 13 trường của CDP thật (handbook §6), còn `catalog` chỉ chứa dữ liệu dựng lại được từ bảng này.
- Không sửa `docs/prd/` hay `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` (nút `D2` cũng ghi `catalog.products`) trước khi đề xuất được chốt (AGENTS.md §8).
- Hai điểm lệch liên quan được ghi vào mục "Ngoài phạm vi" của đề xuất để người chốt quyết định riêng, không gộp vào đề xuất này:
  - Bản clone có FK thật `app.*.product_id → cdp.products`, trong khi PRD ghi "tham chiếu logic" và có quy tắc cấm FK chéo schema.
  - Cột `catalog`/`app` trong sơ đồ §1 thiếu hoặc sai tên một số bảng so với DDL.

## Kiểm tra

- `grep -rn "catalog\.products"` toàn repo (trừ `history/`, `node_modules`, `.git`): đúng 3 chỗ, gồm `docs/prd/test-plan.md:66`, `docs/prd/data-model.md:182` và `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md:325`. Sơ đồ ASCII ở `data-model.md:16` ghi `products` dưới cột `catalog`, không có tiền tố.
- Code đã đọc `cdp.products`: `postgres_catalog.py:23`, `postgres_store.py:36`, `src/evaluation/agent/grounding.py:38`. Không cần sửa code, contract hay DDL.
- Không chạy `validate_contract.py`: không đổi contract hay mock.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất. Sau khi chốt:
  1. Sửa `docs/prd/data-model.md` §1, §2.2 và `docs/prd/test-plan.md` §2.4.
  2. Sửa sơ đồ §3 (nút `P`), §6.1 (bước đọc sản phẩm) và §6.2 (nút `D2`, thêm cạnh `F6`/`F7 → D2`) trong `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md`.
  3. Đổi trạng thái đề xuất và `git mv` nó sang `docs/prd/update-archive/`.
  4. Ghi entry `history/` mới.
