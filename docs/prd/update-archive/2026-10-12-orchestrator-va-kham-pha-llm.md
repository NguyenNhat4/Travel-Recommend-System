# Một orchestrator làm đầu mối hội thoại; khám phá theo ý định người dùng

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-12
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-06), §3 (AC-AGT-06, AC-AGT-07, AC-AGT-08);
  `docs/prd/architecture.md` §3 (sơ đồ LangGraph, Tiêu chuẩn Grounding); `docs/prd/deployment-plan.md` §2 (biến môi
  trường)
- Mã FR/NFR: FR-AGT-01, FR-AGT-06, FR-AGT-07, AC-AGT-06, AC-AGT-07, AC-AGT-08, NFR-REL-01
- Plan chi tiết: `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` (mục 3–4, bước B5–B10)

## Lý do

Chat thử 12/10: "hà nội" → "ngoài ra còn gì nữa" (hoặc "đi rồi") trả lại đúng 4 thẻ cũ. Đo thêm cùng ngày: "khách sạn thứ
hai giá bao nhiêu" và "mấy chỗ lúc nãy cái nào có hồ bơi" đều tìm lại và trả về khách sạn khác, không xét các thẻ vừa
xem. Lỗi kiểu này lặp đi lặp lại vì:

1. Lượt khám phá chọn thẻ bằng hai câu tìm cố định ("điểm tham quan nổi tiếng", "khách sạn được đánh giá tốt"), không
   theo câu hỏi, nên hỏi gì cũng ra cùng 4 thẻ.
2. LLM hiểu được "muốn thêm", "chê nơi vừa xem", "rẻ hơn", "cái thứ hai", nhưng không có kênh để báo cho code. Code đoán ý
   bằng khoảng 30 regex, và mỗi lần chat thử lại phải vá thêm một luật.
3. Mỗi tin chỉ đi được một nhánh. Câu hỏi thứ hai trong cùng tin thành nút gợi ý, không được trả lời.
4. AC-AGT-06 viết như một kịch bản dài (khoảng 6.500 ký tự), nên mỗi câu trong đó thành một luật cứng.

Phần không lệch PRD đã làm (2026-10-12, `history/2026-10-12-nho-ket-qua-da-xem-b1-b3.md`):

- câu "rẻ hơn" của vé (AC-AGT-08);
- trí nhớ "đã cho xem" (`shown`, chỉ cập nhật ở `finalize`);
- khối "đã gợi ý" trong ngữ cảnh mọi lời gọi LLM (`architecture.md` §3 "Ngữ cảnh cho LLM").

Đề xuất này là phần còn lại: **orchestrator quyết cần làm gì; code bảo đảm thực thi đúng phạm vi và trả dữ liệu đúng.**

## Nội dung đề xuất

### 1. `requirements.md` FR-AGT-06 — thêm một gạch đầu dòng

> Trợ lý nhớ những gì đã gợi ý trong hội thoại (thẻ, vé, lịch) và tự quyết tìm gì theo câu hỏi. Nơi đã xem có được hiện
> lại hay không là theo ý người dùng:
> - muốn thêm thì trả nơi chưa giới thiệu trong cùng phạm vi, hết thì nói rõ;
> - hỏi về các thẻ vừa xem thì chỉ xét đúng các thẻ đó, và tra lại thông tin của chúng ngay lượt đó;
> - muốn rẻ hơn hoặc đắt hơn thì so với thẻ đang nói, giữ các điều kiện người dùng chưa đổi, không có thì nói rõ;
> - câu hỏi mới vẫn có thể gặp lại nơi đã xem nếu khớp;
> - chê một nơi không cần nêu tên.
>
> Một tin hỏi nhiều việc được trả lời đủ trong một câu trả lời, trừ yêu cầu lập lịch. Ví dụ: giá vé và một điểm đến; hoặc
> "đi đâu vé rẻ, chỗ đó có gì chơi", khi việc sau cần kết quả của việc trước.

### 2. `requirements.md` AC-AGT-06 — viết lại ô "Kết quả mong đợi" theo nguyên tắc kiểm được

**Hiện tại:** một kịch bản theo từng câu ("xin chào", "không biết" lần 1/2/3, "cứ chọn đại", 2 + 2 thẻ, "ok"…), mỗi câu là
một hành vi cố định.

