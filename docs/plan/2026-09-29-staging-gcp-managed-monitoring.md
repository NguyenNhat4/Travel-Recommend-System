# Staging Google Cloud Managed Monitoring

- Phục vụ: NFR-PERF-01, NFR-REL-01, NFR-SEC-01, NFR-MAINT-01
- Phạm vi: chỉ staging; staging có đầy đủ production-grade monitoring coverage
- Ngoài phạm vi: production resources/state/apply; crawler monitor UI và crawler business metrics

## Mục tiêu

Quản lý monitoring staging bằng Terraform và Google Cloud Managed Monitoring, gồm Cloud Monitoring, Cloud Logging, Ops Agent, uptime check, dashboard, alert policy và notification channel. Terraform state staging được lưu riêng trên GCS; production state chỉ dành chỗ cho giai đoạn sau.

## Thiết kế

```text
App VM / DB VM
      │
      └── Ops Agent
              ├── Cloud Logging
              └── Cloud Monitoring
                       ├── Dashboard
                       ├── Alert policies
                       ├── Uptime check
                       └── Notification channel
```

Terraform quản lý control plane của monitoring. Ops Agent config được version trong repo; cài đặt lên VM là preflight vận hành riêng, không tự apply vào VM từ phiên này.

## Thành phần

- `infra/monitoring/`: Terraform root staging-only, backend GCS partial configuration, variables, dashboard, log-based metrics, metric alerts, uptime check và email notification channel.
- `ops/monitoring/ops-agent-staging.yaml`: cấu hình Ops Agent thu thập host metrics và Docker JSON logs; không thu thập crawler monitor UI.
- `.github/workflows/monitoring-terraform-staging.yml`: fmt/validate trên PR; plan/apply staging bằng WIF, protected GitHub Environment và immutable state prefix.
- `infra/monitoring/tests/test_staging_layout.sh`: guard không cho production resource/path lọt vào staging package và kiểm tra resource bắt buộc.

## Preflight bên ngoài repo

- Tạo GCS state bucket staging với versioning và IAM phù hợp; log retention vẫn do project logging policy quản lý, không đổi `_Default` bucket từ module này.
- Bật Monitoring, Logging, OS Config và Compute APIs.
- Gắn service account có quyền gửi log/metric cho App VM và DB VM.
- Xác định project, zone, VM name, uptime host/path và notification email qua GitHub Environment `staging`.
- Cài Ops Agent lên hai VM và kiểm tra metric/log trước khi apply alert policy.

## Kiểm tra

- Shell layout guard.
- `terraform fmt -check`.
- `terraform init -backend=false`.
- `terraform validate`.
- Workflow YAML parse.
- Không chạy `terraform apply`, không chạm production.
