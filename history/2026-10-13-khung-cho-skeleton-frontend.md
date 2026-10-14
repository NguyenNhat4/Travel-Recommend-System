# Khung chờ (skeleton) cho mọi vùng đang tải ở Web

- Ngày: 2026-10-13
- Tác giả: Pham Nguyen Dang Khoi / Claude Code (hai phiên: phiên đầu làm phần lớn, phiên sau rà lại, làm nốt, test và kiểm trên trình duyệt)
- Nhánh: feat/fe-skeleton-mvp2 (tạo từ origin/release-mvp-v2 8f4877fb)
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Người dùng hỏi khối gợi ý RecSys ở trang chủ chưa có khung chờ, và yêu cầu bổ sung khung chờ cho mọi chỗ còn thiếu, test đầy đủ.
Căn cứ: `docs/spec/product.md` §4.0 (`Skeleton` giữ đúng khung hình nội dung thật) và các dòng "Đang tải" ở §4.1.5 (Home: khung 4 thẻ
cho ①), §4.2.4 (Search: skeleton `row`), §4.3.4 (Product detail), §4.6.3 (Confirmation: khối gợi ý), `docs/prd/requirements.md`
FR-BKG-14 ("Có trạng thái đang tải"), khối gợi ý phục vụ FR-REC-01..03. Không có mã FR/NFR riêng cho khung chờ; thay đổi chỉ hiện thực
đúng điều spec đã ghi, không lệch PRD.

## File thay đổi

- `src/frontend/src/components/common/Skeleton.tsx` — thêm: `SkeletonBlock`, `SkeletonStatus` (vùng `role="status"` có tên, `aria-busy`), `ProductCardSkeleton` (thẻ `grid`), `ProductRowSkeleton` (thẻ `row`).
- `src/frontend/src/components/home/HomeView.tsx` — sửa: khối ① Gợi ý hiện 4 thẻ khung + chỗ nút "Vì sao" khi đang tải mà chưa có thẻ; đã có thẻ thì giữ thẻ, mờ khi tải lại.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: khung trang chi tiết, khung danh sách hạng phòng / chuyến bay con, khối "Phổ biến" và "Gợi ý cho chuyến đi".
- `src/frontend/src/components/detail/RoomCard.tsx` — sửa: thêm `RoomCardSkeleton`.
- `src/frontend/src/components/cart/CartView.tsx` — sửa: khung giỏ hàng thay vòng xoay.
- `src/frontend/src/components/checkout/CheckoutView.tsx` — sửa: khung trang thanh toán thay vòng xoay; export `CheckoutSkeleton` để làm fallback của trang.
- `src/frontend/src/components/checkout/ServicesStep.tsx` — sửa: "Điều kiện vé trẻ em" hiện khung ba dòng thay chữ "Đang tải…".
- `src/frontend/src/components/confirmation/ConfirmationView.tsx` — sửa: khung trang đơn và khối gợi ý sau mua.
- `src/frontend/src/components/search/SearchView.tsx` — sửa: dòng đếm kết quả hiện khung thay vòng xoay; thêm `SearchViewSkeleton` (khung cả trang: ô tìm kiếm, tiêu đề, tab, ba hàng nhóm).
- `src/frontend/src/components/search/GroupShelf.tsx` — sửa: thêm `ShelfTilesSkeleton` (bốn ô của một hàng), hàng đang tải thành `SkeletonStatus` có tên "Đang tải <nhóm>" thay `div aria-busy` không tên.
- `src/frontend/src/components/search/GroupResults.tsx` — sửa: tab nhóm hiện 5 `ProductRowSkeleton` (product.md §4.2.4) thay ba khối xám `animate-pulse` không tên.
- `src/frontend/src/components/assistant/TripDetailsForm.tsx` — sửa: chip điểm đến dạng khung khi đang tải.
- `src/frontend/src/features/flights/results/FlightCard.tsx` — sửa: thêm `FlightCardSkeleton`, `FlightDateStripSkeleton`.
- `src/frontend/src/features/flights/results/FlightResultsView.tsx` — sửa: danh sách chuyến dùng khung dải ngày + 3 thẻ chuyến, vùng `role="status"` "Đang tải chuyến bay".
- `src/frontend/src/features/bookings/BookingCard.tsx` — sửa: thêm `BookingCardSkeleton`.
- `src/frontend/src/features/bookings/BookingHistoryView.tsx` — sửa: lịch sử đơn dùng 3 `BookingCardSkeleton` trong `SkeletonStatus`; tách `PageTitle`, thêm `BookingHistorySkeleton` (tiêu đề thật + thanh lọc khung + 3 thẻ đơn khung) làm fallback của trang.
- `src/frontend/src/app/(storefront)/search/page.tsx`, `checkout/page.tsx`, `profile/booking_history/page.tsx` — sửa: `Suspense fallback={null}` thành khung trang tương ứng, để lúc tải cứng trang (trước khi đọc được `useSearchParams`) không còn trống.
- `src/frontend/src/features/itinerary/widget/WidgetHistory.tsx` — sửa: lịch sử hội thoại hiện các dòng khung thay chữ.
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: bản đồ lộ trình đang tải hiện khung.
- `src/frontend/src/features/itinerary/widget/WidgetProductDetail.tsx` — sửa: mô tả chi tiết và khung lần đầu dùng `SkeletonBlock` thay `animate-pulse`.
- `src/frontend/src/features/profile/AccountShell.tsx` — sửa: giữ chỗ thẻ người dùng khi phiên đang khôi phục.
- `src/frontend/src/features/profile/ProfileView.tsx` — sửa: khung hồ sơ khi phiên đang khôi phục thay vòng xoay.
- `src/frontend/tests/unit/skeleton.test.tsx` — thêm: test component dùng chung.
- `src/frontend/tests/unit/pageFallbacks.test.tsx` — thêm: view của trang treo trong Suspense thì ba trang hiện khung trang.
- `src/frontend/tests/unit/{accountShell,bookingHistoryView,cartView,checkoutView,confirmationView,flightResultsView,homeView,productDetailView,profileView,searchView,tripDetailsForm,widgetHistory}.test.tsx` — sửa: test khung hiện khi đang tải, đúng số khối, có tên, biến mất khi dữ liệu về.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: dòng ① Gợi ý nêu hành vi khung chờ; thêm dòng `Skeleton` vào bảng component (quy ước vùng chờ, nơi còn giữ vòng xoay).

