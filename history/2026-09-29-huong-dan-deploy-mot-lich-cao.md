# Deploy: một lịch cào duy nhất (`install-vota-cron.sh --job`) và hướng dẫn triển khai job cào

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: ci (script deploy), docs

## Mục tiêu

Người yêu cầu: "chủ yếu tôi muốn team deploy không bị nhầm với các cron cũ, và deploy dễ". Trước đó đã chọn để đội deploy
tự sửa workflow CI/CD (không sửa `.github`).

Hiện trạng tìm được:
- CD crawler của `release-mvp-v2` luôn chạy `install-vota-cron.sh` không phân biệt job, và luôn cài **job cũ**
  (`run_daily_docker.sh run`, `daily.py`) mỗi lần push;
- job mới cần `fresh-run tick` mỗi 15 phút;
- cài tay lịch job mới thì lần deploy sau bị thay lại; cài thêm thì hai job cùng ghi một DB.

## File thay đổi

- `scripts/install-vota-cron.sh` — sửa:
  - thêm `--job legacy|fresh` (mặc định `legacy`) và `--log-dir`;
  - đường dẫn / lịch mặc định theo job:
    - legacy: `0 2 * * *`, `/srv/vota/daily-data`, `/etc/vota/daily.env`;
    - fresh: `*/15 * * * *`, `/srv/vota/fresh-catalog-data`, `/etc/vota/fresh-catalog.env`, `/srv/vota/fresh-catalog-logs`;
  - cả hai ghi vào cùng khối `# BEGIN/END VOTA CRAWLER` nên cài job này thay job kia.
- `scripts/tests/test-install-vota-cron.sh` — thêm, crontab tạm:
  - mặc định ra đúng dòng cũ;
  - `--job fresh` thay job cũ, giữ dòng cron khác, chỉ một khối, chạy lại không nhân đôi;
  - quay lại `--job legacy`;
  - tham số ghi đè; `--job` lạ / `--log-dir` tương đối bị từ chối.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — thêm:
  - bảng job cũ / job mới;
  - hiện trạng CI/CD;
  - việc đội deploy cần sửa ở `crawler-ci-cd.yml` (build / publish `Dockerfile.fresh-catalog`, `--job fresh`,
    `fresh-monitor`);
  - chuẩn bị VM, kiểm sau deploy, quay lại job cũ;
  - các script không dùng / đã gỡ.
- `src/data_collection/README.md` — sửa: dẫn tới hướng dẫn ở mục "Đóng gói và bàn giao" và ở đoạn "chỉ một lịch cào".
- `history/2026-09-29-huong-dan-deploy-mot-lich-cao.md` — thêm: entry này.

## Quyết định

- Mặc định `--job legacy` để CD hiện tại (không truyền `--job`) cài đúng dòng như trước. Đã so `--dry-run` với bản
  trước khi sửa: giống hệt.
- Không sửa `.github/workflows` (quyết định trước của người yêu cầu); hướng dẫn ghi rõ ba chỗ cần đổi.
- `cron_daily.sh` giữ (cron máy cá nhân của job cũ, đi cùng `daily.py`), ghi rõ "không dùng trên VM".
- `deploy-backend-vm.sh` chỉ kiểm có file `install-vota-cron.sh`, không cài cron: không cần sửa.

## Kiểm tra

- `bash scripts/tests/test-install-vota-cron.sh`: passed.
- `bash scripts/tests/test-backend-vm-cd-sync.sh`: passed.
- `bash -n` `install-vota-cron.sh`, `check-db-tunnel.sh`, `run_daily_docker.sh`: ok.
- So `--dry-run` mặc định với bản trước khi sửa: giống hệt.
  - Khi so, đã dùng `git stash` vài giây trong lúc bộ test backend đang chạy nền. Đã dừng lượt đó và chạy lại toàn bộ
    backend sau khi cây ổn định (kết quả ở entry `2026-09-29-contract-fare-classes.md`).

## Còn lại / rủi ro

- Đội deploy sửa `crawler-ci-cd.yml` theo hướng dẫn. Cho tới lúc đó, VM vẫn chạy job cũ; không cài tay job mới.
- Nên thêm `bash scripts/tests/test-install-vota-cron.sh` vào bước "Validate deployment scripts" của CI (việc của đội
  deploy).
- Chưa push (người yêu cầu tự push `test/newcrawl`).
