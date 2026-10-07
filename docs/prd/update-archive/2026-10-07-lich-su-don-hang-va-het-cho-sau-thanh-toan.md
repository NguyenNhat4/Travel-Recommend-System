# Trang "Đơn hàng của tôi" (lịch sử đơn, chi tiết đơn) và xử lý đơn đã trả tiền nhưng hết chỗ

- Ngày: 2026-10-07
- Người đề xuất: mihhquan / Claude
- Trạng thái: đã áp dụng (trừ FR-BKG-16 và AC-BKG-20: hoãn, không đưa vào PRD đợt này)
- Chốt bởi / ngày: mihhquan, 2026-10-07
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.5, §1.6 (FR-USR-02) và §3; `docs/prd/user-flow.md` §2 và §4; `docs/prd/api-contract.md` §2.6; `docs/prd/project-brief.md` §4.2 (chỉ đối chiếu, không sửa)
- Mã FR/NFR: mới — đề nghị cấp **FR-BKG-14** (danh sách đơn), **FR-BKG-15** (chi tiết đơn), **FR-BKG-16** (đã thu tiền nhưng hết chỗ) và **AC-BKG-18..20**; liên quan FR-USR-02, FR-BKG-03, FR-BKG-06, FR-BKG-07, FR-BKG-12

## Lý do

1. **Chưa có cách xem lại đơn đã đặt.** Contract chỉ có `POST /bookings`, `GET /bookings/{referenceCode}` và huỷ. Route `/profile` ("Hồ sơ & Lịch sử") đã có trong `user-flow.md` §2 nhưng chưa dựng, và FR-USR-02 chỉ ghi chung "lịch sử đơn hàng", không nói hiển thị, lọc hay phân trang ra sao. Ô "Đặt chỗ của tôi" ở header hiện lấy từ bộ nhớ của trình duyệt nên mất khi tải lại trang.
2. **Trang chi tiết đơn hiện chỉ phục vụ lúc vừa thanh toán xong** (FR-BKG-04). Khách muốn xem lại đầy đủ: cơ sở lưu trú, phòng, hành khách, chính sách huỷ, thông tin thanh toán.
3. **Đơn đã thu tiền nhưng hết chỗ chưa có quy tắc.** FR-BKG-02 chỉ kiểm tra chỗ trống trước khi tạo đơn. Từ lúc tạo đơn đến lúc Stripe báo thu tiền có thể vài phút; nếu trong lúc đó chuyến bay hoặc phòng không còn bán, hệ thống hiện vẫn xác nhận đơn và ghi event `purchase`. Khách trả tiền cho thứ không còn.

Giao diện đã được người dùng chốt trên bản mẫu: https://claude.ai/artifact/ATHDHksuHw5ddMFS5ADqX9 (chốt 2026-10-07).

## Nội dung đề xuất

### 1. `requirements.md` §1.5 — thêm FR-BKG-14 (danh sách đơn)

Hiện tại: mục kết thúc ở FR-BKG-13.

Thêm sau FR-BKG-13:

> - **FR-BKG-14 (Đơn hàng của tôi):** Người đã đăng nhập xem mọi đơn của mình ở `/profile`, mới nhất trước. Chỉ thấy đơn của chính mình.
>   - **Ba tab:** *Sắp đến* gồm đơn `CONFIRMED` có ngày kết thúc dịch vụ (ngày trả phòng, ngày sử dụng cuối cùng) từ hôm nay trở đi và đơn `PENDING_PAYMENT` còn hạn giữ chỗ. *Hoàn thành* gồm đơn `CONFIRMED` mà mọi dịch vụ đã qua ngày kết thúc. *Đã huỷ* gồm `CANCELLED`, `EXPIRED`, `PAYMENT_FAILED` và đơn `PENDING_PAYMENT` đã quá hạn giữ chỗ. Ngày tính theo giờ Việt Nam. Mỗi thẻ đơn có nhãn nói rõ lý do (ví dụ "Hết vé · đã hoàn tiền", "Hết hạn giữ chỗ").
>   - **Lọc:** theo loại dịch vụ (Tất cả, Khách sạn, Vé máy bay, Vé tham quan, Combo, Sân Golf; đơn có ít nhất một dịch vụ thuộc loại đó) và theo ngày đặt (Tất cả, 1, 7, 30, 60 ngày gần nhất). Bộ lọc áp dụng chung cho cả ba tab, nằm trên địa chỉ trang để tải lại hoặc chia sẻ vẫn giữ nguyên.
>   - **Phân trang** đánh số, 5 đơn mỗi trang; đổi tab hoặc bộ lọc thì về trang 1; chỉ một trang thì ẩn thanh phân trang.
>   - **Trạng thái trống:** chưa từng đặt thì mời khám phá; có đơn nhưng bộ lọc không khớp thì có nút xoá bộ lọc. Có trạng thái đang tải và lỗi (nút thử lại, kèm mã yêu cầu).
>   - Thẻ đơn có nút theo trạng thái: Thanh toán ngay, Huỷ giữ chỗ, Huỷ đơn, Đặt lại (theo FR-BKG-05), Tìm chuyến bay khác (đơn hết vé), Xem chi tiết.

