# Vé thương gia thật và index đang chờ quota

Phục vụ FR-CAT-01, FR-CAT-03, FR-SRC-02 và NFR-REL-01. Lúc viết (30/09/2026) task giữ Cohere `embed-multilingual-v3.0` và Weaviate `Product`, không đổi model hoặc schema. Từ 06/10/2026 (FR-SRC-02) bước index dùng model local `intfloat/multilingual-e5-small` (384 chiều, collection `ProductE5`); Cohere chỉ còn là đường lui (`EMBED_PROVIDER=cohere` + `WEAVIATE_COLLECTION=Product`).

## Cào cùng luồng hiện có

`crawl.py trip-flights` thực hiện SEO rồi mở tìm kiếm trên UI Trip.com bằng Chromium cho hai loại giá:

- Thương gia một chiều theo ngày bay (tối đa 4 thẻ/tuyến/ngày).
- Khứ hồi, ngày về sau 3, 5 hoặc 7 ngày: mỗi lần tìm lấy 2 chuyến đi, mỗi chuyến kèm chuyến về đề xuất. Modal giá trọn
  hành trình liệt kê mọi hạng, nên một lần tìm cho cả giá Phổ thông lẫn Thương gia khứ hồi.

Mặc định 6 tuyến HAN–SGN, SGN–HAN, HAN–DAD, SGN–DAD, SGN–PQC, HAN–CXR (nếu có trong interim đã discovery), ngày bay +1..+29
theo giờ Việt Nam. **Xoay vòng:** mỗi lượt chỉ tìm tới khi hết `--fares-minutes` (mặc định 30; job fresh lấy từ cấu hình
monitor `tripFlights.fareMinutes`, 0 = tắt) và luôn dừng trước hạn giờ nguồn 3 phút. Việc chưa tìm, ngày gần nhất được làm
trước; sau đó là việc tìm lâu nhất. Trạng thái ở `<CATALOG_STATE_DIR>/trip_fares_rotation.json` (không có biến này thì
`data/state/`), nên các lượt fresh nối tiếp nhau phủ dần 30 ngày. Worker Trip của `daily.py` và nguồn Trip Flights của
`fresh_catalog full` tự gọi bước này; `fresh_catalog daily` chỉ làm mới giá khách sạn.

```bash
cd src/data_collection
python crawl.py trip-flights --refresh --routes HAN-SGN,SGN-HAN --business-offsets 7,14,21 --roundtrip-stays 3,5,7 --fares-minutes 20
python normalise.py
```

`--no-business` tắt cả phần browser; `--roundtrip-stays ""` chỉ tắt khứ hồi. Ngày bay nằm trong 0..29 (`1-29` hoặc
`7,14,21`). Collector chỉ nhận giá VND một người lớn, chuyến thẳng cả hai chiều, hạng và giá trên cùng thẻ; thẻ khứ hồi phải ghi
"Khứ hồi", ngày/chuyến/tuyến phải khớp URL chi tiết. Nhãn hạng lẫn (vd. "Thương Gia (chiều đi)") bị bỏ. Lưu raw proof,
`businessQuotes` và `roundTripQuotes` trong interim. Vé khứ hồi dùng cùng `sourceRef` với thẻ khứ hồi của trang SEO
(`trip:roundtrip:…:<hạng>`), giá tìm kiếm thắng thẻ SEO cùng mã; không có `priceValidUntil` (không bịa) và hạn cũ bị xoá khi
cập nhật. Không dùng giá economy nhân hệ số. Hình thức thanh toán và "xuất thành nhiều vé riêng" ghi trong description.

**Giới hạn đã biết (30/09/2026):** `robots.txt` của Trip cấm `/flights/showfarefirst*` và `/flights/ShowFareNext*`; Chromium
headless nhận `HTTP 432` ("whaleguard block"). Gặp 432 collector chờ 45 giây rồi thử lại một lần; vẫn 432, hoặc 403/429, thì coi là bị chặn, dừng sau 3 lần lỗi liên tiếp và báo nguồn
chưa hoàn tất; không coi là hết bán, không đăng nhập, checkout, giải challenge hay lách chống bot. Vì vậy trên VM phần này
thường không lấy được vé; 43 vé thương gia hiện có được lấy thủ công qua trình duyệt.

## Vé Thương gia mô phỏng (demo)

Không cào được thêm vé thương gia thật nên demo dùng vé mô phỏng (`docs/prd/data-model.md` §3): giá vé gốc × 2,65, tên
"(giá minh hoạ)", `attributes.simulated = true`, `sourceRef` `demo:business:<sourceRef gốc>`. Sinh sau mỗi lần nạp catalog:
seed demo luôn bật; `seed --catalog-only` (`daily.py`) và job fresh (nạp DB và bảo trì đầu lượt) **mặc định bật**. Vé Thương
gia thật cùng hành trình và ngày thắng. `SIMULATED_BUSINESS_FARES=0` → lần nạp sau khoá toàn bộ vé mô phỏng (không xoá dòng).

