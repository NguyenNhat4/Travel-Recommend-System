# Kiểm chứng pipeline và bổ sung vé máy bay với ít thay đổi

- Ngày: 2026-09-29
- Phục vụ: FR-CAT-01, FR-CAT-03, FR-SRC-02; kiểm tra luồng giữ chỗ FR-BKG-05.
- Căn cứ: PRD requirements/data-model và đề xuất đã chốt `docs/prd/update-archive/2026-09-29-ve-khu-hoi-dat-duoc.md`.
- Phạm vi: tiếp tục cách tổ chức task/dependency/checkpoint/retry như Airflow; không cài Airflow. Chưa triển khai lên VM.

## Đã triển khai

- Cô lập nguồn lỗi, bỏ bước phụ thuộc, tiếp tục nguồn độc lập; thiếu cấu hình index không ngăn nạp DB.
- Hạn giờ retry dùng chung theo nguồn; timeout DB và supervisor bao phủ cả xử lý/joins/streaming. Khi cưỡng chế dừng, dọn tiến trình con và trạng thái trước khi thả khóa.
- Kiểm tra cấu trúc catalog, loại checkpoint nguồn lỗi/thiếu dữ liệu; resume không che lỗi nguồn khác.
- Khứ hồi giữ `level: flight`; mỗi hành trình/ngày/hạng có ID riêng, giữ ID cũ. Loader không dời ngày báo giá cố định; báo giá hết hạn không đặt được.
- Chuẩn hoá Booking chỉ nhận giá một người lớn, hạng được đối chiếu với trang; không suy giá thương gia hoặc chia giá nhóm.
- FE hiển thị hạng, hai chặng và giá tổng ở chi tiết, giỏ, checkout. Backend trả thuộc tính vé trong giỏ/đơn bằng trường optional sẵn có.

## Chỗ vẫn có thể làm chậm hoặc dừng toàn lượt

| Điểm | Hành vi sau sửa | Khôi phục |
|---|---|---|
| Nguồn chậm | Nguồn khác vẫn chạy; lần gộp cuối chờ xong hoặc timeout | Bật streaming và nạp theo phần sau kiểm chứng môi trường |
| Parser/quality gate của một nguồn | Loại nguồn lỗi, nạp nguồn hợp lệ, báo partial | Sửa parser hoặc cào lại riêng nguồn |
| Tất cả nguồn lỗi/catalog không hợp lệ | Không nạp bản mới | Giữ DB cũ, sửa nguồn rồi resume |
| DB hỏng/khóa lâu | Hết hạn và retry có giới hạn; không thể hoàn tất nạp khi DB chưa phục hồi | Sửa DB rồi resume từ db |
| Index/Cohere lỗi | DB đã nạp giữ lại, index báo lỗi | Resume index sau khi sửa cấu hình/dịch vụ |
| Native call/thread không thoát | Supervisor dừng cả worker để giải phóng khóa; có thể kết thúc sớm các nguồn đang chạy | Resume từ dữ liệu/checkpoint đã ghi |

Streaming hiện mặc định tắt. Cần kiểm tra VM bật đúng cờ nếu muốn dữ liệu nguồn nhanh xuất hiện trước khi toàn lượt xong. Lượt daily chỉ lấy khách sạn Trip, không có nguồn độc lập khác để nạp thay.

## Đề xuất tích hợp fareClasses cho FE

Mẫu FE cung cấp là danh sách hiển thị, chưa đủ định danh lựa chọn khi đặt. Đề xuất mỗi phần tử thêm `productId` trỏ tới biến thể flight đã có trong catalog; `code: ECO` chỉ là mã hiển thị, ánh xạ từ `cabinClass: ECONOMY`.

- Request thêm giỏ giữ `productId`, `usingDate`, `quantity`; không gửi giá để backend tin theo và không cần thêm fareClassCode.
- `price` lấy từ unitPrice của đúng biến thể; khứ hồi là tổng hai chặng cho một người lớn.
- Không gộp lựa chọn khác ngày/hành trình vào cùng thẻ chỉ vì trùng hạng.
- Hành lý, suất ăn và đổi vé thiếu bằng chứng phải cho phép thiếu/null; 0/false có ý nghĩa xác nhận riêng.
- `soldOut` không được suy ra chỉ từ báo giá hết hạn. Cần thống nhất cách FE biểu diễn “chưa biết/hết hạn”.
- Chưa thêm mảng fareClasses vào API và chưa xác lập enum mã hạng của FE. Mô hình productId riêng đã nằm trong PRD; thay đổi hình dạng trả API cần đồng bộ contract trước khi triển khai.

## Còn lại trước demo VM

1. Có báo giá mới đúng tuyến/ngày và hạng. Lượt thử Booking BUSINESS SGN–HAN ngày 10/10/2026 chưa lấy được offer (timeout); không tạo giá thay thế. Trip lịch sử không xác nhận hạng.
2. Xác minh bằng nguồn giá khứ hồi cho một người lớn trước khi nạp báo giá thực; fixture chỉ chứng minh logic ghép và đặt trong hệ thống.
3. Thống nhất hình dạng fareClasses với FE theo đề xuất trên.
4. Kiểm chứng một lượt nhỏ trên môi trường VM rồi mới bật streaming tại đó; chỉ upsert, không reset 11k catalog hoặc state giỏ/đơn.
5. Cần kiểm tay giao diện trong trình duyệt. Các kiểm thử tự động và kết quả DB được ghi trong history của task.
