# Seed mock data theo đúng MOCK_DATA_SPEC §2, §4–§6; gom mọi tỷ lệ vào config.py

- Ngày: 2026-09-21
- Tác giả: tqanh123 / Claude Code
- Nhánh: mockdata
- Trạng thái: hoàn thành
- Phạm vi: data, cdp, insider, docs
- Thay thế: phần "Kế hoạch mock data" mà code seed của `2026-09-21-hoan-thanh-seed-catalog.md` đang theo (bảng rút gọn `docs/DATABASE_SCHEMA.md` §8)

## Mục tiêu

Người yêu cầu hỏi mock data đang có những phân bố nào. Đối chiếu cho thấy code lệch `docs/MOCK_DATA_SPEC.md` ở khoảng 40 điểm. Người yêu cầu muốn sửa code cho giống spec và chuyển các tỷ lệ vào `config.py` (spec §8: "mọi tỷ lệ ở §4–§6 nằm trong config.py để Evaluation chỉnh mà không đọc code").

Trước thay đổi, `config.py` chỉ có 4 tham số. Phần còn lại hard-code trong `seed_histories.py`, `seed_insider.py` và `catalog_meta.py`.

## File thay đổi

**Package seed (`src/data_collection/seed/`)**

- `config.py` — sửa: thành nơi duy nhất chứa tham số §2/§4/§5/§6, giữ alias `DEFAULT_*` cũ. Nhóm tham số:
  - lịch phòng/vé và trọng số cụm cuối tuần;
  - stage, tier, home_city, opt-in;
  - số chuyến, recency, cửa sổ 24 tháng, lead time;
  - vertical mix, Zipf, view/search/add_to_cart, quantity, nhiễu giá;
  - cạnh lộn xộn, trần Recall;
  - persona;
  - Insider: gdpr, identifier, TTL, phễu, độ trễ, chiến dịch, lý do bounce, ngày tạo partner.
- `catalog_meta.py` — sửa:
  - thêm `stable_order_key` (crc32);
  - `is_vinpearl` xét thêm property cha;
  - `room_calendar` sinh trực tiếp cho cửa sổ 30 ngày: 25–40% đêm kín, cụm 1–4 đêm, cụm chứa T6/T7 trọng số ×2 (ra ≈ ×1,5 mỗi đêm), Vinpearl ×1,3 chặn ở 40%;
  - `ticket_calendar(product_id, as_of)`: 15% sản phẩm blackout 2–3 ngày, bỏ luật ngày lễ.
- `load_products.py` — sửa:
  - `availability = {from, days, calendar}` chỉ cho hạng phòng, attraction, golf (combo không còn khoá này);
  - ngày bay: fallback `as_of + crc32 % 30`, dùng `sourceAvailableFrom` khi không có `datesSeen`;
  - gán `checkInTime`/`checkOutTime` mặc định cho property;
  - sửa docstring.
- `seed_histories.py` — sửa (viết lại phần sinh):
  - ID tuần tự; Zipf một tầng theo crc32; điểm đến theo số sản phẩm bookable;
  - 65% chuyến ≥ 2 vertical, golf 3%, search 30%, 1–3 view khác nhau, add_to_cart ở 40% chuyến;
  - quantity và giá theo spec; lead 7–45 ngày; vé = nhận phòng + 1; mọi event trong 24 tháng;
  - cap 15 event/khách, không bao giờ bỏ purchase; cạnh lộn xộn theo spec; lifecycle "0 purchase → new";
  - persona theo §5, báo lỗi rõ khi catalog thiếu dữ liệu;
  - report: Recall chỉ tính gid khác NULL, in tỷ lệ search/add_to_cart theo chuyến, cảnh báo khi vượt `RECALL_CEILING`.
