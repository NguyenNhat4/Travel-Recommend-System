# Hỏi đáp và đổi vé, khách sạn sau khi có lịch, không lập lịch lại

- Ngày: 2026-10-09
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng một phần (2026-10-11); phần còn lại từ chối — xem mục "Quyết định chốt (2026-10-11)"
- Chốt bởi / ngày: phần hỏi giá vé — agent chốt theo uỷ quyền của Nguyễn Minh Nhật ("cho bạn quyền tự chốt"), 2026-10-10;
  phần còn lại — agent chốt theo uỷ quyền của Nguyễn Minh Nhật ("về phần technical PRD mình cho bạn quyết định mọi thứ"),
  2026-10-11
- Đã áp dụng một phần (`history/2026-10-10-cau-hoi-ve-hoi-lai-va-nho-ngu-canh.md`): câu hỏi giá vé sau khi có lịch đi nhánh
  giá vé bằng luật (tra lại chuyến theo tuyến của chuyến, không dùng dữ liệu đã lưu), trả `NEEDS_CLARIFICATION`, lịch giữ
  nguyên; không có node `follow_up`, không lưu thêm dữ liệu đã tra. Câu đổi vé, khách sạn vẫn theo luồng hiện có.
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-05), §3 (AC-AGT-02, thêm AC-AGT-05); `docs/prd/architecture.md` §3
- Mã FR/NFR: FR-AGT-01, FR-AGT-05, FR-AGT-04, NFR-PERF-02; AC mới AC-AGT-05

## Lý do

Sau khi có lịch, người dùng hay hỏi tiếp về chính lịch đó: "vé Phú Quốc → Hà Nội chuyến nào rẻ nhất?", "đổi sang chuyến
bay chiều", "đổi khách sạn khác". Hiện tại:

- Câu hỏi về vé không trả lời được. Hệ thống chỉ lưu lại vé đã chọn, không lưu các chuyến đã tra.
- Đổi vé cụ thể qua chat chưa làm được (`ve-may-bay.md`, mục Edge case).
- "Đổi khách sạn" chạy lại cả luồng lập lịch (phân luồng, trích intent, gọi Search/Similar, lọc, xếp lịch, LLM viết lời).
  Lượt này mất vài giây và có thể đổi cả những phần người dùng không nhắc tới, vì kết quả tìm lại có thể khác lần trước.

Những dữ liệu cần để trả lời đều đã được tra ở lượt lập lịch. Đề xuất lưu lại chúng và trả lời từ đó, giống cách lượt
"chọn phương án N" đang làm (AC-AGT-04: không tìm lại, không gọi LLM, mục tiêu dưới 3 giây).

## Phạm vi

Chỉ hai loại sản phẩm, mỗi loại hai việc:

| Loại | Hỏi (lịch giữ nguyên) | Đổi (lịch đổi) |
|---|---|---|
| Vé máy bay | rẻ nhất, sớm nhất, muộn nhất, bay thẳng, có chuyến khoảng giờ X không, theo chiều đi/về | sang chuyến rẻ nhất, theo giờ ("bay chiều", "sau 15h"), sang một chuyến đã nêu tên |
| Khách sạn | rẻ nhất, gần nhất, trong ngân sách, trong số khách sạn đã tra | sang khách sạn khác (không nêu tiêu chí), rẻ hơn, gần hơn, sang khách sạn đã nêu tên |

Ngoài phạm vi, vẫn đi luồng lập lịch như hiện tại: đổi điểm đến, nơi đi, ngày đi, số ngày, số người, ngân sách; đổi hoặc
hỏi hoạt động; hỏi về sản phẩm chưa từng được tra.

## Nội dung đề xuất

### 1. `requirements.md` §1.4, FR-AGT-05

Hiện tại:

> Người dùng có thể yêu cầu đổi phòng, đổi điểm tham quan hoặc rút ngắn/kéo dài số ngày trong lịch trình qua hội thoại
> tiếp theo. Khi người dùng muốn đổi một sản phẩm đã hiển thị mà không nêu tên thay thế, trợ lý có thể tìm sản phẩm tương
> tự sản phẩm đó: sản phẩm gốc chỉ lấy từ lịch trình lượt trước, kết quả cùng loại (taxonomy).

Thêm vào cuối:

> Sau khi có lịch trình, người dùng có thể hỏi về vé máy bay và khách sạn mà trợ lý đã tra cho lịch đó (chuyến rẻ nhất,
> giờ bay, khách sạn rẻ hơn...) và đổi vé hoặc khách sạn trong số đã tra. Trợ lý trả lời từ dữ liệu đã tra, không lập
> lịch lại (AC-AGT-05).

### 2. `requirements.md` §3, AC-AGT-02, câu cuối

Hiện tại:

> Lượt sửa lịch chỉ chọn lại vé khi nơi đi, ngày đi, số ngày hoặc điểm đến đổi.

Thay bằng:

> Lượt sửa lịch chỉ chọn lại vé khi nơi đi, ngày đi, số ngày hoặc điểm đến đổi, hoặc khi người dùng chủ động chọn chuyến
> khác (AC-AGT-05). Chuyến người dùng chọn được giữ ở các lượt sau cho tới khi một trong bốn trường trên đổi.

