# Bastion public IP cho đội DB: SSH bằng username và mật khẩu

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), theo chỉ đạo của người vận hành
- Nhánh: khoa/bastion-db-access
- Trạng thái: hoàn thành
- Phạm vi: infra

## Mục tiêu

Đội DB cần kết nối tới cụm Patroni staging-HA bằng `ssh` thuần, không cần `gcloud`. Các node Patroni không có IP public, nên cần một bastion có IP public. Người vận hành chỉ đạo: dùng IP `34.142.132.251` (địa chỉ tĩnh đã đặt trước), mở `0.0.0.0/0` tới cổng 22, đăng nhập bằng username và mật khẩu.

Thiết kế này thay cho bastion IAP trong `bastion.tf` trước đó (không có IP public, chỉ SSH qua IAP). Đề xuất `docs/prd/update/2026-10-09-team-db-access.md` không có trên nhánh và không được chốt.

## File thay đổi

- `infra/terraform/environments/staging-ha/bastion.tf` — sửa: bỏ khóa SSH và rule IAP; thêm IP public tĩnh qua `bastion_public_ip`; firewall SSH theo `bastion_ssh_source_ranges`; OS Login tắt trên bastion; startup script đặt mật khẩu từ hash metadata, cấu hình sshd (chỉ chuyển tiếp TCP tới `10.148.0.34:5432`), cài `fail2ban`.
- `Makefile` — sửa: target `tunnel` dùng IAP tới `vota-ha-pg-b` (không còn mật khẩu); bỏ `setsid` (không có trên macOS).
- `.env.tunnel.example` — sửa: thay hai mật khẩu bằng `IAP_SSH_USER`, `IAP_SSH_KEY`.
- `docs/guide/van-hanh-db-patroni.md` — sửa: cập nhật trạng thái cutover 2026-10-08 và trạng thái hiện tại.
- `docs/plan/2026-10-07-ha-vung-crawler-rolling.md`, `docs/plan/2026-10-08-hoan-thanh-todo-ha.md` — sửa: ghi chú cutover đã hoàn thành.
- `history/2026-10-12-cap-nhat-tai-lieu-cutover-patroni.md` — mới: entry cho cập nhật tài liệu cutover.

Không commit: `infra/terraform/environments/staging-ha/staging-ha.tfvars` (gitignored, chứa `create_bastion = true` và `bastion_ssh_source_ranges = ["0.0.0.0/0"]`). Mật khẩu gốc và hash nằm ngoài repo (`~/secrets/`).

## Thao tác trên GCP (đã thực hiện)

- Gỡ access config `External NAT` khỏi `vota-backend-crawler-recsys` (đang `TERMINATED`). IP `34.142.132.251` giữ trạng thái `RESERVED`, sau đó được gán cho bastion.
- `terraform apply -target` cho 4 resource: `vota-ha-bastion` (`asia-southeast1-c`, `e2-micro`, IP nội bộ `10.148.15.213`), firewall `vota-ha-bastion-ssh` (`0.0.0.0/0`, tcp:22), firewall `vota-ha-bastion-to-pg` (tcp:5432 tới node Patroni), resource policy lịch `vota-ha-bastion-schedule`.
- Không apply thay đổi app: plan đầy đủ có `google_compute_instance_template.app` must be replaced và MIG update, không thuộc phạm vi thay đổi này và được loại bằng `-target`.
- Đường vào DB dev `v-ota-db-dev` đã không còn, `TERMINATED` và không có IP public. Node Patroni không có IP public và không mở cho bastion ngoài 5432.

## Kiểm tra

- `terraform fmt -check bastion.tf` và `terraform validate`: đạt.
- `terraform plan` với `-target` các resource bastion: `4 to add, 0 to change, 0 to destroy`.
- `gcloud compute instances list`: `vota-ha-bastion` `RUNNING`, NAT IP `34.142.132.251`.
- `ssh bastion@34.142.132.251` bằng mật khẩu: đăng nhập được, in `LOGIN_OK`.
- Chuyển tiếp `ssh -L 127.0.0.1:15435:10.148.0.34:5432 bastion@34.142.132.251`: cổng local mở được.
- Chưa kiểm tra: `fail2ban` đang chạy, và truy vấn Postgres thật qua tunnel (cần role DB).

## Quyết định

- Bastion dùng mật khẩu thay vì khóa SSH, theo chỉ đạo người vận hành. Rủi ro: cổng 22 mở `0.0.0.0/0` và đăng nhập bằng mật khẩu là mục tiêu dò mật khẩu. Giảm rủi ro bằng: mật khẩu ngẫu nhiên 24 ký tự, `MaxAuthTries 3`, `PermitRootLogin no`, `fail2ban`, `PermitTTY no` và `PermitOpen` chỉ tới `10.148.0.34:5432`.
- Hash mật khẩu đi qua metadata của VM và state Terraform. Mật khẩu gốc không đi vào Terraform và không nằm trong repo.
- Bastion nằm trong lịch tắt 23:59–08:30 của staging-HA. IP tĩnh giữ nguyên qua các lần tắt bật.

## Còn lại / rủi ro

- Chưa có đề xuất đã chốt trong `docs/prd/update/` cho thiết kế này. AGENTS.md mục 8 yêu cầu đề xuất khi lệch PRD.
- `Makefile` target `tunnel` vẫn dùng IAP, chưa trỏ sang bastion.
- `scripts/tunnel.ps1`, `scripts/run_tunnel.ps1` và `README.md` dòng 106 vẫn dùng `vota-dev@35.197.148.180` (máy đã dừng).
- `staging-ha.tfvars.example` và `staging-ha.tfvars` còn `db_primary_ip = "10.148.0.2"`.
- Crawler `vota-backend-crawler-recsys` không còn IP public. Nếu bật lại, cần gán IP khác hoặc dùng cách khác để ra internet.
- Cần kiểm `fail2ban` và log `auth.log` trên bastion sau khi chạy vài ngày.
