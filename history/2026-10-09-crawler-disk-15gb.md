# Hạ đĩa boot VM crawler staging-ha từ 30 GB xuống 15 GB (thay VM, khôi phục từ snapshot)

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude Code (Haiku 5.5, thực hiện)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành
- Phạm vi: infra (staging-ha), data (deploy crawler)
- Liên quan: `2026-10-09-deploy-monitor-staging-ha.md` (deploy trước đó, đã commit `c08cc9f5`)

## Mục tiêu

Người yêu cầu muốn hạ đĩa boot của VM `vota-ha-crawler` xuống 15 GB. GCP không thu nhỏ đĩa tại chỗ, nên phải thay VM. Dung lượng đo được trước đó: đang dùng 6.0/30 GB, gồm OS khoảng 2.5 GB, image crawler 3.0 GB, dữ liệu lượt 0.5 GB. Đĩa 10 GB không đủ chỗ khi pull image mới (cần giữ cả image cũ và mới), nên người yêu cầu chọn 15 GB.

## Secret của VM crawler

Người yêu cầu cho rằng CI/CD đã quản lý secret. Kiểm tra cho thấy không đúng với VM staging-ha:
- `staging-ha-crawler-cd.yml` không có bước đồng bộ env. Không dùng `sync-env-from-secret-manager`.
- `GCE_CRAWLER_ENV_SECRET` không được đặt trong GitHub vars. Secret Manager không có secret env nào cho crawler staging-ha.
- `/etc/vota/fresh-catalog.env` được đặt tay, và bản duy nhất nằm trên đĩa boot. Nếu thay VM mà không khôi phục thì mất.

Vì vậy env được khôi phục từ snapshot (xem bước 3), không copy ra máy local.

## Các bước đã thực hiện

1. Tạo snapshot an toàn của đĩa boot: `vota-ha-crawler-pre15gb-20261009` (READY, 30 GB, ~2.8 GB dữ liệu thật). Snapshot được giữ lại để rollback.
2. `infra/terraform/environments/staging-ha/crawler.tf`: `boot_disk.initialize_params.size` 30 → 15. Plan có target chỉ `google_compute_instance.crawler[0]`: 1 add, 1 destroy, `size 30 -> 15 # forces replacement`.
3. Apply có target cho instance: VM mới `vota-ha-crawler` (đĩa 15 GB, cùng tên, cùng IP nội bộ `10.148.15.201`). Startup script cài Docker và cron, mất khoảng 5 phút. Sau đó:
   - Tạo đĩa tạm `vota-ha-crawler-restore` từ snapshot, attach chế độ chỉ đọc.
   - Mount với `-t ext4 -o ro,noload`. Không có `noload` mount bị từ chối vì journal chưa replay.
   - Copy `/etc/vota/fresh-catalog.env` (quyền 600), `/srv/vota/fresh-catalog-data` (state và fresh_runs, 504 MB), `/srv/vota/fresh-catalog-logs`.
   - Unmount, detach, xoá đĩa tạm.
4. Lỗi sau apply: instance group `vota-ha-crawler-ig` có 0 instance. Khi VM cũ bị xoá, GCP tự gỡ instance khỏi group, còn state Terraform vẫn giữ self_link cùng tên nên không thấy thay đổi. Khắc phục: `terraform apply -target='google_compute_instance_group.crawler[0]'` (plan: 1 change, thêm instance). Khi đó LB trả 503 `unconditional drop overload`, và sau khoảng 2 phút chuyển sang 200.
5. Deploy lại monitor bằng `scripts/deploy-staging-ha-crawler.sh` với cùng digest `sha256:af5eec42…` (cùng image đã deploy trước đó). Kết quả `DEPLOY_RC=0`.

## Kiểm tra sau khi thay VM

Trên VM:
- Đĩa `/dev/sda1` 15 GB, đang dùng 5.9 GB (43%) sau khi pull image.
- Container `vota-fresh-catalog-monitor` đang chạy, `BACKEND_URL` rỗng.
- Cron `*/15` dùng `FRESH_IMAGE=...@sha256:af5eec42...`.
- Docker chỉ còn một image (3 GB), không có image cũ.
- `/etc/vota/fresh-catalog.env` có quyền 600. `/srv/vota/fresh-catalog-data` có 504 MB.

Công khai qua `https://monitor.praxis.io.vn`:
- `GET /api/calls`: HTTP 200, `disabled: true`.
- `GET /api/overview`: HTTP 200, `running: null`, lượt kế tiếp 2026-10-10 02:00.
- `POST /api/embed/query`: HTTP 200, trả kết quả. POST không bị chặn.

## Không làm và lưu ý

- Không chạy lượt cào nào. Lượt full kế tiếp: 2026-10-10 02:00. Trước khi thay VM không có lượt nào đang chạy.
- Snapshot `vota-ha-crawler-pre15gb-20261009` được giữ lại để rollback. Đĩa boot 30 GB cũ bị xoá cùng VM cũ.
- Thay đổi `crawler.tf` chưa commit. File này là untracked và chứa toàn bộ tài nguyên VM crawler, nên cần quyết định riêng khi commit.
- Chưa có cơ chế đồng bộ env cho VM crawler staging-ha. Nếu VM bị thay lần nữa thì env vẫn phải khôi phục thủ công từ snapshot hoặc từ bản đặt tay. Đề xuất: đặt secret env cho crawler staging-ha trong Secret Manager và thêm bước sync vào CD.
