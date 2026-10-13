# Gộp release-mvp-v2 vào PR #180 (tắt lịch VM, bỏ cổng khung giờ CD)

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu merge PR 180) / Claude Code (agent)
- Nhánh: Khoa15/khoa-disable-shutdown-schedule
- Trạng thái: hoàn thành
- Phạm vi: infra, .github/workflows

## Lý do

PR #187 đã gỡ `resource_policies` khỏi VM bastion/crawler/patroni/weaviate. PR #180 cũng gỡ cùng chỗ nên xung đột bốn file `.tf` (chỉ khác một dòng comment).

## File thay đổi

- `infra/terraform/environments/staging-ha/{bastion,crawler,patroni,weaviate}.tf`: giữ dòng comment "Không gắn lịch tắt/bật…" của nhánh gốc.
- Phần còn lại của PR giữ nguyên: bỏ job `window-guard` khỏi ba workflow CD (người dùng chốt lại 2026-10-12: bỏ cổng khung giờ), xoá năm Cloud Scheduler job tắt/bật, allowlist thêm `google_cloud_scheduler_job.*|delete`.

## Kiểm tra

- `terraform fmt -check`: pass. pytest `infra/terraform/environments/staging-ha/tests`: 113 passed.
- Không còn tài liệu nào nhắc cổng khung giờ.

## Lưu ý

Sau merge, CD không còn bị chặn ban đêm; plan CD đầu tiên sẽ xoá năm Cloud Scheduler job (đã có trong allowlist).
