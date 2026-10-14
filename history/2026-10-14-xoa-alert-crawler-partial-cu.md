# Xoá alert "lượt cào hoàn thành một phần" của staging cũ (rule chết)

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/canh-bao-tai-nguyen-db-crawler (PR #211)
- Trạng thái: hoàn thành (đã xoá trên GCP `vinpearl-508801`)
- Phạm vi: infra (monitoring, GCP thủ công), docs
- Liên quan: `2026-10-13-xoa-monitoring-staging-cu.md` (đợt xoá trước; giữ 8 policy `vota-staging` còn bảo vệ staging-ha)

## Mục tiêu

Xoá các thành phần staging cũ đã lỗi thời. Đã kiểm từng thành phần: chỉ policy "lượt cào hoàn thành một phần" là lỗi thời.

## Lý do

- Policy lọc `jsonPayload.service="crawler" AND event="run.end" AND exit_code=3`. Bản crawler hiện tại ghi lượt partial với `exit_code=0` (ví dụ 13/10 và 14/10 lúc 03:03 UTC), nên policy không bao giờ kêu.
- Log-metric `vota-staging_crawler_warning` chỉ được policy này dùng.

## Đã xoá trên GCP

- Alert policy `vota-staging: lượt cào hoàn thành một phần` (id `15194489078109687991`).
- Log-metric `vota-staging_crawler_warning`.

Bản sao JSON của cả hai nằm trong scratchpad của phiên, không nằm trong repo.

## Giữ lại, có chủ ý

- 7 policy `vota-staging` còn lại: vẫn có dữ liệu trong 7 ngày và đang bảo vệ staging-ha (OOM, container dừng, log lỗi, watcher Docker, đĩa container, job cào thất bại, log tăng đột biến).
- Kênh `vota-staging: email cảnh báo`, dùng bởi 7 policy trên.
- State Terraform `monitoring/staging` và `infra/staging` trên GCS: chưa xoá, vì xoá state không hoàn tác được và cần chốt riêng.

## Kiểm tra

- Sau xoá: 28 alert policy (trước là 29), 13 log-metric (trước là 14). Không còn policy nào tham chiếu `vota-staging_crawler_warning`.
- `infra/monitoring/README.md`: sửa danh sách policy còn lại từ 8 xuống 7.

## Còn lại

- Quyết định về 7 policy `vota-staging` còn lại: giữ đến khi staging-ha có alert tương đương, hoặc đưa vào Terraform `staging-ha` rồi đổi tên.
- Quyết định về hai state Terraform cũ.
- Policy `vota-staging: job cào thất bại` (`crawler_failure`) chưa có sự kiện trong 7 ngày; chưa đủ bằng chứng để coi là lỗi thời.
