# Góp ý widget trợ lý sau chat thử 11/10: vé mở tab mới, form ngay lượt đầu, sở thích nơi ở, thẻ rõ số

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng (PRD 2026-10-12; source theo 8 phần việc batch cùng ngày, xem `history/2026-10-12-*`)
- Chốt bởi / ngày: agent chốt theo uỷ quyền của Nguyễn Minh Nhật ("mình cho phép bạn duyệt plan luôn ... chốt prd proposed
  luôn"), 2026-10-12
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-01, AC-AGT-03, AC-AGT-04); `docs/prd/user-flow.md` §4.2;
  `docs/prd/architecture.md` §3
- Mã FR/NFR: FR-AGT-01, FR-AGT-03, FR-AGT-04, FR-AGT-06, FR-AGT-07, NFR-REL-01; AC-AGT-01, AC-AGT-03, AC-AGT-04, AC-AGT-08

## Lý do

Người dùng chat thử widget trợ lý và góp ý (11/10/2026):

1. Bấm ô ngày–giá của câu trả lời vé máy bay thì cả trang chuyển sang trang vé, mất cuộc trò chuyện; muốn mở tab mới để
   đóng tab là quay lại. Trang vé lại chọn sẵn hạng Thương gia nên giá không khớp giá trên ô. Nguyên nhân đã kiểm:
   `fareClasses` xếp ECO, PRE, BUS, FST rồi mới tới hạng chưa rõ, mà vé giá gốc của catalog (971 vé) không ghi hạng, còn
   vé Thương gia mô phỏng (1.505 vé) ghi `BUSINESS`; trang vé chọn sẵn phần tử đầu → Thương gia.
2. Người dùng xin lập lịch ("lên lịch trình đi Đà Nẵng") thì lượt đầu chỉ có câu hỏi; form chỉ hiện từ lượt sau. Muốn có
   form ngay dưới câu trả lời đầu.
3. Ô "Sở thích nơi ở" chỉ có 5 chip cố định, không theo dữ liệu của điểm đến; muốn gợi ý dựa trên dữ liệu đang có, tự điền
   được, và có nút "Gợi ý bằng AI".
4. Nút "Dùng vị trí hiện tại" chờ lâu rồi báo "Chưa xác định được".
5. Lời trả lời gọi di tích, thắng cảnh là "vé tham quan tự do"; và nhắc lại giá đã có trên thẻ.
6. Khối "Ngân sách dự tính" hiện "Vé máy bay 0 ₫" khi lịch không có vé máy bay.
7. Bấm ảnh trong panel chi tiết không phóng to.
8. Thẻ phương án khách sạn chỉ ghi "+2,5 km" so với khách sạn đang chọn; người dùng phải tự tính và không biết thẻ nào rẻ
   nhất, thẻ nào ít đi lại nhất.
9. Thẻ combo trông như mọi thẻ khác; muốn nổi bật, nút "Đặt ngay" rộng.

