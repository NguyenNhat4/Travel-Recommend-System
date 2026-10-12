# Dữ liệu mô phỏng bổ sung: tuyến bay chiều ngược và hạng phòng cho khách sạn chưa có phòng

- Ngày: 2026-10-09
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Pham Nguyen Dang Khoi, 2026-10-09 (trong chat: "không sợ lệch prd đâu vì đã ok làm data mock là đc"; yêu cầu "tìm tất cả
  vấn đề mà data có thể bổ sung, mock thêm cho đầy đủ … chỉ cần bổ sung data là team agent và web tự tốt lên")
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.1 FR-CAT-03 (danh sách ngoại lệ mô phỏng); `docs/prd/data-model.md` §3.1
- Mã FR/NFR: FR-CAT-02, FR-CAT-03, FR-BKG-10, FR-AGT-02

## Lý do

Kiểm tra dữ liệu production ngày 09/10/2026 sau khi chốt vé phủ ngày và thành phần combo:

- **24 tuyến chỉ có một chiều** (ví dụ có Pleiku → Hà Nội nhưng không có Hà Nội → Pleiku; Điện Biên, Tuy Hòa, Quảng Bình, Vân Đồn…).
  Trang `/flights` ghép khứ hồi từ hai chặng một chiều, chiều về lấy ở tuyến ngược; agent cũng tìm chặng về ở tuyến có `originCity` là
  điểm đến. Không có tuyến ngược thì cả hai chỉ bán được một chiều.
- **295 khách sạn có giá nhưng không có hạng phòng nào** (Agoda), nên `available = false` (FR-CAT-02): không ra tìm kiếm mặc định, gợi ý,
  trợ lý, và không đặt được.

Cả hai sửa được chỉ bằng dữ liệu, không đổi code Web hay agent.

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.1 FR-CAT-03

Danh sách "Ba ngoại lệ cho demo" thành "Năm ngoại lệ cho demo", thêm: (4) tuyến bay chiều ngược cho tuyến chỉ có một chiều; (5) hạng
phòng cho khách sạn có giá nhưng chưa có hạng phòng nào.

### `docs/prd/data-model.md` §3.1 — thêm vào khối "Vé phủ ngày (demo)"

> - **Tuyến chiều ngược:** tuyến thật A → B có vé thật mà chưa có tuyến B → A (thật) thì sinh tuyến B → A mô phỏng (hiện như tuyến
>   thường): thành phố, sân bay, toạ độ đảo chiều từ tuyến A → B; chặng mẫu (`templateFlight`) = một vé thật A → B đảo sân bay, giữ hãng
>   và giờ cất cánh, không có số hiệu; giá một chiều = giá vé thật đó, `roundTripFrom` = `roundTripFrom` của A → B. `sourceRef` =
>   `demo:reverse:<sourceRef tuyến A → B>`, `simulated: true`, tên có "(giá minh hoạ)". Vé của tuyến này do bước vé phủ ngày sinh.
>   Có tuyến thật B → A thì tuyến mô phỏng `available = false`.

### `docs/prd/data-model.md` §3.1 — thêm khối sau "Thành phần combo mô phỏng (demo)"

> **Hạng phòng cho khách sạn chưa có phòng (demo).**
>
> - Chạy sau mỗi lần nạp catalog. Mặc định bật; tắt bằng `SIMULATED_ROOMS=0`.
> - Khách sạn tổng (không gộp, không mô phỏng) có giá mà không có hạng phòng con nào thì sinh một hạng phòng "Phòng tiêu chuẩn":
>   giá = giá của khách sạn (giá thấp nhất nguồn báo), `maxOccupancy` 2, lịch mở đủ cửa sổ, ảnh = ảnh khách sạn. `sourceRef` =
>   `demo:room:<sourceRef khách sạn>`, `simulated: true`, tên có "(giá minh hoạ)". Khách sạn được bật lại theo FR-CAT-02.
> - Khách sạn có hạng phòng thật, hoặc tắt cấu hình → hạng phòng mô phỏng `available = false`; không xoá dòng.

## Thay đổi source sau khi chốt

- `src/data_collection/seed/simulated_fill.py`: bước tuyến chiều ngược trước bước vé phủ ngày.
- `src/data_collection/seed/simulated_rooms.py` (mới) + test.
- `seed/combo_components.py`: thành phần vé máy bay được nối với tuyến chiều ngược mô phỏng (không sinh tuyến mô phỏng riêng của combo
  khi đã có).
- Tài liệu: `docs/spec/MOCK_DATA_SPEC.md`, `docs/spec/data-collection/schema.md`, `src/data_collection/README.md`.
- Production: chạy theo thứ tự `simulated_rooms` → `simulated_fill` → `combo_components` → `simulated_fill`.
