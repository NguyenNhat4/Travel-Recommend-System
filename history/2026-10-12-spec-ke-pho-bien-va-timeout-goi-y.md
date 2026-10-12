# Spec: kệ "Phổ biến" trộn loại, `/products` nhiều taxonomy và `diversify`, timeout gợi ý 10 giây

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành
- Phạm vi: docs
- Liên quan: `2026-10-12-contract-1-25-0-products-diversify.md`, `2026-10-12-products-tron-theo-nhom-loai.md`, `2026-10-12-ke-pho-bien-trang-chu-tron-loai.md`, `2026-10-09-tang-timeout-goi-y-trang-chu-10s.md`

## Mục tiêu

Đưa spec về khớp với code của các bước trước, theo AGENTS §4 ("feature làm thay đổi quy ước thì cập nhật tài liệu"):

- `GET /products` có tham số `diversify` và `taxonomy` nhiều giá trị;
- khối ④ ở trang chủ: tab "Tất cả" trộn loại có nhãn, tab "Vé tham quan" gồm golf;
- sửa dòng spec còn sót "timeout > 3 giây" và `k=5` của khối ①, vì code đã dùng 10 s và `k=4` từ 2026-10-09.

Phục vụ FR-REC-01 và chỉ số Diversity ở test-plan §2.5.

## File thay đổi

- `docs/spec/hop-dong-tich-hop-backend.md` — sửa: §4.1 sửa dòng `taxonomy`, thêm dòng `diversify`, thêm đoạn mô tả luật trộn (thứ tự nhóm, hoán vị, vì sao cần, nơi đặt bảng nhóm).
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa:
  - §4.1 dòng ①: `k=4`, timeout 10 giây, không hiện bản cũ;
  - §4.1 dòng ④: tham số theo tab, Vé tham quan gồm golf, nhãn loại chỉ ở tab Tất cả;
  - §5: dòng `ProductCard` (tile có `showTaxonomy`) và `TaxonomyBadge` (nơi dùng);
  - §11: fixture `listProducts.200-diversified`.
- `docs/spec/product.md` — sửa:
  - §4.0: `ProductCard` thêm biến thể `tile`; `TaxonomyBadge` thêm ngoại lệ khối ④ tab Tất cả;
  - wireframe §4.1.1: thêm một dòng mô tả khối ④, giữ bề rộng 85 ký tự;
  - §4.1.2 dòng ①: `k=4`, 3–4 thẻ;
  - §4.1.2 dòng ④: request thật và luật trộn, thay câu cũ "Phụ thuộc: endpoint phổ biến…".
- `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` — sửa: dòng trạng thái (đã xong / còn lại).
- `history/2026-10-12-spec-ke-pho-bien-va-timeout-goi-y.md` — thêm: entry này.

## Quyết định

- **Không lệch PRD:** PRD không quy định kệ này. `user-flow.md` §2 chỉ ghi "Personalized Carousels, Trending Destinations".
- **Nhãn loại:** ghi rõ là ngoại lệ có ngày chốt (2026-10-12) của quyết định bỏ nhãn ngày 2026-10-01, chỉ cho nơi trộn nhiều loại mà không có tab theo loại.
- **Không đổi gì về timeout:** hằng số 10 s ở §6.4 và `product.md` §4.1.5 đã đúng. Lần này chỉ sửa dòng ① còn sót.

## Kiểm tra

- `grep -n "3 giây\|k=5"` trên `hop-dong-tich-hop-frontend.md` và `product.md`: không còn kết quả.
- Script sửa wireframe kiểm dòng mới đúng 85 ký tự, bằng các dòng khác của khung.
- Chỉ đổi tài liệu, không chạy test.

## Còn lại / rủi ro

- Spec cold-start (§4.8 `hop-dong-tich-hop-search-recommendation.md`) sửa cùng bước cold-start.
- Spec cache Redis (K1, §7.1, S5) sửa ở bước cuối của giai đoạn 3.
