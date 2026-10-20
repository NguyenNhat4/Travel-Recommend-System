# Fixture cho Itinerary Agent

Team Agent dùng bộ này để phát triển và kiểm thử; Team Web dùng các response để dựng giao diện khi Agent API chưa chạy. Schema dùng chung nằm trong [OpenAPI](../../contracts/openapi.yaml); phiên bản hợp đồng được quản lý tại đó.

| File | Vai trò | Team sử dụng |
|---|---|---|
| `products.json` | ProductSummary ánh xạ từ 50 sản phẩm sample; không phải response Search đầy đủ | Agent, Search/Backend |
| `search-request.json` | Request Agent gửi sang Search | Agent, Search/Backend |
| `completed.json` | Response Agent trả lịch trình | Agent, Web |
| `needs-clarification.json` | Response Agent hỏi thêm thông tin | Agent, Web |
| `explore-ten.json` | Lượt yêu cầu 10 khách sạn; sản phẩm từ sample, kiểm contract 1.28.0 và danh sách 10 thẻ trên Web | Agent, Web |
| `no-results.json` | Response Agent không có kết quả phù hợp | Agent, Web |
| `fallback.json` | Response Agent trả ứng viên khi chưa dựng được lịch trình | Agent, Web |

Sản phẩm lấy từ sample thật; lịch trình, request ID và conversation ID là dữ liệu kiểm thử. Thư mục `../assistant/` chứa fixture UI tổng hợp có sẵn, được liệt kê trong `../index.json`.

Chạy từ repo root: `python3 src/shared/contracts/tests/validate_contract.py`.

MVP 1.2.0: `recommendations-minimal.json` dùng cho card gợi ý, `completed-minimal.json` dùng cho lịch trình. Hai file minh họa payload tối thiểu; fixture đầy đủ vẫn dùng để kiểm tra tương thích.
