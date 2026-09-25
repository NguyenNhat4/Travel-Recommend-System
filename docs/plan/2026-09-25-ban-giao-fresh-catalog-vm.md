# Bàn giao triển khai fresh catalog và monitor trên VM

- Ngày: 2026-09-25
- Phạm vi: vận hành job data collection hiện hữu; FR-CAT-01/03, NFR-SEC-01. Không thay PRD, API sản phẩm hay DDL.
- Nhánh: `test/newcrawl`, đã cập nhật nền `release-mvp-v1` tới `0a9bc66`. Phần monitor mới và bộ bàn giao hiện là thay đổi local; phải commit/push trước khi CI/đội deploy checkout từ remote.
- Đích: VM ứng dụng đang có monitor cũ `http://34.142.132.251:8765/daily`. Task này chưa triển khai lên VM.

## 1. Những gì bàn giao

| Artifact trong repo | Đích sử dụng |
|---|---|
| `Dockerfile.fresh-catalog` + source cùng checkout | Build image crawler/monitor riêng |
| `src/data_collection/run_daily_docker.sh` | `/opt/vota/bin/run_daily_docker.sh` trên VM |
| `src/data_collection/fresh-catalog.env.example` | Điền secret thành `/etc/vota/fresh-catalog.env` trên VM |
| `src/data_collection/fresh-catalog-runner.env.example` | Điền image thành `/etc/vota/fresh-catalog-runner.env` trên VM |

File secret dùng cú pháp Docker `KEY=value`: không nháy, không `export`, không tham chiếu `$VAR`. Mật khẩu trong DSN cần URL-encode. `CLOUD_SEED_DATABASE_URL` là kết nối loader có quyền ghi catalog, không dùng role backend chỉ đọc. `CLOUD_DATABASE_URL` chỉ phục vụ đọc để index, được phép để trống để dùng kết nối loader. Cohere/Weaviate phải cùng hệ thống mà backend đang đọc.

Mặc định đi qua SSH tunnel **đã provision trên VM ứng dụng**: `127.0.0.1:15432` → PostgreSQL VM riêng, dù `DB_TARGET=cloud`. Không khởi động/reset PostgreSQL và không thay đổi VM DB để cài monitor. Network `host` dùng chung cho cron và monitor, không dùng tên service chỉ phân giải được trong Docker bridge. Kiểm tra tunnel tự phục hồi sau reboot theo setup của đội deploy.

## 2. Build và đưa artifact lên VM

Từ checkout đã có đầy đủ thay đổi monitor, kiểm tra `git status` và ghi lại commit triển khai. Build/push một tag bất biến (hoặc dùng digest):

```bash
export FRESH_IMAGE=REGION-docker.pkg.dev/PROJECT/REPOSITORY/vota-fresh-catalog:TAG
# Thay các giá trị REGION/PROJECT/REPOSITORY/TAG thật trước khi chạy.
docker build -f Dockerfile.fresh-catalog -t "$FRESH_IMAGE" .
docker push "$FRESH_IMAGE"
```

Chuyển riêng runner và hai file mẫu tới `/tmp/` trên VM bằng cơ chế deploy/scp hiện có. Không gửi file đã chứa secret vào Git hoặc chat. VM chỉ cần Docker, shell, cron, systemd và SSH tunnel hiện có; không cần source tree/Python/desktop.

## 3. Chuẩn bị VM và env

Chạy bằng tài khoản deploy có quyền Docker; cũng dùng tài khoản này cho cron và service monitor. Các lệnh `install -d` giữ dữ liệu trong thư mục đã tồn tại.

```bash
sudo install -d -m 750 -o 10001 -g 10001 /srv/vota/fresh-catalog-data
sudo install -d -m 750 -o "$USER" -g "$(id -gn)" /srv/vota/fresh-catalog-logs
sudo install -D -m 755 /tmp/run_daily_docker.sh /opt/vota/bin/run_daily_docker.sh
# Chỉ khởi tạo file env nếu chưa có; không ghi đè secret khi nâng cấp.
if [ ! -e /etc/vota/fresh-catalog.env ]; then
  sudo install -D -m 600 -o "$USER" /tmp/fresh-catalog.env.example /etc/vota/fresh-catalog.env
fi
if [ ! -e /etc/vota/fresh-catalog-runner.env ]; then
  sudo install -D -m 600 -o "$USER" /tmp/fresh-catalog-runner.env.example /etc/vota/fresh-catalog-runner.env
fi
```

