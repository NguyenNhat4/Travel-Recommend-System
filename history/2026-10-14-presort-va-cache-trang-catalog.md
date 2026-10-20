# Presort thứ tự sắp xếp và nhớ trang /products trong worker

- Ngày: 2026-10-14
- Tác giả: người dùng (Khoa15) / Claude Code
- Nhánh: release-mvp-v2
- Trạng thái: dang dở
- Phạm vi: backend

## Mục tiêu

Giảm chi phí CPU mỗi request `GET /api/v1/products` (đo trước đó ~36–40 ms CPU mỗi request trên VM, container giới hạn 1.5 vCPU, nên trần khoảng 35 rps). Thực hiện đề xuất 1 và 2 trong `docs/plan/2026-10-13-cache-va-presort-catalog.md` (đã được người dùng duyệt trong chat). Hành vi API không đổi: cùng thứ tự, cùng trường, cùng `total`.

## File thay đổi

- `src/backend/app/domain/catalog/listing.py` — sửa: thêm `precompute_orders(items, popularity)` trả về thứ tự sắp xếp của từng `sort` một lần.
- `src/backend/app/domain/catalog/__init__.py` — sửa: export `precompute_orders`.
- `src/backend/app/application/catalog/use_cases.py` — sửa: `ListProducts` tính `_orders` lúc khởi tạo; khi không có `parent_product_id` và có `units`, trang lấy từ `_orders` (lọc giữ thứ tự, không sắp lại); thêm LRU `_cache` theo khoá truy vấn (`_page_from_units`); nhánh cha/DB giữ nguyên, không nhớ.
- `src/backend/app/core/config.py` — sửa: thêm `catalog_response_cache_size` (mặc định 256, 0 = tắt).
- `src/backend/app/main.py` — sửa: `build_catalog` truyền `response_cache_size` vào `ListProducts`. Cache reset mỗi lần RecSys nạp lại catalog.
- `src/backend/tests/unit/domain/test_catalog_listing.py` — sửa: thêm test ngẫu nhiên 1000 lượt (seed cố định) chứng minh `filter(precomputed) == sort(filter(items))`, có khoá trùng, giá trống, hết chỗ, điểm lượt mua.
- `src/backend/tests/unit/application/test_catalog_use_cases.py` — sửa: thêm test cache (trúng, khác khoá không chung trang, thứ tự taxonomy không đổi khoá, size 0 tắt cache, LRU loại mục cũ nhất, request lỗi không vào cache, nhánh cha/DB không cache, catalog dựng lại thì cache rỗng, trang đã sắp sẵn khớp sắp sau khi lọc).
- `docs/plan/2026-10-13-cache-va-presort-catalog.md` — sửa: cập nhật trạng thái đã duyệt và tiến độ.

## Quyết định

- Presort tận dụng `sort(filter(items)) == filter(sort(items))` vì sắp xếp ổn định: lọc giữ nguyên thứ tự tương đối nên kết quả giống hệt. Test ngẫu nhiên khoá đúng điều này.
- Không có điều kiện lọc thì dùng thẳng danh sách đã sắp sẵn (không copy, không sửa).
- Cache theo khoá `(destination, taxonomy đã sort/unique, available_only, sort, limit, offset, diversify)`. `taxonomy` không đưa vào thứ tự khoá nên `a,b` và `b,a` dùng chung một mục.
- Nhớ theo từng worker, không dùng Redis và không đổi header HTTP. Cache-Control đã có sẵn trên `/products` (`public, max-age=60, s-maxage=300`) và không đổi.
- Không đưa nhánh `parent_product_id` (tầng con) và nhánh DB vào cache, vì chúng không có `units` sẵn và dữ liệu có thể đổi theo thời gian.
- Số đo trên máy dev (in-process, localhost, không qua mạng): cách cũ ~17,8 ms; presort không cache ~0,29 ms; cache hit ~0,023 ms. Đây là số của một request trong bộ nhớ, không phải số p95 trên staging.

## Kiểm tra

- `python3 -m pytest -q src/backend/tests/unit/domain/test_catalog_listing.py src/backend/tests/unit/application/test_catalog_use_cases.py src/backend/tests/architecture/test_import_rules.py -p no:cacheprovider` → 68 passed.
- Chưa chạy toàn bộ unit test backend. Chưa chạy `validate_contract.py` vì không đổi contract.
- Chưa deploy. Staging vẫn chạy bản cũ. Số liệu trên staging chỉ có từ run ghi trong `history/2026-10-14-stress-doc-lien-tuc-den-930.md`, và run đó chạy trên bản cũ.

## Còn lại / rủi ro

- Chưa deploy và chưa đo lại trên VM. Cần đo p95 sau khi deploy, so với run staging trước.
- Cache dựa trên dữ liệu `units` đã nạp: RecSys nạp lại catalog thì cache mới được dựng lại. Dữ liệu catalog chỉ đổi theo chu kỳ nạp 15 phút, nên `max-age` và cache trong worker không lệch nhau đáng kể.
- Còn trong kế hoạch, chưa làm: header contract cho `/destinations` và `/recommendations` (bước 4), metric hit/miss đầy đủ (bước 2.4). Cloudflare cache rule là việc của người vận hành, không do agent làm.
- Ngưỡng 256 trang chọn theo ước lượng, chưa đo RSS thật trên VM. Cần đo trước khi tăng.