### 3. `requirements.md` §3, thêm AC-AGT-05

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| **AC-AGT-05** | Đã có lịch *"Hà Nội đi Phú Quốc 3 ngày từ 10/10, 2 người lớn"*, người dùng hỏi tiếp *"vé Phú Quốc về Hà Nội chuyến nào rẻ nhất?"*, *"đổi sang chuyến bay chiều"*, *"đổi khách sạn khác"* | Trợ lý trả lời từ vé và khách sạn đã tra ở lượt lập lịch gần nhất, không tìm lại và không lập lịch lại. **Hỏi:** câu trả lời nêu đúng sản phẩm thoả câu hỏi (tên, giờ bay, giá), mỗi sản phẩm là liên kết tới sản phẩm thật; lịch trình giữ nguyên. Không có sản phẩm nào thoả thì nói rõ và nêu sản phẩm gần nhất với yêu cầu. **Đổi:** lịch được xếp lại bằng cùng luật (AC-AGT-02 xếp theo giờ bay, AC-AGT-04 quãng đường và phương án khác) trên cùng bộ sản phẩm đã tra, chỉ thay vé hoặc khách sạn được đổi; câu trả lời chỉ nêu phần thay đổi (đổi từ gì sang gì, chênh tiền, giờ bay mới hoặc chênh km) và do hệ thống viết. Trước khi đổi, hệ thống kiểm lại giá và tình trạng còn bán của sản phẩm mới theo mã; giá đổi thì dùng giá mới và nói rõ, hết bán thì không đổi và báo người dùng. Đổi khách sạn mà không nêu tiêu chí thì lấy khách sạn kế tiếp theo luật chọn của AC-AGT-04, bỏ khách sạn đang chọn. Không còn sản phẩm nào khác trong số đã tra thì đi luồng đổi sản phẩm hiện có (FR-AGT-05: tìm sản phẩm tương tự). Câu hỏi ngoài vé và khách sạn, hoặc câu đổi điểm đến, nơi đi, ngày, số ngày, số người, ngân sách thì đi luồng lập lịch như cũ. Hội thoại chưa có lịch, hoặc không còn dữ liệu đã tra, thì cũng đi luồng lập lịch. Mục tiêu thời gian phản hồi: dưới 3 giây. |

### 4. `architecture.md` §3

Sơ đồ trạng thái: thêm nhánh từ `ClassifyTurn`:

```text
ClassifyTurn --> FollowUp: Hỏi hoặc đổi vé/khách sạn của lịch vừa gửi, còn dữ liệu đã tra
FollowUp --> [*]: Trả lời hoặc xếp lại lịch từ dữ liệu đã tra; câu trả lời do hệ thống viết
```

Gạch đầu dòng "Hội thoại", câu cuối, hiện tại:

> Giá và tình trạng còn chỗ luôn được tải lại, không dùng bản lưu trong hội thoại.

Thay bằng:

> Working memory giữ thêm vé và sản phẩm đã tra ở lượt lập lịch gần nhất để trả lời câu hỏi tiếp theo về lịch đó
> (AC-AGT-05). Câu trả lời dạng hỏi dùng giá lúc tra; trước khi đổi sang một sản phẩm, giá và tình trạng còn bán của sản
> phẩm đó được tải lại theo mã. Mọi lượt lập lịch vẫn tải lại giá và tình trạng còn chỗ, không dùng bản lưu.

Gạch đầu dòng "Không suy đoán dữ liệu sản phẩm": thêm "hoặc dữ liệu đã tra ở lượt lập lịch gần nhất (AC-AGT-05)" vào cuối
danh sách nguồn hợp lệ.

## Điểm cần người chốt quyết định

1. **Giá trong câu trả lời dạng hỏi.** Đề xuất: dùng giá lúc tra, không tải lại (nhanh, không gọi catalog). Phương án
   khác: tải lại giá của các sản phẩm được nêu (đúng hơn, thêm một lượt gọi catalog).
2. **Câu hỏi không đổi lịch trả về gì.** Đề xuất: `COMPLETED` với lịch giữ nguyên và lời đáp mới, như lượt "lấy phương án
   N". Không đổi contract, Web không phải sửa. Phương án khác: thêm kiểu trả lời riêng, phải lên version contract và sửa Web.
3. **Lời đáp do code viết hay do LLM viết.** Đề xuất: code viết theo mẫu, như lượt chọn phương án. LLM chỉ dùng để hiểu
   câu hỏi (loại sản phẩm, hỏi hay đổi, tiêu chí, chiều bay). Lời đáp sẽ cứng hơn nhưng nhanh, và không có rủi ro LLM viết
   sai giá.

## Thay đổi source sau khi chốt

