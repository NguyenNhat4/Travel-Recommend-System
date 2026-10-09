# Chọn khách sạn theo ngân sách và luôn kèm phương án khác

- Ngày: 2026-10-08 (gộp và thay đề xuất "Quy đổi km ra tiền" ngày 2026-10-07, chưa chốt)
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-08
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (AC-AGT-04)
- Mã FR/NFR: FR-AGT-03, NFR-REL-01, AC-AGT-04

## Lý do

1. **Luật hiện tại chọn khách sạn quá đắt.** AC-AGT-04 ghi: "hai lịch có chi phí chênh nhau dưới 2 km coi như ngang
   nhau, khi đó chọn lịch có tổng tiền thấp hơn". Nghĩa là chỉ cần bớt được 2 km thì trả thêm bao nhiêu cũng được. Đo
   trên catalog staging ngày 07/10/2026 (30 mẫu mỗi ô, 10 điểm tham quan và 10 hạng phòng còn bán, 2 người lớn), khách
   sạn được chọn đắt gấp **1,8–5,9 lần** khách sạn rẻ nhất (trung vị), có lúc gấp **69 lần**.
2. **Ngân sách chưa ảnh hưởng tới việc chọn.** Ngân sách hiện chỉ dùng để báo `WITHIN_BUDGET`/`OVER_BUDGET` sau khi lịch
   đã dựng xong. Người dùng nêu ngân sách cao vẫn nhận khách sạn như người không nêu.
3. **Người dùng không thấy được đánh đổi.** Theo góp ý của người dùng: khi thấy "thêm X ₫ thì đỡ đi Y km", khách thường
   cân nhắc nâng ngân sách. Hiện câu trả lời chỉ có một lịch, không có con số nào để so.

## Nội dung đề xuất

### 1. Phương án chính

Mỗi lịch ứng viên (cách chọn điểm, ghép ngày và chọn khách sạn) có hai con số:
- **quãng đường** cả chuyến (km, đường chim bay, cách tính như AC-AGT-04 hiện hành, cộng phạt đổi khách sạn);
- **tổng tiền** như `estimatedTotal` (gồm vé máy bay).

Ưu tiên gần, nhưng trong ngân sách nếu có:

| Trường hợp | Phương án chính |
|---|---|
| Không có ngân sách | Giữ luật hiện tại: lịch **ít km nhất**; hai lịch chênh dưới 2 km thì lấy lịch rẻ hơn. |
| Có ngân sách | Trong các lịch có tổng tiền ≤ ngân sách, chọn lịch **ít km nhất**; chênh dưới 2 km thì lấy lịch rẻ hơn. Ngân sách càng rộng, khách sạn càng gần (và thường tốt hơn). |
| Có ngân sách nhưng không lịch nào vừa | Lịch **rẻ nhất**, báo vượt ngân sách như hiện nay. |

Lịch có giá chưa biết không được coi là vừa ngân sách. Vé máy bay chưa rõ giá thì không so được với ngân sách: dùng luật
"không có ngân sách".

Không dùng đơn giá quy đổi km ra tiền. Số đo các mức đơn giá (để tham khảo vì sao) ghi ở report
`src/evaluation/reports/eval-2026-10-08-toi-uu-quang-duong.md`.

### 2. Luôn kèm phân tích "tăng X ₫ → giảm Y km"

Câu trả lời có thêm mục **"Phương án khác"**:
- một dòng tổng của lịch đã chọn: "Lịch trên: đi lại khoảng N km cả chuyến.";
- tối đa 3 phương án, lấy từ các lịch "không bị lịch nào khác hơn cả về tiền lẫn km":
  - phía **gần hơn, đắt hơn** (tối đa 2): lịch rẻ nhất trong số các lịch bớt được ít nhất 2 km, và lịch ít km nhất;
  - phía **rẻ hơn, xa hơn** (tối đa 2): lịch rẻ hơn mà đi thêm ít km nhất, và lịch rẻ nhất;
  - quá 3 thì ưu tiên phía gần hơn (vì đây là thứ khiến người dùng cân nhắc nâng ngân sách).

Ví dụ:

> **Phương án khác**
> Lịch trên: đi lại khoảng 34 km cả chuyến.
> • Phương án 1: thêm 1.200.000 ₫ — ở Khách sạn A: bớt khoảng 8 km đi lại.
> • Phương án 2: thêm 4.500.000 ₫ — ở Khách sạn B: bớt khoảng 15 km đi lại (vượt ngân sách 2.100.000 ₫).
> • Phương án 3: bớt 600.000 ₫ — ở Khách sạn C: đi thêm khoảng 12 km.
> Muốn đổi, bạn nhắn "lấy phương án 1" hoặc tên khách sạn.

