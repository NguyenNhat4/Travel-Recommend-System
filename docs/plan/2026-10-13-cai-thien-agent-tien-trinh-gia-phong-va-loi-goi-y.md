# Cải thiện tiến trình, giá phòng và lời gợi ý của agent

- Ngày: 2026-10-13
- Trạng thái: đã triển khai v2; kiểm kỹ thuật, người dùng tự eval chất lượng
- Người yêu cầu: Nguyễn Minh Nhật
- Mã FR/NFR: FR-AGT-01–06, NFR-REL-01, NFR-PERF-02, NFR-MAINT-02
- AC liên quan: AC-AGT-01/02/04/06/07/09
- Phạm vi chính: assistant v2 hiện có; xác minh phiên bản thật trước khi sửa
- Liên quan: `2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md`, `../prd/update-archive/2026-10-13-giai-thich-quyet-dinh-agent-trong-tien-trinh.md`

## 1. Mục tiêu và quyết định đã có

Người dùng muốn tiến trình đơn giản: **Think → Act → Observe → Think → … → trả lời**. Chỉ hai bên tham gia: LLM quyết định, tool thực thi và trả dữ kiện. Không dựng thêm workflow nghiệp vụ hoặc gọi một LLM khác để viết log. Người dùng đã đồng ý hướng này trong chat, yêu cầu thực thi, và sẽ tự eval chất lượng sau khi sửa.

Ba phản hồi cần xử lý cùng đợt: agent chỉ gợi ý buổi sáng; hai người bị tính giá hai phòng; câu “HCM có gì chơi” vẫn trả sản phẩm dạng liệt kê.

PRD là căn cứ: khám phá không tự xếp lịch; lịch không bắt buộc lấp đầy mọi buổi; giá phải đúng đơn vị và số phòng; sản phẩm/facts phải có nguồn. Tiến trình Think là lời giải thích công khai ngắn do LLM viết, không phải suy luận nội bộ. Cập nhật PRD theo đề xuất tiến trình trước khi đổi contract/code; bản đề xuất dài trước đó cần rút về giao diện ba nhãn này, không mở thêm chức năng chẩn đoán. Không yêu cầu chốt lại hướng UX đã được đồng ý; nếu phát sinh thay đổi nghiệp vụ khác PRD thì đề xuất riêng.

## 2. Bằng chứng và giới hạn hiện tại

Chưa nhận trace đầy đủ của hội thoại người dùng. Đây là kế hoạch kiểm và sửa, **không phải báo cáo đã audit toàn bộ trace**.

| Vấn đề | Bằng chứng hiện có | Điều chưa kết luận |
|---|---|---|
| Câu tiến trình cố định | `widgetProgressLabels.ts` ghép câu theo scope/intent; `widgetProgressView.ts` có câu soạn lời tư vấn cố định | Chưa đối chiếu stream của lượt người dùng với requestId |
| v2 vẫn bị ghép thành ba bước | `widgetV2.v2Progress()` trả `steps: ['understand', 'search', 'write']` | Chưa kiểm cấu hình phiên bản đang phục vụ người dùng |
| Lời khám phá dạng liệt kê | Người dùng phản hồi; lịch sử `2026-10-13-orc-v2-ke-chuyen-goi-y.md` đã sửa prompt v2 | Prompt hiện tại có luật kể chuyện; không sửa lặp lại trước khi biết đang chạy v1/v2 và model có tuân thủ không |
| Chỉ có buổi sáng | Người dùng phản hồi | Có thể do giờ LLM phác, tool kiểm, chuyển response hoặc UI; chưa xác định lớp gây lỗi |
| Hai người thành hai phòng | Người dùng phản hồi; `planning.stay_rooms()` dùng `ceil(adults / priceAdults)`, validator và final đều dùng helper đó | Chưa có product/ref, `priceAdults`, hạng phòng, số đêm và giá nguồn của lượt bị lỗi |

Lịch sử v2 còn ghi E11/E12 dang dở và E13 chưa chuyển mặc định. Số kiểm trước đây là bằng chứng lịch sử, không phải kết quả chạy mới của plan này.

## 3. Danh sách cải thiện theo ưu tiên

### P0 — Giá phòng đúng và giải thích được

Theo AC-AGT-04 hiện tại:

