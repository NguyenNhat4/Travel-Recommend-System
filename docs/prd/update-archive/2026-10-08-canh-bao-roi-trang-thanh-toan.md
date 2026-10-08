# Hỏi lại trước khi khách rời trang thanh toán

- Ngày: 2026-10-08
- Người đề xuất: mihhquan / Claude
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: mihhquan, 2026-10-08 (chốt khi duyệt kế hoạch; áp dụng vào PRD cùng ngày)
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.5 FR-BKG-01 (thêm ý sau "Khi khách không hoàn thành thanh toán") và §3 (thêm AC-BKG-20); `docs/prd/user-flow.md` §3.3 (thêm ý "Rời trang khi chưa thanh toán" và sửa lưu đồ)
- Mã FR/NFR: FR-BKG-01, FR-BKG-06

## Lý do

Ở `/checkout`, khách bấm logo, nút quay lại, một liên kết ở chân trang, nút Back của trình duyệt hoặc đóng tab là rời trang ngay, không có bước hỏi lại. Hậu quả với khách:

- Lần Đặt ngay có khách sạn hoặc vé máy bay: lựa chọn đó không được giữ, phải chọn lại và giá có thể đã đổi.
- Mọi nguồn (giỏ và Đặt ngay): họ tên, ngày sinh, giấy tờ hành khách đã nhập bị mất, vì các thông tin này chỉ nằm trong bộ nhớ của trang.

PRD hiện chỉ ghi kết quả sau khi rời trang (tour nằm lại trong giỏ, khách sạn và vé máy bay không giữ), chưa có bước xác nhận. User story: khách chủ động thoát ra thì hiện thông báo.

Thay đổi chỉ ở Web. Rời trang không gọi API nào: đơn nháp tự hết hạn sau 30 phút, tour và tiện ích đã được chép vào giỏ từ lúc bấm Đặt ngay. Không đổi contract, Backend hay DDL.

Giới hạn của trình duyệt cần biết khi duyệt:

- Trình duyệt chỉ cho trang chặn nút Back sau khi khách đã thao tác trên trang (bấm hoặc gõ). Khách vào trang rồi bấm Back ngay thì rời luôn.
- Khi đóng tab, tải lại hoặc gõ địa chỉ khác, trang chỉ được yêu cầu trình duyệt hỏi lại bằng hộp mặc định của nó; không đổi được chữ hay giao diện, và một số trình duyệt di động không hiện hộp này.

Giao diện đã duyệt: https://claude.ai/artifact/BaFqEtCuhAeewniaj84db6 (trên điện thoại hộp trượt lên từ đáy màn hình).

## Nội dung đề xuất

**`docs/prd/requirements.md` §1.5, FR-BKG-01** — thêm một ý ngay sau ý "Khi khách không hoàn thành thanh toán":

> - **Hỏi lại trước khi rời trang thanh toán:** khách chưa bấm Thanh toán mà chủ động rời trang thanh toán (bấm logo, nút quay lại, một liên kết khác trên trang, hoặc nút Back của trình duyệt khi đang ở bước Hành khách) thì Web hiện hộp cảnh báo trước khi rời. Hộp nêu thứ sẽ mất (khách sạn, vé máy bay của lần đặt không được giữ; thông tin hành khách đã nhập bị xoá) và thứ còn lại (tour, trải nghiệm, tiện ích vẫn trong giỏ), với hai nút "Ở lại thanh toán" và "Rời trang". Áp dụng cho cả thanh toán từ giỏ và từ Đặt ngay, kể cả khi khách chưa nhập gì. Đóng tab, tải lại trang hoặc gõ địa chỉ khác thì trình duyệt hiện hộp hỏi lại mặc định của nó. Không hỏi khi khách bấm Thanh toán để sang Stripe, khi phiên thanh toán hết hạn, hay khi chuyển giữa ba bước. Trình duyệt chỉ cho chặn nút Back sau khi khách đã thao tác trên trang. Hộp chỉ là bước xác nhận ở Web: khách chọn "Rời trang" thì kết quả đúng như mục trên.

**`docs/prd/requirements.md` §3** — thêm dòng vào ma trận tiêu chí nghiệm thu:

> | **AC-BKG-20** | Khách mở trang thanh toán của một lần Đặt ngay phòng khách sạn, nhập họ tên một hành khách, rồi: (a) bấm logo; (b) bấm Back của trình duyệt ở bước Hành khách; (c) bấm Back ở bước Dịch vụ; (d) bấm Thanh toán | (a), (b): hộp "Rời trang thanh toán?" hiện, nêu phòng không được giữ và thông tin đã nhập sẽ mất. "Ở lại thanh toán" đóng hộp, họ tên đã nhập còn nguyên; "Rời trang" đưa khách tới trang chủ (a) hoặc trang trước (b). (c): về bước Hành khách, không hỏi. (d): sang Stripe, không hỏi. Với thanh toán từ giỏ, hộp ghi các dịch vụ vẫn nằm trong giỏ. |

**`docs/prd/user-flow.md` §3.3** — thêm một ý sau ý "Chưa rời trang khi chưa bấm Thanh toán":

> - **Rời trang khi chưa thanh toán.** Khách bấm logo, nút quay lại, một liên kết khác trên trang, hoặc Back của trình duyệt khi đang ở bước Hành khách thì hộp "Rời trang thanh toán?" hiện lên (trên điện thoại trượt lên từ đáy màn hình), nêu thứ sẽ mất và thứ còn trong giỏ. "Ở lại thanh toán" đóng hộp và giữ nguyên dữ liệu đang nhập; "Rời trang" mới rời đi. Back giữa ba bước vẫn chỉ lùi một bước. Đóng tab hoặc tải lại trang thì trình duyệt hỏi bằng hộp mặc định của nó.

Trong lưu đồ của §3.3, cạnh:

> `B -->|Rời trang, chưa thanh toán| X0[Tour, trải nghiệm, tiện ích nằm lại trong giỏ, khách sạn và vé máy bay không giữ]`

thay bằng:

> `B -->|Khách chủ động rời trang| W{Hộp cảnh báo rời trang}`
> `W -->|Ở lại thanh toán| B`
> `W -->|Rời trang| X0[Tour, trải nghiệm, tiện ích nằm lại trong giỏ, khách sạn và vé máy bay không giữ]`

## Thay đổi source sau khi chốt

- `src/frontend/src/context/TravelContext.tsx`: `navigate()` hỏi một guard do trang đang mở đăng ký (`setNavigationGuard`).
- `src/frontend/src/components/checkout/useLeaveGuard.ts` (mới): chặn `navigate()`, thẻ `<a>`, `beforeunload` và nút Back.
- `src/frontend/src/components/checkout/LeaveCheckoutDialog.tsx` (mới): hộp cảnh báo và nội dung theo nguồn.
- `src/frontend/src/components/checkout/useCheckout.ts`, `CheckoutView.tsx`: nối guard, bỏ qua guard ở các lần rời trang do hệ thống (sang Stripe, giỏ rỗng).
- Test: `src/frontend/tests/unit/checkoutView.test.tsx`, `src/frontend/tests/e2e/checkout-leave.spec.ts` (mới).
- Spec: `docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md` §6.2, §10.1; `docs/spec/hop-dong-tich-hop-frontend.md` §4.5; `docs/spec/booking/dat-truc-tiep-theo-don-nhap.md` §13; `docs/spec/product.md` §4.5; `src/frontend/README.md`.
