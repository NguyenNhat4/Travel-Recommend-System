# Backend env từ GCP Secret Manager

Hướng dẫn cho người vận hành. Phục vụ NFR bảo mật về secret (`docs/prd/deployment-plan.md` §2). Quy tắc chung nằm ở `AGENTS.md`; lệch thì AGENTS.md thắng.

## Cách hoạt động

Toàn bộ nội dung file `backend.env` nằm trong **một** secret của Secret Manager. Mỗi lần CD backend chạy, job `deploy` (`.github/workflows/backend-ci-cd.yml`, bước *Sync backend env from Secret Manager*):

1. Đọc `latest` của secret bằng service account của CI (qua Workload Identity).
2. Kiểm tra có đủ 5 khóa bắt buộc: `DATABASE_URL`, `CDP_DATABASE_URL`, `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH`, `AUTH_REDIS_URL`. Thiếu thì dừng, không đụng tới VM.
3. Ghi vào `/etc/vota/backend.env` trên VM qua SSH (stdin, không qua tham số dòng lệnh), giữ bản cũ ở `/etc/vota/backend.env.prev`.
4. Compose và script deploy chạy như cũ (compose vẫn dùng `env_file: /etc/vota/backend.env`).

Không sửa code ứng dụng, không cần thư viện hay quyền Secret Manager cho VM. Biến `GCE_BACKEND_ENV_SECRET` của environment staging chưa đặt thì bước này bị bỏ qua và file đặt tay vẫn dùng như trước.

## Thiết lập một lần — làm TRƯỚC khi merge

CD chạy ngay khi merge vào `release-mvp-v2` và đọc secret ở lần đó, nên hai bước dưới phải xong trước. Đặt biến `GCE_BACKEND_ENV_SECRET` (bước 2) **sau cùng**: biến chưa đặt thì CD bỏ qua bước nạp và dùng file đặt tay như cũ; đã đặt mà secret hoặc quyền sai thì bước nạp dừng deploy trước khi đụng tới VM.

**Bước 1 — tạo secret và cấp quyền:**

```bash
gcloud services enable secretmanager.googleapis.com --project <project>
gcloud secrets create vota-backend-env --project <project> --data-file=<file .env của STAGING>
gcloud secrets add-iam-policy-binding vota-backend-env --project <project> \
  --member="serviceAccount:<GCP_CI_SERVICE_ACCOUNT>" --role="roles/secretmanager.secretAccessor"
```

**Bước 2 — đặt biến** (sau khi bước 1 xong). Đặt **environment variable** (Settings → Environments → staging → Variables) `GCE_BACKEND_ENV_SECRET=vota-backend-env`.

- Dùng `.env` của staging, không dùng `.env` local (chứa URL localhost). Có thể chép nội dung hiện tại từ `/etc/vota/backend.env` trên VM làm điểm xuất phát.
- Service account của CI phải có quyền `secretmanager.secretAccessor` trên secret; quyền này cấp ở GCP, chưa nằm trong Terraform.

## Kiểm tra trên VM sau khi CD chạy

Ghi log của bước CD: *Sync backend env from Secret Manager* phải xanh (không bị skipped). Trên VM (`gcloud compute ssh <vm> --tunnel-through-iap`):

```bash
# 1. File vừa được ghi lúc nào, và bản cũ đã được giữ
sudo ls -l --time-style=full-iso /etc/vota/backend.env /etc/vota/backend.env.prev
# 2. Tên khóa trong file (KHÔNG in giá trị) so với secret
sudo cut -d= -f1 /etc/vota/backend.env | sort | head -50
# 3. Sai khác giữa file trên VM và version mới nhất của secret (chạy trên máy có quyền đọc secret, không in giá trị)
gcloud secrets versions access latest --secret vota-backend-env --project <project> | sha256sum
sudo sha256sum /etc/vota/backend.env      # hai hash phải trùng
# 4. Container đã nạp đúng env (đếm khóa, không in giá trị)
sudo docker exec vota-backend printenv | cut -d= -f1 | grep -c .
```

Cách chắc nhất là hash ở bước 3 trùng nhau và thời điểm sửa file khớp thời điểm chạy CD. Muốn thử "có thật lấy từ Secret Manager": thêm một khóa thử (ví dụ `SM_PROBE=1`) vào secret bằng `versions add`, chạy lại CD, rồi `sudo grep -c '^SM_PROBE=' /etc/vota/backend.env` phải ra 1; xong xóa khóa đó đi bằng một version mới.

## Đổi/thêm/xóa một key

```bash
gcloud secrets versions add vota-backend-env --project <project> --data-file=<file .env đã sửa>
```

Sau đó chạy lại workflow Backend CI/CD (`workflow_dispatch`) hoặc deploy bình thường: CD ghi file mới và khởi động lại container. Key mới cũng cần field trong `src/backend/app/core/config.py` và dòng trong `.env.example`.

## Lưu ý

- Rollback của script deploy chỉ khôi phục image, không khôi phục env. Muốn quay lại env cũ: `sudo cp -p /etc/vota/backend.env.prev /etc/vota/backend.env` trên VM, hoặc thêm lại version cũ của secret.
- File PEM của JWT (`/etc/vota/backend-secrets/`), `/etc/vota/daily.env` (cron) và biến nội suy của frontend (`AUTH_SERVICE_TOKEN`, `AUTH_REDIS_URL`) chưa được quản lý bằng cách này.
- Quản lý secret theo từng key (phân quyền/kiểm toán riêng) không nằm trong phạm vi; secret này là cả file nên ai đọc được thì đọc được tất cả.