Các mục 2, 3, 4, 6, 8 trái với câu chữ PRD hiện hành ("form hiện khi đã hỏi một lượt", năm sở thích cố định, "Nhóm bằng 0
vẫn có dòng", "mỗi thẻ ghi chênh tiền, chênh km"). Các mục còn lại PRD chưa nói rõ; ghi vào đây để PRD mô tả đúng hành vi mới.

## Nội dung đề xuất

### 1. `requirements.md` §3, AC-AGT-01

Sau câu "Trợ lý hỏi gộp một câu, một lần, những gì còn thiếu … (không tự đoán ngày).", thêm:

> Câu hỏi gộp này kèm luôn form thông tin chuyến đi điền sẵn mô tả dưới đây, để người dùng trả lời bằng chữ hoặc điền form.

Sau câu "Sở thích khách sạn chọn trong form hoặc nói trong câu (Hồ bơi, …, Spa) làm khách sạn … còn ít nhất 3 khách sạn
hợp.", thêm:

> Ô sở thích nơi ở của form chỉ liệt kê những sở thích (trong năm sở thích trên) mà khách sạn của điểm đến đang chọn trong
> form có ghi nhận trong catalog, kèm số khách sạn có ghi nhận; điểm đến chưa có khách sạn nào ghi nhận thì liệt kê đủ năm
> sở thích, không kèm số. Ô có thêm một ô tự điền (ví dụ "gần chợ đêm") và nút "Gợi ý bằng AI": LLM nhận danh sách sở thích
> có dữ liệu của điểm đến (nhãn, số khách sạn) cùng điểm đến, số ngày, số người lớn, số trẻ em, rồi chọn tối đa 3 sở thích
> trong danh sách đó kèm một câu lý do; form tích sẵn các sở thích được gợi ý, người dùng bỏ hoặc thêm được trước khi xác
> nhận. LLM lỗi thì form báo chưa gợi ý được và vẫn dùng bình thường. Sở thích tự điền được ghi vào câu yêu cầu như một ưu
> tiên, không phải điều kiện bắt buộc.

### 2. `requirements.md` §3, AC-AGT-03

Hiện tại: "Từ chối hoặc lỗi thì giữ ô để gõ tay."

Thay bằng:

> Danh sách thành phố có sân bay của catalog được nạp sẵn khi form hiện, nên khi trình duyệt trả vị trí thì ô nơi đi được
> điền ngay. Trình duyệt không trả vị trí trong 5 giây, người dùng từ chối hoặc có lỗi thì giữ ô để gõ tay, kèm một câu báo
> ngắn và tối đa 4 nút chọn nhanh là các thành phố có nhiều tuyến bay nhất trong catalog.

### 3. `requirements.md` §3, AC-AGT-04

Hiện tại: "Mục "Phương án khác" hiện trong câu trả lời của trợ lý dưới dạng một hàng thẻ khách sạn lướt ngang: thẻ đầu là
khách sạn của lịch đang chọn (nhãn "Đang chọn", tổng km cả chuyến), các thẻ sau là phương án khác, mỗi thẻ ghi chênh tiền,
chênh km và vượt ngân sách bao nhiêu (nếu có) so với lịch đang chọn."

Thay bằng:

> Mục "Phương án khác" hiện trong câu trả lời của trợ lý dưới dạng một hàng thẻ khách sạn lướt ngang: thẻ đầu là khách sạn
> của lịch đang chọn (nhãn "Đang chọn"), các thẻ sau là phương án khác. Mỗi thẻ ghi số của chính phương án đó: tổng tiền cả
> chuyến (khi biết đủ giá) và tổng km cả chuyến; thẻ phương án ghi thêm ở dòng phụ chênh tiền, chênh km so với lịch đang
> chọn và vượt ngân sách bao nhiêu (nếu có). Mỗi thẻ có một nhãn tiêu chí tính từ chính các số trong hàng thẻ: "Rẻ nhất"
> (tổng tiền thấp nhất), "Đi lại ít nhất" (tổng km nhỏ nhất), "Rẻ nhất · Đi lại ít nhất" khi một thẻ đứng đầu cả hai,
> "Hạng sao cao nhất" khi đúng một khách sạn có hạng sao cao nhất hàng; thẻ không đứng đầu tiêu chí nào ghi điểm đánh đổi so
> với lịch đang chọn ("Gần hơn, đắt hơn" hoặc "Rẻ hơn, xa hơn").

### 4. `user-flow.md` §4.2

- **Thẻ trong khung chat**, thêm cuối đoạn:

  > Lời diễn giải không nhắc lại giá của sản phẩm đã có thẻ và không ghi tổng tiền (đã có khối Ngân sách dự tính). Điểm
  > tham quan tự do (di tích, thắng cảnh, công viên, chợ…) được mô tả như một nơi để ghé, không gọi là vé hay "vé tham quan
  > tự do". Câu hỏi trực tiếp về giá (giá vé máy bay, "bao nhiêu tiền", "có mất vé không") vẫn được trả lời bằng giá hoặc
  > câu có/không. **Thẻ combo** lớn hơn thẻ gọn: ảnh rộng, tên, giá, điểm đánh giá (nếu có) và một nhãn nổi bật lấy từ dữ
  > liệu: "Giảm X%" khi catalog có giá gốc cao hơn giá bán; nếu không thì "Được yêu thích nhất" khi combo có nhiều lượt đánh
  > giá nhất trong các sản phẩm của câu trả lời và từ 50 lượt; nếu không thì "Đánh giá cao" khi điểm từ 4,5; còn lại "Combo
  > trọn gói". Combo thuộc lịch trình có nút [Đặt ngay] rộng hết bong bóng và [Thêm vào giỏ]; combo của câu trả lời khám phá
  > không có hai nút này, bấm thẻ mở panel chi tiết.

- **Ngân sách dự tính**, hiện tại: "Nhóm bằng 0 vẫn có dòng nhưng không có đoạn trên thanh." Thay bằng:

  > Nhóm bằng 0 (ví dụ lịch không có vé máy bay hay lưu trú) không có dòng và không có đoạn trên thanh; dòng ghi chú cuối
  > khối chỉ kể các nhóm có trong lịch.

- **Hàng thẻ ngày–giá**, hiện tại: "Bấm ô mở trang vé máy bay `/flights?origin=<nơi đi>&destination=<nơi đến>&checkIn=<ngày
  bay>` đúng tuyến, đúng ngày." Thay bằng:

  > Bấm ô mở trang vé máy bay ở một tab mới của trình duyệt (widget và cuộc trò chuyện giữ nguyên ở tab cũ, đóng tab mới là
  > quay lại), địa chỉ `/flights?origin=<nơi đi>&destination=<nơi đến>&checkIn=<ngày bay>&fare=<productId của ô>`: đúng
  > tuyến, đúng ngày, chuyến của ô được chọn sẵn đúng hạng vé có giá như trên ô và được cuộn tới. Trang vé máy bay mở không
  > có `fare` (hoặc `fare` không thuộc kết quả) thì mỗi chuyến chọn sẵn hạng có giá thấp nhất.

- **Panel chi tiết**, thêm cuối đoạn:

  > Bấm vào ảnh (ảnh lớn hoặc ảnh nhỏ) mở trình xem ảnh phóng to phủ màn hình: xem ảnh trước/sau bằng nút hoặc phím mũi
  > tên, có số thứ tự ảnh; X hoặc Esc chỉ đóng trình xem và trở về panel.

- **Form gợi ý thông tin chuyến đi**, hiện tại: "chỉ sau khi người dùng đồng ý lập lịch (AC-AGT-06): khi trợ lý đã hỏi một
  lượt mà vẫn thiếu điểm đến, số ngày, ngày đi hoặc số người (form hiện ở mỗi lượt cho tới khi đủ; ngân sách không bắt
  buộc), hoặc ngay khi người dùng xin form" và "sở thích — chọn nhiều, không bắt buộc: Hồ bơi, Phù hợp trẻ nhỏ, View biển,
  Có bữa sáng, Spa". Thay lần lượt bằng:

  > chỉ sau khi người dùng đồng ý lập lịch (AC-AGT-06): ngay ở lượt hỏi gộp đầu tiên khi còn thiếu điểm đến, số ngày, ngày
  > đi hoặc số người (form nằm dưới câu hỏi), ở mỗi lượt sau cho tới khi đủ (ngân sách không bắt buộc), hoặc ngay khi người
  > dùng xin form

  > sở thích nơi ở — chọn nhiều, không bắt buộc: các sở thích (trong Hồ bơi, Phù hợp trẻ nhỏ, View biển, Có bữa sáng, Spa)
  > mà khách sạn của điểm đến đang chọn có ghi nhận, kèm số khách sạn; một ô tự điền; nút "Gợi ý bằng AI" tích sẵn tối đa 3
  > sở thích hợp chuyến đi kèm một câu lý do (AC-AGT-01)

### 5. `architecture.md` §3, Tiêu chuẩn Grounding — thêm sau mục "Vé máy bay"

> - **Gợi ý sở thích nơi ở bằng AI** (AC-AGT-01): LLM chỉ nhận danh sách sở thích có dữ liệu của điểm đến (nhãn, số khách
>   sạn do code đếm từ catalog) và thông tin chuyến (điểm đến, số ngày, số người lớn, số trẻ em); không nhận toạ độ hay dữ
>   liệu cá nhân. Code chỉ nhận nhãn có trong danh sách, bỏ phần còn lại; LLM lỗi hoặc quá giờ thì không có gợi ý, form vẫn
>   dùng được.

### Không đổi

Grounding 100% (FR-AGT-04, NFR-REL-01): mọi sản phẩm, giá, `productId` vẫn từ Search/Recommendation/Catalog; nhãn tiêu chí
và nhãn nổi bật do code tính từ dữ liệu, LLM không đặt. Thẻ vẫn ghi "Tham quan tự do" ở chỗ giá của điểm miễn phí.

## Thay đổi source sau khi chốt

Chia 8 phần việc (plan batch 12/10), mỗi phần một entry `history/2026-10-12-<slug>.md`:

1. Ô ngày–giá mở tab mới, `fare=<productId>`, trang vé chọn sẵn đúng hạng / hạng rẻ nhất:
   `src/frontend/src/features/itinerary/widget/WidgetFareDays.tsx`, `src/frontend/src/features/flights/results/*`.
2. Form ngay lượt hỏi gộp đầu: `src/backend/app/agents/steps/conversation.py`, `classification.py`, `prompts.py`.
3. Sở thích nơi ở theo dữ liệu + "Gợi ý bằng AI": contract 1.26.0 (`POST /assistant/stay-preferences`), backend route,
   use case, port/adapter LLM, `src/frontend/src/components/assistant/TripDetailsForm.tsx`.
4. Vị trí hiện tại nhanh, có nút chọn nhanh khi lỗi: `TripDetailsForm.tsx`, `src/frontend/src/services/flights.ts`.
5. Lời diễn giải không nhắc giá, không gọi điểm miễn phí là vé: `src/backend/app/agents/steps/prompts.py`, `narration.py`,
   `exploration.py`, `messages.py`.
6. Ngân sách bỏ dòng 0 ₫, thẻ khách sạn có nhãn tiêu chí và số tuyệt đối: `WidgetBudget.tsx`, `WidgetStayOptions.tsx`,
   `widgetPlan.ts`.
7. Trình xem ảnh phóng to: `WidgetProductGallery.tsx`, `WidgetProductDetail.tsx`.
8. Thẻ combo nổi bật: `WidgetNarration.tsx`, thẻ mới `WidgetComboCard.tsx`.
