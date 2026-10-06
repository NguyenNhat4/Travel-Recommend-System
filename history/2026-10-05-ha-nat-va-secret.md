# Cloud NAT và secret cho nhóm HA (việc 7)

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành
- Phạm vi: infra | docs

## Mục tiêu

VM nhóm HA không IP public cần đường ra Internet (Stripe, Cohere, LLM, image Weaviate) và env được nạp từ Secret Manager một cách an toàn.

## File thay đổi

- `infra/terraform/environments/staging-ha/network.tf` — thêm: Cloud Router và Cloud NAT (tắt được bằng `create_nat = false`)
- `infra/terraform/environments/staging-ha/secrets.tf` — thêm: vỏ secret env backend và key Weaviate, quyền `secretAccessor`, data source kiểm phiên bản (cổng `require_secret_versions`)
- `infra/terraform/environments/staging-ha/main.tf`, `weaviate.tf` — sửa: `depends_on` NAT và secret
- `infra/terraform/environments/staging-ha/variables.tf` — sửa: `create_nat`, `require_secret_versions`
- `infra/terraform/environments/staging-ha/tests/test_egress_and_secrets.py` — thêm: 6 test
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: use case và dòng việc 7

## Quyết định

- Giá trị secret không bao giờ vào Terraform/state (không có resource `secret_version`).
- Hai lần apply: lần đầu `require_secret_versions = false` tạo vỏ secret; nạp giá trị; lần sau `true`.
- NAT `AUTO_ONLY`: không có allowlist IP phía đối tác nên chưa cần IP tĩnh.
- Use case: Stripe/Cohere không tới được từ VM không IP public; vòng lặp thay VM vì secret chưa có phiên bản (plan §3b).

## Kiểm tra

- `terraform validate` staging-ha: pass.
- `python3 infra/terraform/environments/staging-ha/tests/test_egress_and_secrets.py`: 6 passed; `test_health_checks.py`: 5 passed.
- Chưa chạy: apply; egress thật qua NAT; kiểm VPC staging đã có Cloud NAT chưa.

## Còn lại / rủi ro

- Nếu VPC đã có NAT cho region, đặt `create_nat = false` kẻo xung đột tên/quota.
- `min_ports_per_vm = 256` chọn theo ước lượng, chưa đo.
