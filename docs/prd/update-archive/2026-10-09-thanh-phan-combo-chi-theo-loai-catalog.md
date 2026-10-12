# Thành phần combo: chỉ nối / mô phỏng theo loại catalog đã có; dịch vụ đi kèm không có sản phẩm, không có phần giá

- Ngày: 2026-10-09
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Pham Nguyen Dang Khoi, 2026-10-09 (trong chat: "Không thêm các catalog như xe điện,... tôi chỉ muốn trong combo có
  những item nào mà catalog đã có form thì thêm vào"; chọn "Không, tính là đi kèm" cho phần giá của dịch vụ)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.1 FR-CAT-04; `docs/prd/data-model.md` §2.1 (`CATALOG_COMBO_ITEMS.price_share`), §3.1
  ("Thành phần combo mô phỏng")
- Mã FR/NFR: FR-CAT-04
- Thay đổi một phần: `2026-10-09-mo-phong-thanh-phan-combo-va-ve-phu-ngay.md`

## Lý do

Bản đã chốt trước đó sinh sản phẩm mô phỏng (`taxonomy = attraction`, `serviceKind`) cho cả ăn uống, xe điện, voucher, xông hơi…, tức
là thêm vào catalog những thứ không thuộc loại sản phẩm nào của V-OTA. Người dùng chỉ muốn nối / mô phỏng thành phần thuộc loại catalog đã
có (khách sạn – hạng phòng, vé máy bay – tuyến, vé tham quan, golf). "Voucher" không phải loại catalog: golf "voucher" là sản phẩm `golf`;
"voucher ẩm thực / quà lưu niệm" là quà đi kèm vé.

## Nội dung đề xuất

- FR-CAT-04: thành phần thuộc loại catalog trỏ tới sản phẩm (thật hoặc mô phỏng); dịch vụ kèm theo không thuộc loại nào là phần đi kèm,
  không có sản phẩm, không tách riêng; chỉ thành phần có sản phẩm có `price_share`, tổng = giá combo.
- data-model §3.1: bỏ gạch "dịch vụ mô phỏng `taxonomy = attraction` + `serviceKind`"; `meal | transfer | other` để `item_product_id`,
  `price_share` NULL; phần giá chỉ chia cho thành phần có sản phẩm. ERD `price_share` ghi rõ NULL cho dịch vụ đi kèm.

## Thay đổi source sau khi chốt

- `src/data_collection/seed/combo_components.py`: không sinh dịch vụ mô phỏng; lần chạy sau gỡ liên kết cũ (lấy lại loại gốc từ
  `serviceKind`) và khoá các dịch vụ mô phỏng đã sinh trước đó; `price_share` chỉ cho thành phần có sản phẩm.
- `db/verify.sql`: tổng `price_share` = giá combo, không có `price_share` ở dòng không có sản phẩm.
- Test, `docs/spec/MOCK_DATA_SPEC.md`, `docs/spec/data-collection/schema.md`, DDL comment.
