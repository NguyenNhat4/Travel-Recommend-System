# Khách sạn và vé máy bay đặt trực tiếp, không vào giỏ hàng

- Ngày: 2026-10-01
- Người đề xuất: mihhquan / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-01 (trả lời từng câu Q1–Q14 và các câu phụ)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4, §1.5, §1.6, §1.7, §3 · `docs/prd/user-flow.md` §1.2, §2, §3.2, §3.3, §4.2 · `docs/prd/data-model.md` §1, §2.2, §4.2 · `docs/prd/deployment-plan.md` §2, §5 · `docs/prd/test-plan.md` §3
- Mã FR/NFR: FR-BKG-01 (viết lại) · FR-BKG-05, FR-BKG-10, FR-BKG-13, FR-AGT-04, FR-CDP-01, FR-USR-03 (sửa câu chữ) · AC-BKG-01, 02, 09, 11 (sửa câu chữ) · AC-BKG-13, AC-BKG-14, AC-BKG-15, AC-BKG-16, AC-BKG-17 (mới — cần cấp mã)

Kế hoạch triển khai sau khi chốt: `docs/plan/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md`.

Mock giao diện (10 màn theo các câu đã trả lời): https://claude.ai/artifact/WLaybxVEYFE6fSLpSWpy6q (riêng tư, người đề xuất cần chia sẻ quyền xem).

## Lý do

Khách sạn và vé máy bay không phải hàng hoá có tồn kho ổn định. Chỗ trống và giá đổi theo thời gian, nên một "giỏ hàng" kiểu thương mại điện tử, nơi khách bỏ sản phẩm vào rồi quay lại sau vài ngày, không phù hợp với hai loại này:

- **Giá trong giỏ cũ dần.** Giỏ lưu `unit_price_snapshot` lúc thêm. Job cào chạy hằng ngày làm giá đổi; khách chỉ biết khi bấm Thanh toán và nhận `409 PRICE_CHANGED`, tức ở bước cuối cùng.
- **Chỗ trống trong giỏ cũ dần.** Cửa sổ đặt chỗ là 30 ngày trượt theo ngày nạp. Phòng hoặc chuyến bay nằm trong giỏ đủ lâu sẽ rơi ra ngoài cửa sổ hoặc hết bán, làm hỏng cả lần thanh toán.
- **Giỏ gom những thứ không cùng một lần đặt.** `POST /bookings` thanh toán **toàn bộ** giỏ. Khách bấm "Đặt ngay" một phòng hôm nay sẽ bị kèm cả những mục đã bỏ giỏ từ tuần trước; nút "Đặt ngay" hiện chỉ là "thêm vào giỏ rồi mở checkout".
- **Giỏ tạo cảm giác đã giữ chỗ.** Hệ thống không trừ tồn kho (FR-BKG-05), nên một phòng nằm trong giỏ không bảo đảm gì.

Các OTA lớn (Booking.com, Traveloka, Trip.com) cho đặt thẳng khách sạn và vé máy bay: chọn → điền thông tin → trả tiền, giá được kiểm lại khi vào trang đặt và chỉ có hiệu lực trong thời gian ngắn. Vé tham quan, tour thì vẫn thường có giỏ (Klook, KKday).

## Tóm tắt thay đổi

| Nhóm trên header | Loại (`taxonomy`) | Cách đặt |
|---|---|---|
| Lưu trú | `hotel` | **Đặt trực tiếp**: chỉ có nút Đặt ngay, không vào giỏ |
| Di chuyển | `flight` | **Đặt trực tiếp**: chỉ có nút Đặt ngay, không vào giỏ |
| Tour và trải nghiệm | `attraction`, `golf` | Có Thêm vào giỏ và Đặt ngay; bấm Đặt ngay rồi rời đi thì mục nằm lại trong giỏ |
| Tiện ích khác | `combo` | Có Thêm vào giỏ và Đặt ngay; bấm Đặt ngay rồi rời đi thì mục nằm lại trong giỏ |

