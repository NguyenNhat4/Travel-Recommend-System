# Dữ liệu mô phỏng: thành phần combo, vé phủ ngày, tuyến chiều ngược, phòng cho khách sạn chưa có phòng; sửa chuẩn hoá điểm đến và ngày combo

- Ngày: 2026-10-09
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: `feat/mock-combo-ve-bay` (worktree local `~/code/trp-mock-combo`, tách từ `origin/release-mvp-v2 @ 1515020`), fast-forward sang
  `test/newcrawl` và push
- Trạng thái: dang dở — đóng băng theo yêu cầu người dùng (09/10): code, PRD, test xong, đã commit + push lên `test/newcrawl`; chưa ghi
  production vì DB production (10.148.0.2, vẫn là DB backend đang đọc) bật `default_transaction_read_only = on`, chờ VM phân quyền lại
- Phạm vi: data, docs
- Thay thế: `2026-10-09-de-xuat-mo-phong-combo-va-ve-phu-ngay.md` (bước đề xuất)

## Mục tiêu

Người dùng yêu cầu: mock đủ sản phẩm cho thành phần combo (phòng, vé máy bay, vé tham quan… vì thanh toán sẽ tách combo), vé máy bay một
chiều và khứ hồi phủ đủ ngày, rồi "tìm tất cả vấn đề mà data có thể bổ sung, mock thêm cho đầy đủ" để Web và agent tự tốt lên mà không đổi
code của họ. FR-CAT-02, FR-CAT-03, FR-CAT-04, FR-BKG-10, FR-AGT-02, NFR-REL-01.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-CAT-03 năm ngoại lệ mô phỏng; FR-CAT-04 mỗi thành phần trỏ tới sản phẩm, `price_share`.
- `docs/prd/data-model.md` — sửa: ERD `CATALOG_COMBO_ITEMS.price_share`; §3.1 khối vé phủ ngày (+ tuyến chiều ngược), thành phần combo mô
  phỏng, hạng phòng cho khách sạn chưa có phòng; §4.2 `comboOnly`.
