# Kịch bản thuyết trình Itinerary Agent

Lời nói kèm theo bộ slide [presentation-slides.html](presentation-slides.html) (14 slide, mở bằng trình duyệt, phím ←/→ để chuyển). Phục vụ FR-AGT-01…05, NFR-REL-01 trong `docs/prd/requirements.md`. Số liệu lấy từ `src/evaluation/reports/eval-2026-09-24-golden.md` (commit `601f112`); chạy golden mới thì cập nhật slide 11–12 và phần tương ứng ở đây.

Thời lượng khoảng 15 phút + hỏi đáp. Câu trong ngoặc kép là gợi ý nói, không cần đọc nguyên văn.

---

## Slide 1 — Mở đầu (30 giây)

"Hôm nay em trình bày Trợ lý lập lịch trình, tức Itinerary Agent của V-OTA. Người dùng chỉ cần gõ một câu, ví dụ *lập lịch trình 3 ngày 2 đêm ở Nha Trang ngân sách 5 triệu*, là nhận được lịch trình theo từng ngày. Điểm quan trọng nhất: mỗi thẻ sản phẩm trong lịch trình đều có mã sản phẩm thật trong catalog, giá thật, bấm vào là mở được trang chi tiết."

Chỉ vào thẻ có viền nét đứt: "Viền nét đứt nghĩa là sản phẩm này lấy từ Search, không phải do LLM viết ra."

## Slide 2 — Bài toán (1 phút)

"PRD giao cho agent năm yêu cầu." Đọc lướt bảng bên trái, nhấn vào hai dòng:

- FR-AGT-01: hội thoại nhiều lượt, thiếu thông tin thì hỏi lại.
- FR-AGT-04: grounding 100%, không có sản phẩm nào không có thật.

Chuyển sang khung bên phải: "Tiêu chí nghiệm thu chính là đúng câu ví dụ ở slide trước. Ngoài ra có hai ràng buộc chung: grounding 100% và mục tiêu tổng thời gian phản hồi dưới 5 giây ở p95."

## Slide 3 — Chia vai LLM và backend (1,5 phút)

"Đây là nguyên tắc thiết kế quan trọng nhất, mọi quyết định phía sau đều xuất phát từ đây: **LLM hiểu ngôn ngữ, backend quyết định dữ liệu.**"

- Cột trái: "LLM chỉ làm bốn việc liên quan tới ngôn ngữ: hiểu người dùng muốn gì, khớp tên điểm đến khi người dùng viết khác catalog, viết câu hỏi lại, và trò chuyện hoặc từ chối."
- Cột phải: "LLM không bao giờ được tạo mã sản phẩm, tên hay giá, không tính tổng tiền, không xếp lịch, và không tự trả response ra ngoài."

"Nếu LLM hỏng thì sao? Agent vẫn trả câu cố định hoặc trạng thái FALLBACK, không bao giờ bịa để lấp chỗ trống."

## Slide 4 — Kiến trúc (1,5 phút)

Đi theo mũi tên từ trái sang phải: "Frontend gọi FastAPI qua ba endpoint trong contract: tạo lịch trình, bản stream SSE cho giao diện, và status. FastAPI chuyển vào LangGraph. Graph không gọi Search trực tiếp mà qua một gateway, gateway mới gọi Search, Recommendation và chi tiết sản phẩm, dữ liệu nằm ở Weaviate và Postgres."

Ba ô dưới:

- "Chỉ dựng một LLM client lúc app khởi động. Có key nào thì dùng provider đó, thứ tự Gemini, OpenAI, Anthropic."
- "Tắt được LLM bằng một biến môi trường: app vẫn chạy, chỉ có API lịch trình trả 503. Tiện khi demo không có key."
- "Hội thoại lưu *ý định* và lịch sử chat gần đây trong 24 giờ để hiểu các câu nối tiếp. Giá và tình trạng còn chỗ luôn tải lại, không tin bản lưu."

## Slide 5 — Graph mười node (2 phút)

"Graph có mười node, nhưng đừng nhớ mười cái tên. Nhớ bốn giai đoạn theo bốn dải màu: hiểu người dùng, lấy dữ liệu thật, soạn câu trả lời, và cửa ra."

Chỉ màu: "Node viền cam là node có gọi LLM: classify, converse, clarify. Tool viền cam nét đứt vì nó chỉ gọi LLM khi cần khớp tên điểm đến."

"Có một điểm hay bị hiểu nhầm: compose, node dựng lịch trình, **không gọi LLM**."

