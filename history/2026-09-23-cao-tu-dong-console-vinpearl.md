# Job cào hằng ngày trên console: Vinpearl không trình duyệt, combo bay + ở, Agoda API, data version, nạp chỉ-catalog, UI /daily

- Ngày: 2026-09-23
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: `codex/integrate-catalog-into-release`
- Trạng thái: dang dở
- Phạm vi: data, database

## Mục tiêu

Người dùng cần luồng cào tự động chạy được trên VPS chỉ có console (không trình duyệt), mỗi ngày làm mới giá + lịch 30 ngày,
mở rộng catalog, tự nạp Postgres local + cloud và embed Weaviate; có data version và UI để theo dõi, kiểm soát, switch giữa các
version. Tham khảo cách cào của nhánh `origin/crawler` (`vota-crawler`, tqanh123) nhưng giữ pipeline `src/data_collection` và cách
nạp DB hiện có. Phục vụ FR-CAT-01, FR-CAT-03 (lịch khả dụng 30 ngày và giá), FR-CAT-04 (combo); `project-brief.md` §4.2 ghi dữ liệu
nạp qua snapshot và cấu hình khả dụng định kỳ nên crawl định kỳ nằm trong phạm vi. Không lệch PRD (PRD không ghi số sản phẩm hay
số điểm đến).

## File thay đổi

- `src/data_collection/collectors/vinpearl.py` — sửa: `VinpearlOptions.no_browser`; tách `_get_json`; danh sách tour gọi HTTP,
  bị chặn thì dùng `booking-voucher-api` (`voucher_item`), rồi mới tới cache; chi tiết tour đọc cache trước, gặp Cloudflare một lần
  thì cả lượt chỉ dùng cache; `_browser()` báo lỗi nếu bật `no_browser`.
- `src/data_collection/collectors/vinpearl_bundles.py` — thêm: combo vé khứ hồi + khách sạn (`/api/bundle/v2/search`) theo tuyến
  × ngày khởi hành, gọi lại khi 404 do cache nguội phía server, một bản ghi mỗi (sân bay đi, khách sạn) với `pricesByDate`.
- `src/data_collection/collectors/agoda_api.py` — thêm: agoda.com không trình duyệt — sitemap (41 file) → trang khách sạn lấy
  `hotel_id` → `GetSecondaryData` từng ngày; phạm vi 38 điểm đến, tối đa 50 khách sạn/điểm (ưu tiên khách sạn đã có); tiến độ
  sqlite (dừng lúc nào cũng được); thứ tự: mọi khách sạn một ngày trước rồi lấp dần 30 ngày, còn ngân sách thì làm mới ngày gần;
  raw gọn đã bỏ review; `--max-hours` dừng êm; xuất `interim/agoda_api.jsonl` giữ `sourceRef` cũ `agoda:hotel:<slug>:<city>`.
- `src/data_collection/collectors/plan.py` — sửa: `V1_DESTINATIONS` và nhóm `@v1` = đúng 38 điểm đến của catalog 11.387 dòng.
- `src/data_collection/crawl.py` — sửa: cờ `vinpearl --no-browser`, lệnh `vinpearl-bundles`, lệnh `agoda-api`.
- `src/data_collection/normalise.py` — sửa: `vinpearl_bundle_product` → `combo`, `sourceRef = vinpearl:bundle:<sân bay>:<mã KS>`;
  `agoda_api_hotel` → khách sạn + hạng phòng có `pricesByDate` (bỏ bản Agoda cũ cùng key); gộp khách sạn trùng: giá quan sát mới
  nhất thắng (cùng ngày giữ thứ tự booking → agoda → trip → Vinpearl), hạng phòng lấy từ agoda khi mới hơn booking, giá booking cũ
  hơn không đè giá phòng Vinpearl.
- `src/data_collection/make_docs.py`, `docs/spec/data-collection/schema.md` §6 — sửa: dòng nguồn của `unitPrice` theo quy tắc mới.
- `src/data_collection/seed/parse_combos.py` — sửa: combo có `attributes.comboKind = flight_hotel` lấy thành phần từ attributes
  (`source = 'api'`, map tuyến bay theo sân bay và khách sạn theo `hotelCode`) thay vì tách tên — tên "Resort & Golf" bị cắt ở '&'.
