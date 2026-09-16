# data-collection — V-OTA Vinpearl RecSys, Week 1

Pipeline thu thập kho hàng du lịch thật và nạp vào một PostgreSQL có schema
phản chiếu CDP của V-OTA.

> **Mục tiêu của file này (spec §0.5):** một người khác **tái dựng được toàn bộ
> dataset mà không cần đọc code**. Nếu bạn phải mở một file `.py` để biết chạy
> gì tiếp, file này thiếu — hãy bổ sung.

Bốn mục dưới đây (bảng field→nguồn, rule nguồn thắng field, tỷ giá,
quote_context) và bảng số liệu ở §6 được **sinh tự động** bởi
`python -m cli report --update-readme`. Đừng sửa tay phần nằm giữa các marker
`<!-- BEGIN:x -->` / `<!-- END:x -->` — lần chạy sau sẽ ghi đè.

---

## 0. Tình trạng hiện tại — ĐỌC TRƯỚC

| Nguồn | Trạng thái | Đã kiểm chứng thế nào |
|---|---|---|
| **vinpearl.com** | ❌ Không crawl được | `robots.txt` trả **403** — không đọc được file xin phép. Xem §7. |
| **booking.com** | ❌ Bị chặn (đã latch) | `robots.txt` **cho phép** `/searchresults`, nhưng site trả **HTTP 202** + trang `noscript`: *"we need to verify that you're not a robot"*. |
| **agoda.com** | ❌ Bị chặn (đã latch) | URL search bị **redirect về trang chủ**, trả 200 / 218 KB nhưng **0 ký tự text** — JS-only shell. |
| **vn.trip.com** | ❌ robots disallow | `robots.txt` **cấm** các path `/flights/...` với UA của ta. Đã `skipped`, **không gửi request nào** ngoài `robots.txt`. |
| **amadeus** | ⚠️ Cần API key | Code xong. Điền `AMADEUS_*` vào `.env` rồi `amadeus-probe`. |
| **manual** | ✅ **Đang chạy** | 30 product (18 golf + 12 combo) từ `data/manual/*.yaml`. |
| **osm** | 🔒 Tắt, cần quyết định | Overpass `robots.txt` disallow `/api/`. Xem §7. |

**Cả 3 OTA đều đã thử thật, mỗi site đúng 1 request, và cả 3 đều không dùng
được.** Không site nào bị retry: booking và agoda đã có row trong `source_state`
nên lần `fetch` sau exit 4 ngay mà không gửi request; trip bị chặn ở tầng
robots nên chưa bao giờ được fetch. Spec §1 cấm tìm cách vượt, nên đây là điểm dừng.

**Hệ quả:** hiện có **30 product / 12 destination / 2 trong 5 taxonomy**, còn xa
DoD §0.1. Chốt chặn thứ Tư của spec §0 **đã kích hoạt ngay thứ Hai**, và giờ thì
chắc chắn: crawl web không phải đường đi. Nguồn duy nhất còn lại có thể đạt
2.000 product là **Amadeus** — cần API key (§7).

Pipeline thì đã chạy end-to-end và idempotent — thiếu **nguồn dữ liệu**, không
thiếu code.

---

## 1. Yêu cầu môi trường

| Thứ | Ghi chú |
|---|---|
| **Docker Desktop** | Chỉ để chạy PostgreSQL. Phải đang chạy trước mọi lệnh. |
| **Python ≥ 3.11** | Đã test trên 3.13.14. |
| **uv** | Quản lý venv + lock. `.python-version` ghim 3.13. |
| `psql` | **Không cần.** Máy dev không có `psql` trên PATH; dùng `docker compose exec postgres psql`. |

**Windows — hai việc bắt buộc:**

1. `.env` phải có `PYTHONUTF8=1`. Không có nó, encoding mặc định là `cp1252` và
   mọi output tiếng Việt sẽ `UnicodeEncodeError` ngay khi stdout bị pipe hoặc
   redirect (`python -m cli report > report.txt`).
2. Trong PowerShell, trước khi redirect output ra file:
   ```powershell
   [Console]::OutputEncoding = $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
   ```
   PowerShell 5.1 tự re-encode pipe, nên `python ... | Out-File` làm hỏng dấu
   tiếng Việt **dù** Python đã ghi đúng UTF-8.

**Cổng PostgreSQL:** `POSTGRES_PORT` trong `.env` mặc định **5433**, không phải
5432 — 5432 thường đã bị một project khác chiếm. Trong compose network cổng luôn
là 5432; chỉ mapping ra host thay đổi, và `DATABASE_URL` phải khớp.