### 2. `requirements.md` §1.5 — thêm FR-BKG-15 (chi tiết đơn)

Thêm sau FR-BKG-14:

> - **FR-BKG-15 (Chi tiết đơn hàng):** Trang `/booking/:referenceCode` hiển thị đủ thông tin của đơn ở mọi trạng thái, hai cột trên máy tính, một cột trên điện thoại. Cột trái: dòng trạng thái và lý do; mỗi dịch vụ một khối "Thông tin đặt chỗ" (khách sạn: nhận phòng, trả phòng, tên, hạng sao, địa chỉ, bản đồ, phòng đã chọn, tiện ích, yêu cầu riêng; vé máy bay: điểm đi, điểm đến, hạng vé, hành lý, chỗ ngồi, trạng thái xuất vé và mã đặt chỗ mô phỏng theo FR-BKG-12; vé tham quan, sân golf, combo: tên, địa chỉ, loại vé hoặc thành phần); thông tin khách hàng; thông tin khách lưu trú hoặc hành khách; thông tin dịch vụ (địa chỉ, liên hệ hỗ trợ, chính sách); chính sách hoàn huỷ. Cột phải: mã đơn có nút sao chép, từng dòng giá, tổng thanh toán, trạng thái và phương thức thanh toán, nút hành động. Chính sách hoàn huỷ lấy đúng hạn của FR-BKG-07 (hoàn 100% trước 00:00 ngày liền trước ngày sử dụng sớm nhất; sau đó không huỷ trực tuyến; huỷ cả đơn, không huỷ riêng từng dịch vụ). Không hiển thị mức "tính phí khi huỷ muộn" vì hệ thống không có mức đó.
>   - **Giá trị mặc định chung** (không lấy từ dữ liệu từng khách sạn): nhận phòng sau 14:00, trả phòng trước 12:00. Liên hệ hỗ trợ là một số tổng đài cố định lấy từ cấu hình. Không hiển thị diện tích phòng. Tiện ích khách sạn chỉ hiện các mục thuộc bộ khoá cố định mà API trả về (`docs/spec/data-collection/schema.md`).
>   - Giữ nguyên các hành vi sẵn có của trang: đếm ngược giữ chỗ, kiểm tra lại thanh toán, huỷ đơn, Đặt lại.

### 3. `requirements.md` §1.5 — FR-BKG-16 (đã thu tiền nhưng hết chỗ) — HOÃN

**Quyết định khi chốt (2026-10-07): bước kiểm tra này để lại làm sau, không đưa vào PRD và không code đợt này.** Nội dung dưới đây giữ lại làm tham chiếu cho lần sau; AC-BKG-20 cũng hoãn theo.

Nội dung đề xuất (chưa áp dụng):

