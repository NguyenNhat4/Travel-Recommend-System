# Hỏi lại trước khi khách rời trang thanh toán

- Ngày: 2026-10-08
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend | docs

## Mục tiêu

Khách rời `/checkout` (logo, nút quay lại, link chân trang, nút Back, đóng tab) mà không có cảnh báo, trong khi rời đi là mất lựa chọn khách sạn, vé máy bay của lần Đặt ngay và mọi thông tin hành khách đã nhập. User story: khách chủ động thoát ra thì hiện thông báo. Hành vi này chưa có trong PRD nên đi qua đề xuất `docs/prd/update-archive/2026-10-08-canh-bao-roi-trang-thanh-toan.md`, mihhquan chốt 2026-10-08 (chốt khi duyệt kế hoạch). Mã yêu cầu: FR-BKG-01, FR-BKG-06; AC mới AC-BKG-20.

Giao diện được duyệt trước khi code: https://claude.ai/artifact/BaFqEtCuhAeewniaj84db6

## File thay đổi

- `docs/prd/update-archive/2026-10-08-canh-bao-roi-trang-thanh-toan.md` — thêm: đề xuất, tạo ở `update/`, trạng thái đã áp dụng rồi chuyển sang `update-archive/`.
- `docs/prd/requirements.md` — sửa: FR-BKG-01 thêm ý "Hỏi lại trước khi rời trang thanh toán"; thêm AC-BKG-20.
- `docs/prd/user-flow.md` — sửa: §3.3 thêm ý "Rời trang khi chưa thanh toán", lưu đồ có nút "Hộp cảnh báo rời trang".
- `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` — sửa: dòng cập nhật ở đầu, §6.2 (quy tắc rời trang, cách chặn nút Back, giới hạn), §10.1 (hai file mới).
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: §4.5 thêm đoạn rời trang và `setNavigationGuard`.
- `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` — sửa: §13 dòng Trang thanh toán.
- `docs/spec/product.md` — sửa: §4.5 thêm dòng trạng thái rời trang.
- `src/frontend/README.md` — sửa: một câu về cơ chế hỏi lại.
- `src/frontend/src/context/TravelContext.tsx` — sửa: `setNavigationGuard`; `navigate()` hỏi guard trước khi `router.push`.
- `src/frontend/src/components/checkout/useLeaveGuard.ts` — thêm: chặn `navigate()`, thẻ `<a>`, `beforeunload`, nút Back; `stepHistoryState`.
- `src/frontend/src/components/checkout/LeaveCheckoutDialog.tsx` — thêm: hộp cảnh báo và `leaveLines`.
- `src/frontend/src/components/checkout/useCheckout.ts` — sửa: gọi `useLeaveGuard`; các bước ghi `history.state` qua `stepHistoryState`; `allowLeave()` trước các lần rời trang do hệ thống.
- `src/frontend/src/components/checkout/CheckoutView.tsx` — sửa: hiện `LeaveCheckoutDialog`.
- `src/frontend/src/app/globals.css` — sửa: keyframes của hộp (trượt từ đáy, hiện dần), tắt khi `prefers-reduced-motion`.
- `src/frontend/tests/unit/checkoutView.test.tsx` — sửa: `Harness` có `setNavigationGuard`, logo và hai liên kết; thêm 8 test AC-BKG-20.
- `src/frontend/tests/unit/leaveCheckoutLines.test.ts` — thêm: 5 test cho `leaveLines`.
- `src/frontend/tests/e2e/checkout-leave.spec.ts` — thêm: 5 test trên Chromium thật.
- `history/2026-10-08-canh-bao-roi-trang-thanh-toan.md` — thêm.

## Quyết định

