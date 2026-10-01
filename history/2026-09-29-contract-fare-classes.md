# Contract 1.9.0: `fareClasses` — hạng vé của một hành trình bay

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: contract, backend, frontend (type), docs

## Mục tiêu

Team FE đưa mẫu `fareClasses: [{code, name, price, carryOnKg, checkedKg, mealIncluded, changeRule, soldOut}]`.

Người yêu cầu chốt (2026-09-29):
- "giữ tên FE, thêm trường": thêm `productId`, `currency`, `priceValidUntil` và trạng thái báo giá; các trường chưa biết
  để `null`;
- "ok làm 1 + 4 và sửa contract fareClasses luôn":
  - (1) giữ khứ hồi trip.com (không ghi hạng);
  - (4) chỉ trả hạng có dữ liệu thật, không tạo giá thương gia.

Bối cảnh: booking.com ẩn kết quả vé máy bay với trình duyệt tự động (người yêu cầu mở cùng URL thì có danh sách). Agent
không né cơ chế chống bot, nên hiện chưa có nguồn hợp lệ cho vé thương gia.

Phục vụ FR-CAT-01, FR-CAT-03, FR-AGT-04 (grounding).

## File thay đổi

- `src/shared/contracts/schemas/catalog.yaml` — sửa:
  - thêm schema `FareClass`:
    - bắt buộc `productId`, `code` (ECO/PRE/BUS/FST/null), `name`, `price`, `currency`, `availabilityStatus`;
    - nullable `priceValidUntil`, `soldOut`, `carryOnKg`, `checkedKg`, `mealIncluded`, `changeRule`;
  - thêm `ProductSummary.fareClasses` (optional; `ProductDetail` kế thừa).
- `src/shared/contracts/openapi.yaml` — sửa: `info.version` 1.8.0 → 1.9.0 (thêm, tương thích ngược); component `FareClass`.
- `src/backend/app/domain/catalog/fares.py` — thêm: hàm thuần `itinerary_key`, `fare_class`, `fare_classes_by_product`.
  - Khoá hành trình: `tripType`, tuyến cha, số hiệu chuyến, giờ đi; khứ hồi thêm chuyến / giờ về.
  - Không gồm hạng / giá.
- `src/backend/app/domain/catalog/__init__.py` — sửa: xuất `fare_classes_by_product`, `is_fare_variant`.
- `src/backend/app/application/catalog/views.py` — sửa: `product_summary` / `product_detail` nhận `fare_classes`, chỉ thêm
  khoá khi có.
- `src/backend/app/application/catalog/use_cases.py` — sửa:
  - `ListProducts` với `parentProductId` gom trên mọi chuyến của tuyến, **trước khi phân trang**;
  - `GetProductDetail` của chuyến bay gom với các chuyến anh em;
  - "hôm nay" theo giờ Việt Nam để xét `priceValidUntil`.
- `src/backend/app/main.py` — sửa: `version="1.9.0"`.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract (`generate:api-types`); CI FE bắt `git diff` của file này.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: dòng `fareClasses` ở §2.2 và mục §2.2.1.
- `src/backend/tests/unit/domain/test_fare_classes.py` — thêm, 4 test:
  - gom đủ hạng của cùng hành trình, thứ tự ECO, BUS, chưa rõ hạng;
  - khứ hồi là hành trình riêng; hết hạn là `EXPIRED` và `soldOut` vẫn null;
  - trường chưa biết là null, sản phẩm khác không có `fareClasses`;
  - cùng chuyến khác ngày, khứ hồi khác ngày về là hành trình khác.
- `src/backend/tests/contract/test_fare_classes_contract.py` — thêm, 4 test qua FastAPI:
  - danh sách tầng con có `fareClasses` khớp contract;
  - gom trước khi phân trang (trang một dòng vẫn đủ hạng);
  - trang chi tiết có `fareClasses`, sản phẩm khác không có;
  - payload `FareClass` khớp schema (còn hạn và hết hạn).
- `history/2026-09-29-contract-fare-classes.md` — thêm: entry này.

## Quyết định

- **Trạng thái báo giá dùng lại enum `AvailabilityStatus`** (`AVAILABLE`, `EXPIRED`, `NOT_CHECKED`) với tên
  `availabilityStatus`, như `ProductSummary.availabilityStatus`, thay cho `availability: available|expired|unknown` đã đề
  xuất. Nghĩa giữ nguyên, tránh thêm từ vựng mới.
- **Giữ tên trường FE**; `soldOut` nullable: `null` = chưa biết. Báo giá hết hạn không đổi thành `soldOut`.
- **Không đổi `AddCartItemRequest`**, giỏ, đơn, CDP: mỗi hạng là một `productId`.
- **Vé trip.com:** `code: null`, nhãn "Giá rẻ nhất" (không suy hạng). Hành lý / suất ăn / đổi vé: chưa nguồn nào có số liệu
  dạng kg hoặc quy tắc → `null`.
- **Không có fixture mock mới**; test contract kiểm payload thật của backend.

## Kiểm tra

- `validate_contract.py`: PASS (89 schema, thêm `FareClass`; 64 fixture cũ vẫn pass).
- Test fareClasses + catalog + kiến trúc: **53 passed**, sau khi thêm test ngày khác: 8 test fareClasses pass.
- **Kiểm test bắt được lỗi** (tắt từng hành vi rồi khôi phục, `cmp` sạch):
  - danh sách không gom → 2 test contract fail;
  - khoá bỏ giờ đi → test "khác ngày" fail. Lần đầu **không** bị bắt, nên đã thêm test đó;
  - khoá bỏ chiều về → fail.
- Frontend (node bundled):
  - `generate:api-types` thêm 50 dòng;
  - `tsc --noEmit` ok;
  - vitest **128/128**;
  - eslint exit 0.
- Toàn bộ test backend (vsf2), chạy lại sạch sau khi cây ổn định: **672 passed, 19 skipped** (664 trước đó + 8 test
  fareClasses).
- `data_collection` `pytest tests`: 411 passed, 3 skipped (không đổi).

## Còn lại / rủi ro

- Giao diện FE chưa đọc `fareClasses` (việc của team FE). `FlightSummary` hiện đọc `attributes`.
- Chưa có báo giá thương gia; `fareClasses` hiện chỉ có một phần tử "Giá rẻ nhất" cho mỗi hành trình trip.com.
- Báo giá trip.com có hạn `priceValidUntil` (vd. 30/09): cần cào lại hằng ngày để không thành `EXPIRED`.
- Chưa push.
