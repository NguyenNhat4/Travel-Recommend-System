# Triển khai Ops Agent config cho backend logs

- Ngày: 2026-10-06
- Người: Khoa / Claude
- Trạng thái: hoàn thành
- Phạm vi: infra/monitoring

## Vấn đề

Backend đã code JSON logging, nhưng staging VM chưa nhận config Ops Agent để parse logs đó. Backend logs không hiển thị trên Cloud Monitoring — chỉ thấy `container_disk` metrics.

Nguyên nhân: `infra/monitoring/ops-agent-staging.yaml` được định nghĩa trong repo nhưng chưa cài lên VM. Script `deploy-backend-vm.sh` không cập nhật Ops Agent config.

## Giải pháp

Tạo `infra/monitoring/install-backend-monitoring.sh` theo mẫu `install-db-replica-monitoring.sh`:
1. Check/cài Ops Agent (Google Cloud Ops Agent)
2. Cài config `ops-agent-staging.yaml` → `/etc/google-cloud-ops-agent/config.yaml`
3. Restart Ops Agent để load config mới

Config này thiết lập parser hai tầng:
- Tầng 1: parse Docker JSON wrapper (`field: message`)
- Tầng 2: parse app JSON (`field: log`, `time_key: ts_utc`, `time_format: "%Y-%m-%dT%H:%M:%S.%LZ"`)
- Severity từ `jsonPayload.severity`

## Hướng dẫn deploy

**SSH vào staging backend VM (hoặc qua GCP console):**

```bash
sudo bash infra/monitoring/install-backend-monitoring.sh
```

**Xác nhận:**

1. Ops Agent đang chạy:
   ```bash
   sudo systemctl status google-cloud-ops-agent.service
   ```

2. Xem logs từ backend (qua `gcloud logging read`):
   ```bash
   gcloud logging read 'resource.type="gce_instance" AND jsonPayload.service="backend"' --limit 5 --format json
   ```

3. Xem trên Cloud Monitoring dashboard: refresh, backend logs phải có `jsonPayload.service`, `jsonPayload.event`, `severity`.

## File thay đổi

- `infra/monitoring/install-backend-monitoring.sh` — thêm (mới)

## Lưu ý

- Ops Agent config không manage qua Terraform (chỉ define metrics); update bằng script install thủ công hoặc automation khác.
- Nếu backend container đang chạy trước install, restart container sau install để Ops Agent có chance đọc logs mới (stream từ đầu không có).
- Nếu chỉnh sửa `ops-agent-staging.yaml` (thêm processor, receiver...), chạy lại script install để cập nhật `/etc/google-cloud-ops-agent/config.yaml` và restart Ops Agent.