**`.env` nằm ở đâu:** phía Python tìm lần lượt
`data-collection/.env` → `vota-recsys/.env` → **thư mục gốc repo**, lấy file đầu
tiên thấy được (`config.ENV_SEARCH_PATHS`), nên đặt ở chỗ nào trong ba chỗ đó
cũng chạy. **`docker compose` thì không**: nó chỉ đọc `.env` nằm cạnh
`docker-compose.yml`. Nếu `.env` của bạn ở gốc repo, mọi lệnh compose phải thêm
`--env-file`:

```bash
docker compose --env-file ../.env up -d postgres
```

Không thêm thì compose báo `POSTGRES_PASSWORD is missing a value` trong khi mọi
lệnh `python -m cli` vẫn chạy bình thường — hai triệu chứng đó đi cùng nhau rất
khó đoán, nên nếu gặp thì kiểm tra chỗ này trước.

---

## 2. Chạy lần đầu

```bash
# .env: copy .env.example rồi sửa. Đặt ở gốc repo, ở vota-recsys/, hoặc ở
# data-collection/ đều được với phía Python — xem §1 về ràng buộc của compose.
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
# sửa .env: POSTGRES_PASSWORD, USER_AGENT (email liên hệ THẬT), AMADEUS_* nếu có

cd vota-recsys
docker compose --env-file ../.env up -d postgres   # bỏ --env-file nếu .env nằm cạnh compose

cd data-collection
uv sync --extra dev
uv run pytest -q                       # 127 test, offline, không cần DB
uv run python -m cli migrate --list    # 003_pgvector PHẢI hiện "deferred"
uv run python -m cli migrate
uv run python -m cli config-check
```

`migrate` áp dụng **001, 002, 004, 005** và **cố tình bỏ 003**. Spec §4.3:
dimension của vector nằm trong schema, nên chạy 003 bây giờ là chốt cứng lựa
chọn embedding model trước khi Week 2 benchmark. Danh sách áp dụng là tường minh
trong `db.APPLY_ORDER`, không phải glob — một runner glob theo thứ tự chữ cái sẽ
chạy 003 trên đường tới 004.

---

## 3. Kiến trúc pipeline

```
discover → fetch → cache(raw) → parse → staging → normalize → dedup → load
              │                    │                                     │
              └─ đĩa: data/raw/    └─ products_staging        products + product_sources
```

Hai invariant được **enforce**, không phải chỉ mong đợi:

- **`fetch` không bao giờ parse, `parse` không bao giờ fetch** (spec §2).
  `parse` nhận một `NoNetFetcher` raise trên mọi request, nên một parser muốn
  fetch thêm sẽ lỗi ngay thay vì âm thầm biến `parse --reparse` thành một lần
  crawl thứ hai.
- **bytes xuống đĩa → row `raw_pages` → status của target**, đúng thứ tự đó
  (spec §0.2). Crash giữa bước 1 và 2 để lại một file không ai tham chiếu, và
  `cli adopt-orphans` nhận nó về. Thứ tự ngược lại để lại một row trỏ vào hư
  không — nhìn như đã fetch mà không có gì.

Lỗi cấp item là chuyện bình thường (spec §8): `attempts += 1`, ghi
`last_error`, đi tiếp, **exit code vẫn 0**. Chỉ block hoặc lỗi config mới dừng run.

### Tại sao mỗi command tách rời

Mỗi lệnh chạy lại độc lập được. Vòng lặp sửa lỗi hàng ngày là:

```bash
uv run python -m cli report                 # thấy destination nào chưa map
# sửa config.yaml → destinations[].aliases
uv run python -m cli normalize --force
uv run python -m cli dedup
uv run python -m cli load
uv run python -m cli report
```

Không cần crawl lại. Đó là toàn bộ lý do cache raw tồn tại.

---

## 4. Các lệnh

### 8 lệnh của spec §2 (contract)

| Lệnh | Việc |
|---|---|
| `discover --source X` | Sinh `crawl_targets`. `--dry-run` in ra không ghi, `--dump-unmatched` in URL không khớp `url_patterns` nào. |
| `fetch --source X` | Fetch target pending. `--concurrency ≤ 2`, `--run-id` để resume run bị Ctrl-C. |
| `parse --source X` | Đọc cache → `products_staging`. `--reparse` đọc lại mọi trang đã cache. |
| `normalize` | `products_staging` → `products_normalised` (spec §6). `--force` để normalise lại. |
| `dedup` | Gom cluster xuyên nguồn (spec §7). Vùng xám ra `data/reports/dedup_review.csv`. |
| `load` | Merge cluster → `products` + `product_sources`. Idempotent. |
| `seed-histories` | Sinh profiles/events/users/bookings (spec §10). **Chạy SAU `load` cuối.** |
| `report` | Số liệu demo thứ Sáu + DoD. `--strict` fail khi DoD chưa đạt. |

