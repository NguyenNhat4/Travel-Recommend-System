# Triển khai job cào dữ liệu trên VM — đọc trước khi deploy

Dành cho đội deploy. Phục vụ FR-CAT-01..04 (catalog đúng, đủ, tươi) và FR-SRC-02 (index Weaviate). Chi tiết vận hành (env,
thư mục, lệnh theo dõi) ở `src/data_collection/README.md`, mục "Job catalog mới trên VM console".

## Quy tắc số 1: trên một DB chỉ lên lịch MỘT job cào

Repo có hai job. Hai job cùng ghi `cdp.products` nên không được chạy song song trên cùng một DB.

| | Job cũ (legacy) | Job mới (fresh) — dùng từ nay |
|---|---|---|
| Code | `src/data_collection/daily.py` | `src/data_collection/fresh_catalog.py` (P1–P5, vé khứ hồi, monitor mới) |
| Image | `Dockerfile.daily` | `Dockerfile.fresh-catalog` (có Chromium + Xvfb) |
| Lệnh runner | `run_daily_docker.sh run` | `run_daily_docker.sh fresh-run tick` (giờ chạy đặt trên monitor, mặc định 08:35 VN) |
| Lịch cron | `0 2 * * *` | `*/15 * * * *` (tick rảnh không làm gì, không cần DB) |
| Dữ liệu / env | `/srv/vota/daily-data`, `/etc/vota/daily.env` | `/srv/vota/fresh-catalog-data` (UID 10001), `/etc/vota/fresh-catalog.env`, log `/srv/vota/fresh-catalog-logs` |
| Monitor | `run_daily_docker.sh monitor` (container `vota-daily-monitor`) | `run_daily_docker.sh fresh-monitor` (container `vota-fresh-catalog-monitor`) |
| CI/CD hiện tại | Không deploy (quay lại bằng tay) | **Mặc định deploy**: build/publish, cron ghim digest, khởi động lại monitor; không tự chạy lượt cào |

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

## Push và deploy (CD staging-ha, cập nhật 13/10/2026)

`crawler-ci-cd.yml` chỉ còn CI: kiểm shell, chạy `scripts/tests/test-install-vota-cron.sh`, và build thử `Dockerfile.fresh-catalog`
trên PR. Deploy do `staging-ha-crawler-cd.yml` làm, chạy khi push vào main/release-mvp-v1/v2/v3 và có thay đổi trong
`src/data_collection/**`, `Dockerfile.fresh-catalog`, script cron hoặc `scripts/deploy-staging-ha-crawler.sh`. Nhánh `test/newcrawl`
phải mở PR vào một nhánh này; push riêng nhánh test chỉ chạy CI. CD lên VM staging cũ đã gỡ ngày 13/10/2026.
Các bước:

1. Build và publish image fresh tại secret `GAR_FRESH_IMAGE` (tag SHA), lấy digest bất biến.
2. `scripts/deploy-staging-ha-crawler.sh` qua IAP SSH lên VM `vota-ha-crawler`: chép `run_daily_docker.sh`, cài cấu hình Ops Agent,
   cài khối cron **fresh** duy nhất (`fresh-run tick` mỗi 15 phút) với image ghim digest.
3. Xoá và khởi động lại monitor fresh (cổng 8765). Chỉ container monitor bị thay; lượt cào đang chạy giữ nguyên và tự kết thúc.
4. Kiểm VM đang RUNNING và chỉ có đúng một VM mang tag `vota-crawler`, rồi ghi digest vào last-good của crawler.

CD **không** tự chạy lượt cào ngay. Code mới có hiệu lực ở lượt kế tiếp theo giờ trong monitor. Muốn cào ngay: mở monitor, bấm chạy
lượt `full` (gồm vé Trip SEO/khứ hồi và collector thương gia, rồi normalize → DB → index).