1. **Giỏ hàng từ chối khách sạn và vé máy bay.** Trang `/cart`, số đếm giỏ, nút "Thêm vào giỏ" ở tour, trải nghiệm và tiện ích khác không đổi; riêng khối gợi ý "Thường được đặt cùng chuyến" ở trang giỏ bị bỏ.
2. **Mọi sản phẩm đều có nút "Đặt ngay"; bấm là vào thẳng trang thanh toán.** Phía sau là một đơn nháp (booking draft): chỉ chứa đúng những gì khách đang đặt trong lần này, sống ngắn, giá và tình trạng còn bán được lấy lại mỗi lần đọc.
3. **Khách không hoàn thành thanh toán** (rời trang thanh toán trước khi bấm Thanh toán, rời trang Stripe, thẻ bị từ chối đủ 3 lần (`PAYMENT_FAILED`), hết hạn giữ chỗ (`EXPIRED`), hoặc huỷ đơn chưa trả tiền): tour, trải nghiệm và tiện ích khác của lần đặt đó nằm lại trong giỏ; khách sạn và vé máy bay thì không được giữ lại ở đâu.
4. **Trang thanh toán `/checkout` có hai nguồn**: giỏ (`/checkout`) hoặc một đơn nháp (`/checkout?draft=<mã>`). Ba bước Hành khách → Dịch vụ → Xem lại và thanh toán (FR-BKG-08) dùng chung cho cả hai.
5. **Đơn nháp sống 30 phút.** Hết hạn thì khách sạn và vé máy bay không được giữ lại, khách đặt lại từ đầu; tour và tiện ích vẫn còn trong giỏ.
6. **Khách chưa đăng nhập cũng dùng được giỏ và Đặt ngay.** Đã đăng nhập: giỏ và đơn nháp lưu trong database. Chưa đăng nhập: lưu trong Redis 3 ngày; đăng nhập thì chuyển sang tài khoản. Bấm Thanh toán mới phải đăng nhập.
7. **Lịch trình của trợ lý:** mỗi thẻ có nút riêng (khách sạn, vé máy bay: Đặt ngay; tour, golf, combo: Thêm vào giỏ và Đặt ngay), và có một nút "Thanh toán tất cả" cho cả lịch trình.
8. **Giữ chỗ, thanh toán Stripe, huỷ và hoàn tiền không đổi** (FR-BKG-02, 03, 06, 07, 11, 12).

Cách gọi: `/checkout` là **trang thanh toán**, gồm ba bước; đặt chỗ là một phần của quá trình thanh toán đó (người dùng nêu khi trả lời Q9b). "Đơn nháp" là tên mới để tránh nhầm với "phiên Stripe" (Checkout Session) và "đơn giữ chỗ" (`PENDING_PAYMENT`).

Lưu ý về combo: nhiều combo có thành phần lưu trú (`catalog.combo_items`), nên giá và chỗ của combo cũng biến động như khách sạn. Theo câu trả lời Q1, combo vẫn vào giỏ; giỏ vẫn kiểm lại giá lúc đọc và lúc thanh toán như hiện nay.

## Các quyết định đã chốt

Người dùng trả lời từng câu trong ngày 2026-10-01; không còn câu nào chờ.