Dùng editor trên VM điền hai file. Khi nâng cấp, bổ sung biến mới vào file cũ và thay đúng image; không chép đè toàn bộ file. Giữ `PULL=0`, chủ động pull image sau khi đổi tag để cron không cần pull mỗi 15 phút:

```bash
set -a
. /etc/vota/fresh-catalog-runner.env
set +a
docker pull "$FRESH_IMAGE"
/opt/vota/bin/run_daily_docker.sh fresh-run status
/opt/vota/bin/run_daily_docker.sh fresh-run due
```

Hai lệnh status/due chỉ kiểm trạng thái/lịch; **chưa chứng minh kết nối DB, Cohere hay Weaviate hoạt động**. DB đang có dữ liệu phải được đội DB áp migration bằng `db/migrations/run.py` với kết nối loader; không chạy lại `db/init/*.sql`. Bản monitor không thêm migration mới.

## 4. Chuyển từ job cũ sang job mới

Trước lượt full đầu tiên:

1. Lưu bản crontab hiện tại vào file riêng có quyền `600`; đọc cả user crontab, root crontab và `/etc/cron.d/` liên quan tới VOTA. Xác định lịch đang thật sự gọi crawler.
2. Tạm bỏ đúng lịch crawler cũ (`run`, `legacy-run`, `daily.py`, `cron_daily.sh`); giữ nguyên cron khác. Nếu đã có lịch fresh thì giữ tối đa một lịch. Kiểm tra `docker ps` và log để chờ lượt cũ kết thúc hoặc dừng đúng crawler theo quy trình vận hành; không dừng backend/DB.
3. Dừng đúng monitor cũ đang chiếm cổng 8765; không chạy hai monitor cùng cổng. Giữ dữ liệu cũ để rollback, không chép interim/catalog cũ vào volume fresh.
4. Chạy full bằng tay và xem báo cáo:

```bash
# Cùng shell đã export runner env ở mục 3.
/opt/vota/bin/run_daily_docker.sh fresh-run full
/opt/vota/bin/run_daily_docker.sh report 7
/opt/vota/bin/run_daily_docker.sh fresh-run status
# Khi cần đọc log ở terminal khác:
/opt/vota/bin/run_daily_docker.sh logs -f -n 200
```

`full` có ghi DB và gọi Cohere/Weaviate; sẽ chạy lâu hơn smoke test. Nếu Trip bị chặn, đọc coverage/log, không coi HTTP lỗi là hết phòng. DB có thể đã chạy bước bảo trì trước khi crawl thất bại. Index thất bại sau nạp DB: sửa cấu hình rồi chạy `fresh-run index`; không reset DB.

Ngân sách mới: lần đầu tối đa 30 khách sạn mỗi thành phố, full sau thêm 10 ID/thành phố, daily xoay tối đa 180 ID. Cấu hình lưu trên monitor thắng env: vào Cấu hình → “Áp ngân sách Trip 30 / 10 / 180” → Lưu nếu volume đã có override cũ. Giữ 2 tab giá/4 worker HTTP và 2 site đồng thời trên VM 4 GB; ngân sách không bảo đảm Trip trả đủ kết quả.

## 5. Monitor chạy bền bằng systemd

Tạo `/etc/systemd/system/vota-fresh-monitor.service`, thay `DEPLOY_USER` bằng đúng tài khoản ở mục 3. Không đặt secret trực tiếp trong unit:

```ini
[Unit]
Description=VOTA fresh catalog monitor
Wants=network-online.target
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=simple
User=DEPLOY_USER
EnvironmentFile=/etc/vota/fresh-catalog-runner.env
ExecStart=/opt/vota/bin/run_daily_docker.sh fresh-monitor --port 8765
ExecStop=/usr/bin/docker stop -t 30 ${FRESH_CONTAINER_NAME}-monitor
Restart=on-failure
RestartSec=10
TimeoutStopSec=45
UMask=0027

[Install]
WantedBy=multi-user.target
```

