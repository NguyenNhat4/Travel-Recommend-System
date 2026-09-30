# Thiết kế CI/CD Backend và cron crawler

- Ngày: 2026-09-24
- Mã FR/NFR phục vụ: `FR-CAT-03`, `FR-CAT-04`, `FR-SRC-02`, `NFR-SEC-01`, `NFR-MAINT-02`
- Nguồn yêu cầu: `docs/prd/deployment-plan.md` §3, §4, §5, §6; `src/data_collection/README.md` mục “Job hằng ngày trên VPS”
- Trạng thái: đã duyệt — đã triển khai artifact CI/CD trong repo, chờ cấu hình target VM/Environment để chạy remote

## Cập nhật crawler ngày 30/09/2026

Theo yêu cầu người dùng tự cào ngay sau deploy, workflow crawler riêng hiện build/publish cả daily và fresh. Fresh dùng image `${GAR_DAILY_IMAGE}-fresh`, tag SHA và latest; helper `scripts/deploy-crawler-vm.sh` import gói thương gia insert-only, cài khối cron duy nhất với `--job fresh` và ghi yêu cầu full trong `deploy-pending`. Runner khởi chạy ngay khi rảnh, giữ yêu cầu cho cron nếu fresh/legacy batch đang bận; chỉ xóa sau exit 0 và không xóa yêu cầu của image mới hơn. CD không đợi toàn lượt hoàn tất và không restart monitor/batch hiện tại. Phần mô tả cron legacy bên dưới là thiết kế nền trước cập nhật này; vận hành hiện tại theo `docs/guide/trien-khai-job-cao-du-lieu.md`. Backend CD giữ riêng, không bị sửa trong thay đổi này.

## Mục tiêu

Tạo một luồng CI/CD có thể kiểm tra, build, publish và triển khai Backend cùng image crawler lên VM/VPS có Docker. Sau mỗi lần deploy, crawler được cấu hình tự động để chạy hằng ngày mà không cần người vận hành sửa crontab bằng tay.

Thiết kế giữ nguyên crawler hiện tại: dữ liệu `interim`, cache, state, catalog version và log nằm trên volume của VM; secret nằm ngoài image; Backend không seed dữ liệu khi khởi động. PostgreSQL không nằm trong image hoặc Compose của VM ứng dụng: database chạy trên VM riêng bằng image DB riêng. VM ứng dụng giữ một SSH tunnel bền vững tới VM DB để Backend và crawler dùng PostgreSQL qua `127.0.0.1`.

## Phương án được chọn

GitHub Actions dùng Workload Identity Federation để xác thực GCP, build image và push tag bất biến lên Artifact Registry. Job deploy dùng `gcloud compute ssh --tunnel-through-iap` để gọi script trên VM. VM giữ lịch cron crawler hiện có; CI/CD không cài thêm systemd timer.

Image được publish với cả tag SHA và `latest`; Backend trên VM chạy `latest` theo yêu cầu. Trước khi cập nhật, deploy script ghi nhận `RepoDigests` của container hiện tại để rollback được về image trước nếu health fail. Workflow tự deploy nhánh `dev` đã quy ước; production dùng workflow dispatch hoặc tag sau khi khai báo target tương ứng.

### Bất biến an toàn cho VM dùng chung

