# Trợ lý gợi ý và khám phá trước, hỏi người dùng có muốn lập lịch rồi mới hỏi thông tin chuyến

- Ngày: 2026-10-09
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng (source 2026-10-10; PRD 2026-10-11)
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-10. Người dùng giao agent tự quyết các điểm còn mở và bỏ bước cập nhật PRD
  trước khi sửa source (`history/2026-10-10-tro-ly-kham-pha-truoc-khi-lap-lich.md`). Cập nhật PRD: agent chốt theo uỷ
  quyền của Nguyễn Minh Nhật ("về phần technical PRD mình cho bạn quyết định mọi thứ"), 2026-10-11.
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-01, thêm FR-AGT-06), §3 (AC-AGT-01, thêm AC-AGT-06,
  AC-AGT-07);
  `docs/prd/architecture.md` §3; `docs/prd/user-flow.md` §3.2, §4.2
- Mã FR/NFR: FR-AGT-01, FR-AGT-04, NFR-REL-01, NFR-PERF-02; mới — cần cấp mã: FR-AGT-06, AC-AGT-06, AC-AGT-07

## Lý do

Hiện tại câu nào nhắc tới chuyến đi cũng bị coi là yêu cầu lập lịch:

- "Hà Nội" → trợ lý hỏi số ngày.
- Hỏi tiếp "Hà Nội có gì?" → câu có điểm đến nên vẫn là yêu cầu lập lịch. Vẫn thiếu số ngày, ngày đi, số người, nên trợ lý
  hiện form, và form hiện lại ở mọi lượt cho tới khi đủ (AC-AGT-01).
- "Xin chào" → trợ lý chào lại nhưng không gợi ý gì.
- "ok" khi chuyến còn thiếu thông tin → bị coi là câu trả lời không thêm được gì, nên hiện form.
- "Xin chào" rồi "không biết" → cũng bị coi như vậy, nên form hiện ngay từ lượt thứ hai, dù người dùng chưa nói muốn đi
  đâu.
- Câu hỏi cách dùng như "k bit dat phong sao" (không biết đặt phòng sao) có thể bị xếp vào `out_of_scope` (prompt đang
  ghi "booking, payment or cart actions") và bị từ chối 400. Chưa kiểm bằng trace.

Lý do trong code: bước phân luồng chỉ có bốn nhãn `travel`, `vague`, `conversation`, `out_of_scope`
(`src/backend/app/agents/steps/prompts.py`), và mọi câu `travel` đều đi luồng thu thập thông tin lập lịch. Không có chỗ
cho việc trả lời câu hỏi về một điểm đến, cũng không có bước hỏi người dùng có muốn lập lịch hay không.

Người dùng muốn trợ lý thân thiện, thu thập nhu cầu dần và không ép:

1. **Chưa có điểm đến:** trò chuyện. Gợi ý nhẹ rằng cho biết nơi muốn đến (ví dụ Hà Nội, TP. Hồ Chí Minh) thì trợ lý kể
   được ở đó có gì. Người dùng chưa nói thì vẫn trò chuyện tiếp, không hỏi thông tin chuyến.
2. **Có điểm đến:** giới thiệu điểm tham quan và khách sạn nổi bật ở đó, rồi hỏi người dùng có muốn lập lịch không.
3. **Người dùng đồng ý** ("ok", "được"...) thì mới hỏi số ngày, ngày đi, số người, ngân sách, nơi đi và sở thích (hồ
   bơi, phù hợp trẻ nhỏ...), rồi hiện form như hiện nay.

## Phạm vi

| Giai đoạn | Khi nào | Trợ lý làm gì | Hỏi thông tin chuyến / form |
|---|---|---|---|
| Trò chuyện | Chào hỏi, cảm ơn, "muốn đi chơi", "chưa biết đi đâu" mà chưa có điểm đến | Trả lời thân thiện, mời nói nơi muốn đến, gợi ý 3 điểm đến của catalog, mỗi điểm một nút | Không |
| Khám phá | Câu nêu hoặc hỏi về một điểm đến ("Hà Nội", "Hà Nội có gì?", "khách sạn nào có hồ bơi?"), hoặc chỉ nêu thông tin chuyến ("Hà Nội 3 ngày") khi người dùng chưa đồng ý lập lịch | Lời giới thiệu ngắn kèm thẻ điểm tham quan, khách sạn thật từ Search; hỏi "Bạn có muốn mình lập lịch … không?". Thông tin chuyến đã nêu được ghi lại | Không |
| Lập lịch | Người dùng đồng ý lời mời ("ok", "được", "có", hoặc trả lời lời mời bằng thông tin chuyến); hoặc tự yêu cầu ("lập lịch Hà Nội 3 ngày cho mình"); hoặc bấm nút lập lịch, xác nhận form | Như AC-AGT-01 hiện nay, hỏi thêm sở thích | Có, như hiện nay |