| # | Câu hỏi | Trả lời |
|---|---|---|
| Q1 | Bỏ giỏ cho loại sản phẩm nào? | **mihhquan, 2026-10-01:** chỉ khách sạn và vé máy bay. Tour và trải nghiệm (`attraction`, `golf`) và tiện ích khác (`combo`) vẫn có giỏ hàng. *(Agent đã đề xuất bỏ cho mọi loại; không được chọn.)* Xác nhận lại cùng ngày: nút Thêm vào giỏ chỉ có ở tour và tiện ích; ở khách sạn và vé máy bay thì bỏ nút đó, chỉ còn nút Đặt ngay. |
| Q2 | Lịch trình của trợ lý (lưu trú + hoạt động) đặt thế nào? | **mihhquan, 2026-10-01:** "Sẽ được tự đặt trên lịch trình và một nút thanh toán all cho tất cả." |
| Q3 | Đơn nháp sống bao lâu? | **mihhquan, 2026-10-01:** "Sẽ được giữ trong 30p, thông tin đã nhập được giữ đối với các phần về có giỏ hàng giữ lại còn đối với cái thanh toán luôn như vé máy bay hay, hotel" *(câu dừng ở đây)*. |
| Q4 | Giỏ và đơn nháp lưu ở đâu? | **mihhquan, 2026-10-01:** "Chia ra trường hợp nếu user đã đăng nhập thì lưu vào db, còn nếu chưa thì mình lưu redis với TTL ngắn 3-7 ngày." |
| Q6 | Xử lý `/cart*` trong contract v1? | Không còn là câu hỏi: giỏ ở lại nên `/cart*` giữ nguyên, contract chỉ thêm mới. |
| Q9 | Nút "Đặt ngay" ở tour, trải nghiệm, tiện ích khác làm gì? | **mihhquan, 2026-10-01:** "Tất cả đều có nút đặt ngay và nó vào phần thanh toán, nhưng khi thoát ra chỉ có các vé tour và tiện ích thì sẽ nằm lại trong giỏ hàng." Làm rõ thêm: "ý là cái ở phase khi người dùng không hoàn thành thanh toán". |
| Q9b | Bấm Đặt ngay một vé tham quan khi giỏ đang có mục khác: trang thanh toán gồm những gì? | **mihhquan, 2026-10-01:** "Nếu trong giỏ đang có hàng thì không thanh toán đơn trong giỏ; khi bấm thanh toán thì nếu là đặt ngay thì chỉ thanh toán sản phẩm đó thôi, không liên quan gì đến giỏ. Nếu thanh toán trong màn hình giỏ mới là thanh toán giỏ hàng." Tức phương án (a). Người dùng cũng chỉnh cách gọi: đây là trang thanh toán, đặt chỗ là một bước trong đó. |
| Q3b | Đơn nháp có khách sạn hoặc vé máy bay hết 30 phút | **mihhquan, 2026-10-01:** chốt như đề xuất. Không giữ lại gì; trang báo "Phiên thanh toán đã hết hạn" và dẫn về trang sản phẩm hoặc trang tìm vé để đặt lại từ đầu. |
| Q4a | Khách chưa đăng nhập đi được tới đâu? | **mihhquan, 2026-10-01:** chốt đề xuất. Thêm giỏ, bấm Đặt ngay, điền thông tin đều không cần đăng nhập; bấm Thanh toán thì hộp đăng nhập mở ngay trên trang. |
| Q4b | TTL Redis của khách chưa đăng nhập | **mihhquan, 2026-10-01:** "3 ngày cho khách hàng chưa đăng nhập mà có đơn nháp." |
| Q4c | Khách có giỏ trong Redis rồi đăng nhập: gộp thế nào? | **mihhquan, 2026-10-01:** "Nếu trùng thì chỉ giữ 1 đơn, không duplicate; nếu item khác thì lưu vào giỏ và lưu xuống db. Xoá cái redis cache kia đi." |
| Q7 | Sau khi thanh toán thất bại hoặc hết hạn giữ chỗ? | **mihhquan, 2026-10-01:** chốt đề xuất. Trang đơn có nút "Đặt lại": tạo đơn nháp mới từ các mục của đơn đó, giá tính lại theo catalog hiện tại. |
| Q10 | Khách sạn và vé máy bay đang nằm trong giỏ lúc phát hành? | **mihhquan, 2026-10-01:** "Không đúng logic: khách sạn, vé máy bay quy định là không vào giỏ, nhưng cái đó phải thanh toán luôn." Không còn là câu hỏi: theo luật thì giỏ không được có hai loại này, nên các mục cũ loại đó (thêm trước khi có luật) được migration dọn đi. |
| Q11 | Thẻ và ghim bản đồ của trợ lý khi sản phẩm là khách sạn, vé máy bay | **mihhquan, 2026-10-01:** (b) nút "Đặt ngay" ngay trên thẻ. "Thay vì xem chi tiết có thể nhấn đặt chỗ trực tiếp luôn." |
| Q12 | Thẻ và ghim bản đồ của trợ lý khi sản phẩm là tour, golf, combo | **mihhquan, 2026-10-01:** (b) cả "Thêm vào giỏ" và "Đặt ngay". |
| Q13, Q14 | Khối "Thường được đặt cùng chuyến" ở trang giỏ | **mihhquan, 2026-10-01:** bỏ khối. Q14 không còn áp dụng. |
| Q4d | Sự kiện `add_to_cart` của khách chưa đăng nhập? | **mihhquan, 2026-10-01:** có, "nhưng chú ý là trùng item xử lý như đã trình bày". Không ghi khi chưa đăng nhập; lúc đăng nhập, mỗi mục thực sự được chép sang giỏ của tài khoản ghi một `add_to_cart`; mục trùng (bị bỏ) không ghi. |
| Q5 | Sự kiện `add_to_cart` với sản phẩm đặt trực tiếp? | **mihhquan, 2026-10-01:** đồng ý đề xuất. Vẫn ghi `add_to_cart` khi đơn nháp được tạo, mỗi mục một sự kiện; thêm giỏ vẫn ghi như cũ. |
| Q8 | Chỗ "lưu lại xem sau" cho khách sạn và vé máy bay? | **mihhquan, 2026-10-01:** bỏ, không làm danh sách lưu xem sau. |
| Q11c | Khách sạn trong lịch trình chưa có hạng phòng: bấm Đặt ngay trên thẻ thì sao? | **mihhquan, 2026-10-01:** để lại ghi chú, vì phần này team đang xây dựng, chưa làm được. Trong đợt này: nút Đặt ngay trên thẻ khách sạn của trợ lý chỉ hiện khi sản phẩm đặt được (đã có hạng phòng); chưa có hạng phòng thì thẻ giữ lối sang trang chi tiết như hiện nay và "Thanh toán tất cả" bỏ qua mục đó, báo rõ. Việc lịch trình trả về hạng phòng thuộc phần team trợ lý. |

Cách agent hiểu câu trả lời Q2, Q3, Q4 và đưa vào đề xuất (những chỗ agent phải tự suy ra đã được hỏi lại và có trả lời ở bảng trên):