**Thay bằng** các nguyên tắc dưới đây:

- Không bịa sản phẩm, giá. Thông tin sản phẩm trong câu trả lời chỉ lấy từ dữ liệu tra trong chính lượt đó.
- Không hỏi thông tin chuyến hay hiện form khi chưa đồng ý lập lịch.
- Chỉ coi là đồng ý lập lịch khi người dùng trả lời đúng lời mời đang chờ, tự xin lập lịch, nêu thông tin chuyến hoặc xin
  form. Người dùng từ chối thì lời mời hết hiệu lực: "ok" sau đó không phải đồng ý, nút lập lịch vẫn bấm được.
- Lặp thẻ đúng theo ý định như FR-AGT-06.
- Trả lời đúng và đủ các câu được hỏi.
- Tối đa một câu hỏi lại mỗi lượt.
- Không gợi ý lại nơi bị chê.
- Số thẻ không vượt giới hạn (mục "Cần chốt kèm" bên dưới).
- Mục tiêu thời gian phản hồi đặt lại sau khi đo.

Các nước đi cụ thể hiện có trở thành case trong bộ đo hội thoại nhiều lượt (plan B11–B12), không còn là luật trong code.

### 3. `requirements.md` AC-AGT-07 — đổi một câu, phần còn lại giữ nguyên

AC-AGT-07 quy định cách trình bày câu trả lời khám phá. Với orchestrator, LLM chọn thẻ, nên chỉ câu về lý do chọn thẻ
phải đổi.

**Hiện tại** (đoạn "Thẻ"):

> lý do chọn thẻ (nhiều đánh giá nhất, điểm cao nhất, giá thấp nhất, vào cửa tự do, gần nơi được hỏi) do code tính trên
> toàn bộ kết quả Search, LLM chỉ viết câu và không viết số.

**Thay bằng:**

> LLM chọn thẻ trong kết quả tra của chính lượt đó. Nhãn so sánh (nhiều đánh giá nhất, điểm cao nhất, giá thấp nhất, vào
> cửa tự do, gần nơi được hỏi) do code tính trên toàn bộ kết quả và gắn sẵn; LLM chỉ được nói nhãn đó cho đúng thẻ code
> đã gắn. LLM không viết số; số do code điền.

**Giữ nguyên, vẫn áp dụng:**

- **Nút gợi ý:** tối đa 3, các hướng khác nhau, không lặp nút lượt trước; LLM đề xuất, code kiểm từng nút và thay nút không
  đạt.
- **Thẻ:**
  - mỗi thẻ đứng ngay sau câu đầu tiên nhắc tới nó và có câu dẫn riêng;
  - một cụm khen dùng tối đa một lần;
  - không liệt kê thẻ thành khối không có câu dẫn.
- **Giọng điệu:** tối đa một câu hỏi mỗi lượt, không hỏi lại cùng một câu, nói thẳng điều không kiểm được.
- **Các nhóm người dùng:** khó hiểu, khó tính (không gợi ý lại nơi bị chê), cộc lốc, không quen công nghệ, ngoài phạm vi.

### 4. `requirements.md` AC-AGT-08 — giữ nguyên, ghi rõ thêm một câu

AC-AGT-08 ghi "câu trả lời do code viết từ dữ liệu, LLM chỉ hiểu câu hỏi". Thêm vào đoạn "Chung":

> Tin chỉ hỏi vé thì câu vé do code viết là toàn bộ câu trả lời, như hiện nay. Tin vừa hỏi vé vừa hỏi việc khác thì câu
> vé được chèn nguyên văn vào câu trả lời chung; LLM chỉ viết phần dẫn và không viết số của vé. Tin hỏi vé nhiều tuyến
> cùng thiếu thông tin (ví dụ chưa biết nơi đi) thì chỉ hỏi một câu; các tuyến còn lại được trả lời khi người dùng trả lời
> câu đó.

### 5. `architecture.md` §3

