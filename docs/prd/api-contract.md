# API Contract & Communication Standards — V-OTA Platform

Tài liệu này đặc tả quy chuẩn giao tiếp dữ liệu giữa Frontend, Backend, Trợ lý AI và các dịch vụ tích hợp. Nguồn sự thật (Single Source of Truth) của API được định nghĩa tại `src/shared/contracts/openapi.yaml`.

---

## 1. Nguyên Tắc Thiết Kế & Chuẩn Giao Thức

### 1.1. Tiêu chuẩn thiết kế RESTful
- Mọi API sử dụng định dạng dữ liệu JSON (`Content-Type: application/json; charset=utf-8`).
- Sử dụng chuẩn URL dạng danh từ số nhiều (ví dụ: `/products`, `/bookings`).
- Sử dụng các HTTP Method đúng ngữ nghĩa: `GET` (đọc), `POST` (tạo mới / hành động phức tạp), `PUT` (thay thế toàn bộ), `PATCH` (cập nhật từng phần), `DELETE` (xóa).

### 1.2. Chuẩn định dạng Phản hồi Lỗi (Error Envelope Standard)
Mọi phản hồi lỗi (HTTP status code $\ge 400$) đều phải trả về theo cấu trúc chuẩn:
```json
{
  "error": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "Sản phẩm với mã hotel_vnp_nt_01 không tồn tại hoặc đã ngừng kinh doanh.",
    "details": {
      "productId": "hotel_vnp_nt_01",
      "timestamp": "2026-09-22T02:15:00Z"
    }
  }
}
```

