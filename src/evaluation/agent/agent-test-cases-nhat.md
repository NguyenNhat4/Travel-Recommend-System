# Bộ test case cho agent lập lịch trình du lịch

**Nguồn:** `agent case Nhat -1(1).pdf` (10 trang, 9 case; trang 6 trống).

## Quy ước và phạm vi

- `Tx`: lượt chat của người dùng thứ x; `Ax`: lượt chat của trợ lý theo ký hiệu trong tài liệu gốc.
- Phần **Hội thoại tái hiện** được chép hoặc tóm lược từ văn bản và ảnh chụp trong PDF. Các câu A được tóm lược có ghi theo ý; không phải toàn bộ phản hồi nguyên văn.
- Phần **Tiêu chí đạt đề xuất** là bổ sung để chuẩn bị kiểm thử, cần chốt với nhóm trước khi dùng làm bộ chấm tự động.
- Không có cấu hình tool, fixture dữ liệu, danh sách điểm đến hỗ trợ hoặc quy tắc bắt buộc điền form trong PDF; không tự đặt các giá trị này.
- Case 6 giữ nguyên ký hiệu lượt chat không liên tục của nguồn.
- Ví dụ phản hồi chỉ minh họa ý cần thể hiện; không yêu cầu agent khớp nguyên văn.

## Danh mục

| ID | Tình huống | Trang PDF |
| --- | --- | --- |
| TC-01 | Cập nhật ngày qua nhiều lượt chat | 1 |
| TC-02 | Form hiển thị giá trị mặc định nhất quán | 2 |
| TC-03 | Giải thích khi chưa tìm được lịch trình | 3 |
| TC-04 | Hủy yêu cầu đổi điểm đến | 4 |
| TC-05 | Hỏi điểm đến mới trước khi lập kế hoạch | 5 |
| TC-06 | Hiểu nhu cầu đi biển và xử lý điểm đến mơ hồ | 7 |
| TC-07 | Không tự xác nhận Đà Nẵng | 8 |
| TC-08 | Không dựng lịch trình hoàn chỉnh khi thiếu ngày | 9 |
| TC-09 | Không tự sinh hoặc đảo ngày khởi hành | 10 |
| TC-11 | Lịch không lặp một nơi | — (trace LangSmith 08/10/2026) |

## TC-01 - Cập nhật ngày qua nhiều lượt chat

**Case gốc:** 1. **Trang PDF:** 1.

### Hội thoại tái hiện

```text
T1: Lên lịch trình 1 ngày tại Hà Nội, bắt đầu từ ngày 2026-10-02, cho 2 người lớn, ngân sách khoảng 1 triệu.
T2: Đổi ngày
T3: Ngày 14 tháng 10
T4: À nhầm ngày 15 tháng 10
```

### Lỗi quan sát trong nguồn

Đôi khi không ghi nhận ngày ở T3 và hỏi lại. Ở T4 không đổi ngày, vẫn hỏi lại; chỉ trả lời “Lịch trình đã được hoàn tất.”, thiếu diễn giải.

### Tiêu chí đạt đề xuất

- [ ] Sau T2 hỏi ngày mới.
- [ ] Sau T3 ghi nhận ngày 14/10; sau T4 cập nhật thành 15/10, giữ các thông tin khác.
- [ ] Không hỏi lại ngày đã được cung cấp rõ ràng.
- [ ] Thông báo ngày vừa cập nhật và trình bày lịch trình hoặc trạng thái xử lý thực tế.

### Ví dụ phản hồi mong đợi

> Mình ghi nhận đổi ngày đi thành 15 tháng 10. Lịch trình mình gợi ý như sau…

## TC-02 - Form hiển thị giá trị mặc định nhất quán

**Case gốc:** 2. **Trang PDF:** 2.

### Hội thoại tái hiện

```text
T1: Mình muốn một chuyến nghỉ dưỡng, ưu tiên thư giãn và nghỉ ngơi.
A1: Hỏi điểm đến và số ngày; gợi ý Đà Nẵng, Nha Trang hoặc Phú Quốc.
T2: ko biết đi đâu
A2: Gợi ý Đà Nẵng và hiển thị form thông tin chuyến đi.
```