- **Q2.** Lịch trình có một nút **Thanh toán tất cả**: tạo một đơn nháp gồm mọi mục đặt được của lịch trình (lưu trú và hoạt động) và mở trang thanh toán, trả tiền một lần. Ngoài ra khách tự đặt được từng mục ngay trên lịch trình; nút trên từng thẻ là gì thì theo Q11, Q12.
- **Q3.** Đơn nháp hết hiệu lực sau **30 phút**. Khi hết hạn, hoặc khi khách bỏ dở: tour, trải nghiệm, tiện ích khác vẫn còn trong giỏ với sản phẩm, ngày và số khách đã chọn (luật của Q9). Khách sạn và vé máy bay: phần câu bị dừng được hiểu là **không giữ lại gì, khách đặt lại từ đầu**, người dùng đã chốt ở Q3b. Không còn nút "Cập nhật giá" như bản đề xuất trước. Họ tên, ngày sinh, giấy tờ hành khách vẫn chỉ nằm trong bộ nhớ của trang như quy định hiện có, không lưu ở giỏ hay đơn nháp.
- **Q4.** Người đã đăng nhập: giỏ (`app.carts`, đã có) và đơn nháp (bảng mới) lưu trong database. Khách chưa đăng nhập: giỏ và đơn nháp lưu trong Redis, khoá theo mã phiên khách (`anon_id`) mà Web đã có. Đây là thay đổi phạm vi: hiện nay phải đăng nhập mới thêm giỏ hay bấm Đặt ngay được. Bốn điểm phát sinh (Q4a–Q4d) đã được trả lời ở bảng trên.

Cách agent hiểu các câu trả lời Q4b, Q4c, Q11 và đưa vào đề xuất:

- **Q4b** *(người dùng xác nhận cách hiểu này, 2026-10-01)*. Dữ liệu của khách chưa đăng nhập trong Redis (giỏ và đơn nháp) được giữ **3 ngày** rồi tự xoá. Hiệu lực thanh toán của một đơn nháp vẫn là 30 phút cho mọi người (Q3, Q3b): sau 30 phút, đơn nháp của khách không thanh toán được nữa, khách sạn và vé máy bay phải đặt lại từ đầu; bản ghi còn nằm trong Redis chỉ để trang báo hết hạn biết dẫn khách về sản phẩm nào. Giỏ tour, tiện ích của khách thì dùng được suốt 3 ngày, tính từ lần sửa gần nhất.
- **Q4c** *(người dùng xác nhận cách hiểu này, 2026-10-01)*. Khi đăng nhập: mục nào giỏ tài khoản chưa có thì chép vào `app.carts`; mục trùng sản phẩm và ngày thì chỉ giữ một, là mục đang có trong tài khoản. Đơn nháp đang mở của khách được chuyển vào database dưới tài khoản đó. Xong thì xoá các khoá Redis của phiên khách.
- **Q11.** Thẻ khách sạn trong lịch trình có nút Đặt ngay. Lịch trình hiện có thể gợi ý khách sạn ở cấp cơ sở lưu trú, chưa có hạng phòng (loại không đặt được); trường hợp đó để lại ghi chú theo Q11c.

Cách agent hiểu câu trả lời Q9 và đưa vào đề xuất:

- Bấm Đặt ngay ở bất kỳ sản phẩm nào (và Thanh toán tất cả của trợ lý) đều tạo đơn nháp và mở trang thanh toán.
- Ngay lúc đó, các mục tour, trải nghiệm, tiện ích khác của đơn nháp được **chép vào giỏ** nếu giỏ chưa có mục cùng sản phẩm và ngày. Vì vậy ở mọi trường hợp không hoàn thành thanh toán (rời trang thanh toán trước khi bấm Thanh toán, rời trang Stripe, thẻ bị từ chối đủ 3 lần (`PAYMENT_FAILED`), hết hạn giữ chỗ (`EXPIRED`), hoặc huỷ đơn chưa trả tiền, kể cả đóng tab hay đơn nháp tự hết hạn) các mục này vẫn ở trong giỏ. Khách sạn và vé máy bay chỉ nằm trong đơn nháp và trong đơn giữ chỗ nên không còn lại gì trong giỏ.
- Thanh toán xong (`CONFIRMED`) thì mục tương ứng bị gỡ khỏi giỏ, như luật hiện có.
- Trang thanh toán mở từ Đặt ngay chỉ gồm đúng lần đặt đó, không liên quan tới giỏ; giỏ chỉ được thanh toán khi khách bấm Thanh toán ở trang giỏ (Q9b).

## Nội dung đề xuất

### `requirements.md` §1.4

FR-AGT-04, cuối câu:

> … có giá cụ thể và đường dẫn chuyển tiếp vào trang chi tiết hoặc giỏ hàng.

→

> … có giá cụ thể và đường dẫn chuyển tiếp vào trang chi tiết, giỏ hàng hoặc trang thanh toán.