Nguồn quá giờ có dữ liệu hợp lệ hoặc index bị 429 (chỉ còn ở đường lui Cohere; model local mặc định không có quota) không còn làm lượt trả `exit=3`: report ghi `partial`, index chờ đến hạn rồi tick tự
thử lại (xem [vé thương gia và index chờ](ve-thuong-gia-va-index-cho.md)).

## Điều kiện VM và kiểm sau deploy

VM hiện có job fresh cần giữ nguyên:

- `/srv/vota/fresh-catalog-data` (app UID/GID 10001 ghi được), `/etc/vota/fresh-catalog.env` (deploy account đọc được), `/srv/vota/fresh-catalog-logs` (deploy account ghi được).
- Env có `DB_TARGET`, kết nối DB và Weaviate của đúng đích; tunnel DB và Docker đã hoạt động. Embedding mặc định là model local
  `intfloat/multilingual-e5-small` có sẵn trong image (torch CPU + model tải lúc build, ghi collection `ProductE5`, không cần key);
  chỉ đường lui `EMBED_PROVIDER=cohere` + `WEAVIATE_COLLECTION=Product` mới cần `COHERE_API_KEY`. Không để dòng
  `EMBED_PROVIDER=` / `WEAVIATE_COLLECTION=` trống trong env file (`--env-file` truyền chuỗi rỗng). CD không tự tạo env hay sửa
  secret: **đổi provider embedding / key Cohere hoặc tắt vé Thương gia mô phỏng (`SIMULATED_BUSINESS_FARES=0`) phải sửa tay
  `/etc/vota/fresh-catalog.env` trên VM** (xem [mục dưới](#vé-thương-gia-mô-phỏng-trên-vm)).
- Collection `ProductE5` của đích chưa có vector thì lượt index đầu embed toàn bộ search unit trên CPU của VM (một lần); các
  lượt sau chỉ embed dòng mới hoặc đổi text. Job từ chối ghi vào collection đang giữ vector khác số chiều/model.
- Đường dẫn mặc định là các đường dẫn fresh ở trên; đổi bằng biến `CRAWLER_DATA_DIR`, `CRAWLER_ENV_FILE`, `CRAWLER_LOG_DIR`,
  `CRAWLER_RUNNER` của `scripts/deploy-staging-ha-crawler.sh`.

Sau deploy, `crontab -l` chỉ có một khối `VOTA CRAWLER`, cuối dòng là `fresh-run tick`. `run_daily_docker.sh report 3` và log cho biết
số dòng DB/index.

Import lại 43 vé thương gia đóng gói trong image (insert-only, giữ ID đã có) khi DB mới chưa có:

```bash
IMAGE=<AR>/vota-fresh-catalog:latest ENV_FILE=/etc/vota/fresh-catalog.env /opt/vota/bin/run_daily_docker.sh import-flights
```

Quay lại legacy cần chủ động cài `install-vota-cron.sh --job legacy` và dùng image daily. Workflow này sẽ chọn lại fresh ở lần deploy tiếp.

## Monitor: link để xem và bấm chạy

Monitor là trang web của job: sơ đồ các bước, log, báo cáo từng lượt, nút chạy lượt cào / chạy lại bước / cào lại một nguồn,
trang cấu hình (nguồn, giờ chạy, chạy liên tục), và tab **DB** xem toàn bộ database đích (`cdp`, `catalog`, `app`): số dòng
mỗi bảng, lọc / tìm / sắp xếp, bấm ô khoá để xem một dòng và các bảng trỏ tới / được trỏ tới (khoá ngoại và quan hệ quy ước
sản phẩm cha–con, vé mô phỏng–vé gốc). Tab DB chỉ đọc, không có SQL tự do; cột `password_hash`, `token_hash` hiện "(ẩn)"
(`docs/prd/deployment-plan.md` §5). Link thẳng tới một bảng: `http://<IP>:8765/#page=db&table=cdp.products`. Tab **Realtime** hiện từng lần web / agent gọi
backend (route hoặc công cụ, kết quả, ms, `stageMs` của tìm kiếm, `productId` trả về) và tổng hợp p50 / p95, làm mới 2 giây;
monitor đọc `GET /internal/calls` của backend qua `BACKEND_URL` (mặc định `http://127.0.0.1:8000`, runner truyền vào
container monitor). Cần bản backend có endpoint này; dữ liệu mất khi backend restart. Như bản deploy trước (25/09), mở bằng link không cần SSH:

1. Chạy monitor với `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1` (thao tác riêng khi được phép khởi động/cập nhật monitor). Lệnh `monitor` của job cũ
   nhận cùng hai biến. `fresh-monitor` (CD gọi lệnh này) chạy nền với `--restart unless-stopped`: bị tắt vì hết RAM hay VM khởi
   động lại thì Docker tự bật lại, không phải chờ lần deploy sau. `MONITOR_RESTART=no` chạy tiền cảnh như trước. Không giới
   hạn RAM mặc định: lượt bấm trên monitor (Cào lớn, Làm mới Trip…) chạy trong container monitor, giới hạn 1 GB đã giết
   lượt full ngày 30/09 (mã -9); `MONITOR_MEMORY` đặt giới hạn nếu cần.
2. Firewall GCP cho phép TCP `8765` vào VM (một lần, bỏ qua nếu bản deploy 25/09 đã mở):

   ```bash
   gcloud compute firewall-rules create vota-crawler-monitor --allow tcp:8765 --target-tags <tag của VM> --project <project>
   ```

3. Mở `http://<IP ngoài của VM>:8765`.

**Monitor không vào được (cổng 8765 từ chối kết nối):** VM 2 CPU / 4 GB chạy chung backend, frontend, lượt cào và monitor;
khi hết RAM Linux tắt bớt tiến trình. Kiểm trên VM:

```bash
docker ps -a --filter name=vota-fresh-catalog-monitor
docker logs --tail 50 vota-fresh-catalog-monitor
free -h && dmesg -T | grep -iE "killed process|out of memory" | tail -5
```

Nên thêm swap 2–4 GB một lần (`sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`, thêm
vào `/etc/fstab`) hoặc nâng VM lên 8 GB. Bật lại ngay: GitHub Actions → "Crawler CI" → Run workflow trên nhánh CD.

**Chưa có đăng nhập.** Ai có link đều bấm chạy / đổi cấu hình job được, và các thao tác ghi thẳng vào DB thật. Tạm chấp nhận
theo yêu cầu, bảo mật làm sau: giới hạn IP nguồn trong rule firewall (`--source-ranges`), hoặc đặt sau proxy có đăng nhập.
Tắt link: chạy lại monitor không có hai biến `MONITOR_*` (chỉ còn `127.0.0.1`, xem qua SSH), hoặc xoá rule firewall.

## Nạp catalog snapshot lên DB staging một lần (tuỳ chọn)

Dùng khi FE cần vé khứ hồi trên staging **trước** khi job cào chạy trên VM. Snapshot `2026-09-30` là snapshot `2026-09-23` cộng
vé máy bay trip.com cào ngày 30/09/2026: 11.718 sản phẩm, có 290 vé khứ hồi, 268 vé hạng Phổ thông
(`src/data_collection/snapshots/README.md`).

Chế độ `--catalog-only` chỉ upsert `cdp.products` và thay `catalog.combo_items` của các combo. Nó **không xoá** gì, không đụng
`cdp.profiles` / `cdp.events`, `app.*` (user, giỏ, đơn) hay database `insider`. Không cần Weaviate / model embedding: chuyến bay không
được index, tuyến đã có vector.

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

## Vé thương gia, khứ hồi 3/5/7 ngày và quota Cohere (30/09/2026)

- **Collector thương gia / khứ hồi** (`trip-flights`, chỉ lượt `full`): sau trang SEO, tìm thêm giá Thương gia một chiều và
  khứ hồi về sau 3, 5, 7 ngày cho 6 tuyến, xoay vòng theo ngày bay +1..+29. Mỗi lượt dùng tối đa `tripFlights.fareMinutes`
  phút (monitor, mặc định 30; `0` = tắt), trạng thái xoay vòng ở `/srv/vota/fresh-catalog-data/state/trip_fares_rotation.json`.
- **Giới hạn đã biết:** Trip cấm các trang tìm vé này trong `robots.txt` và trả `HTTP 432` ("whaleguard block") cho Chromium
  headless. Collector chờ 45 giây, thử lại một lần, rồi báo bị chặn; 3 lần liên tiếp thì dừng phần này (khoảng 2,5 phút mỗi
  lượt). Lượt `full` vẫn nạp phần SEO, report ghi nguồn `trip-flights` chưa hoàn tất. Muốn bỏ hẳn thời gian này: đặt
  `tripFlights.fareMinutes = 0` trên monitor. Không lách chống bot.
- **43 vé Thương gia thật** (bay 15/10/2026) đã có trên DB VM. CD không import; DB mới thì chạy lệnh `import-flights` ở mục
  trên.
- **Cohere 429 / nguồn quá giờ** (từ 06/10/2026 phần 429 chỉ còn ở đường lui Cohere): report `partial` nhưng trả 0 khi dữ liệu hợp lệ đã nạp; 429 được hoãn vào
  `state/index_pending.json`, cron thử lại riêng index khi tới `retryAfter`. Lỗi DB / schema / quality gate và lỗi index khác
  vẫn báo lỗi. Chi tiết: [vé thương gia và index chờ](ve-thuong-gia-va-index-cho.md).

## Vé Thương gia mô phỏng trên VM

Cho web có hạng Thương gia ở mọi ngày có vé (quy tắc: `docs/prd/data-model.md` §3). Mỗi vé máy bay có số hiệu chuyến sinh
thêm một vé Thương gia: giá vé gốc × 2,65, tên "(giá minh hoạ)", `attributes.simulated = true`, `sourceRef`
`demo:business:<sourceRef gốc>`. Vé Thương gia thật cùng hành trình và ngày luôn thắng.

**Mặc định bật**, không cần sửa env hay thao tác trên VM: sau khi bản này được deploy, mọi lượt nạp của job (kể cả tick bảo
trì đầu lượt) tự sinh / cập nhật vé mô phỏng theo giá và cửa sổ 30 ngày.

Muốn có ngay, không chờ lượt nạp: chạy một lần (chỉ ghi các dòng `demo:business:*`, dùng chung khoá ghi catalog với job; có
lượt đang ghi DB thì chờ tới khi xong):

```bash
docker run --rm --network host --env-file /etc/vota/fresh-catalog.env --entrypoint python <AR>/vota-fresh-catalog:latest -m src.data_collection.seed.simulated_business --database-url-env CLOUD_SEED_DATABASE_URL
```

Hoặc từ máy có tunnel DB: `cd src && python -m data_collection.seed.simulated_business --database-url-env
CLOUD_SEED_DATABASE_URL`. Kết quả in dạng `simulatedBusiness=<số vé mở> · simulatedBusinessClosed=… ·
simulatedBusinessWritten=…`; chạy lại lần hai ghi `0`.

**Kiểm** (SQL chỉ đọc):

```sql
SELECT available, count(*) FROM cdp.products WHERE source_ref LIKE 'demo:business:%' GROUP BY 1;
```

Monitor / report của lượt nạp DB có thêm `simulatedBusiness`, `simulatedBusinessClosed`, `simulatedBusinessWritten`.

**Tắt:** thêm `SIMULATED_BUSINESS_FARES=0` vào `/etc/vota/fresh-catalog.env` (cần quyền VM); lần nạp sau chuyển mọi vé mô
phỏng sang `available = false`. Muốn tắt ngay: thêm `--disable` vào lệnh chạy một lần ở trên. Chỉ `--disable` mà env chưa đặt
`0` thì lượt nạp sau bật lại. Không xoá dòng vì đơn cũ có thể trỏ tới.

`daily.py` (job legacy) và `seed --catalog-only` (nạp snapshot lên staging ở mục trên) theo cùng biến và cùng mặc định bật.
