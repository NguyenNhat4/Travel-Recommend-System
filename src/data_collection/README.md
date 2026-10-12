# Data collection

Workstream thu thập, cache raw data, chuẩn hoá, khử trùng lặp và seed lịch sử khách hàng.
Khi thêm collector, phải mô tả nguồn của từng field và cách chạy lại từ cache — bảng
[Nguồn của từng trường](#nguồn-của-từng-trường) bên dưới là nơi ghi.

**Chạy mọi lệnh trong thư mục này** (`src/data_collection`). Dữ liệu sinh ra nằm ở `data/` và không vào git;
tài liệu schema cho các đội khác ở `docs/spec/data-collection/schema.md`, bộ mẫu 50 sản phẩm chạy thử ở `sample/`.
Catalog/DB giữ 13 trường; bộ mẫu là projection `ProductSummary` cho API nên thêm `priceUnit=UNKNOWN`
khi catalog chưa có bằng chứng về đơn vị giá.

## Dựng database demo từ snapshot

Setup và `make demo-db` / `make demo-db-reset`: xem [README gốc](../../README.md). Snapshot mặc định (11.718 sản phẩm, có vé máy bay khứ hồi kèm hạng vé) cùng 64 mapping combo đã duyệt nằm trong `snapshots/2026-09-30/`; `make demo-db` kiểm checksum rồi bung vào `data/snapshots/2026-09-30/` (chỉ ở local, không vào git).

---

Thu thập catalog theo đúng **handbook §3**: khoảng 2.000–5.000 sản phẩm thật (hotel, flight, attraction, combo, golf)
trên 15 điểm đến Việt Nam, mô tả tiếng Việt, xuất theo schema `Product` ở §6.

| Handbook yêu cầu | Làm ở đây |
|---|---|
| vinpearl.com trước: khách sạn, VinWonders, golf, combo | `crawl.py vinpearl`: API của booking.vinpearl.com (vinpearl.com có Cloudflare) |
| booking.com: độ phủ chỗ ở, thuộc tính có cấu trúc | `crawl.py booking-hotels`: N khách sạn phổ biến mỗi điểm đến + hạng phòng + giá |
| agoda.com: phủ tốt chỗ ở nội địa | Fresh pipeline gọi `crawl.py agoda-api`: N khách sạn mỗi điểm đến, hạng phòng và một ngày giá thật; loader dựng availability 30 ngày |
| trip.com: vé máy bay, điểm tham quan (gợi ý chéo tuần 3) | `crawl.py trip-flights`, `crawl.py trip-attractions` |
| 2.000–5.000 sản phẩm, 10–15 điểm đến | `collectors/plan.py`: 15 điểm đến, ngân sách mỗi điểm đến |
| Gộp trùng: vinpearl.com thắng tên/mô tả, OTA thắng giá/tình trạng | `normalise.py` |
| Toạ độ nếu có | khách sạn và điểm tham quan theo nguồn, vé Vinpearl theo địa điểm dùng vé, vé máy bay theo sân bay; xuất cho Google My Maps + GeoJSON (xem [Vị trí và Google Maps](#vị-trí-toạ-độ-và-google-maps)) |
| Chỉ dữ liệu sản phẩm, không review / tên người | review bị xoá khỏi HTML/JSON **trước khi** ghi cache |
| Cache raw, rate limit, robots.txt, resume, README nguồn trường | có đủ, xem bên dưới |
| Fallback Amadeus Self-Service | **đã ngừng hoạt động từ 17/07/2026** (Amadeus chỉ còn gói Enterprise), nên không dùng |

## Cài đặt

Cần Python 3.10 trở lên (đã chạy thử trên 3.10 và 3.14).

```bash
cd src/data_collection
conda activate vsf                  # hoặc: python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium         # Linux thiếu thư viện hệ thống: playwright install --with-deps chromium
```

## Source of truth và automation

`src/data_collection` là source chính cho collector đa nguồn, chuẩn hoá và DB. Nhánh `test/newcrawl` đóng gói collector Trip.com và job catalog mới trong `Dockerfile.fresh-catalog`; VM chỉ cần image, file cấu hình, volume dữ liệu và bản copy của script chạy Docker, không cần checkout source. Các job `daily.py`/Docker cũ vẫn có để tham khảo hoặc chạy riêng, nhưng không được lên lịch đồng thời với job mới trên cùng DB. Job mới giữ state/log ở volume `/data` và chỉ tạo raw/catalog tạm theo từng lượt; các job cũ vẫn dùng `data/` (Git ignore).

Catalog baseline được giữ ở hai dạng:

- `data/products.jsonl`: bản runtime 11.387 sản phẩm để chạy ngay tại máy hiện tại, không track bởi Git.
- `snapshots/2026-09-30/products.jsonl.gz` (mặc định, 11.718 sản phẩm): bản nén có manifest/checksum được track, để clone sạch có cùng catalog; `snapshots/2026-09-23/` (11.387) và `2026-09-29` giữ để tái lập.

Job cào mới (`fresh_catalog.py`) cào, chuẩn hoá, nạp PostgreSQL và index; chạy thử trên máy cá nhân qua
`./local_crawl.sh` (mục "Chạy thử job mới trên máy cá nhân") và theo dõi bằng `./local_crawl.sh monitor`
(http://127.0.0.1:8765/). Luồng demo cũ (`pipeline_demo.py`, nguồn API/Apify) và các script chạy tay theo lô đã gỡ ngày
29/09/2026.

## Job hằng ngày trên VPS (console, không trình duyệt)

`daily.py` chạy các nguồn HTTP song song theo site (Vinpearl: khách sạn + lịch 30 ngày, vé/tour, combo bay + ở; trip.com:
vé máy bay + điểm tham quan; agoda.com qua API: tối đa 50 khách sạn mỗi điểm đến, hạng phòng + giá từng ngày; phạm vi 38 điểm
đến `@v1`), chuẩn hoá lại toàn bộ catalog từ `data/interim/`, giữ dòng không thấy
(quá 7 ngày thì `available=false`, không xoá), chặn nếu số lượng/độ phủ tụt, promote thành một **data version**, rồi nạp
`seed --catalog-only` vào Postgres local/cloud và embed vào Weaviate. Nguồn cần trình duyệt (booking.com, trip.com khách sạn)
không chạy ở đây; bản ghi cũ của chúng trong interim vẫn được giữ.

Chuẩn bị một lần trên VPS:

```bash
conda activate vsf                        # hoặc Python ≥ 3.10 + pip install -r requirements.txt
cp -r <interim nền>/*.jsonl data/interim/  # 49 MB interim của lần cào trước; không commit (dữ liệu nội bộ)
cp snapshots/2026-09-23/combo_items_manual.jsonl data/
cp .env.example .env                      # điền các biến ở khối "Job hằng ngày", không commit
```

| Biến trong `.env` | Dùng cho |
|---|---|
| `DAILY_LOAD` | `local`, `cloud` hoặc `local,cloud`: nạp sau mỗi lần promote |
| `SEED_DATABASE_URL`, `DATABASE_URL`, `WEAVIATE_URL` | đích `local` (Postgres Docker + Weaviate local) |
| `CLOUD_SEED_DATABASE_URL` | đích `cloud`: `postgresql://<user>:<mật khẩu mã hoá URL>@127.0.0.1:15432/vota` qua SSH tunnel |
| `CLOUD_WEAVIATE_URL`, `CLOUD_WEAVIATE_API_KEY` | Weaviate Cloud (`https://<cluster>.weaviate.cloud`) |
| `COHERE_API_KEY` | chỉ job `daily.py` cũ còn kiểm khoá này trước bước index; embed thực tế là e5-small trong image |
| `DAILY_DESTINATIONS` | phạm vi điểm đến, mặc định `@v1` (38 điểm, `collectors/plan.py`) |
| `DAILY_AGODA_PER_CITY`, `DAILY_AGODA_HOURS` | số khách sạn Agoda tối đa mỗi điểm đến (50), số giờ Agoda chạy mỗi ngày (14, hết giờ thì dừng êm) |

Máy chạy job cùng mạng nội bộ (VPC) với VM Postgres staging thì `CLOUD_SEED_DATABASE_URL` trỏ thẳng IP nội bộ của VM DB, không
cần tunnel. Máy ngoài VPC thì người vận hành tự mở SSH tunnel (nên dùng SSH key, vd. `autossh -M 0 -N -L 127.0.0.1:15432:<host DB>:5432 <user>@<vps>`); job chỉ đọc chuỗi kết nối trong `.env`.

```bash
python daily.py run --load local,cloud      # một lượt đầy đủ; cron: 0 2 * * * .../cron_daily.sh
python daily.py publish --load local        # chỉ chuẩn hoá + promote + nạp từ interim hiện có
python daily.py status | versions           # lượt gần nhất · danh sách version
python daily.py diff 2026-09-24 2026-09-25  # khác biệt giữa hai version
python daily.py switch 2026-09-24 --load cloud   # quay lại version cũ; dòng không có trong version đó → available=false
python daily.py freeze 2026-09-24 v1        # gắn nhãn, chép thành snapshots/2026-09-24/ để commit

```

Monitor hiện theo dõi `fresh_catalog.py`; `/daily` và `/pipeline` chuyển tới trang mới. Job cũ vẫn thao tác qua CLI.
Mã thoát `daily.py`: 0 ổn · 1 gate chặn / lỗi · 2 có worker lỗi hoặc bị chặn · 3 promote xong nhưng nạp DB/embed lỗi.

### Luồng Docker/daily.py cũ (chỉ chạy khi chủ động chọn `legacy-run`)

Image `Dockerfile.daily` (repository root) gói `src/data_collection` + phần backend mà bước embed cần, Python 3.11 và Chromium cho vé thương gia, không chứa `data/`, `.env` hay secret. Dữ liệu làm việc nằm trên ổ VPS (`DATA_DIR`, mount vào `/data`) nên giữ
nguyên giữa các lượt; kết nối DB/Weaviate nằm trong `ENV_FILE`. Mọi thao tác đi qua một script:
`run_daily_docker.sh` (`init` · `run`/`legacy-run` · `daily <lệnh>`). `run` giữ job cũ để tương thích các lệnh legacy; job mới dùng `fresh-run`, monitor mới dùng `fresh-monitor`.

```bash
# Build + push (máy có repo, từ repository root; <AR> = asia-southeast1-docker.pkg.dev/<project>/<repository>)
docker build -f Dockerfile.daily -t <AR>/vota-daily:<tag> .
docker push <AR>/vota-daily:<tag>

# Một lần trên VPS (user sẽ chạy cron, có quyền docker)
export IMAGE=<AR>/vota-daily:<tag>          # hoặc đặt trong crontab; mặc định vota-daily:latest
sudo install -d -o "$USER" /srv/vota/daily-data                 # DATA_DIR mặc định
sudo install -D -m 600 -o "$USER" /dev/null /etc/vota/daily.env    # ENV_FILE mặc định: điền khối "Job hằng ngày" của .env.example
./run_daily_docker.sh init <thư mục interim nền> [<thư mục raw>]  # interim 49 MB của lần cào trước (dữ liệu nội bộ, không commit)

# Hằng ngày (crontab của user đó)
0 2 * * * IMAGE=<AR>/vota-daily:<tag> /đường/dẫn/src/data_collection/run_daily_docker.sh legacy-run

# Thao tác tay, cùng ổ dữ liệu và ENV_FILE
./run_daily_docker.sh daily status          # hoặc versions · diff <cũ> <mới> · accept <lượt> · switch <version> --load cloud
```

- `init` không đè interim đã có trên VPS và tự chép `combo_items_manual.jsonl` từ snapshot trong image vào `DATA_DIR`
  (`seed --catalog-only` đọc file này; thiếu thì 64 mapping combo duyệt tay bị bỏ qua mà không báo lỗi).
- `legacy-run`: log mỗi lượt ở `DATA_DIR/logs/daily-*.log` (giữ 30 ngày), lượt lỗi ghi thêm một dòng vào `daily-errors.log`; container
  lượt trước còn chạy thì lượt mới bỏ qua; mỗi lượt kéo lại `IMAGE` trước (`PULL=0` để tắt); `MAX_HOURS` mặc định 16.
- Container chạy bằng uid:gid của chủ `DATA_DIR`, nên file ghi ra vẫn thuộc người vận hành.
- VPS cần ra được internet (cào) và tới được Postgres + Weaviate staging. Postgres chạy bằng Docker trên cùng VM thì đặt
  `DOCKER_NETWORK=<mạng docker của Postgres>` và dùng tên container làm host trong `CLOUD_SEED_DATABASE_URL`.
- `freeze` vẫn làm ở máy có repo (ghi `snapshots/<version>/` để commit), không làm trong container.

## Job catalog mới trên VM console: Trip.com + đa nguồn → DB

Image [Dockerfile.fresh-catalog](../../Dockerfile.fresh-catalog) chứa collector đa nguồn, bộ chuẩn hóa Travel, Chromium và Xvfb. Collector Trip.com dùng HTTP/SSR lấy metadata rồi Chromium trong Xvfb bắt JSON phòng/giá thật. `run_daily_docker.sh fresh-run` khởi chạy image này. Lệnh `run` vẫn là job legacy `daily.py`. CI/CD nay triển khai image fresh, thay khối cron bằng `fresh-run tick` mỗi 15 phút và yêu cầu một lượt full sau deploy; lượt đang chạy được giữ nguyên, request chờ tick sau. Không chạy song song hai job trên cùng DB. VM không cần desktop, Python, Playwright hoặc source tree.

- Lượt đầu và mỗi 7 ngày: cào mới các nguồn, tìm ID Trip.com ở 7 thành phố có cityId trong `@deep`; lần đầu chọn tối đa 30 ID/thành phố, các lượt tuần chọn tối đa 10 ID mới/thành phố từ tối đa 300 ID đã quét/thành phố để hỏi giá tại mốc 14/30/60 ngày; chuẩn hóa 13 trường rồi upsert `cdp.products`/`catalog.combo_items`. Tăng `TRIP_DISCOVERY_SCAN_PER_CITY` khi vùng quét đã hết ID mới. Không dùng `data/products.jsonl`, interim hoặc snapshot cũ làm dữ liệu nguồn.
- Lượt full **làm mới cả catalog khách sạn** (setting `refresh.existing`, mặc định bật): đầu lượt đọc từ DB mọi khách sạn tổng quan chưa gộp của Booking/Agoda (kể cả dòng nguồn khác đã gộp ref của chúng vào `sameAs`, qua `bookingUrl`/`agodaUrl`), ghi `<lượt>/refresh/<bước>.jsonl`, dòng lâu chưa thấy (`lastSeenAt`) trước; Booking mở lại trang theo URL, Agoda hỏi lại giá theo `hotel_id` đã lưu; khách sạn Trip hỏi giá **mọi ID đã biết** chứ không chỉ ID mới tìm. Khách sạn mới vẫn tìm theo điểm đến như cũ và xếp trước. Bản ghi làm mới mang `plan.via = "refresh"` nên chuẩn hoá giữ hết, không cắt theo số khách sạn mỗi điểm đến hay phạm vi điểm đến. Đọc DB lỗi thì lượt chỉ cào khách sạn mới tìm và ghi `catalog.refresh.failed`. Thứ tự site `trip → vinpearl → agoda → booking`: Booking (~2.100 trang, 6–9 giờ trên VM) đứng cuối để không ăn giờ của Agoda; Booking mở lại Chromium sau mỗi 100 trang để RAM không tăng dần.
- Sau phần cào, `counts.refresh` ghi số khách sạn đang có đã làm mới theo từng nguồn. Dưới `quality.minRefreshPercent` % (mặc định 90), hoặc tìm Booking theo điểm đến trả 0 khách sạn ở mọi điểm đến (`interim/booking_hotels.search.json`), thì nguồn vào `incompleteSources`, lượt báo `partial` kèm cảnh báo "Cào chưa đủ" trên monitor; phần đã cào vẫn được nạp.
- Lượt full chạy song song theo site: Vinpearl, Trip.com (vé máy bay → điểm tham quan → tìm ID khách sạn → giá phòng), Booking, Agoda; tối đa `CRAWL_PARALLEL` site cùng lúc (mặc định 2, vì Vinpearl, Booking, Agoda và giá phòng Trip đều mở Chromium trên VM 4 GB). Trong một site các bước vẫn tuần tự như trước. Một nguồn lỗi thì các nguồn độc lập vẫn tiếp tục; chỉ bước phụ thuộc nguồn lỗi bị bỏ. Nguồn lỗi chuẩn hoá hoặc không đạt ngưỡng theo nguồn bị loại khỏi bản mới; dữ liệu tốt vẫn được nạp và lượt báo `partial`. Không coi bản ghi thiếu do lỗi nguồn là hết bán. Log mỗi dòng của nguồn có tiền tố `[trip]`, `[vinpearl]`…; mốc `catalog.group.start/done` cho biết site nào đang chạy. Lượt daily chỉ cào Trip nên không đổi.
- Hằng ngày còn lại: xoay vòng tối đa 180 ID đã biết, ưu tiên ID chưa thử/lâu chưa thử, hỏi JSON phòng/giá mới cho cả phòng cũ và phòng mới. Chỉ file ID/thành phố và thời điểm thử/thành công được giữ cho lịch chạy; marker full chỉ ghi sau khi nạp DB thành công. Giá Trip.com gốc quá `tripHotels.priceMaxAgeDays` ngày (mặc định 7; `0` = tạm không tắt, chỉnh trên monitor) chưa làm mới sẽ được đặt chưa khả dụng để không quảng bá giá cũ.
- Hai dòng DB chưa gộp cùng nhận một `sourceRef`/`sameAs` (vd. dòng agoda nạp riêng trong khi dòng booking đã ghi ref agoda vào `sameAs`) không còn làm dừng lượt nạp: dòng ghi ref trong `sameAs` được giữ, dòng kia nhận `mergedInto` và `available = false`, phòng con chuyển sang dòng giữ; số cặp ghi ở `refConflicts`.
- DB giữ các trường mô tả đã có, cập nhật giá/trạng thái, thêm phòng mới, đánh dấu phòng Trip.com không còn xuất hiện trong phản hồi hợp lệ là hết bán. Một phản hồi lỗi/chặn **không** được coi là hết phòng. Không xóa `cdp.products` đã được đơn hàng tham chiếu.
- Đầu mỗi lượt (kể cả khi mọi nguồn lỗi sau đó) job chạy một transaction riêng: đặt chưa khả dụng các giá Trip.com quá `tripHotels.priceMaxAgeDays` ngày (mặc định 7, `0` = bỏ qua), và cuộn cửa sổ đặt chỗ 30 ngày cho toàn catalog đúng như seed (`docs/spec/DATABASE_SCHEMA.md` #13): `available_from/to` = khoảng nguồn `attributes.sourceAvailableFrom/To` cắt vào `[hôm nay, +29]`, thiếu thì lấy cả cửa sổ; chuyến bay `from = to` = ngày bay; vé ngày cố định ngoài cửa sổ (đã bay, sau cửa sổ, hết hạn báo giá) được dời cả hai chặng vào cửa sổ như seed, ngày trong tên/mô tả đổi theo, và vé có giá luôn đặt được (`docs/prd/data-model.md` §3.1, chốt 06/10/2026); giao rỗng → `available = false` kèm `attributes.windowClosed`, và dòng mang dấu này được bật lại khi cửa sổ cuộn tới khoảng của nó (còn giá, chưa gộp, không có `priceFreshness`). Dòng tắt vì lý do khác (hết bán, giá quá hạn) không bị bật lại theo cửa sổ. Khách sạn tổng quan không có hạng phòng con nào đặt được thì `available = false` kèm `attributes.noBookableRoom`; có hạng phòng đặt được thì bật lại (PRD FR-CAT-02, chốt 06/10/2026) — kể cả khách sạn bị lượt cào trước tắt vì nguồn không trả giá cho đúng ngày hỏi, trừ dòng đã gộp, giá quá hạn, ngoài cửa sổ; khách sạn bật lại mà chưa có giá thì lấy giá hạng phòng rẻ nhất đang bán (12/10/2026). Vé máy bay mới mang logo hãng (`collectors/airlines.py`, cả vé phủ ngày mô phỏng); ảnh đã có trên DB của tuyến chiều ngược và tuyến mô phỏng của combo được giữ, không bị ảnh tuyến gốc/ảnh combo ghi đè. Điểm đã soát tay và ẩn nằm trong `collectors/excluded_products.csv` nên lượt cào sau không bật lại. Sân golf Trip không hiện giá nhận giá hiện hành của nền tảng đặt tee time công khai giá và cho phép cào ở `collectors/golf_prices.csv` (giá, nguồn, URL, thời điểm quan sát; `fieldSources.unitPrice` = nguồn đó; giá của chính Trip luôn thắng); sân không tìm được giá giữ `unitPrice = null`, không dùng giá tham khảo cũ (12/10/2026). Dòng mới/làm mới trong lượt ghi lại khoảng nguồn của lượt đó. Lịch `attributes.availability` của hạng phòng, điểm tham quan, golf được sinh lại theo cửa sổ mới như seed (`docs/spec/MOCK_DATA_SPEC.md` §2 bước 2); ngày Trip.com đã hỏi ghi theo kết quả thật, dòng chưa khả dụng có lịch toàn `0`.
- Cũng trong transaction đầu lượt đó và sau mỗi lần nạp DB, `catalog.combo_items` của **mọi combo trong DB** được parse lại từ tên + mô tả đang lưu (`fresh_catalog_db.sync_combo_items`), không chỉ combo lượt này cào được: sửa code parse thì combo đang bị chặn cào cũng nhận bản mới, và thành phần map sang sản phẩm của toàn catalog thay vì chỉ lô đang nạp. Chỉ combo có thành phần đổi mới được ghi lại (`combosChanged`). Xem trước, chỉ đọc: `python src/data_collection/fresh_catalog_db.py combo-items --database-url <dsn>`.
- Sau khi nạp DB (và cả khi lượt cào lỗi), job gọi bước index `embed_products` vào Weaviate của **cùng đích**: chỉ embed search unit mới hoặc đổi text, xoá vector mồ côi. Lỗi 429 (quota) của bước index sau khi DB đã nạp: giữ DB, ghi index pending vào `state/index_pending.json`, lượt báo `partial` nhưng trả mã 0; cron bật sẽ thử lại riêng index sau cooldown (1 giờ, tăng dần tối đa 24 giờ; ưu tiên Retry-After). Các lỗi index khác vẫn trả mã 3. `fresh-run index` cũng tuân thủ cooldown. Backend tự nạp lại giá/trạng thái mỗi `CATALOG_REFRESH_SECONDS` (mặc định 15 phút), không cần restart.
- Raw/JSON đã bỏ review/tên người, interim, `products.jsonl`, log và báo cáo giữ theo từng lượt; mặc định giữ 2 lượt (`runs.keep` trong monitor, hoặc biến môi trường `RUNS_KEEP`). Tóm tắt lịch sử, ID và lịch xoay vòng được giữ lâu dài. Giá/input vẫn chỉ lấy từ phản hồi mới của lượt hiện tại. `KEEP_FAILED_RUNS` cũ không còn dùng; browser profile Trip được dọn sau bước hỏi giá.

### Hạn giờ và phục hồi khi nghẽn

CLI `fresh_catalog.py` giám sát tiến trình chạy: `run.maxHours` mặc định 15 giờ cho toàn lượt (`crawl.maxHours` 14 giờ cho phần cào); `timeout.processing` mặc định 30 phút cho mỗi bước xử lý (chuẩn hoá, kiểm tra, DB, index và lô streaming). Hạn giờ từng nguồn vẫn theo Cấu hình (mặc định `timeout.booking` 600, `timeout.agoda` 180 phút cho lượt làm mới cả catalog; cả lượt ước 11–14 giờ trên VM, dưới `run.maxHours` 15 giờ nên lượt bắt đầu 08:35 kết thúc trước khi VM crawler tắt lúc 23:59). Retry dùng chung hạn giờ của nguồn. Nguồn chạy bằng `crawl.py` quá hạn mà không tự dừng thì supervisor chỉ dừng cây tiến trình của nguồn đó (pid ở `detail.pid` của bước) và lượt chạy tiếp nguồn sau; chỉ khi nguồn vẫn "running" thêm 3 phút, hoặc bước trong tiến trình (khách sạn Trip, chuẩn hoá, DB, index) quá hạn, supervisor mới kết thúc cả lượt, ghi trạng thái lỗi trước khi thả khóa. Lượt full bị kết thúc cưỡng bức như vậy, hoặc bị hệ điều hành giết (hết RAM), tự chạy tiếp **một lần** `resume <lượt> --from normalise` (setting `run.autoResume`, mặc định bật; không áp cho lượt bấm Dừng): dòng ghi dở ở cuối interim được chốt rồi phần đã cào được chuẩn hoá, nạp DB, index. Gọi trực tiếp `run_job()` từ Python không có lớp supervisor; dùng CLI/wrapper khi vận hành.

Nạp DB không dừng cả lượt vì một dòng: dòng mới ghép với DB bị trùng ID mà khác ref, trùng `sourceRef` chuẩn với dòng khác của lượt, hoặc khách sạn Trip chưa đủ mốc ngày giá được bỏ ra, ghi vào `<lượt>/db_quarantine.jsonl` kèm lý do (`counts.database.quarantined`, có cảnh báo); các dòng khác vẫn nạp. `run_daily_docker.sh fresh-run` giới hạn RAM container job bằng `FRESH_MEMORY` (mặc định `2500m`, rỗng = không giới hạn) để hết RAM thì chỉ tiến trình trong job bị giết, không phải backend chạy chung VM.

Kết nối DB giới hạn 10 giây; chờ khóa PostgreSQL 5 giây, câu lệnh 5 phút, transaction rỗi 1 phút. Thiếu cấu hình index không chặn cào/nạp; lỗi index vẫn được báo, dữ liệu đã commit giữ lại. Sau khi khắc phục, chạy lại từ `index`; nguồn lỗi thì chạy lại riêng bằng `resume <runId> --from crawl --source <nguồn>`. Khi chỉ cào lại một nguồn, lỗi của nguồn khác vẫn giữ trạng thái `partial`.

Lượt full vẫn chờ các nguồn hoàn tất hoặc hết hạn trước lần gộp cuối. Để nguồn nhanh vào DB trong lúc nguồn chậm còn chạy, bật cả `stream.enabled` và `stream.db` trên môi trường đã kiểm thử. Hai cờ này hiện mặc định tắt; thay đổi này không tự bật trên VM. Chế độ daily chỉ có nguồn giá khách sạn Trip, nên không có nguồn độc lập để thay thế khi Trip thất bại.

Vé mới có ngày cố định/hạng vé/khứ hồi giữ ngày và giá nguồn. Không cần cào lại toàn bộ 11k catalog: bổ sung báo giá mới đúng tuyến, ngày và hạng cần demo rồi upsert. Dữ liệu Trip cũ có thể dùng kiểm tra cấu trúc khứ hồi, nhưng báo giá hết hạn không được coi là giá mới. Chi tiết và phần còn lại: [kế hoạch kiểm chứng](../../docs/plan/2026-09-29-on-dinh-pipeline-va-ve-may-bay.md).

### Đóng gói và bàn giao cho đội deploy

> Đọc trước: [Triển khai job cào dữ liệu trên VM](../../docs/guide/trien-khai-job-cao-du-lieu.md) — job cũ và job mới, chỉ một lịch cào, luồng CI/CD deploy job mới.

Bộ bàn giao có checklist, hai file env và mẫu systemd: [Bàn giao fresh catalog trên VM](../../docs/plan/2026-09-25-ban-giao-fresh-catalog-vm.md).

Trên máy build/CI có checkout nhánh `test/newcrawl`, build và push image riêng. Image không chứa snapshot, `data/`, `.env` hay secret; Chromium/Xvfb nằm **trong image**:

```bash
# Từ repository root; thay <AR> bằng Artifact Registry của đội deploy.
docker build -f Dockerfile.fresh-catalog -t <AR>/vota-fresh-catalog:<tag> .
docker push <AR>/vota-fresh-catalog:<tag>
```

Đội deploy cần image/tag bất biến, quyền pull image, kết nối PostgreSQL đã migrate, và bản copy **một** file `src/data_collection/run_daily_docker.sh` ở `/opt/vota/bin/run_daily_docker.sh` (không cần thư mục `src/`). Trên Ubuntu VM, Docker là runtime duy nhất của crawler. Tạo volume state riêng cho UID/GID `10001` (tài khoản `app` trong image), thư mục log cho user chạy cron và file env ngoài image; không chép interim/snapshot cũ:

```bash
sudo install -d -m 750 -o 10001 -g 10001 /srv/vota/fresh-catalog-data
sudo install -d -m 750 -o "$USER" /srv/vota/fresh-catalog-logs
sudo install -D -m 600 -o "$USER" /dev/null /etc/vota/fresh-catalog.env
# CI/đội deploy chuyển riêng run_daily_docker.sh từ nhánh này tới /tmp/run_daily_docker.sh trên VM.
sudo install -D -m 755 /tmp/run_daily_docker.sh /opt/vota/bin/run_daily_docker.sh
```

Nội dung ví dụ `/etc/vota/fresh-catalog.env` (điền giá trị thật trên VM, không commit):

```dotenv
DB_TARGET=cloud
CLOUD_SEED_DATABASE_URL=postgresql://USER:PASSWORD@DB_HOST:5432/vota
PRICE_WORKERS=2
FAST_WORKERS=4
TRIP_DAILY_HOTELS=180
TRIP_INITIAL_PER_CITY=30
TRIP_NEW_PER_CITY=10
TRIP_DISCOVERY_SCAN_PER_CITY=300
MIN_DELAY=0.5
MAX_DELAY=1.0
FULL_REFRESH_DAYS=7
# Số site cào cùng lúc ở lượt full (mỗi site vẫn tuần tự). Tăng thì theo dõi RAM bằng `fresh-run status`.
CRAWL_PARALLEL=2
# Bước index sau mỗi lượt (embed e5-small có sẵn trong image, không cần khoá); thiếu cấu hình Weaviate thì vẫn cào/nạp nhưng báo lỗi index. Collection vector mặc định: `ProductE5Small` (`VECTOR_COLLECTION`).
CLOUD_WEAVIATE_URL=https://<cluster>.weaviate.cloud
CLOUD_WEAVIATE_API_KEY=...
# Tuỳ chọn: role chỉ đọc cho bước index; để trống thì dùng CLOUD_SEED_DATABASE_URL.
CLOUD_DATABASE_URL=
# Chỉ dùng khi phải tạo lại collection: Weaviate Cloud của nhóm chỉ cho phép hfresh.
WEAVIATE_VECTOR_INDEX_TYPE=hfresh
```

Nếu PostgreSQL chạy trên cùng Ubuntu VM và mở cổng loopback, dùng `DB_TARGET=local` với `SEED_DATABASE_URL=postgresql://...@127.0.0.1:5432/vota`; bước index khi đó đọc `DATABASE_URL` (thiếu thì `SEED_DATABASE_URL`) và ghi vào `WEAVIATE_URL`/`WEAVIATE_API_KEY`. Runner mặc định dùng network `host`. Nếu DB nằm trong Docker network riêng, đặt `FRESH_NETWORK=<tên-network>` cho runner và dùng tên service DB trong URL. Crawler không tự khởi tạo/reset DB; đội deploy phải bảo đảm DB đã chạy và migration đã áp dụng.

```bash
# Trên VM: đặt tag đã push vào lệnh hoặc cấu hình cron.
FRESH_IMAGE=<AR>/vota-fresh-catalog:<tag> /opt/vota/bin/run_daily_docker.sh fresh-run status
# Chỉ hết hạn giá, cuộn cửa sổ và index lại (không cào), vd. sau khi bước index của lượt trước lỗi:
FRESH_IMAGE=<AR>/vota-fresh-catalog:<tag> /opt/vota/bin/run_daily_docker.sh fresh-run index
FRESH_IMAGE=<AR>/vota-fresh-catalog:<tag> /opt/vota/bin/run_daily_docker.sh fresh-run full

# Cron đánh thức mỗi 15 phút. Giờ chạy cấu hình trên monitor (mặc định 08:35 Việt Nam; VM crawler staging-ha bật 08:30–23:59).
*/15 * * * * FRESH_IMAGE=<AR>/vota-fresh-catalog:<tag> /opt/vota/bin/run_daily_docker.sh fresh-run tick
```

Theo dõi trên console của VM (chỉ cần Docker, `curl` cho lệnh backend):

```bash
/opt/vota/bin/run_daily_docker.sh fresh-run status     # lượt đang chạy: từ lúc nào, site nào đang cào, CPU/RAM; rồi lượt kế tiếp
/opt/vota/bin/run_daily_docker.sh logs -f        # theo dõi log lượt đang chạy; `logs 2 -n 200` là lượt trước đó
/opt/vota/bin/run_daily_docker.sh report 7       # 7 lượt gần nhất: mode, số phút, kết quả, dòng mới/làm mới, embed/xoá vector, lỗi
/opt/vota/bin/run_daily_docker.sh backend        # backend compose cùng VM: /health, CPU/RAM, dòng RecSys 24 giờ, lỗi 1 giờ
/opt/vota/bin/run_daily_docker.sh backend logs -f
```

`backend` gọi `BACKEND_URL` (mặc định `http://127.0.0.1:8000`) và tìm container có nhãn compose `service=backend`; tên khác thì đặt `BACKEND_CONTAINER`. Cột RESULT của `report`: `ok`, `partial:0` (đã nạp dữ liệu hợp lệ, còn nguồn/ngày chưa hoàn tất hoặc index đang chờ quota), `fail:3` (lượt dừng, xem cột NOTE), `running`.

`fresh-run` mount `/srv/vota/fresh-catalog-data` vào `/data`: state ở `/data/state`, dữ liệu từng lượt ở `/data/fresh_runs/<runId>/`. Log runner được giữ 30 ngày ở `/srv/vota/fresh-catalog-logs/` (đổi bằng `CATALOG_LOG_DIR`); lệnh dọn tay `cleanup` xoá log quá 7 ngày. Chỉ đặt **một** lịch cào cho cùng DB: cài bằng `scripts/install-vota-cron.sh --job fresh` (thay lịch job cũ trong cùng khối cron). CI/CD cài rõ `--job fresh`, dùng image `GAR_FRESH_IMAGE` ghim digest và khởi động lại monitor; không tự chạy lượt cào. Xem **[hướng dẫn triển khai job cào](../../docs/guide/trien-khai-job-cao-du-lieu.md)** về nhánh CD và env VM.

### Monitor của cron mới

**Sơ đồ luồng: % hoàn thành và bước con (08/10/2026):** mỗi ô tô nền theo % — đang chạy: đã làm / tổng (cào: dòng tiến độ của
`crawl.py`, Agoda: số lượt hỏi giá, khách sạn Trip: số mốc ngày đã hỏi, bước lớn: số bước con đã xong); đã xong: phần thành
công / tổng (Booking theo dòng `Trạng thái: {...}` cuối, không đếm lượt thử lại; Agoda: có giá + hết phòng / lượt hỏi; chuẩn hoá
theo nguồn: bản ghi không lỗi; Kiểm tra: số luật đạt; Nạp DB: dòng ghép được với DB; Index: dòng embed được). Dưới 90% tô vàng.
Ô đang chạy chưa biết tổng thì có sọc chạy; ô chờ để trắng. Ô cào nguồn có danh sách làm mới hiện thêm "làm mới khách sạn đang
có x/y". Bấm ô Bảo trì DB, Gộp catalog, Kiểm tra, Nạp DB, Index (và chuẩn hoá theo nguồn) để bung chuỗi bước con ngay trong sơ
đồ: tên, trạng thái, giây, vào → ra (bước lọc/gộp hiện "bớt N"; bước chỉ sửa dòng có sẵn hiện "N dòng · M đổi"), đạt/tổng, ghi
chú; bấm lại để thu. Bước con ghi ở `detail.substeps` của bước trong run.json (`stage_log.Stages`; chuẩn hoá dùng
`normalise_stages/steps.json`) và một dòng log `catalog.substep name=<bước>:<bước con> …`: tab Log của ô lớn lọc theo
`name=<bước>`, bấm một ô con mở tab Log lọc đúng bước con đó.

**Bước con chưa chạy và log theo bước (09/10/2026):** danh sách bước con của từng bước lớn khai báo ở
`pipeline_graph.SUBSTEPS` (test đối chiếu với code), nên ô chưa chạy vẫn bung được; bước con chưa có số liệu là ô mờ viền đứt
mang trạng thái "Chờ tới lượt" (sau bước con đang chạy, hoặc cả ô đang chờ) hoặc "Không chạy" (lượt này không chạy bước con
đó). Bản gộp nháp trong lúc cào chỉ có chuỗi từ "đọc checkpoint". Mỗi bước con (`stage_log.Stages`) ghi một dòng
`status=running` lúc bắt đầu và một dòng kết quả lúc xong. Tab Log của ô Gộp và các ô con của nó lấy thêm dòng
`normalise.step.*` (gộp chính thức, và bản nháp có tiền tố `[preview]`) nên xem được ngay trong lúc gộp; ô Gộp (không chọn
ô con) còn hiện toàn bộ log "Catalog đang gộp" (mọi dòng `[preview]`, `catalog.preview.*`), kể cả khi bước Gộp chính thức
chưa chạy, và mọi dòng không tiền tố giữa `catalog.step.start name=normalise` và mốc bước kế tiếp (log của bước Gộp chính
thức chạy trong tiến trình job: đọc interim, gộp trùng, "Đã ghi …", cảnh báo). Lọc `name=<bước>` khớp đúng tên bước, không lẫn `normalise.source:…` / `normalise.preview`; đầu tab Log ghi
đang lọc theo bước nào, kèm nút bỏ lọc. Tab "DB" có nút "Tải lại" và ô "Tự làm mới mỗi 10 giây" (mặc định bật khi đang có
lượt chạy; mỗi lần đếm lại số dòng mọi bảng).

**Dung lượng (tab "Dung lượng" của monitor, 06/10/2026):** hiện đĩa VM (đã dùng / còn trống của filesystem chứa thư mục dữ
liệu), dung lượng từng thư mục con và từng lượt cào còn giữ; nút "Xoá các lượt cũ hơn" giữ N lượt mới nhất (lượt đang chạy
luôn được giữ; state và dữ liệu đã nạp DB không bị đụng). API: `GET /api/storage`, `POST /api/storage/cleanup {"keepRuns": N}`.
Monitor không xoá được image Docker (container không có quyền Docker): bước deploy job cào gọi
`run_daily_docker.sh prune-images <image vừa deploy>`, giữ image đó và một bản trước, xoá image cũ hơn của cùng repository.
Dọn tay trên VM: `run_daily_docker.sh cleanup` (container dừng, image dangling, lượt cũ chỉ giữ N lượt mới nhất — mặc định 2, log quá 7 ngày).

Phục vụ FR-CAT-01/03 và NFR-SEC-01. Dùng cùng **image/tag, env file và volume** với `fresh-run`:

```bash
FRESH_IMAGE=<AR>/vota-fresh-catalog:<tag> /opt/vota/bin/run_daily_docker.sh fresh-monitor
# Tab DB của monitor đọc DB đích bằng SEED_DATABASE_URL (DB_TARGET=local) hoặc CLOUD_SEED_DATABASE_URL, chỉ đọc.
# Tab Realtime đọc GET $BACKEND_URL/internal/calls (mặc định http://127.0.0.1:8000). BACKEND_URL= (trống) tắt tab: staging-ha đang tắt.
# `fresh-monitor` chạy nền với --restart unless-stopped (Docker tự bật lại khi bị tắt vì hết RAM hay VM khởi động lại;
# log: docker logs -f vota-fresh-catalog-monitor). MONITOR_RESTART=no chạy tiền cảnh như trước. Không giới hạn RAM mặc
# định vì lượt bấm trên monitor chạy trong container này; MONITOR_MEMORY đặt giới hạn nếu cần.
# `monitor` (không có `fresh-`) chạy cùng UI trong image daily, đọc <DATA_DIR>/state, /fresh_runs.
# Công khai (đặt env trước khi chạy; mặc định tắt):
#   MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1   nghe mọi interface, chấp nhận Host public, không có đăng nhập
#   MONITOR_READ_ONLY=1                     tuỳ chọn: chỉ GET, mọi POST trả 405; khi bật thì 7 API điều khiển không dùng được
# Trên máy cá nhân:
ssh -L 8765:127.0.0.1:8765 <user>@<vm>
# Mở http://127.0.0.1:8765/ ; /daily và /pipeline tự chuyển về đây.
```

Mặc định server chỉ nghe loopback trên mạng host của VM; URL DB trong env phải phân giải được từ mạng host (IP nội bộ/loopback, không chỉ tên service Docker). **Staging đang công khai:** CD `crawler-ci-cd.yml` chạy `fresh-monitor` với `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1` và không có `MONITOR_READ_ONLY` (đọc và ghi). Staging-ha (`scripts/deploy-staging-ha-crawler.sh`) công khai đủ chức năng qua `monitor.praxis.io.vn` (LB HTTPS sau Cloudflare; VM không có IP public; deploy thủ công; bản đầu chạy chỉ đọc, xem [entry lịch sử](../../history/2026-10-09-monitor-chi-doc-deploy-thu-cong.md)). Dashboard công khai không có đăng nhập; POST chỉ kiểm header `X-Requested-With: vota-monitor`. Tab Realtime trên staging-ha đang tắt (BACKEND_URL trống). Nếu cổng 8765 còn bị monitor cũ chiếm, dừng **đúng tiến trình/container monitor cũ** trước khi khởi động bản mới; không dừng backend/DB. Monitor không mount Docker socket.

- **Tổng quan:** lượt hiện tại, bước đang chạy, lịch kế, log runner, trạng thái cấu hình kết nối và nơi lượt kế tiếp ghi (host/database/collection, không có tài khoản). Secret chỉ báo đã đặt/chưa đặt.
- **Một lượt** (bấm mã lượt), các tab:
  - *Tiến độ & tốc độ*: bước của lượt và bảng từng nguồn: trạng thái, tiến độ x/y, số file raw, bản ghi interim so với lượt cùng chế độ trước đó, cảnh báo/lỗi/bị chặn/mã HTTP lỗi, dòng log gần nhất. “Mất nguồn” khi nguồn lỗi, bị chặn (mã 75), bị bỏ vì nguồn khác lỗi, không chạy tới, hoặc chạy xong mà 0 bản ghi. Khi lượt đang chạy: chỉnh delay từng nguồn, tạm dừng/chạy tiếp (có hiệu lực ở request kế tiếp, mức tối thiểu như trang Cấu hình, chỉ cho lượt đó); số tab/worker lưu cho lượt sau.
  - *Theo thành phố*: catalog đã chuẩn hoá (bản nháp hoặc chính thức) theo thành phố × loại (khách sạn, hạng phòng, điểm tham quan/vé, tuyến bay, chuyến bay, combo) × nguồn; và bản ghi interim theo thành phố × nguồn khi đang cào (đọc tăng dần, tự cập nhật 5 giây). Khách sạn Vinpearl chưa có thành phố cho tới bước chuẩn hoá nên nằm ở dòng "chưa rõ" của bảng interim.
  - *Log* (stream trực tiếp): `job.log` qua server-sent events, lọc theo nguồn, mức, chữ.
  - *Raw / interim*: JSON/HTML gốc đã làm sạch (xem JSON, văn bản hiển thị, JSON-LD, `__NEXT_DATA__`) và bản ghi đã parse.
  - *Chuẩn hoá*: số dòng và từng dòng sau mỗi bước của `normalise.py` (ánh xạ nguồn → gộp trùng → lọc → làm giàu → kiểm vị trí/giá), dòng bị loại kèm lý do, cặp gộp trùng, truy vết một sản phẩm qua các bước với trường đã đổi.
  - *Chuẩn hoá theo nguồn và bản nháp* (lượt cào lớn, cấu hình "Chuẩn hoá từng nguồn ngay khi nguồn cào xong", mặc định bật): bước cào nào xong thì `normalise.py --only-source` ánh xạ ngay file interim của bước đó, không đợi các bước khác cùng site (vd. vé máy bay Trip không đợi điểm tham quan); file còn lại của site được ánh xạ khi cả site xong (tối đa 2 tiến trình) thành checkpoint `<lượt>/normalised/<nguồn>.jsonl`; sau đó gộp nháp từ các checkpoint vào `<lượt>/preview/` để xem ở tab Chuẩn hoá / Catalog cuối (công tắc “Catalog đang gộp (mới nhất)” / “Bản chính thức”). Bước normalize chính thức (`--reuse-checkpoints`) chỉ ánh xạ lại nguồn còn thiếu, cũ hoặc lỗi rồi gộp. Không validate, không nạp DB, không index ở bản nháp; lượt lỗi giữ bản nháp cuối.
  - *Chuẩn hoá – phần ổn định*: bảng "Thời gian từng bước normalize" (giây, vào → ra, RAM, traceback khi lỗi), "Bản ghi lỗi khi ánh xạ" (bản ghi hỏng bị bỏ, quá ngưỡng thì dừng), cột "Lỗi / thử lại" ở bảng bước (lỗi tạm thời/hạ tầng tự thử lại, nguồn bị chặn bị bỏ qua, lỗi code dừng ngay, catalog tụt mạnh thì không nạp DB). Chạy lại riêng: `normalise.py --only-source <nguồn>`, `normalise.py --merge-only`.
  - *Catalog cuối*, *Trước → sau* (nạp DB), *Báo cáo*.
  - *Embedding*: text đưa vào model e5-small cho từng search unit (tiền tố `passage: `), hash, nhúng mới/giữ nguyên/xoá và lý do, 8 chiều đầu + độ dài vector, đọc vector đang lưu trong Weaviate; ô thử truy vấn (e5-small, tiền tố `query: `, xếp hạng cosine trên collection đích; model nạp một lần ở lần bấm đầu).
- Lượt bị kill được đánh dấu mất tiến trình qua khoá file; heartbeat cũ được báo riêng.
- **Cấu hình:** file `/data/state/settings.json` ưu tiên hơn env, rồi mới tới mặc định. Chỉ gửi thay đổi; nút “Về env/mặc định” xoá override của trường đó. Lượt đang chạy giữ cấu hình ban đầu.
- **Trip nhiều khách sạn:** bấm “Áp ngân sách Trip 30 / 10 / 180” rồi Lưu, kể cả env cũ vẫn đặt 10/3/60. Có thể tăng thêm: tối đa 500 ID/thành phố, quét 2.000 ID/thành phố, 2.000 ID/daily. Đây là ngân sách, không bảo đảm nguồn trả đủ. Giữ 2 tab giá + 4 worker HTTP trên VM 2 CPU/4 GB; mức này chưa được benchmark với ngân sách mới trên VM.
- Collector dùng lại HTTP session và kết thúc chờ khi có JSON phòng hợp lệ; lượt khám phá đầu dừng ở ngân sách chọn, thay vì quét đủ 300 rồi bỏ phần dư. Không rút ngắn giới hạn chờ tối đa hoặc bỏ kiểm coverage ba mốc ngày.
- **Chạy/dừng:** chạy tay bỏ qua lịch; cron `tick` kiểm lịch dưới khoá và chỉ bắt đầu một lượt/ngày theo giờ Việt Nam. Lượt đã bắt đầu nhưng lỗi không tự retry mỗi 15 phút; xem log rồi chạy tay. `fresh-run auto` vẫn chạy ngay theo chu kỳ, không chịu công tắc giờ lịch của monitor. `fresh-run due` chỉ in mode đang tới lịch, không chạy job.
- Dừng qua file dùng chung nên có hiệu lực cả khi cron/monitor ở hai container. Tác vụ cào bị huỷ tại điểm kiểm tra; bước DB đã bắt đầu có thể hoàn tất và dữ liệu đã commit được giữ. Bước bảo trì DB ở đầu lượt không bị hoàn tác khi dừng.

- **Giao diện (28/09/2026):** thanh trên Tổng quan · Lịch sử · Hệ thống · Cấu hình, nút chạy/dừng lượt luôn ở thanh trên.
  Mở một lượt là **sơ đồ luồng** (chuẩn bị → cào → chuẩn hoá → gộp → kiểm tra → nạp DB → index); bấm một ô để xem bước đó
  (bước con bên trong, log đã lọc, dữ liệu, lỗi). Ô lỗi được chọn sẵn; URL `#run=…&node=…&view=…` mở lại đúng chỗ.
  Lịch sử có dải ô trạng thái từng bước để so các lượt. Plan: `docs/plan/2026-09-28-monitor-so-do-luong.md`.
- **Chạy lại từ bước lỗi (không cào lại):** nút “Chạy lại từ bước này” trên ô Gộp / Kiểm tra / Nạp DB / Index của lượt đã
  kết thúc, hoặc `./local_crawl.sh run resume <mã lượt> normalise|merge|validate|db|index`
  (`fresh_catalog.py resume <mã lượt> --from <bước>`). Không cập nhật trạng thái xoay vòng khách sạn Trip.
- **Hạn giờ và cào lại một nguồn (29/09/2026):** mỗi bước cào có hạn giờ riêng và cả phần cào có `crawl.maxHours`
  (Cấu hình → Thử lại và kiểm chất lượng; 0 = không giới hạn). Quá hạn thì dừng riêng nguồn đó (cả Chromium), giữ phần đã
  cào, các nguồn khác và các bước sau cào chạy tiếp; lượt kết thúc "chưa đủ dữ liệu" và có cảnh báo `timeout`. Ô cào bị
  chặn / lỗi / quá giờ có nút “Cào lại nguồn này”, hoặc `./local_crawl.sh run resume <mã lượt> crawl <nguồn>`
  (`fresh_catalog.py resume <mã lượt> --from crawl --source <nguồn>`): chỉ cào lại nguồn đó rồi chuẩn hoá, nạp DB, index.
  Nguồn, bước và quan hệ giữa chúng khai báo ở `pipeline_graph.py`. Plan: `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md`.
- **Chạy liên tục** (Cấu hình → Chạy liên tục, mặc định **tắt**): chuẩn hoá từng phần trong lúc cào, gộp theo chu kỳ, và nếu bật
  thêm thì nạp DB / index theo phần vào đích `DB_TARGET` của lượt. Dòng đã nạp giữa lượt ở lại dù cuối lượt lỗi. Khi lượt
  đang chạy, chỉnh chu kỳ / tạm dừng / chạy ngay ở tab “Chạy liên tục” của lượt. Plan: `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`.
- **Cảnh báo và SLA** (Cấu hình → Cảnh báo và SLA): lượt lỗi, bị chặn chất lượng, nguồn bị chặn, trễ SLA được ghi vào
  `<state>/alerts.jsonl` và hiện ở Tổng quan; chưa gửi ra ngoài. SLA được kiểm ở mỗi cron tick.

Job cũ không sinh `run.json` mới nên lịch sử cũ không được chuyển sang giao diện này. Log runner của job mới trước lần nâng cấp vẫn có thể xem khi thư mục log được mount. Runner thêm group của thư mục log cho monitor để đọc được thư mục mode `750`; các file log phải cho group đọc (ví dụ `640` hoặc `644`).

### Chạy thử job mới trên máy cá nhân

Cần Docker, Python ≥ 3.10 có `requirements.txt` (vd. `conda activate vsf`), Chromium của Playwright, `xvfb-run`. Embed chạy e5-small trong tiến trình, không cần khoá; lần đầu model được tải về cache Hugging Face. [local_crawl.sh](local_crawl.sh) ghi vào Postgres + Weaviate Docker local, vào
database `vota_crawl` và collection `ProductCrawl` riêng; không đụng `vota`/`Product` của backend local. Lượt chạy ở chế độ
local (`CATALOG_LOCAL_ONLY=1`) nên `fresh_catalog.py` dừng ngay nếu đích DB/Weaviate không phải localhost, kể cả khi `.env`
gốc đang trỏ `WEAVIATE_URL` tới Weaviate Cloud.

```bash
cd src/data_collection
export LOCAL_CRAWL_NAME=demo  # tuỳ chọn: bộ riêng vota_crawl_demo / ProductCrawlDemo / data/local_crawl_demo
./local_crawl.sh setup      # docker compose up postgres weaviate; tạo database từ db/vota_schema.sql + migration; cấu hình đa luồng
./local_crawl.sh small      # tuỳ chọn: phạm vi nhỏ (Nha Trang + Hà Nội, 3 khách sạn/nguồn, Vinpearl 1 ngày giá)
./local_crawl.sh monitor    # http://127.0.0.1:8765 → "Cào lớn"; theo dõi ở tab Tiến độ & tốc độ / Log
./local_crawl.sh run full   # hoặc chạy từ terminal; `run status` in lịch kế tiếp
./local_crawl.sh run resume <mã lượt> db   # chạy lại lượt đã kết thúc từ một bước sau cào, không cào lại
./local_crawl.sh run resume <mã lượt> crawl booking   # cào lại riêng một nguồn rồi chạy tiếp tới index
./local_crawl.sh reset      # xoá database, collection và thư mục của bộ hiện tại (hỏi xác nhận)
```

`setup` của một bộ mới ghi sẵn cấu hình đa luồng: 4 site (trip vé máy bay/điểm tham quan, vinpearl, booking, agoda) bắt
đầu cùng lúc nên một site lỗi không làm site khác bị bỏ (lượt vẫn dừng trước khi nạp DB), booking/agoda 2 tab, lịch tắt,
khách sạn Trip tắt vì trang danh sách Trip đang trả "Tìm thấy 0 nơi lưu trú" cho trình duyệt tự động (25/09/2026).

Trình duyệt chạy trong Xvfb; `SHOW_BROWSER=1 ./local_crawl.sh monitor` để thấy cửa sổ Chromium (tự bấm xác minh nếu nguồn hỏi).
Dữ liệu các lượt ở `data/local_crawl/` (Git ignore). Bước index embed bằng e5-small cho search unit mới hoặc đổi text; ô thử truy
vấn chạy e5-small trong tiến trình monitor, mỗi lần bấm một truy vấn.

### Nối DB nội bộ và chống chồng lượt (HA)

Job `fresh_catalog.py` nối DB bằng `db.vota.internal:5432` (không tunnel SSH, không qua pgbouncer), giữ **khoá tệp** (một
container) và **khoá DB** `pg_try_advisory_lock(7791025)` (giữa các container; `catalog_run_lock.py`, tắt chỉ để chạy thử bằng
`CATALOG_DB_RUN_LOCK=off`) nên tick chồng nhau thoát với `catalog.lock.busy`. `CATALOG_LOCK_DIR` đặt khoá tệp ra thư mục khác state. Mỗi tick phát `catalog.freshness` (`state`, `age_hours`) cho cảnh báo ngoài job. Hướng dẫn: `docs/guide/van-hanh-crawler-db-noi-bo.md`.

## Chạy

Chạy trọn kế hoạch (Vinpearl → trip.com → booking.com → agoda.com → normalise), ước tính 2–3 giờ:

```bash
python crawl.py handbook --fast
```

Chạy thử nhỏ trước (2 điểm đến, 3 sản phẩm mỗi loại, khoảng 15 phút):

```bash
python crawl.py handbook --destinations 'Nha Trang,Phú Quốc' --per-destination 3 --tour-limit 25 --fast
```

Hoặc chạy từng nguồn, theo thứ tự handbook:

```bash
python crawl.py vinpearl
python crawl.py trip-flights
python crawl.py trip-attractions
python crawl.py booking-hotels --fast --concurrency 2
python crawl.py agoda-hotels
python crawl.py venues              # toạ độ địa điểm vé Vinpearl (chỉ gọi mạng cho địa điểm chưa có toạ độ)
python normalise.py
```

Kết quả: `data/products.jsonl`, `data/products.csv`, `data/stats.md` (có bảng **đối chiếu mục tiêu handbook**),
`data/template.json`, `data/SCHEMA.md`, `data/sample/`, `data/quality_review.csv`, `data/dedup_report.csv`
và thư mục `data/map/` (bản đồ).

Ctrl+C lúc nào cũng được: chạy lại đúng lệnh cũ sẽ tiếp tục từ chỗ dừng. `python crawl.py status` xem tiến độ.

## Kế hoạch: 15 điểm đến

Chọn các điểm đến có Vinpearl trước, rồi thêm các điểm du lịch lớn. Slug/mã của từng nguồn đã được kiểm tra thủ công
và nằm trong [collectors/plan.py](collectors/plan.py).

| Điểm đến | Vinpearl | booking.com tìm | agoda city | trip.com city | Sân bay |
|---|---|---|---|---|---|
| Nha Trang | ✓ | Nha Trang | nha-trang-vn | nha-trang-670 | CXR |
| Phú Quốc | ✓ | Phu Quoc | phu-quoc-island-vn | phu-quoc-island-24779 | PQC |
| Hội An | ✓ | Hoi An | hoi-an-vn | hoi-an-668 | (qua DAD) |
| Đà Nẵng | | Da Nang | da-nang-vn | da-nang-669 | DAD |
| Hạ Long | ✓ | Ha Long | h-long-vn | ha-long-city-1524623 | VDO |
| Hà Nội | ✓ | Hanoi | hanoi-vn | hanoi-181 | HAN |
| TP. Hồ Chí Minh | | Ho Chi Minh City | ho-chi-minh-city-vn | ho-chi-minh-city-434 | SGN |
| Hải Phòng | ✓ | Hai Phong | haiphong-vn | haiphong-180 | HPH |
| Nghệ An | ✓ | Cua Lo | vinh-vn | vinh-city-24768 | VII |
| Hà Tĩnh | ✓ | Ha Tinh | ha-tinh-vn | – | (qua VII) |
| Đà Lạt | | Da Lat | dalat-vn | dalat-1393 | DLI |
| Huế | | Hue | hue-vn | hue-667 | HUI |
| Quy Nhơn | | Quy Nhon | quy-nhon-binh-dinh-vn | quy-nhon-24728 | UIH |
| Sa Pa | | Sa Pa | sapa-vn | sapa-24736 | – |
| Phan Thiết | | Mui Ne | phan-thiet-vn | phan-thiet-1218 | – |

Ngân sách mặc định **mỗi điểm đến**: 30 khách sạn booking.com, 20 khách sạn agoda.com (khách sạn trùng sẽ được gộp),
25 điểm tham quan trip.com, tối đa 3 hạng phòng OTA mỗi khách sạn, 5 chuyến bay cụ thể mỗi tuyến. Toàn bộ sản phẩm
Vinpearl luôn được lấy, cộng mọi khách sạn mang thương hiệu Vinpearl trên booking.com. Ước tính catalog cuối
khoảng **3.000–3.500 sản phẩm**.

- Đổi điểm đến: `--destinations 'Nha Trang,Đà Lạt'` (áp dụng cho cả `crawl.py` và `normalise.py`), hoặc sửa `plan.py`.
- Đổi quy mô: `--per-destination 40` (khách sạn booking và điểm tham quan = 40, agoda = 2/3 con số đó).
- Sau khi đổi kế hoạch, thêm `--rediscover` để tìm URL mới.

## Nguồn và cách lấy

| Nguồn | Cách lấy | Trình duyệt | Lấy được |
|---|---|---|---|
| **Vinpearl, khách sạn** | `booking-hotel-api.vinpearl.com` `/availability/rooms` cho nhiều ngày (`--price-dates`) | không | mô tả, địa chỉ, toạ độ, sao, điểm TripAdvisor, tiện nghi, ảnh; mỗi hạng phòng: mô tả, diện tích, giường, sức chứa, giá theo ngày |
| **Vinpearl, vé/tour/combo/golf** | `booking-tour-api.vinpearl.com`, gọi từ trong trang booking.vinpearl.com | có (Cloudflare) | tên, mô tả chi tiết, bao gồm, lịch trình, giá người lớn/trẻ em, thời gian bán, nhà cung cấp (= nơi dùng vé, để suy ra toạ độ). **API không có toạ độ** |
| **trip.com, vé máy bay** | trang sân bay `/flights/airport-<iata>/` → tuyến giữa các điểm đến → trang giá vé `/flights/<a>-to-<b>/airfares-…/` (JSON-LD) | không | giá theo tháng, khứ hồi, chuyến cụ thể (số hiệu, hãng, giờ, thời gian bay, giá) |
| **trip.com, điểm tham quan** | `/travel-guide/attraction/<city>/tourist-attractions/` → trang điểm (`__NEXT_DATA__`) | không | giới thiệu, địa chỉ, toạ độ, **giờ mở cửa**, **thời lượng đề xuất**, giá vé, điểm, loại hình |
| **booking.com, khách sạn** | trang tìm kiếm theo điểm đến (`order=popularity`) + sitemap lọc thương hiệu Vinpearl → trang khách sạn kèm ngày | có | mô tả tiếng Việt, toạ độ, sao, điểm, tiện nghi, hạng phòng + giá + điều kiện |
| **agoda.com, khách sạn** | trang thành phố → trang khách sạn kèm ngày | có | mô tả tiếng Việt, toạ độ, sao, điểm, tiện nghi, giá rẻ nhất |
| **agoda.com qua API** (`crawl.py agoda-api`) | sitemap → trang khách sạn (lấy `hotel_id`) → `/api/cronos/property/BelowFoldParams/GetSecondaryData` từng ngày nhận phòng; tiến độ ở `data/state/agoda_api.sqlite` | không | mô tả tiếng Anh, toạ độ, sao, điểm, tiện nghi, ảnh; từng hạng phòng: diện tích, giường, sức chứa, giá rẻ nhất mỗi ngày (USD gồm thuế phí → VND) |
| booking.com, attraction *(nguồn phụ, ngoài kế hoạch)* | sitemap → trang attraction | có | mô tả (đa phần tiếng Anh), thời lượng, bao gồm, điểm khởi hành, giá |

Robots.txt được tôn trọng. Riêng trip.com cấm các trang tìm chuyến bay (`showfarefirst`, `/*-to-*/tickets-*`,
`graphql`), nên script chỉ dùng trang giá vé theo tuyến, loại trang được phép.

### Vì sao cần trình duyệt, và `--headless`

Script dùng Chromium thật qua Playwright, **không** dùng stealth plugin, giả fingerprint, proxy hay giải CAPTCHA.
Kết quả chạy thử (15/09/2026):

| | Có cửa sổ (mặc định) | `--headless` |
|---|---|---|
| Vinpearl khách sạn, trip.com (HTTP) | chạy | chạy |
| Vinpearl vé/tour | chạy | **bị Cloudflare chặn** |
| booking.com: dữ liệu khách sạn | chạy | chạy |
| booking.com: **giá** | chạy | **không có giá** |
| agoda.com | chạy | chưa thử |

Nếu cửa sổ hiện ô "Xác minh bạn là con người", **bạn tự bấm** trong cửa sổ đó; script chờ tối đa `--manual-wait` giây.
Server không có màn hình: `xvfb-run -a python crawl.py handbook`.

`--fast` (không chờ trang tải xong, chặn CSS/tracker) nhanh gấp đôi với booking.com; agoda.com tự tắt chế độ này
vì trang không render khi thiếu CSS.

## Luồng xử lý

```mermaid
flowchart LR
  P["collectors/plan.py<br/>15 điểm đến · ngân sách"] --> CLI["crawl.py handbook"]
  CLI --> VP["vinpearl.py"] & TR["trip.py"] & BK["booking_hotels.py"] & AG["agoda_hotels.py"]
  BK --> BB["booking_base.py<br/>tìm URL → hàng đợi → Chromium"]
  AG --> BB
  VP & TR & BB -. dùng .-> CM["common.py<br/>HTTP · trình duyệt · cache · state · robots · rate limit"]
  VP & TR & BB --> RAW[("data/raw/&lt;nguồn&gt;/<br/>đã xoá review")]
  TR & BB --> ST[("data/state/crawl_state.sqlite")]
  VP & TR & BB --> INT["data/interim/&lt;nguồn&gt;.jsonl"]
  INT --> VE["crawl.py venues<br/>trip.com → OpenStreetMap"]
  VE --> VC[("collectors/venues.csv<br/>toạ độ địa điểm, duyệt tay")]
  INT --> N["normalise.py<br/>gộp trùng · OTA thắng giá · toạ độ · lọc theo kế hoạch"]
  VC --> N
  N --> OUT["products.jsonl · products.csv<br/>stats.md · dedup_report.csv"]
  N --> MAP["map/<br/>Google My Maps CSV · places.geojson · can-kiem-tra.csv"]
```

## Dữ liệu nằm ở đâu

Mặc định trong `src/data_collection/data/` (đổi bằng `--data-dir` hoặc `VOTA_DATA_DIR`):

| Đường dẫn | Chứa gì |
|---|---|
| `raw/vinpearl/json/` | JSON gốc API Vinpearl: `api-rooms-<hotelId>-<ngày>-2a`, `api-tour-list-*`, `api-tour-detail-<slug>` |
| `raw/trip_flights/json/`, `raw/trip_attractions/json/` | JSON-LD + dữ liệu sản phẩm của trang (review đã bỏ), kèm URL; `html/` là trang danh sách |
| `raw/booking_hotels/html/` | trang khách sạn và trang tìm kiếm, bản gọn (~45 KB/trang, đã bỏ review); `xmlgz/` là sitemap |
| `raw/agoda_hotels/html/` | trang khách sạn và trang thành phố (đã bỏ review) |
| `interim/<nguồn>.jsonl` | bản ghi đã parse, mỗi nguồn một file |
| `raw/geocode/` | kết quả tìm địa điểm trên OpenStreetMap (Photon), mỗi truy vấn chỉ gửi một lần |
| `map/` | vị trí cho bản đồ: `mymaps-*.csv`, `places.geojson`, `can-kiem-tra.csv` |
| `state/crawl_state.sqlite` | hàng đợi URL (`items`: trạng thái, số lần thử, điểm đến + thứ hạng trong kế hoạch) và tiến độ tìm URL (`discovery`) |
| `browser-profile/<nguồn>/` | cookie trình duyệt |
| `logs/crawl-YYYYMMDD.log` | log |

Parser sai thì sửa code rồi chạy `python crawl.py reparse <nguồn>`: parse lại từ cache, không tải lại.

## Schema đầu ra

Mỗi dòng `products.jsonl` có đúng 13 trường của §6/CDP (xem
[schema.md](../../docs/spec/data-collection/schema.md#bốn-chỗ-dễ-hiểu-sai)). `priceUnit` là field bắt buộc của
`ProductSummary` ở API, nhưng không phải cột của `cdp.products`; lớp API phải chiếu field này và dùng
`UNKNOWN` khi nguồn catalog chưa cung cấp đơn vị, đúng contract baseline. Pipeline không tự suy đơn vị
từ taxonomy. Mọi thông tin nguồn khác nằm trong `attributes`, để không tự thêm field mà CDP thật không có.

```json
{
  "productId": "9d5cd325-a23d-5907-90aa-7286e06d6654",
  "name": "Vinpearl Resort Nha Trang - Deluxe Giường Đôi",
  "taxonomy": "hotel",
  "destination": "Nha Trang",
  "description": "Với diện tích 32 m², Deluxe Giường Đôi là phòng khách sạn thiết kế hiện đại…",
  "attributes": { "level": "room", "starRating": 5, "oceanView": null, "familyFriendly": true, "maxOccupancy": 4,
                  "roomSizeM2": 32, "vinpearlPrice": 3040000, "otaRoomName": "…", "parentProductId": "…" },
  "unitPrice": 2788898,
  "currency": "VND",
  "available": true,
  "availableFrom": null,
  "availableTo": null,
  "imageUrl": "https://booking-static.vinpearl.com/room_types/…jpg",
  "sourceRef": "vinpearl:hotel:1dc9c659-…:room:26863e0c-…"
}
```

- `productId` = UUIDv5 của `sourceRef`, **ổn định giữa các lần chạy**.
- `taxonomy`: `hotel` (`attributes.level` = `property` / `room`), `flight` (`route` / `flight`), `attraction`, `combo`, `golf`.
- Tên theo mẫu handbook: `"<Khách sạn> - <Hạng phòng>"`, `"Vé máy bay Hà Nội - Nha Trang"`.
- Mô tả tự sinh (vé máy bay, phòng OTA, vé và điểm tham quan thiếu giới thiệu) được đánh dấu bằng `attributes.descriptionSource`.
- **Điều khoản vé không nằm trong `description`.** API Vinpearl trả điều khoản, chính sách hoàn huỷ và hướng
  dẫn sử dụng lẫn trong khối nội dung, kể cả khối mang tiêu đề "Mô tả". `normalise.py` lọc theo từng dòng
  (`split_policy_lines`) và đẩy phần điều khoản sang `attributes.policies`; mô tả dùng để embedding chỉ nói về
  sản phẩm. Không có bước này thì 344 vé dùng chung vài đoạn điều khoản làm mô tả và vector của chúng gần như
  trùng nhau.
- Mô tả vé luôn mở đầu bằng tên vé, vì nhiều vé của cùng một khu vui chơi dùng chung đúng một đoạn giới thiệu
  địa điểm. Mô tả ngắn hơn 120 ký tự được bổ sung từ dữ liệu có cấu trúc (thời lượng, đối tượng, địa điểm, giá).
- Biến thể giá thành viên (`[VIN33 - Gold/Platinum/Diamond]`) được gộp về sản phẩm gốc, giá từng hạng giữ trong
  `attributes.memberPrices`. Vé nào không có bản không-hạng thì giữ lại một biến thể và đổi tên về tên gốc.
- Sản phẩm mà nguồn chỉ có mô tả tiếng Anh được dựng mô tả tiếng Việt từ thuộc tính có cấu trúc (tên, loại
  hình, hạng sao, địa chỉ, tiện ích, điểm đánh giá); văn bản gốc chuyển sang `attributes.descriptionOriginal`.
- **Sản phẩm không có giá mà nguồn không cung cấp được sẽ bị loại** (mặc định; `--keep-unsellable` để giữ).
  Không áp dụng cho điểm công cộng không bán vé — với chúng, không có giá là dữ liệu đúng. Số lượng bị loại
  luôn ghi trong mục "Bị loại" của `stats.md`.

### Nguồn của từng trường

| Trường | Khách sạn / phòng | Vé máy bay | Điểm tham quan / vé |
|---|---|---|---|
| `name` | Vinpearl → booking → agoda | ghép từ tên thành phố | Vinpearl → trip.com |
| `description` | Vinpearl → booking (nếu tiếng Việt) → agoda | tự sinh từ dữ liệu chuyến bay | Vinpearl → trip.com (giới thiệu) |
| `destination` | `geo.py`: tên Vinpearl / thành phố / địa chỉ, tên cụ thể thắng tên tỉnh | thành phố đến | quận/huyện → địa chỉ → tỉnh |
| `unitPrice` | **nguồn có giá mới nhất**, cùng ngày thì booking.com → agoda.com → Vinpearl; phòng Vinpearl khớp tên với phòng booking.com thì lấy giá booking nếu không cũ hơn; khách sạn có ở cả booking và agoda (API) thì hạng phòng lấy bên mới hơn | giá một chiều rẻ nhất | **trip.com → Vinpearl** |
| `available` | có giá cho ngày đã hỏi | có chuyến có giá | có giá vé (điểm công cộng không bán vé → `false`, `attributes.ticketed=false`) |
| `availableFrom/To` | – | ngày bay sớm nhất / muộn nhất thấy được | thời gian bán của vé Vinpearl |
| toạ độ (`latitude`, `longitude`) | nguồn chính; nghi sai hoặc thiếu thì nguồn khác | sân bay đến | vé Vinpearl: địa điểm dùng vé (`venues.csv`), rồi trip.com; điểm tham quan: trip.com |
| sao | nguồn chính, thiếu thì nguồn khác | – | – |
| giờ mở cửa, thời lượng | – | thời gian bay | trip.com (`openingHours`, `suggestedDuration`, `durationMinutes`) |
| giá khác | `vinpearlPrice`, `otaPrices`, `bookingReviewScore`, `agodaReviewScore` | `monthlyPrices`, `roundTripFrom` | `vinpearlPrice`, `otaPrices` |

Combo bay + ở trip.com (`comboKind: trip_real_flight_hotel`): `departDate`/`returnDate` là ngày ISO. Trang chỉ ghi "14/10", nên năm lấy từ `dDate`/`rDate` của URL tìm kiếm (`collectors/textutil.trip_combo_dates`); không khớp thì bỏ khoá. Seed (`load_products`) và `apply_window` của job cào chuyển luôn các dòng cũ còn dạng "14/10" trong snapshot/DB.

### Gộp trùng

- **Khách sạn**: so khớp tên (bỏ dấu, bỏ "khách sạn/khu nghỉ dưỡng/hotel", thử cả tên tiếng Anh trong ngoặc của agoda)
  kết hợp khoảng cách toạ độ, trong cùng điểm đến. Mỗi cụm có tối đa một bản của mỗi nguồn. Ví dụ chạy thử:
  "Vinpearl Resort Nha Trang" (Vinpearl) ↔ booking.com cách 523 m; "Hòn Tằm Resort" ↔ agoda "Khu nghỉ dưỡng Hòn Tằm (…)" cách 670 m.
- **Điểm tham quan**: điểm trip.com trùng tên vé Vinpearl thì gộp vào vé. Các vé Vinpearl khác có chứa tên điểm đó được
  bổ sung giờ mở cửa, thời lượng, toạ độ.
- Mọi cặp đã gộp nằm trong `dedup_report.csv`; kiểm tra tay trước khi dùng.

## Vị trí (toạ độ) và Google Maps

Toạ độ nằm trong `attributes.latitude` / `attributes.longitude` (độ thập phân, cùng hệ với Google Maps), kèm:

- `locationSource`: `vinpearl`, `booking.com`, `agoda.com`, `trip.com`, `osm`, `manual`, `ourairports`
- `locationPrecision`: `exact` (vị trí riêng của khách sạn / điểm tham quan), `venue` (khu vui chơi, sân golf nơi dùng vé),
  `poi` (điểm tham quan trip.com trùng tên vé), `airport` (sân bay đến; `originLatitude/originLongitude` là sân bay đi)
- `locationWarning` (toạ độ đáng ngờ), `locationNote` (đã thay toạ độ nguồn chính), `venue` (tên địa điểm dùng vé)

| Loại | Toạ độ lấy từ |
|---|---|
| Khách sạn | API Vinpearl, booking.com, agoda.com. Hạng phòng dùng toạ độ khách sạn |
| Vé, combo, golf Vinpearl | API không có toạ độ. Nhà cung cấp của vé chính là nơi dùng vé (VinWonders Nha Trang…) → `collectors/venues.csv` |
| Điểm tham quan | trip.com |
| Vé máy bay | sân bay đến, dữ liệu OurAirports trong `collectors/geo.py` |

### Toạ độ nghi sai

API Vinpearl có toạ độ sai. `normalise.py` đánh dấu những toạ độ này và không dùng chúng khi ghép trùng. Nếu khách sạn có
bản booking.com/agoda thì lấy toạ độ bên đó (ghi lý do vào `locationNote`); nếu không thì giữ và ghi `locationWarning`.

- **Trùng toạ độ (≤ 30 m) với khách sạn Vinpearl khác địa chỉ.** Vinpearl Empire Nha Trang (Lê Thánh Tôn, trong thành
  phố) trùng khít Vinpearl Luxury Nha Trang trên đảo Hòn Tre. Vinpearl Resort Nha Trang trùng Vinpearl Resort & Spa
  Nha Trang Bay, và trùng luôn điểm "Hòn Tre" trên trip.com, tức chỉ là toạ độ chung của cả đảo.
- **Cách tâm điểm đến xa hơn bán kính trong `geo.py`** (mặc định 40 km). Vinpearl Hà Tĩnh cách thành phố Hà Tĩnh 34 km
  (bán kính Hà Tĩnh là 30 km).

Muốn sửa tay toạ độ của bất kỳ sản phẩm nào: thêm dòng `sourceRef,latitude,longitude,note` vào
`collectors/location_overrides.csv`, rồi chạy lại `normalise.py`. Toạ độ sửa tay thắng mọi nguồn.

### Địa điểm dùng vé Vinpearl: `collectors/venues.csv`

Bảng này có 23 địa điểm (VinWonders, Safari, Grand World, Aquafield, các sân golf…). Vé được khớp địa điểm theo mã nhà
cung cấp; không có mã thì theo alias trong tên vé, ví dụ `[Vinpearl Golf Nha Trang] …`. Nếu vé khớp qua nhà cung cấp mà
điểm đến lệch với điểm đến của địa điểm, vé nhận điểm đến của địa điểm (giá trị cũ giữ ở `attributes.originalDestination`).
Lý do là tỉnh trong API hay sai: Vinpearl Golf Léman ở Củ Chi (TP.HCM) bị ghi Hải Phòng, vé Grand World Hà Nội bị tính
thành Phú Quốc.

`python crawl.py venues` điền toạ độ cho các dòng chưa có. Thứ tự tìm: điểm tham quan trip.com đã crawl, rồi
OpenStreetMap (qua Photon). Kết quả chỉ được nhận khi chứa đủ mọi từ của tên cần tìm và nằm trong bán kính điểm đến; kết
quả là trạm xe buýt hay con đường mang tên địa điểm thì bị loại. Chạy ngày 15/09/2026, 17/23 địa điểm tự tìm được toạ độ,
6 địa điểm cần duyệt tay.

| status | Nghĩa | normalise dùng? |
|---|---|---|
| `ok` | đã kiểm tra bằng mắt; script không bao giờ ghi đè | có |
| `auto` | tự tìm được, qua kiểm tra | có |
| `review` | không tìm thấy hoặc không qua kiểm tra; `note` ghi lý do, toạ độ là kết quả đã bị loại | không |

Cách duyệt:

1. Mở `data/map/can-kiem-tra.csv` (hoặc thẳng `collectors/venues.csv`), bấm link ở cột `googleMapsUrl` / `mapUrl` để xem ghim.
2. Ghim sai hoặc chưa có: tìm đúng vị trí trên bản đồ, điền `latitude`, `longitude` (độ thập phân), đặt `source=manual`,
   `status=ok`. Ghim đúng: chỉ cần đổi `status=ok`.
3. Chạy lại `python normalise.py`.

Nên sửa CSV bằng VS Code, LibreOffice hoặc Google Sheets (lưu UTF-8); Excel có thể làm hỏng dấu tiếng Việt. Muốn thêm
địa điểm thì thêm dòng có `key, name, destination`, `suppliers` hoặc `aliases`, `queries`. Nhà cung cấp mới xuất hiện
trong dữ liệu Vinpearl sẽ được `crawl.py venues` tự thêm dòng.

### Đưa lên Google Maps: `data/map/`

Mỗi địa điểm là một ghim: hạng phòng gộp vào ghim khách sạn, vé/combo gộp vào ghim địa điểm, vé máy bay gộp vào ghim
sân bay đến.

| File | Dùng cho |
|---|---|
| `mymaps-khach-san.csv`, `mymaps-vui-choi.csv`, `mymaps-san-bay.csv` | Google My Maps, mỗi file là một lớp. My Maps không nhận file quá 2.000 dòng, nên lớp lớn được tách thành `-2`, `-3`… |
| `places.geojson` | web app (Maps JavaScript API); mỗi ghim có danh sách `items` gồm productId, tên, giá |
| `can-kiem-tra.csv` | các vị trí cần xem bằng mắt |

Các cột CSV: `name`, `latitude`, `longitude`, `category`, `destination`, `description` (tóm tắt số phòng/vé, giá từ),
`products`, `priceFromVnd`, `available`, `starRating`, `url`, `imageUrl`, `locationSource`, `locationPrecision`,
`warning`, `googleMapsUrl`, `placeKey`.

Import vào Google My Maps:

1. Vào [mymaps.google.com](https://mymaps.google.com), tạo bản đồ mới.
2. Dưới lớp đầu tiên, bấm **Import** (Nhập) và chọn `mymaps-khach-san.csv`.
3. Cột vị trí chọn `latitude` và `longitude`; cột tiêu đề chọn `name`.
4. Thêm lớp mới, lặp lại với `mymaps-vui-choi.csv` và `mymaps-san-bay.csv`. Có thể tô màu ghim theo cột `category`
   hoặc `warning` để thấy ngay ghim đáng ngờ.

Web app:

```js
map.data.loadGeoJson("places.geojson");   // GeoJSON ghi [kinh độ, vĩ độ]
map.data.addListener("click", (e) => console.log(e.feature.getProperty("name"), e.feature.getProperty("items")));
```

## Kiểm tra trước khi coi là xong tuần 1

1. Mở `data/stats.md`, xem bảng **Đối chiếu handbook §3** (số sản phẩm, số điểm đến, đủ loại, tỷ lệ tiếng Việt, có giá)
   và bảng điểm đến × loại sản phẩm.
2. Đọc tay 15 mẫu cuối `stats.md`.
3. Xem `dedup_report.csv`.
4. Sản phẩm Vinpearl ngoài 15 điểm đến (Bắc Ninh, Tây Ninh…) vẫn được giữ và đánh dấu *(ngoài kế hoạch)* trong bảng.
5. Xem mục **Vị trí (toạ độ)** trong `stats.md` và duyệt `data/map/can-kiem-tra.csv`.
6. Xem `data/quality_review.csv`: danh sách thiếu giá, mô tả, toạ độ, cảnh báo vị trí và ngôn ngữ cần đọc lại.
   File này được tạo mới mỗi lần normalise; chỉnh sửa báo cáo không làm thay đổi catalog.

### Áp dụng bản sửa chất lượng vào dữ liệu đã crawl

```bash
conda activate vsf
cd src/data_collection
python crawl.py reparse agoda-hotels && python normalise.py
python crawl.py status
cat data/stats.md
```

`reparse` đọc lại HTML trong `data/raw/`, giữ ngày lấy giá đã lưu và ghi lại dữ liệu trung gian;
`normalise.py` xuất lại catalog. Các lệnh trên không tải lại website. Nên sao lưu `data/interim/` và các file
catalog trước khi áp dụng bản sửa parser mới; bản sửa ngày 16/09/2026 đã có bản sao trong `data/backups/`.

- Mô tả Agoda thiếu JSON-LD được lấy từ phần `property-short-description` trên chính trang đã lưu.
- `collectors/destination_overrides.csv` lưu các điểm đến du lịch đã đối chiếu theo `sourceRef`, kèm bằng chứng.
  Khi áp dụng, catalog giữ `originalDestination`, `destinationSource`, `destinationEvidence` để truy nguồn.
  Không suy điểm đến từ một tên đường trùng tên địa danh ở tỉnh khác.
- Căn hộ/condotel cùng toà nhà cần đạt ngưỡng giống tên như các khách sạn khác; khoảng cách gần không đủ để gộp.
- Nhãn `[Ưu Đãi Người ...]` là đối tượng hưởng ưu đãi, không phải địa điểm sử dụng vé.
- Giá hoặc toạ độ chưa xác minh vẫn để thiếu/cần kiểm tra; `available` chưa phải xác nhận còn phòng/vé hiện tại.

Kiểm tra hồi quy offline: `python -m unittest discover -s tests -t . -v`.

### Nạp catalog vào DDL chính thức

Catalog runtime đặt tại `src/data_collection/data/products.jsonl`; thư mục `data/` bị Git bỏ qua nên snapshot dữ liệu không đi vào lịch sử của repository này. Từ thư mục `src/`, chạy:

```bash
export SEED_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vota
export INSIDER_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/insider
python -m data_collection.seed --as-of 2026-09-23 --seed 42 --reset
```

Pipeline parse combo, chuẩn hoá cửa sổ đặt chỗ, sinh lịch sử CDP/app/Insider rồi nạp hai database bằng transaction. Vector không nằm trong PostgreSQL; sau khi seed, chạy `make index-vectors` ở repository root để chỉ embed text mới/đã đổi và đồng bộ collection `Product` của Weaviate. `purchase` thiếu `event_group_id` khoảng 3% là edge case cố ý và vẫn được giữ lại.

Dữ liệu mô phỏng cho demo (`docs/prd/data-model.md` §3.1, chốt 09/10/2026): hạng phòng cho khách sạn chưa có phòng (`demo:room:*`),
tuyến chiều ngược (`demo:reverse:*`) + vé phủ ngày (`demo:fill:*`), sản phẩm cho mọi thành phần combo + `price_share` (`demo:combo:*`).
Mọi đường nạp catalog (seed, `--catalog-only`, job fresh) tự chạy `seed/demo_data.py` sau vé Thương gia mô phỏng; chạy tay khi cần
(cả bốn bước trong một transaction, `--dry-run` chạy rồi ROLLBACK). Mỗi bước chỉ ghi dòng của mình, chạy lại không đổi gì; tắt bằng
`SIMULATED_ROOMS=0` / `SIMULATED_FILL_FLIGHTS=0` / `SIMULATED_COMBO_ITEMS=0` thì khoá các dòng đó, không xoá. Từng bước có CLI riêng
(`--dry-run` chỉ đọc), `combo_components --report` ghi quyết định từng thành phần ra JSON:

```bash
python -m data_collection.seed.demo_data --database-url-env SEED_DATABASE_URL [--as-of YYYY-MM-DD] [--dry-run]
python -m data_collection.seed.combo_components --database-url-env SEED_DATABASE_URL --dry-run --report combo_report.json
```

Chạy kiểm tra từ repository root:

```bash
psql "$SEED_DATABASE_URL" -f db/verify.sql
psql "$INSIDER_DATABASE_URL" -f db/verify_insider.sql
```

## Tuỳ chọn hay dùng

| Lệnh | Tuỳ chọn | Ý nghĩa |
|---|---|---|
| mọi lệnh crawl | `--destinations`, `--per-destination` | đổi kế hoạch |
| | `--fast` | nhanh hơn (booking.com); agoda tự bỏ qua |
| | `--headless` | không mở cửa sổ (mất giá booking.com và vé Vinpearl) |
| | `--delay 5`, `--concurrency 2` | tốc độ |
| | `--rediscover` | tìm URL lại sau khi đổi kế hoạch |
| | `--limit N`, `--discover-only` | chạy thử |
| `vinpearl` / `handbook` | `--price-dates 30,14,60` | các ngày hỏi giá phòng Vinpearl (số ngày từ hôm nay hoặc `YYYY-MM-DD`) |
| | `--tour-limit N` | chỉ lấy chi tiết N vé/tour (chạy thử) |
| `booking-hotels`, `agoda-hotels` | `--checkin 2026-10-15 --nights 1 --adults 2` | ngày lấy giá (mặc định hôm nay + 30) |
| `booking-hotels` | `--all-vietnam` | thêm toàn bộ ~34.000 chỗ ở VN (ngoài handbook, vài ngày) |
| `venues` | `--refresh` | tìm lại cả dòng `auto`/`review` (dòng `ok` luôn giữ nguyên) |
| | `--only vinwonders-cua-hoi,hon-tam` | chỉ các địa điểm này |
| | `--offline` | không gọi mạng: chỉ dùng trip.com đã crawl và cache |
| `normalise.py` | `--no-plan` | giữ mọi thứ đã crawl, không lọc theo kế hoạch |
| | `--rooms-per-hotel 3`, `--flights-per-route 5` | số phòng OTA / chuyến bay cụ thể giữ lại |
| | `--vietnamese-only`, `--min-description 80` | lọc chất lượng mô tả |
| | `--keep-member-variants` | giữ nguyên từng bản giá thành viên của vé Vinpearl (`[VIN33 - Gold]`…); mặc định gộp về một sản phẩm |
| | `--keep-unsellable` | giữ cả sản phẩm không có giá mà nguồn không cung cấp được; mặc định loại bỏ |
| | `--usd-vnd 26300` | tỷ giá khi nguồn không trả VND |

Nguồn bị chặn (mã thoát 75) đã lưu tiến độ: chạy lại đúng lệnh sau vài giờ để cào tiếp; trong job mới dùng nút
"Cào lại nguồn này" trên monitor hoặc `./local_crawl.sh run resume <mã lượt> crawl <nguồn>`.

## Khi có sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `Chưa cài trình duyệt cho Playwright` | `playwright install chromium` |
| Log báo "Bị chặn … dừng" | nghỉ vài giờ, chạy lại cùng lệnh; cân nhắc `--delay 6` |
| Cửa sổ đứng ở "Chờ một chút…" | bấm xác minh trong cửa sổ đó |
| booking.com không có giá | đang `--headless`, hoặc hết phòng ngày đó → `--checkin` khác rồi `retry-failed` |
| `Nguồn … đang được một tiến trình khác chạy` | mỗi nguồn chỉ một tiến trình; đợi tiến trình kia xong |
| Sửa parser xong | `python crawl.py reparse <nguồn>` rồi `python normalise.py` |
| Vé Vinpearl không có toạ độ | xem `data/map/can-kiem-tra.csv`: địa điểm đang `review`, hoặc vé chưa khớp địa điểm nào |
| Ghim khách sạn sai chỗ | thêm dòng vào `collectors/location_overrides.csv` |
| Log báo bản ghi Vinpearl chưa có `supplierCode` | dữ liệu crawl trước khi có trường này: `python crawl.py reparse vinpearl` (đọc cache, không tải lại; chạy ngày khác ngày crawl vẫn dùng đúng các ngày giá đã cache) |
| `crawl.py venues` lỗi mạng / Photon trả 429 | chạy lại sau; truy vấn đã có kết quả được lưu trong `raw/geocode/` |
| Catalog lệch khỏi 2.000–5.000 | chỉnh `--per-destination` hoặc `--destinations` rồi `--rediscover` |

## Dữ liệu cá nhân và pháp lý

- Theo handbook: chỉ lấy dữ liệu sản phẩm. Review, tên và ảnh đại diện người đánh giá, trích dẫn review
  ("điểm nổi bật" của agoda) bị xoá khỏi HTML/JSON **trước khi ghi đĩa**. Chỉ giữ điểm trung bình và số lượt đánh giá.
- Vinpearl là dữ liệu của chính công ty; nếu dùng lâu dài nên xin đội kỹ thuật Vinpearl quyền truy cập API.
- Điều khoản của booking.com và agoda.com không cho phép thu thập tự động. Dữ liệu chỉ dùng nội bộ cho demo thực tập,
  không phân phối lại.
- Không ghi gì vào CDP hay Insider production.
- Toạ độ từ OpenStreetMap theo giấy phép ODbL: khi hiển thị hay chia sẻ bản đồ, ghi "© OpenStreetMap contributors".
  Trang Photon cho phép dùng API cho dự án nếu dùng vừa phải; script lưu cache mỗi truy vấn và gửi cách nhau ≥ 1 giây.
  robots.txt của photon.komoot.io chặn crawler trang web, còn đây là gọi API nên không kiểm tra robots.
- Toạ độ sân bay từ OurAirports (public domain).
- Không lấy toạ độ từ Google Geocoding/Places API để lưu vào catalog: điều khoản Google Maps Platform chỉ cho lưu tạm
  lat/lng tối đa 30 ngày. Link Google Maps trong các file CSV chỉ để mở xem.

<!-- seed-report:start -->
### Snapshot seed gần nhất — `2026-09-30`

- Nguồn catalog: `src/data_collection/data/snapshots/2026-09-30/products.jsonl` — SHA-256 `07134fc2c5e50c28f63fefdcb02fef5699e75ee19a7e2364c29e05d336918235`.
- Seed `42`: 12,515 products · 2,000 profiles · 7,130 events · 307 combo items.
- Search units: 3,183; vector nằm ngoài PostgreSQL và được index sang Weaviate bằng `make index-vectors`.
- Insider clone: 2,000 profiles · 4,169 events · 19,522 channel events.
- Purchase thiếu `event_group_id` là edge case được sinh có chủ đích khoảng 3%; không xoá purchase.
<!-- seed-report:end -->

### Vé thương gia và index thiếu quota

`crawl.py trip-flights` mặc định lấy thêm báo giá BUSINESS từ UI Trip.com cho 6 tuyến demo, ngày bay hiện tại +14 ngày, tối đa 8 thẻ mỗi tuyến. Luồng này chạy cùng worker Trip của `daily.py` và bước Trip Flights trong lượt `fresh_catalog full`; chế độ `fresh_catalog daily` vẫn chỉ làm mới khách sạn như trước. Collector yêu cầu Chromium, giữ ngày bay thật, số hiệu chuyến, cabin, giá và điều kiện thanh toán cùng nguồn. Không thấy cabin/giá hợp lệ thì bỏ bản ghi và báo nguồn chưa hoàn tất, không sinh vé giả.

Cách cấu hình tuyến/ngày, nhập gói 43 vé thật và xử lý index pending: [hướng dẫn vé thương gia và quota](../../docs/guide/ve-thuong-gia-va-index-cho.md).