Quy tắc:
- Phương án vượt ngân sách vẫn hiện, ghi rõ vượt bao nhiêu.
- Chỉ hiện phương án chênh từ 2 km trở lên và có giá biết được; không còn phương án nào thì không hiện mục này.
- Số tiền, số km và tên khách sạn do code tính từ catalog, không do LLM viết (grounding 100%, NFR-REL-01). Km ghi
  "khoảng" vì là đường chim bay.
- Chỉ hiện trong câu trả lời chat; contract không đổi.
- Người dùng chọn bằng lượt nhắn tiếp ("lấy phương án N" hoặc tên khách sạn); hệ thống dựng lại lịch với khách sạn đó
  (khách sạn đêm 1 nếu phương án có hai khách sạn).

### 3. Câu nêu tiêu chí

- Có ngân sách: thêm vế "…mà vẫn nằm trong ngân sách của bạn".
- Không có ngân sách: giữ câu hiện tại.

### `requirements.md` §3 — sửa AC-AGT-04

Câu hiện tại:

> Gần trước, rẻ sau: hai lịch có chi phí chênh nhau dưới 2 km coi như ngang nhau, khi đó chọn lịch có tổng tiền thấp hơn.

Thay bằng:

> Gần trước, trong ngân sách nếu có: hai lịch có chi phí chênh nhau dưới 2 km coi như ngang nhau, khi đó chọn lịch có
> tổng tiền thấp hơn; khi người dùng nêu ngân sách, chỉ xét các lịch có tổng tiền (gồm vé máy bay) không vượt ngân sách,
> không lịch nào vừa thì lấy lịch rẻ nhất. Câu trả lời có mục "Phương án khác": tổng km của lịch đã chọn và tối đa 3
> phương án (ưu tiên tối đa 2 gần hơn và đắt hơn, rồi rẻ hơn và xa hơn), mỗi phương án ghi khách sạn, chênh tiền và chênh
> km so với lịch đã chọn, phương án vượt ngân sách ghi rõ vượt bao nhiêu; chỉ hiện phương án chênh từ 2 km trở lên.
> Người dùng chọn phương án bằng lượt nhắn tiếp theo.

Câu "lịch trình chưa hiện số km" đổi thành: "lịch trình chưa hiện số km từng ngày; tổng km và chênh km chỉ xuất hiện
trong mục Phương án khác."

## Thay đổi source sau khi chốt

- `src/backend/app/domain/itinerary/routing.py`:
  - mỗi lịch giữ cả km và tiền;
  - chọn phương án chính theo mục 1;
  - lọc các lịch không bị lịch nào khác hơn cả về tiền lẫn km, lấy phương án khác theo mục 2 và giải chính xác các lịch
    đó;
  - danh sách khách sạn đem ra so có thêm 3 khách sạn rẻ nhất;
- `src/backend/app/domain/itinerary/planning.py`:
  - tiền tính đúng như `totals` (gồm vé máy bay, truyền vào `compose_plan`);
  - truyền phần ngân sách còn lại sau vé vào `optimize`;
  - proposal có `options`;
  - `validate_plan` kiểm grounding cả khách sạn trong phương án khác.
- `src/backend/app/agents/steps/`:
  - `messages.py`: câu tiêu chí, dòng phương án khác (vi, en);
  - `narration.py` và `prompts.py`: mục "Phương án khác" bằng văn bản tất định, LLM không viết lại số;
  - `composition.py`: warning `STAY_OPTIONS`; `nodes.py`/`classification.py`: lưu phương án vào hội thoại, lượt "lấy
    phương án N" thành `specific_hotel` (chỉ nhận tên đã hiện).
- Test:
  - `test_itinerary_routing.py`: ngân sách cao chọn khách sạn gần hơn ngân sách thấp; không lịch nào vừa thì lấy lịch
    rẻ nhất; phương án khác đúng biên, đúng số lượng, không hiện khi chênh dưới 2 km;
  - test agent: chuỗi văn bản phương án khác và lượt "lấy phương án 1".
- Spec: `docs/spec/agent/nghiep-vu/xep-lich.md`, `glossary.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.
- Report `src/evaluation/reports/eval-2026-10-08-toi-uu-quang-duong.md`: số đo luật hiện tại, các mức ngân sách, phương
  án khác, kèm bảng các mức đơn giá km→tiền đã thử và lệnh tái sinh số.

## Sửa khi áp dụng

Người dùng chốt ngày 2026-10-08 với các điều chỉnh so với bản đầu: không dùng đơn giá km→tiền (ưu tiên gần, trong ngân
sách nếu có); câu trả lời luôn có phân tích "tăng X ₫ → giảm Y km"; phương án khác chỉ hiện trong chat.
