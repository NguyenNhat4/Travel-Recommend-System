# Ô điểm đi, điểm đến chỉ nhận sân bay hiện hành; ô địa điểm ở khách sạn và combo hiện khách sạn nổi tiếng

- Ngày: 2026-10-13
- Người đề xuất: người dùng (yêu cầu trực tiếp trong phiên 2026-10-13) / agent thực hiện
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: người dùng, 2026-10-13 (áp dụng vào `docs/prd/requirements.md` FR-SRC-03 và `docs/prd/user-flow.md` dòng `/flights` cùng ngày). Ghi lại theo yêu cầu trong chat ("khi click vào có hiển thị Khách Sạn Nổi Tiếng thay thế cho địa điểm nổi tiếng", "phải nhập đúng sân bay hiện hành thì submit… nếu nhập địa điểm bất kỳ thì ô tự xóa"). Người dùng cần xác nhận lại nếu nội dung ghi ở đây chưa đúng ý.
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.2 FR-SRC-03 (ô Địa điểm của trang danh mục); `docs/prd/user-flow.md` dòng `/flights` trong bảng route
- Mã FR/NFR: FR-SRC-03 (mở rộng); phục vụ FR-CAT-01 (tuyến bay trong catalog là nguồn sân bay)

## Lý do

FR-SRC-03 chỉ nói ô Địa điểm "hiện kết quả ngay tại trang danh mục". Chưa quy định hai việc người dùng đang gặp:

1. Ô Điểm đi và Điểm đến ở `/flights` nhận chữ tự do. Gõ "xứ sở" vẫn gửi tìm kiếm và trang chỉ báo lỗi sau. Cần ô chỉ nhận sân bay hiện hành đang có trong catalog, để tìm không bao giờ gửi một điểm không có tuyến.
2. Khi bấm ô Địa điểm ở `/hotels` và `/combos`, danh sách hiện là "điểm đến phổ biến". Người dùng muốn thấy khách sạn nổi tiếng để chọn trực tiếp.

## Nội dung đề xuất

**Ô Điểm đi và Điểm đến ở `/flights`:**
- Gợi ý là sân bay lấy từ tuyến bay đang còn bán trong catalog (không lấy từ danh sách cố định trong mã nguồn). Mỗi dòng ghi thành phố, mã IATA và tên sân bay nếu catalog có.
- Nhóm "Thành phố hoặc sân bay phổ biến" (tối đa 5 sân bay nhiều tuyến nhất), rồi nhóm "Trong nước" với các sân bay còn lại. Chưa có sân bay quốc tế trong catalog nên chưa có nhóm quốc tế.
- Chữ gõ khớp đúng một sân bay (mã IATA, tên thành phố có đúng một sân bay, hoặc "Thành phố (MÃ)") mới được coi là hợp lệ.
- Khi người dùng rời ô (hoặc gửi tìm kiếm) mà chữ không khớp sân bay nào thì ô tự xoá, không gửi tìm kiếm với điểm đó.
- Kết quả và đường dẫn `/flights?origin&destination` vẫn dùng tên thành phố như hiện nay.

**Ô Địa điểm ở `/hotels` và `/combos`:**
- Khi bấm ô (chữ còn trống), dropdown hiện "Khách sạn nổi tiếng" thay cho "Điểm đến phổ biến": tối đa 5 khách sạn của catalog xếp theo độ phổ biến, mỗi dòng có ảnh, tên, thành phố.
- Khi đang gõ: khách sạn khớp chữ gõ, và các điểm đến khớp chữ gõ (để vẫn tìm được theo thành phố như trước).
- Bấm một khách sạn thì mở trang chi tiết khách sạn đó, kèm ngày và số khách đang chọn.
- Ô Điểm đến của `/experiences` không đổi.

## Thay đổi source sau khi chốt

- `src/frontend/src/services/flights.ts`: hàm lấy sân bay từ tuyến còn bán.
- `src/frontend/src/features/flights/airports/*`: xử lý khớp, nhóm gợi ý và ô nhập sân bay.
- `src/frontend/src/features/catalog/landing/LandingSearchSheet.tsx`, `FamousHotelsPanel.tsx`, `verticals.ts`: ô Điểm đi, Điểm đến và ô Địa điểm.
- `src/frontend/src/features/flights/FlightsPage.tsx`: thông báo khi thiếu sân bay.
- Test trong `src/frontend/tests/unit/`; spec `docs/spec/ui-dia-diem-san-bay-va-khach-san-noi-tieng.md`; entry `history/2026-10-13-san-bay-va-khach-san-noi-tieng.md`.