Ngoài phạm vi, để đề xuất sau:

- Hỏi giá vé máy bay khi chưa lập lịch. Thẻ vé cần ngày bay và các trường riêng của chuyến bay.
- Gợi ý điểm đến theo lịch sử từng người.
- Hỏi đáp và đổi vé, khách sạn sau khi có lịch: đã có đề xuất riêng `2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md`.
- Đổi framework agent hoặc tách agent thành nhiều service (A2A). Đề xuất này làm trong LangGraph hiện có.

## Nội dung đề xuất

### 1. `requirements.md` §1.4, FR-AGT-01

Hiện tại:

> Trợ lý có khả năng duy trì ngữ cảnh trò chuyện, làm rõ nhu cầu du lịch (thời gian, địa điểm, nơi đi, số người, ngân
> sách, phong cách du lịch).

Thay bằng:

> Trợ lý có khả năng duy trì ngữ cảnh trò chuyện và thu thập nhu cầu du lịch dần qua hội thoại, không ép người dùng
> cung cấp thông tin. Chưa có điểm đến thì trợ lý mời người dùng nói nơi muốn đến và gợi ý điểm đến; có điểm đến thì
> giới thiệu điểm tham quan, khách sạn nổi bật ở đó và hỏi người dùng có muốn lập lịch không (FR-AGT-06). Chỉ khi người
> dùng đồng ý hoặc tự yêu cầu lập lịch, trợ lý mới làm rõ thời gian, nơi đi, số người, ngân sách và sở thích (AC-AGT-01).

Phần còn lại của FR-AGT-01 (lịch sử hội thoại, khách sạn theo số phòng) giữ nguyên.

### 2. `requirements.md` §1.4, thêm FR-AGT-06

> **FR-AGT-06 (Gợi ý và khám phá trước khi lập lịch):** Trước khi người dùng đồng ý lập lịch, trợ lý trò chuyện, gợi ý
> điểm đến có trong catalog và trả lời câu hỏi về một điểm đến bằng thẻ điểm tham quan, khách sạn thật lấy từ Search.
> Trợ lý hỏi người dùng có muốn lập lịch không, và không hỏi thông tin chuyến hay hiện form cho tới khi người dùng đồng
> ý (AC-AGT-06).

### 3. `requirements.md` §3, AC-AGT-01

Thêm vào đầu cột "Kết quả mong đợi":

> Câu này là yêu cầu lập lịch người dùng tự đưa ra, nên trợ lý không hỏi lại có muốn lập lịch không (AC-AGT-06).

Câu hỏi gộp, hiện tại:

> Trợ lý hỏi gộp một câu, một lần, những gì còn thiếu trong ngày đi, số người, ngân sách và nơi đi (không tự đoán ngày).

Thay bằng:

> Trợ lý hỏi gộp một câu, một lần, những gì còn thiếu trong ngày đi, số người, ngân sách, nơi đi và sở thích (ví dụ
> khách sạn có hồ bơi, phù hợp trẻ nhỏ) (không tự đoán ngày).

Danh sách ô của form, hiện tại:

> (điểm đến, số ngày, ngày khởi hành, số người, ngân sách, nơi đi)

Thay bằng:

> (điểm đến, số ngày, ngày khởi hành, số người, ngân sách, nơi đi, sở thích — chọn nhiều, không bắt buộc)

Thêm vào cuối cột "Kết quả mong đợi":

> Sở thích khách sạn chọn trong form hoặc nói trong câu (hồ bơi, phù hợp trẻ nhỏ, view biển, bữa sáng miễn phí, spa) làm
> khách sạn có ghi nhận tiện ích đó được ưu tiên khi tìm. Khách sạn thiếu dữ liệu tiện ích không bị loại. Người dùng nói
> rõ là bắt buộc thì theo luật điều kiện bắt buộc hiện có.

