# Cảnh báo bộ nhớ và đĩa cho từng VM app staging-ha

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/xoa-monitoring-staging-cu
- Trạng thái: dang dở (code và test local xong; chưa commit, chưa apply. Apply đi qua `staging-ha-infra-cd.yml` sau merge)
- Phạm vi: infra (staging-ha)
- Liên quan: `history/2026-10-13-go-ci-cd-staging-cu.md` (cùng PR; gỡ monitoring cũ). Hai alert memory/disk của stack cũ đã xoá vì gắn VM cũ đã TERMINATED; staging-ha không có thay thế.

## Mục tiêu

Sau khi xoá monitoring cũ, nhóm app staging-ha không còn cảnh báo bộ nhớ và đĩa cho từng VM. Thêm hai policy cho nhóm `vota-ha-app`.

## File thay đổi

- `infra/terraform/environments/staging-ha/monitoring.tf` — thêm: `locals.group_memory_filter`, `locals.group_disk_filter`; `google_monitoring_alert_policy.group_memory_high` (mục 2b); `google_monitoring_alert_policy.group_disk_high` (mục 2c).
- `infra/terraform/environments/staging-ha/variables.tf` — thêm: `alert_memory_percent` (mặc định 90), `alert_disk_percent` (mặc định 90).
- `infra/terraform/environments/staging-ha/tests/test_alerts.py` — sửa: thêm hai policy vào danh sách kiểm chung; thêm 3 test (filter theo nhóm, ngưỡng và absent, ngưỡng memory cao hơn `memory_target_percent`).
- `scripts/deploy-staging-ha-app.sh` — sửa: thêm hai địa chỉ `|create` vào `allowed_changes`, kèm chú thích. Nếu thiếu, cổng plan dừng apply.

## Quyết định

- **Lọc theo nhãn instance của template, không theo tên VM.** Metric `agent.googleapis.com/memory|disk/percent_used` không có nhãn `instance_name` (khác `compute.googleapis.com/instance/cpu/utilization`, `group_vm_filter` dùng nhãn đó). Lọc bằng `metadata.user_labels."group"="vota-ha-app"` (template đặt `group = <prefix>-app`). Đã kiểm trên GCP (chỉ đọc, 30 phút gần nhất): có 2 series memory và 4 series đĩa (`/dev/sda1`, `/dev/sda15` cho mỗi VM).
- **Ngưỡng 90% trong 5 phút, cùng mức với alert VM cũ.** Autoscaler co giãn theo memory ở `memory_target_percent` (60), nên alert không trùng với co giãn: nó chỉ báo khi co giãn không kịp hoặc tiến trình rò rỉ. Ảnh hưởng: không đổi hành vi autoscaler.
- **`REDUCE_MAX` trên mọi VM và mọi thiết bị.** Một VM hay một thiết bị vượt ngưỡng là đủ báo. Không group_by để không tạo policy theo từng VM (nhóm đổi tên mỗi lần thay VM).
- **Thêm điều kiện `condition_absent` (5 phút) cho cả hai.** Nếu Ops Agent dừng trên toàn nhóm thì ngưỡng "lớn hơn" không bao giờ kích hoạt. Mẫu lấy từ `group_below_min`. Vẫn có điểm mù: Ops Agent dừng trên một VM còn VM khác gửi dữ liệu thì không báo (chấp nhận, ghi trong Còn lại).
- **Dùng kênh `local.alert_channels`.** Vì vậy lịch mute ban đêm (`alert_mute.tf`) cũng tắt hai alert này, giống các alert HA khác.
- **Không đổi PRD.** `deployment-plan.md` §5 chỉ mô tả endpoint health và metrics của backend; không có yêu cầu cảnh báo VM trong `requirements.md` (không có FR/NFR/AC về memory hay disk). Đây là chi tiết vận hành, không phải hành vi sản phẩm, nên không tạo đề xuất `docs/prd/update/`.
- **CD gate.** Hai policy là địa chỉ mới, nên được thêm vào `allowed_changes` (quy trình đã ghi trong `2026-10-12-monitor-ha-canh-bao-va-dashboard.md`). Không nới cổng.

## Số liệu hiện tại (chỉ đọc, GCP `vinpearl-508801`, 30 phút gần nhất)

- Memory `used`: VM `vota-ha-app-fn9m` ~63%, VM `vota-ha-app-9bbx` ~36%. Dưới 90%, không kích hoạt.
- Đĩa `used` lớn nhất: `/dev/sda1` ~20%. Dưới 90%, không kích hoạt.

## Kiểm tra

- `python3 infra/terraform/environments/staging-ha/tests/test_*.py` (8 file): tất cả OK; `test_alerts.py` 18 test (gồm 3 test mới).
- `bash -n scripts/deploy-staging-ha-app.sh`: OK.
- `terraform -chdir=infra/terraform/environments/staging-ha fmt -check -recursive`: sạch.
- `terraform validate` (sau `init -backend=false`, Terraform 1.15.8): "Success! The configuration is valid."
- Render hai chuỗi filter bằng `terraform console` trên bản sao không có backend: khớp đúng cú pháp đã kiểm trên GCP thật.
- Chưa chạy `terraform plan` với state thật: cần `STAGING_HA_TFVARS` (secret CI) và `TF_STATE_BUCKET`. Kỳ vọng plan chỉ có hai `create` mới, nằm đúng trong allowlist.

## Còn lại / rủi ro

- Chưa apply. Sau merge, `staging-ha-infra-cd.yml` tạo hai policy. Cần kiểm trên GCP sau apply: policy hiện đúng số điều kiện, và hai filter có dữ liệu.
- Điểm mù: Ops Agent dừng trên một VM (VM kia vẫn gửi) không được báo. Muốn bắt được, cần alert per-VM hoặc đếm số VM có dữ liệu so với `targetSize`.
- Ngưỡng 90% và 5 phút là mức khởi điểm, chọn theo alert VM cũ. Chưa có dữ liệu tải thật để tinh chỉnh.
- Một VM sau thay thế (slot deploy) có thể đẩy memory tạm thời cao khi nạp model e5; thời gian nạp dài hơn 5 phút thì có thể báo nhầm. Theo dõi lần deploy đầu tiên.
- Policy này đặt cạnh `group_below_min` và `group_at_max`, nên một sự cố làm nhiều alert cùng bắn. Chấp nhận, khớp với cách HA đã làm.
