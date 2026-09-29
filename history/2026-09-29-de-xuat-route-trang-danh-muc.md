# Chốt và áp dụng đề xuất route trang danh mục dịch vụ

- Ngày: 2026-09-29
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: docs (prd)

## Mục tiêu

Người dùng chốt plan `docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md` ("Tôi chốt với đề xuất hãy hoàn thành plan"). Bốn route mới không có trong bảng route của PRD nên cần đề xuất được chốt trước khi sửa source (`AGENTS.md` §8). Phục vụ FR-CAT-01, FR-SRC-01, FR-SRC-03.

## File thay đổi

- `docs/prd/update-archive/2026-09-29-route-trang-danh-muc-dich-vu.md` — thêm: đề xuất, trạng thái `đã áp dụng`, chốt bởi mihhquan 2026-09-29; tạo rồi chuyển thẳng vào `update-archive/` (file chưa được git theo dõi nên dùng `mv`, không phải `git mv`).
- `docs/prd/user-flow.md` — sửa: §2 thêm bốn dòng `/hotels`, `/flights`, `/experiences`, `/combos`; §4.1 dòng thanh điều hướng của wireframe Trang chủ.

## Quyết định

- Coi lời chốt "với đề xuất" là chốt nội dung đề xuất PRD nêu trong plan (bốn route, thanh điều hướng bốn nhóm + Trợ lý AI) cùng giả định A1–A6. Nếu ý người dùng khác thì đổi ở đề xuất đã lưu trữ và `navConfig.ts`.
- Chỉ sửa hai chỗ ở `user-flow.md`; không đụng phần bị lặp §4.2–§4.4 và `/products/:id` (tồn đọng ghi trong plan).

## Kiểm tra

- Không có code; đọc lại hai đoạn đã sửa của `user-flow.md`.

## Còn lại / rủi ro

- Không có.
