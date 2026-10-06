# Ẩn khách sạn không có hạng phòng đặt được

- Ngày: 2026-10-06
- Người đề xuất: Đăng Khôi / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Đăng Khôi, 2026-10-06
- PRD bị ảnh hưởng: `docs/prd/requirements.md` FR-CAT-02; `docs/prd/data-model.md` §4.2
- Mã FR/NFR: FR-CAT-02, FR-SRC-01

## Lý do

Team Web (daily 06/10) báo dữ liệu đưa lên web "không được đúng lắm". Trên DB VM ngày 06/10 có 303/2.424 khách sạn tổng quan đang bán (`available = true`) nhưng **không có hạng phòng nào**: toàn bộ từ Agoda, nguồn báo không có nhà cung cấp mở bán online. Chúng không vào `/recommendations` (`is_recommendable = false`), nhưng vẫn ra ở tìm kiếm và trong lịch trình của trợ lý; người dùng chỉ biết không đặt được khi mở trang chi tiết ("chưa có hạng phòng nào trên V-OTA — chỉ để tham khảo"). Người dùng muốn catalog trên web chỉ còn khách sạn đặt được.

Sửa tay trên DB (đặt `available = false`) không bền: lượt cào sau ghi lại `available` theo nguồn.

## Nội dung đề xuất

- `requirements.md` FR-CAT-02, sau ý "Điểm lưu trú tổng quan (`hotel_property`) chỉ mang tính hiển thị thông tin…" → thêm: "Khách sạn tổng quan không có hạng phòng con nào đặt được (`available` và `is_bookable`) thì `available = false`: không ra ở tìm kiếm mặc định, trợ lý và gợi ý. Dòng được giữ (không xoá) và tự bật lại khi có hạng phòng đặt được."
- `data-model.md` §4.2 → thêm cùng quy tắc ở mục `is_search_unit`.

Không đổi contract, DDL, 13 trường. Tuyến bay (`flight_route`) không đổi: mọi vé có giá đã luôn đặt được (chốt 06/10).

## Thay đổi source sau khi chốt

- `src/data_collection/fresh_catalog_db.py` `apply_window` (chạy ở `maintain_catalog` đầu mỗi lượt và sau mỗi lần nạp): `hotel_property` có `available` = có ít nhất một hạng phòng con đang bán có giá; đánh dấu riêng để chỉ bật lại các dòng do quy tắc này tắt (không bật dòng tắt vì lý do khác, như `mergedInto`).
- Test `src/data_collection/tests/test_fresh_catalog_job.py`; `docs/spec/data-collection/schema.md`, `src/data_collection/README.md`.
- Seed demo (`load_products.convert`) áp cùng quy tắc để DB local giống VM.
- DB VM: đã ẩn tay 303 khách sạn ngày 06/10 bằng `hide_unbookable_hotels.py` (sao lưu kèm theo); sau khi code lên VM, `maintain_catalog` giữ quy tắc này.