- **Theo lựa chọn của người dùng:** luôn cảnh báo cả giỏ và Đặt ngay, kể cả khi chưa nhập gì; có chặn nút Back; trên điện thoại hộp trượt từ đáy.
- **Chỉ sửa Web.** Rời trang không gọi API: đơn nháp tự hết hạn sau 30 phút, tour và tiện ích đã được chép vào giỏ lúc Đặt ngay. Không đổi contract, Backend, DDL.
- **Một điểm chặn cho `navigate()`** đặt ở `TravelContext` (`setNavigationGuard`), nên logo, "Quay lại giỏ hàng", "Sửa giỏ hàng" không phải sửa từng chỗ. Thẻ `<a>` bị chặn bằng một listener `click` pha capture trên `document`, nên `Footer.tsx` và các liên kết thêm sau này không cần biết tới guard.
- **Nút Back:** không huỷ được `popstate`, nên đặt một mục lịch sử "chặn" ngay dưới trang (dấu trên `history.state`), các mục của bước `?step=` mang cùng dấu để tải lại trang không đặt mục thứ hai. Mục chặn chỉ được đặt ở thao tác đầu tiên của khách, vì trình duyệt bỏ qua mục lịch sử do script thêm khi khách chưa chạm vào trang.
- **Mặc định là ở lại:** focus vào "Ở lại thanh toán"; Esc và bấm ra ngoài hộp là ở lại.
- **Không hỏi** khi rời trang do hệ thống: bấm Thanh toán sang Stripe, tiếp tục đơn đang giữ chỗ, giỏ rỗng, `CART_EMPTY`, màn hình hết hạn và không tìm thấy.
- Nội dung hộp chỉ ghi "vẫn nằm trong giỏ hàng" cho mục đang thật sự có trong giỏ (cùng sản phẩm, cùng ngày), cùng cách kiểm với màn hình hết hạn (`checkoutSource.fail`).

## Kiểm tra

Chạy từ `src/frontend` (máy không có `npm` trên PATH):

- `node_modules/.bin/tsc --noEmit`: sạch.
- `node_modules/.bin/eslint .`: 0 lỗi, 2 cảnh báo có sẵn ở `components/assistant/ItineraryMap.tsx` (file không đổi).
- `node_modules/.bin/vitest run tests/unit`: 68 file, 724 test pass. Một lần chạy riêng `checkoutView.test.tsx` lúc máy đang tải nặng (load average khoảng 8) có 2 test cũ quá hạn 5 giây; chạy lại riêng file đó và chạy toàn bộ đều pass.
- `tests/e2e/checkout-leave.spec.ts`: 5 test pass trên Chromium, chạy bằng một cấu hình Playwright tạm trỏ vào dev server đang chạy sẵn ở `http://localhost:3000`, API giả bằng `page.route`. Kiểm: logo, liên kết chân trang, Back ở bước Hành khách (ở lại và rời trang), Back giữa hai bước không hỏi, tải lại trang rồi Back, khung điện thoại 390 px (hộp sát đáy, nút xếp dọc, cao từ 44 px).
- `node_modules/.bin/playwright test tests/e2e/checkout-leave.spec.ts` với cấu hình chính thức của repo: **không chạy được ở máy này** (`cross-env: command not found` khi khởi động web server). Spec chưa được chạy trên bản build production.
- Ảnh chụp hộp thật (máy tính và điện thoại, nguồn giỏ và đơn nháp) đã đối chiếu với bản thiết kế.
- Không đổi contract hay mock nên không chạy `validate_contract.py`; không đổi schema nên không chạy `db/verify.sql`.

## Còn lại / rủi ro

- Khách vào trang rồi bấm Back ngay, chưa thao tác gì, thì rời luôn không hỏi (giới hạn của trình duyệt, đã ghi trong PRD và spec §6.2). Playwright không tái hiện được hành vi bỏ qua mục lịch sử của nút Back thật, nên giới hạn này chưa được kiểm tự động.
- Hộp của trình duyệt khi đóng tab hoặc tải lại không đổi được chữ; một số trình duyệt di động không hiện.
- Chưa kiểm tay trên Safari và Firefox; e2e chỉ chạy Chromium.
- Guard trong `navigate()` của `TravelProvider` chưa có test đơn vị riêng (chưa có test harness cho provider); được kiểm qua e2e.