### `requirements.md` §1.5

FR-BKG-01, thay toàn bộ:

> - **FR-BKG-01 (Quản lý giỏ hàng & Đơn hàng tạm thời):** Cho phép người dùng lưu trữ nhiều dịch vụ (khách sạn, vé máy bay, trải nghiệm) trong cùng một lịch trình.

→

> - **FR-BKG-01 (Giỏ hàng và đặt trực tiếp):**
>   - **Giỏ hàng** chỉ nhận tour và trải nghiệm (vé tham quan, vui chơi, golf) và tiện ích khác (combo). Khách lưu nhiều dịch vụ trong giỏ và thanh toán một lần bằng nút Thanh toán ở trang giỏ. "Đặt ngay" không bao giờ thanh toán kèm giỏ: nó chỉ thanh toán đúng sản phẩm vừa bấm, kể cả khi giỏ đang có mục khác.
>   - **Khách sạn và vé máy bay không vào giỏ** vì giá và chỗ trống đổi liên tục. Khách bấm "Đặt ngay"; hệ thống tạo một đơn nháp chỉ chứa các mục của lần đặt đó và mở trang thanh toán. Thêm hai loại này vào giỏ bị từ chối.
>   - **Mọi sản phẩm đặt được đều có nút "Đặt ngay"** dẫn thẳng vào trang thanh toán. Một đơn nháp được tạo khi khách bấm "Đặt ngay" ở một sản phẩm, chọn một hành trình bay (một chiều hoặc khứ hồi), hoặc bấm "Thanh toán tất cả" ở một lịch trình do trợ lý lập (lưu trú và hoạt động cùng một đơn nháp). Giá và tình trạng còn bán của từng mục được lấy lại từ catalog mỗi lần đọc. Đơn nháp hết hiệu lực sau 30 phút; khi đó khách sạn và vé máy bay không được giữ lại, khách đặt lại từ đầu. Không thêm được sản phẩm rời vào đơn nháp đã có. Đơn nháp không giữ chỗ và không trừ tồn kho.
>   - **Khi khách không hoàn thành thanh toán** (rời trang thanh toán trước khi bấm Thanh toán, rời trang Stripe, thẻ bị từ chối đủ 3 lần (`PAYMENT_FAILED`), hết hạn giữ chỗ (`EXPIRED`), hoặc huỷ đơn chưa trả tiền): các mục tour, trải nghiệm và tiện ích khác của lần đặt nằm lại trong giỏ hàng (được chép vào giỏ lúc bấm "Đặt ngay", nếu giỏ chưa có mục cùng sản phẩm và ngày; chỉ bị gỡ khi đơn `CONFIRMED`). Khách sạn và vé máy bay không được giữ lại.
>   - **Nơi lưu:** người đã đăng nhập thì giỏ và đơn nháp lưu trong database. Khách chưa đăng nhập cũng thêm giỏ và bấm "Đặt ngay" được; giỏ và đơn nháp của họ lưu trong Redis 3 ngày (đơn nháp vẫn chỉ thanh toán được trong 30 phút) và được chuyển sang tài khoản khi đăng nhập: mục chưa có thì thêm, mục trùng thì chỉ giữ một. Tạo đơn và thanh toán luôn cần đăng nhập.

FR-BKG-05, câu cuối:

> Giữ chỗ không trừ tồn kho. Giỏ hàng giữ nguyên cho tới khi đơn `CONFIRMED`.

→

> Giữ chỗ không trừ tồn kho. Đơn tạo từ giỏ: giỏ giữ nguyên cho tới khi đơn `CONFIRMED`. Đơn tạo từ đơn nháp: đơn nháp bị xoá khi đơn giữ chỗ được tạo; các mục tour, trải nghiệm, tiện ích khác của đơn vẫn nằm trong giỏ cho tới khi đơn `CONFIRMED`, còn khách sạn và vé máy bay thì không. Đơn `PAYMENT_FAILED` hoặc `EXPIRED` có nút "Đặt lại": tạo đơn nháp mới từ các mục của đơn đó với giá hiện tại của catalog.

FR-BKG-10: "Hai chặng bay ngược chiều trong cùng giỏ" → "Hai chặng bay ngược chiều trong cùng đơn nháp".

FR-BKG-13: "Khi giỏ có vé máy bay" → "Khi đơn nháp có vé máy bay".

### `requirements.md` §1.6

FR-USR-03, thêm câu cuối:

> Giỏ hàng và đơn nháp không thuộc nhóm endpoint cần đăng nhập: khách chưa đăng nhập dùng được, dữ liệu gắn với phiên khách và chỉ người giữ phiên đó đọc được. Tạo đơn, thanh toán, xem và huỷ đơn vẫn cần đăng nhập.

### `requirements.md` §1.7

FR-CDP-01:

> - `add_to_cart`: Thêm sản phẩm vào giỏ/lịch trình.

→

> - `add_to_cart`: Thêm sản phẩm vào giỏ, hoặc bắt đầu đặt trực tiếp (bấm "Đặt ngay", đặt một lịch trình); mỗi mục của đơn nháp một sự kiện. Chỉ ghi cho người đã đăng nhập (FR-CDP-02); mục khách thêm trước khi đăng nhập được ghi một lần lúc chuyển sang tài khoản, mục trùng bị bỏ thì không ghi.

### `requirements.md` §3

Sửa câu chữ:

| Mã | Hiện tại | Thay bằng |
|---|---|---|
| AC-BKG-01 | "…bấm thanh toán giỏ hàng và trả bằng thẻ test hợp lệ" | "…bấm Thanh toán ở trang thanh toán (mở từ giỏ hoặc từ Đặt ngay) và trả bằng thẻ test hợp lệ" |
| AC-BKG-02 | "…không có event `purchase`, giỏ hàng còn nguyên." | "…không có event `purchase`; các mục tour, trải nghiệm, tiện ích khác của đơn vẫn nằm trong giỏ, khách sạn và vé máy bay thì không. Trang đơn có nút Đặt lại, bấm vào mở trang thanh toán với cùng các mục theo giá hiện tại." |
| AC-BKG-09 | "Giỏ có VJ1602 SGN → CXR…" | "Đơn nháp có VJ1602 SGN → CXR…" |
| AC-BKG-11 | "Giỏ có vé máy bay…" | "Đơn nháp có vé máy bay…" |

AC-BKG-05 (giỏ có vé VinWonders) giữ nguyên.

Thêm năm dòng:

| Mã tiêu chí | Kịch bản / Điều kiện kích hoạt | Hành vi kỳ vọng của hệ thống |
|---|---|---|
| **AC-BKG-13** | Khách bấm Đặt ngay một phòng; trước khi khách bấm Thanh toán, giá phòng trong catalog đổi | Lần đọc đơn nháp kế tiếp (chuyển bước hoặc tải lại trang) hiện giá mới kèm thông báo giá đã đổi từ bao nhiêu sang bao nhiêu. Nếu khách bấm Thanh toán khi chưa thấy giá mới: `409 PRICE_CHANGED`, không tạo đơn, không tạo phiên Stripe. |
| **AC-BKG-14** | Khách mở lại trang thanh toán sau khi đơn nháp đã quá 30 phút: (a) đơn nháp một phòng khách sạn; (b) đơn nháp một vé tham quan; hoặc mở đơn nháp của người khác | (a) Trang báo phiên thanh toán đã hết hạn và dẫn về trang khách sạn; không còn lựa chọn nào được giữ. (b) Trang báo hết hạn và dẫn về giỏ, nơi vé tham quan còn nguyên ngày và số khách. Đơn nháp của người khác: `404`, không lộ nội dung. |
| **AC-BKG-15** | Trang chi tiết hạng phòng khách sạn và trang kết quả vé máy bay; gọi thẳng `POST /cart/items` với một phòng hoặc một chuyến bay | Hai trang chỉ có nút Đặt ngay, không có nút Thêm vào giỏ. Trên thẻ và ghim bản đồ của trợ lý, khách sạn và vé máy bay có nút Đặt ngay, không có nút Thêm vào giỏ; tour, golf, combo có cả Thêm vào giỏ và Đặt ngay. Trang giỏ không còn khối gợi ý. Lời gọi API bị từ chối với mã lỗi cho biết sản phẩm chỉ đặt trực tiếp; giỏ không đổi, không ghi `add_to_cart`. Trang chi tiết vé tham quan vẫn có cả Thêm vào giỏ và Đặt ngay. |
| **AC-BKG-16** | Khách không hoàn thành thanh toán ở ba lần đặt: (a) Đặt ngay một vé tham quan rồi rời trang thanh toán; (b) Đặt ngay một phòng khách sạn rồi rời trang thanh toán; (c) đặt một lịch trình của trợ lý có khách sạn và hai vé tham quan, bấm Thanh toán rồi để đơn hết hạn giữ chỗ (`EXPIRED`) | Giỏ có vé tham quan của (a) (đúng ngày và số khách lúc bấm Đặt ngay) và hai vé của (c); không có phòng khách sạn nào. Bấm Đặt ngay hai lần cho cùng vé và ngày không tạo hai mục giỏ. Khi một lần đặt như vậy được thanh toán thành công, mục tương ứng không còn trong giỏ. |
| **AC-BKG-17** | Khách chưa đăng nhập thêm một vé tham quan vào giỏ, bấm Đặt ngay một phòng khách sạn, điền thông tin rồi bấm Thanh toán; sau đó đăng nhập | Thêm giỏ và mở trang thanh toán đều được mà không cần đăng nhập; không có sự kiện nào trong `cdp.events`. Bấm Thanh toán thì hộp đăng nhập mở, thông tin đã nhập còn nguyên. Đăng nhập xong: giỏ của tài khoản có vé tham quan, `cdp.events` có `add_to_cart` cho vé đó, và thanh toán đi tiếp được. Một trình duyệt khác (phiên khách khác) không đọc được giỏ hay đơn nháp này. |