### Lệnh hỗ trợ

| Lệnh | Việc |
|---|---|
| `migrate [--list] [--verify]` | Áp dụng migration; `--verify` so `models.py` với schema thật |
| `robots-check --source X` | Chỉ fetch `robots.txt` và in được/không được crawl gì |
| `unblock --source X --reason "..."` | Xoá latch chặn nguồn. **Bắt buộc có lý do người viết**, không có timer |
| `adopt-orphans` | Nhận lại file cache có row DB bị mất giữa crawl |
| `sanity-check [--k N]` | Baseline độ phổ biến trên events đã seed (spec §10) |
| `sample-descriptions --n 20 --mark --by "tên"` | **Đọc tay 20 mô tả** (spec §7, §13 — bắt buộc) |
| `amadeus-probe` | ~20 request: test tier có bao nhiêu inventory VN |
| `save-fixture --raw-page-id N` | Copy một trang đã cache vào `tests/fixtures/` |
| `config-check` | Load + validate `config.yaml`, in setting politeness thực tế |

### Exit code

Một bảng duy nhất trong `exitcodes.py`. Script fallback branch trên các số này:

`0` ok · `1` lỗi không lường · `2` sai tham số · `3` config/DB · **`4` bị chặn
anti-bot** · `5` robots.txt không đọc được · `6` hết budget · `7` gate fail
(DoD/sanity) · `130` Ctrl-C

```powershell
uv run python -m cli fetch --source booking
if ($LASTEXITCODE -eq 4) { uv run python -m cli fetch --source amadeus }
```

---

## 5. Field lấy từ đâu (spec §12 mục 1)

Bảng này **sinh từ `payload->'_prov'`** — map mà mọi parser ghi kèm payload —
nên nó mô tả việc parser thật sự đã làm, không phải việc ai đó nhớ ra để ghi lại.

<!-- BEGIN:extraction-table -->
| source | field | cách trích | số row |
|---|---|---|---|
| manual | amenities | manual:curated | 18 |
| manual | components | manual:curated | 12 |
| manual | course_name | manual:curated | 18 |
| manual | curated_at | 2026-09-15 | 30 |
| manual | curated_by | data workstream (Week 1) | 30 |
| manual | description | manual:curated | 30 |
| manual | destination | manual:curated | 30 |
| manual | holes | manual:curated | 18 |
| manual | latitude | manual:curated | 18 |
| manual | longitude | manual:curated | 18 |
| manual | min_pax | manual:curated | 12 |
| manual | name | manual:curated | 30 |
| manual | nights | manual:curated | 12 |
| manual | note | Curate tay từ thông tin công khai về các sân golf đang hoạt động tại các destination trong §6.1. Tên, địa điểm và mô tả đã kiểm chứng; số hố/par để null ở những sân chưa xác nhận lại. Giá để null có chủ ý — xem nguyên tắc 2. | 18 |
| manual | note | Combo template curate tay để taxonomy `combo` có dữ liệu dùng được trong Week 1 khi vinpearl.com không crawl được. Thành phần gói và số đêm là cấu trúc điển hình của loại sản phẩm này tại từng destination; giá và điều kiện cụ thể chưa xác minh và để null. Không dùng các dòng này cho bất kỳ nội dung nào hiển thị giá cho người dùng thật. | 12 |
| manual | par | manual:curated | 18 |
| manual | price_raw | manual:curated | 30 |
| manual | _source | manual YAML file:///H:/study/VIN20K/VSF/Travel-Recommendation-Product/vota-recsys/data-collection/data/manual/golf.yaml | 18 |
| manual | _source | manual YAML file:///H:/study/VIN20K/VSF/Travel-Recommendation-Product/vota-recsys/data-collection/data/manual/combo.yaml | 12 |
| manual | transfer_included | manual:curated | 12 |
<!-- END:extraction-table -->

### Nguồn nào thắng field nào khi dedup (spec §12 mục 2)

Sinh từ `config.merge` — đúng dữ liệu mà merge đọc — nên rule ghi ở đây không
thể lệch với rule chạy thật.

