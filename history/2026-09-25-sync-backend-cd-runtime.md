# Đồng bộ CD Backend với runtime trên VM

- Ngày: 2026-09-25
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: hoàn thành
- Phạm vi: backend | data | CI/CD

## Mục tiêu

Đưa cấu hình chạy Backend trên application VM vào nguồn chuẩn trong repository. Workflow CD phải chép Compose app-only cùng deploy script lên VM trước khi deploy, để container nhận đúng `backend.env`, khóa JWT RS256 và image Backend hiện đang dùng trên Artifact Registry.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — sửa: theo dõi template Compose, chép template lên VM bằng đường dẫn tuyệt đối và validate bằng Docker Compose trước deploy; chạy test đồng bộ trong CI.
- `ops/docker-compose.backend-vm.yml` — thêm: Compose app-only dùng host network, env file trên VM và mount khóa RS256 read-only; không quản lý PostgreSQL, Redis hoặc Weaviate.
- `scripts/deploy-backend-vm.sh` — sửa: preflight env/key/runtime Compose và giữ deploy Backend ở `--no-deps`; hỗ trợ file có quyền đọc giới hạn qua `sudo`.
- `scripts/tests/test-backend-vm-cd-sync.sh` — thêm: kiểm tra workflow, template Compose và các guard bắt buộc của deploy script.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md` — sửa: bổ sung template Compose vào danh sách file của thiết kế.
- `history/2026-09-25-sync-backend-cd-runtime.md` — thêm: ghi quyết định và bằng chứng kiểm tra.

## Quyết định

- Compose trên application VM chỉ có Backend. PostgreSQL vẫn ở DB VM qua SSH tunnel loopback; Redis auth và monitor không bị workflow dựng lại.
- Workflow chép template từ repo mỗi lần deploy nên file Compose cũ trên VM không còn là nguồn cấu hình độc lập.
- Template dùng image Backend `asia-southeast1-docker.pkg.dev/vinpearl-508801/v-ota-data-pipeline-crawler/vota-backend:latest`, khớp image hiện có trên VM; giá trị secret `GAR_BACKEND_IMAGE` trong GitHub Environment vẫn phải trỏ cùng repository image.
- Deploy dừng sớm nếu thiếu `DATABASE_URL`, `CDP_DATABASE_URL`, `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH`, `AUTH_REDIS_URL` hoặc hai file khóa trên VM.
- Không đưa secret vào repo, image hoặc log; không dùng `docker compose down`, không thay đổi database và không restart dependency.

## Kiểm tra

- Test đỏ trước khi thêm template: fail vì thiếu `ops/docker-compose.backend-vm.yml`.
- `bash scripts/tests/test-backend-vm-cd-sync.sh` — PASS.
- `bash -n scripts/deploy-backend-vm.sh scripts/check-db-tunnel.sh scripts/install-vota-cron.sh scripts/tests/test-backend-vm-cd-sync.sh` — PASS.
- PyYAML parse `.github/workflows/backend-ci-cd.yml` và `ops/docker-compose.backend-vm.yml` — PASS.
- Đóng gói đúng các file deploy bằng `tar` với ba thư mục nguồn tuyệt đối — PASS; cách dùng `-C` tương đối cũ tái hiện lỗi `could not chdir to '../ops'` và đã được loại bỏ.
- `git diff --check` — PASS.
- Compose local chưa resolve được vì `/etc/vota/backend.env` chỉ tồn tại trên VM; sẽ validate lại bằng Compose trên VM trong bước áp dụng template.

## Còn lại / rủi ro

- GitHub Environment `staging` cần giữ `GCE_COMPOSE_FILE` là đường dẫn tuyệt đối tới Compose app-only và `GAR_BACKEND_IMAGE` phải dùng đúng Artifact Registry repository như template.
- Cần một lần chạy CD thật từ GitHub để xác nhận WIF, IAP SSH và các secret/environment variables của Environment; chưa tự nhận là workflow đã chạy thành công chỉ từ kiểm tra local.