`phòng = ceil(người lớn / priceAdults)`

`tiền lưu trú = giá mỗi phòng mỗi đêm × số đêm thật × số phòng`

Hai người lớn, `priceAdults=2` → một phòng. Hai người lớn, `priceAdults=1` → hai phòng theo luật giá đang có. `maxOccupancy` và `priceAdults` có ý nghĩa khác nhau; sức chứa hai người không tự chứng minh giá đã gồm hai người. Không sửa thành `rooms=1` hoặc dùng sức chứa thay luật giá để làm số đẹp.

Việc cần làm:

1. Đối chiếu thẻ khách sạn tổng với hạng phòng thực sự đưa vào lịch: ref/productId, `unitPrice`, `priceUnit`, `priceAdults`, `maxOccupancy`, ngày nhận/trả và số khách.
2. Theo dòng dữ liệu từ tool → registry → draft → validator → final → widget. Tìm lớp nhân người sai, chọn sai hạng phòng hoặc đánh rơi thuộc tính.
3. Nếu nguồn/adapter thiếu hoặc sai `priceAdults`, sửa đúng lớp và nguồn có bằng chứng. Không tự viết lại catalog; nếu cần đổi loader/seed thì mở phạm vi riêng và đọc tài liệu Data/DB.
4. Nếu phép tính đúng nhưng thẻ một phòng/đêm bị hiểu là giá cả đoàn, làm rõ nhãn đơn giá và tổng tiền. Cùng một phương án phải hiển thị thống nhất số phòng, số đêm và tổng trên câu trả lời, thẻ và ngân sách.
5. Thiếu giá/cơ sở tính thì cảnh báo unknown; không chốt tổng hoàn chỉnh. Kiểm `rooms_of()` mặc định một phòng có tạo cảm giác đã xác minh hay không; chưa có bằng chứng thì không gọi đây là lỗi đã xác định.

Nếu người dùng muốn hai người chung một phòng kể cả giá chỉ gồm một người, cần dữ liệu phụ thu hoặc chính sách giá tương ứng. Đổi công thức PRD phải có đề xuất riêng, không lẫn vào bugfix.

### P1 — Think → Act → Observe theo vòng thật

Tái dùng graph `decide ⇄ dispatch` hiện có. Mỗi vòng:

| Nhãn | Ai tạo | Nội dung |
|---|---|---|
| Think | LLM trong cùng quyết định execute/respond | Giải thích ngắn cách hiểu và quyết định tiếp theo; sau tool nói kết quả đủ/chưa đủ và vì sao |
| Act | Code từ call đã kiểm | Công việc đang gọi: tìm, đọc chi tiết, kiểm lịch…; không hiển thị JSON/arguments thô |
| Observe | Code từ result thực tế | Kết quả, số đếm có định nghĩa, partial, không có dữ liệu hoặc lỗi; không dùng lời mẫu đóng vai suy nghĩ LLM |

- Thêm phần giải thích công khai vào structured decision đang có, không thêm model call.
- Phát Think sau khi quyết định hợp lệ; rồi Act trước await, Observe khi có kết quả. Quyết định bị từ chối không hiện như công việc đã chạy.
- Tool chạy song song: nhiều Act có thể xuất hiện trước Observe; gắn callId/runId để không nhầm kết quả. Không ép mỗi tool phải được LLM gọi tuần tự để đẹp log.
- Trả lời ngay thì Think → câu trả lời; lỗi tool vẫn quay về LLM nếu còn quota; lỗi terminal hiện lỗi thật, không bịa một vòng Think.
- UI lưu danh sách sự kiện theo sequence cho đúng lượt, cập nhật trạng thái cùng callId, không nối stream hai lượt hoặc cộng số hai lần.
- Bỏ cách ghép tiến trình v2 vào understand/search/write; giữ cách thu gọn khi xong và mở xem lại. Final/thẻ sản phẩm tiếp tục dùng phần hiển thị đang có.
- Số found/eligible/selected/displayed giữ đúng nghĩa. Đặc biệt `v2Progress()` hiện lấy eligible thành inScope và displayed thành chosen; kiểm và sửa nhãn/mapping để không nói sai số tìm thấy hay số LLM đã chọn.
- Câu Think có facts dùng cơ chế ref/fact hiện có; không đưa product claims chưa kiểm vào tiến trình. Nếu không có giải thích hợp lệ, chỉ hiện trạng thái thực thi.