Theo đường xanh đậm: "Đây là luồng đầy đủ cho câu *Nha Trang 2 ngày*: intake, classify, tool, evaluate, compose, finalize. Nhìn bên phải: cả bốn node soạn câu trả lời đều đổ về một node finalize duy nhất."

## Slide 6 — `finalize` (1,5 phút)

"Cách dễ nhớ: như cổng an ninh sân bay. Khách đến từ nhiều quầy check-in, nhưng ai cũng phải qua đúng một cổng soi chiếu."

"Ở cổng này làm năm việc, mỗi việc đúng một lần cho mọi response: kiểm hình dạng theo contract, kiểm grounding, đo thời gian, lưu hội thoại và sinh câu hiển thị."

Sang khung đỏ: "Và finalize không chỉ đóng dấu, nó có quyền bác. Lịch trình nào có sản phẩm không nằm trong kết quả tìm kiếm sẽ bị thay bằng lỗi 500. Nghe thì lạ, nhưng thà backend tự nhận lỗi còn hơn đưa người dùng một lịch trình không có căn cứ."

"Nếu không có cửa ra chung thì mỗi node tự kiểm. Thêm node mới mà quên kiểm là có ngay một đường lách grounding."

## Slide 7 — Bốn đường chính (1 phút)

"Nhìn từ phía người dùng thì graph chỉ có bốn đường chính, mỗi đường là một kiểu trả lời:"

- "*chào bạn*: đi converse, chỉ trò chuyện, không đụng sản phẩm."
- "*đi 3 ngày*: đi clarify, thiếu điểm đến thì hỏi lại, không đoán."
- "*Nha Trang 2 ngày*: đi đủ tool, evaluate, compose, ra lịch trình có sản phẩm thật."
- "*Paris 2 ngày*: đi dead_letter, ngoài catalog nên trả lỗi 422 kèm danh sách điểm đến hỗ trợ."

Chốt: "Bốn đường khác nhau nhưng đều kết thúc ở finalize."

## Slide 8 — `compose` xếp lịch bằng luật (1,5 phút)

"Vì sao không để LLM xếp lịch? Vì cần kiểm chứng được: cùng một tập sản phẩm thì luôn ra cùng một lịch trình, test được bằng unit test, và không có cửa nào để LLM chèn sản phẩm lạ vào."

Lướt sáu luật, nhấn luật 2 và 4: "Khách sạn chọn giá thấp nhất; hoạt động rải vào ngày đang ít việc nhất, tối đa hai hoạt động một ngày, buổi sáng rồi buổi chiều. Ngày nào không có sản phẩm thì để trống và cảnh báo, không bịa bữa ăn hay giờ nghỉ."

"Giới hạn hiện tại: nhịp độ chuyến đi, tức `pace`, chưa ảnh hưởng tới cách xếp."

## Slide 9 — Contract response (1 phút)

"Response có bốn trạng thái nghiệp vụ: hoàn thành, cần hỏi thêm, không có kết quả và suy giảm. Tổng tiền do backend tính; thiếu giá thì tổng để trống kèm cảnh báo, không coi thiếu giá là 0."

"Lỗi đi riêng theo chuẩn Error Envelope. Đáng chú ý nhất là 422 cho điểm đến ngoài catalog: hội thoại vẫn tiếp tục được, người dùng chỉ cần chọn điểm đến khác."

## Slide 10 — Hội thoại nhiều lượt (1 phút)

Đọc theo bốn lượt: "Mỗi lượt chỉ sửa phần người dùng vừa đổi. Nói *đổi thành Đà Nẵng* thì chỉ đổi điểm đến, giữ nguyên số ngày và ngân sách."

Lượt 4: "Khi người dùng nói *bỏ khách sạn này*, LLM chỉ được chọn trong các sản phẩm đã hiển thị ở lượt trước. Mã lạ bị lọc bỏ, nên kể cả ở bước này LLM cũng không đưa được sản phẩm lạ vào."

## Slide 11 — Đánh giá (1,5 phút)

"Bọn em chạy bộ golden 75 case, thêm một lượt quét mọi điểm đến, tổng 124 lượt trên catalog thật."

"Ba chỉ số PRD bắt buộc đều đạt: grounding 100%, output đúng cấu trúc 100%, gọi tool đúng 100% so với ngưỡng 95%. 113 trên 124 lượt đạt kỳ vọng hành vi."

Chỉ biểu đồ, nói thẳng: "Về độ trễ: p50 là 3,8 giây, nhưng p95 là 5,3 giây, **vượt** mục tiêu 5 giây. Lưu ý lần chạy này dùng timeout LLM 30 giây để model có thời gian trả lời, rộng hơn ngân sách trong spec, nên con số chưa dùng để khẳng định đạt hay không đạt SLA."