### `user-flow.md`

- §1.2 bước 4: "**Thêm vào giỏ & Đặt:** Lưu toàn bộ các sản phẩm đã chọn trong lịch trình vào giỏ hàng và tiến hành thanh toán một lần." → "**Đặt lịch trình:** Tự đặt từng mục ngay trên lịch trình, hoặc bấm Thanh toán tất cả để mở trang thanh toán với toàn bộ sản phẩm của lịch trình và thanh toán một lần."
- §2, dòng `/products/:id`, cột thành phần: "Add-to-Cart CTA" → "Book-now CTA; Add-to-Cart CTA (chỉ tour, trải nghiệm, tiện ích khác)".
- §2, dòng `/checkout`: tuyến đường ghi `/checkout` (từ giỏ) và `/checkout?draft=<mã đơn nháp>` (từ Đặt ngay).
- §3.2: nút `I[Người dùng bấm 'Xem chi tiết' hoặc 'Thêm vào chuyến đi']` → `I[Người dùng bấm 'Xem chi tiết', đặt từng mục, hoặc 'Thanh toán tất cả']`; `J[Chuyển trực tiếp sang Giỏ hàng / Đặt chỗ]` → `J[Tạo đơn nháp và mở trang Thanh toán]`.
- §3.3: "Chỉ sửa giỏ, không tạo đơn cho tới khi bấm Thanh toán." → "Chỉ sửa giỏ hoặc đơn nháp, không tạo đơn cho tới khi bấm Thanh toán."; "Backend kiểm giỏ, tạo đơn giữ chỗ 30 phút…" → "Backend kiểm giỏ hoặc đơn nháp, tạo đơn giữ chỗ 30 phút…" (cả trong đoạn văn và nút `D` của sơ đồ).
- §3.3 sơ đồ: giữa `A` và `B` thêm `A1[Backend tạo đơn nháp: kiểm còn bán, lấy giá hiện tại, chép tour và tiện ích vào giỏ]`; thêm nhánh `B -->|Rời trang, chưa thanh toán| X0[Tour, trải nghiệm, tiện ích nằm lại trong giỏ, khách sạn và vé máy bay không giữ]`, và nối `X1`, `X2` về `X0`; thêm nhánh vào `B` từ giỏ: `A2[Khách mở giỏ tour, trải nghiệm, tiện ích khác & bấm Thanh toán] --> B`; `X1[Đơn PAYMENT_FAILED, giỏ còn nguyên]` → `X1[Đơn PAYMENT_FAILED, có nút Đặt lại]`; `X2[Đơn EXPIRED, giỏ còn nguyên]` → `X2[Đơn EXPIRED, có nút Đặt lại]`.
- §4.2 wireframe widget: `[Thêm vào giỏ]  [Thanh toán]` → `[Thanh toán tất cả]`; mỗi thẻ sản phẩm có nút riêng: khách sạn, vé máy bay có `[Đặt ngay]`; tour, golf, combo có `[Thêm vào giỏ] [Đặt ngay]`.
- §3.3: thêm một gạch đầu dòng: "**Đăng nhập.** Khách chưa đăng nhập vẫn thêm giỏ, bấm Đặt ngay và điền thông tin được. Bấm Thanh toán thì hộp đăng nhập mở ngay trên trang; đăng nhập xong, giỏ và đơn nháp của phiên khách chuyển sang tài khoản và thanh toán đi tiếp." Sơ đồ: giữa `P` và `D` thêm `L{Đã đăng nhập?}`, nhánh Chưa đi qua `L1[Đăng nhập, chuyển giỏ và đơn nháp sang tài khoản]`.

### `data-model.md`

- §2.2 ERD: thêm hai thực thể và quan hệ `APP_BOOKING_DRAFTS ||--o{ APP_BOOKING_DRAFT_ITEMS`.
  - `APP_BOOKING_DRAFTS`: `draft_id` PK, `cdp_user_id`, `created_at`, `expires_at`.
  - `APP_BOOKING_DRAFT_ITEMS`: `draft_item_id` PK, `draft_id` FK, `product_id`, `quantity`, `using_date`, `using_date_to`, `unit_price_snapshot`, `adults`, `children`, `child_unit_price_snapshot`.
