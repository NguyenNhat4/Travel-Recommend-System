# Env của Backend, Frontend, Crawler từ GCP Secret Manager

Hướng dẫn cho người vận hành. Phục vụ NFR bảo mật về secret (`docs/prd/deployment-plan.md` §2). Quy tắc chung nằm ở `AGENTS.md`; lệch thì AGENTS.md thắng.

## Cách hoạt động

Nội dung file env của mỗi nhóm nằm trong **một** secret của Secret Manager. Mỗi lần CD chạy, job deploy gọi action dùng chung `.github/actions/sync-env-from-secret-manager`, action này:

1. Đọc `latest` của secret bằng service account của CI (Workload Identity).
2. Dừng nếu secret rỗng hoặc thiếu giá trị của khóa bắt buộc; lúc đó không đụng tới VM.
3. Ghi vào file env trên VM qua SSH stdin (không qua tham số dòng lệnh, không vào log), giữ bản cũ ở `<file>.prev`. File đã có thì giữ nguyên owner/mode; file chưa có thì tạo `root:<nhóm user SSH>` 0640 để user deploy/cron (docker `--env-file`) đọc được.

Mỗi dịch vụ bật bằng một biến của **Environment `staging`** (Settings → Environments → staging → Variables). Biến chưa đặt thì bước tương ứng bị bỏ qua và file đặt tay trên VM vẫn dùng như trước.

| Dịch vụ | Biến bật | File trên VM | Khóa bắt buộc |
|---|---|---|---|
| Backend | `GCE_BACKEND_ENV_SECRET` | `/etc/vota/backend.env` | `DATABASE_URL`, `CDP_DATABASE_URL`, `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH`, `AUTH_REDIS_URL` |
| Frontend | dùng chung `GCE_BACKEND_ENV_SECRET` | `/etc/vota/backend.env` | `AUTH_SERVICE_TOKEN`, `AUTH_REDIS_URL` |
| Crawler | `GCE_CRAWLER_ENV_SECRET` | `GCE_CRON_ENV_FILE` (mặc định `/etc/vota/fresh-catalog.env`) | không kiểm (chưa rõ danh sách khóa) |

Vì sao Frontend dùng chung secret của Backend: `scripts/deploy-frontend-vm.sh` đọc `AUTH_SERVICE_TOKEN` và `AUTH_REDIS_URL` từ `backend.env` rồi truyền cho container. Đồng bộ ở workflow Frontend để lần deploy chỉ-frontend cũng dùng giá trị mới nhất. Việc này không khởi động lại backend; backend nhận giá trị mới ở lần deploy backend kế tiếp. Ba job deploy dùng chung nhóm `concurrency` `vota-application-vm-deploy` nên không ghi chồng lên nhau.

Không sửa code ứng dụng, Terraform hay quyền của VM; VM không cần quyền Secret Manager.

## Thiết lập — làm TRƯỚC khi merge

CD chạy ngay khi merge vào `release-mvp-v2` và đọc secret ở lần đó, nên các bước dưới phải xong trước. Đặt biến (bước 2) **sau cùng**: biến chưa đặt thì CD bỏ qua; đã đặt mà secret hoặc quyền sai thì bước nạp dừng deploy trước khi đụng tới VM.

**Bước 1 — tạo secret và cấp quyền** (dùng `.env` của STAGING, không dùng `.env` local chứa URL localhost; có thể chép nội dung hiện tại từ các file env trên VM làm điểm xuất phát):

```bash
gcloud services enable secretmanager.googleapis.com --project <project>

gcloud secrets create vota-backend-env --project <project> --data-file=<file env backend>
gcloud secrets create vota-crawler-env --project <project> --data-file=<file env crawler>

for s in vota-backend-env vota-crawler-env; do
  gcloud secrets add-iam-policy-binding "$s" --project <project> \
    --member="serviceAccount:<GCP_CI_SERVICE_ACCOUNT>" --role="roles/secretmanager.secretAccessor"
done
```

Quyền `secretAccessor` cấp ở GCP, chưa nằm trong Terraform.

