# Chạy thử cào trên local và monitor theo dõi real-time từng nguồn, từng bước

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, backend (job embed)

## Mục tiêu

Người dùng muốn chạy thử job cào mới (`fresh_catalog.py`) trên máy cá nhân. Họ cần biết chạy lệnh nào, rồi mở monitor để theo dõi:
- luồng nào đang cào, cào từ nguồn nào, có mất nguồn không;
- raw output của từng nguồn, output của từng bước normalize và output cuối;
- dữ liệu khi embed;
- chỉnh tốc độ gửi request khi lượt đang chạy, và xem log real-time.

Phục vụ FR-CAT-01..04 (cào, chuẩn hoá, giá/lịch, combo), FR-SRC-02 (embed Cohere: `search_document` khi nạp, `search_query` ở ô thử truy vấn), NFR-SEC-01 (monitor không trả secret). Local dùng Postgres + Weaviate Docker theo `docs/prd/deployment-plan.md` §1. Không đổi PRD, contract hay DDL.

## File thay đổi

- `src/data_collection/collectors/live_control.py` — thêm: file điều khiển live `<state>/live_control.json`. Monitor ghi file (có kiểm mức tối thiểu); crawler đọc trước mỗi request (stat ≤ 2 lần/giây). File có `paused`, `delay` (vinpearl/trip/booking/agoda), `delayMin`/`delayMax` (khách sạn Trip).
- `src/data_collection/collectors/common.py` — sửa: `HostRateLimiter.wait()` giữ request khi nguồn bị tạm dừng, dùng delay live nếu có và tính lại mốc chờ mỗi giây. Crawl-delay của robots.txt và `penalise` vẫn thắng.
- `src/data_collection/collectors/trip_live.py` — sửa: `next_start()` thay hai đoạn chờ trùng nhau. Nhịp mở trang giá/thông tin khách sạn Trip nhận delay và tạm dừng live.
- `src/data_collection/fresh_catalog.py` — sửa:
  - truyền `CRAWL_LIVE_FILE`/`CRAWL_RUN_ID`/`CRAWL_LIVE_KEY` cho lượt và từng `crawl.py`;
  - thêm `check_local_only()`: khi `CATALOG_LOCAL_ONLY=1`, chặn đích không phải localhost, database `vota` và collection `Product`;
  - normalize ghi `--stage-dir`; index ghi `index_detail.jsonl`.
- `src/data_collection/fresh_run_log.py` — sửa: xoá `live_control.json` đầu và cuối mỗi lượt (như `stop.request`).
- `src/data_collection/normalise.py` — sửa: thêm `--stage-dir` và `StageDump`.
  - Ghi ra `mapped`/`merged`/`filtered`/`enriched.jsonl.gz`, `dropped.jsonl.gz` (bước + lý do), `merges.jsonl`, `stages.json`.
  - Nhãn nguồn thống nhất theo `_meta.src`.
  - Không có cờ thì không ghi gì và kết quả không đổi.
- `src/data_collection/monitor.py` — sửa:
  - thêm `LogScan` (quét `job.log` tăng dần);
  - API mới `/api/health` (tình trạng từng nguồn, "mất nguồn"), `/api/live` GET/POST, `/api/log/stream` (SSE);
  - API mới `/api/normalise`, `/rows`, `/row`, `/trace`, `/api/embed`, `/row`, `/vector`, POST `/api/embed/query`;
  - overview thêm nơi ghi (host/database/collection, không có tài khoản).
- `src/data_collection/monitor_ui/index.html` — sửa: trang một lượt có tab Luồng & nguồn (kèm chỉnh live), Log trực tiếp, Raw/interim, Chuẩn hoá, Catalog cuối, Nạp DB, Embedding (kèm ô thử truy vấn), Báo cáo.
- `src/data_collection/local_crawl.sh` — thêm: `setup` / `small` / `monitor` / `run` / `env` / `reset` cho đích riêng `vota_crawl` + `ProductCrawl` trên Docker local. `LOCAL_CRAWL_NAME=<tên>` tách hẳn một bộ (database `vota_crawl_<tên>`, collection `ProductCrawl<Tên>`, thư mục `data/local_crawl_<tên>`). `setup` ghi cấu hình đa luồng khi bộ chưa có cấu hình; `small` thêm phạm vi nhỏ.
- `src/data_collection/collectors/vinpearl.py` — sửa: gọi `BrowserSession.fetch_json(page, url, headers=API_HEADERS)`. Trước đây truyền header theo vị trí nên mọi lần gọi API tour đều lỗi `takes 3 positional arguments but 4 were given`, Vinpearl chỉ lấy được khách sạn, 0 tour/vé/combo (lỗi có từ lúc chuyển code vào monorepo).
- `src/data_collection/tests/test_vinpearl_browser_api.py` — thêm: test hồi quy (fail với code cũ, pass sau khi sửa).
- `src/data_collection/tests/test_live_monitor.py` — thêm: 20 test cho live control, limiter/Trip pacing, health, API live, SSE, stage dump + trace, embed + query, chặn đích local.
- `src/data_collection/README.md` — sửa: mục "Chạy thử job mới trên máy cá nhân" và các tab mới của monitor.
- `src/backend/jobs/embed_products.py` — sửa: tham số tuỳ chọn `detail_path`. Mặc định `None`, không đổi hành vi. Ghi mỗi search unit (text gửi Cohere, hash, hành động, lý do nhúng lại, 8 chiều đầu + độ dài vector) và mỗi vector mồ côi.
- `src/backend/tests/unit/infrastructure/test_embed_products_job.py` — sửa: test `detail_path`.
- `history/2026-09-25-monitor-cao-local-real-time.md` — thêm: entry này.

