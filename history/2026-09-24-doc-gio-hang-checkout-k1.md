# Viết đặc tả kỹ thuật cho giỏ hàng/checkout/K1

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu viết tài liệu kỹ thuật giúp các dev khác hiểu tính năng vừa làm ở commit `8cf8511`
(nối vòng đặt chỗ → gợi ý K1). Không phải hợp đồng đang thương lượng, mà là bản đọc-hiểu-triển-khai: bản đồ
module, vì sao mỗi quyết định kỹ thuật được chọn, đường dữ liệu đầy đủ một lượt đặt, và bản đồ test.

## File thay đổi

- `docs/spec/gio-hang-checkout-va-vong-lap-k1.md` — thêm: đặc tả kỹ thuật giỏ/checkout/K1, phục vụ
  FR-BKG-01…04, FR-REC-02, FR-CAT-02, AC-BKG-01, AC-REC-02.

## Quyết định

- Đặt trong `docs/spec/` thay vì `docs/guide/`: nội dung mô tả thiết kế kỹ thuật của một phần hệ thống (giỏ
  hàng/checkout), đúng định nghĩa "spec" ở `AGENTS.md` §7, trong khi `docs/guide/` (đề xuất
  `docs/prd/update/2026-09-24-them-thu-muc-docs-guide.md`) còn "chờ chốt" và dành cho hướng dẫn đọc code
  chung toàn repo, không phải đặc tả một module. Đặt ở `docs/spec/` không cần chờ đề xuất đó.
- Không tạo file mới ở nơi khác trong repo (AGENTS.md §7).

## Kiểm tra

- Không đổi code/contract/DDL nên không cần `validate_contract.py` hay `db/verify.sql`.
- Đối chiếu thủ công nội dung tài liệu với code đã commit (`domain/booking/`, `application/booking/`,
  `infrastructure/persistence/postgres_{cart,bookings,catalog}.py`, `services/booking.ts`) — khớp.

## Còn lại / rủi ro

- Không có.
