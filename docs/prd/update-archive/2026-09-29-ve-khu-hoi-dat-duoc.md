# Vé máy bay khứ hồi đặt được, không thêm `level`

- Ngày: 2026-09-29
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-09-29 ("ok đã chốt")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.1 (FR-CAT-01, FR-CAT-02); `docs/prd/data-model.md` §3.1
- Mã FR/NFR: FR-CAT-01, FR-CAT-02, FR-CAT-03; liên quan FR-AGT-04 (grounding: thẻ có `productId` thật và giá thật)

## Lý do

- `docs/prd/user-flow.md` §1.1 (bước 4) và wireframe §4.1 có **"Thẻ vé máy bay khứ hồi"** sau khi đặt phòng. Catalog chưa có
  sản phẩm nào như vậy:
  - tuyến bay (`level: route`) chỉ có `unitPrice` một chiều và một con số `attributes.roundTripFrom` (khứ hồi rẻ nhất);
  - chuyến bay (`level: flight`) chỉ có giá một chiều.
- Người dùng yêu cầu vé khứ hồi **phải đặt được** (2026-09-29).
- Dữ liệu lịch sử đã có cấu trúc khứ hồi để chuẩn hoá; báo giá mới và hạng vé vẫn cần bổ sung:
  - mỗi trang tuyến của trip.com trả **10 hành trình khứ hồi**: chuyến đi (số hiệu, ngày giờ), chuyến về (số hiệu, ngày giờ),
    giá tổng;
  - collector đã lưu vào interim (`roundTripLegs`) nhưng bước chuẩn hoá bỏ qua;
  - kho dữ liệu cũ có 284 bản ghi lịch sử của 113 tuyến; giá cũ cần ghi rõ thời điểm quan sát, không coi là giá hiện tại.
- Người dùng chọn **không thêm giá trị mới cho `level`** (2026-09-29). Thêm level phải sửa đồng bộ enum trong contract, view
  `catalog.product_meta` (+ migration), `domain/catalog/models.py` và `hasVariants` ở frontend.

## Mô hình đề xuất

Mỗi hành trình khứ hồi là **một sản phẩm `taxonomy: flight`, `level: flight`**, con của tuyến (`parentProductId` = tuyến đi),
thêm `attributes.tripType = "roundTrip"`.

| Trường | Giá trị |
|---|---|
| `unitPrice` | giá tổng khứ hồi **cho một người lớn** (`attributes.priceBasis = "per_person"`); `quantity` khi đặt = số khách |
| `availableFrom` = `availableTo` | **ngày đi** (giờ Việt Nam), như quy tắc chuyến bay "from = to = ngày bay" |
| `attributes` | `tripType: "roundTrip"`; chuyến đi (như chuyến một chiều: `flightNumber`, `airline`, `originAirport`, `destinationAirport`, `departureAt`, `arrivalAt`…); chuyến về trong `returnFlight` cùng các khoá đó; `returnDate`; `stayDays`; `priceValidUntil` |
| `sourceRef` | `trip:roundtrip:<đi>-<đến>:<số hiệu đi>:<ngày đi>:<số hiệu về>:<ngày về>:<hạng-hoặc-unknown>` |

Hệ quả, **không phải sửa**:

- **Contract:** `level` giữ nguyên 4 giá trị; `ProductAttributes` có `additionalProperties: true`.
- **DDL / view:** `level: flight` sẵn là `is_bookable = true`, `is_search_unit = false`, như chuyến một chiều.
- **Backend giỏ / đơn:**
  - `usingDate` = ngày đi; kiểm `DATE_OUT_OF_RANGE`, giá và event `purchase` dùng lại như chuyến một chiều;
  - ngày về nằm trong sản phẩm, **không** ghi vào `using_date_to` (cột này được đọc ngược thành `nights`, chỉ dành cho khách
    sạn);
  - `line_total` = `unitPrice × quantity` như mọi loại khác khách sạn.
- **Search / Recommendation:** tầng con không có vector, không đổi.

Chuyến một chiều hiện có giữ nguyên. Chúng được phân biệt bằng `tripType` vắng mặt, hoặc `"oneWay"` nếu muốn ghi rõ (xem
"Cần chốt" 3).

## Nội dung đề xuất (sửa PRD)

**`docs/prd/requirements.md` §1.1, FR-CAT-01**

- Hiện tại: "…Chuyến bay (`flight_route`, `flight_instance`)…"
- Thay bằng: "…Chuyến bay (`flight_route`, `flight_instance`; `flight_instance` gồm chuyến một chiều và hành trình khứ hồi
  `attributes.tripType = "roundTrip"` có chuyến đi, chuyến về và giá tổng)…"

**`docs/prd/requirements.md` §1.1, FR-CAT-02**, gạch đầu dòng thứ nhất, thêm câu:

- "Hành trình khứ hồi là một `flight_instance` đặt được: ngày sử dụng là ngày đi, ngày về cố định theo sản phẩm."

**`docs/prd/data-model.md` §3.1**, sau ví dụ "Chuyến bay (`flight_instance`)", thêm ví dụ:

```json
{
  "level": "flight",
  "tripType": "roundTrip",
  "parentProductId": "<tuyến đi>",
  "flightNumber": "VU1270",
  "airline": "Vietravel Airlines",
  "originAirport": "CXR",
  "destinationAirport": "HAN",
  "departureAt": "2026-10-10T08:55:00+07:00",
  "returnDate": "2026-10-13",
  "stayDays": 3,
  "returnFlight": {
    "flightNumber": "VU1271",
    "airline": "Vietravel Airlines",
    "originAirport": "HAN",
    "destinationAirport": "CXR",
    "departureAt": "2026-10-13T06:10:00+07:00"
  },
  "priceBasis": "per_person",
  "priceValidUntil": "2026-09-30"
}
```

## Quyết định đã chốt

1. **Khoá sản phẩm.** Đề xuất: một sản phẩm cho mỗi hành trình **có ngày cố định** (cặp chuyến + ngày đi + ngày về), vì giá
   chỉ đúng cho đúng cặp ngày đó.
   - Hệ quả: mỗi lượt cào có thể thêm tới 10 × số tuyến sản phẩm mới.
   - Hành trình đã qua ngày đi hết hạn theo cửa sổ ngày hiện có (bảo trì DB cuộn cửa sổ).
   - Cách khác: gộp theo cặp chuyến, giữ ngày rẻ nhất (như chuyến một chiều đang làm). Ít sản phẩm hơn, nhưng `usingDate`
     khác ngày đó thì giá và ngày về không còn đúng.
2. **Giá một người lớn.** Suy ra từ trang trip.com (giá hiển thị theo người lớn), chưa kiểm hết. Sẽ kiểm trên raw trước khi
   chuẩn hoá; nếu là giá cả nhóm thì đổi `priceBasis` thành `per_package`.
3. **Chuyến một chiều có ghi `tripType: "oneWay"` không.** Đề xuất: có, để frontend và agent lọc rõ ràng; không đổi gì
   khác của chuyến một chiều.
4. **Phạm vi phía hiển thị.** Đề xuất: đợt này làm dữ liệu (chuẩn hoá, spec, test) và thẻ khứ hồi ở trang chi tiết tuyến /
   giỏ hàng. Agent chọn vé khứ hồi trong lịch trình để đợt sau.

## Thay đổi source sau khi chốt

- `src/data_collection/normalise.py`:
  - `trip_route_products` sinh sản phẩm khứ hồi từ `roundTripLegs`: ghép chặng `out` / `in` theo thứ tự trang, giá ở
    chặng `out`;
  - lọc hành trình thiếu chặng / giá / ngày;
  - chuyến một chiều thêm `tripType: "oneWay"` (nếu chốt mục 3).
- `docs/spec/data-collection/schema.md` §3.7: thêm các khoá `tripType`, `returnFlight`, `returnDate`, `stayDays`,
  `priceValidUntil`.
- `src/shared/contracts/schemas/catalog.yaml`: chỉ thêm mô tả các khoá mới trong `ProductAttributes` (không đổi enum, không
  bắt buộc).
  - Chạy `python3 src/shared/contracts/tests/validate_contract.py`.
- `src/frontend`: thẻ khứ hồi (hai chặng, ngày đi / về, giá tổng, số khách) ở danh sách chuyến của tuyến và trong giỏ.
- Test:
  - chuẩn hoá: ghép chặng, `sourceRef` ổn định, giá / ngày;
  - `db/verify.sql` nếu có thêm kiểm;
  - backend: thêm vào giỏ một sản phẩm khứ hồi với `usingDate` = ngày đi → OK, khác ngày → `DATE_OUT_OF_RANGE`.
- Chuẩn hoá lại kho cũ (284 bản ghi lịch sử, 113 tuyến), nạp lại catalog, index. Tầng con không nhúng vector, nên không tốn Cohere.
- Plan chi tiết: `docs/plan/2026-09-29-ve-khu-hoi-dat-duoc.md` (viết sau khi chốt).

## Bổ sung đã chốt trong phiên kiểm tra pipeline

- Giữ `level: flight`, 13 cột và các ID cũ. Một biến thể đặt được ứng với hành trình, ngày cố định và hạng vé có bằng chứng từ nguồn.
- Hạng `ECONOMY` / `BUSINESS` đặt tại `attributes.cabinClass`; thiếu bằng chứng thì để trống, không suy hạng hay nhân giá.
- Vé mới có `fixedDepartureDate: true`; loader không dời ngày của báo giá cố định. `unitPrice` là tổng hành trình cho một người lớn; không dùng `using_date_to` của khách sạn cho ngày về.
- Dữ liệu Trip cũ không có hạng vé. Có thể chuẩn hoá khứ hồi từ `roundTripLegs`, nhưng phải bổ sung báo giá có hạng từ nguồn; không cần cào lại toàn bộ 11k catalog.
- Thực hiện bằng cập nhật cộng thêm, không reset DB VM. Chưa thực hiện triển khai VM trong phiên sửa code.
