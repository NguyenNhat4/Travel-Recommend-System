# Gộp `release-mvp-v2` vào `khoa/bastion-db-access` để giải xung đột PR #161

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: `khoa/bastion-db-access`
- Trạng thái: hoàn thành
- Phạm vi: infra

## Mục tiêu

PR #161 (`khoa/bastion-db-access` → `release-mvp-v2`) báo `CONFLICTING`. Gộp `release-mvp-v2` mới nhất vào nhánh để PR merge được.
Xung đột duy nhất là `infra/terraform/environments/staging-ha/bastion.tf`.

## File thay đổi

- `infra/terraform/environments/staging-ha/bastion.tf` — sửa (giải xung đột): lấy nguyên bản của `release-mvp-v2`.
- `history/2026-10-12-gop-release-vao-bastion-db-access.md` — thêm: entry này.
- Các file còn lại do merge mang vào từ `release-mvp-v2`, không sửa tay (`db/`, `docs/`, `src/`, `scripts/`, `infra/` của CD và
  dữ liệu mô phỏng); mỗi thay đổi đó đã có entry riêng trên `release-mvp-v2`.

## Quyết định

- Giữ bản `release-mvp-v2` cho `bastion.tf`, đúng chỉ dẫn ở `history/2026-10-12-bastion-trong-cd.md` ("khi merge #161 cần giữ bản trên
  `release-mvp-v2`, nếu không plan sẽ lại thay đổi bastion"). Nhờ đó:
  - `create_bastion` mặc định `true` (CD plan khớp state; CD không có tfvars gitignored).
  - `bastion_ssh_source_ranges` mặc định `["0.0.0.0/0"]`, theo chỉ đạo người vận hành ngày 2026-10-12.
  - Bỏ `precondition` về hash và danh sách IP của PR: CI không có `TF_VAR_bastion_password_hash`, precondition sẽ làm plan CD fail.
  - Giữ `lifecycle.ignore_changes` cho `metadata["bastion-password-hash"]` và `metadata["startup-script"]`.
- Không tự gộp hai khối `lifecycle` (một của PR, một của `release-mvp-v2`) thành một: bản `release-mvp-v2` đã là bản đang chạy CD, và
  PR đã bỏ `precondition` có chủ đích.
- Phần còn lại của PR (IP tĩnh, firewall SSH, sshd, `fail2ban`, OS Login tắt, `Makefile`, tài liệu cutover) được giữ nguyên, auto-merge sạch.

## Kiểm tra

- `git merge-tree` trước khi gộp: 1 xung đột (`bastion.tf`), đã giải.
- `terraform fmt -check -recursive infra/terraform/environments/staging-ha/`: đạt.
- `terraform init -backend=false` rồi `terraform validate` tại `infra/terraform/environments/staging-ha/`: `Success! The configuration is valid.`
- Chưa chạy `terraform plan`: cần state và credential GCP; CD sẽ chạy plan khi merge.

## Còn lại / rủi ro

- Comment đầu `bastion.tf` còn ghi "Tắt mặc định (create_bastion = false)" trong khi default đã là `true`. Lỗi có sẵn trên `release-mvp-v2`,
  chưa sửa ở entry này.
- PR #161 chưa có đề xuất trong `docs/prd/update/` cho thiết kế bastion (AGENTS.md mục 8). Việc này có từ trước, chưa xử lý ở entry này.
- Target `tunnel` trong `Makefile` vẫn dùng IAP, chưa trỏ sang bastion (theo `history/2026-10-12-bastion-ssh-mat-khau.md`).
