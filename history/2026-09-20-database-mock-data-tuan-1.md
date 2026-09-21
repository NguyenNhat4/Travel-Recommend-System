# Database tuần 1: schema `vota` + `insider`, gộp bundle, và package mock data

- Ngày: 2026-09-20
- Tác giả: Nguyễn Hải Sơn / Claude Code
- Nhánh: data_contract
- Trạng thái: hoàn thành
- Phạm vi: data, cdp, insider, docs
- Thay thế: `2026-09-17-thiet-ke-schema-3-service.md` (phần "ba service, mỗi service một database" và "CDP clone là service HTTP")

## Mục tiêu

Người yêu cầu đã giải nén `vota-schema-bundle.zip` vào gốc repo và yêu cầu làm theo `CLAUDE.database.md`:
gộp phần hạ tầng vào repo, dựng Postgres, rồi viết `src/data_collection/seed/` sinh mock data tất định
để `db/verify.sql` và `db/verify_insider.sql` chạy được.

Chia làm ba phần, mỗi phần một commit. **Entry này viết ở phần A và được bổ sung ở phần B, C.**

- Phần A (commit này): gộp bundle, sửa tài liệu cho khớp, dựng database, kiểm tra 15 bảng + 3 view.
- Phần B: package `src/data_collection/seed/` (gen_products → seed_insider).
- Phần C: unit test, báo cáo seed, chốt trạng thái.

## File thay đổi

Phần A — đối chiếu `git status` ngày 20/09:

- `docker-compose.yml` — thêm: service `postgres` (pgvector/pgvector:pg16, db `vota`, mount `db/init`), đổi tên từ `docker-compose.db.yml` của bundle. Thêm healthcheck `pg_isready` để `up -d --wait` dùng được.
- `docker-compose.db.yml` — xóa: đã đổi tên thành `docker-compose.yml`. Repo trước đó **không có** `docker-compose.yml` ở gốc nên không có gì để "gộp vào" như README.database.md mô tả.
- `AGENTS.md` — sửa: thêm mục 6 "Database" (nội dung `CLAUDE.database.md`), thêm 2 dòng bảng §1.2 (Database, Mock data tuần 1), sửa dòng CDP clone trỏ sang mục 6, mở rộng §5 để `db/` cũng phải có entry lịch sử.
- `CLAUDE.database.md` — xóa: đã gộp vào `AGENTS.md`.
- `db/` — thêm (từ bundle): `init/00_create_insider.sql`, `init/01_vota.sql`, `init/02_insider.sql`, `init/03_roles_dev.sql`, `vota_schema.sql`, `insider_schema.sql`, `verify.sql`, `verify_insider.sql`.
- `docs/DATABASE_SCHEMA.md`, `docs/PRODUCT_SCHEMA.md` — thêm (từ bundle).
- `docs/MOCK_DATA_SPEC.md` — thêm (từ bundle) và sửa §0: connection seed/verify là `SEED_DATABASE_URL`, báo cáo ghi vào khối đánh dấu trong `src/data_collection/README.md`, và ghi rõ hai dòng verify FAIL theo thiết kế với catalog tổng hợp.
- `docs/spec/Mock-data.md` — xóa: trùng byte-for-byte với `docs/MOCK_DATA_SPEC.md` (chỉ khác CRLF), mà mọi tài liệu đều trỏ tới bản trong `docs/`.
- `docs/research/recsys-data-cleaning-embedding-strategy.md` — thêm (từ bundle).
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: banner đầu file nêu phần nào chưa áp dụng ở tuần 1; §1.5 gạch quy tắc "seed qua API"; §11 chốt nơi lưu `products`/`users`/`bookings`/`product_vectors`; §13 thêm 2 dòng quyết định 20/09.
- `src/ARCHITECTURE.md` — sửa: §3 vẽ lại sơ đồ theo hai connection và nêu `db/` + compose ở gốc; §4 chú thích lại `data_collection` và `cdp_clone`, thêm câu về thư mục hạ tầng ngoài `src/`; §7 sửa dòng CDP clone; §9 viết lại 3 gạch đầu dòng (CDP clone là schema, ngoại lệ loader/seed, nơi lưu các bảng).
- `src/cdp_clone/README.md` — sửa: banner "tuần 1 CDP clone là database" ở trên, **khôi phục toàn bộ tài liệu service** mà bundle đã xóa, đặt dưới mục "Service HTTP — tạm gác". Thêm cảnh báo bảng trong `app/infrastructure/tables.py` chưa khớp `db/init/01_vota.sql`.
- `.env.example` — sửa: giữ 7 biến database của bundle, **khôi phục** phần crawl politeness (`RATE_LIMIT_RPS`, `MAX_CONCURRENCY`, `USER_AGENT`), Amadeus và `PYTHONUTF8=1` mà bundle đã xóa; thêm ghi chú DSN thuần cho psycopg v3.
- `src/data_collection/seed/README.md` — thêm (placeholder từ bundle; phần B thay bằng bản viết tay).
- `history/2026-09-17-thiet-ke-schema-3-service.md` — sửa: thêm đúng một dòng `Bị thay thế bởi:` (mức sửa duy nhất `history/README.md` cho phép với entry cũ).

