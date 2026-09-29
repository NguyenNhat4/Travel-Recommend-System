# Kế hoạch: Checkout nhiều bước, đoàn khách người lớn/trẻ em và giá theo loại khách

- Ngày: 2026-09-29
- Phục vụ: FR-BKG-01, FR-BKG-02, FR-BKG-06, FR-BKG-08, FR-CAT-02, FR-CAT-03, NFR-SEC-01, NFR-MAINT-02 (`docs/prd/requirements.md`); AC-BKG-05, AC-BKG-06, AC-BKG-07; giữ nguyên AC-BKG-01…04.
- Đề xuất PRD: `docs/prd/update-archive/2026-09-29-checkout-nhieu-buoc-hanh-khach.md` — **đã chốt và đã áp dụng vào PRD (2026-09-29, Q1–Q10 theo cột Đề xuất)**.
- Spec: `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md`
- Người làm: mihhquan / Claude Code, nhánh `feat/booking`
- Lịch sử: `history/2026-09-29-trien-khai-checkout-nhieu-buoc-hanh-khach.md`

## Phạm vi lần này

**Trong phạm vi:** toàn bộ spec §1–§9 và các mục §10–§16 được viết bổ sung. Gồm contract 1.8.0, DDL và migration 0005, Backend (domain, application, adapter Postgres, DTO, route), Web (checkout ba bước, trang giỏ, hộp đặt ở trang chi tiết, thêm giỏ từ trợ lý, trang đơn), mock, bộ test dùng chung Web và Backend.

**Ngoài phạm vi (ghi rõ để người nghiệm thu không tìm nhầm):**

- Phụ lục A của spec (hành lý ký gửi, chọn ghế, FR-BKG-11): catalog chưa có `baggageOptions`, `seatPricing`, `aircraft`; theo R-EXT-01 phần này bị ẩn hoàn toàn.
- FR-BKG-10 (hạng vé, khứ hồi, AC-BKG-09) và FR-BKG-12 (xuất vé mô phỏng): hai yêu cầu vé máy bay khác đã vào PRD, phụ thuộc dữ liệu catalog chưa có. Đề xuất thông tin hành khách bay (danh xưng, quốc tịch, giấy tờ) chưa vào PRD, không có mã FR-BKG-09.
- Sổ hành khách lưu trong hồ sơ, bảo hiểm, suất ăn, mã giảm giá (spec §3.3).

## Tiến độ

Cập nhật lần cuối 2026-09-29, sau khi triển khai xong. Kết quả chạy kiểm thử ghi ở `history/2026-09-29-trien-khai-checkout-nhieu-buoc-hanh-khach.md`.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | Đọc tài liệu, xác nhận theo `AGENTS.md` §1.3 | Xong |
| 1 | Bộ ca kiểm thử dùng chung (`src/shared/contracts/tests/booking-rules-cases.json`, 90 ca) | Xong |
| 2 | Contract 1.8.0, mock, `api.gen.ts`, `validate_contract.py` | Xong |
| 3 | DDL (`vota_schema.sql`, `init/01_vota.sql`), migration 0005, `verify.sql`, seed `line_total` | Xong |
| 4 | Backend domain: `party`, `fares`, `party_rules`, `pricing`, `models` | Xong |
| 5 | Backend application: `cart`, `create_hold`, `views`, `errors`, `messages`; port giỏ | Xong |
| 6 | Backend adapter Postgres, DTO, route, thông điệp lỗi | Xong |
| 7 | Test Backend: unit, contract, integration Postgres | Xong |
| 8 | Web: `checkoutRules`, checkout ba bước, tóm tắt đơn, hộp lỗi | Xong |
| 9 | Web: trang giỏ, hộp đặt ở trang chi tiết, trợ lý thêm theo `intent.party`, trang đơn | Xong |
| 10 | Test Web (vitest); chạy thử toàn luồng trên trình duyệt thật với Backend thật (`PAYMENT_PROVIDER=fake`) và Postgres đã migrate | Xong (chạy tay bằng script Playwright, không nằm trong repo) |
| 11 | Tài liệu: hoàn thiện spec §10–§16, sửa spec liên quan, README | Xong. **Chưa làm:** dọn `docs/prd/user-flow.md` bị lặp §4.2–§4.4 (thuộc PRD, cần đề xuất riêng; spec §15.3) |
| 12 | Entry `history/`, báo cáo nghiệm thu | Xong |
| 13 | Nghiệm thu cuối của người dùng (spec §12.4) | Chờ |

## Thứ tự và ràng buộc

1. Contract trước code (`AGENTS.md` §3): mọi trường mới đều tuỳ chọn; không đổi nghĩa `quantity`, `lineTotal`, `guestNames`.
2. DDL: sửa `db/vota_schema.sql` và `db/init/01_vota.sql` (hai file giống hệt nhau), thêm migration idempotent, cập nhật `docs/spec/DATABASE_SCHEMA.md`, trong cùng một thay đổi.
3. Domain thuần (không import framework); luật kiểm nằm ở `domain/booking/party_rules.py` và được Web phản chiếu ở `checkoutRules.ts`; cả hai chạy chung một bộ ca JSON.
4. Không gửi họ tên, ngày sinh sang CDP, Insider, Stripe; không ghi log họ tên, ngày sinh, số điện thoại; API không trả ngày sinh.

## Quyết định thiết kế bổ sung (chưa có trong spec nháp)

- **Họ và tên hai ô** (`surname`, `givenNames`), theo Q7 đã chốt; `full_name` do Backend nối.
- **Khoá chính `app.booking_travelers`** là `traveler_id` (theo ERD PRD), kèm `UNIQUE (booking_id, traveler_ref)` và `UNIQUE (booking_id, position)`.
- **Port giỏ** đổi từ "cộng dồn trong SQL" sang ghi giá trị tuyệt đối: use case đọc dòng hiện có, gộp, kiểm R-CRT-01…04 rồi ghi, vì luật sức chứa không biểu diễn được trong SQL.
- **Sai định dạng JSON** (kiểu dữ liệu) vẫn trả `422 VALIDATION_ERROR` như handler chung; DTO không giới hạn khoảng giá trị để mọi vi phạm luật nghiệp vụ đều đi qua bộ luật và về `400` kèm `fields[]`.
- **`line_total` bỏ cột sinh**: các dòng cũ giữ nguyên giá trị (`DROP EXPRESSION`). Ngoại lệ: đơn khách sạn nhiều đêm do Backend tạo trước đây (không phải seed, chưa có dòng giá) được tính lại cho khớp `total_amount`; đơn seed giữ nguyên vì `total_amount` của seed không nhân số đêm.
- **Tên tài khoản không dùng được làm họ tên** (có chữ số, một từ) thì ô họ tên Người lớn 1 để trống thay vì điền sẵn.
- **Hạn hoàn tiền đã qua ngay lúc đặt**: câu chính sách huỷ nói rõ không được hoàn tiền thay vì hứa hoàn 100%.
- **Hàng đợi `PATCH` giỏ** (`patchQueue.ts`): debounce 400 ms, các lần của cùng một mục nối tiếp nhau, so số khách đã gửi thay vì giỏ chưa vẽ lại (spec §10.3).
