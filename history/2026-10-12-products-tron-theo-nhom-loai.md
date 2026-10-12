# GET /products: trộn theo nhóm loại (`diversify=taxonomy`) và lọc nhiều taxonomy

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành
- Phạm vi: backend
- Liên quan: `2026-10-12-contract-1-25-0-products-diversify.md` (contract đi trước), `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md`

## Mục tiêu

Hiện thực hai tham số của contract 1.25.0 cho `GET /products`:

- `diversify=taxonomy`: trộn danh sách popular theo nhóm loại, để tab "Tất cả" của kệ Phổ biến ở trang chủ không còn toàn vé máy bay.
- `taxonomy` nhiều giá trị (`attraction,golf`): cho tab "Vé tham quan" gồm cả golf.

Phục vụ FR-REC-01 và chỉ số Diversity ở `docs/prd/test-plan.md` §2.5.

## File thay đổi

- `src/backend/app/domain/catalog/listing.py` — sửa:
  - `filter_items` nhận một loại hoặc một tập loại;
  - thêm `DIVERSIFY_MODES`, `DIVERSIFY_GROUPS` (hotel; attraction + golf; combo; flight) và hàm thuần `interleave_by_taxonomy`.
- `src/backend/app/domain/catalog/__init__.py` — sửa: export ba tên mới.
- `src/backend/app/application/catalog/use_cases.py` — sửa: `ListProducts.__call__` nhận `taxonomy: str | Sequence[str]` và `diversify`, kiểm hợp lệ (400 `fields`), trộn sau khi sắp xếp và trước khi cắt trang.
- `src/backend/app/api/v1/routes/catalog.py` — sửa: thêm query `diversify`; tách `taxonomy` theo dấu phẩy.
- `src/backend/tests/unit/domain/test_catalog_listing.py` — sửa, thêm 7 test: lọc nhiều loại, nhóm phủ đủ enum, round-robin đúng thứ tự, golf chung nhóm attraction, là hoán vị và giữ thứ tự trong nhóm, một nhóm thì không đổi, loại ngoài bảng xếp cuối.
- `src/backend/tests/unit/application/test_catalog_use_cases.py` — sửa:
  - thêm 7 ca vào test 400 tham số hoá;
  - thêm test hai trường lỗi cùng lúc (`sort`, `diversify`);
  - lọc hợp nhiều loại, bỏ trùng;
  - trộn trước khi phân trang: hai trang 4 món ghép lại bằng danh sách 8 món;
  - một nhóm thì giữ thứ tự popular.
- `src/backend/tests/contract/test_catalog_contract.py` — sửa: tham số khai đúng trong contract, `diversify` qua HTTP đúng thứ tự nhóm, `taxonomy=attraction,golf` và bản `%2C`, 400 cho `diversify` đi cùng sort giá và cho `taxonomy=hotel,`.
- `history/2026-10-12-products-tron-theo-nhom-loai.md` — thêm: entry này.

## Quyết định

- **Tách dấu phẩy ở route** (serialization HTTP `style: form`). Use case nhận `str` hoặc dãy, nên tool trong tiến trình của trợ lý (`engine_tools.py`) vẫn truyền một chuỗi như cũ, và test kwargs `test_itinerary_engine_tools.py:444-463` giữ nguyên.
- **Tham số route giữ kiểu `str`**, không dùng `Literal`. Lý do: FastAPI sẽ trả 422, contract chỉ khai 400.
- **Kiểm taxonomy chặt:** không trim, không đổi hoa thường. Đoạn rỗng hoặc giá trị lạ trả 400; giá trị trùng bỏ qua.
- **Taxonomy ngoài bảng nhóm** (giá trị enum thêm sau này) vào nhóm cuối, để kết quả luôn là hoán vị.
- **Agent không gửi được `diversify`:** allow-list của gateway không có tham số này, và đó là chủ ý.
- **Không đổi gì khác:** ngữ nghĩa `sort=popular` và công thức popularity ([C7]) giữ nguyên.

## Kiểm tra

- `pytest` các file: test catalog domain/use case/contract, `test_itinerary_engine_tools.py`, `src/backend/tests/architecture`: 108 passed.
- Toàn bộ `PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false python -m pytest -q -p no:cacheprovider src/backend/tests`: 2852 passed, 36 skipped.

## Còn lại / rủi ro

- Frontend dùng hai tham số này ở bước kế tiếp.
- Mỗi worker tự dựng popularity mỗi 900 s, không đồng bộ với worker khác, nên phân trang qua nhiều worker có thể gặp hai bảng xếp hạng khác nhau. Lỗi này có từ trước; kệ trang chủ không phân trang.