### 4. `requirements.md` §3, thêm AC-AGT-06

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| **AC-AGT-06** | Người dùng lần lượt nhắn *"xin chào"*, *"không biết"*, *"tuỳ bạn"*, *"Hà Nội có gì?"*, *"có khách sạn nào có hồ bơi không?"*, rồi *"ok"* sau khi trợ lý hỏi có muốn lập lịch không | **Trò chuyện:** chào hỏi, hoặc muốn đi chơi mà chưa có điểm đến, thì trợ lý trả lời thân thiện. Trợ lý mời người dùng nói nơi muốn đến và gợi ý 3 điểm đến có trong catalog, kèm một nút cho mỗi điểm. Người dùng chưa nói điểm đến thì trợ lý vẫn trò chuyện tiếp và có thể gợi ý theo loại nơi (biển, nơi mát…), chỉ nêu điểm đến trong catalog. Người dùng trả lời *"không biết"*, *"chưa biết"*, *"tuỳ bạn"* khi được mời nói điểm đến thì trợ lý không hỏi lại cùng một câu: lần đầu hỏi một câu dễ trả lời hơn về loại nơi (biển, nơi mát, thành phố), kèm một nút cho mỗi loại; lần thứ hai tự chọn một điểm đến trong catalog, giới thiệu luôn như lượt khám phá và nói rõ người dùng đổi được; từ lần thứ ba không hỏi tiếp, chỉ giữ nút gợi ý. Không hỏi số ngày, ngày đi, số người, không hiện form. **Khám phá:** câu nêu hoặc hỏi về một điểm đến thì trợ lý trả lời 2–4 câu giới thiệu. Kèm theo là thẻ sản phẩm thật lấy từ Search, nhóm theo loại: tối đa 4 điểm tham quan hoặc tour và 3 khách sạn của điểm đến đó; hỏi riêng một loại thì chỉ loại đó, tối đa 6. Tên sản phẩm trong câu là link tới sản phẩm có thẻ; giá là giá niêm yết hiện tại. Lượt khám phá đầu tiên của một điểm đến kết thúc bằng câu hỏi "Bạn có muốn mình lập lịch … không?" và nút đồng ý; các lượt khám phá sau chỉ giữ nút "Lập lịch …", không hỏi lại bằng câu, trừ khi người dùng vừa nêu thêm thông tin chuyến. Người dùng từ chối ("để sau", "chưa") hoặc trả lời "không biết", "chưa biết" thì trợ lý coi như để sau và không hỏi lại bằng câu cho tới khi người dùng nêu thông tin chuyến mới. Câu chỉ nêu thông tin chuyến khi chưa đồng ý lập lịch (*"Hà Nội 3 ngày"*) thì trợ lý ghi lại thông tin đó, trả lời như khám phá và hỏi *"Bạn có muốn mình lập lịch Hà Nội 3 ngày không?"*. Không hỏi thông tin chuyến, không hiện form; lượt này không tính vào số lần đã hỏi lại. Điểm đến ngoài catalog thì nói không có và gợi ý điểm đến trong catalog, như AC-AGT-01. Chưa có điểm đến thì điểm đến vừa nhắc được ghi cho chuyến; đang lập lịch cho nơi khác thì không đổi điểm đến của chuyến. Search không trả sản phẩm nào thì nói rõ và vẫn hỏi có muốn lập lịch không. **Đồng ý lập lịch:** khi trợ lý vừa hỏi có muốn lập lịch không, câu đồng ý ngắn (*"ok"*, *"được"*, *"có"*, *"lập đi"*) hoặc câu trả lời bằng thông tin chuyến (*"3 ngày thôi"*) là đồng ý. Câu tự yêu cầu lập lịch (*"lập lịch Hà Nội 3 ngày cho mình"*), bấm nút lập lịch, hoặc xác nhận form cũng là đồng ý. Sau khi đồng ý, trợ lý đi luồng AC-AGT-01 với thông tin đã ghi từ các lượt trước. Từ lúc đó, câu trả lời thông tin chuyến ở luồng lập lịch. Câu hỏi khám phá xen giữa vẫn được trả lời như trên, giữ nguyên thông tin đã thu, và có nút "Tiếp tục lập lịch" thay cho form. Câu "không biết", "tuỳ bạn" chỉ dẫn tới form sau khi người dùng đã đồng ý lập lịch. Mục tiêu thời gian phản hồi của lượt trò chuyện và khám phá: dưới 3 giây. |

