# Lọc theo ngày ở tìm kiếm: loại khách sạn kín lịch, vé ngày blackout, sản phẩm ngoài cửa sổ

- Ngày: 2026-10-07
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-07 ("tôi chốt" sau khi xem đề xuất)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.1 FR-CAT-03 (vai trò của lịch `attributes.availability`), §1.2 FR-SRC-03 (bộ lọc ngày), §3 (thêm AC-SRC-03)
- Mã FR/NFR: FR-SRC-03, FR-CAT-03; mới: AC-SRC-03 (cần cấp mã)

## Lý do

Tấm tìm kiếm ở `/hotels`, `/experiences`, `/combos` có ô ngày và số khách, nhưng hiện chỉ điền sẵn hộp đặt ở trang chi tiết, không lọc kết quả (Backend không đọc `travelContext.checkIn/checkOut`). Người dùng yêu cầu những gì điền ở form phải là tiêu chí tìm. FR-SRC-03 đã liệt kê "Ngày khởi hành / Thời gian nhận phòng" là bộ lọc, nhưng chưa có hiện thực.

Người dùng chọn (2026-10-07) lọc mạnh: loại cả khách sạn kín lịch trong khoảng ngày đã chọn, không chỉ loại sản phẩm ngoài cửa sổ đặt. Chọn này lệch FR-CAT-03 hiện hành, vốn ghi lịch `attributes.availability` "chỉ để tham khảo, không dùng để chặn", vì ký tự `0` có thể chỉ là "nguồn không có giá ngày đó" chứ chưa chắc hết phòng. Vì vậy cần đề xuất này.

## Nội dung đề xuất

**1. `requirements.md` FR-SRC-03, gạch đầu dòng "Ngày khởi hành / Thời gian nhận phòng".**

- Hiện tại: "Ngày khởi hành / Thời gian nhận phòng."
- Thay bằng: "Ngày khởi hành / Thời gian nhận phòng: tham số `travelContext.checkIn`/`checkOut` của `POST /search` là bộ lọc cứng (chỉ khi gửi cả hai hoặc `checkIn` cho loại dịch vụ một ngày). Sản phẩm không dùng được vào khoảng ngày đó bị loại khỏi kết quả, quy tắc ở FR-CAT-03. Thiếu dữ liệu thì giữ lại, không loại. Số khách (`travelContext.guests`) cũng là bộ lọc cứng sức chứa. Tấm tìm kiếm ở trang danh mục gửi cả hai."

**2. `requirements.md` FR-CAT-03, thêm một gạch đầu dòng sau gạch về lịch khách sạn.**

- Thêm: "Tìm kiếm với ngày (FR-SRC-03) dùng lịch như sau, độc lập với việc đặt chỗ: (a) khách sạn: ngày nhận và số đêm phải theo luật đặt phòng ở trên (từ hôm nay đến hôm nay + 3 tháng, 1–30 đêm); và phải có ít nhất một hạng phòng đang bán mà lịch `attributes.availability` đánh dấu mở (`1`) ở mọi đêm trong `[checkIn, checkOut)`; khách sạn mà mọi hạng phòng đều có ít nhất một đêm `0` thì bị loại; đêm nằm ngoài khoảng lịch (30 ngày kể từ `availability.from`) hoặc hạng phòng không có lịch thì coi là chưa biết và giữ; (b) vé tham quan, sân golf: ngày dùng (`checkIn`) nằm trong `[available_from, available_to]` và ký tự lịch của ngày đó không phải `0`; (c) combo: ngày bắt đầu (`checkIn`) nằm trong `[available_from, available_to]`, không có lịch ngày; (d) vé máy bay không lọc theo ngày ở `/search`. Lịch vẫn **không** chặn đặt chỗ: người dùng mở thẳng trang chi tiết và đặt ngày kín lịch vẫn được kiểm theo luật đặt phòng như hiện nay, nên một khách sạn bị loại khỏi tìm kiếm vẫn đặt được nếu vào trực tiếp."

**3. `requirements.md` §3, thêm hàng AC.**

- Thêm: "AC-SRC-03 | Người dùng ở `/hotels` chọn Nha Trang, nhận phòng ngày X, 2 người lớn, bấm Tìm | Kết quả chỉ gồm khách sạn Nha Trang có hạng phòng đặt được ngày X và đủ chỗ cho 2 người; khách sạn mà mọi hạng phòng đều kín lịch ngày X không có trong danh sách; khách sạn chưa biết lịch hoặc sức chứa vẫn có."

Không đổi: luật kiểm ngày khi đặt phòng (FR-CAT-03, `DATE_OUT_OF_RANGE`), FR-BKG-08, `/search` không có lọc điểm đến, các FR/NFR khác.

## Thay đổi source sau khi chốt

- Contract (làm trước, 1.19.0 additive): `src/shared/contracts/schemas/search.yaml` (`TravelContext.checkIn/checkOut` có hiệu lực, thêm họ `date` vào `applied`/`emptyReason` của `queryPlan`, khóa `appliedFilters.hard.checkIn/checkOut`), `paths/search.yaml`, `openapi.yaml` (version), mock `src/shared/mocks/search/`; chạy `validate_contract.py`.
- Backend: `src/backend/app/api/v1/routes/search.py` (nhận `checkIn`/`checkOut`, 400 khi `checkOut <= checkIn`), `application/search/use_cases.py`, `domain/search/query_plan.py`, `application/ports/unit_index.py` (mask theo ngày), `domain/catalog/unit_attributes.py` (cửa sổ và lịch theo đơn vị, theo hạng phòng con), hàm miền dùng chung với `domain/booking/pricing.py` cho luật cửa sổ khách sạn; test cạnh `test_search_v116_knobs.py`, `test_unit_index_mask.py`, `test_search_route.py`, `test_search_contract.py`.
- Frontend: `src/frontend/src/services/search.ts` (gửi `travelContext` gồm ngày và số khách), `features/catalog/landing/LandingResults.tsx`, `components/search/GroupResults.tsx`; bỏ chú thích "không lọc theo ngày".
- Tài liệu: `docs/spec/hop-dong-tich-hop-search-recommendation.md` (§2.2, §2.5, §2.7 dòng `available: true`), `docs/spec/hop-dong-tich-hop-frontend.md` (§4.1a), `docs/spec/product.md`, `src/frontend/README.md`, `src/frontend/src/types/api.gen.ts` (sinh lại).

## Rủi ro đã biết

- Số `0` trong lịch phòng có thể chỉ là "nguồn không có giá ngày đó": khách sạn còn phòng thật có thể bị loại khỏi tìm kiếm.
- Lịch chỉ phủ 30 ngày kể từ ngày nạp, trong khi khách sạn đặt trước được 3 tháng: ngày xa hơn thì không lọc được theo lịch.
- Tìm kiếm và đặt phòng không còn cùng một luật (tìm loại, đặt vẫn cho).
