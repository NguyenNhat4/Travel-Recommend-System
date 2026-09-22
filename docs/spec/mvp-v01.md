# Mục tiêu MVP v01

- Hạn chót: **thứ Hai 21/09/2026**
- Phạm vi: năm thứ "không bao giờ được bỏ" của handbook §2 — tìm kiếm, gợi ý, đăng nhập, vòng lặp đặt dịch vụ → gợi ý, bộ khung đánh giá.
- Contract áp dụng: OpenAPI hiện hành và [bộ trường tối thiểu 1.2.0](mvp-minimal-fields-1.2.0.md).

Tài liệu này chỉ chốt **đích đến và cách nghiệm thu** của v01. Chi tiết field, mã lỗi, hành vi nằm ở các hợp đồng tích hợp; khi mâu thuẫn, theo thứ tự ưu tiên trong `AGENTS.md` §2.

## 1. Thế nào là đạt MVP v01

MVP v01 đạt khi kịch bản sau chạy được **trên service thật, không dùng mock**, từ một lần khởi động sạch theo README:

```text
1. Mở Home khi chưa đăng nhập → thấy gợi ý phổ biến, không có dòng lý do cá nhân
2. Tìm "nghỉ dưỡng biển cho gia đình" → kết quả hợp lý, toàn sản phẩm thật
3. Mở chi tiết một sản phẩm → sinh product_view trong CDP clone
4. Đăng nhập tài khoản P1 (khách Nha Trang) → Home khác Home ẩn danh, có because
5. Đổi sang P4 (không lịch sử) bằng bộ chọn tài khoản demo → không có lý do cá nhân hóa
6. P1 thêm khách sạn Nha Trang vào giỏ → checkout → nhận mã VOTA-YYYYMMDD-XXXX
7. Booking sinh event purchase trong CDP clone
8. Quay lại Home → gợi ý chuyển sang danh mục còn thiếu (vé máy bay, vé tham quan)   ← K1
9. Chạy bộ đánh giá offline → có bảng Recall@10/20, NDCG@10 cho model và 3 baseline
```

Bước 8 là tiêu chí quan trọng nhất. Thiếu bước 8 thì v01 **chưa đạt**, dù các màn hình khác đã xong.

## 2. Phạm vi

| Trong v01 | Ngoài v01 (không chặn nghiệm thu) |
|---|---|
| Catalog thật trong DB + product vector trong pgvector | Trợ lý lịch trình (K3), chat UI |
| CDP clone + `CdpClient`; seed 4 persona | Insider clone, `InsiderClient`, batch push sang Insider |
| Search ngữ nghĩa, similar products | Hybrid keyword + vector, diversity re-ranking, tinh chỉnh index |
| Đăng ký/đăng nhập/JWT, tài khoản demo | Chế độ dormant (handbook §2, mục cắt số 5) |
| `/recommendations`: profile builder, loại trừ danh mục đã đặt, popular fallback, `because` | Nghiên cứu ablation |
| Booking giả lập: giỏ, checkout, đọc lại đơn, ghi `purchase` | Thanh toán thật, kiểm tra giá/tồn kho trực tiếp từ nguồn |
| Ghi `product_view`, `search`, `add_to_cart` qua Backend | Bố cục mobile hoàn chỉnh, trạng thái hoàn thiện Tuần 5 |
| Bộ khung đánh giá + 3 baseline | Mục tiêu vượt baseline (là mục tiêu Tuần 5) |

Nếu trễ tiến độ, **chỉ** được cắt thêm theo handbook §2: bỏ giỏ hàng, đi thẳng từ chi tiết sang checkout. Khi đó bước 6 đổi tương ứng và `add_to_cart` không còn là tiêu chí. Không cắt phần nào khác trong cột trái mà không hỏi chủ dự án.

## 3. Mục tiêu theo team

Mỗi team tự demo phần của mình và trỏ tới bằng chứng (lệnh test, ảnh chụp, log). Số trong cột "Nghiệm thu" tham chiếu tiêu chí gốc trong hợp đồng tương ứng.

### 3.1. Data