### 5. `requirements.md` §3, thêm AC-AGT-07

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| **AC-AGT-07** | Câu trả lời ở giai đoạn trò chuyện và khám phá, kể cả khi người dùng nhắn khó hiểu (*"?"*, *"đi đâu mà vắng vắng, không xa lắm"*), khó tính (*"chán, đi rồi"*, *"khách sạn gì mà đắt thế"*), cộc lốc (*"hỏi lắm thế, cứ đưa đại đi"*) hoặc không quen công nghệ (*"toi muon di da lat ma k bit dat phong sao"*, *"cái bảng này điền sao"*) | **Nút gợi ý:** tối đa 3 nút, mỗi nút một hướng khác nhau: đi tiếp (ví dụ lập lịch), xem sâu một khía cạnh (khách sạn gần biển, chỗ chơi buổi tối), hoặc đổi hướng (nơi khác, kiểu chuyến khác). Không có hai nút cùng một mẫu câu (không để "Đà Nẵng có gì?" và "Hà Nội có gì?" cùng lúc). Không lặp nút của lượt trước, trừ nút lập lịch; nút này được viết lại theo thông tin mới nhất (ví dụ "Lên lịch Hà Nội, ở khách sạn có hồ bơi"). Câu trên nút viết như lời người dùng, ngắn, chỉ nêu điểm đến có trong catalog và sản phẩm có trong kết quả. **Thẻ:** mỗi thẻ đứng ngay sau câu đầu tiên nhắc tới sản phẩm đó, như lời diễn giải lịch trình (`user-flow.md` §4.2). Mỗi thẻ có một câu dẫn riêng nêu lý do bằng dữ liệu (giờ mở cửa, khoảng cách, giá, điểm đánh giá). Không liệt kê thẻ thành một khối không có câu dẫn. **Giọng điệu:** mỗi lượt hỏi tối đa một câu; không hỏi lại cùng một câu; nói thẳng điều không kiểm được từ dữ liệu (đông hay vắng, ngon hay không) rồi làm phần kiểm được; không bình luận thái độ người dùng. **Khó hiểu:** trợ lý nói gọn mình giúp được gì kèm một ví dụ, hoặc tách phần kiểm được ra và hỏi đúng một câu dễ trả lời. Tin rác vẫn đi luật tầng 1, nhưng câu cố định có kèm nút gợi ý. **Khó tính:** điểm đến hoặc sản phẩm bị chê không được gợi ý lại trong hội thoại. Gợi ý tiếp theo đổi hẳn một chiều (biển sang núi, đắt sang rẻ) và nêu chênh lệch bằng số. Trợ lý nói rõ đánh đổi, ví dụ chỗ rẻ là hostel, phòng ở chung. **Cộc lốc:** người dùng nhắn rất ngắn hoặc tỏ ra khó chịu thì trả lời tối đa 2 câu, không hỏi câu không bắt buộc. Đã đồng ý lập lịch mà không muốn trả lời câu hỏi thì hiện ngay form điền sẵn (AC-AGT-01), không hỏi thêm bằng câu chữ. Câu có tục tĩu xen nội dung thì trả lời phần nội dung, không nhắc tới tục tĩu; câu chỉ có tục tĩu thì vẫn từ chối như hiện nay. **Không quen công nghệ:** câu không dấu, viết tắt, sai chính tả được hiểu như câu có dấu. Trợ lý chỉ dẫn giao diện bằng tên nút người dùng nhìn thấy, mỗi lần một bước, không dùng từ kỹ thuật (form, chip, intent). Người dùng trả lời bằng chat ("thứ 7 này") thay cho điền form thì trợ lý tự điền giúp. Câu hỏi cách dùng ("đặt phòng sao", "trả tiền thế nào") là trong phạm vi: trợ lý chỉ nút cần bấm; chỉ từ chối khi người dùng yêu cầu trợ lý tự đặt chỗ, thanh toán hay sửa giỏ hàng. |

### 6. `architecture.md` §3

Sơ đồ trạng thái. Dòng hiện tại:

```text
ClassifyTurn --> Converse: Trò chuyện / ngoài phạm vi (đặt chỗ, chèn lệnh) / tin nhắn rác, tục tĩu (luật tất định, không gọi LLM)
ClassifyTurn --> AnalyzeIntent: Yêu cầu du lịch
```

Thay bằng:

```text
ClassifyTurn --> Converse: Trò chuyện (chưa có điểm đến: mời nói điểm đến, gợi ý 3 điểm, không ép) / ngoài phạm vi (đặt chỗ, chèn lệnh) / tin nhắn rác, tục tĩu (luật tất định, không gọi LLM)
ClassifyTurn --> Explore: Nêu hoặc hỏi về một điểm đến, hoặc nêu thông tin chuyến khi chưa đồng ý lập lịch
Explore --> [*]: Thẻ điểm tham quan, khách sạn thật từ Search + hỏi có muốn lập lịch không; không hỏi thông tin chuyến
ClassifyTurn --> AnalyzeIntent: Đồng ý lời mời lập lịch / tự yêu cầu lập lịch / bấm nút lập lịch / xác nhận form
```