<!-- BEGIN:precedence -->
| loại | field | nguồn thắng |
|---|---|---|
| column | name | vinpearl > manual > booking > agoda > trip > osm > amadeus |
| column | description | vinpearl > manual > booking > agoda > trip > osm > amadeus; Vietnamese text preferred |
| column | taxonomy | vinpearl > manual > booking > agoda > trip > osm > amadeus |
| column | destination | vinpearl > manual > booking > agoda > trip > osm > amadeus |
| column | unit_price | booking > agoda > trip > amadeus (then vinpearl > manual > booking > agoda > trip > osm > amadeus) |
| column | currency | constant 'VND' |
| column | available | booking > agoda > trip > amadeus |
| column | available_from | booking > agoda > trip > amadeus |
| column | available_to | booking > agoda > trip > amadeus |
| column | image_url | first element of images |
| column | images | vinpearl > manual > booking > agoda > trip > osm > amadeus |
| column | latitude | booking > agoda > trip > amadeus (then vinpearl > manual > booking > agoda > trip > osm > amadeus) |
| column | longitude | booking > agoda > trip > amadeus (then vinpearl > manual > booking > agoda > trip > osm > amadeus) |
| column | source_ref | primary member (winner of name) |
| attribute | starRating | booking > agoda > vinpearl > trip > amadeus |
| attribute | amenities | booking > agoda > vinpearl > trip > amadeus |
| attribute | address | booking > agoda > trip > amadeus (then vinpearl > manual > booking > agoda > trip > osm > amadeus) |
| attribute | brand | vinpearl > manual > booking > agoda > trip > osm > amadeus |
| attribute | aggregateRating | highest reviewCount among booking, agoda, trip, amadeus |
| attribute | reviewCount | highest reviewCount among booking, agoda, trip, amadeus |
| attribute | descriptionEn | amadeus > booking > agoda > trip |
<!-- END:precedence -->

### Tỷ giá đã dùng + ngày áp dụng (spec §12 mục 3)

<!-- BEGIN:fx -->
- **Ngày áp dụng (`as_of`)**: `2026-09-15`
- **Nguồn tỷ giá**: Vietcombank ty gia trung tam, ghi tay - khong goi API trong Week 1
- **Base**: `VND`

| tiền tệ | tỷ giá sang VND |
|---|---|
| AUD | 17300 |
| CNY | 3660 |
| EUR | 28400 |
| GBP | 33100 |
| JPY | 176 |
| KRW | 19.1 |
| SGD | 19450 |
| THB | 745 |
| USD | 26150 |
| VND | 1 |
<!-- END:fx -->

### quote_context đã crawl (spec §12 mục 4)

`quote_contexts.anchor_date` trong `config.yaml` là **bắt buộc** và phải commit.
Nếu để trống, `discover` exit 3.

Lý do: nếu check-in = `hôm nay + 30`, thì `discover` thứ Hai và `discover` thứ Tư
sinh ra `quote_ctx` khác nhau. `crawl_targets` UNIQUE trên
`(source, url_hash, quote_ctx)` → mọi target bị insert lại thành pending → crawl
lại toàn bộ ở 0.5 rps. Và giá giữa các nguồn crawl ở hai ngày khác nhau không
còn so sánh được — tức là mất đúng mục đích mà §5.5 tồn tại vì nó.

<!-- BEGIN:quote-contexts -->
- **`anchor_date`**: `2026-09-15`

| quote_ctx | check-in sớm nhất | check-out muộn nhất | số trang |
|---|---|---|---|
| base | 2026-10-15 | 2026-10-16 | 2 |
<!-- END:quote-contexts -->

---

## 6. Chạy lại toàn bộ từ đầu (spec §12 mục 5)

Danh sách này sinh từ command registry và các source đang `enabled` trong
config (`python -m cli report --runbook`), nên nó không lệch được khỏi những gì
pipeline thật sự chạy được.

<!-- BEGIN:runbook -->
```bash
# 0. prerequisites: Docker Desktop running, uv installed, .env filled in
cd vota-recsys
docker compose up -d postgres
cd data-collection
uv sync
uv run python -m cli migrate            # applies 001, 002, 004, 005 (003 deferred)

# 1. catalogue
uv run python -m cli robots-check --source agoda
uv run python -m cli discover     --source agoda
uv run python -m cli fetch        --source agoda --concurrency 2
uv run python -m cli parse        --source agoda
uv run python -m cli robots-check --source amadeus
uv run python -m cli discover     --source amadeus
uv run python -m cli fetch        --source amadeus --concurrency 2
uv run python -m cli parse        --source amadeus
uv run python -m cli robots-check --source booking
uv run python -m cli discover     --source booking
uv run python -m cli fetch        --source booking --concurrency 2
uv run python -m cli parse        --source booking
uv run python -m cli robots-check --source manual
uv run python -m cli discover     --source manual
uv run python -m cli fetch        --source manual --concurrency 2
uv run python -m cli parse        --source manual
uv run python -m cli robots-check --source trip
uv run python -m cli discover     --source trip
uv run python -m cli fetch        --source trip --concurrency 2
uv run python -m cli parse        --source trip
uv run python -m cli robots-check --source vinpearl
uv run python -m cli discover     --source vinpearl
uv run python -m cli fetch        --source vinpearl --concurrency 2
uv run python -m cli parse        --source vinpearl

# 2. normalise, dedup, load
uv run python -m cli normalize
uv run python -m cli dedup
uv run python -m cli load

# 3. mandatory manual check (spec sections 7, 13)
uv run python -m cli sample-descriptions --n 20 --mark --by '<your name>' --verdict ok

# 4. customer histories — AFTER the final load, so product ids are stable
uv run python -m cli seed-histories --users 500 --seed 42
uv run python -m cli sanity-check

# 5. report
uv run python -m cli report
uv run python -m cli report --strict   # Friday: fails on unmet DoD checks
```
<!-- END:runbook -->

