# Thanh phân cấp trang chi tiết về đúng trang danh mục

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend, docs

## Mục tiêu

Ở trang chi tiết khách sạn, thanh phân cấp chỉ có "Trang chủ › {điểm đến}" và mục điểm đến dẫn sang `/search` (trang tìm kiếm gộp), nên người dùng từ kết quả `/hotels` vào chi tiết rồi bấm mục đó lại rơi vào trang gộp. Cần thanh phân cấp "Trang chủ › Khách sạn tại Nha Trang › tên khách sạn" quay về đúng trang danh mục. Không lệch PRD: `/search` vẫn dùng cho tìm tự do; đây là hệ quả của đề xuất `update-archive/2026-10-07-tim-kiem-tai-trang-danh-muc.md` (kết quả theo loại nằm ở trang danh mục).

## File thay đổi

- `src/frontend/src/components/detail/ProductBreadcrumb.tsx` — thêm: `breadcrumbOf` (dựng mục) và `ProductBreadcrumb` (thẻ `nav` + `ol`, liên kết thật, `aria-current="page"` ở mục cuối).
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: dùng `ProductBreadcrumb`; đọc ngày và số khách từ URL (`tripQuery`) sau khi mount.
- `src/frontend/tests/unit/productBreadcrumb.test.tsx` — thêm; `tests/unit/productDetailView.test.tsx` — sửa: thêm một test.
- `docs/spec/hop-dong-tich-hop-frontend.md` (§4.3), `docs/spec/product.md` — sửa.
- `history/2026-10-07-thanh-phan-cap-trang-chi-tiet.md` — thêm: entry này.

## Quyết định

- Mục giữa dựng bằng `buildSearchHref` nên cùng quy ước URL với tấm tìm kiếm: `/hotels?q=khách sạn&destination=…`, sân golf về `/experiences?…&type=golf`, vé tham quan `/experiences`, combo `/combos`; vé máy bay về `/flights?destination=`.
- Giữ ngày và số khách trên URL để quay về đúng kết quả đã lọc; đọc sau khi mount (đọc `window.location` lúc render sẽ lệch giữa server và client).
- Nút Back của trình duyệt không cần sửa: kết quả nằm ngay trên `/hotels`, `router.push` đã giữ lịch sử.
- Không đụng bộ ảnh nhiều tấm như ảnh bạn gửi: trang hiện tại chỉ có một ảnh (`imageUrl`).

## Kiểm tra

- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 63 file, 669 test pass. `tsc --noEmit` sạch. `eslint`: 0 lỗi, 2 cảnh báo cũ ở `ItineraryMap.tsx`.
- Trình duyệt thật với backend thật: từ `/hotels?q=…&destination=Nha+Trang&checkIn=…&adults=2` mở khách sạn đầu tiên: thanh phân cấp "Trang chủ › Khách sạn tại Nha Trang › Le Duong Hotel"; Back về `/hotels?q=…`; bấm "Khách sạn tại Nha Trang" về `/hotels?q=…&checkIn=2026-10-12&checkOut=2026-10-14&adults=2&rooms=1`.

## Còn lại / rủi ro

- Vào chi tiết từ trang khác (trang chủ, trợ lý, đơn hàng) thì mục giữa vẫn về trang kết quả của điểm đến đó, không phải trang trước đó; muốn "quay lại đúng trang đã đến" cần lưu nguồn điều hướng.
- Còn một vài chỗ khác dẫn sang `/search` (thanh tab điện thoại, gợi ý "Xem tất cả"), giữ nguyên có chủ đích.
