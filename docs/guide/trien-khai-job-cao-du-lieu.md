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
| CI/CD hiện tại | **Có**: build, publish, cài cron, khởi động monitor | **Chưa**: image không được CI build |

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

Không có `--job` thì script cài job cũ, giống hệt trước đây (CI/CD hiện tại không bị đổi). Test:
`bash scripts/tests/test-install-vota-cron.sh`.

## Hiện trạng CI/CD (nhánh `release-mvp-v2`)

`.github/workflows/crawler-ci-cd.yml`, khi push vào nhánh release:

1. build / publish **`Dockerfile.daily`** (secret `GAR_DAILY_IMAGE`);
2. chép `run_daily_docker.sh` lên VM, chạy `install-vota-cron.sh` **không có `--job`** → cài **job cũ**;
3. khởi động `run_daily_docker.sh monitor` bằng image daily, chờ container `vota-daily-monitor`.

Hệ quả: nếu cài tay lịch job mới trên VM, **lần push tiếp theo CD sẽ cài lại job cũ** (thay mất lịch job mới). Phải sửa
workflow trước (mục dưới), không cài tay.

## Chuyển sang job mới — việc của đội deploy

1. **Workflow `crawler-ci-cd.yml`:**
   - thêm build / publish `Dockerfile.fresh-catalog` với tag `:<sha>` và `:latest` (secret mới, vd. `GAR_FRESH_IMAGE`);
   - bước "Install crawler cron": thêm `--job fresh --image "$FRESH_IMAGE:latest"`, bỏ `--data-dir` / `--env-file`
     của job cũ (mặc định của `--job fresh` đã đúng đường dẫn ở bảng trên);
   - bước "Restart crawler monitor":
     - chạy `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1 FRESH_IMAGE="$FRESH_IMAGE:latest" run_daily_docker.sh fresh-monitor`
       (link công khai, xem mục "Monitor: link để xem và bấm chạy"; bỏ hai biến `MONITOR_*` nếu chỉ muốn xem qua SSH);
     - chờ container `vota-fresh-catalog-monitor` thay cho `vota-daily-monitor`.
   - Có thể bỏ build `Dockerfile.daily` khi không còn cần quay lại job cũ.
2. **Một lần trên VM, trước lần deploy đầu tiên:**
   - tạo thư mục và env file theo README ("Đóng gói và bàn giao cho đội deploy");
   - điền `/etc/vota/fresh-catalog.env`: DB đích, `COHERE_API_KEY`, Weaviate; tuỳ chọn `COHERE_EMBED_CONCURRENCY`,
     `COHERE_CALLS_PER_MINUTE`.
   - DB phải đã migrate. Job chỉ upsert, **không reset** catalog 11.387 sản phẩm hay giỏ / đơn.
3. **Kiểm sau deploy:**
   - `crontab -l`: đúng **một** khối `VOTA CRAWLER`, dòng kết thúc bằng `fresh-run tick`, không còn dòng ` run`;
   - `run_daily_docker.sh fresh-run status`: lịch kế tiếp, không có lượt treo;
   - chạy thử một lượt (`fresh-run full`, hoặc chờ lịch) rồi:
     - `run_daily_docker.sh report 3`: kết quả, số dòng mới / làm mới, embed;
     - monitor (http://<IP ngoài của VM>:8765, hoặc qua SSH: `ssh -L 8765:127.0.0.1:8765 <vm>` rồi http://127.0.0.1:8765):
       sơ đồ luồng không có ô đỏ.
4. **Quay lại job cũ** (nếu cần): `install-vota-cron.sh --job legacy …` và dùng lại `monitor`.

## Monitor: link để xem và bấm chạy

Monitor là trang web của job: sơ đồ các bước, log, báo cáo từng lượt, nút chạy lượt cào / chạy lại bước / cào lại một nguồn,
trang cấu hình (nguồn, giờ chạy, chạy liên tục). Như bản deploy trước (25/09), mở bằng link không cần SSH:

1. Chạy monitor với `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1` (bước "Restart crawler monitor" ở trên). Lệnh `monitor` của job cũ
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

Dùng khi FE cần vé khứ hồi trên staging **trước** khi job mới chạy trên VM. Snapshot `2026-09-29` là snapshot `2026-09-23` cộng
vé máy bay trip.com cào ngày 29/09/2026: 11.708 sản phẩm, có 290 vé khứ hồi (`src/data_collection/snapshots/README.md`).

Chế độ `--catalog-only` chỉ upsert `cdp.products` và thay `catalog.combo_items` của các combo. Nó **không xoá** gì, không đụng
`cdp.profiles` / `cdp.events`, `app.*` (user, giỏ, đơn) hay database `insider`. Không cần Weaviate / Cohere: chuyến bay không được
index, tuyến đã có vector.

1. Mở SSH tunnel tới Postgres staging rồi kiểm: `bash scripts/check-db-tunnel.sh` (mặc định `127.0.0.1:15432`).
2. Tài khoản cần quyền ghi `cdp.products`, `catalog.combo_items`: tài khoản seed/superuser của staging, không phải
   `vota_app_login`.
3. Chạy từ gốc repo (DSN để trong biến môi trường, không ghi vào file commit):

   ```bash
   cd src && SEED_DATABASE_URL='postgresql://<user>:<mật khẩu>@127.0.0.1:15432/vota' python -m data_collection.seed --products data_collection/snapshots/2026-09-29/products.jsonl.gz --as-of "$(date +%F)" --catalog-only
   ```

   - Kết quả mong đợi trên DB đang có catalog 11.387: `inserted=321 · updated=110`.
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
