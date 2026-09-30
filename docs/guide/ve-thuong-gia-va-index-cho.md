# Vé thương gia thật và index đang chờ quota

Phục vụ FR-CAT-01, FR-CAT-03, FR-SRC-02 và NFR-REL-01. Giữ Cohere `embed-multilingual-v3.0` và Weaviate `Product`; không đổi model hoặc schema.

## Cào cùng luồng hiện có

`crawl.py trip-flights` thực hiện SEO rồi mở tìm kiếm Thương gia trên UI Trip.com bằng Chromium. Mặc định lấy HAN–SGN, SGN–HAN, HAN–DAD, SGN–DAD, SGN–PQC, HAN–CXR nếu tuyến nằm trong interim đã discovery; ngày hiện tại +14 ngày theo giờ Việt Nam; tối đa 8 thẻ/tuyến. Worker Trip của `daily.py` và nguồn Trip Flights của `fresh_catalog full` tự gọi bước này. `fresh_catalog daily` vẫn chỉ làm mới giá khách sạn; lịch full sẽ cập nhật vé.

```bash
cd src/data_collection
python crawl.py trip-flights --refresh --routes HAN-SGN,SGN-HAN --business-offsets 7,14,21 --business-max-flights 8
python normalise.py
```

`--no-business` tắt phần browser. Các offset phải nằm trong 0..29. Collector chỉ nhận giá VND của một người lớn, chuyến thẳng, cabin Thương Gia được hiển thị trên cùng thẻ giá; ngày/chuyến/tuyến phải khớp URL chi tiết. Lưu raw proof và `businessQuotes` trong interim; normalizer xuất đủ 13 trường, cabin `BUSINESS`, ngày bay cố định và `priceObservedAt`. Không dùng giá economy nhân hệ số. Giá có điều kiện thanh toán được ghi trong description (gói hiện tại dùng MoMo). Browser bị chặn/timeout hoặc không có quote kiểm chứng thì báo chưa hoàn tất; không coi là hết bán. Không đăng nhập, checkout hoặc giải challenge.

## Khi Agoda timeout hoặc Cohere 429

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