### Lỗi quan sát trong nguồn

Agent gợi ý Đà Nẵng nhưng form chưa chọn Đà Nẵng.

### Tiêu chí đạt đề xuất

- [ ] Giá trị điểm đến gợi ý/mặc định hiển thị trên form phải khớp lời trả lời.
- [ ] Phân biệt giá trị được agent đề xuất với giá trị người dùng đã xác nhận.
- [ ] Người dùng có thể sửa và xác nhận form.

## TC-03 - Giải thích khi chưa tìm được lịch trình

**Case gốc:** 3. **Trang PDF:** 3.

### Hội thoại tái hiện

```text
T1: Mình muốn một chuyến nghỉ dưỡng, ưu tiên thư giãn và nghỉ ngơi. 1 ngày 2 đêm
A1: Hỏi điểm đến.
T2: Đà nẵng
A2: Hỏi ngày khởi hành, số người và ngân sách.
T3: ngày 15/10, 2 người lớn
```

### Lỗi quan sát trong nguồn

Agent báo “Chưa dựng được lịch trình hoàn chỉnh”, chỉ nói các phần bên dưới là ứng viên tham khảo; chưa giải thích nguyên nhân hay gợi ý điều chỉnh.

### Tiêu chí đạt đề xuất

- [ ] Khi không tìm được lịch trình, giải thích nguyên nhân dựa trên kết quả thực tế; không bịa nguyên nhân.
- [ ] Đề xuất bước tiếp theo phù hợp, chẳng hạn đổi ngày hoặc điều kiện tìm kiếm.
- [ ] Không tuyên bố đã hoàn tất lịch trình.

## TC-04 - Hủy yêu cầu đổi điểm đến

**Case gốc:** 4. **Trang PDF:** 4.

### Hội thoại tái hiện

```text
T1: đi hà nội 3 ngày
A1: Hỏi thêm ngày khởi hành, số người và ngân sách.
T2: đổi điểm đi
A2: Hỏi muốn đổi điểm đến thay Hà Nội thành nơi nào.
T3: không đổi nữa
```

### Lỗi quan sát trong nguồn

Agent hiểu thành không muốn đi Hà Nội nữa và tiếp tục hỏi điểm đến mới.

### Tiêu chí đạt đề xuất

- [ ] Nhận diện T3 là hủy thao tác thay đổi.
- [ ] Giữ Hà Nội và thời lượng 3 ngày.
- [ ] Xác nhận lại vẫn đi Hà Nội theo yêu cầu trong PDF.

### Ví dụ phản hồi mong đợi

> Vậy mình giữ chuyến đi Hà Nội 3 ngày như ban đầu, đúng không?

## TC-05 - Hỏi điểm đến mới trước khi lập kế hoạch

**Case gốc:** 5. **Trang PDF:** 5.

### Hội thoại tái hiện

```text
T1: đi ha noi
A1: Hỏi số ngày chuyến đi.
T2: 3 ngay
A2: Hỏi ngày khởi hành, số người và ngân sách.
T3: doi diem den
```

### Lỗi quan sát trong nguồn

Không hỏi đổi sang đâu mà trả lời “Lịch trình đã được hoàn tất.”

### Tiêu chí đạt đề xuất

- [ ] Hỏi người dùng muốn đổi sang điểm đến nào.
- [ ] Không tự chọn điểm đến mới.
- [ ] Không lập kế hoạch hoàn chỉnh khi yêu cầu đổi điểm đến còn thiếu thông tin.

### Ví dụ phản hồi mong đợi

> Bạn muốn đổi từ Hà Nội sang điểm đến nào?

## TC-06 - Hiểu nhu cầu đi biển và xử lý điểm đến mơ hồ

**Case gốc:** 6. **Trang PDF:** 7.

### Hội thoại tái hiện