- Backend agent (`src/backend/app/`):
  - `agents/steps/classification.py`, `agents/steps/prompts.py`: thêm nhãn phân luồng hỏi/đổi vé, khách sạn. LLM chỉ trả
    loại sản phẩm, hỏi hay đổi, tiêu chí, chiều bay, và mã sản phẩm khi người dùng nêu tên.
  - `agents/graph.py`, `agents/routing.py`, `agents/nodes.py`, `agents/state.py`: thêm node `follow_up`
    (`classify → follow_up → finalize`).
  - `agents/steps/follow_up.py` (mới): dựng lời đáp, gọi xếp lại lịch.
  - `domain/itinerary/follow_up.py` (mới): luật thuần để lọc, xếp và chọn vé, khách sạn theo tiêu chí.
  - `agents/nodes.py` (`finalize_node_async`): lưu vé và ứng viên đã tra của lượt `COMPLETED` vào working state, có giới
    hạn kích thước.
  - `agents/steps/validation.py`: grounding của lượt `follow_up` kiểm với dữ liệu đã lưu.
  - `application/itinerary/`: kiểm lại giá và tình trạng còn bán theo mã qua `CatalogPort` trước khi đổi.
- Contract: không đổi nếu chốt theo đề xuất ở điểm 2.
- Frontend: không đổi nếu chốt theo đề xuất ở điểm 2.
- Spec: `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md`, `docs/spec/agent/nghiep-vu/ve-may-bay.md` (gỡ edge case
  "chưa đổi được chuyến bay qua chat"), `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/state-fields.md`,
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Test: unit cho `domain/itinerary/follow_up.py` và node `follow_up`; golden case cho ba câu ở AC-AGT-05.

## Quyết định chốt (2026-10-11)

Chốt theo những gì source đang làm (đã chạy qua hai đợt chat thử 10/10 và 11/10).

**Chốt và đã áp dụng vào PRD:**

- Sau khi có lịch, câu **hỏi** về vé máy bay của chuyến (rẻ nhất, đắt nhất, giờ bay, chuyến về, ngày khác) được trả lời bằng
  code từ chuyến bay của catalog, tra lại theo tuyến của chuyến ngay lượt đó. Trả `NEEDS_CLARIFICATION`, lịch giữ nguyên,
  không lập lịch lại. LLM của `classify` chỉ hiểu câu hỏi. Cách trả lời chi tiết theo FR-AGT-07 / AC-AGT-08 (đề xuất
  `2026-10-11-tu-van-ve-may-bay-va-sua-loi-chat-thu-lan-3.md`).
- Câu **đổi** vé, khách sạn đi luồng đổi hiện có (đã chốt khi áp dụng `2026-10-09-goi-y-truoc-khi-lap-lich.md`): chưa nói
  rõ thì hỏi lại kèm phương án đã tính hoặc chuyến khác cùng ngày, mỗi lựa chọn một nút; nói rõ thì đổi rồi lập lại lịch.
  Chuyến người dùng chọn được giữ ở các lượt sau khi còn bán đúng ngày của chặng.
- Giá trị điểm chốt: điểm 1 — không áp dụng (câu hỏi luôn tra lại giá); điểm 2 — `NEEDS_CLARIFICATION`, không phải
  `COMPLETED`, contract không thêm status; điểm 3 — lời đáp do code viết, LLM chỉ hiểu câu hỏi.

**Từ chối** (luồng hiện có đã làm được việc cần làm):

- Node `follow_up` riêng và nhãn phân luồng hỏi/đổi riêng: câu hỏi vé đi nhánh vé của `explore`; câu đổi đi luật đổi trong
  `classify` rồi lập lại lịch. Thêm node không thêm được hành vi nào người dùng thấy.
- Lưu vé và ứng viên đã tra vào working memory để trả lời và đổi từ đó; giữ nguyên câu "Giá và tình trạng còn chỗ luôn được
  tải lại" ở `architecture.md` §3. Tra lại theo tuyến nhanh (bấm nút dưới 1 giây; gõ chữ khoảng 2 giây vì qua LLM của `classify`) và không trả lời bằng giá
  cũ.
- Đổi vé, khách sạn chỉ thay đúng món đó trên cùng bộ sản phẩm, không lập lại lịch: luồng đổi hiện có lập lại lịch, vì giờ
  bay đổi thì cửa sổ ngày đến, ngày về đổi (AC-AGT-02); đổi khách sạn bằng nút phương án đã không tìm lại (AC-AGT-04).
- Hỏi về khách sạn của lịch (rẻ nhất, gần nhất, trong ngân sách) từ dữ liệu đã tra: hàng thẻ "Phương án khác" (AC-AGT-04)
  đã cho xem và đổi khách sạn; câu hỏi khách sạn khác đi nhánh khám phá (FR-AGT-06).
- Bản AC-AGT-05 ở mục "Nội dung đề xuất" được thay bằng bản theo hành vi trên; gạch đầu dòng "Hội thoại" và "Không suy
  đoán dữ liệu sản phẩm" ở `architecture.md` §3 không đổi theo §4 của đề xuất.

**Đã áp dụng vào PRD:** `requirements.md` §1.4 (FR-AGT-05 thêm một gạch đầu dòng), §3 (AC-AGT-02 câu cuối, thêm AC-AGT-05);
`architecture.md` §3 (ghi chú dưới sơ đồ, câu hỏi vé sau khi có lịch tra lại theo tuyến).