> - **FR-BKG-16 (Đã thu tiền nhưng hết chỗ):** Khi Stripe xác nhận đã thu tiền và trước khi chuyển đơn `CONFIRMED`, hệ thống kiểm tra lại từng dịch vụ của đơn trong catalog. Có dịch vụ không còn bán (`available` sai hoặc không đặt được) thì: không ghi event `purchase` sang CDP; đơn chuyển `PAYMENT_FAILED` với lý do `INVENTORY_UNAVAILABLE`; hoàn 100% toàn bộ số đã thu qua Stripe (cùng cơ chế hoàn tiền, khoá chống hoàn trùng và job đối soát như FR-BKG-07). Đơn không bị xác nhận một phần. Kiểm tra chỉ về chỗ còn bán, không so lại giá (giá đã chốt lúc tạo đơn theo FR-BKG-02). Khách thấy lý do và tiến trình hoàn tiền (đã thu tiền → hết chỗ → đang hoàn → đã hoàn) ở `/profile` và `/booking/:referenceCode`, kèm nút tìm lựa chọn khác. Hệ thống chưa gửi email, nên hai trang này là nơi khách biết kết quả. Webhook gửi trùng hoặc job đối soát chạy lại không được hoàn tiền hai lần.
>   - **Giới hạn:** "hết chỗ" dựa trên bản chụp catalog (`available`, `is_bookable`), không phải tồn ghế thời gian thực, đúng giới hạn ở `project-brief.md` §4.2. Hệ thống vẫn có thể bán một chuyến mà hãng thật đã hết; điều đề xuất này bảo đảm chỉ là: nếu catalog đã đánh dấu hết chỗ thì khách không bị giữ tiền.

### 4. `requirements.md` §1.6 — FR-USR-02

Hiện tại: "…danh sách yêu thích, lịch sử đơn hàng và các tiêu chí ưu tiên du lịch…".
Thay bằng: "…danh sách yêu thích, lịch sử đơn hàng (theo FR-BKG-14) và các tiêu chí ưu tiên du lịch…".

### 5. `requirements.md` §3 — thêm AC-BKG-18..19 (AC-BKG-20 hoãn cùng FR-BKG-16)

Thêm sau AC-BKG-17:

> | **AC-BKG-18** | Khách có 12 đơn `CONFIRMED` đã qua ngày đi, 3 đơn `CONFIRMED` chưa đi, 1 đơn `PENDING_PAYMENT` còn hạn, 4 đơn huỷ, hết hạn hoặc thất bại; mở `/profile` | Mở vào tab Sắp đến thấy 4 đơn. Tab Hoàn thành thấy 12 đơn chia 3 trang, 5 đơn mỗi trang. Tab Đã huỷ thấy 4 đơn, mỗi đơn có nhãn lý do. Chọn "Vé máy bay" và "7 ngày" thì chỉ còn đơn có vé máy bay đặt trong 7 ngày gần nhất, về trang 1, địa chỉ trang chứa bộ lọc. Gọi API bằng tài khoản khác không thấy đơn nào của khách này. |
> | **AC-BKG-19** | Khách chưa có đơn nào; hoặc có đơn nhưng bộ lọc không khớp; hoặc mất mạng khi tải | Chưa có đơn: lời nhắn thân thiện và nút khám phá. Bộ lọc không khớp: nút "Xoá bộ lọc". Mất mạng: thông báo lỗi, nút "Thử lại" và mã yêu cầu; không để màn trắng. |
> | **AC-BKG-20** | Khách thanh toán Stripe thành công cho một đơn có vé máy bay, nhưng ngay trước khi Backend xử lý webhook, chuyến đó bị đánh dấu hết chỗ trong catalog | Đơn `PAYMENT_FAILED` với lý do `INVENTORY_UNAVAILABLE`, không có event `purchase` trong `cdp.events`, Stripe có đúng một lệnh hoàn toàn bộ số tiền. Gửi lại webhook hoặc chạy lại job đối soát không tạo lệnh hoàn thứ hai. `/profile` hiện đơn ở tab Đã huỷ với nhãn "Hết vé" và tiến trình hoàn tiền; trang chi tiết nêu lý do và có nút tìm chuyến khác. Đơn có vé máy bay vẫn còn bán thì xác nhận bình thường. |

### 6. `user-flow.md` §2 — bảng route

