# CD backend, frontend, crawler nạp env từ GCP Secret Manager

- Ngày: 2026-10-02
- Tác giả: Khoa15 / Claude
- Nhánh: feat/inject-env-from-secret-manager
- Trạng thái: hoàn thành
- Phạm vi: infra | docs

## Mục tiêu

Bỏ việc đặt tay các file env trên VM (backend, frontend, crawler): lưu cả file trong một secret của Secret Manager và để CD ghi vào VM. Thay thế hướng mỗi-key-một-secret của PR #91 (đã đóng) vì quá phức tạp.

## File thay đổi

- `.github/actions/sync-env-from-secret-manager/action.yml` — thêm: composite action dùng chung, đọc secret rồi ghi file env trên VM qua SSH stdin
- `.github/workflows/backend-ci-cd.yml` — sửa: bước "Sync backend env from Secret Manager" (biến `GCE_BACKEND_ENV_SECRET`); thêm đường dẫn action vào `paths`
- `.github/workflows/frontend-ci-cd.yml` — sửa: cùng bước, đồng bộ `backend.env` (frontend đọc `AUTH_*` từ đó) trước khi deploy; thêm `paths`
- `.github/workflows/crawler-ci-cd.yml` — sửa: bước "Sync crawler env from Secret Manager" (biến `GCE_CRAWLER_ENV_SECRET`, file `GCE_CRON_ENV_FILE`); thêm `paths`
- `scripts/tests/test-backend-vm-cd-sync.sh` — sửa: kiểm action và ba bước trong workflow
- `docs/guide/env-secret-manager.md` — thêm
- `history/2026-10-02-inject-backend-env-from-secret-manager.md` — thêm

## Quyết định

- CI đọc secret rồi đẩy vào VM qua SSH stdin, không để VM tự kéo: không phải đổi scope service account của VM (VM có `deletion_protection`, đổi scope buộc dừng VM) và không cần gcloud/IAM Secret Manager trên VM.
- Bước tùy chọn theo biến của environment staging: chưa đặt thì hành vi cũ giữ nguyên.
- Một action dùng chung cho cả ba workflow để không lặp logic; file mới tạo `root:<nhóm user SSH>` 0640 để user deploy/cron đọc được.
- Frontend dùng chung secret với Backend vì `deploy-frontend-vm.sh` đọc `AUTH_SERVICE_TOKEN`/`AUTH_REDIS_URL` từ `backend.env`; ba job deploy chung nhóm `concurrency` nên không ghi chồng.
- Kiểm khóa bắt buộc (backend 5 khóa, frontend 2 khóa, crawler không kiểm vì chưa rõ danh sách) trước khi ghi để secret hỏng không làm hỏng file trên VM; giữ `backend.env.prev`.

## Kiểm tra

- `bash scripts/tests/test-backend-vm-cd-sync.sh`: pass
- YAML ba workflow và action parse được; chuỗi lệnh từ xa dựng thử cục bộ cho ra đúng lệnh.
- Chưa chạy workflow thật; cần thiết lập secret và IAM trước (xem guide).

## Còn lại / rủi ro

- Thiết lập GCP TRƯỚC khi merge theo guide (tạo `vota-backend-env` và `vota-crawler-env`, cấp quyền cho service account của CI, rồi đặt `GCE_BACKEND_ENV_SECRET`, `GCE_CRAWLER_ENV_SECRET` sau cùng); CD chạy ngay khi merge.
- PEM của JWT và `/etc/vota/daily.env` (job legacy) chưa được quản lý.
- Frontend deploy riêng sẽ ghi `backend.env` mà không khởi động lại backend.
- Chưa biết danh sách khóa của env crawler nên chưa kiểm khóa bắt buộc.
- Rollback image không khôi phục env.