Gạch đầu dòng "Không suy đoán dữ liệu sản phẩm": thêm "và câu trả lời khám phá (FR-AGT-06) chỉ nêu sản phẩm có trong
kết quả Search của chính lượt đó" vào cuối.

### 7. `user-flow.md` §3.2

Hai dòng hiện tại:

```text
    H -->|Không| B[Nhập yêu cầu lịch trình hoặc chọn gợi ý]
    B --> C[Backend trích xuất Intent: Điểm đến, Thời gian, Ngân sách]
```

Thay bằng:

```text
    H -->|Không| B[Nhập câu bất kỳ hoặc chọn gợi ý]
    B --> K{Đã đồng ý lập lịch?}
    K -->|Chưa, chưa có điểm đến| K1[Trò chuyện, mời nói điểm đến, gợi ý 3 điểm]
    K -->|Chưa, có điểm đến| K2[Thẻ điểm tham quan, khách sạn + hỏi: bạn có muốn lập lịch không?]
    K1 --> B
    K2 --> B
    K -->|Đồng ý hoặc tự yêu cầu| C[Backend trích xuất Intent: Điểm đến, Thời gian, Ngân sách, Sở thích]
```

### 8. `user-flow.md` §4.2

Mục 1 "Thẻ trong khung chat", câu "Dữ liệu thẻ lấy từ `itinerary`/`searchResults` của response, không từ chữ của LLM":
thêm "kể cả câu trả lời khám phá (AC-AGT-06)".

Ghi chú "Form gợi ý thông tin chuyến đi": thêm ô "sở thích — chọn nhiều, không bắt buộc" sau ô nơi đi.

## Điểm cần người chốt quyết định

1. **Thế nào là đồng ý lập lịch.**
   - Đề xuất: khi trợ lý vừa hỏi có muốn lập lịch không, câu đồng ý ngắn ("ok", "được", "có", "lập đi") hoặc câu trả lời
     bằng thông tin chuyến ("3 ngày thôi") đều là đồng ý. Câu tự yêu cầu lập lịch cũng là đồng ý. Câu đồng ý ngắn được
     nhận bằng luật; LLM chỉ dùng cho cách nói khác.
   - Phương án chặt hơn: chỉ nhận câu đồng ý và câu tự yêu cầu; trả lời lời mời bằng "3 ngày thôi" thì ghi lại rồi hỏi
     lại lần nữa. Đổi lại người dùng phải nhắn thêm một lượt.
2. **Hỏi "có muốn lập lịch không" bao nhiêu lần.**
   - Đề xuất: hỏi bằng câu ở lượt khám phá đầu tiên của mỗi điểm đến, và khi người dùng vừa nêu thêm thông tin chuyến.
     Các lượt khác chỉ giữ nút "Lập lịch …".
   - Phương án khác: hỏi ở mọi lượt khám phá. Dễ làm hơn nhưng lặp, dễ gây khó chịu.
3. **Kiểu response của lượt khám phá.**
   - Đề xuất: `NEEDS_CLARIFICATION` có thêm trường tuỳ chọn `searchResults` (contract 1.24.0, tương thích ngược). Nút
     gợi ý dùng `suggestions` đã có, Web đã hiển thị nút này cho `NEEDS_CLARIFICATION`. Web chỉ cần hiển thị thẻ
     `searchResults` cho thêm status này.
   - Phương án khác: thêm status mới `EXPLORE`. Đúng nghĩa hơn, nhưng Web, lưu hội thoại và bộ chấm golden đều phải xử
     lý thêm một status.
4. **Sở thích khách sạn là ưu tiên hay bắt buộc.**
   - Đề xuất: ưu tiên. Dữ liệu tiện ích còn thiếu nhiều (`familyFriendly` có ở 35% sản phẩm,
     `docs/spec/data-collection/schema.md`), nên bắt buộc sẽ loại oan nhiều khách sạn.
   - "Bắt buộc có hồ bơi" vẫn đi luật điều kiện bắt buộc hiện có.
5. **Ai viết lời giới thiệu ở lượt khám phá.**
   - Đề xuất: LLM viết 2–4 câu, chỉ được nhắc sản phẩm có trong kết quả Search của lượt đó, và được kiểm như lời diễn
     giải lịch trình.
   - Phương án khác: code viết theo mẫu. Nhanh hơn nhưng cứng, đi ngược mục tiêu thân thiện.