- **Sơ đồ:** `ClassifyTurn` thành **Orchestrator** — một LLM làm đầu mối hội thoại. Mỗi vòng nó chọn một trong bốn việc:
  - **trả lời** ngay (trò chuyện, giải thích khả năng, nhắc lại đã gợi ý gì);
  - **hỏi lại** một câu;
  - **chuyển vào nhánh lập lịch** hiện tại, giữ nguyên `extract` → … → `compose` → `narrate`;
  - **yêu cầu thực thi** một hoặc nhiều việc có cấu trúc: loại việc, ý định (`new`, `more`, `about_shown`, `cheaper`,
    `dearer`), mã thẻ đang nói tới, phạm vi và điều kiện tìm. Kèm theo là các việc còn chờ kết quả của vòng này.
- **Thực thi do code.**
  - `explore` là nhóm tool chỉ đọc: tìm, tra lại chi tiết, liệt kê theo giá, tìm quanh một nơi. Không có LLM riêng.
  - `fare` tra và so vé như hiện tại.
  - Code giữ kết quả đầy đủ; orchestrator nhận bản rút gọn: mã `#n`, dữ kiện cần thiết, số kết quả còn lại.
  - Việc độc lập chạy song song; việc cần kết quả trước thì chạy ở vòng sau.
  - Tin chỉ hỏi vé không có việc nào còn chờ thì trả câu vé ngay, không thêm lời gọi LLM.
  - Phanh do code: tối đa 3 vòng thực thi, ngân sách thời gian, trần lời gọi tool, chặn việc trùng.
- **Gác cổng bằng code** trước `finalize`:
  - thẻ và link chỉ cho sản phẩm tra trong lượt;
  - mọi số liệu sản phẩm trong câu LLM viết đi qua placeholder gắn với sản phẩm đã tra trong lượt, ở mọi lượt, bất kể
    lượt gọi bao nhiêu tool; câu vé do code viết được miễn;
  - lặp thẻ theo ý định, không cấm chỉ vì đã xem;
  - giới hạn số thẻ, nhãn "nhất", điền giá và giờ;
  - một câu hỏi mỗi lượt, kể cả khi nhiều việc cùng cần hỏi lại. Câu hỏi lại chỉ bị bỏ khi việc sau là cập nhật của
    đúng yêu cầu đó (ví dụ vừa có nơi đi); hai yêu cầu khác nhau, như hai nơi đi hay hai ngày bay, đều được trả lời;
  - chưa đồng ý lập lịch thì không vào nhánh lập lịch, không hỏi thông tin chuyến. Đồng ý được kiểm từ trường có cấu
    trúc: trả lời lời mời đang chờ, tự xin lập lịch, nêu thông tin chuyến, xin form. Từ chối lời mời thì lời mời hết
    hiệu lực ngay trong lượt đó.
- **"Đã xem"** chỉ cập nhật ở `finalize` theo response cuối. Kết quả vừa tìm mà chưa hiện thì chưa tính.
- **Tiêu chuẩn Grounding:**
  - Câu "lý do chọn thẻ do code tính, LLM chỉ viết câu và số được code điền" thay bằng: "LLM chọn thẻ trong kết quả tool
    của chính lượt đó và chỉ nhắc sản phẩm qua mã ngắn `#n`. Code kiểm mã, luật lặp theo ý định, tính nhãn 'rẻ nhất',
    'nhiều đánh giá nhất', điền giá và số."
  - Thêm ranh giới: "Câu trả lời không gọi tool chỉ được nhắc lại đã gợi ý gì (tên, lúc nào). Thẻ, link, giá và mọi
    thông tin khác của sản phẩm (giờ mở, tiện ích, còn chỗ…) phải lấy từ kết quả tool của chính lượt đó; hỏi về thẻ đã
    xem thì tra lại đúng các thẻ đó. Phần 'đã gợi ý' trong ngữ cảnh chỉ để hiểu người dùng nói tới sản phẩm nào. Mọi số
    liệu sản phẩm (giá, giờ, điểm, khoảng cách) trong câu LLM viết đi qua placeholder gắn với sản phẩm đã tra trong lượt
    và do code điền, kể cả khi lượt đã gọi tool khác; câu vé do code viết được miễn. Số so với một mốc (khoảng cách tới
    một nơi, chênh giá với một thẻ) ghi rõ mốc; code chỉ điền khi xác định được đúng một giá trị." Ranh giới này đi cùng
    câu đang có ở mục "Hội thoại": giá và tình trạng còn chỗ luôn được tải lại.
  - Câu vé vẫn do code viết. Orchestrator chỉ viết phần dẫn và chèn nguyên văn khối câu vé; code kiểm khối được chèn đủ.
  - Phần còn lại giữ nguyên: grounding 100%, `compose` tất định, mọi nhánh qua `finalize`.

