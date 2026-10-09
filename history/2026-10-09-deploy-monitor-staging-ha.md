# Deploy monitor job cào staging-ha: realtime tắt (BACKEND_URL trống), POST không bị chặn

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude Code (Haiku 5.5, thực hiện)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành
- Phạm vi: scripts, data (deploy staging-ha)
- Liên quan: `2026-10-09-realtime-tat-staging-ha.md` (mã được deploy)

## Mục tiêu

Deploy lại monitor job cào trên VM `vota-ha-crawler` (staging-ha) với mã mới: realtime tắt khi `BACKEND_URL` trống, các API POST không bị chặn. Người yêu cầu: "deploy lại monitor staging-ha, kết quả khả quan thì commit".

## Image

- Tag: `asia-southeast1-docker.pkg.dev/vinpearl-508801/v-ota/vota-fresh-catalog:monitor-realtime-off-202610092246-fc19c865`
- Digest: `sha256:af5eec42b704d7e616cc4d96883b4348828c0026f7ad9fce715fedecfdc40e0a`
- Build từ working tree tại HEAD `fc19c865`, cộng các thay đổi chưa commit trong `src/data_collection` (monitor.py, run_daily_docker.sh, monitor_ui/index.html, README.md, tests/test_monitor_backend_calls.py). `src/backend` không có thay đổi chưa commit. `.dockerignore` loại `.env.*`, không có secret trong image.
- Lệnh build: `docker buildx build --platform linux/amd64 -f Dockerfile.fresh-catalog --push .`

## Lệnh deploy

```bash
GCP_PROJECT_ID=vinpearl-508801 CRAWLER_INSTANCE=vota-ha-crawler CRAWLER_ZONE=asia-southeast1-a \
CRAWLER_REF=asia-southeast1-docker.pkg.dev/vinpearl-508801/v-ota/vota-fresh-catalog@sha256:af5eec42b704d7e616cc4d96883b4348828c0026f7ad9fce715fedecfdc40e0a \
bash scripts/deploy-staging-ha-crawler.sh
```

## Các lần chạy

Có bốn lần chạy. Ba lần đầu lỗi:

1. `CRAWLER_REF` dạng `image:tag@sha256:...`: script từ chối (regex chỉ nhận `image@sha256:`), rc=1. Chưa có lệnh nào tới VM.
2. Dạng `image@sha256:...`: gcloud `ReadTimeout` tới `compute.googleapis.com`, rc=1, ở bước đầu.
3. Bước 0 (docker login trên VM) chạy được, bước 1 (copy runner qua IAP) lỗi `ConnectionCreationError`, rc=255. Lệnh không chạy trên VM. IAP SSH kiểm tra lại sau đó hoạt động.
4. Lần chạy thành công, rc=0. Chạy đủ các bước: copy runner và installer, kiểm env file, chown thư mục, cài cron với digest mới, khởi động lại container monitor. Script xoá hai image cũ, còn lại image hiện tại.

## Kiểm tra sau deploy

Trên VM:
- Container `vota-fresh-catalog-monitor` đang chạy, lệnh `monitor.py --host 0.0.0.0 --allow-public-host`, log khởi động `http://0.0.0.0:8765`.
- `BACKEND_URL` trong env container: rỗng.
- Cron `*/15` dùng `FRESH_IMAGE=...@sha256:af5eec...`.

Công khai qua `https://monitor.praxis.io.vn`:
- `GET /api/calls`: HTTP 200, `disabled: true`, lý do "BACKEND_URL trống".
- `GET /api/overview`: HTTP 200, `running: null`, lượt kế tiếp 2026-10-10 02:00 (full).
- `POST /api/embed/query` (header `X-Requested-With: vota-monitor`, q "resort gần biển"): HTTP 200, trả 10 kết quả, collection `ProductE5Small`, 4138 vector. Lần đầu nạp model mất khoảng 34 giây. Đây là bằng chứng POST không còn bị chặn. Không gọi POST nào làm đổi trạng thái lượt (không run, stop, settings, cleanup).

## Không làm và lưu ý

- Không chạy lượt cào nào. Lượt full kế tiếp: 2026-10-10 02:00.
- Trước deploy không có lượt nào đang chạy. Lượt `full-20261009T075357Z-361` (14:53 ngày 09/10 giờ VN) đang ở trạng thái `dead` (mất tiến trình). Lượt này không được chạy lại.
- Chưa đổi `infra/terraform/environments/staging-ha/crawler.tf`. Việc hạ đĩa boot xuống 10 GB là yêu cầu riêng, sẽ có entry riêng.
- Các thay đổi infra không liên quan (crawler_monitor.tf, main.tf, staging-ha.tfvars.example) vẫn chưa commit; không đưa vào commit này.
