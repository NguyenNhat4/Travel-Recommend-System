# Lưu trữ đề xuất PRD đã xử lý sang docs/prd/update-archive

- Ngày: 2026-09-23
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu chuyển đề xuất đã chốt sang một folder khác, để agent không phải đọc lại những gì đã có trong PRD và `docs/prd/update/` không bị rối.

## File thay đổi

- `AGENTS.md` — sửa:
  - §1.1: chỉ đọc `docs/prd/update/` (đề xuất đang chờ, hoặc đã chốt nhưng chưa áp dụng); không cần đọc `update-archive/`.
  - §1.3, §4: bỏ yêu cầu tra `update/` cho đề xuất đã chốt; §4 thêm điều kiện đề xuất phải đã được lưu trữ.
  - §7: thêm dòng `docs/prd/update-archive/`.
  - §8 bước 4: đổi thành bước "Lưu trữ" — đề xuất đã áp dụng hoặc bị từ chối thì `git mv` sang `update-archive/`.
- `docs/prd/update/2026-09-23-nguyen-tac-lech-prd-phai-chot.md` → `docs/prd/update-archive/2026-09-23-nguyen-tac-lech-prd-phai-chot.md` — chuyển (đề xuất đã bị từ chối).
- `docs/prd/update/.gitkeep` — thêm: giữ folder trống trong Git.

## Quyết định

- Tên folder `docs/prd/update-archive/`, nằm ngoài `update/`, nên đọc `update/` sẽ không vô tình đọc cả phần đã lưu trữ.
- Đề xuất bị từ chối cũng được lưu trữ, không xoá, để giữ lý do từ chối.
- Đề xuất đã chốt nhưng chưa áp dụng vào PRD vẫn nằm trong `update/` cho tới khi áp dụng xong.

## Kiểm tra

- Không có lệnh kiểm tra tự động cho tài liệu. Đã kiểm tra `ls -A docs/prd/update docs/prd/update-archive`.

## Còn lại / rủi ro

- Không có.
