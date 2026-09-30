# Guide cho FE: hiển thị hạng vé máy bay (`fareClasses`)

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người yêu cầu muốn bàn giao cho team FE và team deploy bằng file đọc được trong repo thay vì tin nhắn dài. Team deploy đã
có `docs/guide/trien-khai-job-cao-du-lieu.md`; team FE chưa có trang hướng dẫn dùng `fareClasses` (contract 1.9.0).

## File thay đổi

- `docs/guide/hien-thi-hang-ve-may-bay.md` — thêm: trường thêm so với shape FE đưa, ví dụ payload, endpoint trả
  `fareClasses`, quy tắc hiển thị (mỗi hành trình một thẻ, `null` = chưa biết, `EXPIRED` không phải hết ghế, trip.com
  "Giá rẻ nhất"), vé khứ hồi, giỏ hàng không đổi.
- `history/2026-09-29-guide-hien-thi-hang-ve.md` — thêm: entry này.

## Quyết định

- Đặt ở `docs/guide/` (AGENTS.md §7 không cho tạo `README.md` mới); guide chỉ hướng dẫn, nguồn sự thật vẫn là contract và
  `docs/spec/hop-dong-tich-hop-backend.md` §2.2.1.
- Không đổi contract, code hay spec.

## Kiểm tra

- Đối chiếu `schemas/catalog.yaml`: `priceValidUntil` là `format: date`; `tripType`, `returnDate`, `returnFlight` có trong
  schema thuộc tính chuyến bay.

## Còn lại / rủi ro

- FE chuyển `FlightSummary` sang đọc `fareClasses`.
- Chưa commit (người yêu cầu tự commit / push).
