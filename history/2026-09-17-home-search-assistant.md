# Tổng hợp thay đổi HomeView, thanh tìm kiếm và trợ lý AI ngày 17-09-2026

- Ngày: 2026-09-17
- Tác giả: người dùng / agent
- Nhánh: data_contract, main
- Trạng thái: hoàn thành
- Phạm vi: frontend

## Mục tiêu

Tổng hợp các thay đổi frontend ngày 17-09-2026, gồm trang chủ, thanh tìm kiếm, ProductCard và AiFloatingWidget; giữ lại quyết định, kết quả kiểm tra và việc còn lại.

### Các thay đổi đã gộp

- Carousel trang chủ đo khoảng cách card trong DOM và cuộn tối thiểu hai card; mục Bạn muốn đi đâu hiển thị bốn card trên desktop nhưng vẫn cuộn ngang.
- Tạm ẩn bốn nút Xem thêm vì các luồng đích chưa hoàn thiện; giữ nguyên markup để bật lại sau.
- Thanh tìm kiếm được thử nghiệm dưới dạng Mega Panel ba cột, sau đó chuyển thành ba panel riêng cho điểm đến, ngày và số lượng. Kích thước panel được điều chỉnh riêng: điểm đến rộng toàn thanh, DatePicker và số lượng gọn hơn.
- DatePicker hỗ trợ chọn khoảng ngày, đổi tháng, định dạng DD/MM/YYYY và tự điều chỉnh khoảng ngày không hợp lệ. Các thay đổi sau đó bỏ số đêm, preset nhanh, và nút Tiếp tục/Áp dụng; ngày và số lượng cập nhật trực tiếp.
- Panel điểm đến được thiết kế lại với tìm kiếm gần đây, điểm đến phổ biến và gợi ý khách sạn. Gợi ý được chuyển từ địa danh chung sang khách sạn/resort cụ thể kèm địa phương; section “Khách sạn được lựa chọn” đổi thành “Khách sạn được yêu thích nhất”.
- Ba Trust Badge dùng ảnh minh họa tương ứng; badge trợ lý dùng mascot_hello.png.
- AiFloatingWidget được chuyển thành sidebar mép trái và giao diện fullscreen chat/timeline/map. Bố cục có tab Tất cả ngày, lịch sử hội thoại, New Chat, điều khiển thu nhỏ/đóng, khóa cuộn nền và map nạp client-only. Sidebar được chỉnh theo tỷ lệ 4/12.
- Footer timeline hiển thị tổng tiền VND và nút thanh toán đưa sản phẩm vào giỏ rồi chuyển tới checkout. Bỏ banner kế hoạch bị lặp và không còn tự tạo hội thoại/lịch trình mock khi mở trợ lý lần đầu.
- Điều hướng checkout bỏ scrollTo gây nhảy trang; widget giữ mở cho đến khi route checkout sẵn sàng rồi tự đóng. Lỗi panel Điểm đến nhấp nháy được xử lý bằng cách chặn event bubbling ở input.
- ProductCard bỏ BecauseLine ở compact trước, rồi bỏ khỏi cả compact và grid; entry đầu được entry sau đánh dấu thay thế.

## File thay đổi

- `src/frontend/src/components/home/HomeView.tsx` — sửa nhiều lần: carousel, panel tìm kiếm, DatePicker, nội dung điểm đến/khách sạn, tiêu đề section, Trust Badge và các nút Xem thêm.
- `src/frontend/src/context/TravelContext.tsx` — bỏ cuộn trang trước điều hướng.
- `src/frontend/src/components/assistant/AiFloatingWidget.tsx` — sửa sidebar/fullscreen, lịch sử chat, timeline, footer checkout và trạng thái khởi tạo.
- `src/frontend/src/components/assistant/AssistantView.tsx` — bỏ itinerary Nha Trang tự sinh.
- `src/frontend/src/components/assistant/ItineraryMap.tsx` — bố trí điều khiển Leaflet và map trong giao diện fullscreen.
- `src/frontend/src/components/common/ProductCard.tsx` — bỏ BecauseLine theo variant.
- `src/frontend/next-env.d.ts` — Next.js tự cập nhật type reference trong lần build được ghi nhận.
- `src/frontend/public/mascot_hello.png`, `src/frontend/public/trust_badge_ecosystem.png`, `src/frontend/public/trust_badge_booking.png`, `src/frontend/public/trust_badge_ai_assistant.png` — thêm ảnh.

## Quyết định

- Giữ trải nghiệm tìm kiếm theo từng panel và nội dung điểm đến gắn với khách sạn cụ thể; lựa chọn ngày/số lượng cập nhật tức thì, không yêu cầu nút xác nhận phụ.
- Giữ các thay đổi trợ lý dựa trên intent/catalog; trạng thái mới bắt đầu không có lịch trình giả. Thanh toán dùng giá từ itinerary hiện có và điều hướng sau khi checkout sẵn sàng.
- Trạng thái cuối của ProductCard là bỏ BecauseLine ở cả compact và grid.
- Kết quả kiểm tra dưới đây được ghi nhận từ các lần thực hiện thay đổi; không chạy lại trong lần tổng hợp này.

## Kiểm tra

- Các lần kiểm tra ghi nhận Next.js web/API build, typecheck và contract validation pass ở những thay đổi tương ứng.
- Entry ẩn Xem thêm ghi nhận typecheck và lint pass, với lint warnings có sẵn.
- Không có kiểm tra mới được chạy trong lần gộp tài liệu này.

## Còn lại / rủi ro

- Không còn việc đáng kể được ghi nhận. Các nút Xem thêm được giữ ở dạng comment để bật lại khi trang danh mục/điều hướng tương ứng hoàn thiện.
