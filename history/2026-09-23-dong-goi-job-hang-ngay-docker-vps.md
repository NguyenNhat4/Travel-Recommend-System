# Đóng gói job hằng ngày thành image Docker chạy trên VPS

- Ngày: 2026-09-23
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: `codex/integrate-catalog-into-release`
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Team deploy cần đưa job hằng ngày của data collection (`daily.py`: cào → chuẩn hoá → gate → promote → nạp DB → embed) lên VPS
và chỉ muốn nhận một script. Người dùng chốt chạy trên VPS bằng Docker + cron (không Cloud Run, không bucket): dữ liệu làm việc
nằm trên ổ VPS nên `daily.py` giữ nguyên. Phục vụ FR-CAT-01, FR-CAT-03 (cửa sổ + lịch 30 ngày, giá), FR-CAT-04 (mapping combo);
NFR-SEC-01 (không đưa secret vào image hay log). Nối tiếp `2026-09-23-cao-tu-dong-console-vinpearl.md` (dang dở).

## File thay đổi

- `Dockerfile.daily` — thêm: image Python 3.11 cho job, `TZ=Asia/Ho_Chi_Minh` (+ tzdata), `VOTA_DATA_DIR=/data`, user không
  phải root; cài requirements data collection trừ playwright và đúng ba gói backend mà bước embed import (pydantic,
  pydantic-settings, numpy — ràng buộc phiên bản lấy từ `src/backend/requirements.txt`).
- `Dockerfile.daily.dockerignore` — thêm: context chỉ gồm `src/__init__.py`, `src/backend`, `src/data_collection`; loại `data/`,
  `cache/`, test, `.env*`, `__pycache__`.
- `src/data_collection/run_daily_docker.sh` — thêm: script cho người vận hành: `init` (chép interim nền, không đè; chép
  `combo_items_manual.jsonl` từ snapshot trong image), `run` (lượt cho cron: log theo lượt giữ 30 ngày, bỏ qua khi container lượt
  trước còn chạy, kéo image trước mỗi lượt, trả mã thoát của `daily.py`), `daily <lệnh>` (thao tác tay), `monitor` (trang `/daily`
  qua mạng host vì `monitor.py` chỉ nghe 127.0.0.1). Container chạy bằng uid:gid chủ `DATA_DIR`.
- `src/data_collection/.env.example` — sửa: khối Job hằng ngày ghi cách dùng làm `ENV_FILE` của Docker (không nháy, chmod 600),
  kết nối DB staging qua IP nội bộ khi cùng VPC, thêm dòng `COHERE_API_KEY`.
- `src/data_collection/README.md` — sửa: mục "Chạy bằng Docker trên VPS (bàn giao team deploy)"; câu SSH tunnel chỉ còn cho máy
  ngoài VPC.

## Quyết định

- Chạy trên VPS thay vì Cloud Run Jobs (người dùng chốt 23/09/2026): VPS có ổ đĩa nên không cần bucket, không cần script kéo/đẩy
  trạng thái, khoá `flock` + sqlite + trang `/daily` giữ nguyên. Không lệch PRD: Docker đã có ở `deployment-plan.md` §3; không đổi DDL.
- Không cài cả requirements backend: chuỗi import của `src.backend.jobs.embed_products` chỉ cần pydantic, pydantic-settings, numpy,
  httpx, psycopg (đã dò các `__init__`); bản đủ kéo thêm langgraph/langchain/openai không dùng tới.
- Dockerfile đặt ở root như `Dockerfile.backend` (context cần cả `src/backend` và `src/data_collection`); file ignore riêng vì
  `.dockerignore` root loại `src/data_collection`.
- Người dùng chốt thêm cùng ngày: không đưa data version vào DB; giữ cách tính "thấy" = có trong kết quả chuẩn hoá (dòng booking.com
  từ interim cũ vẫn đang bán); vector giữ Weaviate theo PRD (không quay lại pgvector).
- Không làm theo `tripcom-hotel-crawler` (giả vân tay TLS, proxy xoay vòng, đường dẫn robots.txt cấm) dù người dùng đề nghị;
  handbook §3 yêu cầu kiểm tra `robots.txt`.

## Kiểm tra

- `bash -n src/data_collection/run_daily_docker.sh`: pass.
- `docker build -f Dockerfile.daily -t vota-daily:test .`: pass, image 394 MB. Trong image: không có `data/`, `cache`, test, `.env`;
  Python 3.11.16, giờ +07; `crawl.py --help`, `daily.py --help`, `import src.backend.jobs.embed_products`, `python -m
  data_collection.seed --help` đều chạy; không có playwright.
- `init` với interim nền (7 file, thư mục tạm): chép 7 file + `combo_items_manual.jsonl`; chạy lần hai chép 0 file.
- `run` với `MAX_HOURS=0.01` (36 s cào thật, `DAILY_DESTINATIONS=Đà Nẵng`, Agoda 1 khách sạn), nạp vào Postgres 16 tạm dựng từ
  `db/init` qua `DOCKER_NETWORK`: 3 worker dừng êm vì hết giờ, promote 11.387 dòng, nạp cloud ok, mã thoát 2 (đúng quy ước: có
  worker không xong); DB: `cdp.products` 11.387 dòng, `catalog.combo_items` 243 dòng parse + 64 dòng manual; file trong `DATA_DIR`
  thuộc user chạy script.
- `daily publish --load cloud` lần hai: 0 inserted, 0 updated, mã thoát 0.
- `run` khi container cùng tên đang chạy: mã 0, ghi dòng SKIP vào `daily-errors.log`.
- `monitor --port 18765`: `/daily` HTTP 200, `/api/daily/overview` trả version đang dùng.
- Không chạy bước embed thật (không dùng quota Cohere trong test; env thử không có `COHERE_API_KEY`/`CLOUD_WEAVIATE_URL` nên bước
  embed tự bỏ qua). Không chạy trên VPS thật. PG tạm, mạng docker và dữ liệu thử đã xoá.
- Build trên máy này chậm (~10–20 kB/s tới PyPI), không phải lỗi Dockerfile.

## Còn lại / rủi ro

- Team deploy: VPS phải ra được internet (cào) và tới được Postgres + Weaviate staging; role DB cho job (INSERT/UPDATE
  `cdp.products`, DELETE/INSERT `catalog.combo_items`); build/push image lên Artifact Registry; tạo `ENV_FILE` và dòng cron.
- Weaviate staging: cluster Weaviate Cloud trong `.env` gốc còn chạy (23/09) nhưng mới có 5 object; nếu là Sandbox thì hết hạn sau
  14 ngày — chọn gia hạn hoặc tự host trên VM.
- Chưa chạy bước embed thật và chưa cào từ IP của VPS.
- `deployment-plan.md` §2 chưa liệt kê biến `DAILY_*`/`CLOUD_*` (tồn đọng từ job hằng ngày).
- Cron của repo cũ `~/code/vsf/data-collection/cron_run.sh` đã được comment trong crontab theo yêu cầu người dùng (ngoài repo này).
