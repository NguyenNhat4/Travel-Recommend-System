# CD backend nạp backend.env từ GCP Secret Manager

- Ngày: 2026-10-02
- Tác giả: Khoa15 / Claude
- Nhánh: feat/inject-env-from-secret-manager
- Trạng thái: hoàn thành
- Phạm vi: infra | docs

## Mục tiêu

Bỏ việc đặt tay `/etc/vota/backend.env` trên VM: lưu cả file trong một secret của Secret Manager và để CD ghi vào VM. Thay thế hướng mỗi-key-một-secret của PR #91 (đã đóng) vì quá phức tạp.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — sửa: bước "Sync backend env from Secret Manager" (tùy chọn theo `vars.GCE_BACKEND_ENV_SECRET`)
- `scripts/tests/test-backend-vm-cd-sync.sh` — sửa: kiểm bước mới có trong workflow
- `docs/guide/backend-env-secret-manager.md` — thêm
- `history/2026-10-02-inject-backend-env-from-secret-manager.md` — thêm

## Quyết định

- CI đọc secret rồi đẩy vào VM qua SSH stdin, không để VM tự kéo: không phải đổi scope service account của VM (VM có `deletion_protection`, đổi scope buộc dừng VM) và không cần gcloud/IAM Secret Manager trên VM.
- Bước tùy chọn theo biến của environment staging: chưa đặt thì hành vi cũ giữ nguyên.
- Kiểm 5 khóa bắt buộc trước khi ghi để secret hỏng không làm hỏng file trên VM; giữ `backend.env.prev`.

## Kiểm tra

- `bash scripts/tests/test-backend-vm-cd-sync.sh`: pass
- YAML workflow parse được.
- Chưa chạy workflow thật; cần thiết lập secret và IAM trước (xem guide).

## Còn lại / rủi ro

- Thiết lập GCP TRƯỚC khi merge theo guide (tạo secret, cấp quyền cho service account của CI, rồi đặt `GCE_BACKEND_ENV_SECRET` sau cùng); CD chạy ngay khi merge.
- PEM của JWT, `daily.env` (cron) và biến nội suy của frontend chưa được quản lý.
- Rollback image không khôi phục env.
