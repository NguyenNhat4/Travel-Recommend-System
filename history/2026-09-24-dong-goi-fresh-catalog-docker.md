# Đóng gói luồng cào mới thành Docker image cho VM console

- Ngày: 2026-09-24
- Tác giả: người dùng / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, deployment

## Mục tiêu

VM Ubuntu của đội triển khai chỉ chạy Docker, không có source tree hoặc môi trường Python. Đưa toàn bộ luồng cào mới của nhánh `test/newcrawl` vào một image riêng, giữ state xoay vòng ID trên volume và tiếp tục nạp DB sau mỗi lượt.

## File thay đổi

- `Dockerfile.fresh-catalog` — thêm: image Python 3.11 chứa collector, requirements, Chromium và Xvfb; chạy bằng user `app` UID 10001.
- `Dockerfile.fresh-catalog.dockerignore` — thêm: giới hạn build context vào code data collection, loại data, snapshot, test và `.env`.
- `src/data_collection/run_fresh_catalog_container.sh` — thêm: entrypoint `auto/full/daily/status`, chạy crawler dưới Xvfb trong container.
- `src/data_collection/run_daily_docker.sh` — sửa: lệnh `run` dùng image mới, volume state, env file, log host và mạng Docker; các lệnh workflow cũ giữ nguyên.
- `src/data_collection/run_fresh_catalog_vm.sh` — sửa: wrapper tương thích chuyển tới `run_daily_docker.sh run`.
- `src/data_collection/README.md` — sửa: hướng dẫn build/push image và chạy VM chỉ bằng Docker, một runner script, env file, volume và cron.
- `history/2026-09-24-dong-goi-fresh-catalog-docker.md` — thêm: entry này.

## Quyết định

- Phục vụ FR-CAT-01/02/03/04: không đổi schema, cách cào, bước chuẩn hóa hoặc DB upsert của luồng mới. Chỉ thay cách đóng gói và khởi chạy theo `docs/prd/deployment-plan.md` §3.
- Tài khoản `app` trong image chạy Chromium; volume `/data` thuộc UID/GID 10001. Runner không ép UID của host vì Chromium crash trong trường hợp đó. Log ở thư mục riêng thuộc user chạy cron.
- VM chỉ nhận image từ registry và một bản copy `run_daily_docker.sh`; không cần checkout repo hay cài Python/Chromium/Xvfb trên host. Secret chỉ ở env file trên VM, không nằm trong image.
- Không push nhánh; người dùng sẽ tự push. Không bật cron mới trên VM trong task này.

## Kiểm tra

- `docker build -f Dockerfile.fresh-catalog -t vota-fresh-catalog:local .`: pass; image khoảng 2 GB.
- Copy runner ra `/tmp` để mô phỏng VM không có source, chạy `run status` với volume thuộc UID 10001: pass; báo lượt kế tiếp là `full`.
- `docker run` với user mặc định, volume, `--network host`, `--shm-size 512m` và Xvfb: Chromium mở trang `about:blank` thành công.
- `run full` với `DB_TARGET=invalid`: trả mã 3 và ghi log lỗi như mong đợi, không chạm DB.
- Trong image: không có `.env`, `data/products.jsonl` hay `snapshots`; `crawl.py --help`, `normalise.py --help` và `load_catalog.py --help` chạy được.
- `bash -n` cho ba shell script mới/sửa và `git diff --check`: pass.

## Còn lại / rủi ro

- Chưa chạy full đa nguồn và upsert trên Google Cloud VM thật; đội deploy cần cấu hình DB đã migrate, thử `run full` một lần, kiểm tra log rồi mới bật cron.
- Image khoảng 2 GB trên đĩa; VM cần đủ dung lượng cho image, volume state và log. Số ID tăng có thể khiến vòng làm mới dài hơn ngân sách 60 khách sạn/ngày.