- Không gọi `gcloud compute instances stop`, `reset` hoặc `start` trong CI/CD.
- Không chạy `docker compose down`, `docker compose down -v`, `docker system prune` hoặc thao tác xoá volume.
- Không restart, recreate hoặc thay đổi PostgreSQL, Weaviate, Redis và các service khác trên VM.
- Không pull, build, run hoặc recreate image/container PostgreSQL trên VM ứng dụng; không chạy Compose có service `postgres` trong deployment Backend.
- SSH tunnel DB chạy độc lập dưới một supervisor bền vững, chỉ bind local vào `127.0.0.1`; CI/CD không mở cổng PostgreSQL ra Internet và không tạo tunnel từ GitHub-hosted runner.
- Deploy pull image mới, restart đúng service/container Backend và refresh container monitor crawler sau khi image đã sẵn sàng. Nếu Backend hiện được quản lý bằng Compose, lệnh phải tương đương `docker compose up -d --no-deps backend`, không dựng lại dependency; crawler batch vẫn chỉ chạy theo cron.
- Lịch crawler hiện hữu vẫn là nguồn sự thật; CD có thể khởi động một lượt crawler nền sau deploy theo yêu cầu vận hành, nhưng không thêm một lịch cron thứ hai. Nếu cần bootstrap trên VM mới, script cài cron phải idempotent và có marker riêng để không tạo dòng trùng.

## Luồng CI/CD

### CI

Chạy trên pull request và push vào nhánh được cấu hình:

1. Kiểm tra Python compile/import và unit test Backend.
2. Chạy validator OpenAPI/contract khi thay đổi contract hoặc shared code.
3. Kiểm tra `Dockerfile.backend` và `Dockerfile.daily` build được.
4. Chạy smoke command không cần secret: Backend import/health wiring và crawler `daily.py --help`/`status`.

CI không chạy crawl live, không ghi database staging và không log secret.

### CD

Khi push vào nhánh staging hoặc chạy manual:

1. Build Backend và crawler với tag commit SHA.
2. Push tag SHA và `latest` vào Artifact Registry đã cấu hình qua biến workflow.
3. Gọi deploy script trên VM với hai image reference `:latest`.
5. VM ứng dụng kiểm tra SSH tunnel tới VM DB, pull image trước, cập nhật service environment với DSN `127.0.0.1:<local-port>`, restart Backend và container monitor crawler từ image mới, kiểm tra health endpoint; Redis, tunnel, VM DB và các dependency khác vẫn giữ nguyên.
6. Giữ nguyên cron crawler hiện có; nếu VM mới chưa có lịch, cài một dòng cron idempotent cho đúng runner đã chọn. Sau deploy, CD khởi động một lượt crawler nền và chỉ kiểm tra container đã bắt đầu; không chờ toàn bộ crawl hoàn tất.
7. Nếu Backend không healthy, deploy script khôi phục image digest trước đó và báo lỗi.

## Lệnh crawler và cron khác nhau thế nào?

`python daily.py run` hoặc `run_daily_docker.sh run` chỉ chạy **một lượt**. Bản thân lệnh không tự lặp lại vào ngày hôm sau.

Repo đã ghi rõ lịch cron mẫu ở `src/data_collection/README.md` dòng 138:

```cron
0 2 * * * IMAGE=<AR>/vota-daily:latest PULL=1 /đường/dẫn/src/data_collection/run_daily_docker.sh run
```

Cron là phần lập lịch; runner là phần thực thi. Đến 02:00, cron gọi runner, runner tạo container tạm cho một lượt crawl, ghi log vào `/srv/vota/daily-data/logs`, rồi container thoát. `run_daily_docker.sh` tiếp tục bảo vệ hai lớp: bỏ qua lượt mới nếu container trước còn chạy và `daily.py` giữ lock trong data directory.

Các lệnh vận hành chính:

```bash
crontab -l
crontab -e
/đường/dẫn/src/data_collection/run_daily_docker.sh run  # chạy tay một lượt
tail -n 200 /srv/vota/daily-data/logs/daily-errors.log
```

CI/CD chỉ chịu trách nhiệm phát hành image và cập nhật tag/digest trong dòng cron hoặc file cấu hình mà dòng cron đọc. Không chạy lịch trên GitHub Actions vì crawler cần data volume, SSH tunnel tới VM DB riêng, Weaviate private network và internet của VM ứng dụng.

### SSH tunnel tới VM DB

Tunnel được mở từ VM ứng dụng, ví dụ:

