# Đưa bastion vào cấu hình CD staging-HA để plan khớp state

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), sửa theo CI check fail của PR #157 (run 38199825117)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: infra

## Mục tiêu

Bastion `vota-ha-bastion` đã được tạo bằng `terraform apply -target` trên máy local, nên 4 resource bastion nằm trong state staging-HA dùng chung. Nhánh `release-mvp-v2` (CD) chưa có cấu hình bastion và CI không có `create_bastion = true`, nên plan của CD đề xuất xóa `google_compute_firewall.bastion_ssh[0]`. Guard `scripts/deploy-staging-ha-app.sh` chặn đúng, không có gì bị apply, nhưng mọi lần push vào `release-mvp-v2` sẽ fail cho đến khi cấu hình khớp state.

## File thay đổi

- `infra/terraform/environments/staging-ha/bastion.tf` — sửa: `create_bastion` mặc định `true`; `bastion_ssh_source_ranges` mặc định `["0.0.0.0/0"]` (chỉ đạo người vận hành ngày 2026-10-12); bỏ `precondition` về hash; thêm `lifecycle.ignore_changes` cho `metadata["bastion-password-hash"]` và `metadata["startup-script"]`.

## Quyết định

- Hash mật khẩu không có trong secret của CI. Nếu không `ignore_changes`, plan của CD sẽ đặt metadata về rỗng và khóa đăng nhập bastion. Nên hash và startup script chỉ đặt khi dựng VM, CD không ghi đè.
- Allowlist `0.0.0.0/0` nằm trong code vì CI không có tfvars của bastion. IP mở ra internet là lựa chọn của người vận hành, không phải mặc định an toàn.
- Không sửa secret tfvars của CI; không chạy `state rm` hay `import`.

## Kiểm tra

- `terraform validate`: đạt.
- Plan với tfvars giống CI (không có dòng bastion, không có `TF_VAR_bastion_password_hash`): các thay đổi còn lại là `google_compute_instance_template.app|create,delete` và `google_compute_region_instance_group_manager.app|update`, đúng danh sách cho phép của guard. Bốn resource bastion đều `no-op`.

## Còn lại / rủi ro

- Nhánh `khoa/bastion-db-access` (PR #161) vẫn có `bastion.tf` phiên bản cũ có `precondition` và không có `ignore_changes`. Khi merge #161 cần giữ bản trên `release-mvp-v2`, nếu không plan sẽ lại thay đổi bastion.
- Bastion chưa được đưa vào root Terraform riêng. Nếu cần tách, phải `state mv` có kiểm soát trên state dùng chung.
