# Vé thương gia thật và import bổ sung vào VM

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Codex
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: data, docs

## Mục tiêu

Lấy vé thương gia thật từ Trip.com, nạp DB VM và đóng gói để push release có thể nạp lại. Người dùng đã xác nhận 43 vé đủ demo; sau đó yêu cầu tích hợp lấy thương gia vào luồng cào định kỳ và xử lý index Cohere 429, không restart.

## File thay đổi

- `src/data_collection/snapshots/2026-09-30-business/products.jsonl.gz` — thêm: 43 vé ngày 15/10/2026 trên 6 tuyến.
- `src/data_collection/snapshots/2026-09-30-business/evidence.json.gz` — thêm: bằng chứng UI Trip.com gồm URL, thời điểm, số hiệu/giờ bay, cabin, giá, điều kiện MoMo.
- `src/data_collection/snapshots/2026-09-30-business/manifest.json` — thêm: checksum, số dòng, phạm vi nguồn.
- `src/data_collection/snapshots/2026-09-30-business/combo_items_manual.jsonl` — thêm: mapping rỗng theo định dạng snapshot.
- `src/data_collection/seed/release_flights.py` — thêm: xác minh gói và insert-only, transaction; yêu cầu tuyến cha có sẵn.
- `src/data_collection/collectors/trip_business.py` — thêm: báo giá BUSINESS từ UI, kiểm cabin/giá cùng thẻ và ngày/tuyến/chuyến, bằng chứng raw, giới hạn lượt.
- `src/data_collection/crawl.py` — sửa: mặc định enrich thương gia sau SEO Trip Flights, CLI tuyến/ngày/giới hạn, exit 2 khi nguồn thiếu quote kiểm chứng.
- `src/data_collection/normalise.py` — sửa: giữ lịch sử businessQuotes, ánh xạ BUSINESS có ngày thật và ID ổn định; tăng mapper version để bỏ checkpoint cũ.
- `src/data_collection/index_backlog.py` — thêm: cooldown 429 có file trạng thái/khóa, tăng backoff và CLI index cho daily.
- `src/data_collection/fresh_catalog.py` — sửa: hoãn riêng quota, retry index qua cả due/tick, source timeout có dữ liệu hợp lệ vẫn trả 0 với report partial.
- `src/data_collection/stream_feed.py` — sửa: index deferred không đánh dấu số dòng đã index thành công.
- `src/data_collection/daily.py` — sửa: wrapper index pending theo target; tiếp tục target khác, ghi version DB và trạng thái partial khi quota hết. Giữ thay đổi real-flight-dates có sẵn.
- `src/data_collection/run_daily_docker.sh` — sửa: lệnh import-flights trong image, dùng env kết nối VM.
- `Dockerfile.daily` — sửa: thêm Chromium/Playwright cho collector; giữ sửa argon2 có sẵn.
- `.github/workflows/crawler-ci-cd.yml` — sửa: import từ image SHA trước monitor trong bước CD.
- `src/data_collection/tests/test_release_flights.py` — thêm: bằng chứng, ngày thật, checksum, replay, rollback, thiếu cha.
- `src/data_collection/tests/test_trip_business.py` — thêm: ánh xạ 43 proof, từ chối economy/tuyến/ngày/chuyến sai, giữ quote mới nhất.
- `src/data_collection/tests/test_index_backlog.py` — thêm: 429, Retry-After, cooldown qua các lượt, backoff và lỗi khác giữ fatal.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: quota sau DB commit, due/tick retry riêng index.
- `src/data_collection/tests/test_daily.py` — sửa: quota không dừng đích nạp tiếp theo.
- `src/data_collection/tests/test_timeouts_recrawl.py` — sửa: partial source timeout giữ cảnh báo, process exit 0 sau commit.
- `src/data_collection/README.md` — sửa: hành vi partial/quota và hướng dẫn collector thương gia; giữ các sửa snapshot/khứ hồi có sẵn.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa: liên kết hướng dẫn business/quota và giới hạn deploy daily/fresh; giữ nội dung có sẵn.
- `docs/guide/ve-thuong-gia-va-index-cho.md` — thêm: chạy, import, retry, quyền VM, giới hạn demo và deploy.
- `docs/prd/update-archive/2026-09-30-embedding-local-cho-demo.md` — thêm/lưu trữ: đề xuất local bị bỏ theo lựa chọn người dùng tiếp tục Cohere với key mới. Không áp dụng vào PRD hay source.
- `history/2026-09-30-ve-thuong-gia-that-va-import-vm.md` — thêm: entry của task này.

Các file dirty khác (Makefile, collector Trip SEO, seed/config/load_products, snapshot 2026-09-30, tài liệu/test khứ hồi, đề xuất vé mô phỏng và hai entry lịch sử tương ứng) có trước task; không hoàn nguyên/gộp lịch sử của chúng vào đây.

## Quyết định