- `docs/prd/update-archive/2026-10-09-mo-phong-thanh-phan-combo-va-ve-phu-ngay.md` — thêm (đã áp dụng; chốt "Ok, đã chốt data mock").
- `docs/prd/update-archive/2026-10-09-mo-phong-tuyen-nguoc-va-phong-cho-khach-san.md` — thêm (đã áp dụng; chốt "không sợ lệch prd đâu
  vì đã ok làm data mock là đc").
- `docs/prd/update-archive/2026-10-09-thanh-phan-combo-chi-theo-loai-catalog.md` — thêm (đã áp dụng): chỉ nối / mô phỏng thành phần thuộc
  loại catalog đã có; ăn uống, xe, voucher, spa… là phần đi kèm, không sản phẩm, không `price_share`.
- `docs/prd/update-archive/2026-10-09-gia-le-san-pham-mo-phong-cua-combo.md` — thêm (đã áp dụng): giá lẻ của sản phẩm mô phỏng = giá thật
  nếu có, không thì phần giá combo; tách combo luôn dùng `price_share`.
- `db/vota_schema.sql`, `db/init/01_vota.sql` — sửa (giữ byte-identical): view `catalog.product_meta` loại `comboOnly` khỏi search unit /
  gợi ý; `catalog.combo_items.price_share numeric(14,2) CHECK (>= 0)`.
- `db/migrations/0010_combo_only_va_price_share.sql` — thêm: migration idempotent tương ứng.
- `db/verify.sql` — sửa: thêm "combo price_share sums to price", "comboOnly not searchable".
- `docs/spec/DATABASE_SCHEMA.md` — sửa: ERD, §7, §11 theo DDL mới.
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: bước 6–8 và thứ tự chạy `demo_data`.
- `docs/spec/data-collection/schema.md` — sửa: khoá `comboOnly`, `comboProductId`, `comboBaseProductId`, `serviceKind`, `simulated` (mở
  rộng), `simulatedFrom`, `templateFlight(s)`, `templateReturnFlight`, `reverseOf`.
- `src/data_collection/seed/combo_components.py` — thêm: sản phẩm cho mọi thành phần combo + `price_share`.
- `src/data_collection/seed/simulated_fill.py` — thêm: tuyến chiều ngược + vé phủ ngày (một chiều, khứ hồi).
- `src/data_collection/seed/simulated_rooms.py` — thêm: "Phòng tiêu chuẩn" cho khách sạn có giá mà chưa có phòng, bật lại khách sạn.
- `src/data_collection/seed/demo_data.py` — thêm: chạy bốn bước theo thứ tự trong một transaction; CLI một lần; chưa áp migration 0010
  thì bỏ qua riêng bước thành phần combo (không làm hỏng lượt nạp của job).
- `src/data_collection/seed/database.py` — sửa: gọi `demo_data.sync` sau vé Thương gia ở seed đầy đủ và `--catalog-only`.
- `src/data_collection/fresh_catalog_db.py` — sửa: gọi `demo_data.sync` ở `load_into_db` và `maintain_catalog`; `apply_window` bỏ qua dòng
  `demo:fill/combo/reverse` (vẫn tính ngày vé phủ ngày vào cửa sổ tuyến); parse combo và khớp khách sạn bỏ qua dòng `demo:*`.
- `src/data_collection/normalise.py` — sửa: thành phố của tuyến bay lấy theo sân bay khi tên không khớp alias ("Điện Biên Phủ" → "Điện
  Biên"); `departDate` / `returnDate` của combo Trip thành ngày ISO (từ `dDate` / `rDate` của URL).
- `src/data_collection/collectors/geo.py` — sửa: alias "Tuyên Quang" (tên khách sạn từng thành điểm đến).
- `src/data_collection/README.md` — sửa: lệnh `demo_data`, cờ tắt.
- `src/data_collection/tests/test_combo_components.py`, `test_simulated_fill.py`, `test_simulated_rooms.py`, `test_demo_data.py` — thêm.
- `src/data_collection/tests/test_fresh_catalog_job.py`, `test_quality.py`, `test_trip_combos.py` — sửa: test hook, chuẩn hoá.
- `src/data_collection/tests/fixtures/normalise_sample/expected_products.jsonl` — sửa: 2 combo mẫu nay có ngày đi/về ISO từ URL.
- `history/2026-10-09-mock-thanh-phan-combo-ve-phu-ngay-va-phong.md` — thêm: entry này.
- Ngoài repo / thư mục bị gitignore: sao lưu production `src/data_collection/data/vm-repair-20261009/` (cdp.products tuyến, khách sạn,
  combo; catalog.combo_items; định nghĩa view cũ); DB test `vota_mocktest`, `vota_mocktest2` trên container `wt-seed-postgres-1`.

## Quyết định

- Người dùng chọn (09/10): thành phần vé máy bay trỏ tới tuyến + phủ vé mọi ngày; giá thành phần chia đúng giá combo; sản phẩm mô phỏng
  của combo ẩn khỏi tìm kiếm / gợi ý; ghi DB trước, sửa job sau. "Phòng" = phòng trong thành phần combo.
- Mỗi combo có bộ sản phẩm mô phỏng riêng (giá = phần giá của combo đó). Phòng mô phỏng của combo nằm dưới khách sạn mô phỏng riêng, không
  gắn vào khách sạn thật.
- Dịch vụ ăn uống / xe / voucher / khác không thuộc loại catalog nào: để là phần đi kèm combo (`item_product_id`, `price_share` NULL),
  không sinh sản phẩm (người dùng 09/10; thay cách làm ban đầu là sinh dịch vụ mô phỏng `taxonomy = attraction`). "Voucher" không phải
  loại catalog (golf "voucher" là sản phẩm `golf`).
- Giá lẻ của sản phẩm mô phỏng: giá thật nếu có (khách sạn đã khớp: giá khách sạn; số tiền trong nhãn), không thì phần giá combo. Nguồn
  Vinpearl (377 sản phẩm) và web 09/10 cho thấy Vườn Thú / Khu Trò Chơi / GoKart Vũ Yên chỉ bán theo gói, không có giá lẻ.
- Lần chạy sau lấy lại liên kết gốc từ `comboBaseProductId` / `serviceKind`, đi theo `mergedInto` → idempotent.
- Tồn kho phòng mặc định: không làm — Web, backend, agent đều không đọc trường tồn kho, thêm vào không đổi gì cho họ (đã báo người dùng).
- Không làm giá mô phỏng cho 346 điểm tham quan chưa có giá (nhiều điểm miễn phí; giá giả gây hiểu sai).
- Không gỡ hay lách cờ chỉ đọc của DB production (người dùng: VM đang bảo trì).

## Kiểm tra

- `pytest src/data_collection/tests` (vsf2, `PYTHONPATH=src`): **627 passed, 27 skipped**.
- Bản chép production mới (09/10, `vota_mocktest3`): `demo_data` hai lần (lần hai 0 dòng đổi), `verify.sql` giống hệt trước khi chạy;
  `maintain_catalog` hai lần: md5 `combo_items` không đổi, lần hai 0 dòng sản phẩm đổi. Combo đang bán: 187 thành phần trỏ sản phẩm thật,
  84 trỏ sản phẩm mô phỏng (40 phòng, 37 vé, 9 tuyến/chuyến chiều ngược và tuyến của combo), 174 dịch vụ đi kèm. Phòng mô phỏng: 23 lấy
  giá khách sạn thật, 17 lấy phần giá combo (khách sạn Trip chưa có trong catalog). Quét API 873 dòng mock + combo: 200, sau script sửa
  ngày combo thì 0 lỗi contract.
- Đường job thật: `fresh_catalog_db.maintain_catalog` (bước đầu mỗi lượt cào) chạy hai lần trên bản chép production có mock: md5 của
  `catalog.combo_items` giống hệt trước và sau (liên kết + `price_share` giữ nguyên); phòng, tuyến chiều ngược, sản phẩm combo mô phỏng giữ
  nguyên; 129 vé phủ ngày khoá vì cùng ngày đã có vé thật sau khi cuộn cửa sổ (vé thật thắng); lần hai 0 dòng sản phẩm đổi.
  `demo_data --dry-run` trên DB chưa có 0010: bỏ qua bước combo kèm cảnh báo, các bước khác chạy.
- Bản chép production (09/10) ở `vota_mocktest2`: chạy rooms → fill → combo → fill hai lần; lần hai 0 dòng đổi. `db/verify.sql` giống hệt
  trước khi chạy module (các FAIL còn lại có sẵn từ dữ liệu production: số profile/event, persona). 139/140 tuyến đang bán có vé một chiều
  và khứ hồi đủ 30 ngày; mọi tuyến có chiều ngược đang bán trừ "Cà Mau – Hà Nội"; khách sạn được gợi ý 2.471 → 2.766; tổng
  `price_share` = giá combo ở mọi combo có giá; 0 sản phẩm `comboOnly` là search unit.
- Migration 0010 chạy hai lần trên DB test: lần hai không lỗi.
- Quét API như Web gọi (FastAPI TestClient + `PostgresProductQuery`) trên bản chép có mock: 24.166 `GET /products/{id}` + danh sách con của
  3.045 khách sạn / tuyến đều 200; lỗi contract duy nhất là 33 combo Trip `returnDate` "15/10" (đã sửa ở chuẩn hoá); 504 dòng mock không
  lỗi contract.
- Không đổi contract / mock API → không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Khi VM bảo trì xong và DB ghi được: áp `db/migrations/run.py --database-url <prod>` (0010) rồi
  `python -m data_collection.seed.demo_data --database-url-env CLOUD_SEED_DATABASE_URL --dry-run`, xem số, chạy thật; sửa dữ liệu cũ đang
  có trong DB (33 combo `returnDate` "dd/mm", tuyến/vé "Điện Biên Phủ", khách sạn có điểm đến "Vinpearl Onsen Resort Tuyên Quang") bằng
  `src/data_collection/data/vm-repair-20261009/repair_names_dates.py` (thư mục bị gitignore). Lượt nạp với normaliser mới tự sửa ngày combo
  và tên tuyến/vé (upsert ghi attributes và tên vé máy bay) nhưng không sửa cột `destination` của dòng đã có → khách sạn Tuyên Quang cần script.
- Job chỉ giữ mock sau khi nhánh này được merge + deploy; trước đó lượt nạp ghi đè liên kết combo (sản phẩm mock vẫn còn).
- Tuyến "Cà Mau – Hà Nội" không có chuyến nào và sân bay nguồn ghi VCA: chưa sửa.
- Quy tắc chia giá đã chốt cho kết quả chia gần đều ở combo chỉ có một thành phần biết giá (vd. combo Buggy: vé VinWonders = Kem 260.000).
- Khi DB ghi được: deploy (Backend CI/CD chạy migration 0010; Crawler CI/CD deploy job), chạy `repair_names_dates.py` một lần, rồi bấm
  Index trên monitor (bước "Bảo trì DB" chạy `demo_data`). Khi DB còn chỉ đọc, job cào vẫn cào nhưng bước DB lỗi, không ghi gì (09/10:
  rollback / WAL / `n_mod_since_analyze` không đổi từ lượt 02:00 08/10).
- PR do người dùng mở.
