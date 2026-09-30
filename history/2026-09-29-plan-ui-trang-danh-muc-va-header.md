# Plan: trang danh mục dịch vụ và thanh điều hướng mới theo bố cục VP-OTA

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành (chỉ tài liệu; chưa có dòng code nào được sửa)
- Phạm vi: docs (frontend)

## Mục tiêu

Người dùng cung cấp file HTML trang khách sạn của VP-OTA làm mẫu bố cục và nêu hai vấn đề: Home đang gọi tất cả dữ liệu cùng lúc, và các nút header như "Di chuyển", "Tour và trải nghiệm" chưa có nội dung. Yêu cầu: xây UI theo mẫu, đầu ra của bước này là **một file `.md` trong `docs/plan/`**.

## File thay đổi

- `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md` — thêm: plan gồm hiện trạng đo từ code, sáu giả định cần xác nhận, thiết kế header/trang danh mục/Home tải lười, các bước P0–P6, kế hoạch kiểm thử, tài liệu cần cập nhật, rủi ro.

## Quyết định

- **Chỉ viết plan, không code.** Người dùng chốt đầu ra là plan; các bước P1–P6 làm sau, mỗi bước một entry và một commit.
- **P4 (route mới) bị gác bởi đề xuất PRD.** Bảng route ở `docs/prd/user-flow.md` §2 chưa liệt kê `/hotels`, `/flights`, `/experiences`, `/combos`; theo `AGENTS.md` §8 cần đề xuất trong `docs/prd/update/` được chốt trước khi sửa source. Đề xuất chưa tạo (nằm ở bước P0 của plan); P1–P3 không lệch PRD nên làm được ngay. Mọi `href` nằm ở `navConfig.ts` nên đổi sang route mới hoặc quay lại `/search?type=…` chỉ là một chỗ sửa.
- **Chỉ lấy bố cục và hành vi từ mẫu.** Không lấy logo, ảnh, khẩu hiệu, thông tin pháp nhân, màu, font, script theo dõi. Câu phụ đề hero hiện trong `HomeView.tsx` đang chép nguyên từ mẫu, plan ghi rõ sẽ viết lại. Email và ID người dùng có trong HTML mẫu không được đưa vào plan.
- **Ngày và số khách trên tấm tìm kiếm không phải bộ lọc phòng trống:** grep `src/backend` không thấy xử lý `travelContext`/`CHECK_DATE_RANGE` dù contract có khai báo, nên plan không gửi các trường đó và chỉ mang ngữ cảnh qua URL tới hộp đặt.
- **Không thêm dependency** (TanStack Query, nuqs); dùng hai hook nhỏ `useInView`, `useLazySection`.
- **Code mới đặt trong `features/`** theo `architecture.md` §6.2 và `AGENTS.md` §3; file cũ sửa tại chỗ, không di chuyển (nhất quán entry 2026-09-25).

## Kiểm tra

- Chưa chạy lệnh kiểm tra nào: không có thay đổi code, contract hay mock, nên `validate_contract.py` không áp dụng.
- Số request "trước" trong plan được đọc từ mã (`HomeView.tsx`), **chưa đo trên trình duyệt**; bước P0 của plan có việc đo lại.
- Đã đối chiếu với code các điểm plan nêu: nav header cứng `/search?type=…` và ẩn dưới 1024 px, danh sách điểm đến/khách sạn cứng trong `HomeView.tsx`, `SearchView` chỉ đọc `q`/`type`/`destination`, `search.ts` mặc định `'khách sạn'`, footer toàn `navigate('/')`.

## Còn lại / rủi ro

- Người dùng cần xác nhận sáu giả định A1–A6 trong plan (ánh xạ nhóm header ↔ danh mục, Home là trang tổng quan, nút Trợ lý AI, bỏ chuông/V-Points, ngữ nghĩa ngày/số khách, banner CTA).
- Cần tạo và chờ chốt `docs/prd/update/2026-09-29-route-trang-danh-muc-dich-vu.md` trước P4.
- Chưa xác nhận `sort=price_asc` xếp `unitPrice: null` ở đâu; `/destinations` không tách theo danh mục và không có ảnh (chi tiết ở mục Rủi ro của plan).
- Chưa đọc `contracts-guide.md`, `api-contract.md`, `hop-dong-tich-hop-backend.md` vì plan không đổi API; phải đọc nếu phạm vi đổi.