### Số liệu lần chạy gần nhất (spec §12 mục 6)

<!-- BEGIN:last-run-stats -->
_Cập nhật 2026-09-15T15:38:24+00:00 — config `6ea6faedaf6e`_

**Product theo taxonomy**

| taxonomy | product | đạt ngưỡng demo | thiếu description | quality TB |
|---|---|---|---|---|
| combo | 12 | 12 | 0 | 0.700 |
| golf | 18 | 18 | 0 | 0.600 |

**Product theo destination**

| destination | product | đạt ngưỡng demo | số taxonomy |
|---|---|---|---|
| Đà Nẵng | 5 | 5 | 2 |
| Nha Trang | 4 | 4 | 2 |
| Đà Lạt | 3 | 3 | 2 |
| Phú Quốc | 3 | 3 | 2 |
| Hạ Long | 2 | 2 | 2 |
| Hà Nội | 2 | 2 | 1 |
| Huế | 2 | 2 | 2 |
| Nam Hội An | 2 | 2 | 2 |
| Quy Nhơn | 2 | 2 | 2 |
| TP. Hồ Chí Minh | 2 | 2 | 1 |
| Vũng Tàu | 2 | 2 | 1 |
| Sa Pa | 1 | 1 | 1 |

**Số liệu khác**

- Tỉ lệ thiếu description: **0.0%**
- Cặp dedup: `{'review': 1}` — 0 cluster nhiều nguồn
- Destination không map được: **0**
- Profiles / events / trips: 504 / 2696 / 672
<!-- END:last-run-stats -->

---

## 7. Nguồn dữ liệu — tình trạng thật và quyết định cần ra

### vinpearl.com trả 403 ở robots.txt

`cli robots-check --source vinpearl`:

```
DISALLOW  https://vinpearl.com  (robots.txt not readable, status=403)
```

**403, không phải 404.** Đó là khác biệt quan trọng: 404 nghĩa là site không
disallow gì (và ta được crawl); 403 nghĩa là **không đọc được chính cái file
dùng để xin phép** — gần như chắc chắn là một rule WAF/CDN từ chối client không
phải browser.

Spec §1 dự đoán nguồn này là nguồn dễ ("không có rào anti-bot"). Thực tế khác.

**Pipeline xử lý đúng:** không request gì ngoài `robots.txt`, báo đúng nguyên
nhân, exit 5, in ra các fallback. Nó **không** thử user-agent kiểu browser —
việc đó là vượt rào, đúng thứ §1 cấm, và code có test chặn
(`test_no_browser_user_agent_anywhere_in_the_tree`).

**Cần ai đó quyết định:**
- Vinpearl là công ty của chính mình → hỏi nội bộ xem có được whitelist IP/UA,
  hoặc lấy data feed/API nội bộ. Đây là đường tốt nhất và nó là việc tổ chức,
  không phải việc kỹ thuật.
- Nếu có xác nhận bằng văn bản là được crawl, ghi vào `docs/decisions/` rồi mới
  đổi `sources.vinpearl.respect_robots`.

### Amadeus cần API key — đây là đường ra nhanh nhất

```bash
# 1. https://developers.amadeus.com/register → tạo app "Self-Service"
# 2. điền AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET vào vota-recsys/.env
# 3. đo xem test tier có gì cho Việt Nam (~20 request):
uv run python -m cli amadeus-probe
```

`amadeus-probe` in số hotel/activity khả dụng **theo từng destination** và
extrapolate ra tổng. Con số đó — không phải vinpearl — quyết định tuần này:
vinpearl có ~45–50 property VN (vài trăm product ở grain room-type), ba OTA dự
kiến ra 0, nên phần lớn 2.000 product phải đến từ Amadeus.

