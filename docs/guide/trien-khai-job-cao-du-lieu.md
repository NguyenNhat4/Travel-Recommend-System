# Triển khai job cào dữ liệu trên VM — đọc trước khi deploy

Dành cho đội deploy. Phục vụ FR-CAT-01..04 (catalog đúng, đủ, tươi) và FR-SRC-02 (index Weaviate). Chi tiết vận hành (env,
thư mục, lệnh theo dõi) ở `src/data_collection/README.md`, mục "Job catalog mới trên VM console".

## Quy tắc số 1: trên một DB chỉ lên lịch MỘT job cào

Repo có hai job. Hai job cùng ghi `cdp.products` nên không được chạy song song trên cùng một DB.

| | Job cũ (legacy) | Job mới (fresh) — dùng từ nay |
|---|---|---|
| Code | `src/data_collection/daily.py` | `src/data_collection/fresh_catalog.py` (P1–P5, vé khứ hồi, monitor mới) |
| Image | `Dockerfile.daily` | `Dockerfile.fresh-catalog` (có Chromium + Xvfb) |
| Lệnh runner | `run_daily_docker.sh run` | `run_daily_docker.sh fresh-run tick` (giờ chạy đặt trên monitor, mặc định 02:00 VN) |
| Lịch cron | `0 2 * * *` | `*/15 * * * *` (tick rảnh không làm gì, không cần DB) |
| Dữ liệu / env | `/srv/vota/daily-data`, `/etc/vota/daily.env` | `/srv/vota/fresh-catalog-data` (UID 10001), `/etc/vota/fresh-catalog.env`, log `/srv/vota/fresh-catalog-logs` |
| Monitor | `run_daily_docker.sh monitor` (container `vota-daily-monitor`) | `run_daily_docker.sh fresh-monitor` (container `vota-fresh-catalog-monitor`) |
| CI/CD hiện tại | Build/publish để giữ khả năng quay lại | **Mặc định deploy**: build/publish, cron và yêu cầu cào full ngay; giữ monitor đang chạy |

Cả hai lịch được cài bằng **một** script `scripts/install-vota-cron.sh`, trong **cùng một khối** crontab
(`# BEGIN VOTA CRAWLER` … `# END VOTA CRAWLER`). Cài job này là **thay** job kia, nên không thể vô tình chạy cả hai:

```bash
# Job mới (thay lịch job cũ):
scripts/install-vota-cron.sh --job fresh --image <AR>/vota-fresh-catalog:latest --runner /opt/vota/bin/run_daily_docker.sh
# Quay lại job cũ:
scripts/install-vota-cron.sh --job legacy --image <AR>/vota-daily:latest --runner /opt/vota/bin/run_daily_docker.sh
# Xem trước, không ghi crontab:
scripts/install-vota-cron.sh --job fresh --image <AR>/vota-fresh-catalog:latest --runner /opt/vota/bin/run_daily_docker.sh --dry-run
```

Không có `--job` thì script vẫn cài job cũ để tương thích; CI/CD mới truyền rõ `--job fresh`. Test:
`bash scripts/tests/test-install-vota-cron.sh`.

## Push và deploy tự động cào (cập nhật 30/09/2026)

Workflow `crawler-ci-cd.yml` chạy trên main/release-mvp-v1/v2/v3. Nhánh `test/newcrawl` cần merge/PR vào một nhánh này; push riêng nhánh test không deploy. Các bước:

1. Kiểm shell, chạy test cron/deploy giả lập và build cả `Dockerfile.daily`, `Dockerfile.fresh-catalog`.
2. Publish image daily như trước và image fresh tại `${GAR_DAILY_IMAGE}-fresh:<sha>` / `:latest`, cùng Artifact Registry đã cấu hình. Không cần thêm secret tên image.
3. Chép runner mới rồi gọi `scripts/deploy-crawler-vm.sh` trên VM. Helper pull image SHA, import bổ sung gói 43 vé thương gia (insert-only) và thay khối cron quản lý thành **fresh**, mỗi 15 phút gọi `fresh-run tick`.
4. Ghi `deploy-pending` trong thư mục log, chứa image SHA, rồi gọi `fresh-run full` ở nền. Lượt full gồm vé Trip SEO/khứ hồi và collector thương gia, rồi normalize → DB → index.
5. Nếu fresh hoặc legacy batch còn chạy, giữ nó và giữ request. Tick tiếp theo thử full khi máy rảnh. Request chỉ được xóa sau exit 0; deploy mới thay request trong lúc lượt cũ chạy thì lượt cũ không xóa request mới. Khóa file bảo vệ cập nhật request. Không restart monitor/container đang chạy.

