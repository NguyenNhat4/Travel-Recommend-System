# Bỏ theo dõi access_config của VM crawler sau khi gỡ IP public

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), sửa theo CI check fail "Plan and apply staging infra" của PR #157 (run 38202247700)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: infra

## Mục tiêu

Ngày 2026-10-12 IP public tĩnh `34.142.132.251` được gỡ khỏi VM `vota-backend-crawler-recsys` (đang `TERMINATED`) và gán cho bastion `vota-ha-bastion` (`staging-ha`). Cấu hình root `infra/terraform/environments/staging` vẫn khai báo `access_config` với IP này trên `google_compute_instance.app`, nên plan đề xuất update tại chỗ để gắn lại IP. Guard `INFRA_ALLOW_VM_UPDATE` chặn đúng.

## File thay đổi

- `infra/terraform/environments/staging/app.tf` — sửa: thêm `network_interface[0].access_config` vào `lifecycle.ignore_changes` của `google_compute_instance.app`, kèm comment giải thích.

## Quyết định

- Không gắn lại IP cho VM crawler, vì IP đã thuộc bastion. Không đặt `INFRA_ALLOW_VM_UPDATE=true`, vì nó sẽ cho plan cố gắn IP đang bị bastion giữ.
- Giữ nguyên `google_compute_address.app_public` (địa chỉ tĩnh `vota-backend-crawler-recsys-public`, trạng thái `RESERVED`), không xóa.

## Kiểm tra

- `terraform init -backend-config=backend.staging.hcl` và `terraform plan -var-file=staging.tfvars -lock=false` trên commit `3c82c937` + thay đổi này: `No changes. Your infrastructure matches the configuration.`

## Còn lại / rủi ro

- DuckDNS (theo `infra/terraform/environments/staging/addresses.tf`) từng trỏ vào IP này. Nay DNS đó không còn trỏ tới VM crawler. VM crawler đang `TERMINATED` nên chưa có tác động đang chạy, nhưng khi bật lại thì không có IP public và DuckDNS cần được cập nhật hoặc bỏ.
- Nếu cần VM crawler có IP public trở lại, phải chọn IP khác, không lấy lại IP của bastion.