Mô tả của Amadeus là **tiếng Anh**. `description_policy: en_to_attributes` đưa
nó vào `attributes.descriptionEn` và để `products.description` NULL. Để text
tiếng Anh vào cột description sẽ làm số "thiếu description" trông đẹp trong khi
làm nhiễu corpus tiếng Việt mà so sánh model Week 2 dựa vào.

### OSM/Overpass đang tắt — cần một quyết định có ghi chép

`cli robots-check --source osm`:

```
DISALLOW  https://overpass-api.de/api/interpreter
DISALLOW  https://vi.wikipedia.org/w/api.php
```

`robots.txt` của Overpass đúng nghĩa là `Disallow: /api/`, và MediaWiki disallow
`/w/`. Cả hai nhắm vào **search engine indexer**, không nhắm vào API client —
đây là API có tài liệu, có usage policy riêng, và Wikimedia còn xuất bản trang
API etiquette dành cho truy cập bằng chương trình. Nên có lập luận tốt rằng
`robots.txt` không phải văn bản điều chỉnh ở đây, mà usage policy mới là.

**Lập luận đó không phải việc để code tự quyết.** Spec §1 nói đọc `robots.txt`
và nếu bị chặn thì đổi nguồn. Vì vậy nguồn này để `enabled: false` cho tới khi
có người quyết định và ghi vào `docs/decisions/`. Cách bật:

1. Đọc <https://operations.osmfoundation.org/policies/api/> và
   <https://www.mediawiki.org/wiki/API:Etiquette>.
2. Ghi quyết định + tên người quyết vào `docs/decisions/`.
3. Trong `config.yaml`: `enabled: true` và `robots_policy: api_terms`.

`robots_policy: api_terms` là **cách duy nhất** để gọi các endpoint đó. Nó tồn
tại để ngoại lệ là tường minh, theo từng source, và grep được — thay vì một
`respect_robots: false` chung cũng sẽ bao che cho việc crawl thật.

Nếu bật, OSM cho: **tên tiếng Việt thật**, toạ độ thật, và `opening_hours` —
đúng field mà spec §5.2 nói Week 4 cần và đừng để phải quay lại lấy. Mô tả thì
thường không có; khi POI có tag `wikipedia`, `discover` sinh thêm target lấy
đoạn mở đầu Wikipedia tiếng Việt (mô tả thật của chính điểm đó). Không có thì
`description` để **NULL** và `quality_score` phản ánh đúng — tự sinh câu "X là
một điểm tham quan ở Y" chính là loại mô tả generic mà §7 bắt đọc tay 20 mẫu để
phát hiện.

### Dữ liệu curate tay: `data/manual/*.yaml`

Tồn tại vì DoD §0.1 cần đủ 5 taxonomy, và truy vết từng taxonomy thì **golf** và
**combo** chỉ có duy nhất một nguồn (vinpearl) — nguồn đang 403. Amadeus không
có endpoint sân golf hay package.

Đây là nguồn trung thực, không phải lối tắt: `source='manual'`, có trong bảng
provenance §5 như mọi nguồn khác, và `source_priority` **thấp nhất** nên khi nào
crawl được nguồn thật thì nguồn đó thắng mọi field.

**Giá để `null` ở tất cả các mục — có chủ ý.** Spec §6.1 "không tự đoán" áp dụng
cho giá y như destination. Một con số bịa sẽ chảy thẳng vào
`products.unit_price` và trông y như giá crawl thật. Thà để trống:
`quality_score` nhìn thấy được chỗ trống, không nhìn thấy được số sai. Có test
enforce việc này (`test_manual_yaml_invents_no_prices`).

### trivago RecSys 2019 — từ chối, có lý do

Spec §9 liệt kê nó. Không dùng: đó là dữ liệu click-log, **không có product text
tiếng Việt**, nên nó không giải quyết được đúng thứ dataset này cần. Ghi lại ở
đây để quyết định là có chép, không phải bị bỏ qua.

---

## 8. Chất lượng dữ liệu

### `quality_score` (spec §7)

Trọng số trong `config.quality.weights`: description ≥ 200 ký tự (0.30), có
tiếng Việt thật (0.25), có ảnh (0.15), có giá (0.15), destination hợp lệ (0.15).
Ngưỡng demo `0.5` nằm **đúng một chỗ**: `config.quality.demo_threshold`.

Component không áp dụng được cho một taxonomy thì bị **bỏ khỏi mẫu số**, không
cho điểm 1.0. Cho 1.0 sẽ tặng một chuyến bay 0.55 điểm trước khi đo bất kỳ tín
hiệu thật nào, nên một flight không giá, không ảnh, `destination='unknown'` vẫn
vượt ngưỡng 0.5 — ngược hẳn mục đích của ngưỡng.

