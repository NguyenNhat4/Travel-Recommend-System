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
     - chạy `FRESH_IMAGE="$FRESH_IMAGE:latest" run_daily_docker.sh fresh-monitor`;
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
     - monitor (`ssh -L 8765:127.0.0.1:8765 <vm>` rồi mở http://127.0.0.1:8765): sơ đồ luồng không có ô đỏ.
4. **Quay lại job cũ** (nếu cần): `install-vota-cron.sh --job legacy …` và dùng lại `monitor`.

## Không dùng trên VM

- `src/data_collection/cron_daily.sh`: cron **máy cá nhân** của job cũ, không cài trên VM.
- Đã gỡ ngày 29/09/2026: `cron_hotels_daily.sh`, `run_fresh_catalog_vm.sh`, `cron_run.sh`, `run_forever.sh`,
  `run_extra_queue.sh`, `stop_crawl.sh` và các script chạy tay khác. Hướng dẫn cũ nhắc tới chúng không còn đúng.
- Chạy liên tục (`stream.enabled`, `stream.db`) mặc định **tắt**. Bật trên monitor sau khi lượt đầu trên VM ổn
  (`docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md`, P2).
