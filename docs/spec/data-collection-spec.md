# Data Collection Spec — V-OTA Vinpearl RecSys (Week 1)

> Spec để sinh code ở local. Bám theo §3, §6, §13, §16 của *Building a Travel Recommendation Product — V-OTA Internship Handbook v3*.
> Phạm vi: **workstream Data, Week 1**. Không bao gồm backend Java, search, web.
> Ngôn ngữ code: **Python** (handbook: Python chỉ dùng cho data collection + evaluation).

---

## 0. Mục tiêu & Definition of Done

Kết thúc Week 1 phải có:

1. PostgreSQL chứa **2.000–5.000 products** thật, trải **10–15 destinations**, taxonomy `hotel | flight | combo | attraction | golf`.
2. Toàn bộ raw response đã **cache xuống đĩa trước khi parse** (re-parse không cần fetch lại).
3. Pipeline **resumable**: một trang lỗi không giết cả run.
4. Products đã **normalize + deduplicate** giữa các nguồn.
5. `data-collection/README.md` cho phép người khác tái dựng dataset mà không cần đọc code.
6. Seeded customer histories: events gom thành **trips** qua `event_group_id`.
7. Demo thứ Sáu: đếm được số product theo category / destination, tên tiếng Việt hiển thị đúng, và show được 1 customer có events gom thành 1 trip.

**Checkpoint thứ Tư:** chưa có dữ liệu dùng được → dừng crawl, chuyển sang Amadeus / public dataset (§9). Mất cả tuần ở đây là mất recommendation engine — tức là mất dự án.

---

## 1. Nguồn dữ liệu & thứ tự ưu tiên

| # | Nguồn | Lấy gì | Ưu tiên | Thời lượng |
|---|---|---|---|---|
| 1 | **vinpearl.com** | Hotel/resort, vé VinWonders, golf, combo — mô tả tiếng Việt do chính công ty viết | **Start here** | Mon–Tue |
| 2 | booking.com | Breadth accommodation VN, attributes có cấu trúc, phân loại nhất quán | High | Wed |
| 3 | agoda.com | Coverage domestic VN thường tốt hơn site global | High | Wed |
| 4 | vn.trip.com | **Flight** + attraction (bắt buộc cho cross-category Week 3), thêm hotel | Medium | Thu |

Lý do vinpearl.com đi đầu: mô tả tiếng Việt là **input embedding tốt nhất**, sản phẩm là thứ stakeholder nhận ra khi demo, và không có rào anti-bot. Có catalog chạy được trước khi đụng phần khó.

**Quy tắc ứng xử với 3 OTA:** đọc `robots.txt`, rate-limit chặt, chạy chậm. Nếu bị chặn → **không tìm cách vượt anti-bot**, chuyển sang fallback ở §9. Một lần bị block tốn nhiều thời gian hơn toàn bộ thời gian tiết kiệm được khi chạy nhanh.

---

## 2. Kiến trúc pipeline

```
discover → fetch → cache(raw) → parse → staging → normalize → dedup → load(products)
                      │                     │
                      └─ đĩa: data/raw/     └─ Postgres: products_staging
```

Sáu lệnh rời nhau, mỗi lệnh chạy lại được độc lập:

```bash
python -m cli discover  --source vinpearl
python -m cli fetch     --source vinpearl --concurrency 2
python -m cli parse     --source vinpearl [--reparse]
python -m cli normalize
python -m cli dedup
python -m cli load
python -m cli seed-histories --users 500
python -m cli report          # số liệu cho demo thứ Sáu
```

Nguyên tắc: **fetch không bao giờ parse**, **parse không bao giờ fetch**. Parser sai là chuyện chắc chắn xảy ra — khi đó chỉ chạy lại `parse --reparse`.

---

## 3. Repo layout