```bash
autossh -M 0 -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:15432:<db-vm-private-host>:5432 \
  <db-ssh-user>@<db-vm-private-host>
```

Backend dùng `DATABASE_URL`/`CDP_DATABASE_URL` trỏ tới `127.0.0.1:15432`; crawler dùng `CLOUD_SEED_DATABASE_URL` trỏ tới cùng local port nếu cần nạp catalog. `autossh` phải được quản lý bởi supervisor hiện có trên VM hoặc một service long-running riêng; không dùng GitHub Actions để giữ tunnel và không dùng tunnel này làm lịch crawler. Health check của Backend chỉ được chạy sau khi local port đã accept kết nối.

## Secret và quyền

- GitHub Actions dùng Workload Identity Federation, không lưu service-account JSON key.
- VM ứng dụng được provision trước `/etc/vota/backend.env`, `/etc/vota/daily.env` và cấu hình SSH tunnel, quyền `0600`, owner là user/service account chạy workload. Các DSN trong đó trỏ tới local port của SSH tunnel; không dùng hostname `postgres` từ Compose local.
- Workflow không truyền `DATABASE_URL`, `COHERE_API_KEY`, `WEAVIATE_API_KEY` hoặc token crawler qua command line/log.
- Deploy account chỉ cần quyền push Artifact Registry ở CI và quyền SSH/IAP plus quyền restart service ở VM.
- Docker container Backend và crawler chạy non-root khi image hỗ trợ; data directory giữ owner của user vận hành.

## File dự kiến

- `.github/workflows/backend-ci-cd.yml`: CI, build/publish image và gọi deploy.
- `ops/docker-compose.backend-vm.yml`: Compose app-only được workflow chép lên VM; dùng đúng image Backend, `network_mode: host`, `/etc/vota/backend.env` và mount key RS256 read-only.
- `scripts/deploy-backend-vm.sh`: deploy `latest`, health check, rollback về digest trước.
- `scripts/install-vota-cron.sh`: tùy chọn bootstrap một dòng cron idempotent trên VM mới; không chạy nếu VM đã có lịch.
- `docs/spec/2026-09-24-backend-cicd-crawler-timer-design.md`: thiết kế này.

## Kiểm tra nghiệm thu

- CI syntax được kiểm tra bằng actionlint/yaml parser nếu có trong runner và `bash -n` cho script.
- Image Backend và crawler build được trong CI; crawler image giữ kích thước tối ưu đã đo trước đó.
- Deploy script chạy dry-run/local fixture không chạm production DB.
- Trên VM: `crontab -l` chỉ có đúng lịch crawler được quản lý với `IMAGE=:latest` và `PULL=1`, chạy runner bằng tay một lượt và kiểm tra log có exit code thật.
- Trên VM: tunnel đang kết nối, `127.0.0.1:15432` chỉ listen loopback, Backend health trả HTTP 200 qua đường DB tunnel; VM DB không bị recreate hoặc restart.
- Backend: `GET /health` trả HTTP 200 sau deploy.
- Rollback: cố ý đưa một image không healthy trong môi trường test và xác nhận service quay về digest trước.
- Không coi việc image push hoặc unit active là bằng chứng crawler đã crawl thành công; cần log lượt chạy và trạng thái `daily.py`.

## Rủi ro và ranh giới

- Tên VM, zone, user deploy và Artifact Registry repository backend chưa được suy đoán trong thiết kế; chúng sẽ là input bắt buộc của GitHub Environment/secret hoặc repository variable.
- Việc cài cron chỉ cần một lần bootstrap quyền của user chạy job; CI không tự cấp IAM, mở firewall hoặc tạo database/Weaviate. Bootstrap cũng không được stop/reboot VM.
- Chưa triển khai production target trong cùng thay đổi nếu chưa có tên VM, zone và environment secret tương ứng.
- Thiết kế không thay đổi contract API, schema database, luồng frontend hoặc crawler behavior; không cần đề xuất lệch PRD.