6. **Trả lời "không biết" khi chưa có điểm đến.**
   - Đề xuất ba bậc: hỏi loại nơi kèm nút → tự chọn một điểm đến và giới thiệu → ngừng hỏi, giữ nút. Điểm đến tự chọn là
     điểm có nhiều sản phẩm nhất (hiện là Đà Nẵng), cùng cách chọn với ô điểm đến của form hiện nay.
   - Phương án khác: bỏ bậc hỏi loại nơi, tự chọn ngay từ lần đầu. Nhanh hơn nhưng ít hỏi ý người dùng.
   - Chọn theo lịch sử của người dùng đã đăng nhập: ngoài phạm vi đề xuất này.
7. **Ô sở thích trong form.**
   - Đề xuất 5 lựa chọn có dữ liệu: hồ bơi, phù hợp trẻ nhỏ, view biển, bữa sáng miễn phí, spa.
   - Không đưa `kidsClub`, `kidsPool` vì chưa có dữ liệu.
8. **Ai viết nút gợi ý.**
   - Đề xuất: LLM đề xuất ba nút, mỗi nút gắn một hướng (đi tiếp, xem sâu, đổi hướng). Code kiểm từng nút: mỗi hướng một
     nút, không trùng mẫu câu, không lặp nút lượt trước, điểm đến và sản phẩm phải có trong catalog hoặc kết quả. Nút
     không đạt thì code thay bằng nút theo mẫu.
   - Phương án khác: code dựng nút hoàn toàn theo mẫu. Chắc chắn đúng nhưng dễ lặp câu chữ, đúng điều người dùng muốn
     tránh.

## Liên quan tới đề xuất đang chờ

- `2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md`: cũng thêm một nhánh từ `ClassifyTurn`. Khi đã có lịch, câu hỏi về vé
  hoặc khách sạn của lịch đó đi nhánh hỏi đáp/đổi; câu hỏi khác về điểm đến đi nhánh khám phá. Hai đề xuất dùng mã AC
  khác nhau (AC-AGT-05, AC-AGT-06).
- `2026-10-05-go-golden-dataset-cu.md`: các test case hiện mong trợ lý hỏi số ngày khi câu chỉ có điểm đến sẽ phải sửa
  thành khám phá kèm lời mời lập lịch. Ví dụ hội thoại "Đi Đà Nẵng → 3 ngày → không biết":
  - "Đi Đà Nẵng" → khám phá, hỏi có muốn lập lịch không;
  - "3 ngày" → trả lời lời mời bằng thông tin chuyến, tính là đồng ý → hỏi gộp;
  - "không biết" → form, như hiện nay.

## Thay đổi source sau khi chốt

- Contract (`src/shared/contracts/`), lên 1.24.0:
  - `schemas/itinerary-agent.yaml`: `ItineraryNeedsClarification` thêm `searchResults` tuỳ chọn và mở rộng mô tả
    `suggestions`.
  - `clarificationForm.fields` thêm `interests`, thêm `interestOptions`.
  - Mock `src/shared/mocks/itinerary-agent/` thêm response khám phá.
  - Chạy `validate_contract.py`.
- Backend agent (`src/backend/app/agents/`), vẫn trong LangGraph:
  - `steps/prompts.py`, `models.py`:
    - nhãn phân luồng `explore`, prompt viết lời khám phá;
    - `CONVERSATION_PROMPT` mời nói điểm đến, không ép;
    - luật giọng điệu của AC-AGT-07;
    - `CLASSIFY_PROMPT`: câu hỏi cách đặt chỗ, thanh toán không còn là `out_of_scope`.
  - `steps/classification.py`:
    - luật tất định nhận câu đồng ý khi vừa có lời mời;
    - lượt khám phá không tăng `clarification_rounds`;
    - `vague` chỉ dẫn tới form sau khi đã đồng ý. Trước đó, `vague` đi bậc gợi ý điểm đến, có bộ đếm riêng số lần "không
      biết".
  - `graph.py`, `routing.py`, `nodes.py`, `state.py`:
    - node `explore` (`classify → explore → finalize`);
    - state ghi lời mời đang chờ (điểm đến, thông tin chuyến đã nêu) và cờ đã đồng ý lập lịch;
    - cập nhật test kiến trúc đếm node.
  - `steps/explore.py` (mới): gọi Search theo loại, dựng `searchResults`, câu hỏi mời lập lịch và nút gợi ý; kiểm nút
    theo AC-AGT-07.
  - `state.py`: thêm danh sách điểm đến và sản phẩm bị người dùng chê trong hội thoại.
  - `steps/messages.py`: câu cố định cho tin rác có kèm nút gợi ý.
  - `steps/validation.py`: kiểm grounding của lời khám phá.
  - `steps/conversation.py`: nút gợi ý 3 điểm đến khi chào hỏi.
  - `steps/tool_planning.py`: sở thích vào câu tìm khách sạn.
