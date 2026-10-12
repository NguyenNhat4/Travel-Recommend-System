# Dữ liệu mô phỏng: vé máy bay phủ đủ ngày và sản phẩm cho mọi thành phần combo

- Ngày: 2026-10-09
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Pham Nguyen Dang Khoi, 2026-10-09 (trong chat: "Ok, đã chốt data mock")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.1 FR-CAT-03 (gạch "Vé khứ hồi…", "Ngoại lệ duy nhất"), FR-CAT-04;
  `docs/prd/data-model.md` §2.1 (khối `CATALOG_COMBO_ITEMS`), §3.1 (sau "Vé Thương gia mô phỏng"), §4.2
- Mã FR/NFR: FR-CAT-01, FR-CAT-03, FR-CAT-04, NFR-REL-01 (grounding: dữ liệu vẫn nằm trong catalog, có nhãn mô phỏng)

## Lý do

Kiểm tra DB production ngày 09/10/2026 (chỉ đọc):

- **Vé máy bay thưa ngày.** 112 tuyến đang gợi ý; trong 30 ngày tới, 76 tuyến chỉ có vé ở 1–5 ngày, vì vé thật có ngày cố định
  và job chỉ dời mỗi vé vào một ngày (`crc32`). Có 3.360 cặp (tuyến, ngày): 2.903 cặp không có vé một chiều, 2.885 cặp không có vé
  khứ hồi (không tính vé Thương gia mô phỏng). Người dùng chọn ngày nào cũng phải có chuyến để demo luồng đặt vé.
- **Combo không tách được khi thanh toán.** Bước thanh toán sẽ tách combo thành từng dịch vụ, nên mỗi thành phần phải trỏ tới một
  sản phẩm đặt được. Với 147 combo đang bán, chỉ 93/334 thành phần làm được việc này:

| Thành phần | Đã trỏ tới sản phẩm đặt được | Thiếu |
|---|---:|---|
| Khách sạn (50) | 6 (hạng phòng) | 21 chỉ trỏ tới khách sạn tổng; 23 khách sạn chưa có trong DB |
| Vé máy bay (50) | 0 | 41 chỉ trỏ tới tuyến; 9 thuộc 3 tuyến chưa có (HAN–VDO, SGN–VDO, SGN–VCA) |
| Vé tham quan (124) | 87 | 30 chưa nối; 7 trỏ tới điểm không bán vé (không có giá) |
| Ăn uống / xe đưa đón / khác (110) | 0 | Toàn bộ: catalog không có loại sản phẩm này, và khoá ngoại `(item_product_id, item_kind)` không cho nối |

PRD hiện cấm tự tạo giá (FR-CAT-03: "không suy hạng hoặc tự tạo giá. Ngoại lệ duy nhất: vé Thương gia mô phỏng") nên cả hai việc
trên đều cần chốt. Người dùng đã chọn (09/10): thành phần vé máy bay trỏ tới tuyến và tuyến được phủ vé mọi ngày; giá các thành phần
chia đúng giá combo; sản phẩm mô phỏng của combo không hiện riêng ở tìm kiếm và gợi ý; ghi vào DB production trước, sửa job sau.

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.1 FR-CAT-03 — gạch "Vé khứ hồi là `flight_instance`…"

Hiện tại:

> … không đổi ID vé cũ, không suy hạng hoặc tự tạo giá. Ngoại lệ duy nhất: vé Thương gia mô phỏng cho demo UI chọn hạng, sinh từ vé
> thật, luôn gắn nhãn "giá minh hoạ" và `simulated: true` (xem `data-model.md` §3); mặc định bật, tắt bằng cấu hình; tắt thì các vé
> này không đặt được nữa. Giá là tổng hành trình cho một người lớn.

Thay bằng:

> … không đổi ID vé cũ, không suy hạng hoặc tự tạo giá. Ba ngoại lệ cho demo, đều sinh từ dữ liệu thật trong catalog, luôn gắn
> `simulated: true` và nhãn "giá minh hoạ" (xem `data-model.md` §3): (1) vé Thương gia mô phỏng cho UI chọn hạng; (2) vé phủ ngày:
> mỗi tuyến có ít nhất một vé một chiều và một vé khứ hồi ở mọi ngày trong cửa sổ đặt chỗ; (3) sản phẩm thành phần combo (FR-CAT-04).
> Mỗi ngoại lệ mặc định bật, tắt riêng bằng cấu hình; tắt thì các dòng đó không đặt được nữa. Dữ liệu thật luôn thắng dữ liệu mô phỏng.
> Giá vé là tổng hành trình cho một người lớn.

### `docs/prd/requirements.md` §1.1 FR-CAT-04

Hiện tại:

> **FR-CAT-04 (Gói kết hợp - Combo Handling):** Hỗ trợ tách bóc và truy xuất chi tiết các thành phần trong combo (phòng ở, vé máy bay,
> vé vui chơi) với tỷ lệ tin cậy và căn cứ trích xuất rõ ràng.

Thay bằng:

> **FR-CAT-04 (Gói kết hợp - Combo Handling):** Hỗ trợ tách bóc và truy xuất chi tiết các thành phần trong combo (phòng ở, vé máy bay,
> vé vui chơi, dịch vụ kèm theo) với tỷ lệ tin cậy và căn cứ trích xuất rõ ràng. Mỗi thành phần trỏ tới một sản phẩm trong catalog để
> bước thanh toán tách được combo: khách sạn → hạng phòng, vé máy bay → tuyến (chọn chuyến theo ngày đi), vé tham quan và dịch vụ kèm
> theo → vé/dịch vụ đặt được. Thiếu sản phẩm thật thì dùng sản phẩm thành phần mô phỏng (FR-CAT-03 ngoại lệ 3). Mỗi thành phần có phần
> giá (`price_share`); tổng phần giá các thành phần của một combo đúng bằng giá combo.

### `docs/prd/data-model.md` §2.1 — khối `CATALOG_COMBO_ITEMS`

Thêm dòng `numeric price_share "Phần giá combo của thành phần; tổng = giá combo"`.

### `docs/prd/data-model.md` §3.1 — thêm hai khối sau "Vé Thương gia mô phỏng (demo)"

> **Vé phủ ngày (demo).**
>
> - Chạy sau mỗi lần nạp catalog, sau bước vé Thương gia mô phỏng. Mặc định bật; tắt bằng `SIMULATED_FILL_FLIGHTS=0`.
> - Với mỗi tuyến và mỗi ngày trong cửa sổ đặt chỗ chưa có vé một chiều đặt được (hạng không phải Thương gia), sinh một vé một chiều;
>   chưa có vé khứ hồi đặt được thì sinh một vé khứ hồi.
> - Chặng đi chép từ một vé thật của tuyến (hãng, số hiệu, giờ đi/đến, sân bay); chọn cố định theo ngày (`crc32`) trong các vé thật
>   để các ngày không giống hệt nhau. Chặng về chép từ vé thật của tuyến ngược chiều, ngày về = ngày đi + 2–5 ngày (cố định theo
>   `crc32`); tuyến không có chiều ngược thì đảo sân bay của chặng đi, giữ hãng, không có số hiệu.
> - Giá = giá của vé thật đã chép (khứ hồi: giá vé khứ hồi thật của tuyến nếu có, không thì cộng hai chặng). `cabinClass: ECONOMY`.
> - `sourceRef` = `demo:fill:<sourceRef tuyến>:<oneWay|roundTrip>:<ngày đi>`; `productId` sinh cố định từ `sourceRef`. Đánh dấu như vé
>   Thương gia mô phỏng: `simulated: true`, `fieldSources.unitPrice = "mô phỏng"`, tên có hậu tố "(giá minh hoạ)".
> - Hiện ở trang vé máy bay như vé thường. Không sinh vé Thương gia mô phỏng từ vé phủ ngày.
> - Ngày đó có vé thật đặt được, ngày đã qua, hoặc tắt cấu hình → vé phủ ngày chuyển `available = false`; không xoá dòng.
>
> **Thành phần combo mô phỏng (demo).**
>
> - Chạy sau bước parse combo (`catalog.combo_items`). Mặc định bật; tắt bằng `SIMULATED_COMBO_ITEMS=0`.
> - Khách sạn: trỏ tới hạng phòng thật khi tên khách sạn và tên hạng phòng trong combo khớp catalog (sau chuẩn hoá, độ giống ≥ 0,9);
>   không thì sinh một khách sạn tổng + một hạng phòng mô phỏng riêng cho combo (tên, địa chỉ, sao, ảnh lấy từ combo; nếu khớp được
>   khách sạn thật thì chép thông tin khách sạn đó và ghi `comboBaseProductId`). Không gắn phòng mô phỏng vào khách sạn thật, để trang
>   khách sạn thật không đổi.
> - Vé máy bay: trỏ tới tuyến theo sân bay đi/đến của combo; tuyến chưa có thì sinh tuyến mô phỏng. Tuyến (thật hoặc mô phỏng) được phủ
>   vé mọi ngày theo khối "Vé phủ ngày"; tuyến mô phỏng lấy chặng mẫu từ giờ bay ghi trong combo.
> - Vé tham quan: giữ liên kết tới vé đặt được; chưa nối hoặc trỏ tới điểm không bán vé thì sinh vé mô phỏng (tên = nhãn thành phần
>   + khu vui chơi của combo).
> - Ăn uống, xe đưa đón, khác: sinh dịch vụ mô phỏng, `taxonomy = attraction`, loại gốc ở `attributes.serviceKind`
>   (`meal | transfer | other`); dòng `combo_items` đổi `item_kind` thành `attraction` để thoả khoá ngoại.
> - Sản phẩm thành phần mô phỏng mang `attributes.comboOnly = true`: `catalog.product_meta` trả `is_search_unit = false` và
>   `is_recommendable = false` (không ra tìm kiếm, gợi ý, không embed), `is_bookable` giữ quy tắc chung. Mỗi combo có bộ sản phẩm riêng:
>   `sourceRef` = `demo:combo:<sourceRef combo>:<position>`. Đánh dấu `simulated: true`, tên có hậu tố "(giá minh hoạ)".
> - **Phần giá:** `catalog.combo_items.price_share` = giá combo × giá tham khảo của thành phần / tổng giá tham khảo, làm tròn nghìn
>   đồng, phần lẻ dồn vào thành phần lớn nhất, nên tổng đúng bằng giá combo (cùng `priceBasis` với combo). Giá tham khảo × số lượng của
>   dòng: phòng = giá hạng phòng (thật hoặc khách sạn đã khớp), vé máy bay = giá khứ hồi rẻ nhất của tuyến, vé tham quan = giá vé, dịch
>   vụ = số tiền ghi trong nhãn ("300k", "150.000 VNĐ"). Thành phần không có giá tham khảo lấy bằng thành phần rẻ nhất của combo; không
>   thành phần nào có giá thì chia đều. Sản phẩm mô phỏng có `unit_price = price_share / số lượng`.
> - Combo đổi thành phần, hết bán, hoặc tắt cấu hình → sản phẩm thành phần mô phỏng chuyển `available = false`; không xoá dòng.