CD thành công ở bước này nghĩa là **đã gửi yêu cầu**, không phải crawl nhiều giờ đã hoàn tất. Xem `deploy-*.log`, `fresh-catalog-*.log`, `run.json` và monitor để biết tiến độ. Lỗi pull/import không thay cron hay request hiện tại. Nguồn incomplete/quota deferred vẫn giữ report partial theo hướng dẫn quota.

## Điều kiện VM và kiểm sau deploy

VM hiện có job fresh cần giữ nguyên:

- `/srv/vota/fresh-catalog-data` (app UID/GID 10001 ghi được), `/etc/vota/fresh-catalog.env` (deploy account đọc được), `/srv/vota/fresh-catalog-logs` (deploy account ghi được).
- Env có `DB_TARGET`, kết nối DB, Cohere và Weaviate của đúng đích; tunnel DB và Docker đã hoạt động. Helper không tự tạo env hay sửa secret.
- Đổi đường dẫn nếu cần bằng các secret tùy chọn `GCE_FRESH_DATA_DIR`, `GCE_FRESH_ENV_FILE`, `GCE_FRESH_LOG_DIR`; runner dùng `GCE_CRON_RUNNER` như trước. Các `GCE_CRON_DATA_DIR/ENV_FILE` của job legacy không áp cho fresh.
- VM mới chưa có thư mục/env phải provision theo README trước; helper báo thiếu rõ ràng, không tự tạo DB hay volume mới.

Sau deploy, `crontab -l` chỉ có một khối `VOTA CRAWLER`, cuối dòng là `fresh-run tick`. `run_daily_docker.sh report 3` và log cho biết số dòng DB/index. Monitor hiện có đọc chung volume nên xem được lượt mới, nhưng bản code của monitor vẫn là bản cũ cho tới lần cập nhật riêng được cho phép. Không tuyên bố monitor đã nâng cấp khi chỉ thay image batch.

Quay lại legacy cần chủ động cài `install-vota-cron.sh --job legacy` và dùng image daily. Workflow này sẽ chọn lại fresh ở lần deploy tiếp; chỉ quay lại khi đã quyết định kế hoạch rollback tương ứng.

## Monitor: link để xem và bấm chạy

Monitor là trang web của job: sơ đồ các bước, log, báo cáo từng lượt, nút chạy lượt cào / chạy lại bước / cào lại một nguồn,
trang cấu hình (nguồn, giờ chạy, chạy liên tục). Như bản deploy trước (25/09), mở bằng link không cần SSH:

1. Chạy monitor với `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1` (thao tác riêng khi được phép khởi động/cập nhật monitor). Lệnh `monitor` của job cũ
   nhận cùng hai biến.
2. Firewall GCP cho phép TCP `8765` vào VM (một lần, bỏ qua nếu bản deploy 25/09 đã mở):

   ```bash
   gcloud compute firewall-rules create vota-crawler-monitor --allow tcp:8765 --target-tags <tag của VM> --project <project>
   ```

3. Mở `http://<IP ngoài của VM>:8765`.

**Chưa có đăng nhập.** Ai có link đều bấm chạy / đổi cấu hình job được, và các thao tác ghi thẳng vào DB thật. Tạm chấp nhận
theo yêu cầu, bảo mật làm sau: giới hạn IP nguồn trong rule firewall (`--source-ranges`), hoặc đặt sau proxy có đăng nhập.
Tắt link: chạy lại monitor không có hai biến `MONITOR_*` (chỉ còn `127.0.0.1`, xem qua SSH), hoặc xoá rule firewall.

