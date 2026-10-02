# Sửa pg_basebackup treo vì không đọc được file mật khẩu replicator

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude
- Nhánh: khoa/fix-replica-basebackup-secret
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng, CI/CD)

## Mục tiêu

Job `replication_staging` bị treo ở bước dựng replica: log lặp `Password:` hàng chục nghìn lần. Cần sửa gốc để CI tự nối được hai DB.

## File thay đổi

- `ops/bootstrap-db-replica.sh` — sửa: bước `pg_basebackup` đọc mật khẩu bằng root rồi hạ quyền bằng `gosu postgres`, thêm `-w`, kiểm mật khẩu không rỗng.
- `ops/tests/test_infra_layout.sh` — sửa: kiểm `pg_basebackup -w`, `gosu postgres`, và cấm dạng `PGPASSWORD=$(cat …)` trong cùng lệnh.

## Nguyên nhân

Log CI: `cat: /run/secrets/replicator_password: Permission denied`, rồi `Password:` lặp. Container chạy `--user postgres` nhưng file bind-mount là `root:root` mode 600. `PGPASSWORD=$(cat …) pg_basebackup` không bị `set -e` bắt khi `cat` lỗi (command substitution đứng trước lệnh), nên `pg_basebackup` chạy với mật khẩu rỗng và nhắc nhập mật khẩu. Không liên quan quyền `osAdminLogin`: SA CI đã có role này ở cấp project, và mô phỏng SSH + `sudo -n` bằng impersonate SA chạy tốt trên cả hai VM. Primary đã được chuẩn bị đúng ở lần chạy lỗi (role, slot, `pg_hba`); bước chuyển mật khẩu cũng thành công.

## Quyết định

- Đọc file bằng root trong container, hạ quyền bằng `gosu` (có sẵn trong image postgres) thay vì nới quyền file mật khẩu trên host.
- `-w` để thiếu hay sai mật khẩu thì thất bại ngay thay vì chờ nhập.
- Xử lý thủ công phần dư: dừng container `pg_basebackup` kẹt trên replica (CI bị huỷ không dừng được tiến trình trong VM); volume `vota-pg18` rỗng nên chạy lại an toàn.

## Kiểm tra

- `bash -n ops/bootstrap-db-replica.sh`: pass; `bash ops/tests/test_infra_layout.sh`: PASS.
- Trên replica (chỉ đọc): `gosu` có trong image, thư mục dữ liệu rỗng, không còn container kẹt.
- Chưa chạy end-to-end: cần merge rồi để CI chạy lại.

## Còn lại / rủi ro

- Sau merge, workflow tự chạy lại (đổi `ops/bootstrap-db-replica.sh` nằm trong `paths`); job replication phải xanh.
- Primary SSH công khai (`default-allow-ssh` mở `0.0.0.0/0`) đang bị dò mật khẩu liên tục từ Internet; nên siết về IAP (`35.235.240.0/20`) ở một thay đổi riêng.