### P1 — Khám phá thành lời tư vấn có mạch

- “HCM có gì chơi” là khám phá: mở bằng câu định hướng ngắn; nối vài lựa chọn theo trải nghiệm/sở thích; mỗi thẻ ở cạnh đoạn giới thiệu tương ứng; kết bằng lời mời phù hợp.
- Nêu nơi đó có gì và hợp với ai dựa trên description/attributes thật. Không bịa không khí, độ đông, món ăn hay thời điểm đẹp.
- Không tự chia sáng/chiều/tối hoặc dùng thứ tự “đầu tiên… sau đó…” khi chưa có yêu cầu lập lịch.
- Không lặp tên ngay sau thẻ, không một khối toàn tên sản phẩm, không lặp cùng lời khen cho mọi nơi.
- Prompt v2 đã có các quy tắc này: tái hiện trước, sửa phần còn thiếu ở prompt/context/renderer. Không thêm bộ đếm câu hay guardrail ép giọng văn cho mọi lượt.
- Tôn trọng người dùng nhắn cộc lốc hoặc xin liệt kê: độ dài/cách trình bày theo ý người dùng và AC-AGT-07; không ép mọi câu thành văn dài.

### P1 — Lịch trình không dồn vô lý vào buổi sáng

Tách hai loại câu: khám phá không cần nhãn buổi; yêu cầu lập lịch mới kiểm phân bổ thời gian.

- So `draft.days.activities.start_minute/end_minute` → kết quả tool → final `startMinute/endMinute` → `widgetV2.period()` → `WidgetDays`.
- Nếu giờ đúng nhưng UI chỉ ghi sáng: sửa mapping/render. Nếu draft chỉ có sáng: sửa chỉ dẫn phác lịch/đọc giờ mở và nhịp chuyến. Nếu tool trả violations: kiểm LLM có đọc/sửa hay bỏ mất hoạt động.
- Lịch nhiều ngày có đủ thời gian và dữ liệu hoạt động phù hợp nên phân bổ tự nhiên qua các khung giờ; không nhét hết vào sáng theo mặc định.
- Không lấp mọi buổi bằng hoạt động giả. Giữ đúng yêu cầu “chỉ buổi sáng”, nhịp đi thư thả, hoạt động cả ngày và cửa sổ ngày đến/về.
- Không ép có hoạt động ban đêm khi catalog chưa có giờ mở hoặc bằng chứng. Thiếu thời lượng/di chuyển thì nêu giả định, không nhận đã kiểm hoàn toàn.

### P2 — Những điểm cần rà thêm khi có trace

Đây là checklist, không phải các lỗi đã xác nhận:

| Nhóm | Cần kiểm |
|---|---|
| Hiểu câu | Câu mới và follow-up; đổi điểm đến; số khách/trẻ em; consent lập lịch |
| Tool | Chọn công cụ phù hợp; calls phụ thuộc không nằm cùng batch; cursor giữ đúng arguments; lỗi khác empty |
| Chọn sản phẩm | Không lặp khi xem thêm; đủ yêu cầu số lượng hoặc nói thiếu; giữ tiện ích/giá/ngày chưa đổi; tránh các nơi đã bị chê |
| Dữ kiện | Giá/miễn phí/đánh giá/giờ có nguồn; lịch sử chỉ nhận diện, facts được refresh; không gọi popular là cá nhân hóa |
| Chi phí | Vé theo khách, phòng theo cơ sở giá, vé trẻ em đúng chính sách; total unknown khi thiếu giá; ngân sách warning-only |
| Trình bày | Câu dẫn và thẻ khớp; không lặp; tên/giá/đơn vị/ngày đúng; lỗi và thiếu dữ liệu có giải thích |
| Thực thi | Gọi thừa/tra detail tuần tự; retry hợp hạn mức; model timeout; final không bị preview commit trước |

Mỗi phát hiện phải có: requestId + phiên bản/commit → quyết định/call/result/response liên quan → hiện tượng → ảnh hưởng → nguyên nhân đã xác định hoặc giả thuyết → file sửa → ca kiểm. Không ghi “đã review trace” khi chỉ có mô tả hoặc fixture.