## Quyết định

- Vòng xoay chỉ còn ở chỗ báo một việc đang chạy, không giữ chỗ nội dung: nút đang gửi, tiến trình trợ lý, màn chờ xác nhận thanh toán, dòng "Đang tìm chuyến chiều về…" khi khách còn ở bước chiều đi; lớp phủ "Đang tải tuyến đường thực tế từ OSRM…" trên bản đồ đã hiện cũng giữ nguyên. Ghi vào dòng `Skeleton` của spec frontend.
- Khung của từng loại thẻ đặt cạnh thẻ thật (`RoomCard.tsx`, `FlightCard.tsx`, `BookingCard.tsx`) để sửa bố cục thẻ thì sửa khung cùng chỗ; khung dùng chung (`grid`, `row`) ở `components/common/Skeleton.tsx`.
- Fallback Suspense của `Header` trong `AppShell` giữ `null`: `Header` tự bọc riêng hai chỗ đọc `useSearchParams` (thanh nhóm, nút quay lại của checkout) bằng Suspense có fallback thật, nên ranh giới ngoài không bao giờ hiện fallback.
- Fallback của `/search` theo bố cục tab "Tất cả" (trường hợp phổ biến nhất); trang server không đọc `searchParams` để giữ trang tĩnh, nên tab nhóm (`?type=`) cũng thấy khung "Tất cả" trong chốc lát trước khi `GroupResults` hiện khung dòng.
- Khung dùng `.skeleton-wave` sẵn có trong `globals.css` (tắt sóng khi giảm chuyển động), bỏ `animate-pulse` ở các vùng chờ dữ liệu.

## Kiểm tra

- `npx tsc --noEmit` (src/frontend): exit 0.
- `npx eslint src tests`: 0 lỗi, 3 cảnh báo `react-hooks/exhaustive-deps` có sẵn ở `ItineraryMap.tsx`, `useFloatingWidget.ts` (không chạm).
- `npx vitest run`: 85 file, 895 test pass.
- `npx next build --webpack`: thành công (16 trang); HTML dựng sẵn của `/search`, `/checkout`, `/profile/booking_history` có sẵn khung ("Đang tải trang tìm kiếm", "Đang tải thông tin thanh toán", "Lịch sử đặt chỗ" + "Đang tải đơn hàng"); `curl` trang dev :3010 cũng trả khung. `next-env.d.ts` do build sửa đã trả lại.
- Trình duyệt (Next dev :3010 + backend :8010 trên bản sao DB `vota_fe_skeleton`, request bị làm chậm tạm trong trang để chụp khung): trang chủ đăng nhập tài khoản demo P1 hiện 4 thẻ khung ở khối Gợi ý (desktop và bề ngang hẹp), đăng xuất rồi đăng nhập lại không hiện gợi ý của lượt trước; `/profile/booking_history` hiện 3 thẻ đơn khung; `/flights?origin=Hà Nội&destination=Đà Lạt` hiện dải ngày + 3 thẻ chuyến khung ở cột giữa. Console không lỗi.

## Còn lại / rủi ro

- Chưa push, chưa mở PR.
- Lỗi có sẵn, không do thay đổi này: dưới `md` (< 768 px) trang `/profile/*` tràn ngang (~738 px trong khung 569 px) vì `AccountShell` dùng `grid` không khai cột, hàng chip lọc `flex-none` đẩy cột rộng ra.
