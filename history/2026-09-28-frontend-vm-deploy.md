# Thêm CD Frontend lên cùng VM với Backend

- Ngày: 2026-09-28
- Tác giả: Người yêu cầu / Codex
- Nhánh: `khoa/frontend-vercel-to-vm`
- Trạng thái: dang dở — cấu hình repo xong; chưa chạy GitHub Actions hoặc deploy VM thật
- Phạm vi: frontend, CI/CD

## Mục tiêu

Đóng gói Frontend thành Docker image và triển khai lên application VM đang chạy Backend, dùng lại cấu hình GCP/IAP và Docker Compose hiện có.

## File thay đổi

- `.github/workflows/frontend-ci-cd.yml` — đổi tên và sửa: build/publish image Frontend vào Artifact Registry và thêm VM deploy sau quality/E2E trên `release-mvp-v1`; giữ Vercel deploy làm đường lui.
- `.github/workflows/backend-ci-cd.yml` — sửa: serialize deploy VM giữa workflow Backend và Frontend.
- `ops/docker-compose.backend-vm.yml` — sửa: thêm service Frontend trên host network, gọi Backend qua loopback và dùng Redis/session token đã cấu hình cho Backend.
- `scripts/deploy-frontend-vm.sh` — thêm: cập nhật riêng service Frontend, kiểm tra Backend/Frontend/BFF và rollback về image digest trước nếu health check lỗi.
- `history/2026-09-28-frontend-vm-deploy.md` — thêm: ghi quyết định, kiểm tra và phần chưa xác minh.

## Quyết định

- Dùng cùng Workload Identity Federation, Artifact Registry repository, IAP SSH, VM và GitHub Environment `staging` đã dùng cho Backend; image Frontend được suy ra từ `GAR_BACKEND_IMAGE`, không thêm secret image repository.
- Chỉ deploy VM trên `release-mvp-v1`, khớp nhánh CD Backend. Vercel workflow hiện tại vẫn hoạt động trong giai đoạn xác minh.
- PR checks của Backend và Frontend nhận target `release-mvp-v2`; push/deploy tự động vẫn giới hạn theo cấu hình release hiện có.
- Frontend chạy bằng Compose `network_mode: host`, gọi `http://127.0.0.1:8000`; không thêm Nginx, domain, TLS hoặc firewall rule.
- Chỉ chuyển `AUTH_SERVICE_TOKEN` và `AUTH_REDIS_URL` từ `/etc/vota/backend.env` vào biến môi trường Frontend; không nạp toàn bộ Backend env file vào container Frontend.
- Điều phối workflow dùng chung để hai lần deploy không ghi đè Compose hoặc cập nhật VM đồng thời.

## Kiểm tra

- `bash -n scripts/deploy-frontend-vm.sh` — PASS.
- PyYAML parse `.github/workflows/frontend-ci-cd.yml`, `.github/workflows/backend-ci-cd.yml` và `ops/docker-compose.backend-vm.yml` — PASS.
- `git diff --check` — PASS.
- `actionlint` — không có trong môi trường.
- Chưa chạy test ứng dụng, Docker image build, GitHub Actions hoặc deploy/runtime trên VM.

## Còn lại / rủi ro

- Cần chạy GitHub Actions từ `release-mvp-v1` để xác nhận WIF, quyền Artifact Registry, IAP và các biến của Environment `staging`.
- Chưa xác nhận image Frontend build/push được hoặc BFF thực sự gọi được Backend/Redis trên VM.
- VM đã được gắn firewall tag `vota-web`, mở TCP 80/443 và cài Caddy cho `v-ota.duckdns.org`; TLS hợp lệ nhưng domain hiện trả 502 vì Frontend chưa có image/container trên VM. Vercel vẫn là đường phục vụ hiện tại cho đến khi VM được xác minh.
