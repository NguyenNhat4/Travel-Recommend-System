# Đề xuất PRD và kế hoạch: khách sạn và vé máy bay đặt trực tiếp, không vào giỏ hàng

- Ngày: 2026-10-01
- Tác giả: mihhquan / Claude Code
- Nhánh: feat/booking
- Trạng thái: hoàn thành — đề xuất đã được chốt; việc áp dụng và triển khai ghi ở `history/2026-10-01-ap-dung-khach-san-ve-may-bay-dat-truc-tiep.md`
- Phạm vi: docs

## Mục tiêu

Người dùng đổi chiến lược giỏ hàng: khách sạn và vé máy bay trên OTA không nên gom vào giỏ như thương mại điện tử, vì chỗ trống và giá đổi liên tục. Yêu cầu viết kế hoạch thay đổi. Thay đổi này lệch PRD (FR-BKG-01 cho giỏ chứa cả khách sạn và vé máy bay), nên phải có đề xuất và được chốt trước khi sửa source (`AGENTS.md` §8).

## File thay đổi

- `docs/prd/update/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` (sau khi chốt đã chuyển sang `docs/prd/update-archive/`) — thêm: đề xuất giỏ hàng từ chối khách sạn và vé máy bay, "Đặt ngay" tạo đơn nháp ngắn hạn; bảng quyết định Q1–Q14 và các câu phụ, người dùng trả lời dần trong ngày; trích đoạn PRD cần sửa ở `requirements.md`, `user-flow.md`, `data-model.md`, `deployment-plan.md`, `test-plan.md`.
- `docs/plan/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md` — thêm: kế hoạch tám bước (spec, contract, DDL, Backend, Frontend, chạy thử, tài liệu, nghiệm thu), thiết kế API và bảng, kịch bản nghiệm thu, rủi ro, và bảng "nếu chốt khác đề xuất".

Ngoài repo: mock giao diện trên canvas https://claude.ai/artifact/WLaybxVEYFE6fSLpSWpy6q (riêng tư), dựng theo yêu cầu của người dùng để hình dung kết quả và chọn phương án cho các câu còn chờ (cập nhật theo các đợt trả lời: 10 màn đã chốt); không có file nào trong repo.

## Quyết định