- `src/data_collection/seed/database.py` — sửa: `upsert_catalog` (INSERT … ON CONFLICT DO UPDATE chỉ dòng đổi, không DELETE; thay
  `combo_items` của combo trong catalog; `retire_missing` → `available=false` cho dòng DB không có trong catalog).
- `src/data_collection/seed/__main__.py` — sửa: `--catalog-only`, `--retire-missing`; không chạm profiles/events/app/insider.
- `src/data_collection/daily.py` — thêm: job hằng ngày (worker song song theo origin, khoá, hạn giờ, chuẩn hoá vào staging, giữ dòng
  7 ngày, gate, promote, data version, nạp local/cloud + embed, switch, freeze, diff, status, báo cáo, ghi bước đang chạy).
- `src/data_collection/daily_api.py` — thêm: API cho trang `/daily` (tổng quan, lượt, log, phễu số dòng, version, diff, tìm và truy
  vết sản phẩm raw → interim → chuẩn hoá → catalog → dòng nạp DB, thao tác chạy/accept/switch/freeze qua `daily.py`).
- `src/data_collection/monitor.py` — sửa: route `/daily`, `/api/daily/*`; POST dùng lại chặn Host + `X-Requested-With`.
- `src/data_collection/monitor_ui/daily.html` — thêm: giao diện job hằng ngày.
- `src/data_collection/cron_daily.sh` — thêm: chạy `daily.py run --max-hours` từ cron, log vào `data/logs/`.
- `src/data_collection/.env.example` — sửa: khối biến của job hằng ngày (chỉ chỗ trống / giá trị Docker local mặc định).
- `src/data_collection/README.md` — sửa: mục "Job hằng ngày trên VPS".
- `src/data_collection/tests/test_agoda_api.py` — thêm: khớp city-slug, parser + raw gọn không còn review, thứ tự hỏi giá, sản phẩm
  Agoda trong normalise, gộp giá mới hơn thắng.
- `src/data_collection/tests/test_vinpearl_bundles.py`, `src/data_collection/tests/test_daily.py` — thêm: test tuyến/gộp giá combo,
  voucher, giữ dòng, gate, diff, vòng đời version (tạo → switch → freeze → `materialize_snapshot`), và test DB có điều kiện
  (`CATALOG_ONLY_TEST_DATABASE_URL`).
- `db/verify.sql` — sửa: `products = 11387` → `products >= 11387` (người dùng chốt 23/09/2026: catalog chỉ tăng).
- `AGENTS.md`, `docs/spec/MOCK_DATA_SPEC.md` — sửa: mô tả dòng verify theo ngưỡng mới.

## Quyết định

- Không dùng thẳng `vota-crawler`: cần Python ≥ 3.11 (conda `vsf` là 3.10), xuất mỗi ngày một dòng sản phẩm (`sourceRef@ngày`,
  23.094 dòng từ ~1.967 sản phẩm thật) trái mô hình một dòng + `attributes.availability`, và `productId` khác namespace. Chỉ lấy
  endpoint (voucher, bundle, Agoda `GetSecondaryData`) và cách vận hành.
- Đơn vị embed giữ là khách sạn (FR-CAT-02, `PRODUCT_SCHEMA.md` §8): mô tả phòng gần trùng mô tả khách sạn, text builder đã gộp
  đặc điểm cấp phòng vào khách sạn; người dùng chốt giữ.
- Người dùng chốt: phạm vi v1 = 38 điểm đến hiện có; Agoda (bước sau) 3–5 s/request, lùi khi 429, mỗi khách sạn đủ giá hôm nay…+30;
  publish 1 lần/ngày; không thấy 7 ngày thì `available=false`, giữ dòng; version = mỗi lần promote (theo ngày), đóng băng thành
  v1/v2 trong `snapshots/<version>/`; switch = đổi catalog + nạp lại DB được chọn; UI web trong `monitor.py`.
- Catalog chỉ tăng (giữ dòng) vì `app.booking_items`/`app.cart_items` có khoá ngoại RESTRICT tới `cdp.products`; switch về version
  cũ chỉ đổi `available`, không xoá.
