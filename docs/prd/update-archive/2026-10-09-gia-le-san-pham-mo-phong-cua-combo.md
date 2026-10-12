# Giá lẻ của sản phẩm mô phỏng trong combo: giá thật nếu có, không thì phần giá combo

- Ngày: 2026-10-09
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Pham Nguyen Dang Khoi, 2026-10-09 (trong chat: "nếu được thì lấy giá thật … người đặt ngoài sẽ không có giá combo";
  chọn "Giá thật nếu có, không thì phần giá")
- PRD bị ảnh hưởng: `docs/prd/data-model.md` §3.1 ("Thành phần combo mô phỏng", gạch "Phần giá")
- Mã FR/NFR: FR-CAT-03, FR-CAT-04
- Thay đổi một phần: `2026-10-09-mo-phong-thanh-phan-combo-va-ve-phu-ngay.md` (câu "Sản phẩm mô phỏng có `unit_price = price_share / số lượng`")

## Lý do

Giá của thành phần khi nằm trong combo và giá khi đặt lẻ là hai thứ khác nhau. Lấy phần giá combo làm giá lẻ của sản phẩm mô phỏng khiến
giá lẻ mang mức chiết khấu của combo. Tra nguồn Vinpearl (377 sản phẩm) và web 09/10: nhiều thành phần không có giá lẻ (Vườn Thú, Khu Trò
Chơi, GoKart Vũ Yên chỉ bán theo gói); khách sạn đã khớp catalog có giá thật (giá thấp nhất nguồn báo).

## Nội dung đề xuất

data-model §3.1: khi tách combo dùng `price_share` của combo đó; giá lẻ (`unit_price`) không đổi theo combo — sản phẩm thật giữ giá thật,
sản phẩm mô phỏng lấy giá thật nếu có (phòng của khách sạn đã khớp: giá khách sạn; vé có số tiền ghi trong nhãn), không có thì
`price_share / số lượng`. Giá thật cũng là giá tham khảo khi chia `price_share` (đã có trong quy tắc).

## Thay đổi source sau khi chốt

- `src/data_collection/seed/combo_components.py`: `unit_price` của phòng / vé mô phỏng = giá thật nếu có; tuyến mô phỏng giữ phần giá.
- Test `src/data_collection/tests/test_combo_components.py`; `docs/spec/MOCK_DATA_SPEC.md`.