`ExecStop` nhắm đúng container monitor do runner tạo. Trước khi khởi động, bảo đảm không còn container monitor chạy tay cùng tên. Unit dùng Docker CLI ở `/usr/bin/docker`; đối chiếu `command -v docker` trên VM nếu khác.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vota-fresh-monitor
sudo systemctl status vota-fresh-monitor --no-pager
curl -fsS http://127.0.0.1:8765/api/overview
```

Monitor và cron cùng image/env/volume; khóa file ngăn chạy trùng giữa hai container. Server chỉ nghe `127.0.0.1`; gỡ đường public/proxy hoặc firewall rule cũ mở cổng 8765 theo quản lý hạ tầng của đội deploy. Truy cập từ máy cá nhân:

```bash
ssh -N -L 8765:127.0.0.1:8765 DEPLOY_USER@34.142.132.251
# Mở http://127.0.0.1:8765/ ; /daily tự chuyển sang giao diện mới.
```

Nếu thiếu log runner: thư mục log phải có quyền traverse/read theo group, các file `fresh-catalog-*.log` cần group-readable (`640`/`644`). Runner tự thêm group của thư mục log vào container monitor. Không mở quyền đọc env secret.

## 6. Cài duy nhất một lịch mới

Chỉ bật sau khi full và index đã được kiểm tra. Chỉnh user crontab bằng `crontab -e`, thay block crawler cũ bằng block dưới, giữ mọi dòng không thuộc crawler:

```cron
# BEGIN VOTA CRAWLER
*/15 * * * * /bin/bash -c 'umask 027; set -a; . /etc/vota/fresh-catalog-runner.env; set +a; exec /opt/vota/bin/run_daily_docker.sh fresh-run tick'
# END VOTA CRAWLER
```

Tick mỗi 15 phút; giờ bắt đầu mặc định **02:00 Việt Nam** do Python tính, không phụ thuộc timezone cron. Sau giờ đó tối đa một lần thử/ngày; lần đã bắt đầu nhưng lỗi không tự chạy lại mỗi tick. Chạy tay `full/auto/daily` bỏ qua công tắc lịch. Lượt full chạy tay không đánh dấu “đã chạy theo lịch hôm nay”, vì vậy nếu không muốn chạy thêm daily trong ngày chuyển đổi thì bật cron từ ngày kế tiếp hoặc tạm tắt lịch ở monitor.

**CI/CD hiện chưa chuyển:** `scripts/install-vota-cron.sh` vẫn sinh lệnh `run` và pipeline build crawler cũ. Không dùng installer đó để cài fresh. Đội deploy phải điều chỉnh/bỏ riêng bước cài cron cũ trong pipeline trước lần deploy backend tiếp theo; nếu để nguyên, nó sẽ thay block trên và bật job cũ trở lại. Bộ bàn giao này không thay workflow backend hay triển khai pipeline mới.

## 7. Nghiệm thu và rollback

- `crontab -l` chỉ có một lịch catalog mới; đã rà lịch crawler của user/root/system cron liên quan.
- `systemctl status vota-fresh-monitor`: active; mở qua SSH tunnel thấy giao diện fresh, không còn màn job hằng ngày cũ.
- Monitor và cron cùng `FRESH_IMAGE`, `FRESH_DATA_DIR`, `CATALOG_ENV_FILE`; cấu hình trên UI lưu lại và lượt kế tiếp dùng đúng.
- Full có `run.json`, raw/interim/catalog, `db_load.jsonl`, `index_report.json`; log/báo cáo không còn lỗi chưa xử lý. Giá/số lượng phụ thuộc nguồn thật; không nghiệm thu chỉ bằng container exit 0.
- Kiểm tra backend nhận catalog mới sau chu kỳ refresh (mặc định 15 phút).
- Stop trên monitor là dừng hợp tác; DB đang commit có thể hoàn tất, dữ liệu đã commit không tự rollback.

Rollback ứng dụng: tắt đúng lịch fresh, chờ/dừng lượt hiện hành; dừng service monitor, đổi `FRESH_IMAGE` về bản trước đã hỗ trợ fresh monitor, pull rồi khởi động lại. Giữ nguyên volume và env. Nếu quay hẳn về job/monitor legacy thì phục hồi cấu hình legacy đã lưu và chỉ bật một lịch; giao diện cũ không đọc state fresh. Rollback image không hoàn tác giá/DB đã nạp.
