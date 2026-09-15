# Research UX — Hệ thống Gợi ý Du lịch (V-OTA)

**Brief cho agent nghiên cứu UX**

Đây là brief giao việc cho một agent (Claude Code hoặc tương đương) thực hiện nghiên cứu UX cho sản phẩm được mô tả trong `recsys-internship-handbook-v3-vi.md`. Đọc handbook đó trước — brief này không lặp lại phần kiến trúc kỹ thuật hay recommendation engine, chỉ tập trung vào trải nghiệm người dùng của web app.

---

## 1. Bối cảnh

Sản phẩm là một demo đặt dịch vụ du lịch (Vinpearl/V-OTA) với recommendation engine ở trung tâm. Khách hàng tìm kiếm, đăng nhập, nhận gợi ý cá nhân hóa, trò chuyện với trợ lý lên kế hoạch chuyến đi, và đặt dịch vụ.

Các màn hình đã được xác định trong handbook (§2, §4, §10):

- Home (cá nhân hóa)
- Search / kết quả tìm kiếm
- Product detail
- Cart
- Checkout
- Confirmation
- Login / Register
- Chat assistant (trợ lý lịch trình)

UX phải phục vụ đúng vòng lặp cốt lõi của dự án: **đặt một khách sạn → gợi ý trên trang chủ chuyển sang vé máy bay/vé tham quan**, và phải hiển thị được lý do gợi ý (`because`, xem handbook §7) một cách dễ hiểu với người dùng cuối, không chỉ trong response API.

## 2. Mục tiêu nghiên cứu

Sản xuất một đặc tả UX (`product.md`, xem §4) đủ chi tiết để workstream Web dùng làm căn cứ thiết kế và implement giao diện, bao gồm:

1. Information architecture / luồng điều hướng giữa các màn hình
2. Đặc tả từng màn hình: bố cục, thành phần chính, nội dung hiển thị, trạng thái (rỗng / đang tải / lỗi)
3. Cách hiển thị cá nhân hóa và giải thích gợi ý (`because`) trên UI sao cho khách hàng tin tưởng được
4. Luồng trợ lý lịch trình (chat) và cách nó render kế hoạch kèm sản phẩm thật, link đặt dịch vụ
5. Bố cục mobile cho toàn bộ luồng
6. Đề xuất được neo vào các pattern thực tế từ ứng dụng du lịch/OTA đang chạy production — không phải suy đoán từ đầu

## 3. Công cụ bắt buộc: MCP Mobbin

Agent thực hiện nghiên cứu **phải sử dụng MCP server `mobbin`** (đã được đăng ký ở user scope, xem `claude mcp list`) trong suốt quá trình nghiên cứu, không chỉ tham khảo trí nhớ nội tại.

Cách dùng:

- Dùng các tool của `mobbin` để tra cứu screen/flow thật từ các ứng dụng cùng ngành: OTA và du lịch (Booking.com, Agoda, Traveloka, Klook, Airbnb, Trip.com), e-commerce cho luồng cart/checkout, và các app có trợ lý chat/AI assistant cho luồng lập lịch trình.
- Với mỗi màn hình trong phạm vi (§2), tra cứu ít nhất 2–3 app tham chiếu qua Mobbin trước khi viết đặc tả cho màn hình đó.
- Trích dẫn rõ trong `product.md`: app nào, màn hình/flow nào, lấy được pattern gì — không chỉ nói chung chung "theo chuẩn ngành".
- Nếu Mobbin không có kết quả phù hợp cho một luồng cụ thể (ví dụ trợ lý lập lịch trình AI còn hiếm), ghi rõ điều đó trong `product.md` thay vì bịa ra nguồn.

## 4. Đầu ra bắt buộc

**Kết quả nghiên cứu phải được ghi vào đúng một file: `product.md`**, đặt tại thư mục gốc repo (cùng cấp với `spec/`), không tạo thêm file phụ hoặc rải kết quả ra nhiều nơi.

Cấu trúc gợi ý cho `product.md`:

```markdown
# Product UX Spec — [tên sản phẩm]

## 1. Tổng quan & phạm vi
## 2. Personas / tài khoản seed (đối chiếu handbook §8)
## 3. Information architecture — sơ đồ luồng màn hình
## 4. Đặc tả từng màn hình
   - Home (cá nhân hóa)
   - Search / kết quả
   - Product detail
   - Cart / Checkout / Confirmation
   - Login / Register
   - Chat assistant (trợ lý lịch trình)
   Mỗi màn hình: bố cục, thành phần, dữ liệu hiển thị, trạng thái rỗng/loading/lỗi,
   pattern tham chiếu từ Mobbin (app + màn hình cụ thể).
## 5. Hiển thị cá nhân hóa & giải thích gợi ý (`because`)
## 6. Luồng trợ lý lịch trình — từ tin nhắn tới kế hoạch có thể đặt dịch vụ
## 7. Mobile layout
## 8. Nguồn tham khảo Mobbin (danh sách app/screen đã tra cứu)
```

Nếu agent thấy cấu trúc khác phù hợp hơn thì có thể điều chỉnh, nhưng tên file đầu ra (`product.md`) và việc mọi phần nghiên cứu đều dồn về một file duy nhất là bắt buộc.

## 5. Ngoài phạm vi

- Không thiết kế lại recommendation engine, schema dữ liệu, hay kiến trúc backend — những phần đó đã cố định trong handbook.
- Không đề xuất luồng thanh toán thật hay xác thực nâng cao (OAuth, 2FA...) — handbook đã loại trừ rõ ở §8.
- Không tạo mockup hình ảnh/Figma trừ khi được yêu cầu thêm — đầu ra là đặc tả dạng văn bản trong `product.md`.

## 6. Tiêu chí hoàn thành

- `product.md` tồn tại, đầy đủ các màn hình trong phạm vi §2.
- Mọi đề xuất UX quan trọng có ít nhất một pattern tham chiếu tra được qua MCP Mobbin, trích dẫn rõ nguồn.
- Cách hiển thị `because` và cá nhân hóa được mô tả cụ thể, không chỉ nói "hiển thị lý do gợi ý" chung chung.
- Luồng trợ lý lịch trình mô tả rõ cách render kế hoạch với sản phẩm thật + link đặt dịch vụ, khớp nguyên tắc "LLM không tự bịa sản phẩm" (handbook §9).