### 6. Model riêng cho orchestrator

- Orchestrator dùng một model mạnh hơn các bước khác; người dùng chọn **GPT-6.1 Sol** của OpenAI.
- Các bước còn lại (trích ý định, lập tool plan, lọc trùng, viết lời lịch trình) giữ model nhanh hiện tại.
- `deployment-plan.md` §2 thêm ba biến:
  - `ITINERARY_ORCHESTRATOR` (`off|on`, mặc định `off`);
  - `ITINERARY_ORCHESTRATOR_MODEL` (model ID, bỏ trống thì dùng model chung);
  - `ITINERARY_ORCHESTRATOR_PROVIDER` (`gemini|openai|anthropic`).

  Không bí mật; khoá của provider đi theo biến khoá hiện có.
- Nhiệt độ, mức reasoning và ngân sách thời gian của lượt đặt bằng số đo, so với model chung.

### Đã chốt kèm (Nguyễn Minh Nhật, 2026-10-12)

1. **Số thẻ mỗi lượt khám phá.** Người dùng đã nêu "tối đa 3 điểm tham quan". Đề xuất:
   - tối đa 3 điểm tham quan hoặc tour;
   - 2 khách sạn khi hỏi chung, 4 khi hỏi riêng chỗ ở;
   - orchestrator được chọn ít hơn khi câu hỏi hẹp.

   Hiện nay là 2 + 2, hoặc 4 khi hỏi riêng chỗ ở.
2. **Phạm vi "đã xem" khi người dùng muốn thêm.** Đề xuất: cả hội thoại, theo điểm đến + loại sản phẩm.
3. **Số việc tối đa mỗi vòng thực thi.** Đề xuất 3.
4. **Số vòng thực thi tối đa mỗi lượt.** Đề xuất 3.

## Thay đổi source sau khi chốt

Mọi code mới nằm sau cờ `ITINERARY_ORCHESTRATOR=off|on`. Mặc định giữ hành vi cũ cho tới khi bộ đo (plan B12) đạt ngưỡng.

- `src/backend/app/agents/steps/jobs.py` (mới): thực thi `explore`/`fare` theo ý định, cấp mã `#n`, rút gọn kết quả, giữ
  con trỏ để lấy tiếp kết quả.
- `src/backend/app/domain/itinerary/gatekeeper.py` (mới): gác cổng.
- `src/backend/app/agents/steps/consent.py`: đồng ý lập lịch từ trường có cấu trúc; lời mời đang chờ đổi theo bảng của
  plan (4.4 luật 7).
- `src/backend/app/core/config.py`, `main.py`, `infrastructure/llm/client.py`: cấu hình và dựng model riêng cho
  orchestrator; `.env.example`, `src/backend/README.md`.
- `src/backend/app/agents/models.py` (`OrchestratorTurn`, `Job`), `agents/steps/prompts.py` (`ORCHESTRATOR_PROMPT`),
  `agents/steps/shown.py` (nhận mã của lượt và điều kiện đã sinh ra thẻ).
- `src/backend/app/agents/nodes.py`, `agents/graph.py`, `agents/routing.py`: node `orchestrate`, `run_jobs`, `gatekeep`,
  đường tắt vé, phanh.
- `src/backend/app/agents/steps/messages.py`: lời mời lập lịch, câu tạm biệt, tiêu đề khám phá do orchestrator viết; câu
  cố định chỉ còn là dự phòng.
- Contract không đổi: vé và khám phá dùng chung `searchResults`.
- Tài liệu:
  - `docs/spec/agent/langgraph-nodes.md`, `state-fields.md`;
  - `docs/spec/agent/nghiep-vu/tro-chuyen-va-kham-pha.md`, `vong-doi-mot-luot.md`;
  - `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`;
  - `docs/spec/agent/working-context.md` §3;
  - skill `building-itinerary-agent` bước 3.