- Không dùng kỹ thuật vượt chống bot. Repo `tripcom-hotel-crawler` người dùng gửi dựa vào giả vân tay TLS + proxy xoay vòng trên
  đường dẫn robots.txt cấm → không chạy thử, không mang sang. booking.com trả HTTP 202 trang AWS WAF challenge khi gọi HTTP thường
  (kiểm 23/09/2026) nên không có worker trên VPS.
- Thông tin đăng nhập SSH/Postgres staging người dùng gửi trong chat không được dùng, không ghi vào file, log hay lệnh nào; job chỉ
  đọc chuỗi kết nối từ `.env` do người vận hành tự điền. SSH tunnel do người vận hành tự mở.

## Kiểm tra

- Dựng lại catalog từ interim cũ (49 MB) bằng `normalise.py --no-plan --rooms-per-hotel 0 --flights-per-route 0` → 11.387 dòng,
  trùng 100% `productId`.
- Chạy thật trên thư mục tạm: `vinpearl-bundles --days 2 --limit-routes 1` → 2 request 200, 1 combo; `vinpearl --no-browser
  --skip-hotels --tour-limit 5` → 5 tour, chi tiết lấy được bằng HTTP.
- Postgres 16 dùng một lần (Docker, `db/init`), seed đầy đủ rồi `seed --catalog-only`: nạp lại cùng catalog 0 thay đổi; thêm combo
  + 5 tour → 1 thêm, 5 cập nhật; chạy lại → 0; events/users/bookings giữ nguyên 7145/54/1; combo có 2 thành phần `api` map đúng.
- `daily.py publish --load local` trên dữ liệu tạm → promote 11.388 dòng, nạp local ok, 17 giây; hai lượt → 2 version, diff đúng,
  `switch` về version đầu nạp lại DB, `freeze` → snapshot qua `materialize_snapshot`.
- `db/verify.sql` trên DB tạm sau seed lại với catalog 11.388 dòng → **16/16 PASS**.
- Quy tắc giá mới hơn thắng trên interim cũ: 11.387 dòng, 100% `productId` giữ nguyên, 3 dòng đổi giá (booking → agoda).
- Agoda chạy thật (thư mục tạm): đọc 41 sitemap → 61.339 URL chỗ ở Việt Nam; 20 khách sạn × 2 ngày = 102 request, 0 lỗi, 0 bị chặn,
  ~4,3 s/request; 20/20 khách sạn thuộc dữ liệu cũ; trung bình ~8 hạng phòng/khách sạn; raw gọn ~18 KB/khách sạn.
- `python -m pytest -q data_collection/tests` (từ `src/`, conda `vsf`) → **283 passed, 3 skipped**; `test_daily.py` với
  `CATALOG_ONLY_TEST_DATABASE_URL` trỏ DB tạm → 10 passed.
- UI `/daily` mở trên dữ liệu tạm: tổng quan, luồng từng bước, phễu số dòng, version, tra sản phẩm qua từng bước hiển thị đúng.
- Chưa chạy trên Postgres/Weaviate cloud (chưa có `.env` cloud) và chưa chạy job embed thật (chưa có `COHERE_API_KEY`).

## Còn lại / rủi ro

- Lượt thử Agoda 200 khách sạn × 1 ngày đang chạy khi ghi entry này; chưa chạy Agoda ở quy mô v1 (~1.900 khách sạn × 30 ngày ≈
  57.000 request ≈ 2,5 ngày ở 4 s).
- 38 điểm đến v1 cho ~9 dòng/khách sạn Agoda (khách sạn + hạng phòng) → catalog sẽ vượt xa ~10k dòng; khách sạn trùng booking được
  gộp theo tên + toạ độ.
- Loader chỉ dựng lịch thật cho `hotel_room`; combo bundle có `pricesByDate` nhưng chưa có `attributes.availability`.
- Người vận hành cần kiểm quyền user staging (INSERT/UPDATE `cdp.products`, DELETE/INSERT `catalog.combo_items`) và schema staging
  đã áp đủ `db/migrations` trước lần nạp cloud đầu tiên.
- Thông tin đăng nhập staging đã nằm trong đoạn chat: nên đổi mật khẩu SSH và DB.