Không commit: `README.database.md`, `PROMPT_claude_code.md` (bundle ghi rõ không cần commit).

Phần B — package seed:

- `src/data_collection/seed/__init__.py` — thêm: docstring mô tả thứ tự bước và quy ước tách `build_*` / `write_*`.
- `src/data_collection/seed/__main__.py` — thêm: CLI `--as-of/--seed/--users/--products/--reset/--allow-remote-reset`, điều phối 6 bước, chặn `--reset` vào host không phải local, chặn chạy lại trên bảng đã có dữ liệu, exit code 1 khi có FAIL ngoài dự kiến.
- `src/data_collection/seed/config.py` — thêm: toàn bộ tỷ lệ, phân bố, bảng từ khoá combo, thông tin persona.
- `src/data_collection/seed/common.py` — thêm: RNG theo stream, `stable_order_key` (crc32, không dùng `hash()`), uuid5, bỏ dấu tiếng Việt, trọng số Zipf, batch insert.
- `src/data_collection/seed/gen_products.py` — thêm: sinh catalog tổng hợp 433 dòng đúng contract `SCHEMA.md` + `_validate()` chặn giá trị làm vỡ view `product_meta`.
- `src/data_collection/seed/load_products.py` — thêm: cắt cửa sổ 30 ngày, dời ngày bay vào cửa sổ, lịch `availability`, regex `nights`/`minPax`/`priceBasis`, upsert idempotent.
- `src/data_collection/seed/parse_combos.py` — thêm: tách hạng mục, nhận loại theo từ khoá, map bằng `pg_trgm` + `unaccent`, ghi `source`/`confidence`/`evidence`.
- `src/data_collection/seed/seed_histories.py` — thêm: `ProductPool` power-law, sinh chuyến, cạnh lộn xộn, và `rebuild_profiles` suy profile từ event.
- `src/data_collection/seed/seed_app.py` — thêm: lịch sử cố định của 4 persona, 54 tài khoản, đơn của P1, và bộ mã hoá radix-64 của BCrypt để salt tất định.
- `src/data_collection/seed/seed_insider.py` — thêm: partners, profiles (tập con attribute), identifiers có lịch sử, event theo TTL 90/730, phễu channel_events.
- `src/data_collection/seed/report.py` — thêm: chạy `db/verify*.sql` bằng psycopg, phân loại FAIL dự kiến, đo baseline Recall@20, ghi khối `seed-report`.
- `src/data_collection/seed/requirements.txt` — thêm: `psycopg[binary]`, `numpy`, `bcrypt`, tách khỏi requirements của crawler.
- `src/data_collection/seed/README.md` — sửa: thay placeholder của bundle bằng hướng dẫn chạy, 6 bước, tài khoản demo và danh sách ràng buộc dễ vấp.
- `src/data_collection/README.md` — sửa: thêm khối `<!-- seed-report:start/end -->` ở cuối (138 dòng, do `report.py` sinh). Sổ tay crawler 426 dòng giữ nguyên, không xoá dòng nào.
- `src/data_collection/.gitignore` — sửa: bỏ qua `products.jsonl` và `products.synthetic.jsonl` (sinh lại được từ `--seed` + `--as-of`).

Phần C — test và chốt:

- `src/data_collection/tests/test_seed.py` — thêm: 59 test `unittest` chạy offline (không cần Postgres) cho `gen_products`, cửa sổ đặt chỗ, lịch 30 ngày, regex combo, parser combo, sinh chuyến, salt BCrypt và phễu Insider.
- `src/data_collection/seed/seed_histories.py` — sửa: chốt thời điểm mua trước rồi đặt `product_view`/`add_to_cart` lùi về trước nó; purchase của các vertical trong cùng checkout cách nhau 10 giây theo thứ tự hotel → flight → attraction → golf.
- `src/data_collection/seed/gen_products.py` — sửa: miễn combo khỏi cạnh lộn xộn "mô tả ngắn".
- `src/data_collection/README.md` — sửa: khối `seed-report` cập nhật theo lần chạy cuối.

## Quyết định

- **CDP clone là schema `cdp` trong database `vota`, không phải service HTTP có PostgreSQL riêng.** Người yêu cầu chọn phương án "theo bundle + sửa tài liệu" ngày 20/09. Căn cứ: handbook §6 "one implementation now, reading locally"; tách database sẽ mất FK và view của `catalog`/`app` sang `cdp.products`, mà `catalog` vẫn phải là bảng local để search p95 < 300 ms. Ranh giới production được mô phỏng bằng **role + connection riêng** và bằng việc mọi truy cập của app đi qua port `CdpClient` — đổi sang `HttpCdpClient` là thay adapter, không sửa use case. Đã kiểm chứng ranh giới chạy thật (xem Kiểm tra).
- **Giữ nguyên code `src/cdp_clone/`.** Bundle viết README thành "Chưa viết gì ở đây" trong khi thư mục có service FastAPI + Alembic + test chạy được. Không xóa code, không xóa tài liệu; chỉ đánh dấu "tạm gác" và nêu rõ nó là nền cho `HttpCdpClient`.
- **Mục Database đặt trong `AGENTS.md`, không phải `CLAUDE.md`.** Bundle bảo gộp vào `CLAUDE.md`, nhưng `AGENTS.md` dòng 3 quy định `CLAUDE.md` chỉ import `AGENTS.md` và mọi quy tắc sửa tại `AGENTS.md`. Quy tắc repo thắng.
- **`docker-compose.db.yml` đổi tên thành `docker-compose.yml`**, không gộp: repo chưa có compose ở gốc. Thêm healthcheck vì các bước sau cần `--wait`.
- **Quy mô catalog: giữ đúng MOCK_DATA_SPEC §1b (~450 dòng, 40 property).** Người yêu cầu chọn phương án này ngày 20/09, chấp nhận hai dòng `db/verify.sql` FAIL theo thiết kế (`products = 2216`, `is_recommendable properties >= 300`) thay vì thổi quy mô tổng hợp lên 2.216 dòng để lách ngưỡng của crawl thật. Không sửa `db/*.sql`.
- **Báo cáo seed ghi vào khối `<!-- seed-report:start/end -->` trong `src/data_collection/README.md`.** Spec ghi `data-collection/README.md` (gạch nối) — thư mục đó không tồn tại trong monorepo; còn cây thư mục §1 lại trỏ vào chính file sổ tay crawler 426 dòng. Dùng khối đánh dấu để vừa đúng ý spec vừa không mất sổ tay.
- **Seed và verify chạy bằng `SEED_DATABASE_URL` (superuser).** Dòng đầu `db/verify*.sql` ghi `$DATABASE_URL` là nhầm: role `vota_app` không SELECT được `cdp.events`/`cdp.profiles` nên sẽ lỗi quyền chứ không ra FAIL. Ghi chú trong `docs/MOCK_DATA_SPEC.md` §0 thay vì sửa file .sql.
- **Khôi phục biến môi trường crawler trong `.env.example`.** `docs/spec/data-collection-spec.md` dòng 499 quy định file này phải có `RATE_LIMIT_RPS`, `MAX_CONCURRENCY`, `USER_AGENT`, `AMADEUS_*`; `PYTHONUTF8=1` là bắt buộc trên Windows để output tiếng Việt không vỡ khi pipe. Bundle ghi đè cả file nên đã mất hết. (Đã gặp đúng lỗi `UnicodeEncodeError` này khi chạy thử `gen_products` không có biến đó.)