- `seed_insider.py` — sửa:
  - attributes chỉ 4 khoá; luật gdpr (tắt cả 3 kênh + 2%);
  - email `<id>@example.com`; 1% có email cũ `valid_to = as_of − 30`;
  - dừng mọi kênh sau unsubscribe; `campaign_id = CMP-yyyymm-NN`;
  - token mặc định `dev-token`; partner tạo trước mọi profile;
  - bỏ tham số `users` không dùng (không đọc `app_users.jsonl` nữa);
  - `main` trả 1 khi có vi phạm ràng buộc.
- `__main__.py` — sửa: lấy tham số từ config; dừng pipeline (exit 1) khi `seed_histories`/`seed_insider` trả mã ≠ 0.
- `common.py` — xóa: không module nào import, và import còn lỗi (`config.ZIPF_S` không tồn tại, cần numpy). `stable_order_key` chuyển sang `catalog_meta.py`.
- `requirements.txt` — sửa: bỏ `numpy` (chỉ `common.py` đã xoá dùng tới).
- `README.md` — sửa: chỉnh phân bố ở `config.py` và cách kiểm lại sau khi chỉnh.

**Test (`src/data_collection/tests/`)**

- `test_seed_histories.py` — sửa: khẳng định theo quy tắc mới. `RealCatalogSmoke` đọc thẳng snapshot gzip nên luôn chạy (trước đây bị skip khi chạy từ `src/`).
- `test_seed_load_products.py` — sửa: lịch phòng/vé theo spec (có kiểm tỷ lệ T6/T7 ≈ ×1,5), shape `availability`, combo không có lịch, ngày bay, giờ nhận/trả phòng. Bỏ test "cuộn cửa sổ giữ nguyên trạng thái đêm".
- `test_seed_insider.py` — sửa: attributes, email, lịch sử email 1%, gdpr, unsubscribe, campaign_id, event search, ngày tạo partner.

**Tài liệu**

- `src/data_collection/README.md` — sửa: khối `seed-report` sinh lại (7.131 event; Insider 4.155 event, 19.517 channel event).
- `docs/MOCK_DATA_SPEC.md` — sửa: §0 thêm "Điểm chốt 21/09" (6 quyết định, bảng diễn giải, số đo).
- `docs/DATABASE_SCHEMA.md` — sửa:
  - §8 trỏ sang MOCK_DATA_SPEC là nguồn chi tiết và sửa các dòng lệch (lịch attraction/combo, new = 0 purchase, Zipf 0,8, cạnh lộn xộn tính theo purchase);
  - §1 #11 ghi seed đang theo MOCK_DATA_SPEC, vẫn chờ Evaluation chốt số.
- `history/2026-09-21-seed-theo-mock-data-spec.md` — thêm: entry này.

## Quyết định

Người yêu cầu chốt (21/09):

1. **Phạm vi:** §2, §4, §5, §6 và `config.py`. Không sửa §1b (`gen_products.py`) và §2.3/§3 (`parse_combos.py`, đã tinh chỉnh cùng 64 mapping duyệt tay). Giữ RNG `random.Random`, không đổi sang numpy.
2. **Khách sạn `quantity = 1`** (số phòng, khớp `schemas/booking.yaml`). P1 ở 1 đêm vì `booking_items.line_total` là cột GENERATED `unit_price × quantity`, không nhân số đêm.
3. **Sinh event `search`** (30% chuyến) không có câu truy vấn. Ghi nhận xung đột: `schemas/cdp-clone.yaml` bắt buộc `searchQuery`.
4. **Chỉ `purchase` mang `event_group_id`**, giống dữ liệu app ghi thật. "3% event bỏ gid" áp lên purchase.
5. **Lịch phòng Vinpearl** = `min(40%, gốc × 1,3)`.
6. **`lifetime_order_count` đúng chữ spec:** chỉ đếm gid khác NULL.

Tự quyết, có căn cứ (chi tiết ở MOCK_DATA_SPEC §0):