**Bước 2 — đặt biến** (sau khi bước 1 xong): `GCE_BACKEND_ENV_SECRET=vota-backend-env` và `GCE_CRAWLER_ENV_SECRET=vota-crawler-env`. Có thể bật từng dịch vụ riêng.

## Kiểm tra trên VM sau khi CD chạy

Trong log CD, bước *Sync ... env from Secret Manager* phải xanh (không *skipped*). Rồi SSH vào VM (`gcloud compute ssh <vm> --tunnel-through-iap`); các lệnh dưới không in giá trị key. Thay `<file>` bằng `/etc/vota/backend.env` hoặc `/etc/vota/fresh-catalog.env`:

```bash
sudo ls -l --time-style=full-iso <file> <file>.prev      # thời điểm sửa khớp lần chạy CD; .prev là bản cũ (không có nếu file chưa tồn tại trước đó)
sudo cut -d= -f1 <file> | sort                           # danh sách tên khóa
# so hash với version mới nhất của secret (lệnh đầu chạy trên máy có quyền đọc secret)
gcloud secrets versions access latest --secret <secret> --project <project> | sha256sum
sudo sha256sum <file>                                    # hai hash phải trùng
sudo docker exec vota-backend printenv | cut -d= -f1 | grep -c .   # backend: số khóa container nạp
```

Muốn chắc là giá trị đến từ Secret Manager: thêm khóa thử `SM_PROBE=1` vào secret bằng `versions add`, chạy lại CD, rồi `sudo grep -c '^SM_PROBE=' <file>` phải ra 1; xong đẩy version mới đã bỏ khóa đó. Crawler chạy bằng cron, container mới đọc file ở lần chạy kế tiếp.

## Đổi/thêm/xóa một key

```bash
gcloud secrets versions add <secret> --project <project> --data-file=<file env đã sửa>
```

Rồi chạy lại workflow tương ứng (`workflow_dispatch`) hoặc deploy bình thường. Key mới của backend còn cần field trong `src/backend/app/core/config.py` và dòng trong `.env.example`.

## Lưu ý

- Rollback của script deploy chỉ khôi phục image, không khôi phục env. Quay lại env cũ: `sudo cp -p <file>.prev <file>` trên VM, hoặc thêm lại version cũ của secret.
- Chưa quản lý bằng cách này: file PEM của JWT (`/etc/vota/backend-secrets/`), `/etc/vota/daily.env` (job legacy).
- Quyền đọc theo cả file, không theo từng key; ai đọc được secret thì đọc được toàn bộ khóa trong đó.

## DSN cho migration lúc deploy Backend

Khác các secret ở trên (nội dung file env, ghi lên VM), secret này chỉ chứa **một dòng** DSN của role có quyền tạo bảng trong schema `app` (không phải `DATABASE_URL` của backend). Job deploy Backend đọc nó bằng danh tính CI rồi đưa cho `deploy-backend-vm.sh --migrate-dsn-stdin` qua stdin của SSH; không có file nào trên VM. Script chạy `db/migrations/run.py` bằng image sắp deploy, **trước** khi thay container.

```bash
printf '%s' 'postgresql://USER:PASS@127.0.0.1:15432/vota' | \
  gcloud secrets create vota-migrate-database-url --project <project> --data-file=-
gcloud secrets add-iam-policy-binding vota-migrate-database-url --project <project> \
  --member="serviceAccount:<GCP_CI_SERVICE_ACCOUNT>" --role="roles/secretmanager.secretAccessor"
```

Cổng phải khớp `GCE_DB_TUNNEL_PORT` (mặc định 15432). Đổi tên secret thì đặt biến `GCE_MIGRATE_DB_SECRET` ở Environment `staging`; mặc định là `vota-migrate-database-url`. Khác các secret trên, bước này **không** tự bỏ qua khi thiếu: secret thiếu, rỗng hoặc không phải DSN thì job dừng trước khi đụng tới VM. Đổi mật khẩu: `gcloud secrets versions add …`.
