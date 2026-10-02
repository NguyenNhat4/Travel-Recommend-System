# Đề xuất thẻ sản phẩm trong khung chat và panel chi tiết khi bấm (desktop)

- Ngày: 2026-10-02
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Phạm vi: docs, frontend

## Mục tiêu

Người dùng muốn widget trợ lý trên desktop giống ảnh tham chiếu:

- ngay sau mỗi địa điểm trong lời kể có thẻ thật;
- bấm thẻ thì cột phải mở panel chi tiết (bộ ảnh, mô tả, địa chỉ với chỉ đường, giờ mở cửa, điểm đánh giá).

`user-flow.md` §4.2 chưa có hai hành vi này, nên theo AGENTS.md §8 phải có đề xuất được chốt trước khi sửa source.
Phục vụ FR-AGT-03, FR-AGT-04, AC-AGT-01, NFR-REL-01.

## File thay đổi

- `docs/prd/update/2026-10-02-the-va-panel-chi-tiet-trong-tro-ly.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-10-02-de-xuat-the-va-panel-chi-tiet-tro-ly.md` — thêm: entry này.

## Quyết định

- Chưa sửa PRD, spec hay code của phần này; chờ người dùng chốt.
- Thẻ trong chat dùng `ProductCard` compact (người dùng chọn kiểu thẻ gọn), đặt sau lần nhắc đầu tiên.
  Dữ liệu thẻ lấy từ `itinerary`/`searchResults` của response, không lấy từ chữ của LLM.
- Panel chi tiết đọc `GET /products/{productId}`, endpoint đã có. Endpoint này trả đủ `attributes.images` (điểm tham quan
  100%, trung vị 4 ảnh), `openingHours` (68% điểm tham quan, dạng chữ), `address`, toạ độ và điểm đánh giá
  (snapshot 2026-09-30). Không cần đổi contract.
- Không làm danh sách bình luận hay video như ảnh mẫu: catalog không có nội dung bình luận, tên người đánh giá hay video.

## Kiểm tra

- Không có code thay đổi. Chưa chạy lệnh nào cho entry này.

## Còn lại / rủi ro

- Chờ người dùng chốt: `đã chốt`, sửa đề xuất, hoặc `từ chối`.
- Sau khi chốt:
  1. Sửa `docs/prd/user-flow.md` §3.2 và §4.2 trước, sau đó spec frontend §4.8 và §5.
  2. Code: `WidgetChat`, `ProductCard` compact, `WidgetProductDetail` mới, `useFloatingWidget`, `FloatingWidget`, và
     `rating`/`reviewCount` trong `hit` của Search.
  3. Chuyển đề xuất sang `docs/prd/update-archive/`.