- **Q1 do người dùng trả lời (2026-10-01):** tour và trải nghiệm (`attraction`, `golf`) và tiện ích khác (`combo`) vẫn có giỏ hàng; chỉ khách sạn và vé máy bay đặt trực tiếp. Bản nháp đầu của agent đề xuất bỏ giỏ cho mọi loại và gỡ `/cart*`; đã viết lại cả đề xuất lẫn kế hoạch theo câu trả lời, đổi tên ba file cho khớp phạm vi (các file chưa commit).
- **Hệ quả của Q1:** contract chỉ thêm, không gỡ gì (câu hỏi Q6 không còn); trang `/cart`, header, thanh tab giữ nguyên; checkout có hai nguồn (giỏ hoặc đơn nháp). Phát sinh hai câu hỏi mới: Q9 (nút Đặt ngay ở tour, tiện ích tạo đơn nháp riêng hay thanh toán cả giỏ) và Q10 (xoá mục khách sạn, vé máy bay đang nằm trong giỏ).
- **Q9 do người dùng trả lời (2026-10-01):** "Tất cả đều có nút đặt ngay và nó vào phần thanh toán, nhưng khi thoát ra chỉ có các vé tour và tiện ích thì sẽ nằm lại trong giỏ hàng." Người dùng làm rõ thêm: ý nói giai đoạn khách không hoàn thành thanh toán, nên luật áp dụng cho cả rời trang thanh toán, rời trang Stripe, `PAYMENT_FAILED`, `EXPIRED` và huỷ đơn chưa trả tiền. Agent hiện thực bằng cách chép mục `attraction`, `golf`, `combo` của đơn nháp vào giỏ ngay lúc tạo đơn nháp (nếu giỏ chưa có mục cùng sản phẩm và ngày), vì Web không bắt được mọi kiểu rời trang; thanh toán xong thì `clear_cart_items` sẵn có gỡ mục đó. Thêm AC-BKG-16.
- **Người dùng xác nhận lại luật nút (2026-10-01):** nút Thêm vào giỏ chỉ có ở tour và tiện ích; khách sạn và vé máy bay bỏ nút đó, chỉ còn Đặt ngay. Kế hoạch thêm bảng rà năm chỗ đang có nút Thêm vào giỏ ở Web (`ProductDetailView`, `FlightResultsView`, `ItineraryMap` + `WidgetPlanPanel`, `AssistantResultPanel`, khối gợi ý của `CartView`); AC-BKG-15 mở rộng cho mọi nơi hiển thị.
- **Thẻ và ghim bản đồ của trợ lý, khối gợi ý ở trang giỏ chuyển thành câu hỏi (Q11–Q14):** agent đã tự ghi cách xử lý hai chỗ này; người dùng yêu cầu chốt lại bằng câu hỏi và trả lời dần. Hai dòng tương ứng trong bảng rà nút của kế hoạch được đánh dấu "chờ", AC-BKG-15 thu về hai trang đã chốt (chi tiết khách sạn, kết quả vé máy bay).
- **Người dùng trả lời dần từng câu; chỉ bắt đầu triển khai khi mọi câu đã có trả lời.**
- **Q2, Q3, Q4 do người dùng trả lời (2026-10-01):** Q2: khách tự đặt từng mục trên lịch trình và có một nút thanh toán tất cả. Q3: đơn nháp giữ 30 phút; thông tin được giữ với phần có giỏ, câu trả lời về khách sạn và vé máy bay dừng giữa chừng. Q4: đã đăng nhập thì lưu database, chưa đăng nhập thì lưu Redis với TTL 3–7 ngày.
- **Cách agent hiện thực ba câu trả lời:** nút "Thanh toán tất cả" tạo một đơn nháp cho cả lịch trình; TTL đơn nháp 30 phút, bỏ luồng "Cập nhật giá", khách sạn và vé máy bay hết hạn là đặt lại từ đầu (tách Q3b để xác nhận phần câu bị dừng); khách chưa đăng nhập dùng được giỏ và Đặt ngay, lưu Redis theo `anon_id` của phiên khách (`hop-dong-tich-hop-auth.md` §3.7), gộp sang tài khoản khi đăng nhập, thanh toán vẫn cần đăng nhập.
- **Q4 mở rộng phạm vi** (hiện phải đăng nhập mới thêm giỏ được): thêm FR-USR-03 vào PRD bị ảnh hưởng, AC-BKG-17, và bốn câu hỏi Q4a–Q4d (đăng nhập ở bước nào, TTL áp cho giỏ hay đơn nháp và mấy ngày, luật gộp, sự kiện `add_to_cart` của khách). "TTL 3–7 ngày" mâu thuẫn với 30 phút của Q3 nếu áp cho đơn nháp, nên kế hoạch tạm áp cho giỏ khách.
- **Đợt trả lời thứ ba (2026-10-01, sau khi xem mock):** Q3b, Q4a, Q7 chốt theo đề xuất; Q11 (b) Đặt ngay trên thẻ khách sạn của trợ lý; Q12 (b) thẻ tour có cả Thêm vào giỏ và Đặt ngay; Q13/Q14 bỏ khối "Thường được đặt cùng chuyến" ở trang giỏ (khối này chỉ có ở spec, không có trong PRD); Q4b 3 ngày; Q4c trùng thì chỉ giữ một, mục khác thì lưu vào giỏ trong database, xoá cache Redis; Q10 người dùng coi là không phải câu hỏi (hai loại này theo luật không vào giỏ), nên migration dọn mục cũ được giữ.
- **Đổi cách gọi theo người dùng:** `/checkout` là "trang thanh toán" (đặt chỗ là một bước trong đó), thay cho "trang đặt chỗ" ở các bản trước. Q9b vẫn chờ vì người dùng mới chỉnh cách gọi, chưa chọn (a) hay (b).
- **Dung hoà Q4b với Q3/Q3b:** Redis giữ dữ liệu của khách chưa đăng nhập 3 ngày (`GUEST_BOOKING_TTL_DAYS`), nhưng đơn nháp vẫn chỉ thanh toán được trong 30 phút; bản ghi còn lại sau 30 phút chỉ phục vụ màn hình hết hạn. Lý do: Q3b vừa được chốt trong cùng lượt là hết 30 phút thì khách sạn, vé máy bay không giữ gì.
- **Q11 (b) sinh câu hỏi Q11c:** lịch trình có thể gợi ý khách sạn ở cấp cơ sở lưu trú, chưa có hạng phòng (không đặt được); code agent hiện không chọn hạng phòng (`src/backend/app/application/itinerary`, `agents` không có xử lý phòng con).
- **Đợt trả lời thứ tư (2026-10-01):** người dùng xác nhận cách hiểu Q4b (3 ngày là thời gian Redis giữ dữ liệu của khách vãng lai, đơn nháp vẫn 30 phút) và Q4c (trùng thì giữ mục của tài khoản); chốt Q9b: Đặt ngay chỉ thanh toán sản phẩm đó, không liên quan tới giỏ, giỏ chỉ thanh toán từ màn hình giỏ. Mock cập nhật: bảng Q9b thành màn đã chốt số 10.
- **Đợt trả lời cuối (2026-10-01):** Q5 có ghi `add_to_cart` khi bấm Đặt ngay; Q4d có ghi lúc chuyển giỏ khách sang tài khoản, mục trùng không ghi; Q8 không làm danh sách lưu xem sau; Q11c để lại ghi chú vì phần lịch trình trả hạng phòng do team trợ lý đang xây. Không còn câu nào chờ, đề xuất chuyển sang đã chốt.
- **Q9b tách ra để xác nhận:** câu trả lời Q9 chưa nói trang thanh toán mở từ Đặt ngay của một vé tham quan có kèm các mục khác trong giỏ hay không. Kế hoạch đang theo hướng chỉ hiện lần đặt đó.
- **Gọi là "đơn nháp" (`booking draft`)**, không gọi "phiên đặt chỗ", để không nhầm với phiên Stripe Checkout và đơn giữ chỗ `PENDING_PAYMENT`.
- **Mục của đơn nháp dùng lại schema `CartItem`** (`cartItemId` là mã mục chung), để `CheckoutItemDetail`, `ValidationFieldError` và bộ luật checkout không phải đổi.
- **Nhóm sản phẩm lấy theo header hiện có** (`src/frontend/src/services/search.ts`, `navConfig.ts`): Tour và trải nghiệm = `attraction`, `golf`; Tiện ích khác = `combo`.
- **Combo có thành phần lưu trú vẫn vào giỏ** theo Q1; đề xuất ghi chú điểm này để người chốt thấy.

