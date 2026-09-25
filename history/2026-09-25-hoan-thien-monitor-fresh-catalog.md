# Hoàn thiện monitor cho fresh catalog và tăng ngân sách khách sạn Trip

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Tiếp tục phần code dang dở từ phiên hết hạn sử dụng: monitor cũ `/daily` chỉ đọc `daily.py`, không theo dõi `fresh_catalog.py`. Hoàn thiện monitor cho job mới, cấu hình/lịch, log và truy vết theo lượt. Người dùng chọn ưu tiên lấy nhiều khách sạn Trip mỗi lượt. Hoàn thành ở source và image kiểm thử local; chưa triển khai lên VM.

Phục vụ FR-CAT-01/02/03/04 (thu thập, chuẩn hóa, phân cấp, giá/lịch, combo) và NFR-SEC-01 (không trả secret qua API). Monitor là công cụ vận hành data collection hiện hữu, không thêm API sản phẩm hay thay đổi PRD/DDL. Giữ ranh giới loader và catalog 13 trường; nhật ký job nằm trong file.

## File thay đổi

Các file bên dưới bao gồm phần đã sửa/dang dở khi nhận task và phần hoàn thiện trong phiên này; không hoàn tác thay đổi có trước.

- `src/data_collection/.env.example` — sửa: biến cấu hình job fresh, ngân sách Trip và môi trường DB.
- `src/data_collection/README.md` — sửa: cách chạy monitor mới, cấu hình, lịch tick, volume/log, SSH tunnel và chuyển cron.
- `src/data_collection/collectors/common.py` — sửa: log thời gian/status/bytes mỗi HTTP request ở mức debug.
- `src/data_collection/collectors/trip_live.py` — sửa: dùng chung HTTP session trong batch, kết thúc chờ ngay khi có JSON giá hợp lệ, giới hạn scan lượt đầu, raw JSON gzip bỏ review/tên người, xóa profile trình duyệt sau đóng.
- `src/data_collection/crawl.py` — sửa: tùy chọn ngân sách theo nguồn từ runner.
- `src/data_collection/daily_api.py` — xóa: API monitor job cũ; việc xóa đã staged khi tiếp nhận task.
- `src/data_collection/deepen_jobs.py` — sửa: bỏ phụ thuộc class Monitor cũ, giữ kiểm tra PID riêng.
- `src/data_collection/fresh_catalog.py` — sửa: cấu hình chung, due/tick, lịch theo giờ Việt Nam, log bước, dừng hợp tác, retention và báo cáo DB/index.
- `src/data_collection/fresh_catalog_db.py` — sửa: cho phép lượt tắt Trip không cần coverage Trip; báo cáo từng dòng trước/sau, chỉ công bố sau commit DB thành công.
- `src/data_collection/fresh_run_log.py` — thêm: trạng thái lượt, heartbeat, stop request, bước, tee log, lịch sử tóm tắt và dọn lượt cũ; join heartbeat trước kết thúc.
- `src/data_collection/fresh_settings.py` — thêm: cấu hình có kiểm tra kiểu/ràng buộc, thứ tự ưu tiên file/env/default, lịch Việt Nam và mô tả form, không chứa secret.
- `src/data_collection/monitor.py` — sửa: API overview/run/log/artifact/catalog/trace/DB/Trip/settings/start/stop cho job fresh; loopback/Host guard, giới hạn body và đường dẫn artifact; `/daily` và `/pipeline` chuyển hướng về `/`.
- `src/data_collection/monitor_ui/index.html` — sửa: giao diện mới đọc API fresh, lịch sử/bước, raw/interim/catalog/báo cáo, tra sản phẩm, cấu hình và nút áp ngân sách Trip.
- `src/data_collection/monitor_ui/daily.html` — xóa: giao diện job cũ; việc xóa đã staged khi tiếp nhận task.
- `src/data_collection/monitor_ui/pipeline.html` — xóa: giao diện batch cũ; việc xóa đã staged khi tiếp nhận task.
- `src/data_collection/run_daily_docker.sh` — sửa: hỗ trợ fresh-run due/tick; fresh-monitor/monitor dùng image/env/volume fresh và mount log chỉ đọc, thêm group của thư mục log.
- `src/data_collection/run_fresh_catalog_container.sh` — sửa: hỗ trợ due/tick; bỏ qua Xvfb khi tick không đến lịch.
- `src/data_collection/tests/test_api_sources.py` — sửa: bỏ test API/setting của monitor đã gỡ; giữ test collector.
- `src/data_collection/tests/test_pipeline_demo.py` — sửa: bỏ test giao diện pipeline đã gỡ; giữ test pipeline/PID.
- `src/data_collection/tests/test_fresh_monitor.py` — thêm: 24 test cấu hình/lịch, khóa và dừng, trạng thái chết, retention, API/path guard, artifact/trace, Trip và Docker runner.
- `history/2026-09-25-hoan-thien-monitor-fresh-catalog.md` — thêm: ghi lịch sử task này.

## Quyết định