### Đọc tay 20 mô tả — bắt buộc

```bash
uv run python -m cli sample-descriptions --n 20 --mark --by "tên bạn" --verdict ok
```

Spec §7 và §13: mô tả generic hoặc bị cắt cụt thì semantic search Week 2 không
demo được và so sánh model thành vô nghĩa. `--mark` ghi vào
`description_reviews` để `report --strict` kiểm tra được — đó là khác biệt giữa
một **gate** và một **ý định**.

Review chỉ được tính nếu nó xảy ra **sau** lần `load` gần nhất. Vì vậy `load`
không được đụng `updated_at` khi không có gì đổi — nếu đụng, gate này fail vĩnh
viễn vào đúng thứ Sáu.

### Cái không thu thập (spec §5.4)

Không nội dung review, không tên người review, không dữ liệu khách du lịch cá
nhân. Chỉ `aggregateRating` + `reviewCount`.

Đây là enforce ở mức trích xuất, không phải lọc sau: `extract.jsonld_pick` áp
allowlist **trước** khi payload được tạo. JSON-LD của trang khách sạn thật
thường nhúng `review: [{author: {...}, reviewBody: ...}]` ngay trong object
`Hotel`, nên giữ blob thô vừa vi phạm §5.4 vừa làm validator PII từ chối mọi
trang hotel — biến nguồn tốt nhất thành 0 sản phẩm.

---

## 9. Customer histories đã seed (spec §10)

```bash
uv run python -m cli seed-histories --users 500 --seed 42 --truncate
uv run python -m cli sanity-check --k 20
```

**Chạy SAU lần `load` cuối.** `events.product_id` cố tình không có FK (spec
§4.2), nên `load` sau khi seed sẽ để lại event trỏ vào product không còn tồn
tại. `load` giữ `product_id` ổn định qua `product_sources` nên việc này an toàn
hơn là nghe, nhưng thứ tự vẫn là thứ tự.

Dữ liệu có cấu trúc thật, không random — spec §10 cảnh báo dữ liệu random làm
một recommender hỏng trông vẫn ổn:

- **Trip, không phải event rời.** 1 `event_group_id` = 1 trip = 1 destination.
- **Power law theo từng destination.** Hotel Nha Trang phổ biến trong các trip
  Nha Trang, không phổ biến toàn cục — nếu toàn cục thì baseline
  most-popular-in-destination trùng most-popular và việc so hai cái là vô nghĩa.
- **Thưa.** Phần lớn user 1–5 event/năm. Ai cũng 50 event thì cold start không
  bao giờ kích hoạt.
- **Profile derive từ event**, không sample độc lập. Một profile ghi
  `lifetime_order_count = 7` cạnh 3 event là loại bất nhất làm feature trông
  hỏng khi lỗi nằm ở dữ liệu.
- **Rìa lộn xộn có chủ ý:** event trỏ vào product đã xoá, profile không có
  event, một phần nhỏ opt-out.

Mọi thứ derive từ `--seed` và `--now`, **kể cả `created_at`** — dựa vào
`DEFAULT now()` sẽ khiến hai lần chạy khác nhau by construction và không gate
idempotency nào pass được.

### Sanity check bắt buộc

Spec §10: baseline độ phổ biến gần 0 → dữ liệu quá random; không gì đánh bại
được nó → quá tập trung.

Với catalogue hiện tại (26 product), `sanity-check` báo **INCONCLUSIVE** ở
`--k 20` và nói rõ đó là vấn đề **kích thước catalogue**, không phải vấn đề
seeding: ở 26 product, một recommender random đã đạt Recall@20 ≈ 0.77 vì list
phủ 77% catalogue. Ở `--k 3`, cấu trúc hiện ra đúng như mong đợi:

| baseline | Recall@3 |
|---|---|
| random | 0.13 |
| most-popular | 0.54 |
| most-popular-in-destination | 0.98 |

Popularity đánh bại random rõ rệt, và per-destination đánh bại global — đúng
hình mà §10 muốn. Khi catalogue đủ lớn, chạy lại ở `--k 20`.

### Demo account (Week 2)

Bốn persona trong `config.seed.demo_accounts`: hay đi Nha Trang, lần đầu, ngủ
đông 6 tháng, trắng lịch sử. Password hash bằng **bcrypt** để
`BCryptPasswordEncoder` của Spring Security verify trực tiếp ở Week 2.

---

## 10. Layout