- Frontend (`src/frontend/src/features/itinerary/widget/`):
  - Hiển thị thẻ `searchResults` cho `NEEDS_CLARIFICATION`, xen giữa câu dẫn bằng `WidgetNarration` đang dùng cho lịch
    trình (thẻ ngay sau dòng đầu tiên nhắc sản phẩm).
  - Form thêm ô sở thích chọn nhiều, ghép vào câu xác nhận.
- Spec:
  - `docs/spec/agent/nghiep-vu/hieu-y-dinh-va-hoi-lai.md`, `docs/spec/agent/langgraph-nodes.md`,
    `docs/spec/agent/state-fields.md`.
  - `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`.
- Test:
  - Unit cho luật đồng ý lập lịch và node `explore`.
  - Golden case cho:
    - các câu ở AC-AGT-06;
    - "xin chào" → "không biết" → "tuỳ bạn" → "không biết" (ba bậc, không form);
    - "Hà Nội 3 ngày" khi chưa đồng ý (hỏi lại, không form);
    - "lập lịch Hà Nội 3 ngày cho mình" (vào luồng lập lịch ngay);
    - "để sau" (không hỏi thông tin chuyến);
    - câu hỏi khám phá xen giữa lúc đang hiện form;
    - các câu khó ở AC-AGT-07: kiểm nút không trùng mẫu câu, thẻ có câu dẫn, tối đa một câu hỏi mỗi lượt, không gợi ý
      lại nơi bị chê, câu trả lời tối đa 2 câu khi người dùng cộc lốc.

## Quyết định khi áp dụng (2026-10-10)

Người dùng giao agent tự quyết, với yêu cầu "linh hoạt, không cứng". Khác với đề xuất ở trên:

- **Đồng ý lập lịch:** ngoài các cách ở điểm chốt 1, câu có thông tin chuyến ngoài điểm đến ("Hà Nội 3 ngày", "đi 3 ngày", "2
  người") cũng coi là đồng ý, không hỏi lại "có muốn lập lịch không". Chỉ nêu hoặc hỏi về điểm đến thì khám phá rồi mời.
- **Vừa đồng ý bằng "ok":** hỏi gộp một câu trước (AC-AGT-01), chưa đưa form ngay.
- **Số thẻ:** tối đa 4 mỗi lượt (2 điểm tham quan và 2 khách sạn; hỏi riêng chỗ ở thì 4 khách sạn), không phải 4 + 3.
- **Ngoài phạm vi:** câu trả lời 200 kèm nút thay cho lỗi 400; chỉ đầu vào bị guardrail chặn còn là lỗi 400.
- **Nút gợi ý:** tối đa 3, ít nhất hai hướng, luôn có một nút đi tiếp khi chưa nút nào xin lập lịch (nới điểm chốt 8: không bắt
  buộc đủ ba hướng).
- **Lý do của thẻ:** do luật tính trên toàn bộ kết quả Search; LLM chỉ viết câu, số điền bằng placeholder.

- **Câu "cứ chọn đại", "tuỳ bạn":** nhận bằng luật, trợ lý tự chọn và khám phá ngay (bậc 2), vì LLM hay xếp câu này là trò
  chuyện.
- **Đổi nơi ngay sau lời mời** ("Thôi, Hà Nội thì sao?") không phải đồng ý; chỉ "ok"/"được"… hoặc câu có thông tin chuyến mới
  là đồng ý.
- **Sở thích (điểm chốt 4, 7):** ưu tiên, nằm trong `intent.interests`, vào câu tìm khách sạn và lọc mềm (chỉ bỏ khách sạn
  không hợp khi còn ít nhất 3 khách sạn hợp). Năm lựa chọn: Hồ bơi, Phù hợp trẻ nhỏ, View biển, Có bữa sáng (dữ liệu không
  nói miễn phí nên không hứa "miễn phí"), Spa. Không ẩn lựa chọn theo điểm đến.
- **Nhớ nơi bị chê:** có, theo luật (tên nơi đã gợi ý + từ chê, hoặc "chỗ khác đi"); hỏi lại đúng tên nơi đó là đổi ý.
- **Ngày không có chuyến bay** (kịch bản bản 5, cảnh 10): câu cảnh báo vé nêu tối đa 2 ngày gần nhất có vé, giữ số ngày.

- **Đổi khách sạn, chuyến bay khi chưa nói rõ** (kịch bản bản 5; trước đây đề xuất hỏi đáp sau lịch ghi "tự lấy phương án
  kế tiếp"): "đổi khách sạn" trơn thì hỏi lại kèm các phương án đã tính sẵn (nút "Lấy phương án N" đổi ngay); có hướng ("rẻ
  hơn") hoặc "bạn chọn giúp" thì tự đổi như trước. "Đổi chuyến bay" thì liệt kê chuyến khác cùng ngày, mỗi chuyến một nút;
  "chuyến về muộn hơn/sớm hơn/rẻ hơn" thì chọn luôn. Luật tất định, không gọi LLM để hỏi.

- **Lời dẫn khám phá** (góp ý người dùng 2026-10-10): câu chat nói nơi đó là gì, có gì đáng xem, hợp với ai (lấy từ mô tả
  và tags của catalog). Điểm, lượt đánh giá, giờ mở cửa và giá không nằm trong câu chat (thẻ và khung chi tiết bên phải đã
  hiện); giờ mở cửa chỉ nêu khi người dùng hỏi đúng nơi đó, giá chỉ nêu khi người dùng hỏi giá.
- **Hỏi giá vé trước khi lập lịch** (kịch bản bản 5, cảnh 6, người dùng chốt 2026-10-10): thiếu nơi đi hoặc điểm đến thì
  hỏi lại (kèm nút những nơi có chuyến); đủ thì báo vé một chiều rẻ nhất trong 30 ngày tới (hoặc đúng ngày đi nếu đã có)
  và vài ngày rẻ khác, lấy từ chuyến bay của catalog. Luật tất định, không gọi LLM.
- **Ngôn ngữ:** chỉ tiếng Việt ở đợt này (người dùng chốt 2026-10-10), chưa trả lời theo ngôn ngữ người dùng.

Chưa làm: ẩn lựa chọn sở thích theo dữ liệu từng điểm đến, cẩm nang điểm đến (cần DDL), đổi riêng một chiều của vé khứ hồi,
cập nhật PRD (người dùng cho bỏ qua).

## Áp dụng vào PRD (2026-10-11)

PRD được cập nhật theo nội dung đề xuất ở trên, sửa theo mục "Quyết định khi áp dụng" và theo source đang chạy:

- `requirements.md` §1.4: FR-AGT-01 thay câu đầu; thêm FR-AGT-06.
- `requirements.md` §3: AC-AGT-01 (không hỏi lại có muốn lập lịch, hỏi gộp có sở thích, ô sở thích trong form, sở thích là
  ưu tiên và lọc mềm khi còn ít nhất 3 khách sạn hợp); thêm AC-AGT-06 và AC-AGT-07.
- Khác với bản ở mục "Nội dung đề xuất": tối đa 4 thẻ mỗi lượt (2 + 2, hỏi riêng chỗ ở thì 4 khách sạn); câu có thông tin
  chuyến ngoài điểm đến là đồng ý; đổi nơi ngay sau lời mời không phải đồng ý; vừa "ok" thì hỏi gộp trước, chưa form; "cứ
  chọn đại", "tuỳ bạn" thì trợ lý tự chọn ngay; câu chat không nêu điểm, lượt đánh giá, giờ, giá (trừ khi người dùng hỏi);
  hỏi về chính một nơi chỉ trả lời nơi đó; nút tối đa 3, ít nhất hai hướng; ngoài phạm vi là câu trả lời 200 kèm nút, chỉ
  đầu vào bị luật chặn mới là lỗi 400.
- `architecture.md` §3: sơ đồ có nhánh `Explore` và luật đồng ý; gạch đầu dòng grounding thêm câu trả lời khám phá; response
  `NEEDS_CLARIFICATION` có `searchResults` (1.24.0).
- `user-flow.md` §3.2: sơ đồ có bước "Đã đồng ý lập lịch?"; §4.2: thẻ của câu trả lời khám phá, ô sở thích của form, form chỉ
  sau khi đồng ý.
- Hỏi giá vé trước khi lập lịch (mục "Quyết định khi áp dụng") được ghi vào PRD qua đề xuất
  `2026-10-11-tu-van-ve-may-bay-va-sua-loi-chat-thu-lan-3.md` (FR-AGT-07, AC-AGT-08). Đổi khách sạn, chuyến bay khi chưa nói
  rõ được ghi vào AC-AGT-05 qua đề xuất `2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md`.
- Không đưa vào PRD: chỉ tiếng Việt ở đợt này (quyết định tạm, không phải yêu cầu sản phẩm); các việc ở dòng "Chưa làm".