```text
T1: đi hà nội
A1: Hỏi số ngày.
T2: 3 ngày
A2: Hỏi ngày khởi hành, số người và ngân sách.
T3: doi diem di
A3: Hỏi xác nhận điểm đến và số ngày.
T4: không đổi nữa
A4: Lập kế hoạch Hà Nội 3 ngày.
T5: mình muốn đi biển cơ
A5: Báo điểm đến không hỗ trợ; liệt kê Hà Nội, Đà Nẵng, Nha Trang…
T6: biển hà nội
A7: Tiếp tục báo chỉ hỗ trợ trong nước; gợi ý Đà Nẵng/Nha Trang và hiển thị form.
T8: biển hà nội
A9: Lặp lại phản hồi tương tự.
```

### Lỗi quan sát trong nguồn

Agent nhận “biển” thành điểm đến rồi báo không nằm trong địa điểm hỗ trợ.

### Tiêu chí đạt đề xuất

- [ ] Hiểu “đi biển” là nhu cầu/loại trải nghiệm; hỏi hoặc đề xuất điểm đến phù hợp.
- [ ] Với “biển hà nội”, làm rõ người dùng muốn đi biển xuất phát từ Hà Nội hay muốn tìm nơi đi biển khác.
- [ ] Không lặp thông báo ngoài phạm vi trong nước chỉ vì từ “biển”.
- [ ] Không tự gán điểm đến mới khi chưa được xác nhận.

## TC-07 - Không tự xác nhận Đà Nẵng

**Case gốc:** 7. **Trang PDF:** 8.

### Hội thoại tái hiện

```text
T1: muốn đi biển 3 ngày
A1: Gợi ý Đà Nẵng và hỏi có muốn chọn nơi này không.
T2: đi biển
```

### Lỗi quan sát trong nguồn

Agent trả lời “Rất vui khi bạn chọn Đà Nẵng!” dù người dùng chưa chọn.

### Tiêu chí đạt đề xuất

- [ ] Giữ nhu cầu đi biển và thời lượng 3 ngày.
- [ ] Không coi T2 là xác nhận Đà Nẵng.
- [ ] Hỏi chọn điểm đến hoặc đưa các lựa chọn để người dùng xác nhận.

## TC-08 - Không dựng lịch trình hoàn chỉnh khi thiếu ngày

**Case gốc:** 8. **Trang PDF:** 9.

### Hội thoại tái hiện

```text
T1: đi hà nội 3 ngày
A1: Hỏi ngày khởi hành, số người và ngân sách.
T2: đi PQ 3 ngày
```

### Lỗi quan sát trong nguồn

Agent đổi thành Phú Quốc và gợi ý kế hoạch ngay, dù chưa có ngày khởi hành.

### Tiêu chí đạt đề xuất

- [ ] Ghi nhận đổi điểm đến thành Phú Quốc, giữ thời lượng 3 ngày.
- [ ] Tiếp tục hỏi ngày khởi hành còn thiếu.
- [ ] Không coi các thông tin chưa cung cấp là đã được xác nhận.
- [ ] Nếu đưa ý tưởng tham khảo, phải ghi rõ chưa phải lịch trình hoàn chỉnh đã kiểm tra theo ngày.

## TC-09 - Không tự sinh hoặc đảo ngày khởi hành

**Case gốc:** 9. **Trang PDF:** 10.

### Hội thoại tái hiện

```text
Bối cảnh: Agent đang hỏi ngày khởi hành và ngân sách cho chuyến đi Nha Trang; phần đầu hội thoại không hiển thị đầy đủ.
T1: ngày nào cũng được.
A1: Gợi ý ngày khởi hành 03/10/2026 và hỏi có phù hợp không.
T2: bao nhiêu người cũng được
A2: Báo ngày khởi hành “10/03/2026” không hợp lệ vì đã qua; gợi ý “03/10/2026”.
```

### Lỗi quan sát trong nguồn

Agent trả lời ngày 10/03 dù hội thoại không đề cập đến ngày đó. Trong ảnh, ngày đề xuất 03/10/2026 bị chuyển thành 10/03/2026 ở lượt sau.