```
data-collection/
├── cli.py                  # python -m cli — toàn bộ command
├── config.py config.yaml   # config.yaml là authority cho rate limit/alias/taxonomy/precedence
├── db.py models.py         # .sql migration là source of truth, models.py chỉ để query
├── cache.py                # data/raw/<source>/<date>/<sha256>.<ext>.gz
├── exitcodes.py runtime.py ids.py
├── collectors/
│   ├── base.py             # contract spec §8 + registry + PAYLOAD_CONTRACT
│   ├── net.py              # robots, rate limit, retry, BlockDetector, NoNetFetcher
│   ├── extract.py          # jsonld_pick (allowlist), state_blob, sitemap, spec_pairs
│   ├── runner.py           # discover/fetch/parse runner
│   ├── ota.py              # base dùng chung cho booking/agoda/trip
│   └── vinpearl.py booking.py agoda.py trip.py amadeus.py manual.py osm.py
├── normalise.py quality.py merge.py load.py dedup.py report.py
├── seed_histories.py sanity.py
├── migrations/001…005.sql  # 003 DEFERRED
├── data/manual/*.yaml      # dữ liệu curate tay (tracked)
└── tests/                  # 127 test, offline
```

**Bảng phụ vs CDP.** `001`/`002` là DDL verbatim từ spec §4.1/§4.2 và **không
được sửa** — §4.2 là mirror field-for-field của CDP. Mọi bảng phụ mà pipeline
cần nằm ở `004`/`005` và có ghi rõ ở đầu file rằng chúng là crawl layer, sẽ bị
drop khi thay bằng `CdpClient` production.

`name_normalized` và các field dedup §5.3 (`latitude/longitude`, `address`,
`phone`, `star_rating`, `brand`) sống ở `products_normalised`, **không** thêm vào
`products`.

Câu hỏi còn mở về schema CDP: [`../docs/decisions/cdp-schema-questions.md`](../docs/decisions/cdp-schema-questions.md)
— mỗi câu kèm **giá trị đang giả định**, để code vẫn chạy khi chưa có trả lời và
để giả định đó nhìn thấy được thay vì nằm im trong parser.

---

## 11. Khi có gì sai

| Triệu chứng | Xem |
|---|---|
| `discover` ra 0 target | `discover --dry-run --dump-unmatched` → sửa `sources.X.url_patterns`, không sửa parser |
| exit 5 | `robots.txt` không đọc được. Không đổi UA. Xem §7. |
| exit 4 | Bị chặn anti-bot; nguồn đã latch trong `source_state`. Chuyển fallback. Xoá latch: `unblock` kèm lý do. |
| Product "biến mất" giữa các stage | `report` in `normalise_rejects` theo lý do. Không có row nào mất im lặng. |
| `destination = 'unknown'` | `report` in mẫu + `destination_raw`. Thêm alias vào config rồi `normalize --force`. |
| `UnicodeEncodeError` | Thiếu `PYTHONUTF8=1`, hoặc PowerShell đang re-encode pipe. Xem §1. |
| `POSTGRES_PASSWORD is missing a value` (chỉ ở compose) | `.env` không nằm cạnh `docker-compose.yml`. Thêm `--env-file ../.env`. Xem §1. |
| `USER_AGENT still has a placeholder contact address` | `.env` không được nạp, hoặc `USER_AGENT` chưa sửa. Lỗi in ra đúng các đường dẫn đã tìm. Crawl với email giả là điều spec §11 không cho. |
| Ctrl-C giữa `fetch` | Run ghi `status='failed'`, `interrupted: true`. Chạy lại `fetch` tiếp tục; hoặc `--run-id <id>` để cộng dồn số liệu vào run cũ. |
| File cache không có row DB | `adopt-orphans` (crash giữa ghi file và ghi row) |
| `load` báo `rejected` | Cluster không project được thành row hợp lệ — lý do ở `normalise_rejects` reason `load` |

---

## 12. Gate trước khi tuyên bố Week 1 xong

```bash
uv run python -m cli report --strict
```

Chỉ enforce đúng những gì spec §0 nói — không có ngưỡng tự bịa. Các check đếm
(2.000–5.000 product, 10–15 destination, đủ 5 taxonomy) **WARN** từ thứ Hai đến
thứ Năm và chỉ **FAIL** dưới `--strict`: một gate đỏ suốt tuần sẽ bị bỏ qua vào
đúng thứ Năm, là lúc nó quan trọng nhất.

Taxonomy có **0 product** bị báo là FAIL, không phải một dòng trống — dòng trống
là thứ không ai để ý.

**Gate cuối, không tự động được:** một người **không viết pipeline** clone repo
vào thư mục trắng và đi tới `products` có data **chỉ bằng file này**. Đó mới là
DoD §0.5, không phải "README tồn tại". Đặt việc đó vào thứ Năm, có tên người cụ thể.