## Quyết định

- Người dùng chọn đích local riêng: database `vota_crawl` và collection `ProductCrawl` trên Docker local. Lý do: `.env` gốc đang trỏ `WEAVIATE_URL` tới Weaviate Cloud của team. Nếu chạy lượt local với env đó, bước index sẽ ghi lên collection staging và xoá vector không có trong DB local. `local_crawl.sh` ghi đè env; `CATALOG_LOCAL_ONLY=1` là lớp chặn thứ hai trong `fresh_catalog.py`. VM không đặt biến này nên hành vi trên VM không đổi.
- Người dùng chọn chỉnh live cả delay từng nguồn lẫn tạm dừng/chạy tiếp. Số tab/worker không đổi được giữa chừng (trình duyệt đã mở), nên lưu vào Cấu hình và áp từ lượt sau.
- Mức tối thiểu delay live bằng mức tối thiểu của trang Cấu hình: 2 giây với nguồn tuân robots.txt (`docs/spec/data-collection-spec.md` §8), 0,5 giây với khách sạn Trip (mức code). Test kiểm hai nơi khớp nhau.
- Chỉnh live chỉ áp cho lượt đang chạy vì file bị xoá đầu/cuối lượt. Chạy tiếp không mất tiến độ; nút Dừng cả lượt giữ nguyên như cũ.
- Người dùng chọn xem text gửi Cohere, xem trước vector và ô thử truy vấn.
  - File chi tiết chỉ lưu 8 chiều đầu và độ dài vector, không lưu cả 1024 chiều.
  - Vector đầy đủ đọc trực tiếp từ Weaviate khi bấm.
  - Ô thử truy vấn gọi Cohere một lần, rồi xếp hạng cosine trên vector đọc qua REST (Weaviate Cloud có thể tắt GraphQL), giữ trong bộ nhớ 2 phút.
- Log real-time dùng server-sent events trên server loopback hiện có; guard Host/loopback giữ nguyên.
- `local_crawl.sh` bỏ thêm `XDG_SESSION_TYPE` khi chạy trong Xvfb. Trên phiên Wayland, Chromium của Playwright (chromium-1234) tự chọn Wayland theo biến này và nối vào `/run/user/1000/wayland-0` dù `DISPLAY` trỏ Xvfb, nên cửa sổ vẫn hiện trên desktop khi bấm Cào lớn (người dùng phát hiện).
- Người dùng muốn cào đa luồng. Ba lượt full liên tiếp đều chỉ còn Vinpearl chạy: bước tìm ID khách sạn Trip trả 0 khách sạn sau ~8 giây. Trang danh sách Trip Nha Trang hiện "Tìm thấy 0 nơi lưu trú" cho trình duyệt tự động, cả khi có cửa sổ thật lẫn trong Xvfb. Theo quy tắc đã chốt (`history/2026-09-25-cao-song-song-va-lenh-theo-doi.md`), nhóm trip lỗi làm booking/agoda chưa bắt đầu bị bỏ. Không tìm cách vượt lớp chặn của Trip. Cấu hình `base` của script:
  - `crawl.parallelSites=4`: mọi site bắt đầu cùng lúc, nên site lỗi không làm site khác bị bỏ. Quy tắc dừng trước khi nạp DB giữ nguyên.
  - booking/agoda 2 tab (mức tối đa spec §8).
  - tắt `sources.tripHotels` và lịch.