Phần B:

- **Số chuyến/khách chuyển từ khoảng đều sang phân bố có trọng số** (`STAGE_TRIP_WEIGHTS`). Spec §4 ghi "active 1–4 · dormant 1–2 · churned 1–2"; hiểu là phân bố đều thì 2.000 khách sinh ~15.000 event, vượt xa cổng `events 6000-8000` của `db/verify.sql`. Hai con số trong cùng bộ spec mâu thuẫn nhau; `db/verify.sql` là tiêu chí nghiệm thu nên nó thắng. Giữ đúng *khoảng* (active vẫn có thể tới 4 chuyến), nghiêng trọng số về 1, và hạ `VIEWS_PER_TRIP` từ (1,3) xuống (1,2). Kết quả 7.653 event. Knob nằm trong `config.py` để Evaluation chỉnh.
- **`using_date` tương lai được kẹp vào `[available_from, available_to]` của chính sản phẩm.** Không kẹp thì chuyến bay (from = to = đúng một ngày) làm `verify.sql` FAIL 38 dòng. Chỉ áp cho ngày tương lai — event lịch sử không bị ràng buộc này (DATABASE_SCHEMA §1 mục 13).
- **Salt BCrypt sinh tất định từ RNG** bằng bộ mã hoá radix-64 riêng của BCrypt. Ghép chuỗi tuỳ ý vào salt của `gensalt()` bị `ValueError: Invalid salt` vì ký tự cuối chỉ mang 2 bit. Salt tất định là có chủ ý cho dữ liệu demo dùng chung một mật khẩu; tài khoản đăng ký thật qua backend vẫn phải dùng salt ngẫu nhiên.
- **Id "sản phẩm đã xoá" dùng uuid5, không phải uuid4**, và `profiles.updated_at` suy từ `as_of` thay vì `now()` — nếu không, hai lần chạy cùng seed cho dữ liệu khác nhau (đã đo bằng checksum md5).
- **Persona lấy `vinclub_tier`/`home_city` từ `config.PERSONA_PROFILE`, không rút ngẫu nhiên.** UX spec §5 yêu cầu P1 là Gold; để ngẫu nhiên thì đúng Gold chỉ là may. Persona cũng luôn bật cả 3 kênh opt-in để demo không phụ thuộc vào việc có rơi vào 5% tắt email hay không.
- **Chỉ sinh tuyến bay chiều *tới* điểm đến** (3 origin × 4 destination = 12 tuyến). Sinh cả chiều về thì `destination` của vé bay là "Hà Nội"/"TP. Hồ Chí Minh" — nơi không có khách sạn nào trong catalog — và quy tắc "mỗi chuyến một destination" sẽ ghép vé bay về Hà Nội vào chuyến đi Nha Trang.
- **Tỷ lệ attraction không bán vé do `ATTRACTION_UNTICKETED_RATE` quyết định**, không do số lượng mẫu tên. Bản đầu có 3/9 mẫu là điểm công cộng nên ra 37% thay vì 15% như §1b.
- **Báo cáo tách "tỷ lệ map được" theo loại map được.** `meal`/`transfer`/`other` luôn `item_product_id = NULL` vì FK `(item_product_id, item_kind) → products (product_id, taxonomy)` không có taxonomy tương ứng; gộp chúng vào mẫu số làm chỉ số trông tệ mà không phản ánh chất lượng parser. Map được 86,3% trên các loại map được (yêu cầu §1b: ≥ 70%).
- **Không hạ `ZIPF_S` để ép baseline Recall@20 xuống dưới 0,6.** Chỉnh phân bố cho vừa thước đo là bóp méo dữ liệu. Giữ nguyên `ZIPF_S = 1.1` và ghi rõ trong báo cáo; xem mục Kiểm tra — chỉ số này tự về trong khoảng sau khi sửa thứ tự event ở phần C, không phải nhờ vặn tham số.

Phần C:

- **Miễn combo khỏi cạnh lộn xộn "2% mô tả ngắn".** `description` của combo là đầu vào của `parse_combos`; cắt cụt nó thì §1b ("map được ≥ 70%") không thể đạt. Hai yêu cầu trong cùng §1b xung khắc; yêu cầu về combo cụ thể hơn nên thắng. Cạnh lộn xộn vẫn áp cho các taxonomy khác, đúng mục đích của nó là làm khó search/dedupe.
- **Một chuyến là một lần checkout: chốt `purchase_at` trước, rồi đặt `product_view`/`add_to_cart` lùi về trước nó.** Cách cũ sinh giờ ngẫu nhiên trong ngày cho view, nên view `lead = 0` có thể rơi vào buổi tối *sau* lần mua buổi sáng — sai quy tắc "product_view trước purchase 0–7 ngày" (§4).

## Kiểm tra

Đã chạy thật, ngày 20/09:

- `docker compose up -d --wait postgres` → container Healthy. Log initdb không có ERROR/FATAL (chỉ warning "trust authentication" mặc định của image).
- `vota`: **15 bảng + 3 view**, đúng kỳ vọng.
  - `cdp.products`, `cdp.profiles`, `cdp.events`
  - `catalog.combo_items`, `catalog.product_vectors`
  - `app.users`, `carts`, `cart_items`, `bookings`, `booking_items`, `conversations`, `conversation_messages`, `itineraries`, `recommendation_logs`, `search_logs`
  - view `catalog.product_meta`, `catalog.product_parents`, `catalog.search_rows`
- `insider`: **5 bảng + view `live_events`** (`partners`, `insider_profiles`, `identifiers`, `insider_events`, `channel_events`).
- Role: `cdp_reader`, `cdp_writer`, `vota_app` (NOLOGIN) + `vota_app_login`, `cdp_client_login`, `cdp_eval_login` (LOGIN). Extension: `vector`, `plpgsql`.
- Ranh giới role kiểm chứng bằng 4 truy vấn thật:
  - `vota_app_login` → `cdp.products`: OK (0 dòng).
  - `vota_app_login` → `cdp.events`: `ERROR: permission denied for table events`.
  - `cdp_client_login` → `catalog.combo_items`: `ERROR: permission denied for schema catalog`.
  - `cdp_client_login` → `cdp.events`: OK (0 dòng).
- `validate_contract.py`: không chạy — phần A không đổi OpenAPI, mock hay fixture.

Phần B — `cd src && PYTHONUTF8=1 python -m data_collection.seed --as-of 2026-09-20 --seed 42 --reset`, chạy hết trong **4,2 giây** (yêu cầu < 2 phút), exit code 0:

| Bảng | Số dòng |
|---|---|
| `cdp.products` | 433 (40 property + 2 gần trùng, 140 room, 12 route, 131 flight, 60 attraction, 8 golf, 40 combo) |
| `catalog.combo_items` | 136, 0 combo rỗng, 73 dòng trong hàng đợi soát tay |
| `cdp.profiles` / `cdp.events` | 2.000 / 7.653 |
| `app.users` / `bookings` / `booking_items` | 54 / 1 / 1 |
| `insider`: profiles / identifiers / events / channel_events | 2.000 / 6.000 / 5.618 / 18.532 |

- `db/verify.sql` (chạy bằng `SEED_DATABASE_URL`): **14/16 PASS**. Hai dòng FAIL đúng như dự kiến: `products = 2216` (433) và `is_recommendable properties >= 300` (40).
- `db/verify_insider.sql`: **6/6 PASS**.
- Combo: map được **86,3%** trên các loại map được (hotel 100%, golf 100%, attraction 77%) — trên mức ≥ 70% của §1b.
- Tất định: chạy `--reset` ba lần, md5 của `cdp.events` (mọi cột), `cdp.profiles` và `insider.channel_events` **giống nhau cả ba lần**. Hai lỗi tất định phát hiện nhờ phép đo này (uuid4, `now()`) đã sửa.
- Chạy lại **không** `--reset`: dừng với thông báo `cdp.profiles đã có 2000 dòng…`, exit code 1 — không nhân đôi dữ liệu.
- 4 persona đúng bảng §5: P1 active/Gold/4 đơn/3 ngày/Nha Trang, có đơn `VOTA-20261002-4D6N` với `using_date = as_of + 12` nằm trong cửa sổ và **đúng một** event `purchase` cùng `event_group_id`; P2 new/0 đơn/2 `product_view`; P3 dormant/190 ngày/Phú Quốc; P4 new/0 event.
- Ranh giới role kiểm chứng lại sau khi có dữ liệu: `vota_app_login` đọc `cdp.products` OK, `cdp.events` bị từ chối.