## Kiểm tra

- Chỉ thêm tài liệu, không đổi code, contract, DDL; không chạy `validate_contract.py`, `db/verify.sql` hay test.
- Đã đối chiếu trích đoạn PRD trong đề xuất với `requirements.md` §1.4, §1.5, §1.7, §3; `user-flow.md` §1.2, §2, §3.2, §3.3, §4.2; `data-model.md` §2.2, §4.2; `deployment-plan.md` §2, §5; `test-plan.md` §3.
- Đã đối chiếu đường dẫn trong kế hoạch với code nhánh `feat/booking`: `paths/booking.yaml`, `schemas/booking.yaml`, `schemas/common.yaml`, `application/booking/{cart,create_hold,settlement}.py`, `ports/{cart_repository,booking_store}.py`, `db/vota_schema.sql`, `db/verify.sql`, `services/booking.ts`, `services/search.ts`, `TravelContext.tsx`, `useCheckout.ts`, `useAssistantCart.ts`, `ProductDetailView.tsx`, `FlightResultsView.tsx`, `AssistantResultPanel.tsx`, `ConfirmationView.tsx`.

## Còn lại / rủi ro

- Không còn câu hỏi nào chờ. Việc còn lại là triển khai theo kế hoạch (bước 1–8).
- Chưa đọc đầy đủ `docs/spec/product.md` §4.4, §6.7, `docs/spec/hop-dong-tich-hop-frontend.md` §4.4–§4.8 và `docs/spec/hop-dong-tich-hop-auth.md` (mới dò mục có nhắc giỏ và phiên khách). Cách BFF chuyển mã phiên khách cho Backend chưa được kiểm trên code. Phải đọc hết ở bước 1 theo `AGENTS.md` §1.2.
- `POST /cart/items` từ chối khách sạn và vé máy bay là đổi hành vi của một endpoint v1; không đổi schema, đã ghi trong đề xuất (AC-BKG-15).
- Hai đề xuất khác trong `docs/prd/update/` vẫn chờ chốt (`2026-09-25-goi-y-ngay-hom-nay…`, `2026-09-29-vong-react-co-chan…`); cả hai thuộc trợ lý, không chạm phần đặt chỗ.