Trên VM: deploy bản này là đủ, không cần sửa env. Muốn có ngay, không chờ lượt cào, chạy một lần qua tunnel DB (chỉ ghi
dòng `demo:business:*`, cùng khoá ghi catalog với job):

```bash
cd src && CLOUD_SEED_DATABASE_URL=<dsn> python -m data_collection.seed.simulated_business --database-url-env CLOUD_SEED_DATABASE_URL --enable
```

Tắt hẳn: `SIMULATED_BUSINESS_FARES=0` trong env của job. Chỉ chạy `--disable` mà env chưa tắt thì lượt nạp sau bật lại.

## Khi Agoda timeout hoặc index bị 429 (Cohere)

Với model local mặc định, bước index không gọi API ngoài nên không có 429/quota; phần về 429 dưới đây chỉ áp khi chạy đường lui `EMBED_PROVIDER=cohere`.

Nguồn timeout được giữ cảnh báo và checkpoint; các nguồn độc lập tiếp tục. Nếu catalog hợp lệ đã commit, `fresh_catalog` trả `exit=0`, report vẫn `status=partial` và có `incompleteSources`. Lỗi kiểm tra dữ liệu, DB hoặc lỗi index khác 429 vẫn là lỗi thực sự; không chuyển toàn bộ lỗi thành thành công.

429 ở index (kể cả streaming) tạo `<CATALOG_STATE_DIR>/index_pending.json` với `retryAfter`, không lưu response body hay key. Sau khi adapter trả lỗi 429, bỏ vòng retry ngoài. Cooldown khởi đầu 1 giờ, tăng gấp đôi đến 24 giờ và tôn trọng `Retry-After` dài hơn. Cron `tick`/`due` chỉ thử lại riêng index khi đến hạn và `schedule.enabled=true`; lịch cào đến hạn vẫn ưu tiên. Lượt thủ công `index` cũng giữ cooldown. Khi index thành công file pending được xóa. Phần vector/text đã ghi trước đó được job embedding hiện có nhận diện để tránh gọi lại không cần thiết.

`daily.py` dùng `data/state/index_pending-<target>.json`, báo đích `partial` nhưng vẫn ghi nhận version DB và tiếp tục đích sau. Lần nạp kế tiếp thử index khi cooldown đã hết. Không có vòng daemon retry riêng cho `daily.py`.

Có key mới không làm thay đổi thời điểm retry đã lưu. Giữ file pending nếu muốn tuân thủ cooldown; không xóa cache embedding hay reset catalog chỉ để xử lý quota. Vector mới vẫn chưa tìm kiếm được cho đến khi index thành công. Giá/trạng thái DB tiếp tục được backend reload theo `CATALOG_REFRESH_SECONDS`.

## Gói vé demo và triển khai

Gói `snapshots/2026-09-30-business` gồm 43 vé, 6 tuyến, bay 15/10/2026, quan sát 30/09/2026. Gói có checksum và bằng chứng UI. Không dời ngày bay nếu nạp sau khi hết hạn.

```bash
# Tại repo root: chỉ kiểm gói, chưa kết nối DB
PYTHONPATH=src python -m data_collection.seed.release_flights --validate-only
# URL VM lấy từ file ignored; chỉ thêm ID mới, không reset/ghi đè giá đã có
PYTHONPATH=src python -m data_collection.seed.release_flights --env-file src/data_collection/.env
# Với image daily trên VM có env sẵn
IMAGE=<AR>/vota-fresh-catalog:latest ENV_FILE=/etc/vota/fresh-catalog.env /opt/vota/bin/run_daily_docker.sh import-flights
```

Import đòi 6 tuyến cha đã tồn tại; thiếu cha hoặc lỗi constraint thì rollback toàn bộ. CD không tự import: DB VM đã có 43 vé (30/09), chỉ chạy lệnh trên khi DB mới chưa có. CD của main/release-mvp-v1/v2/v3 build image `Dockerfile.fresh-catalog` (secret `GAR_FRESH_IMAGE`), cài cron fresh và khởi động lại monitor; không tự chạy lượt cào — bấm `full` trên monitor nếu cần cào ngay. Xem [hướng dẫn deploy](trien-khai-job-cao-du-lieu.md).

Task ngày 30/09 không restart VM. Key mới đã được đặt vào `.env` ở gốc repo và `src/data_collection/.env`, đều ignored và quyền 600. Người dùng chỉ có quyền DB: chưa thay `/etc/vota/fresh-catalog.env` hoặc `/etc/vota/daily.env` trên VM. Người có quyền VM cần cập nhật `COHERE_API_KEY` trong đúng env file; container hiện chạy giữ environment cũ, lần tạo job/container kế tiếp mới nhận giá trị mới.

Cập nhật theo yêu cầu tiếp ngày 30/09: DB VM đã áp migration 0001–0004, có `app.payments`. Nạp thêm 1.331 ID còn thiếu từ snapshot (loại 31 vé bị loader dời ngày), tổng 12.261 sản phẩm; giữ nguyên 43 BUSINESS và mọi sản phẩm đã có. `db/verify.sql` đạt 18/18 PASS. Chi tiết: `history/2026-09-30-sua-db-vm-migration-va-bo-sung-catalog.md`.