Phần C — `cd src/data_collection && python -m unittest discover -s tests -t . -p "test_seed.py"`: **59 test, OK, 0.54 giây**, không cần database.

Hai lỗi thật do test phát hiện, đã sửa (không phải sửa test cho vừa code):

1. `product_view` có thể rơi vào *sau* `purchase` khi cùng ngày (`lead = 0`) — sai thứ tự §4.
2. Cạnh lộn xộn "mô tả ngắn" cắt cụt description của combo, phá chính đầu vào của `parse_combos`.

Chạy lại toàn bộ sau khi sửa: 433 products · 142 combo_items · 2.000 profiles · 7.614 events · 54 users · 18.532 channel_events; `verify.sql` 14/16 PASS (2 FAIL dự kiến), `verify_insider.sql` 6/6 PASS; md5 của `cdp.events` giống nhau qua hai lần `--reset`.

Chạy cả bộ test của workstream (`python -m unittest discover -s tests -t .`): 73 test, 59 test seed **OK**, `test_quality` **OK** sau khi cài `requirements.txt`. Còn **5 lỗi có sẵn từ trước, không liên quan thay đổi này**: `test_overnight` dùng `signal.SIGKILL` — hằng số chỉ có trên POSIX, không có trên Windows (`overnight.py:155`). Cả `overnight.py` lẫn `test_overnight.py` đều không nằm trong thay đổi này.

`validate_contract.py`: **lỗi có sẵn từ trước** (`KeyError: 'priceUnit'`), đã kiểm chứng bằng cách chạy lại ở commit `cbbb482` (trước thay đổi này) và ra đúng lỗi đó. Thay đổi này không đụng `src/shared/contracts`, `src/shared/mocks` hay `sample/`.

**Baseline Recall@20 = 0,501 — nằm trong khoảng mục tiêu 0,05–0,60, DoD mục 5 đạt.** Trước khi sửa thứ tự event, chỉ số này là 0,766. Lý do đổi: lần mua *cuối* của mỗi khách (mục bị giấu khi đo) trước đây rơi vào vertical ngẫu nhiên, thường là hotel — vertical tập trung nhất nên baseline "phổ biến nhất" đoán trúng quá dễ. Khi checkout theo đúng thứ tự hotel → flight → attraction → golf, mục bị giấu phân bố ra nhiều vertical (hotel 538 · combo 391 · attraction 334 · flight 200 · golf 38) và phần lớn là hạng mục đuôi dài. Chỉ số tự về đúng khoảng nhờ **sửa lỗi thứ tự**, không phải nhờ vặn `ZIPF_S`.

## Còn lại / rủi ro

