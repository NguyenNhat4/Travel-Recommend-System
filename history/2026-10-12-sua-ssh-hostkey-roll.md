# Sửa Backend CD lỗi `Host key verification failed` ở bước roll

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/fix-roll-ssh-hostkey
- Trạng thái: dang dở (đã sửa và có test cấu trúc; chưa chạy lại trên CI)
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-10-12-sua-reload-proxy-slot.md`, `2026-10-12-cd-zero-downtime-slot.md`

## Triệu chứng

Backend CD `38268890647` (`534dd687`) lỗi ở `Roll app VMs to the new image without downtime` trên `vota-ha-app-fn9m`, sau ~1 phút:
`REMOTE HOST IDENTIFICATION HAS CHANGED ... Host key verification failed` (khoá ED25519 `SHA256:b+16ct...`, `/home/runner/.ssh/google_compute_known_hosts:3`). Cùng lỗi trên laptop.

## Nguyên nhân (đã đối chiếu)

- Audit log: `compute.instances.repair.recreateInstance` bởi `system@google.com` lúc 22:10:27 VN: MIG autohealing tạo lại `fn9m`. VM mới có khoá SSH host mới; `known_hosts` của runner giữ khoá cũ.
- Điều dẫn tới autohealing (suy luận, chưa kiểm từng bước): lần roll hỏng trước đó (lỗi `nginx -s reload`, đã sửa ở PR #179) để `upstream.conf` ghi sang slot mới trong khi proxy vẫn trỏ slot cũ; rollback của lần đó coi slot kia là đang chạy và dừng slot blue đang thực sự phục vụ, cổng 3000 trả lỗi, health check `live` rớt. Domain không sập vì `vota-ha-app-9bbx` vẫn phục vụ.
- Autohealing tạo lại VM từ chính template mà instance đang giữ (MIG `OPPORTUNISTIC`), nên `fn9m` quay về bố cục kiểu cũ (`vota-backend`, `vota-frontend`, không proxy), chứ không phải template mới nhất.

## File thay đổi

- `scripts/roll-staging-ha-app-slots.sh` — sửa: `gcloud compute ssh ... --strict-host-key-checking=no`, kèm chú thích.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — thêm: test cờ `--strict-host-key-checking=no`.

## Quyết định

- Không ghim khoá host: VM app có thể bị tạo lại bất kỳ lúc nào (autohealing, thay template). Kênh vẫn đi qua IAP tới đúng instance và đăng nhập bằng OS Login. Đánh đổi: mất kiểm tra chống giả mạo host; chấp nhận vì không có tài sản bí mật nào đi qua phiên SSH này ngoài lệnh deploy.
- Không xoá `known_hosts` trên runner (ngoài quyền và dễ lặp lại lỗi).

## Kiểm tra

- `bash -n`: OK. `pytest infra/terraform/environments/staging-ha/tests`: 107 passed. Chưa chạy lại Backend CD.

## Còn lại / rủi ro

- Cả hai VM app đang ở bố cục kiểu cũ (`fn9m` bị tạo lại; `9bbx` chưa từng được chuyển). Lần deploy kế sẽ chuyển cả hai (legacy → slot), có khoảng vài giây một lần giữa lúc frontend cũ nhả cổng 3000 và proxy bind cổng; hai VM nên được chuyển lần lượt.
- Một lần roll làm cổng 3000 trả lỗi quá lâu có thể bị autohealing tạo lại VM (như tối nay).
- Frontend CD `38268891116` lỗi ở build: `403` khi đẩy image `vota-frontend` lên Artifact Registry, trên `vota-ci-runner-6`; chưa xác định nguyên nhân.