```
vota-recsys/
├── docker-compose.yml
├── .env.example
└── data-collection/
    ├── README.md               # mỗi field lấy từ đâu — bắt buộc
    ├── pyproject.toml
    ├── config.yaml             # rate limit, quote_context, destinations
    ├── cli.py
    ├── db.py                   # engine, session, helpers
    ├── models.py               # SQLAlchemy models
    ├── cache.py                # ghi/đọc raw response xuống đĩa
    ├── collectors/
    │   ├── base.py             # BaseCollector (§5)
    │   ├── vinpearl.py
    │   ├── booking.py
    │   ├── agoda.py
    │   ├── trip.py
    │   └── amadeus.py          # fallback
    ├── normalise.py
    ├── dedup.py
    ├── seed_histories.py
    ├── migrations/
    │   ├── 001_raw_and_staging.sql
    │   ├── 002_cdp_clone.sql
    │   └── 003_pgvector.sql    # chạy sau khi chốt model Week 2
    └── data/
        └── raw/<source>/<yyyy-mm-dd>/<sha256>.html.gz
```

---

## 4. Database schema

### 4.1 Tầng crawl (`001_raw_and_staging.sql`)

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE crawl_runs (
    id              UUID PRIMARY KEY,
    source          TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running',  -- running|done|failed
    stats           JSONB       NOT NULL DEFAULT '{}'
);

-- hàng đợi resumable: discover ghi vào đây, fetch tiêu thụ
CREATE TABLE crawl_targets (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    url_hash        TEXT        NOT NULL,
    page_type       TEXT        NOT NULL,       -- list|detail|price|room
    quote_ctx       TEXT,                       -- NULL với trang không phụ thuộc ngày
    status          TEXT        NOT NULL DEFAULT 'pending', -- pending|fetched|parsed|failed|skipped
    attempts        INT         NOT NULL DEFAULT 0,
    last_error      TEXT,
    priority        INT         NOT NULL DEFAULT 100,
    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, url_hash, quote_ctx)
);
CREATE INDEX ON crawl_targets (source, status, priority);

CREATE TABLE raw_pages (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID        REFERENCES crawl_runs(id),
    target_id       BIGINT      REFERENCES crawl_targets(id),
    source          TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    http_status     INT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_path    TEXT        NOT NULL,       -- data/raw/... (.html.gz | .json.gz)
    content_sha256  TEXT        NOT NULL,
    content_type    TEXT,
    quote_ctx       TEXT,
    meta            JSONB       NOT NULL DEFAULT '{}'
);
CREATE INDEX ON raw_pages (source, fetched_at);

