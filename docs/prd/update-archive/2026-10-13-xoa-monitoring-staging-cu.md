# Xoá monitoring cũ của staging cũ khỏi GCP, cập nhật mô tả tài nguyên còn lại

- Ngày: 2026-10-13
- Người đề xuất: Khoa15 / Claude Code (agent)
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Khoa15, 2026-10-13. Chốt trong chat qua ba lựa chọn: (1) xoá phần monitoring chết, giữ 8 policy toàn project đang bảo vệ staging-ha; (2) xoá cả 3 policy do Compute Engine tạo và exclusion log `vota-staging-debug-and-health-ok`; (3) yêu cầu xoá monitoring cũ và đưa lên `release-mvp-v2`.
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §1.1 (mô tả tài nguyên staging cũ còn trên GCP)
- Mã FR/NFR: không đổi FR/NFR (dọn hạ tầng vận hành)

## Lý do

Đề xuất `2026-10-13-ngung-ci-cd-staging-cu.md` (đã áp dụng) viết rằng tài nguyên GCP của staging cũ "vẫn còn, chưa bị destroy" và liệt kê cả exclusion log. Sau đó các alert, log-metric, dashboard và uptime check gắn VM cũ đã nghỉ được xoá khỏi GCP, nên mô tả trong PRD không còn đúng. Ngoài ra hai state `infra/staging` và `monitoring/staging` vẫn giữ các resource đã xoá, nên đã lệch.

## Nội dung đề xuất

Đoạn hiện tại (`deployment-plan.md` §1.1):

> Tài nguyên GCP cũ và hai state `infra/staging`, `monitoring/staging` vẫn còn. **Không destroy hai state này:** chúng còn giữ những tài nguyên staging-ha đang dùng, gồm alert và log-metric áp cho toàn project (...), cấu hình retention/exclusion log, và IP tĩnh ...

Đoạn thay thế: xem `deployment-plan.md` §1.1 sau khi áp dụng. Nội dung: đã xoá 18 policy, 4 log-metric, dashboard, uptime check, exclusion khỏi GCP; còn lại 8 policy toàn project, log-metric `vota-staging_*` của chúng, kênh email cũ, metric descriptor `custom.googleapis.com/vota/container/*`, IP tĩnh bastion, và hai state đã lệch (không plan hay apply).

## Thay đổi source sau khi áp dụng

- `docs/prd/deployment-plan.md` §1.1 — sửa theo nội dung trên.
- `infra/monitoring/README.md` — sửa: bỏ exclusion đã xoá, ghi danh sách còn lại đúng với GCP.
- `history/2026-10-13-go-ci-cd-staging-cu.md` và `history/2026-10-13-xoa-monitoring-staging-cu.md` — ghi thao tác xoá trên GCP.