Dòng `/profile` hiện tại: "Hồ sơ & Lịch sử — Quản lý thông tin cá nhân, lịch sử đơn hàng và chuyến đi — User Preferences, Booking History, Saved Items".
Thay bằng: "Đơn hàng của tôi (Hồ sơ & Lịch sử) — Xem lại đơn theo ba tab Sắp đến, Hoàn thành, Đã huỷ; lọc theo dịch vụ và ngày đặt; phân trang (FR-BKG-14) — Tab trạng thái, Service Chips, Date Filter, Booking Cards, Pagination, Empty State". Các phần hồ sơ cá nhân và sở thích để việc khác, không thuộc đề xuất này.

Dòng `/booking/:referenceCode`: thêm vào "Mục đích": "xem lại đầy đủ đơn ở mọi trạng thái (FR-BKG-15)"; thêm vào "Thành phần": "Booking Detail Blocks, Cancellation Policy, Payment Panel".

### 7. `user-flow.md` §4 — wireframe

Thêm wireframe ASCII cho `/profile` và cập nhật §4.3 theo bản mẫu đã chốt. Nội dung wireframe lấy từ bản mẫu; viết khi áp dụng.

### 8. `api-contract.md` §2.6 — quản lý đơn hàng

Thêm sau "Xem chi tiết đơn hàng":

> - **Danh sách đơn của tôi:** `GET /api/v1/bookings?tab=upcoming|done|cancelled&taxonomy=&days=1|7|30|60&page=&pageSize=` — trả `{data[], pagination}`; mỗi phần tử là bản tóm tắt nhẹ của đơn. Ví dụ chỉ minh hoạ, nguồn sự thật là `openapi.yaml`.

(Các ví dụ ở §2.6 hiện dùng `bookingCode`, lệch với contract dùng `referenceCode`; không sửa trong đề xuất này.)

## Thay đổi source sau khi chốt

Theo thứ tự: PRD trước, contract, rồi backend và frontend.

- **Contract:** `src/shared/contracts/paths/booking.yaml`, `schemas/booking.yaml`, `openapi.yaml` (tăng phiên bản minor, chỉ thêm): `GET /bookings`, schema tóm tắt đơn, thêm `INVENTORY_UNAVAILABLE` vào `PaymentFailureReason`. Mock `src/shared/mocks/booking/listBookings.*` và `index.json`. Chạy `validate_contract.py`.
- **Backend:** `application/ports/booking_store.py`, `infrastructure/persistence/postgres_booking.py` (truy vấn danh sách, nạp dịch vụ theo lô), `application/booking/queries.py`, `api/v1/routes/booking.py`; kiểm tra chỗ trong `application/booking/payment_events.py` trước `confirm_paid`; `views.py` nhận lý do mới. Không đổi DDL (`last_failure_code` là text); xác nhận lại với `db/verify.sql`.
- **Frontend:** `src/app/(storefront)/profile/`, `features/bookings/`, dựng lại `components/confirmation/ConfirmationView.tsx` theo FR-BKG-15, `Header.tsx` trỏ về `/profile`, `services/booking.ts`, `types/api.gen.ts` (tái sinh).
- **Spec:** `docs/spec/hop-dong-tich-hop-frontend.md` §3 (thêm `/profile`), `docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md` §5, §6.3, §10.2 (nhánh hết chỗ), `src/frontend/README.md`.
- **Test:** đơn vị và hợp đồng cho danh sách (lọc, phân trang, cách ly người dùng), xử lý hết chỗ (không event `purchase`, hoàn một lần, webhook gửi trùng), vitest cho trang, Playwright thêm `/profile`.

## Điểm còn mở cần người chốt

- **Số tổng đài** hiển thị ở "Liên hệ hỗ trợ": đã chốt là số giả lập lấy từ cấu hình (1900 0000), thay bằng số thật khi có.
- **Bước kiểm tra hết chỗ sau thanh toán:** đã chốt để lại làm sau (FR-BKG-16, AC-BKG-20, lý do `INVENTORY_UNAVAILABLE` không làm đợt này).
- **Email báo hoàn tiền** nằm ngoài đề xuất này (`so-do-luong-dat-cho-thanh-toan.md` §1 loại trừ email).
