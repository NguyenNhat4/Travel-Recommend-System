# Đồng đều kích thước thẻ kết quả dạng hàng

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Sau khi kết quả tìm kiếm hiện ngay tại trang danh mục (`history/2026-10-07-tim-kiem-tai-trang-danh-muc.md`), các thẻ trong danh sách có kích thước lệch nhau: thẻ có ảnh dọc cao hơn thẻ khác, thẻ golf không có ảnh chỉ còn ô trống. Cần đồng nhất chiều cao, khung ảnh và vùng nội dung. Thẻ `row` cũng dùng ở `/search`, nên sửa này áp dụng cho cả hai nơi.

## File thay đổi

- `src/frontend/src/components/common/ProductCard.tsx` — sửa (chỉ bản `row`): thẻ cao cố định `md:h-60`; khung ảnh 16:10 trên điện thoại và cao bằng thẻ trên màn hình rộng, ảnh `absolute inset-0 object-cover`; thiếu hoặc lỗi ảnh thì dùng `placeholderImage(taxonomy)` (như bản `compact`); mô tả `min-h-10`; hàng tag một dòng cao 22px, cắt bớt thay vì xuống dòng; chân thẻ `min-h-[54px]` để thẻ không có giá vẫn cao bằng thẻ có giá.
- `history/2026-10-07-dong-deu-the-ket-qua-dang-hang.md` — thêm: entry này.

## Quyết định

- Chiều cao cố định thay vì để nội dung quyết định: ảnh có tỉ lệ bất kỳ nên không thể cho ảnh tự quyết chiều cao thẻ.
- Bản `grid`, `compact`, `tile` không đổi.
- Không thêm ảnh placeholder mới; dùng các file có sẵn ở `public/placeholders/`.

## Kiểm tra

- Trình duyệt thật với backend thật, đo chiều cao các thẻ (`/hotels`, `/experiences?type=golf`, `/combos`, có `?q=`): 1280px mọi thẻ đúng 240px; 390px mọi thẻ đúng 455px (trước khi thêm `min-h` cho chân thẻ có một thẻ 434px); không có cuộn ngang.
- `node_modules/.bin/vitest run tests/unit` (từ `src/frontend`): 62 file, 655 test pass. `tsc --noEmit` và `eslint` trên file đã sửa: sạch.

## Còn lại / rủi ro

- Mô tả sản phẩm thật dài hoặc nhiều tag sẽ bị cắt (mô tả 2 dòng, tag một hàng) thay vì làm thẻ cao thêm.
- Chưa có test tự động cho chiều cao thẻ (jsdom không tính layout); đã kiểm bằng trình duyệt thật.