## 4. Thứ tự thực hiện và file dự kiến

| Bước | Việc | File chính | Điều kiện xong |
|---|---|---|---|
| 0 | Tái hiện ba lỗi, xác định v1/v2, giữ baseline và dữ kiện giá | Trace người dùng hoặc ca tái hiện tối thiểu; không cần tạo hệ thống eval mới | Có bằng chứng từng lỗi hoặc ghi chưa tái hiện |
| 1 | Sửa số phòng/nhãn giá tại lớp gây lỗi | `domain/itinerary/planning.py`, `draft_validation.py`, `application/itinerary/v2_final.py`, widget giá nếu cần | Hai khách/priceAdults=2 không bị nhân hai phòng; unknown không thành tổng chắc chắn |
| 2 | Rút đề xuất tiến trình, cập nhật PRD trước; contract và types trước code | `docs/prd/`, `src/shared/contracts/schemas/assistant-v2.yaml`, mocks v2, types sinh tự động | Nội dung đúng hướng Think/Act/Observe đã đồng ý; contract PASS |
| 3 | Phát Think cùng decision, dùng Act/Observe hiện có | `application/itinerary/orc_contracts.py`, `agents/orc_v2.py`, route v2 nếu cần | Đúng vòng/call/run; không tăng model calls/deadline |
| 4 | Render tiến trình động | `services/assistantV2Stream.ts`, `context/AssistantProvider.tsx`, state, `widgetV2.ts`, progress model/view/component | Không khung bước cố định; nhiều vòng/thứ tự/lỗi/thu gọn đúng |
| 5 | Sửa lời khám phá và giờ lịch theo nguyên nhân | `agents/orc_v2.py`; adapter/renderer/widget nếu tái hiện chỉ ra lỗi ở đó | Hai loại câu đáp ứng mục 3, không thêm sản phẩm hay giờ giả |
| 6 | Kiểm kỹ thuật, cập nhật spec/history và bàn giao | Tests hiện có + ca hồi quy cần thiết, docs liên quan | Báo kiểm mới, baseline đỏ, giới hạn bằng chứng và ca người dùng tự eval |

Đây là refactor tập trung vào schema quyết định, stream và UI tiến trình; không viết lại agent/Search/Recommendation, không đổi framework và không tách thêm agent. Các file ở bước 1/5 chỉ sửa khi bằng chứng xác định đúng lớp. Nếu trace lỗi thuộc v1, ghi rõ phạm vi: sửa v2 không tự làm phiên bản người dùng đang chạy hết lỗi. Không chuyển mặc định v2 hoặc bỏ v1 trong task này; điều kiện chuyển theo plan E12/E13 hiện có.

## 5. Kiểm kỹ thuật và bàn giao để người dùng tự eval

### Agent kiểm trước khi bàn giao

- Số phòng: hai người/priceAdults=2; ba người/priceAdults=2; thiếu cơ sở giá; nhiều đêm; 0 đêm không lưu trú; trẻ em theo luật hiện hành; phần biết/unknown nhất quán.
- Tiến trình: trả lời ngay; một và nhiều vòng; calls song song; partial/empty/error; decision không hợp lệ; hai run; stream sự kiện lặp; thiếu Think; final và preview đúng trạng thái.
- Giờ: hoạt động sáng/chiều/tối giữ giờ qua adapter/UI; cùng buổi nhiều hoạt động không bị rơi; ngày có cửa sổ chuyến bay ngắn không bị ép đủ buổi.
- Contract validator, tests domain/application/agent/contract/architecture có liên quan; frontend tests/typecheck/lint/build và browser cho tiến trình mới. Không chạy model giả rồi nhận đã chứng minh giọng kể chuyện.
- DoD coverage domain/application theo PRD: đo phần thay đổi khi khả dụng, ghi rõ nếu chưa đạt/chưa đo. Không gọi focused tests là full-suite PASS; baseline lỗi cũ ghi riêng.
- Không mở suite eval mới hay chạy rộng model thật nếu người dùng tự eval; các kiểm kỹ thuật bắt buộc vẫn làm. Nếu đổi mặc định v2 thì nghiệm thu E12/E13 hiện có vẫn áp dụng.