- FR-CAT-01, FR-CAT-03, NFR-REL-01. Không đổi PRD, contract, DDL. Không áp dụng đề xuất vé mô phỏng đang chờ.
- Giá đầu tiên được hiển thị với cabin Thương Gia trong chi tiết chuyến bay thẳng, cho 1 người lớn; ghi rõ điều kiện thanh toán MoMo tại nguồn. Không đoán cabin hay nhân giá economy.
- Giữ ngày bay thật, có priceObservedAt, không bịa priceValidUntil. Tách snapshot bổ sung, giữ snapshot nền của thay đổi có sẵn.
- Import chỉ thêm ID mới, không ghi đè bất cứ ID đã có; không chạm user/event/booking/combo. Thiếu cha hoặc constraint lỗi thì rollback.
- Kết nối SSH tunnel theo người dùng cung cấp; DSN chỉ lưu `.env` local ignored quyền 600. Key mới cập nhật ở `.env` gốc repo và `src/data_collection/.env` (đều ignored/600), không đưa vào image. Không ghi secret vào lịch sử hoặc source. Chưa push, không restart dịch vụ VM.
- Đã đọc PRD README/requirements/architecture/data-model/deployment-plan/test-plan/implementation-plan; spec DATABASE_SCHEMA/PRODUCT_SCHEMA/MOCK_DATA_SPEC/data-collection/schema/architecture-repo; DDL hai DB, migrations README, verify; README data/snapshot, guide deploy; history README, 10 entry mới nhất và lịch sử seed/snapshot/CD từ 21–30/09 (đặc biệt `2026-09-29-merge-release-mvp-v2-vao-newcrawl`, `2026-09-30-hang-ve-khu-hoi-trip-va-daily-tu-cap-nhat`, `2026-09-30-de-xuat-ve-thuong-gia-mo-phong`).

- Người dùng xác nhận chỉ có quyền DB, không có shell VM app. SSH tunnel DB hoạt động; SSH exec `hostname` xác thực được nhưng không trả output, đã đóng riêng các phiên kiểm tra. Không tuyên bố đã thay key hay cập nhật code VM.
- Giữ Cohere theo quyết định mới; chỉ 429 vào backlog. Cron bật thử lại riêng index khi đến hạn; stream và final cùng khóa cooldown. Không chuyển lỗi DB/quality gate/index khác thành success.
- Giữ lịch fresh hiện có: full có Trip Flights và business; daily fresh chỉ cập nhật khách sạn. Daily legacy có worker Trip cũng lấy business.

## Kiểm tra

- `release_flights --validate-only`: 43 vé, 6 tuyến.
- `unittest data_collection.tests.test_release_flights` với PostgreSQL riêng `vota_business_test_20260930`: 6 PASS. Tạo từ template0 vì template1 local có lỗi collation sẵn; không sửa cluster local.
- VM trước: 10.887 products, 0 BUSINESS. Import: 43 inserted. Replay: 0 inserted, 43 kept. Sau: 10.930 products.
- Profiles 2.000, events 7.131, users 54, bookings 1, combo_items 328: trước/sau không đổi.
- Chạy toàn bộ `db/verify.sql` trên VM bằng kết nối read-only: 16 PASS; `products >= 11387: FAIL (10930)` và `app.payments` thiếu (`42P01`). Đã sửa cách tách comment của script kiểm tra, không đổi SQL/schema. Đây là lỗi nền có trước import. BUSINESS = 43.
- `PYTHONPATH=src:src/data_collection /home/dangkhoi/miniconda3/envs/vsf2/bin/python -m pytest -q src/data_collection/tests --disable-warnings --maxfail=3`: 435 PASS, 6 SKIP (35.87s). Các test import DB được chạy riêng ở trên.
- Build `Dockerfile.daily` và `Dockerfile.fresh-catalog` thành công, tags local `business-quota-check`.
- Smoke trong container local `--network none`: release validate 43/6, index CLI/import dependency, fresh status, Chromium executable có sẵn, `.env` không nằm trong image: PASS. Không chạy browser tự động bên ngoài tool CUA; selector cùng thẻ đã đối chiếu trực tiếp DOM Trip qua CUA.
- `bash -n` hai runner, parse YAML workflow, `git diff --check`: PASS.
- `git check-ignore .env src/data_collection/.env`: cả hai ignored; không in secret.

## Còn lại / rủi ro

- Source, image local, import DB và test đã hoàn tất. Task ghi dang dở vì chưa có quyền cập nhật key/config/image trên VM app. Người có quyền VM cần triển khai bản mới; lượt/container hiện chạy vẫn dùng code/key cũ. Không restart, không push/commit trong phiên này.
- Workflow hiện chỉ deploy main/release-mvp-v1/v2/v3, và deploy image daily. Nhánh test/newcrawl không tự deploy; fresh image cần được triển khai riêng, không giả định push daily đã thay fresh.
- Giá là ảnh chụp ngày 30/09; chọn ngày bay 15/10/2026 để demo gói hiện tại. Giá có điều kiện MoMo, có thể đổi. Không có tồn kho hãng bay thời gian thực.
- Collector UI phụ thuộc selector/ngôn ngữ và truy cập mạng VM. Đã kiểm parser trên toàn bộ 43 proof và selector DOM; chưa chạy toàn bộ cào headless trên VM. Khi bị chặn/không có bằng chứng, báo partial chứ không sinh vé.
- Thiếu quota thật thì vector mới vẫn chờ; cooldown không tạo thêm quota. Giữ vector và catalog đã có; lỗi nền DB nêu trên chưa xử lý trong task.
