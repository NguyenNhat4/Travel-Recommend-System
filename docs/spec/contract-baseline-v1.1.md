# Baseline tích hợp 1.1.0 — 16/09/2026

> **MVP 1.2.0:** ưu tiên hiển thị recommendation; [bộ trường tối thiểu](mvp-minimal-fields-1.2.0.md) và OpenAPI hiện hành thay thế danh sách required/optional cũ bên dưới. Các trường mở rộng vẫn được hỗ trợ nhưng không bắt buộc gửi.

Baseline này chốt cấu trúc để Search, Agent, Backend và Web làm độc lập theo [OpenAPI](../../src/shared/contracts/openapi.yaml). Đây là quyết định triển khai trong repo theo yêu cầu chủ dự án, không phải xác nhận các service đã triển khai hoặc các team đã nghiệm thu. Phần còn chờ xác nhận được ghi riêng bên dưới.

## Quyết định đã chốt

| Phần | Quyết định |
|---|---|
| SearchRequest | query bắt buộc; taxonomy viết thường; giá phẳng priceMin/priceMax; chỉ chấp nhận các khóa đã khai báo |
| Default | Optional null tương đương bỏ qua. availableOnly=true, limit=20, offset=0, sort=relevance; implementation phải áp default, validator không tự điền |
| Giá tìm kiếm | Lọc trên unitPrice VND, không phải ngân sách chuyến đi. Giá null không khớp bộ lọc giá |
| Ngày/party | Chưa có trong SearchRequest; Agent hậu kiểm và cảnh báo, không tuyên bố Search đã xác minh theo ngày/party |
| ProductSummary | Giữ taxonomy/unitPrice/currency và attributes nguyên bản; unitPrice và availableFrom/To nullable; sao thập phân và boolean false hợp lệ |
| Mô tả | Search nên trả description; Agent lấy ProductDetail nếu thiếu. RecommendationItem là projection cần hydrate qua ProductDetail |
| Đơn vị | priceUnit optional; thiếu là UNKNOWN. Không tự suy đơn vị theo taxonomy. Không ép mọi combo thành lưu trú |
| URL | Web dựng /product/{productId}; endpoint API là /api/v1/products/{productId}; không có bookingUrl trong product |
| Recommendation | Query k; response recommendations, strategy viết thường, because[]. Không dùng limit/results/reason của spec Agent cũ |
| ItineraryResponse | HTTP 200: COMPLETED, NEEDS_CLARIFICATION, NO_RESULTS, FALLBACK; lỗi non-200 dùng ErrorResponse |
| Kế hoạch | stay riêng, days[].slots[].product dùng ProductSummary, hoạt động chung product=null |
| Tổng | estimatedTotal nullable; thiếu cơ sở thì null + UNKNOWN + warnings. Đủ tổng nhưng không có ngân sách dùng NO_BUDGET |
| Thời điểm giá | priceAsOf nullable; không dùng generatedAt thay ngày quan sát giá nguồn |
| Version | 1.1.0 là baseline trước integration. Các nullable/enum mở rộng cần regenerate client; không coi là tương thích với client 1.0 chưa xử lý null |

## Kết quả đối chiếu sample

50 ID duy nhất, 13 trường/bản ghi, 9 điểm đến. 8 property, 15 room, 5 attraction, 4 route, 9 flight, 5 combo, 4 golf. Không có cha bị thiếu. Có 1 giá null, 3 memberPrices, 12 policies, 1 descriptionOriginal. available có 49 true và 1 false; false của điểm không bán vé không chứng minh sản phẩm hết chỗ.

Bộ [fixture từ sample](../../src/shared/mocks/itinerary-agent) giữ nguyên trường nguồn. Giá trị UNKNOWN là quyết định adapter thận trọng, không phải dữ liệu crawl. Lịch trình/request ID là dữ liệu kiểm thử. Bộ fixture UI cũ vẫn là dữ liệu tổng hợp, không dùng làm bằng chứng sản phẩm tồn tại trong sample.

## Phần chờ xác nhận — đã gửi câu hỏi cho chủ dự án

| Chủ sở hữu | Cần cung cấp | Quy tắc tạm thời và phạm vi bị chặn |
|---|---|---|
| Backend/Booking | MVP giả lập snapshot hay kiểm tra nguồn trực tiếp? Nếu trực tiếp: endpoint, auth, request theo ngày/khách/số lượng, giá trả về, timeout/mã lỗi | Không cam kết còn chỗ; có thể làm UI/mock. Chưa nghiệm thu kiểm tra giá/tồn kho thực tế |
| Data + Booking | Đơn vị giá, thành phần combo, điều kiện trẻ em/thành viên/số phòng; mapping máy đọc được kèm ví dụ | priceUnit=UNKNOWN, tổng chưa đủ cơ sở=null. Chưa nghiệm thu dự toán đầy đủ và checkout cho trường hợp thiếu đơn vị |

Chủ dự án sẽ phản hồi sau; không diễn giải việc chờ phản hồi là đồng ý một phương án. Khi có câu trả lời, cập nhật adapter/quy tắc và fixture; chỉ thay schema khi cần thêm dữ liệu giao tiếp.

## Phân công có thể bắt đầu ngay

- Search/Backend: adapter sample → ProductSummary/ScoredProduct, giữ attributes; thực hiện bộ lọc và default SearchRequest. Chuẩn hóa score 0–1 trước khi trả.
- Agent: SearchClient theo contract, hydrate recommendation thiếu trường, intent merge, 4 nhánh response, warnings cho snapshot và giá chưa biết.
- Web: sinh type từ OpenAPI; render nullable, UNKNOWN và ActivityNote; nhãn boolean chỉ hiện khi true; không render mọi giá trị attributes thành tag. Dựng route số ít; ẩn CTA ticketed=false.
- Integration: chạy script kiểm tra bên dưới trước khi đổi contract; dùng fixture từ sample cho grounding, fixture tổng hợp cho UI/error states.

## Kiểm tra bắt buộc

`python3 src/shared/contracts/tests/validate_contract.py` (PyYAML, jsonschema).

Script kiểm tra schema JSON Schema 2020-12, local refs, 50 sản phẩm giữ nguyên trường, cha–con, 4 nhánh response, payload sai và fixture UI hiện có. Đây không phải kiểm thử server hay validator đầy đủ mọi quy tắc OpenAPI.

Các bất biến liên trường phải kiểm tra ở runtime: priceMin <= priceMax; đúng destination/ngày/điểm đi; days đủ số ngày và đánh số liên tục; thời gian không chồng nhau, timezone/qua đêm được xử lý; không cộng giá cha và con hoặc quyền lợi combo trùng; ID/tên/giá có trong nguồn retrieval; phép tính tổng và bookableCount đúng. Khoảng ngày null không được dùng để tuyên bố ngày nào cũng có chỗ. Mục tiêu latency/grounding phải đo riêng khi service chạy.
