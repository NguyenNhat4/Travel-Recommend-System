# Sửa lỗi nginx reload trong slot-deploy.sh (proxy không đổi sang slot mới)

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/fix-slot-proxy-reload
- Trạng thái: dang dở (đã sửa và có test cấu trúc; chưa chạy lại trên VM)
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-10-12-cd-zero-downtime-slot.md`

## Triệu chứng

Frontend CD `38266237899` (`9290aa3a`) lỗi ở bước `Roll app VMs to the new image without downtime` trên `vota-ha-app-fn9m`:
`nginx: [error] open() "/run/nginx.pid" failed (2: No such file or directory)`. Bước rollback chạy cùng đường nên lỗi cùng chỗ.

## Nguyên nhân

`reload_proxy` gọi `nginx -s reload` không kèm `-c`. `nginx.conf` do script ghi đặt `pid /tmp/nginx.pid`, còn nginx không có `-c` tìm file pid theo cấu hình mặc định (`/run/nginx.pid`). Đường reload chưa từng chạy: lần chuyển đầu từ VM kiểu cũ dùng `docker run` (không reload), và test chỉ kiểm cấu trúc.

## Hệ quả đã quan sát (không sập)

Trạng thái `fn9m` sau lỗi nhất quán: `upstream.conf` và `active-slot` là `blue`, proxy phục vụ `blue`, `/health/ready` qua cổng 3000 trả 200. Slot `blue` chạy image last-good (do bước rollback dựng lại), slot `green` (image mới) còn chạy nhưng không nhận traffic. `vota-ha-app-9bbx` vẫn kiểu cũ vì bước roll dừng ở VM đầu tiên.

## File thay đổi

- `infra/terraform/environments/staging-ha/slot-deploy.sh` — sửa: `reload_proxy` dùng `nginx -c "$PROXY_DIR/nginx.conf" -s reload` và trả mã lỗi thay vì thoát; nếu reload lỗi thì `mode_deploy` đưa `upstream.conf` về slot cũ, bỏ slot mới, rồi báo lỗi (trước đó upstream đã bị ghi sang slot mới mà proxy chưa nạp, dễ làm lần deploy sau dừng nhầm slot đang phục vụ).
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — thêm: test lệnh reload có `-c`, test reload lỗi thì trả upstream cũ.

## Kiểm tra

- `bash -n`: OK. `pytest infra/terraform/environments/staging-ha/tests`: 106 passed.
- Chưa chạy lại `deploy` trên VM thật. Đường reload (slot→slot) vẫn chưa được thử trên VM sau khi sửa.

## Còn lại / rủi ro

- Slot `green` trên `fn9m` (image mới, đang idle) sẽ được dọn bởi lần deploy kế (`stop_slot` slot đích trước khi dựng).
- `vota-ha-app-9bbx` vẫn kiểu cũ, sẽ được chuyển sang slot ở lần roll kế.
- Backend mới (kể cả PR #165) chưa lên staging: Backend CD `38266237856` bị hủy tay bởi @Khoa15.
