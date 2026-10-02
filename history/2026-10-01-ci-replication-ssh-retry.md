# CI replication: thử lại SSH 255 và bỏ pipe hai tiến trình gcloud

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude
- Nhánh: khoa/fix-ci-ssh-retry
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng, CI/CD)

## Mục tiêu

Sau khi sửa `pg_basebackup` (#78), run kế tiếp qua được bước chuẩn bị primary nhưng fail ở bước chuyển mật khẩu sang replica: `sa_…@compute.…: Permission denied (publickey)`, exit 255. Cùng bước đó chạy thành công ở run trước, và preflight cùng run vào replica được.

## File thay đổi

- `ops/ci-db-replication.sh` — sửa: thêm `retry_ssh` (thử lại tối đa 4 lần, chỉ với exit 255), áp dụng cho mọi lệnh SSH; `copy_secret` đọc mật khẩu từ primary vào biến shell rồi mới ghi sang replica, thay cho pipe giữa hai tiến trình `gcloud ssh` chạy đồng thời.
- `ops/tests/test_infra_layout.sh` — sửa: kiểm có `retry_ssh` và `copy_secret`.

## Quyết định

- Chỉ retry exit 255 (kết nối/xác thực SSH). Lỗi của lệnh từ xa (exit khác) trả về nguyên trạng, không chạy lại vô ích.
- Không tái hiện được lỗi bằng impersonate SA (3/3 lần pipe hai VM đều chạy), nên coi là lỗi chập chờn của OS Login (khoá vừa import chưa sẵn sàng) hoặc tranh chấp giữa hai tiến trình gcloud; sửa theo hướng chịu lỗi thay vì đoán nguyên nhân.
- Mật khẩu chỉ nằm trong biến shell (`set +x`), không in, không ghi file trên runner.

## Kiểm tra

- `bash -n ops/ci-db-replication.sh`, `ops/tests/test_infra_layout.sh`: PASS.
- Test đơn vị `retry_ssh` bằng hàm giả: 255 hai lần rồi thành công thì dừng ở lần 3; exit 1 không retry; 255 mãi thì bỏ cuộc sau 4 lần.
- Chưa chạy end-to-end: cần merge rồi để CI chạy lại.

## Còn lại / rủi ro

- Nếu vẫn fail sau retry, xem `gcloud compute ssh … --troubleshoot` và OS Login profile của SA (`gcloud compute os-login describe-profile --impersonate-service-account=…`) để xem khoá đã được import chưa.