- `psql` không có trên máy này; mọi lệnh psql chạy qua `docker compose exec -T postgres psql`. `report.py` tự chạy các câu verify bằng psycopg (bỏ dòng `\pset`) nên không phụ thuộc psql.
- **Hai dòng `db/verify.sql` FAIL theo thiết kế** với catalog tổng hợp: `products = 2216` và `is_recommendable properties >= 300`. Hết FAIL khi có `products.jsonl` thật từ crawler — chạy lại `--reset` với file thật, không sửa code.
- Chỉ số Recall ở `report.py` là phép đo nhanh để phát hiện dữ liệu quá ngẫu nhiên, **không thay** bộ đo của `src/evaluation` (Recall@20, NDCG@10, cross-category rate, availability precision, coverage — ARCHITECTURE §10). Evaluation nên đo lại trên catalog thật.
- **DoD mục 6 (đăng nhập 4 persona, Home hiện đúng section) chưa kiểm được**: backend/frontend chưa đọc database này. Mới xác minh tới mức dữ liệu — stage, tier, đơn sắp tới và số event của từng persona đúng bảng §5.
- `products.synthetic.jsonl` không commit (đã vào `.gitignore`) vì sinh lại được từ `--seed` + `--as-of`.
- **Code chưa theo kiến trúc mới:** `src/backend/app/infrastructure/clients/cdp_http_client.py` và `cdp_event_dispatcher.py` vẫn là thiết kế service HTTP. Các adapter mà `README.database.md` nhắc tới — `infrastructure/cdp/local_cdp_client.py`, `infrastructure/insider/http_insider_client.py`, `application/ports/insider_client.py` — **chưa tồn tại**. `src/backend/app/core/config.py` còn default `sqlite:///./data/app.db` và `cdp_base_url`. Việc này thuộc Backend, ngoài phạm vi tuần 1 của Data.
- `src/cdp_clone/app/infrastructure/tables.py` (revision `0001`) chưa khớp `db/init/01_vota.sql`; phải đối chiếu lại trước khi dựng `HttpCdpClient`.
- `src/insider_clone/` vẫn rỗng (chỉ có README + `.gitkeep`); `seed_insider.py` ghi thẳng vào database `insider`, chưa qua service.
- Chờ xác nhận, chưa tự quyết: tên cột opt-in trong `cdp.profiles` (chờ reviewer CDP); D và model vector (tuần 2, `catalog.product_vectors` để trống); "mọi route có ≥ 1 chuyến?" — catalog tổng hợp cố ý tạo đúng 1 route không có chuyến để câu hỏi này có ví dụ.
- `--reset` bị chặn với host không phải localhost trừ khi có `--allow-remote-reset`; khi reset Postgres staging chung phải báo trong nhóm (AGENTS.md §6.3).
- **Hai lỗi có sẵn từ trước, không sửa trong thay đổi này** vì nằm ngoài phạm vi: `validate_contract.py` lỗi `KeyError: 'priceUnit'` (đã kiểm chứng có từ commit `cbbb482`) và `test_overnight` lỗi `signal.SIGKILL` trên Windows (`overnight.py:155`). Cần chủ sở hữu tương ứng (Integration, Data/crawler) xử lý.

---

## Bổ sung 21/09 — sửa hai lỗi phát hiện khi chạy lại ở ngày khác

- `src/data_collection/seed/config.py` — thêm `WINDOW_CLAMP_SKEW_DAYS = 1`.
- `src/data_collection/seed/seed_histories.py` — sửa: kẹp `using_date` khi `>= as_of - dung sai`, thay vì `> as_of`.
- `src/data_collection/seed/report.py` — sửa: bỏ dòng "Thời gian chạy" khỏi khối `seed-report`.
- `src/data_collection/tests/test_seed.py` — thêm: test hồi quy `test_purchases_on_the_as_of_boundary_are_also_clamped`.
- `src/data_collection/README.md` — sửa: khối `seed-report` sinh lại.

**Lỗi 1 — `future purchases inside window: FAIL (1)`.** Chỉ lộ ra khi seed bằng `--as-of` khác ngày của database. `db/verify.sql` so `using_date > current_date` — đồng hồ **của database** — còn seed chỉ biết `as_of`. Đồng hồ container Postgres trôi một ngày so với host (container `2026-09-20`, host `2026-09-21`), nên một chuyến bay có `using_date` đúng bằng `as_of` lọt qua bước kẹp (điều kiện cũ `> as_of`) rồi bị verify bắt: `VP0000035`, bay ngày `2026-09-28`, `using_date = 2026-09-21`. Sửa bằng cách kẹp từ `as_of - 1 ngày`; event lịch sử cũ hơn vẫn được miễn (DATABASE_SCHEMA §1 mục 13). Đã chạy lại với `--as-of` 20, 21 và 22/09: cả ba đều PASS.

**Lỗi 2 — báo cáo làm bẩn git sau mỗi lần seed.** Khối `seed-report` in "Thời gian chạy" chính xác tới 0,1 giây nên `src/data_collection/README.md` đổi ở **mọi** lần chạy, gây conflict vô ích khi nhiều người cùng seed. Thời gian chạy chỉ còn in ra stdout. Đã kiểm: chạy seed hai lần liên tiếp, `git status` sạch.

Kiểm tra: 60 test `unittest` OK; `verify.sql` 14/16 PASS (2 FAIL dự kiến) và `verify_insider.sql` 6/6 PASS ở cả ba mốc ngày.