- §2.2, sau đoạn "Giỏ hàng (FR-BKG-08): …", thêm: "Giỏ hàng chỉ chứa tour, trải nghiệm và tiện ích khác (`attraction`, `golf`, `combo`). Đơn nháp (FR-BKG-01): tạo khi khách bấm Đặt ngay; mỗi mục lưu cùng các trường như mục giỏ. Khi tạo đơn nháp, mục `attraction`, `golf`, `combo` được chép vào giỏ nếu giỏ chưa có mục cùng sản phẩm và ngày. Đơn nháp bị xoá khi tạo đơn giữ chỗ hoặc khi quá hạn."
- §1 (tổng quan lưu trữ): thêm Redis giữ giỏ và đơn nháp của khách chưa đăng nhập, khoá theo mã phiên khách; dữ liệu được giữ 3 ngày rồi tự xoá; đơn nháp vẫn chỉ thanh toán được trong 30 phút. Mã phiên khách không được ghi xuống PostgreSQL.
- §4.2: "Đơn vị có thể thêm vào giỏ và đặt chỗ" → "Đơn vị có thể đặt chỗ. Khách sạn và vé máy bay chỉ đặt trực tiếp; các loại khác thêm được vào giỏ".

### `deployment-plan.md`

- §2 bảng biến môi trường, thêm dòng: `BOOKING_DRAFT_TTL_MINUTES` — thời gian hiệu lực của đơn nháp, mặc định `30` — Tất cả — Không bí mật. Thêm `GUEST_BOOKING_TTL_DAYS` — thời gian Redis giữ giỏ và đơn nháp của khách chưa đăng nhập, mặc định `3` — Tất cả — Không bí mật. Thêm `BOOKING_REDIS_URL` — Redis cho giỏ và đơn nháp của khách chưa đăng nhập, dùng DB index riêng — Tất cả — Có mật khẩu; không mở ra mạng ngoài.
- §5, mục xem DB trên monitor: ví dụ liên kết ngược của sản phẩm thêm `booking_draft_items`; mô tả luồng dữ liệu "giỏ, đơn, thanh toán" → "giỏ, đơn nháp, đơn, thanh toán".

### `test-plan.md` §3

Bước 6: "Thêm sản phẩm vào giỏ, điền thông tin…" → "Bấm Đặt ngay ở khách sạn A, điền thông tin…" (bước 3–4 của kịch bản đang xem khách sạn A, loại không còn vào giỏ được).

## Thay đổi source sau khi chốt

Chi tiết và thứ tự: `docs/plan/2026-10-01-khach-san-ve-may-bay-dat-truc-tiep.md`.

- **Spec:** spec mới `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md`; bỏ khối "Thường được đặt cùng" khỏi `docs/spec/product.md` §4.4, §6 và `docs/spec/hop-dong-tich-hop-frontend.md` §4.4 (khối này chỉ có ở spec, PRD không nhắc); sửa `docs/spec/hop-dong-tich-hop-auth.md` (§3.7 khách vãng lai, bảng endpoint cần đăng nhập); sửa `docs/spec/hop-dong-tich-hop-backend.md` §7.1, §7.2, §8.2, `docs/spec/hop-dong-tich-hop-frontend.md` §4.4–§4.8, `docs/spec/product.md` §4.4, §6.7, `docs/spec/hop-dong-tich-hop-cdp.md`, `docs/spec/DATABASE_SCHEMA.md`, hai spec trong `docs/spec/booking/`.
- **Contract (chỉ thêm, không gỡ):** `src/shared/contracts/paths/booking.yaml`, `schemas/booking.yaml`, `schemas/common.yaml`, `schemas/catalog.yaml`, `paths/events.yaml`, `openapi.yaml`: thêm `/booking-drafts*`, `draftId`, ba mã lỗi; `/cart*` và `/booking-drafts*` nhận cả khách chưa đăng nhập (`CartResponse.cdpUserId` cho phép `null` với khách); mock trong `src/shared/mocks/booking/`; sinh lại `src/frontend/src/types/api.gen.ts`.
- **DDL:** `db/vota_schema.sql`, `db/init/01_vota.sql`, một migration mới (tạo hai bảng đơn nháp; xoá mục giỏ là khách sạn, vé máy bay), `db/verify.sql`.
- **Backend:** `src/backend/app/domain/booking/`, `application/booking/` (thêm `drafts.py`; sửa `cart.py`, `create_hold.py`), `application/ports/`, adapter Postgres và adapter Redis cho khách chưa đăng nhập, gộp khi đăng nhập, route và DTO booking, `core/config.py`.
- **Frontend:** `TravelContext`, checkout (hai nguồn), trang chi tiết, kết quả vé máy bay, widget trợ lý, trang đơn, trang giỏ (bỏ khối gợi ý). Header, thanh tab giữ nguyên.
- **Seed:** `src/data_collection/seed/database.py` (thêm hai bảng đơn nháp vào danh sách `--reset`).
