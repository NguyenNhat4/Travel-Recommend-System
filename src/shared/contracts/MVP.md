# API tối thiểu để hiển thị gợi ý — 1.2.0

Mục tiêu MVP: người dùng thấy sản phẩm phù hợp, giá tham khảo, ảnh và lý do được gợi ý. Không cần gửi toàn bộ catalog hoặc dữ liệu thuật toán ra Web. Đây là cập nhật hiện hành về required/optional, thay thế các danh sách bắt buộc của baseline 1.1; quy tắc giá snapshot và grounding vẫn giữ nguyên.

## Recommendation → Web

Response chỉ bắt buộc `strategy` và `recommendations`. Thứ tự mảng là thứ tự hiển thị, không cần rank/score để render.

| Trường sản phẩm | Dùng để |
|---|---|
| productId | Mở trang `/product/{productId}` |
| name | Tên trên card |
| taxonomy | Loại sản phẩm |
| destination | Điểm đến |
| unitPrice, currency | Giá tham khảo; null hiển thị “Chưa có giá” |
| available | Trạng thái snapshot; không phải xác nhận tồn kho |
| because | Lý do gợi ý từ lịch sử; [] nếu chưa có căn cứ |

`imageUrl` tùy chọn nhưng nên gửi; thiếu thì Web dùng placeholder. `priceUnit` thiếu là UNKNOWN, không tự thêm “/người” hoặc “/đêm”. `attributes`, score, rank, modelVersion, diagnostics và các trường metadata không cần gửi trong luồng hiển thị cơ bản. Chỉ gửi khi tính năng UI cần chúng.

Mỗi because chỉ cần `productName`, `event`, `daysAgo`. Ví dụ khi có lịch sử thật: người dùng đã xem một khách sạn 2 ngày trước → Web dựng câu “Vì bạn đã xem … cách đây 2 ngày”. Không có lịch sử thì trả [] và dùng nhãn “Gợi ý phổ biến”, không tạo lý do cá nhân hóa giả. `contribution`, ảnh và ID của sản phẩm lịch sử là tùy chọn.

Fixture chạy được: [recommendations-minimal.json](../mocks/itinerary-agent/recommendations-minimal.json). Fixture này dùng sản phẩm sample thật và strategy popular, vì sample không cung cấp lịch sử người dùng.

## Search → Agent

Request tối thiểu: query. Thông thường gửi thêm destination, taxonomy, limit. Các bộ lọc còn lại tùy nhu cầu. Response chỉ bắt buộc results và total; facets, topScore, phân trang và requestId là tùy chọn. ScoredProduct vẫn có score để phục vụ xếp hạng.

ProductSummary chỉ bắt buộc 7 trường card: productId, name, taxonomy, destination, unitPrice, currency, available. Attributes/ngày/mô tả tùy chọn ở summary. Agent cần đọc ProductDetail nếu thiếu dữ liệu để kiểm tra điều kiện hoặc lập lịch. ProductDetail bắt buộc description, attributes, availableFrom/To; dữ liệu nguồn đầy đủ vẫn ở backend, không mất vì card được rút gọn.

## Agent → Web

COMPLETED chỉ bắt buộc status, conversationId, itinerary, warnings. Không bắt buộc lặp searchResults và intent hoặc gửi metadata.

- itinerary: days, estimatedTotal, currency, budgetStatus.
- Mỗi ngày: day, slots.
- Mỗi slot: time, product, note. Nếu product=null thì cần activityType.
- source, because, giờ chính xác, tiêu đề, stay và bookableCount là tùy chọn. Khi có lý do recommendation thì giữ because để Web hiển thị.
- Tổng chưa tính được: null + UNKNOWN, kèm warning; không biến thiếu giá thành 0.
- NEEDS_CLARIFICATION: status, conversationId, question.
- NO_RESULTS: status, conversationId, message.
- FALLBACK: status, conversationId, message, searchResults.

Fixture: [completed-minimal.json](../mocks/itinerary-agent/completed-minimal.json).

## Cách dùng

Backend trả bộ tối thiểu cho MVP; Web không giả định trường tùy chọn luôn có. Payload cũ nhiều trường vẫn hợp lệ. Cần cập nhật type/client khi dùng 1.2.0 vì client cũ có thể đang đọc metadata/attributes bắt buộc.

Chạy `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` từ repo root. Kiểm tra bao gồm cả payload tối thiểu và fixture cũ. Chưa phải bằng chứng backend thực tế đã trả payload rút gọn.
