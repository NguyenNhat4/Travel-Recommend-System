# Đề xuất: job cào dời ngày vé máy bay vào cửa sổ, vé luôn đặt được

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl (soạn trên bench_search_recomSys, chuyển sang cùng ngày)
- Trạng thái: hoàn thành (đã chốt 06/10, áp dụng ở 2026-10-06-ap-dung-doi-ngay-ve-va-gom-code-cao.md)
- Phạm vi: docs, data

## Mục tiêu

Người dùng muốn vé máy bay luôn đặt được và cập nhật theo ngày như hạng phòng, vì team Web cần dữ liệu dùng được. `docs/prd/data-model.md` §3.1 hiện cấm job cào dời ngày vé ngày cố định, nên phải đề xuất trước (AGENTS §8). Phục vụ FR-CAT-01, FR-CAT-03.

## File thay đổi

- `docs/prd/update/2026-10-06-job-cao-doi-ngay-ve-vao-cua-so.md` — thêm: đề xuất áp quy tắc dời ngày của seed demo cho job cào.

## Quyết định

- Dùng lại đúng quy tắc seed đã chốt 29/09 (dời vào `as_of + crc32 % 30`, hai chặng cùng số ngày, giá giữ làm giá tham khảo, `priceValidUntil` giữ nguyên), không đặt quy tắc mới.
- Chưa sửa code: chờ người dùng chốt.

## Kiểm tra

- Không có (chỉ tài liệu). Số liệu trong đề xuất lấy từ truy vấn chỉ đọc DB VM ngày 06/10 (xem `2026-10-06-sua-loi-nap-db-job-cao-va-bat-lai-theo-cua-so.md`).

## Còn lại / rủi ro

- Chờ chốt. Sau khi chốt: cập nhật PRD trước, rồi sửa `fresh_catalog_db.py`, test, spec, README theo mục "Thay đổi source" của đề xuất.
- Cần thống nhất với team Web cách hiển thị giá của vé đã dời (`fareClasses` báo `EXPIRED`).