| Phải đạt | Nghiệm thu |
|---|---|
| Catalog chuẩn hóa nạp vào PostgreSQL Backend: đủ các taxonomy hotel/room, flight, attraction, combo, golf; tên và mô tả tiếng Việt | `data/stats.md` mục đối chiếu handbook §3; checklist "Kiểm tra trước khi coi là xong tuần 1" trong `src/data_collection/README.md` |
| Bộ dựng văn bản để embed, khác nhau theo taxonomy | Mẫu câu của ít nhất một hotel, một flight, một attraction được Search duyệt |
| Seed lịch sử khách hàng có quy luật (handbook §6), gom event theo `eventGroupId` | Baseline most-popular không cho điểm gần bằng 0 (handbook §13) |
| Seed 4 persona P1–P4 vào CDP clone và bảng `users` Backend khớp nhau | Bước kiểm tra 4 persona trong `hop-dong-tich-hop-cdp.md` §9.2 |
| Suy ra được danh mục đã đặt và điểm đến gần nhất của một chuyến | Unit test trên lịch sử của P1 |

### 3.2. CDP clone

| Phải đạt | Nghiệm thu |
|---|---|
| 5 endpoint theo `cdp-clone.openapi.yaml`, service token bắt buộc | `hop-dong-tich-hop-cdp.md` §12 tiêu chí 2 |
| Chống trùng theo `eventId`, huỷ bằng `cancelledAt` | §12 tiêu chí 7, 8 |
| Log `X-Request-ID` | §12 tiêu chí 9 |
| Test chạy xanh | `python -m pytest src/cdp_clone/tests` |

### 3.3. Search

| Phải đạt | Nghiệm thu |
|---|---|
| Chốt một embedding model đa ngôn ngữ và số chiều, ghi lý do | Bảng so sánh của Evaluation (~80 cặp truy vấn tiếng Việt) |
| Toàn bộ product vector trong pgvector kèm metadata | Số vector = số sản phẩm trong catalog |
| `POST /api/v1/search` đúng `SearchRequest`: default, lọc taxonomy/destination/giá, `availableOnly`, score 0–1 | Backend §12 tiêu chí 6, 7, 8 |
| `GET /api/v1/products/{productId}/similar` | Trả sản phẩm thật, không chứa chính nó |
| Tra vector sản phẩm theo lô đủ nhanh cho profile builder | p95 `/search` < 300 ms trên seed data (Backend §8.5) |

### 3.4. Backend

| Phải đạt | Nghiệm thu |
|---|---|
| Auth: đăng ký, đăng nhập, JWT, danh sách tài khoản demo | Đăng nhập được cả 4 persona |
| Catalog: `/products`, `/products/{id}`, `/destinations` | Khách ẩn danh nhận `200` (Backend §12 tiêu chí 3) |
| `/recommendations`: User Profile Builder (trọng số, half-life trong config), loại trừ danh mục đã đặt trong chuyến, `because`, popular fallback, cold start < 3 event | Backend §6.2 quy tắc 1, 3; §12 tiêu chí 5, 9 |
| Giỏ hàng tách theo người dùng | Backend §12 tiêu chí 10 |
| Checkout giả lập: mã tham chiếu, đọc lại đơn, tách `eventGroupId` theo điểm đến, `409 PRODUCT_UNAVAILABLE` | Backend §12 tiêu chí 11, 12, 14 |
| `purchase` ghi đồng bộ trước commit, bù trừ khi commit lỗi; event duyệt web ghi nền | CDP §12 tiêu chí 3–8 |
| Vòng lặp K1 | Backend §12 tiêu chí 13; CDP §12 tiêu chí 10 |
| Suy giảm êm: tắt CDP clone thì search/giỏ/xem vẫn chạy, recommendation về `popular` | CDP §12 tiêu chí 6 |
| Contract test trên cùng `openapi.yaml` | Backend §12 tiêu chí 16 |

Với P3, v01 chấp nhận `strategy` là `recent_activity` hoặc `popular` vì dormant nằm ngoài phạm vi. Vì vậy Backend §12 tiêu chí 4 (bốn strategy khác nhau) chỉ bắt buộc ở mức: **P1 và P4 khác strategy, và Home của 4 persona khác nhau về nội dung**.

### 3.5. Web