- Giữ quyết định tại `history/2026-09-25-tach-lenh-fresh-run.md`: `run`/`legacy-run` vẫn gọi job cũ. Job mới dùng `fresh-run`; không đổi ngầm ý nghĩa lệnh CI đang dùng.
- Cron mới gọi `fresh-run tick` mỗi 15 phút; cấu hình mặc định chạy sau 02:00 Việt Nam, full mỗi 7 ngày, các ngày còn lại daily. Mỗi ngày tối đa một lần thử theo lịch; lỗi thì chạy lại tay. `auto/full/daily` chạy tay không phụ thuộc bật/tắt lịch. Recheck lịch dưới khóa file; monitor và cron phải dùng chung volume.
- Tăng mặc định Trip từ 10 lên 30 khách sạn/thành phố lần đầu, 3 lên 10 ID mới/thành phố ở full sau, 60 lên 180 khách sạn/lượt daily. Giữ số worker/tab và delay mặc định; dùng lại HTTP session và chờ theo sự kiện để giảm thời gian thừa. Không tuyên bố số khách sạn thực tế hay tốc độ đã đo trên VM.
- Cấu hình lưu trên monitor ưu tiên hơn env, env ưu tiên hơn default. Vì env cũ có thể giữ ngân sách cũ, UI có nút áp 30/10/180 rồi lưu. Giới hạn tối đa số lượng cho phép chỉnh, không tăng mặc định độ đồng thời.
- Giữ nguồn giá thật và kiểm coverage cho khách sạn Trip; không tạo giá thay thế khi bị chặn. Chỉ bỏ yêu cầu coverage khi nguồn khách sạn Trip được tắt rõ ràng.
- Dừng là hợp tác: ngắt tác vụ cào con, bỏ bước tiếp theo; transaction DB đang chạy có thể hoàn tất và dữ liệu đã commit được giữ. Lượt nhận tín hiệu dừng ở cuối vẫn báo stopped.
- Giữ raw/báo cáo chi tiết N lượt gần nhất (mặc định 7), lịch sử tóm tắt ở state. API artifact chỉ đọc danh sách artifact cho phép; không dùng nó để đọc browser profile. Không thêm bảng job hay sửa schema.
- Monitor chạy loopback, không dùng Docker socket. Không tự thay firewall/proxy hoặc dừng service đang chạy trên VM.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/dangkhoi/miniconda3/envs/vsf/bin/python -m pytest -q -p no:cacheprovider src/data_collection/tests`: **330 passed, 3 skipped** (25.83 giây).
- Sau sửa group đọc log ở runner: cùng lệnh với `src/data_collection/tests/test_fresh_monitor.py`: **24 passed**.
- `bash -n src/data_collection/run_daily_docker.sh src/data_collection/run_fresh_catalog_container.sh`: PASS.
- `git diff --check`: PASS.
- `docker build -f Dockerfile.fresh-catalog -t vota-fresh-catalog:monitor-check .`: PASS, image local; chưa push registry.
- Chromium/Playwright smoke bằng fixture tạm (`/tmp/vota-ui-smoke.py`): PASS overview, chuyển từ `/daily`, chi tiết lượt/catalog, trace sản phẩm, lưu cấu hình, mobile 390px không tràn trang, không lỗi JavaScript. Đã xem screenshot desktop/mobile.
- Docker runtime smoke (`/tmp/vota-docker-smoke.py`): PASS `fresh-run due/tick` khi lịch tắt, không tạo lượt cào, cấu hình saved thắng env và được monitor đọc từ cùng volume; monitor đọc log runner từ thư mục mode 750. Không dùng DB/network nguồn thật.
- PostgreSQL 16 tạm, DDL `db/vota_schema.sql` (`/tmp/vota-db-smoke.py`): PASS nạp không Trip, thêm/cập nhật giá với report trước/sau, deferred trigger từ chối lúc commit thì DB rollback và không xuất report thành công. Container tạm đã xóa; không đụng staging.
- GET read-only tới VM: `/daily` vẫn trả trang “V-OTA · Job hằng ngày”; `/api/overview` và `/api/daily/overview` có cấu trúc API cũ. Không bấm chạy/dừng hay ghi cấu hình VM. Kết quả này xác nhận monitor cũ, không xác nhận crontab thực tế.
- Không đổi contract, schema hay seed nên không chạy validate_contract hoặc db/verify.sql toàn snapshot. Bộ test DB phía trên kiểm tra đúng phạm vi loader/report.

## Còn lại / rủi ro

- Source local đã hoàn thiện; chưa commit/push hay triển khai VM. Cần build/push tag triển khai, cập nhật runner/image, dùng cùng FRESH_DATA_DIR cho cron/monitor, thay dòng cron cũ bằng fresh-run tick và chạy fresh-monitor. Hướng dẫn trong README data collection.
- `scripts/install-vota-cron.sh` của CI hiện vẫn cài cron job cũ. Deploy bằng luồng CI đó có thể khôi phục dòng cũ; cần đội deploy phối hợp trước chuyển lịch. Không chạy hai job trên cùng DB staging.
- Trip.com có thể chặn VM. Chưa chạy full crawl hoặc benchmark trên VM; tăng budget không bảo đảm đạt quota hay giảm tổng thời gian lượt lớn. Lỗi nguồn phải đọc trong coverage/log.
- Monitor mới chỉ nghe loopback. URL public cũ chưa bị đóng/thay bởi task này; sử dụng SSH tunnel theo README khi triển khai.
- Env của monitor phải dùng DB/Weaviate hostname truy cập được từ host network. Log runner cần group-readable; trạng thái cấu hình volume thuộc UID 10001 của image.