- **Trọng số số chuyến nghiêng về 1**, vẫn giữ đúng khoảng của spec. Phân bố đều vượt cổng 6.000–8.000 event của `verify.sql` (tiền lệ `2026-09-20-database-mock-data-tuan-1.md`). Trọng số được hiệu chỉnh bằng mô phỏng trên snapshot.
- **`MULTI_FLIGHT_RATE = 0,8` và `MULTI_TICKET_RATE = 0,10`** (spec không quy định hai giá trị này).
  - Với 1,0 / 0,20, seed 42 cho Recall@20 = 62,7% > 60% (DoD #5).
  - Với 0,8 / 0,10, seed 42 = 58,4%; qua 62 seed trung bình 54,0%, sd 3,5 điểm, và 4/62 seed vượt 60%.
  - Không tổ hợp knob nào trong phạm vi spec xoá được phần đuôi đó: trung bình luôn quanh 53–54% vì tập ẩn chỉ khoảng 270 khách.
  - Vì vậy vượt trần chỉ in WARNING, không dừng pipeline.
  - Không vặn Zipf (spec cố định s = 0,8, Vinpearl ×2).
- **Kẹp `using_date` của khách thường ≤ as_of − 1.** Lần mua cuối của active cách as_of ≥ 9 ngày để lead vẫn ≥ 7 (spec 7–45). Lần mua cũ nhất ≤ 722 ngày để view/search vẫn trong 730 ngày.
- **Persona theo khuôn cố định** (không search, 1 view mỗi chuyến): P1 = 12 event, P3 = 6, dưới cap 15 mà `verify.sql` tính cả persona.
- **Lịch phòng sinh theo `(product_id, as_of)`**, bỏ tính chất "một đêm không đổi khi cuộn cửa sổ" của bản cũ. Bản cũ để 62% phòng ra ngoài khoảng 25–40%, và Vinpearl chỉ đạt ×1,18. "T6/T7 ×1,5" hiểu theo từng đêm: trọng số cụm ×2 ra ×1,48–1,49 mỗi đêm (trọng số trung bình theo đêm của bản đầu chỉ ra ×1,25).
- **Ngày bay giữ `datesSeen` sớm nhất trong cửa sổ** (trùng `sourceAvailableFrom` khi nó nằm trong cửa sổ), fallback theo spec. Bỏ `datesSeen` sẽ mất ngày thật của 15–98 chuyến, tuỳ `as_of`.
- **Vinh → origin "Nghệ An":** catalog gắn sân bay Vinh vào nhãn này.
- **Xoá `common.py`:** mã chết và import lỗi.
- **Review độc lập** (3 reviewer, mỗi phát hiện có 1 skeptic kiểm lại) xác nhận 14 phát hiện và bác 14. Đã sửa cả 14:
  - hệ số cuối tuần;
  - event vượt 24 tháng;
  - view trùng trong một chuyến;
  - view của khách new có thể qua nửa đêm;
  - lỗi rõ ràng cho persona khi catalog thiếu dữ liệu, và kiểm mọi đêm của P1 với khoảng bán của nguồn;
  - cảnh báo khi Recall vượt trần;
  - dung sai test golf/gdpr theo biên nhị thức;
  - tỷ lệ add_to_cart trong report;
  - thêm config còn thiếu (khoảng cách view, lý do bounce, ngày tạo partner);
  - dọn mã chết (`World.rows`, khoá `stage`/`home`, tham số `users`, phép gán thừa);
  - bỏ `numpy` khỏi requirements.

## Kiểm tra

Đã chạy thật ngày 21/09, Python 3.13 trong `.venv`. Đã cài thêm `beautifulsoup4` theo `src/data_collection/requirements.txt` để `parse_combos` import được.

- `cd src && python -m unittest discover -s data_collection/tests -t . -p "test_seed*.py"` → **53 test OK**. `RealCatalogSmoke` chạy trên snapshot thật, không bị skip.
- **Tất định:** chạy `python -m data_collection.seed --products …/products.jsonl.gz --as-of 2026-09-21 --seed 42 --generate-only` trong hai tiến trình riêng → md5 của 11 file (`seed/*.jsonl`, `loader/cdp_products.jsonl`) **giống nhau**.
- **Số đo với seed 42:**
  - 7.131 event: purchase 3.148 · product_view 2.190 · add_to_cart 1.258 · search 535.
  - Stage 25,1 / 45,0 / 20,0 / 10,0%.
  - 64% chuyến ≥ 2 vertical, golf 3,2%, 29% chuyến có search, 40% có add_to_cart.
  - Purchase trỏ sản phẩm không tồn tại 2,0%, purchase thiếu gid 3,0%.
  - Recall@20 = 157/269 = **58,4%**.
  - Insider: 2.000 profile, 6.020 identifier (20 đã đóng), 4.155 event, 19.517 channel event, mọi `viol_*` = 0.
- **Database:**
  - Cổng `localhost:5432` của máy đang do một Postgres khác chiếm (sai mật khẩu), và container `travel-recommendation-product-postgres-1` không publish cổng.
  - Vì vậy kiểm trên **container tạm** `pgvector/pgvector:pg16` ở cổng 55432, cùng `db/init`; đã xoá kèm volume sau khi xong.
  - Chạy `--reset` với `--as-of` 2026-09-20, 21 và 22, cả trước và sau lượt sửa theo review: `db/verify.sql` **16/16 PASS**, `db/verify_insider.sql` **6/6 PASS** ở mọi lần.
- **Backend:** `RUN_POSTGRES_INTEGRATION=1 pytest src/backend/tests` trên DB tạm đã seed → **37 passed**. Gọi `/api/v1/recommendations` qua TestClient:
  - P1 `cross_vertical` Nha Trang (vé bay, attraction, combo, golf; because purchase);
  - P2 `cold_start_content` Phú Quốc (because product_view);
  - P3 `dormant`;
  - P4 `popular` (because rỗng).
- `git diff --check` → sạch.
- `validate_contract.py`: không chạy, vì không đổi OpenAPI, schema hay mock.

## Còn lại / rủi ro

- **Database demo local đã nạp lại** bằng `make demo-db-reset AS_OF=2026-09-21`: verify 16/16 và 6/6 PASS.
  - Cổng 5432 trước đó bị container `p205-dev-postgres` (project khác) chiếm. Người dùng chọn tạm dừng container đó; bật lại bằng `docker start p205-dev-postgres` thì hai project không chạy cùng lúc được.
  - Trên Windows cần `PYTHONUTF8=1` khi output bị pipe.
  - `make demo-db`/`demo-db-reset` hỏng ở bước `$(MAKE) verify-db`: đường dẫn GnuWin32 `C:/Program Files (x86)/…` không được đặt trong nháy. Lỗi có sẵn trong `Makefile`, chưa sửa; tạm chạy `make verify-db` riêng.
- Recall@20 phụ thuộc seed: khoảng 6% seed vượt 60% (report ghi VƯỢT TRẦN). Seed demo 42 đạt. Bộ đo thật vẫn là việc của `src/evaluation`.
- Event `search` không có câu truy vấn nên không replay được qua `HttpCdpClient`.
- Hợp đồng Insider §6 yêu cầu attribute `recommended_products`. Yêu cầu này nằm ngoài MOCK_DATA_SPEC, để job activation tuần 5.
- Hợp đồng recommendation "coldStart ⇒ because rỗng" mâu thuẫn với kỳ vọng "P2 cold start có because". Mâu thuẫn có từ trước, không sửa.
- `seed_app.rows_from_history` vẫn không được gọi (spec §1 muốn `seed_app.py` tạo `app.users`). Đây là refactor cấu trúc, ngoài phạm vi.
- Khoảng 8% chuyến có điểm đến trùng home_city (HN/HCM). Spec không cấm.
- `parse_combos.py` và `gen_products.py` vẫn lệch §2.3/§1b (ngoài phạm vi theo quyết định 1).
- `bcrypt` trong `seed/requirements.txt` cũng không được import (hash demo tính sẵn). Có từ trước, không đổi.
- Chưa commit, chưa push.
