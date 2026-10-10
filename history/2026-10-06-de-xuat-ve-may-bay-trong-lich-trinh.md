# Đề xuất: vé máy bay trong lịch trình của trợ lý và dùng vị trí trình duyệt để gợi ý nơi đi

- Ngày: 2026-10-06
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: history/2026-10-06-ve-may-bay-trong-lich-trinh.md

## Mục tiêu

Người dùng muốn lịch trình của trợ lý có vé máy bay, và muốn xin quyền vị trí để gợi ý nơi đi. PRD chưa có trường nơi
đi, sơ đồ `architecture.md` §3 chỉ tìm "phòng & tour", và PRD chưa nhắc tới dữ liệu vị trí. Vì vậy theo AGENTS.md §8,
việc này phải có đề xuất được chốt trước khi sửa source.

## File thay đổi

- `docs/prd/update/2026-10-06-ve-may-bay-trong-lich-trinh-va-vi-tri.md` — thêm, trạng thái `chờ chốt`. Nội dung:
  - sửa FR-AGT-01/02/03 và AC-AGT-01;
  - thêm AC-AGT-02 (khi nào có hoặc không có chặng bay) và AC-AGT-03 (vị trí trình duyệt);
  - sửa `architecture.md` §3 và `user-flow.md` §4.2.

## Quyết định

- **Có vé thì xếp vào lịch và tính vào tổng.** Người dùng chọn phương án này thay cho khối "cân nhắc thêm".
- **Mặc định có chặng bay khi đủ 5 điều kiện:**
  1. biết nơi đi;
  2. catalog có tuyến;
  3. người dùng không loại trừ;
  4. có chuyến còn bán, có giá, đúng ngày;
  5. chuyến đi từ 2 ngày.

  Không có chặng bay thì luôn nói lý do. Không bỏ vé vì vượt ngân sách.
- **Nơi đi không bắt buộc**, như ngân sách, để không chặn lập lịch.
- **Vị trí chỉ xin khi người dùng bấm.** Toạ độ không rời trình duyệt; chỉ tên thành phố có sân bay gần nhất được gửi lên,
  tính từ `originLatitude`/`originLongitude` sẵn có trong catalog.
- **Dữ liệu catalog đã đủ** (Postgres local 06/10/2026): 113 tuyến, 1.594 chuyến, 19 thành phố đi, có vé khứ hồi.
  Chuyến của một tuyến lấy qua `GET /products?parentProductId=`.

## Kiểm tra

- Không chạy lệnh nào: thay đổi chỉ là tài liệu đề xuất.

## Còn lại / rủi ro

- **Đang dừng ở bước 1 của AGENTS.md §8: chờ người dùng chốt đề xuất.** Chưa sửa PRD, contract hay code.
- Sau khi chốt:
  1. cập nhật PRD;
  2. sửa contract `itinerary-agent.yaml` trước;
  3. backend agent (`origin`, tool liệt kê chuyến, chọn chặng trong `compose`);
  4. widget;
  5. spec và test;
  6. chuyển đề xuất sang `docs/prd/update-archive/`.