### Bộ ca gợi ý người dùng tự eval

| Ca | Kỳ vọng chính |
|---|---|
| “HCM có gì chơi?” | Có mạch tư vấn và thẻ thật, không lịch sáng/chiều/tối |
| “Xem thêm điểm tham quan và khách sạn ở HCM” | Think/Act/Observe phản ánh cả hai việc; không lặp các thẻ đã xem |
| “Lập lịch HCM 3 ngày, 2 người lớn, từ <ngày hợp lệ>” | Phân bổ tự nhiên theo cửa sổ thời gian; giá phòng đúng cơ sở giá |
| “Chỉ đi buổi sáng thôi” | Giữ giới hạn buổi sáng, không tự lấp chiều/tối |
| “Khách sạn này giá cho hai người hay một phòng?” | Phân biệt đơn giá, số khách giá bao gồm, phòng/đêm/tổng; thiếu dữ kiện nói rõ |
| “Đổi thành 3 người lớn” | Phòng/tiền cập nhật theo sản phẩm thực tế, không nhân người trực tiếp vào giá phòng |
| “Không cần khách sạn” | Không tự thêm lưu trú, phần tiền phản ánh đúng lịch |
| Tool lỗi hoặc tìm chưa đủ | Observe đúng lỗi/phần thiếu; Think quyết định tiếp có căn cứ |

Bàn giao gồm diff/file sửa, kiểm kỹ thuật đã chạy, cách bật bản để eval và các lỗi còn mở. Trace thật nếu được cung cấp sẽ bổ sung mục 3/P2 bằng entry mới hoặc lần cập nhật plan; chưa có trace không chặn việc lập plan hôm nay.

## 6. Bổ sung đã chốt và triển khai ngày 13/10

- Lỗi chỉ sáng/không chiều được xác nhận là lịch trình theo ngày. Prompt hướng ngày trọn vẹn có sáng và chiều khi dữ liệu/cửa sổ phù hợp, không ép lịch chỉ sáng hoặc hoạt động cả ngày thành lịch đủ buổi. Adapter/UI giữ giờ; kiểm fixture không chứng minh chất lượng LLM.
- “Phòng tối đa 8” là sức chứa 8 người/phòng. Validator kiểm maxOccupancy riêng với priceAdults, kể cả trẻ em; API rooms null khi thiếu cơ sở giá, sửa cảnh báo giả “tạm một phòng”. Không thay công thức đã chốt bằng sức chứa.
- Người dùng chốt phân biệt mất hứng và dừng rõ. Đề xuất `../prd/update-archive/2026-10-13-khoi-goi-to-mo-khi-khach-mat-hung.md` đã áp dụng PRD trước code: một gợi ý mới có nguồn khi mất hứng, từ chối tiếp/dừng rõ không níu; chưa biết gì thì chủ động tra gợi mở. Không cấp consent lập lịch bằng gợi ý.
- Think từ cùng structured decision, không thêm model call; Act/Observe từ call/result, Observe phát khi từng call xong. UI thay cùng group, bỏ khung v2 ba bước. Giải thích có con số/giá/link/secret chưa kiểm bị bỏ khỏi tiến trình mà không phá câu trả lời.
- Prompt kể chuyện v2 đã có từ trước; giữ và bổ sung khơi tò mò, chưa có trace đầy đủ để kết luận lỗi liệt kê của người dùng đã được tái hiện/khắc phục bằng model thật.
- Bằng chứng kỹ thuật và các giới hạn mới ghi trong history triển khai, không lấy số chạy cũ làm kết quả mới. Không chuyển mặc định v2/deploy; người dùng bật v2 để eval.

## 7. Web mặc định v2 theo chỉ đạo tiếp theo

Người dùng yêu cầu chuyển ngay, sau đó thu hẹp chỉ web Next.js để tự test, không dùng Streamlit. Đề xuất `../prd/update-archive/2026-10-13-nextjs-mac-dinh-assistant-v2.md` đã áp dụng: mặc định v2 dù không có env; v1 là override tường minh. Phạm vi này thay quyết định “chưa chuyển mặc định” của task trước, không coi E12 đã đạt, không triển khai archive/Streamlit hay ngừng backend v1. Kiểm provider mặc định, build không đặt env và browser gọi endpoint v2.