### Tiêu chí đạt đề xuất

- [ ] Không tạo giá trị 10/03/2026 từ đề xuất 03/10/2026.
- [ ] Giữ phân biệt ngày agent đề xuất và ngày người dùng xác nhận.
- [ ] T2 không phải xác nhận hay thay đổi ngày.
- [ ] Không báo lỗi quá khứ cho một ngày không có nguồn trong hội thoại.
- [ ] Khi chạy test, cố định ngày hiện tại và múi giờ; tránh kết quả thay đổi theo ngày chạy.

## Chuẩn bị chạy kiểm thử

- Reset hội thoại giữa các case; giữ state giữa các lượt trong cùng case.
- Cố định ngày hiện tại, múi giờ và dữ liệu/tool trả về. Ngày cụ thể trong PDF là dữ liệu test lịch sử, không đổi tự động thành ngày hiện tại.
- Case 1: cần chốt cách suy ra năm cho “14/10” và “15/10”; năm 2026 là ứng viên theo ngày ban đầu, chưa phải quy tắc được nguồn xác nhận.
- Case 2: kiểm thử cả lời trả lời, giá trị form và trạng thái xác nhận.
- Case 3: thiết lập fixture không tìm được lịch trình; PDF không cung cấp nguyên nhân kỹ thuật cụ thể. Giữ nguyên “1 ngày 2 đêm” từ nguồn và làm rõ nếu hệ thống yêu cầu.
- Case 9: cố định ngày hiện tại trước hoặc bằng 03/10/2026 khi tái hiện lỗi đảo ngày; nội dung đang gõ “bao nhiêu tiền cũng được” trong ảnh chưa được gửi, không đưa vào input.
- Chấm theo hành vi và state sau từng lượt; lưu actual response, state, tool calls và kết quả pass/fail.

## Phụ lục - Văn bản trích xuất từ PDF

Phần dưới giữ nội dung văn bản trích xuất, gồm lỗi chính tả và cách đánh số của nguồn. Nội dung trong ảnh đã được đưa vào các case phía trên theo phần đọc được.