### 1.3. Chuẩn phân trang (Pagination Envelope)
Các API trả về danh sách sử dụng cơ chế phân trang dựa trên `page` và `pageSize`:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 156,
    "totalPages": 8
  }
}
```

---

## 2. Danh Mục Các Phân Nhóm API Chính

### 2.1. Phân Nhóm Xác Thực & Phiên Người Dùng (`/api/v1/auth`)
| Phương thức | Endpoint | Chức năng | Dữ liệu chính |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Đăng nhập tài khoản | `email`, `password` $\rightarrow$ Auth token / Cookie session |
| `POST` | `/api/v1/auth/logout` | Hủy phiên đăng nhập | Thu hồi token |
| `GET` | `/api/v1/auth/me` | Lấy thông tin hồ sơ hiện tại | Trả về `userId`, `email`, `fullName`, `personaTag` |
| `POST` | `/api/v1/auth/persona-switch` | Chuyển đổi nhanh persona | Nhận `personaTag` (`P1_family`, `P2_biz`,...) $\rightarrow$ Phiên mới |

### 2.2. Phân Nhóm Danh Mục Sản Phẩm (`/api/v1/products`)
| Phương thức | Endpoint | Chức năng | Ghi chú & Ràng buộc |
|---|---|---|---|
| `GET` | `/api/v1/products` | Lấy danh sách sản phẩm | Hỗ trợ lọc theo `destination`, `productType`, `priceMin`, `priceMax` |
| `GET` | `/api/v1/products/{id}` | Lấy chi tiết một sản phẩm | Trả về đầy đủ 13 trường chuẩn + `attributes` chi tiết |
| `GET` | `/api/v1/products/{id}/availability` | Kiểm tra lịch trống | Trả về lịch khả dụng 30 ngày (`calendar` string "1/0") |

### 2.3. Phân Nhóm Tìm Kiếm Ngữ Nghĩa (`/api/v1/search`)
- **Endpoint:** `POST /api/v1/search`
- **Request Payload:**
  ```json
  {
    "query": "resort yên tĩnh có hồ bơi riêng cho gia đình",
    "destination": "Nha Trang",
    "priceRange": { "min": 2000000, "max": 6000000 },
    "checkInDate": "2026-10-15",
    "checkOutDate": "2026-10-17",
    "page": 1,
    "pageSize": 10
  }
  ```
- **Response Payload:** Trả về danh sách sản phẩm kèm điểm tương đồng ngữ nghĩa (`similarityScore`) và nhãn tiện ích nổi bật.

### 2.4. Phân Nhóm Gợi Ý Cá Nhân Hóa (`/api/v1/recommendations`)
- **Endpoint:** `GET /api/v1/recommendations`
- **Tham số truy vấn (Query Params):**
  - `context`: Ngữ cảnh hiển thị (`home`, `product_detail`, `checkout_confirmation`).
  - `targetId`: ID sản phẩm tham chiếu (khi ở trang chi tiết) hoặc ID đơn hàng vừa đặt.
  - `limit`: Số lượng sản phẩm muốn nhận (mặc định 6).
- **Định dạng trả về:**
  ```json
  {
    "sectionTitle": "Gợi ý hoàn thiện chuyến đi Nha Trang",
    "context": "checkout_confirmation",
    "items": [
      {
        "productId": "flight_vna_cxr_01",
        "title": "Vé máy bay Vietnam Airlines SGN - CXR",
        "price": 1450000,
        "productType": "flight",
        "because": "Phù hợp với thời gian nhận phòng tại Vinpearl Resort của bạn"
      }
    ]
  }
  ```

### 2.5. Phân Nhóm Trợ Lý Lập Lịch Trình AI (`/api/v1/assistant`)
- **Tạo hội thoại mới:** `POST /api/v1/assistant/conversations`
- **Gửi tin nhắn & Lập lịch trình:** `POST /api/v1/assistant/chat`
  - **Request:**
    ```json
    {
      "conversationId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "message": "Mình muốn đi Phú Quốc 3N2Đ cùng bạn bè, thích lặn biển và ăn hải sản, ngân sách khoảng 6 triệu/người"
    }
    ```
  - **Response (Hỗ trợ Streaming hoặc JSON chuẩn):**
    ```json
    {
      "messageId": "msg_90124",
      "content": "Dưới đây là gợi ý lịch trình 3N2Đ tại Phú Quốc được thiết kế riêng cho nhóm bạn...",
      "structuredData": {
        "destination": "Phú Quốc",
        "days": 3,
        "items": [
          {
            "day": 1,
            "productId": "tour_pq_snorkeling_01",
            "isProduct": true,
            "title": "Tour cano 4 đảo & Lặn ngắm san hô",
            "price": 850000,
            "actionUrl": "/products/tour_pq_snorkeling_01"
          }
        ]
      }
    }
    ```

### 2.6. Phân Nhóm Quản Lý Đơn Hàng (`/api/v1/bookings`)
- **Tạo đơn đặt chỗ:** `POST /api/v1/bookings`
  - Nhận danh sách các mục đặt chỗ (`items`: `productId`, `usingDate`, `quantity`).
  - Hệ thống kiểm tra lịch khả dụng $\rightarrow$ Ghi nhận event sang CDP $\rightarrow$ Tạo bản ghi trong `app.bookings`.
- **Xem chi tiết đơn hàng:** `GET /api/v1/bookings/{bookingCode}`

### 2.7. Phân Nhóm Theo Dõi Hành Vi Khách Hàng (`/api/v1/events`)
- **Endpoint:** `POST /api/v1/events`
- **Payload:**
  ```json
  {
    "eventType": "product_view",
    "anonymousId": "anon_9281a17",
    "productId": "hotel_vnp_nt_01",
    "eventTime": "2026-09-22T02:15:30Z",
    "properties": {
      "source": "recommendation_home",
      "viewport": "desktop"
    }
  }
  ```

---

## 3. Quy Tắc Grounding & Kiểm Soát Tính Nhất Quán Dữ Liệu

1. **Ràng buộc trường bắt buộc (Contract Invariants):**
   - Trường `productId` trong mọi API phản hồi phải là chuỗi định danh duy nhất có thật trong hệ thống.
   - Trường `price` luôn là số nguyên hoặc số thực dương, đơn vị tính chuẩn là VND.
   - Mọi đề xuất cá nhân hóa bắt buộc phải có thuộc tính `because` giải thích lý do gợi ý cho người dùng.
2. **Quy tắc Tương thích Ngược (Backward Compatibility):**
   - Trong phiên bản API v1, tuyệt đối không được xóa, đổi tên hoặc thay đổi ngữ nghĩa của các trường hiện hữu.
   - Các trường mới bổ sung bắt buộc phải ở dạng không bắt buộc (Optional).
   - Những thay đổi mang tính phá vỡ cấu trúc (Breaking changes) phải được thảo luận và nâng cấp lên phiên bản API v2 (`/api/v2/...`).

---

## 4. Cơ Chế Xác Thực & Kiểm Thử Hợp Đồng Tự Động

- **Kiểm thử tự động:** Mọi thay đổi trong các file contract YAML (`src/shared/contracts/paths/`, `schemas/`) phải vượt qua bài kiểm tra tính hợp lệ bằng lệnh:
  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py
  ```
- **Xác thực dữ liệu tại Runtime:** Backend sử dụng Pydantic models được sinh từ hợp đồng để đảm bảo mọi request/response đi qua API đều khớp 100% với đặc tả kỹ thuật đã cam kết.