| Phải đạt | Nghiệm thu |
|---|---|
| Type sinh từ OpenAPI, không khai báo lại payload, mọi HTTP qua `services` | Frontend §13 tiêu chí 1, 3, 4 |
| Màn hình: Home (ẩn danh + cá nhân hóa), Search, Product detail, Cart, Checkout, Confirmation, Login/Register | Chạy được trên cả mock và backend thật |
| Đổi mock → backend thật không sửa `services` | Frontend §13 tiêu chí 8 |
| `ProductCard` + `BecauseLine` dùng chung; `popular` hiện "Phổ biến tại…", không giả cá nhân hóa | `docs/product.md` §1.4, §5 |
| Giá null hiện "Chưa có giá", `priceUnit` thiếu không tự thêm đơn vị | `mvp-minimal-fields-1.2.0.md` mục Recommendation → Web |
| Bộ chọn tài khoản demo; đổi tài khoản xóa giỏ và gợi ý của người trước | Frontend §13 tiêu chí 10 |
| Khoảnh khắc K1: Confirmation có gợi ý mới, Home báo đã cập nhật | `docs/product.md` §4.1.4 |
| Trạng thái rỗng/đang tải/lỗi tối thiểu, không trang trắng | `docs/product.md` §1.4 nguyên tắc 4 |

### 3.6. Evaluation

| Phải đạt | Nghiệm thu |
|---|---|
| Metrics Recall@K, NDCG@K, cross-category rate, catalog coverage kèm unit test | Test chạy xanh |
| Harness: giấu lần đặt gần nhất của mỗi khách, dự đoán từ dữ liệu trước đó | Script tái chạy được bằng một lệnh |
| 3 baseline: random, most-popular, most-popular-in-destination | Có số trong báo cáo |
| Báo cáo đầu tiên trong `src/evaluation/reports/` | Ghi commit đã đo và lưu ý "lịch sử là dữ liệu sinh" (handbook §12) |
| So sánh embedding model trên ~80 cặp truy vấn tiếng Việt | Bảng khuyến nghị cho Search |

Vượt baseline **chưa** là điều kiện của v01, nhưng báo cáo phải nêu rõ model đang đứng ở đâu so với most-popular-in-destination.

### 3.7. Integration / Contract

| Phải đạt | Nghiệm thu |
|---|---|
| OpenAPI và fixture hợp lệ | `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` pass |
| Mọi thay đổi giao diện sửa OpenAPI trước, có reviewer Web + Backend | Theo `architecture-repo.md` §11 |
| Chạy kịch bản §1 end-to-end trước hạn chót | Biên bản chạy: commit, tài khoản, kết quả từng bước |

### 3.8. Agent

Không có mục tiêu bắt buộc trong v01. Team Agent được tiếp tục làm trên mock và contract hiện có, nhưng không được đổi `SearchRequest`, `ProductSummary`, `ItineraryResponse` mà không qua quy trình contract.

## 4. Mốc kiểm tra đề xuất

| Ngày | Mốc |
|---|---|
| Thứ Sáu 18/09 | Mỗi team demo phần của mình độc lập (service thật hoặc mock). Catalog, vector và seed persona đã có trong DB. Chốt embedding model |
| Thứ Hai 21/09 | Nối toàn luồng, chạy kịch bản §1 trên service thật, Evaluation có báo cáo đầu tiên |

## 5. Quy tắc chung

- Grounding: mọi `productId`, tên, giá đến từ catalog/search/recommendation; không dữ liệu sản phẩm do LLM hoặc code tự tạo.
- Không bịa lý do: không có lịch sử thì `because: []`.
- Không commit hoặc log secret, API key, JWT, service token.
- Mọi thay đổi trong `src/` hoặc `docs/` có entry `history/`.

## 6. Quy tắc tạm cho phần chờ xác nhận

Theo `docs/spec/contract-baseline-v1.1.md`; không coi việc chờ phản hồi là đã chọn phương án.

| Chủ đề | Quy tắc tạm trong v01 | Hệ quả |
|---|---|---|
| Kiểm tra giá/tồn kho khi checkout | Dùng snapshot trong catalog | Không cam kết còn chỗ thật |
| Đơn vị giá, thành phần combo | `priceUnit` thiếu là UNKNOWN; tổng thiếu cơ sở là `null` | Không nghiệm thu dự toán đầy đủ |
| Nơi lưu `products`, `users`, `bookings`, `product_vectors` | PostgreSQL của Backend | Seed phải khớp với CDP clone |
| Bề mặt API CDP thật | 5 endpoint của CDP clone | Có thể đổi khi có tài liệu V-OTA |
