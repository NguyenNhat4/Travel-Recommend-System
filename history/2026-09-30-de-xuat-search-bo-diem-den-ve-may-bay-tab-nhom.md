# Đề xuất chỉnh trang /search: bỏ điểm đến, bỏ vé máy bay, tab theo nhóm

- Ngày: 2026-09-30
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: dang dở
- Phạm vi: docs, frontend
- Bị thay thế bởi: 2026-09-30-search-tab-nhom-hang-cuon-ngang.md

## Mục tiêu

Người dùng yêu cầu sửa `/search` (tìm kiếm ngữ nghĩa): bỏ bộ lọc Điểm đến, bỏ vé máy bay, đổi tab thành Tất cả · Lưu trú · Tour và trải nghiệm · Tiện ích khác, "Tất cả" là các hàng cuộn ngang theo nhóm, và chỉ sắp xếp giá trong cùng loại. Phục vụ FR-SRC-01, FR-SRC-03. Các thay đổi này lệch PRD nên theo `AGENTS.md` mục 8 phải có đề xuất được chốt trước khi sửa source.

## File thay đổi

- `docs/prd/update/2026-09-30-trang-search-bo-diem-den-ve-may-bay-va-tab-theo-nhom.md` — thêm: đề xuất, trạng thái `chờ chốt`.

## Quyết định

- Chưa sửa source: FR-SRC-03 (lọc địa điểm), `user-flow.md` §2 và `product.md` §4.2 (tab có Vé máy bay, lọc điểm đến) đều bị lệch.
- Đã đọc: `docs/prd/README.md`, `history/README.md`, `requirements.md` §1.2, `user-flow.md` (mục `/search`), `product.md` §4.2, frontend spec §4.2, `SearchView.tsx`, `services/search.ts`, `navConfig.ts`, `searchHref.ts`, entry `2026-09-29-trien-khai-trang-danh-muc-va-header.md`.

## Kiểm tra

- Không có thay đổi code nên không chạy test.

## Còn lại / rủi ro

- Chờ người dùng chốt, kèm hai điểm cần quyết: đường vào `/search?type=flight` từ `/flights`, và xử lý `?destination=` từ tấm tìm kiếm trang danh mục.
- Sau khi chốt: cập nhật PRD, sửa `SearchView.tsx` và `services/search.ts`, thêm test, chuyển đề xuất sang `update-archive/`.