```text
Tx: chính là lượt chat của người dùng thứ x
Ax: chính là lượt chat của trợ lý thứ x

case 1:

T1: Lên lịch trình 1 ngày tại Hà Nội, bắt đầu từ ngày 2026-10-02, cho 2 người lớn, ngân
sách khoảng 1 triệu.
T2: Đổi ngày
T3: Ngày 14 tháng 10
T4: À nhầm ngày 15 tháng 10
Sometimes: agent không ghi nhận ngày cũng cấp ở T3 và vẫn hỏi lại đổi ngày nào
Current Issues: Ở t4 agent không đổi ngày mà vẫn hỏi lại. Câu trả lời ngắn "Lịch trình
đã được hoàn tất." và thiếu diễn giải.
-> Cần diễn giải như sau " Mình ghi nhận đổi ngày đi thành x tháng x. Lịch trình mình gợi
ý như sau"

Case 2: form cần hiển thị giá trị mặc định. Agent gợi ý Đà nẵng nhưng form lại chưa
select đà nẵng.

Case 3 chưa tìm được lịch trình , agent dùng -> phải giải thích tại sao nữa và suggest
người dùng nên đổi sang cái gì khác, ngày khác chẳng hạn.

case 4 khi người dùng đổi rồi lại đổi ý không đổi nữa -> agent cần hỏi lại vẫn đi hà nội
chứ.

case 5: Người dùng bảo đổi điểm đến nhưng agent không hỏi lại là đổi chỗ nào mà
lập kế hoạch luôn.


Case 6: Agent nhần biển thành điểm đến và bảo ko nằm trong địa điểm hỗ trợ
T1 đi hà nội

A1 Số ngày chuyến đi Hà Nội là một điểm đến tuyệt vời! Để giúp bạn lên kế hoạch tốt hơn,
mình cần biết bạn dự định ở lại bao nhiêu ngày. Bạn có thể cho mình biết số ngày cụ thể
không? Ví dụ như "3 ngày" nhé.
T2 3 ngày

A2 Cần thêm thông tin về chuyến đi Cảm ơn bạn đã cho biết thời gian ở lại là 3 ngày! Bây
giờ, mình cần biết ngày khởi hành, số lượng người lớn và trẻ em trong đoàn, cũng như
ngân sách tổng cho chuyến đi. Bạn có thể cho mình biết những thông tin này không? Nếu
chưa quyết định được, bạn có thể bỏ qua những phần không chắc chắn.
T3 doi diem di

A3 Đổi điểm đến Bạn đã chọn Hà Nội là điểm đến, nhưng có vẻ như bạn muốn đổi. Bạn có
thể xác nhận lại điểm đến và số ngày không? Nếu bạn vẫn muốn đi Hà Nội trong 3 ngày,
hãy cho mình biết nhé!
T4 không đổi nữa

A4 Khám phá Hà Nội trong 3 ngày Mình đã lên kế hoạch cho bạn một chuyến đi 3 ngày tại
Hà Nội, nơi bạn sẽ khám phá những điểm đến thú vị và tận hưởng không gian văn hóa đặc
sắc. Nơi ....
T5 mình muốn đi biển cơ

A5 Điểm đến không hỗ trợ Mình thấy bạn muốn đi biển, nhưng hiện tại mình chỉ hỗ trợ lên
kế hoạch cho các chuyến đi trong nước, như Hà Nội, Đà Nẵng, Nha Trang và nhiều nơi
khác. Bạn có muốn chọn một trong những điểm đến này không? Nếu có, hãy cho mình biết
nhé!
T6 biển hà nội

A7 Điền nhanh thông tin chuyến đi Mình thấy bạn muốn đi biển, nhưng hiện tại mình chỉ hỗ
trợ lên kế hoạch cho các chuyến đi trong nước. Bạn có thể chọn một trong những điểm đến
như Đà Nẵng hoặc Nha Trang. Mình đã chuẩn bị một mẫu thông tin để bạn điền, bạn có thể
điều chỉnh và xác nhận nhé!

T8
biển hà nội


A9 Điền nhanh thông tin chuyến đi Mình thấy bạn muốn đi biển, nhưng....

case 7 Agent chọn đà nẵng khi người dùng chưa bảo đi đà nẵng

Case 8 Người dùng chỉ mới cung cấp địa điểm và thời lượng đi chưa cung cấp ngày.
Lượt 2 người dùng lại tiếp tục nhắn thiếu thông tin nhưng agent đã gợi ý kế hoạch rồi

case 9 agent trả lời ngày 10/03 trong khi hội thoại không hề đề cập tới
```

## TC-11 - Lịch không lặp một nơi

**Nguồn:** trace LangSmith 08/10/2026 (không có trong PDF). Phục vụ AC-AGT-04 (node `filter`, chốt 2026-10-08).

### Hội thoại tái hiện

```text
T1: Lên lịch trình 3 ngày tại Phú Quốc, bắt đầu từ ngày 2026-10-08, cho 2 người lớn, đi từ trung quoc.
A1: Hỏi ngân sách (hội thoại gốc đã trả lời ở lượt trước).
T2: Chưa có ngân sách, cứ lên lịch giúp mình.
```

### Lỗi quan sát trong nguồn

Lịch có "hòn Thơm", "Sun World Hòn Thơm", "Cáp Treo Hòn Thơm" (cùng chuyến cáp treo ra đảo) và hai vé "[Grand World Phú
Quốc] - Vé đi thuyền Venice (Water Taxi)" khác mã, cùng tên.

### Tiêu chí đạt đề xuất

- [ ] Lịch không có hai điểm tham quan cùng một nơi hoặc cùng một trải nghiệm.
- [ ] Mã bị bỏ có cảnh báo `PRODUCT_DROPPED_DUPLICATE` và hiện ở mục "Đã loại" của eval.
