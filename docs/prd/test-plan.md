# Test Plan & Quality Assurance — V-OTA Platform

Tài liệu này xác định toàn bộ chiến lược kiểm thử, quy trình xác thực chất lượng và các tiêu chuẩn nghiệm thu kỹ thuật nhằm đảm bảo độ tin cậy của toàn bộ nền tảng V-OTA.

---

## 1. Chiến Lược Kiểm Thử & Tháp Kiểm Thử (Testing Pyramid)

Hệ thống áp dụng mô hình tháp kiểm thử 5 tầng toàn diện:

```
                  / \
                 /   \      [Tầng 5: RecSys & AI Grounding Evaluation]
                / E2E \     [Tầng 4: End-to-End User Flow Tests]
               /-------\
              / Integr. \   [Tầng 3: Database & Adapter Integration Tests]
             /-----------\
            /   Contract  \ [Tầng 2: OpenAPI Contract Schema Validation]
           /---------------\
          /   Unit Tests    \[Tầng 1: Domain Entities & Application Use Cases]
         ---------------------
```

---

## 2. Các Tầng Kiểm Thử Chi Tiết

### 2.1. Tầng 1: Kiểm Thử Đơn Vị (Unit Testing)
- **Mục tiêu:** Kiểm tra độc lập các quy tắc nghiệp vụ cốt lõi, logic tính giá phòng/vé, thuật toán phân rã combo và các hàm tiện ích.
- **Phạm vi kiểm tra:**
  - `src/backend/app/domain/`: Tính hợp lệ của Entity, State transition của Booking.
  - `src/backend/app/application/use_cases/`: Các luồng điều phối nghiệp vụ với mock ports.
- **Công cụ thực thi:** `pytest`, `pytest-cov`, `unittest.mock`.
- **Tiêu chuẩn vượt qua:** Tỷ lệ bao phủ dòng mã (Code Coverage) $\ge 80\%$ trên các thư mục `domain` và `application`.

### 2.2. Tầng 2: Kiểm Thử Hợp Đồng (Contract Testing)
- **Mục tiêu:** Đảm bảo tính nhất quán tuyệt đối giữa tài liệu đặc tả OpenAPI, mock fixture và mã nguồn triển khai thực tế.
- **Phạm vi kiểm tra:**
  - Định dạng cú pháp của toàn bộ file YAML trong `src/shared/contracts/`.
  - Kiểm tra đối chiếu xem các mock fixtures trong `src/shared/mocks/` có tuân thủ 100% schema hay không.
- **Lệnh thực thi bắt buộc:**
  ```bash
  PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py
  ```
- **Tiêu chuẩn vượt qua:** 100% tests pass, không có cảnh báo vi phạm kiểu dữ liệu hoặc thiếu trường bắt buộc (`required`).

### 2.3. Tầng 3: Kiểm Thử Tích Hợp & Cơ Sở Dữ Liệu (Integration Testing)
- **Mục tiêu:** Xác thực tính toàn vẹn dữ liệu, quyền hạn RBAC của database và sự hoạt động chính xác của các adapter giao tiếp cơ sở dữ liệu.
- **Các kịch bản trọng yếu:**
  - Kiểm tra quyền cách ly: Role `vota_app` không thể đọc hoặc ghi vào schema `cdp`.
  - Kiểm tra cơ chế giao dịch bù trừ: Khi ghi `cdp.events` thành công nhưng commit đơn hàng tại `app.bookings` thất bại, adapter phải kích hoạt lệnh hủy/bù trừ sự kiện.
  - Kiểm tra webhook Stripe: webhook sai chữ ký bị từ chối và không đổi dữ liệu; webhook gửi trùng không đổi trạng thái lần hai.
  - Chạy kịch bản SQL thẩm định hệ thống:
    ```bash
    psql "$SEED_DATABASE_URL" -f db/verify.sql
    psql "$SEED_DATABASE_URL" -f db/verify_insider.sql
    ```
- **Tiêu chuẩn vượt qua:** Toàn bộ các câu lệnh kiểm tra trong `db/verify.sql` và `db/verify_insider.sql` đều trả về trạng thái `PASS` (ngoại trừ các trường hợp cố ý giới hạn khi chạy trên catalog tổng hợp nhỏ).

### 2.4. Tầng 4: Kiểm Thử Tác Tử AI & Nguyên Tắc Grounding (AI & Grounding QA)
- **Mục tiêu:** Đảm bảo Trợ lý Lịch trình AI hoạt động ổn định, trích xuất chính xác ý định và tuyệt đối không bịa đặt sản phẩm (Zero Hallucination).
- **Bộ dữ liệu kiểm thử (Evaluation Benchmark Dataset):**
  - Tập 50 câu prompt đa dạng: từ yêu cầu rõ ràng đến các câu hỏi mơ hồ, câu hỏi có điều kiện ngân sách ngặt nghèo, hoặc các yêu cầu cố tình bẫy địa danh không có trong catalog.
