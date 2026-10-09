# Chuẩn hoá ngày bay của combo trip.com về ISO (lịch trình TP. Hồ Chí Minh không dựng được)

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Yêu cầu "Lên lịch trình 3 ngày tại TP. Hồ Chí Minh, bắt đầu từ ngày 2026-10-08, cho 2 người lớn, đi từ TP. Hồ Chí Minh."
không ra lịch trình. Trace LangSmith `01a119af-3976-7673-a07b-a07671281873` (project `nhat-10-7`):

- `get_recommendations` trả `INVALID_TOOL_RESPONSE` (`retryable: false`);
- `evaluate` chọn `fallback` (`agents/steps/evaluation.py` `_decision`: có lỗi vĩnh viễn + có candidate), dù search đã có 21
  candidate;
- `narrate` báo "skipped (no itinerary)".

Tái hiện trên backend local: đăng nhập minh.anh / quoc.bao / thu.ha, `GET /recommendations?k=10&destination=TP. Hồ Chí Minh`
trả combo `e463e0ff-2902-5a87-b295-92b9d5ff1d0c` có `attributes.returnDate = "15/10"`. Giá trị này sai `format: date` của
`ProductAttributes.returnDate` (`src/shared/contracts/schemas/catalog.yaml`), nên agent bỏ cả response. Khách chưa đăng nhập
(strategy `popular`) không gặp combo này.

Gốc lỗi: `collectors/trip_combos.py` lưu nguyên chữ trên trang ("14/10", không có năm), và `normalise.trip_combo_product`
chép thẳng vào catalog. Phục vụ FR-CAT-01, FR-CAT-04 và đúng hợp đồng; gián tiếp NFR-REL-01, AC-AGT-04.

## File thay đổi

- `src/data_collection/collectors/textutil.py` — sửa: thêm `day_month_iso` và `trip_combo_dates`. Năm lấy từ `dDate`/`rDate`
  của `url` trang tìm kiếm combo; giá trị đã là ISO thì giữ; không khớp thì bỏ khoá; combo khác giữ nguyên.
- `src/data_collection/normalise.py` — sửa: `trip_combo_product` ghi `departDate`/`returnDate` dạng ISO.
- `src/data_collection/seed/load_products.py` — sửa: `convert` chuyển ngày combo trip ở snapshot cũ khi nạp; thêm stat
  `combo trip: ngày bay về ISO`.
- `src/data_collection/fresh_catalog_db.py` — sửa: `apply_window` chuyển ngày combo trip của các dòng đã có trong DB.
- `src/data_collection/tests/test_trip_combos.py` — sửa: thêm `ComboDatesTests` (3 test).
- `src/data_collection/tests/test_seed_load_products.py` — sửa: thêm test loader chuyển snapshot cũ.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: thêm test `apply_window` chuyển một lần, lượt sau không đổi.
- `src/data_collection/README.md` — sửa: ghi chú dưới bảng "Nguồn của từng trường".
- `docs/spec/data-collection/schema.md` — sửa: thêm dòng `departDate`, `returnDate` (combo) ở §3.7.

## Quyết định

- **Sửa phía data, không sửa agent**: người dùng chọn. Không lệch PRD: `data-model.md` §3.1 không quy định ngày của combo,
  hợp đồng đã yêu cầu ISO, nên không cần đề xuất.
- **Năm lấy từ URL, không đoán theo ngày cào.** 33/33 dòng combo trip trong DB local có `dDate`/`rDate` khớp ngày/tháng trên
  trang.
- **Sửa ở ba chỗ**, vì sửa normaliser không chạm được dữ liệu cũ:
  - `normalise` cho các lượt cào mới;
  - `load_products` cho `make demo-db` từ snapshot `2026-09-30`, không phải cắt snapshot mới;
  - `apply_window` cho DB staging.
- Plan ban đầu định sửa `price_attributes`. Đã đổi sang `apply_window`: job cào mới không cào `trip-combos` (chỉ có
  `crawl.py`), nên dòng combo không bao giờ đi qua `price_attributes`; còn `apply_window` chạy trên toàn catalog mỗi lượt.
- Ngày combo vẫn là ngày thật đã cào, không dời vào cửa sổ như vé ngày cố định. Hiện không code nào đọc ngày combo:
  mọi chỗ đọc `returnDate` chỉ xử lý `taxonomy == flight`.
- Khoá `date` của từng chặng trong `outboundFlight`/`inboundFlight` vẫn dạng "14/10": hợp đồng không khai báo khoá này nên
  response không bị bỏ. Không đổi.

## Kiểm tra

- `pytest src/data_collection/tests/test_trip_combos.py tests/test_seed_load_products.py` (`.venv` repo,
  `PYTHONPATH=src:src/data_collection`): 24 passed.
- `test_fresh_catalog_job.py`: 45 passed. Chạy với `curl_cffi` giả trong `sys.modules`, vì `.venv` repo thiếu thư viện này;
  `apply_window` không dùng nó.
- Cả bộ `src/data_collection/tests`, cùng cách giả `curl_cffi`: 521 passed, 22 skipped, 0 failed.
- DB local (`postgres@localhost:5432/vota`): chạy `trip_combo_dates` trên 39 combo trip, có 33 dòng được cập nhật, không
  dòng nào mất khoá. Còn 0 dòng `departDate`/`returnDate` không phải ISO.
- Gọi `/recommendations` ngay sau khi sửa DB vẫn thấy "15/10": backend giữ catalog trong bộ nhớ và chỉ nạp lại mỗi
  `CATALOG_REFRESH_SECONDS` (900 giây). Câu "khoi hanh ngay 15" lúc 04:31:56 UTC (trace `01a119c8-400a-7a52-94f2-3162770273e9`)
  vẫn `fallback` vì lý do này. Sau lượt nạp lại lúc 04:34 UTC, `validate("get_recommendations", …, "response")` cho
  minh.anh / quoc.bao / thu.ha / khach.moi (`/recommendations?k=10&destination=TP. Hồ Chí Minh`): cả 4 ok.
- Chưa chạy lại cả câu yêu cầu qua widget sau khi backend nạp lại.

## Còn lại / rủi ro

- Staging: dòng combo cũ chỉ được chuyển ở lượt chạy đầu tiên của job cào sau khi code này được deploy.
- Agent vẫn bỏ cả response khi một sản phẩm gợi ý sai hợp đồng, rồi `evaluate` chọn `fallback` dù search đủ candidate.
  Dữ liệu sai khác sẽ gây lại đúng lỗi này. Người dùng chưa chọn sửa phía agent.