## Nạp catalog snapshot lên DB staging một lần (tuỳ chọn)

Dùng khi FE cần vé khứ hồi trên staging **trước** khi job cào chạy trên VM. Snapshot `2026-09-30` là snapshot `2026-09-23` cộng
vé máy bay trip.com cào ngày 30/09/2026: 11.718 sản phẩm, có 290 vé khứ hồi, 268 vé hạng Phổ thông
(`src/data_collection/snapshots/README.md`).

Chế độ `--catalog-only` chỉ upsert `cdp.products` và thay `catalog.combo_items` của các combo. Nó **không xoá** gì, không đụng
`cdp.profiles` / `cdp.events`, `app.*` (user, giỏ, đơn) hay database `insider`. Không cần Weaviate / Cohere: chuyến bay không được
index, tuyến đã có vector.

1. Mở SSH tunnel tới Postgres staging rồi kiểm: `bash scripts/check-db-tunnel.sh` (mặc định `127.0.0.1:15432`).
2. Tài khoản cần quyền ghi `cdp.products`, `catalog.combo_items`: tài khoản seed/superuser của staging, không phải
   `vota_app_login`.
3. Chạy từ gốc repo (DSN để trong biến môi trường, không ghi vào file commit):

   ```bash
   cd src && SEED_DATABASE_URL='postgresql://<user>:<mật khẩu>@127.0.0.1:15432/vota' python -m data_collection.seed --products data_collection/snapshots/2026-09-30/products.jsonl.gz --as-of "$(date +%F)" --catalog-only
   ```

   - Kết quả mong đợi trên DB đang có catalog 11.387: `inserted=331 · updated=110`.
   - Đã thử trên database nháp: `app.bookings`, `cdp.events` không đổi, `db/verify.sql` 0 FAIL.
   - Muốn xem trước, không ghi DB: thêm `--generate-only`.

Lưu ý:

- **Seed** dời vé khứ hồi có ngày đi ngoài cửa sổ vào cửa sổ, giá giữ nguyên. Đó là giá tham khảo; quy tắc ở
  `docs/prd/data-model.md` §3.
- **Job cào** không dời ngày. Mỗi lượt, nó khoá vé hết hạn báo giá (`priceValidUntil` 30/09/2026), rồi nạp vé mới với ngày và
  giá thật.
- Vì vậy khi job mới đã chạy trên staging, **không cần** bước này nữa.

## Không dùng trên VM

- `src/data_collection/cron_daily.sh`: cron **máy cá nhân** của job cũ, không cài trên VM.
- Đã gỡ ngày 29/09/2026: `cron_hotels_daily.sh`, `run_fresh_catalog_vm.sh`, `cron_run.sh`, `run_forever.sh`,
  `run_extra_queue.sh`, `stop_crawl.sh` và các script chạy tay khác. Hướng dẫn cũ nhắc tới chúng không còn đúng.
- `make demo-db` / `make demo-db-reset`: chỉ cho máy dev (Postgres local); không chạy lên staging (có `--reset`).
- Chạy liên tục (`stream.enabled`, `stream.db`) mặc định **tắt**. Bật trên monitor sau khi lượt đầu trên VM ổn
  (`docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md`, P2).

## Vé thương gia và quota Cohere (30/09/2026)

`trip-flights` nay lấy thêm báo giá Thương Gia từ UI Trip.com; image daily đã có Chromium. Gói 43 vé ngày 15/10/2026 được import insert-only từ image SHA trong CD. Xem [hướng dẫn chi tiết](ve-thuong-gia-va-index-cho.md) về giới hạn tuyến/ngày, import và kiểm chứng.

Job fresh giữ report `partial` nhưng trả 0 khi nguồn timeout mà dữ liệu hợp lệ đã nạp, hoặc Cohere 429 được hoãn vào `state/index_pending.json`. Cron thử lại riêng index khi đến `retryAfter`. Lỗi DB/schema/quality gate và lỗi index khác vẫn báo lỗi. Workflow hiện build/publish cả daily và fresh, rồi yêu cầu cào full bằng image fresh mới. Task này không restart VM hoặc monitor.