### `docs/prd/data-model.md` §4.2 — gạch `is_search_unit = true`, thêm câu cuối

> Sản phẩm thành phần combo mô phỏng (`attributes.comboOnly = true`) không phải đơn vị tìm kiếm và không được gợi ý; chỉ đặt qua combo.

## Thay đổi source sau khi chốt

- DDL: `db/vota_schema.sql` + `db/init/01_vota.sql` (giữ byte-identical): `catalog.product_meta` thêm điều kiện `comboOnly` vào
  `is_search_unit`, `is_recommendable`; `catalog.combo_items` thêm `price_share numeric(14,2) CHECK (price_share >= 0)`.
  Migration `db/migrations/0010_combo_only_va_price_share.sql` (idempotent: `CREATE OR REPLACE VIEW`, `ADD COLUMN IF NOT EXISTS`).
  `docs/spec/DATABASE_SCHEMA.md` §4, §7, §11.
- Job dữ liệu (`src/data_collection`): `seed/simulated_fill.py` (vé phủ ngày), `seed/combo_components.py` (thành phần combo + phần giá);
  gọi sau `simulated_business.sync` và `sync_combo_items` ở seed, `seed --catalog-only`, job fresh/daily; `fresh_catalog_db.apply_window`
  bỏ qua dòng `demo:fill:` / `demo:combo:` như `demo:business:`; `sync_combo_items` so sánh và ghi kèm `price_share`.
- Tài liệu: `docs/spec/data-collection/schema.md` §3.1, §3.7 (khoá `comboOnly`, `serviceKind`, `comboBaseProductId`, `simulated` mở rộng);
  `docs/spec/MOCK_DATA_SPEC.md` (hai bước mới); `src/data_collection/README.md`.
- Test: unit cho hai module (sinh đủ ngày, dữ liệu thật thắng, tổng `price_share` = giá combo, idempotent); `db/verify.sql` thêm kiểm
  "tổng `price_share` = giá combo" và "`comboOnly` không là search unit".
- Production, trước khi sửa job (người dùng chọn "ghi trước vào DB"): áp migration 0010 bằng `db/migrations/run.py`, chạy hai module
  một lần qua tunnel (`--database-url-env CLOUD_SEED_DATABASE_URL`, có `--dry-run`). Cho tới khi job mới được deploy, lượt chạy job
  02:00 sẽ parse lại `combo_items` và ghi đè liên kết + phần giá của các combo đổi thành phần, và dời vé phủ ngày đã qua theo `crc32`;
  cần chạy lại hai module sau mỗi lượt cho tới khi deploy.
- Backend không cần đổi: tìm kiếm, gợi ý và embed đọc `is_search_unit` từ view; trang chi tiết đọc sản phẩm theo id.
  Bước thanh toán tách combo (chưa có trong code) đọc `combo_items.item_product_id` + `price_share`.