- Người dùng yêu cầu "cào mới hoàn toàn, sang một folder riêng để demo, không áp lên data cũ": tạo bộ `demo` (`vota_crawl_demo` rỗng, `ProductCrawlDemo`, `data/local_crawl_demo`). Bộ `vota_crawl`/`ProductCrawl`/`data/local_crawl` và `vota`/`Product` giữ nguyên. Job cào mới vốn không đọc `products.jsonl`, interim hay snapshot cũ.
- DB local tạo từ `template0`. Volume Postgres Docker hiện có báo `collation version mismatch` ở `template1` (image `postgres:16` đã lên glibc 2.41, volume tạo từ 2.36). Không sửa server của người dùng.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -q -p no:cacheprovider tests` (từ `src/data_collection`, env `vsf`): **350 passed, 3 skipped** (330 cũ + 20 mới).
- `python -m pytest -q src/backend/tests/unit/infrastructure/test_embed_products_job.py src/backend/tests/architecture`: **10 passed**.
- `bash -n local_crawl.sh`, `git diff --check`: sạch.
- `./local_crawl.sh setup` trên máy người dùng: bật postgres + weaviate, tạo `vota_crawl`, áp 4 migration, Weaviate ready. Chạy lại lần hai: giữ nguyên dữ liệu.
- Lượt full thật, rất nhỏ, bấm từ monitor: chỉ trip.com vé máy bay + điểm tham quan, Nha Trang + Hà Nội, 6 điểm/điểm đến.
  - Kết quả: ok, 91 giây, 22 sản phẩm nạp vào `vota_crawl`, 14 search unit embed vào `ProductCrawl` local, một lần gọi Cohere.
  - Giữa lượt đổi delay trip lên 8 giây rồi tạm dừng. Log ghi `live.control key=trip delay=8.0` và `paused=True`. Số file raw đứng yên 8 giây; chạy tiếp ghi `resumed after 35s`.
  - Đã xem trên Browser pane: tab Luồng & nguồn, Log trực tiếp (SSE), Chuẩn hoá (5 bước, truy vết VinWonders Nha Trang), Embedding (text, vector 1024 chiều độ dài 1, đọc vector Weaviate). Ô thử truy vấn "công viên giải trí cho gia đình ở Nha Trang" trả VinWonders đứng đầu, cosine 0,717.
  - Ở 375 px không tràn ngang.
  - Sau khi kiểm, cấu hình local trả về preset `small`.
- Dò socket của Chromium chạy trong `xvfb-run`: chỉ bỏ `DISPLAY`/`WAYLAND_DISPLAY` → nối `/run/user/1000/wayland-0` (hiện cửa sổ); bỏ thêm `XDG_SESSION_TYPE` → nối `@/tmp/.X11-unix/X100` (Xvfb, ẩn).
- Sau các sửa đổi: `pytest tests` (data collection) **351 passed, 3 skipped**.
- `crawl.py vinpearl --refresh --skip-hotels --tour-limit 3` trong Xvfb (thư mục tạm): API tour báo tổng 375, lấy đủ 3 tour (có combo vé VinWonders + Safari).
- `LOCAL_CRAWL_NAME=demo ./local_crawl.sh setup`: tạo `vota_crawl_demo`, áp 4 migration, ghi cấu hình `base`. Chưa chạy lượt nào trên bộ demo.
- Không đổi contract/schema/seed nên không chạy `validate_contract.py` hay `db/verify.sql`.

## Còn lại / rủi ro

- booking.com và agoda.com chưa được chạy thật trong Xvfb trên máy này (các lượt trước đều bị bỏ trước khi tới hai site này). Tour Vinpearl đầy đủ (~375 trang chi tiết) chưa chạy trọn.
- Khách sạn Trip đang tắt trong cấu hình `base` cho tới khi Trip trả kết quả cho trình duyệt tự động.
- Chưa chạy lượt local có Vinpearl, booking.com, agoda.com, khách sạn Trip. Delay/tạm dừng live của các nguồn này đi qua cùng `HostRateLimiter` / `next_start` (đã có test), nhưng chưa quan sát trên trang thật.
- Lượt kiểm thử còn trong `data/local_crawl/`, `vota_crawl` (22 dòng) và `ProductCrawl` (14 vector). `./local_crawl.sh reset` xoá sạch.
- Volume Postgres Docker local bị lệch phiên bản collation (có từ trước). Database `vota` cũ có thể cần `REINDEX` + `ALTER DATABASE … REFRESH COLLATION VERSION`; task này không đụng.
- Monitor trên VM dùng chung code: có thêm các tab mới khi build lại image `Dockerfile.fresh-catalog`. Chưa build/push image. Ô thử truy vấn trên VM sẽ đọc toàn bộ vector của collection Cloud (vài nghìn × 1024) mỗi 2 phút khi có người bấm.
- Chưa commit (người dùng tự commit).