## Slide 12 — 11 lượt FAIL (1,5 phút)

"Tin tốt: không lượt nào hỏng grounding. Lỗi nằm ở hai chỗ: hiểu ý người dùng và độ phủ dữ liệu."

Chọn nói ba nhóm:

- "Chuẩn hóa điểm đến: người dùng gõ *tphcm* hay *Mũi Né* thì agent chưa hiểu đúng."
- "Thiếu hoạt động: chuyến gia đình có trẻ nhỏ chỉ ra 0–1 hoạt động trong khi kỳ vọng ít nhất 3."
- "Không từ chối: yêu cầu *đặt phòng và thanh toán giúp tôi* phải bị từ chối nhưng agent lại hỏi thêm."

## Slide 13 — Theo dõi và chạy thử (1 phút)

"Muốn biết agent đã làm gì trong một lượt thì có ba chỗ xem: bảng trace trên Streamlit cho biết node nào chạy và mất bao lâu; LangSmith cho xem dữ liệu vào ra từng node; và X-Request-ID để nối trace với log backend."

"Một mẹo đọc trace: thấy node converse thì chắc chắn lượt đó không có sản phẩm, thấy compose thì chắc chắn đã có dữ liệu thật."

Nếu có thời gian thì chuyển sang demo trực tiếp bằng ba lệnh trên slide (xem mục Demo bên dưới).

## Slide 14 — Việc tiếp theo và hỏi đáp (1 phút)

"Hướng tiếp theo: giữ nguyên grounding 100%, kéo phần hành vi lên cùng mức." Đọc lướt danh sách: bảng alias điểm đến, đủ hoạt động cho chuyến gia đình, từ chối rõ yêu cầu đặt chỗ thay người dùng, không tự đặt ngày đi, đo lại độ trễ với timeout theo spec, và cân nhắc đưa `pace` vào bước xếp lịch.

"Em xin hết, mời mọi người đặt câu hỏi."

---

## Demo trực tiếp (tuỳ chọn, 3–5 phút)

Chuẩn bị trước buổi thuyết trình theo [README.md](README.md) mục "Chạy demo". Nên chạy thử một lượt trước để khởi động LLM client và kết nối database.

| Gõ | Muốn cho thấy |
|---|---|
| `chào bạn` | Trace chỉ có `converse`, không có `tool` |
| `đi 3 ngày` rồi `Nha Trang nhé` | Hỏi lại, rồi ghép intent qua hai lượt |
| `Nha Trang 3 ngày ngân sách 5 triệu` | Luồng đầy đủ, thẻ sản phẩm có `productId` |
| `đổi thành Đà Nẵng` | Chỉ điểm đến đổi, tìm lại từ đầu |
| `Paris 2 ngày` | 422 `UNSUPPORTED_DESTINATION` kèm danh sách điểm đến |

Demo gọi LLM thật và phát sinh chi phí. Không bật LangSmith khi chia sẻ màn hình trước người ngoài dự án.

## Câu hỏi dễ gặp

**Làm sao chắc LLM không bịa sản phẩm?** Có ba lớp. LLM không được viết vào vị trí sản phẩm; `compose` xếp lịch bằng luật từ danh sách candidate lấy từ Search; `finalize` kiểm lại mọi sản phẩm với candidate và bác cả response nếu có sai lệch. Golden đo grounding 100% trên 124 lượt.

**Sao không để LLM xếp lịch cho tự nhiên hơn?** Để kết quả tái lập được và kiểm được bằng test. LLM vẫn được viết phần mô tả không nêu tên sản phẩm.

**LLM chết thì sao?** Câu hỏi làm rõ và câu trò chuyện dùng câu cố định. Nếu chính bước `classify` lỗi thì trả 503 `LLM_UNAVAILABLE` theo contract, không trả lịch trình đoán mò.

**Độ trễ vượt 5 giây thì xử lý thế nào?** Số đo hiện tại dùng timeout demo 30 giây. Bước tiếp là đo lại với ngân sách của spec (classify 2 giây, compose 3 giây) trước khi kết luận.

**Giá trong lịch trình có đúng lúc thanh toán không?** Giá và `available` là snapshot lúc tìm. Checkout kiểm tra lại; hội thoại không bao giờ dùng giá đã lưu.

**Sao không hỗ trợ Paris hay điểm đến ngoài catalog?** Agent chỉ đề xuất những gì V-OTA bán được. Điểm đến ngoài catalog trả 422 kèm danh sách điểm đến hỗ trợ để người dùng chọn tiếp.
