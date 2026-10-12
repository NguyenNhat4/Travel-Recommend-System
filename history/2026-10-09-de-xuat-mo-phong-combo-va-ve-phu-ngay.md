# Đề xuất dữ liệu mô phỏng: vé máy bay phủ đủ ngày, sản phẩm cho mọi thành phần combo

- Ngày: 2026-10-09
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `feat/mock-combo-ve-bay` (worktree local `~/code/trp-mock-combo`, tách từ `origin/release-mvp-v2 @ 1515020`; chưa commit)
- Trạng thái: dang dở (đề xuất chờ chốt; chưa sửa source, chưa ghi DB)
- Phạm vi: docs, data

## Mục tiêu

Người dùng yêu cầu mock thêm vé máy bay (một chiều và khứ hồi) phủ đủ ngày, và đủ sản phẩm cho các thành phần combo (phòng, vé máy bay,
vé tham quan…) vì bước thanh toán sẽ tách combo; kiểm tra DB production rồi làm. FR-CAT-03, FR-CAT-04.

## File thay đổi

- `docs/prd/update/2026-10-09-mo-phong-thanh-phan-combo-va-ve-phu-ngay.md` — thêm: đề xuất (lệch FR-CAT-03 "không tự tạo giá"), chờ chốt.
- `history/2026-10-09-de-xuat-mo-phong-combo-va-ve-phu-ngay.md` — thêm: entry này.

## Quyết định

- Kiểm tra production chỉ đọc (09/10): 76/112 tuyến chỉ có vé 1–5 ngày trong 30 ngày; 2.903 (tuyến, ngày) thiếu vé một chiều,
  2.885 thiếu khứ hồi; 147 combo đang bán có 334 thành phần, 93 trỏ tới sản phẩm đặt được.
- Lựa chọn của người dùng (09/10): thành phần vé máy bay trỏ tới tuyến + phủ vé mọi ngày; giá thành phần chia đúng giá combo; sản phẩm mô
  phỏng của combo ẩn khỏi tìm kiếm / gợi ý; ghi DB production trước, sửa job sau.
- "Phòng" trong yêu cầu = phòng trong thành phần combo (người dùng làm rõ), không phải 368 khách sạn Agoda chưa có phòng.
- Lệch PRD → AGENTS.md §8: viết đề xuất và dừng phần lệch tới khi người dùng chốt.

## Kiểm tra

- Chỉ truy vấn đọc trên DB production (kết nối `default_transaction_read_only=on`). Chưa chạy test (chưa có code).

## Còn lại / rủi ro

- Người dùng chốt / sửa / từ chối đề xuất. Chốt thì: cập nhật PRD trước, viết DDL + migration 0010, hai module job, test, chạy dry-run rồi
  ghi production (cần xác nhận lần nữa trước khi ghi).
- Trước khi job mới được deploy, lượt job 02:00 sẽ ghi đè liên kết combo đã ghi tay → phải chạy lại module sau mỗi lượt.

Bị thay thế bởi: 2026-10-09-mock-thanh-phan-combo-ve-phu-ngay-va-phong.md