- **Chỉ số đánh giá:**
  - **Tool Calling Accuracy:** $\ge 95\%$ trường hợp gọi đúng công cụ tìm kiếm với các tham số địa điểm, thời gian hợp lệ.
  - **Grounding Rate:** Bắt buộc đạt $100\%$. Tất cả các ID sản phẩm được render thành thẻ đặt chỗ phải tồn tại thực trong bảng `cdp.products`.
  - **Structured Output Integrity:** Phản hồi JSON khớp chính xác schema `ItineraryOutput`.

### 2.5. Tầng 5: Đánh Giá Thuật Toán Gợi Ý (RecSys Offline Evaluation)
- **Mục tiêu:** Định lượng chất lượng của các thuật toán đề xuất sản phẩm và tìm kiếm ngữ nghĩa.
- **Các độ đo đánh giá (Evaluation Metrics):**
  - **NDCG@10 (Normalized Discounted Cumulative Gain):** Đo lường chất lượng xếp hạng của kết quả tìm kiếm ngữ nghĩa.
  - **Recall@K (K=5, 10):** Tỷ lệ sản phẩm người dùng thực sự quan tâm xuất hiện trong danh sách đề xuất.
  - **Catalog Coverage:** Tỷ lệ phần trăm tổng số sản phẩm trong kho được hệ thống đưa vào các gợi ý (tránh thiên lệch chỉ gợi ý một số ít sản phẩm nổi tiếng).
  - **Diversity & Novelty:** Độ đa dạng về loại hình dịch vụ trong một trang gợi ý (kết hợp hài hòa giữa khách sạn, vé máy bay và tour trải nghiệm).

---

## 3. Kế Hoạch Kiểm Thử Chấp Nhận Đầu-Cuối (End-to-End User Acceptance Test)

Kịch bản xác thực tổng thể trước khi phát hành phiên bản mới:

| Bước | Hành động người dùng | Kỳ vọng hệ thống | Kiểm tra ngầm (Backend/DB) |
|---|---|---|---|
| 1 | Truy cập Trang chủ ẩn danh | Thấy danh sách gợi ý phổ biến/trending | **Không** sinh sự kiện trong `cdp.events` (khách chưa đăng nhập không được tracking — FR-CDP-02 hoãn) |
| 2 | Nhập tìm kiếm: *"khách sạn trung tâm có hồ bơi"* | Trả về danh sách khách sạn phù hợp ngữ nghĩa | Không sinh sự kiện `search` vì đang ẩn danh |
| 3 | Mở xem chi tiết sản phẩm khách sạn A | Hiển thị đủ ảnh, tiện ích, lịch phòng khả dụng | Không sinh sự kiện `product_view` vì đang ẩn danh |
| 4 | Đăng nhập tài khoản Persona P1 (Gia đình), rồi tìm kiếm và xem lại khách sạn A | Trang chủ chuyển sang giao diện cá nhân hóa cho gia đình; trình duyệt chỉ có cookie `vota_sid`, không có token | Từ lúc này mới sinh `search`, `product_view` gắn `cdp_user_id` của P1; không gộp lịch sử ẩn danh |
| 5 | Mở Trợ lý AI, yêu cầu lên lịch trình 3N2Đ | Nhận được kế hoạch có cấu trúc, chứa thẻ đặt phòng khách sạn thật | Log Agent ghi nhận luồng StateGraph và tool call thành công |
| 6 | Bấm Đặt ngay ở khách sạn A, điền thông tin, chọn Stripe, bấm Thanh toán và trả bằng thẻ test `4242 4242 4242 4242` | Qua trang Stripe, quay về trang thành công với mã `VOTA-…` | `app.bookings` = `confirmed`, `app.payments` = `succeeded`, có event `purchase` trong CDP |
| 7 | Quan sát màn hình xác nhận đơn hàng | Hiển thị các khối gợi ý vé máy bay và tour phù hợp với chuyến đi vừa đặt | API recommendation nhận context `checkout_confirmation` |
| 8 | Huỷ đơn vừa đặt | Đơn `CANCELLED` | Stripe Dashboard (test) có refund; event `purchase` bị huỷ |

---

## 4. Báo Cáo & Tự Động Hóa Kiểm Thử (CI/CD Pipeline)

Mỗi lần có mã nguồn mới được đẩy lên repository:
1. **Lint & Static Check:** Chạy Flake8 / Ruff / ESLint để đảm bảo chuẩn code style.
2. **Contract Check:** Chạy `validate_contract.py` kiểm tra toàn bộ file YAML.
3. **Automated Unit Tests:** Chạy test suite của Backend và Frontend.
4. **Integration Smoke Test:** Khởi động container Postgres, chạy seed tối giản, xác nhận các endpoint chính phản hồi HTTP 200.