-- 1 row / (source, source_ref) — output của parse, chưa normalize
CREATE TABLE products_staging (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT        NOT NULL,
    source_ref      TEXT        NOT NULL,       -- 'vinpearl:VPNT-DLX-OCV'
    raw_page_id     BIGINT      REFERENCES raw_pages(id),
    parser_version  TEXT        NOT NULL,
    payload         JSONB       NOT NULL,       -- field thô, tên field giữ như nguồn
    parsed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_ref, parser_version)
);
```

### 4.2 CDP clone (`002_cdp_clone.sql`)

> Mirror CDP của V-OTA **field for field**. Chỗ nào không chắc thì **hỏi, đừng tự đặt** — field không tồn tại ở upstream là cái bẫy cho người tích hợp sau này. Ghi danh sách field cần xác nhận vào `docs/decisions/cdp-schema-questions.md` và hỏi trong Week 1.

```sql
CREATE TABLE products (
    product_id      UUID PRIMARY KEY,
    name            TEXT        NOT NULL,
    taxonomy        TEXT        NOT NULL CHECK (taxonomy IN
                    ('hotel','flight','combo','attraction','golf')),
    destination     TEXT        NOT NULL,
    description     TEXT,
    attributes      JSONB       NOT NULL DEFAULT '{}',
    unit_price      NUMERIC(14,2),
    currency        CHAR(3)     NOT NULL DEFAULT 'VND',
    available       BOOLEAN     NOT NULL DEFAULT true,
    available_from  DATE,
    available_to    DATE,
    image_url       TEXT,
    source_ref      TEXT        NOT NULL,
    -- cột hỗ trợ, không thuộc contract CDP:
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    images          JSONB       NOT NULL DEFAULT '[]',
    quality_score   REAL,                       -- §7
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON products (taxonomy, destination);
CREATE INDEX ON products USING gin (attributes);
CREATE INDEX ON products USING gin (name gin_trgm_ops);

-- mapping dedup: nhiều bản ghi nguồn → 1 product
CREATE TABLE product_sources (
    product_id      UUID        REFERENCES products(product_id) ON DELETE CASCADE,
    source          TEXT        NOT NULL,
    source_ref      TEXT        NOT NULL,
    is_primary      BOOLEAN     NOT NULL DEFAULT false,
    match_score     REAL,
    PRIMARY KEY (source, source_ref)
);

CREATE TABLE profiles (
    cdp_user_id                 TEXT PRIMARY KEY,
    lifecycle_stage             TEXT,     -- new|active|dormant|churned
    days_since_last_booking     INT,
    lifetime_order_count        INT NOT NULL DEFAULT 0,
    vinclub_tier                TEXT,
    purchased_verticals         TEXT[],
    home_city                   TEXT,
    last_destination            TEXT,
    gdpr_optin                  BOOLEAN NOT NULL DEFAULT true,
    email_optin                 BOOLEAN NOT NULL DEFAULT true,
    sms_optin                   BOOLEAN NOT NULL DEFAULT true,
    push_optin                  BOOLEAN NOT NULL DEFAULT true,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    cdp_user_id     TEXT        NOT NULL REFERENCES profiles(cdp_user_id),
    event_name      TEXT        NOT NULL,  -- purchase|add_to_cart|product_view|search
    timestamp       TIMESTAMPTZ NOT NULL,
    product_id      UUID,                  -- cố tình KHÔNG có FK: phải có event trỏ vào product đã xoá
    taxonomy        TEXT,
    event_group_id  TEXT,                  -- gom 1 trip — Week 3 cần cột này
    quantity        INT,
    unit_price      NUMERIC(14,2),
    using_date      DATE,
    payload         JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX ON events (cdp_user_id, timestamp DESC);
CREATE INDEX ON events (event_group_id);

-- demo only
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    cdp_user_id     TEXT NOT NULL REFERENCES profiles(cdp_user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bookings (
    id              BIGSERIAL PRIMARY KEY,
    cdp_user_id     TEXT NOT NULL,
    event_group_id  TEXT NOT NULL,
    product_id      UUID NOT NULL,
    quantity        INT  NOT NULL DEFAULT 1,
    unit_price      NUMERIC(14,2),
    using_date      DATE,
    reference_no    TEXT UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.3 pgvector (`003_pgvector.sql`) — chạy sau khi chốt model ở Week 2

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE product_vectors (
    product_id      UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
    model_version   TEXT NOT NULL,
    embedding       vector(768),   -- 768 = multilingual-e5-base; 384 nếu chọn MiniLM-L12
    indexed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> **Dimension nằm trong schema.** Đổi model sau = re-index toàn bộ. Không chạy migration này trong Week 1.

---

## 5. Field spec

### 5.1 Core — mọi product đều phải có

| Field | Type | Bắt buộc | Ghi chú |
|---|---|---|---|
| `productId` | UUID | ✅ | sinh ở bước `load` |
| `name` | text | ✅ | **giữ nguyên tiếng Việt, không cắt, không viết hoa lại** |
| `description` | text | ✅ (hotel/attraction/combo) | **full text, không truncate** — đây là thứ model đọc |
| `taxonomy` | enum | ✅ | `hotel\|flight\|combo\|attraction\|golf` |
| `destination` | text | ✅ | chuẩn hoá theo danh sách §6.1 |
| `attributes` | jsonb | ✅ | theo taxonomy, §5.2 |
| `unitPrice` | numeric | ⬜ | kèm `price_raw` trong staging |
| `currency` | char(3) | ✅ | quy về VND ở normalize |
| `available` / `availableFrom` / `availableTo` | bool/date | ✅ | |
| `imageUrl` + `images[]` | text | ✅ | **lấy bản kích thước lớn nhất** |
| `sourceRef` | text | ✅ | `<source>:<id gốc>` |
| `latitude` / `longitude` | float | ⬜ | cần cho dedup + itinerary Week 4 |

### 5.2 Attributes theo taxonomy

**hotel / resort**
```
starRating, roomType, bedType, maxOccupancy, sizeSqm, view (ocean|city|garden|pool),
amenities[], breakfastIncluded, freeCancellation, cancellationPolicy,
checkIn, checkOut, address, brand, aggregateRating, reviewCount,
familyFriendly, privatePool, beachfront, petFriendly, hasSpa, hasKidsClub
```

**attraction / vé VinWonders**
```
ticketType (adult|child|senior), duration, openingHours, includedServices[],
heightRestrictionCm, ageRestriction, poiName, indoorOutdoor, bestFor[]
```
> `openingHours` + `duration` là thứ Week 4 cần để dựng lịch trình hợp lý. Crawl luôn từ Week 1, đừng để quay lại lấy bổ sung.

**flight (trip.com)**
```
carrier, flightNo, originIata, destinationIata, departTime, arriveTime,
durationMin, stops, cabinClass, baggageAllowanceKg, fareType, refundable
```

**combo**
```
components[] ({taxonomy, name, quantity}), nights, minPax,
validFrom, validTo, blackoutDates[], transferIncluded
```

**golf**
```
courseName, holes, par, teeTimeSlots[], caddieFeeIncluded,
weekdayPrice, weekendPrice, buggyIncluded
```

### 5.3 Field phục vụ dedup

`name_normalized`, `latitude/longitude`, `address`, `phone`, `starRating`, `brand`.

### 5.4 KHÔNG crawl

Nội dung review, tên người review, mọi dữ liệu về khách du lịch cá nhân. Không hữu ích cho embedding (review mô tả **chuyến đi**, không mô tả **sản phẩm**) và kéo theo nghĩa vụ bảo vệ dữ liệu. **Chỉ lấy `aggregateRating` + `reviewCount`.**

### 5.5 `quote_context` — đừng bỏ sót

Giá và tình trạng phòng phụ thuộc tham số tìm kiếm, nên phải cố định 1 bộ chuẩn để giá giữa các nguồn so sánh được:

```yaml
quote_contexts:
  base:  { checkin_offset_days: 30, nights: 1, adults: 2, rooms: 1 }   # bắt buộc
  near:  { checkin_offset_days: 7,  nights: 1, adults: 2, rooms: 1 }   # theo dõi ưu đãi
  far:   { checkin_offset_days: 90, nights: 1, adults: 2, rooms: 1 }
```

Week 1 chỉ cần `base`. `near`/`far` để dành cho phần "cập nhật trạng thái phòng và ưu đãi theo thời gian".

---

## 6. Normalize

### 6.1 Destination — danh sách chuẩn cố định

```
Nha Trang, Phú Quốc, Hạ Long, Đà Nẵng, Hội An, Nam Hội An, Hà Nội,
TP. Hồ Chí Minh, Đà Lạt, Sa Pa, Huế, Quy Nhơn, Vũng Tàu, Cần Thơ, Tây Ninh
```
Mọi alias (`Khánh Hoà`, `Cam Ranh`, `Bãi Dài` → `Nha Trang`) khai trong `config.yaml`. Product không map được → `destination = 'unknown'`, **không tự đoán**, và ghi vào report để rà tay.

### 6.2 Các rule còn lại

- **Giá**: parse số từ chuỗi (`"3.400.000đ"` → `3400000`), giữ `price_raw` trong staging; ngoại tệ quy về VND theo tỷ giá cố định trong `config.yaml` (ghi lại tỷ giá đã dùng).
- **Taxonomy**: bảng map `category nguồn → taxonomy` khai trong config, không hardcode trong parser.
- **Text**: bỏ thẻ HTML, gộp whitespace, **giữ nguyên dấu tiếng Việt**, chuẩn hoá về NFC. Không lowercase, không bỏ dấu.
- **Ảnh**: bỏ query param resize, giữ URL bản lớn nhất.

---

## 7. Dedup

Cùng một resort xuất hiện trên vinpearl + booking + agoda với tên, mô tả, giá khác nhau.

**Thuật toán (rẻ, đủ dùng):**
1. Block theo `destination`.
2. Ứng viên trùng nếu: khoảng cách toạ độ < 150 m, **hoặc** `similarity(name_normalized)` ≥ 0.82 (pg_trgm) và `starRating` lệch ≤ 1.
3. Tính `match_score`, trên ngưỡng thì gộp; trong vùng xám (0.7–0.82) ghi ra `dedup_review.csv` để rà tay.

**Thứ tự nguồn thắng theo từng field:**

| Field | Nguồn thắng |
|---|---|
| `name`, `description`, `images` | **vinpearl.com** |
| `unitPrice`, `available`, `availableFrom/To` | **OTA** (booking > agoda > trip) |
| `attributes` structured (amenities, starRating) | booking.com |
| `latitude/longitude`, `address` | nguồn nào có trước, ưu tiên OTA |
| `aggregateRating`, `reviewCount` | OTA có `reviewCount` cao nhất |

Ghi rule này vào `README.md` — handbook yêu cầu chốt sớm việc nguồn nào thắng field nào.

**`quality_score`** (0–1) để rà chất lượng: `description` ≥ 200 ký tự, có tiếng Việt thật, có ảnh, có giá, có destination hợp lệ. Product `quality_score < 0.5` không được đưa vào demo.

> Trước khi tuyên bố Week 1 xong: **đọc tay 20 mô tả ngẫu nhiên**. Mô tả generic hoặc bị cắt cụt thì semantic search ở Week 2 không chứng minh được gì và model comparison thành vô nghĩa.

---

## 8. Collector contract

```python
# collectors/base.py
@dataclass
class Target:
    url: str
    page_type: str            # list|detail|price|room
    quote_ctx: str | None = None
    priority: int = 100

@dataclass
class RawPage:
    url: str
    http_status: int
    content: bytes
    content_type: str
    quote_ctx: str | None

class BaseCollector(ABC):
    source: str
    parser_version: str
    rate_limit_rps: float
    respect_robots: bool = True

    @abstractmethod
    def discover(self) -> Iterator[Target]: ...

    @abstractmethod
    def fetch(self, target: Target) -> RawPage: ...

    @abstractmethod
    def parse(self, raw: RawPage) -> list[dict]:
        """Trả về payload thô. KHÔNG normalize ở đây."""
```

**Ràng buộc bắt buộc với runner:**
- `fetch` ghi `raw_pages` + file `.gz` xuống đĩa **trước** khi bất kỳ parse nào chạy.
- Lỗi cấp item: `attempts += 1`, `status='failed'`, ghi `last_error`, **đi tiếp**. Retry với exponential backoff, tối đa 3 lần.
- Kiểm tra `robots.txt` khi khởi động collector; disallow thì bỏ URL đó.
- `rate_limit_rps` cấu hình trong `config.yaml`, mặc định ≤ 0.5 rps/domain, concurrency ≤ 2.
- Mỗi lần sửa parser thì tăng `parser_version` → `parse --reparse` sinh row mới trong staging, không đè bản cũ.

---

## 9. Ghi chú theo nguồn

**vinpearl.com** — bắt đầu từ sitemap. Lấy trang khách sạn/resort (mỗi room type là 1 product), trang vé VinWonders, golf, combo. Mô tả tiếng Việt lấy đủ: intro, mô tả phòng, tiện ích, điểm nổi bật. Đây là nguồn quyết định chất lượng dataset.

**booking.com / agoda.com** — đi theo trang danh sách của từng destination trong §6.1, rồi vào trang chi tiết. Nhiều dữ liệu nằm trong JSON nhúng (`__NEXT_DATA__`, JSON-LD) — parse từ đó ổn định hơn parse DOM. Chạy chậm. **Bị chặn thì dừng, không tìm cách vượt** — chuyển fallback.

**vn.trip.com** — mục tiêu chính là **flight** (các cặp HAN/SGN ↔ CXR/PQC/DAD/HPH...) và **attraction**. Hotel ở đây chỉ là bonus.

**Fallback (cũng nên dùng làm nguồn bổ sung kể cả khi crawl thuận lợi):**

| Nguồn | Được gì |
|---|---|
| Amadeus Self-Service API | 150.000+ hotel có description/rating/ảnh, + flights + activities. Free test tier, có SDK. |
| trivago RecSys 2019 dataset | dataset công khai |
| OpenStreetMap / Wikivoyage | destinations, POI, attractions cho itinerary assistant |

---

## 10. Seed customer histories (`seed_histories.py`)

Crawl cho ra **products, không cho ra customers**. Phải sinh — và sinh cho tử tế, vì dữ liệu random làm một recommender hỏng trông vẫn ổn.

| Yêu cầu | Chi tiết |
|---|---|
| **Trips, không phải events rời** | 1 trip = hotel + flight cùng ngày + vé, chung `event_group_id` |
| **1 trip = 1 destination** | nếu không, filter theo destination trông vô dụng |
| **Popularity power-law** | ~20% product chiếm ~80% booking (Zipf α≈1.2) |
| **Sparse** | phần lớn user 1–5 events/năm. Ai cũng 50 events thì cold start không bao giờ kích hoạt |
| **Life stages** | new / active / dormant 6 tháng / churned — theo `lifecycle_stage` |
| **Messy edges** | thiếu description, user opt-out, event trỏ vào product đã xoá |

Mặc định: 500 profiles, ~1.500–2.500 events. Seed thêm vài **demo account** cho Week 2: một người hay đi Nha Trang, một người lần đầu, một người dormant 6 tháng, một người trắng lịch sử.

**Sanity check bắt buộc:** popularity baseline gần 0 → dữ liệu quá random; không gì đánh bại được nó → quá tập trung.

---

## 11. Docker Compose + config

```yaml
# docker-compose.yml (phần data)
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: vota
      POSTGRES_USER: vota
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  collector:
    build: ./data-collection
    env_file: .env
    volumes: ["./data-collection/data:/app/data"]
    depends_on: [postgres]
volumes: { pgdata: }
```

`.env.example`: `POSTGRES_*`, `RATE_LIMIT_RPS`, `MAX_CONCURRENCY`, `USER_AGENT` (ghi rõ danh tính + email liên hệ), `AMADEUS_CLIENT_ID/SECRET`.

Không commit API key vào repo.

---

## 12. `data-collection/README.md` phải có

1. Mỗi field lấy từ đâu — bảng `field → source → cách trích`.
2. Rule nguồn thắng field khi dedup.
3. Tỷ giá đã dùng + ngày áp dụng.
4. `quote_context` đã crawl.
5. Lệnh chạy lại toàn bộ từ đầu.
6. Số liệu lần chạy gần nhất: product theo taxonomy, theo destination, tỉ lệ thiếu description, số cặp dedup.

---

## 13. Bẫy đã biết

| Bẫy | Xử lý |
|---|---|
| Week 1 tan vào việc crawl | Cache raw → re-parse miễn phí. Chốt chặn thứ Tư: không có data dùng được thì sang Amadeus/public dataset |
| Description generic hoặc bị cắt | Đọc tay 20 mẫu trước khi tuyên bố xong |
| Lịch sử sinh ra không có pattern | §10. Popularity baseline gần 0 nghĩa là dữ liệu sai, không phải model sai |
| Parse DOM vỡ mỗi lần site đổi layout | Ưu tiên JSON nhúng / JSON-LD |
| Tự bịa field CDP | Chỗ nào không chắc thì hỏi, ghi vào `docs/decisions/cdp-schema-questions.md` |
| Quên `event_group_id` | Week 3 không làm được cross-category. Có từ ngày đầu |
| Đụng anti-bot rồi cố vượt | Dừng, chuyển fallback. Không đáng đánh đổi cả tuần |

---

## 14. Thứ tự implement (gợi ý chạy ở local)

1. `models.py` + `migrations/001`, `002` → `docker compose up -d postgres` → chạy migration.
2. `cache.py` + runner `fetch` + `BaseCollector` (chưa có collector thật) — test bằng 1 URL tĩnh.
3. `collectors/vinpearl.py`: `discover` → `fetch` → `parse`. Chạy full, kiểm tra `products_staging`.
4. `normalise.py` + `load` → có `products` đầu tiên. **Đọc tay 20 mô tả.**
5. `collectors/booking.py`, `agoda.py`, `trip.py` — cùng contract.
6. `dedup.py` + `product_sources`.
7. `seed_histories.py` + sanity check.
8. `cli report` + viết `README.md`.

Bước 1–4 xong trước trưa thứ Tư. Chưa xong thì kích hoạt fallback.
