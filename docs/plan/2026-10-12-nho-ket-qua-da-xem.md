# Agent có trí nhớ và một orchestrator làm đầu mối hội thoại

- Ngày: 2026-10-12
- Người yêu cầu / phân tích: Nguyễn Minh Nhật / Claude Code. Thực thi B5–B10: Codex, theo yêu cầu đã chốt ngày 2026-10-12.
- Phục vụ: FR-AGT-01, FR-AGT-06, FR-AGT-07, AC-AGT-05, AC-AGT-06, AC-AGT-08, NFR-REL-01 (`docs/prd/requirements.md`).
- Trạng thái:
  - B1–B3 xong (2026-10-12, `history/2026-10-12-nho-ket-qua-da-xem-b1-b3.md`).
  - B4: đã chốt và áp dụng PRD ngày 2026-10-12 bởi Nguyễn Minh Nhật; cả 4 điểm ở mục 8 theo mức đề xuất.
  - Sửa theo review cùng ngày (`history/2026-10-12-sua-plan-orchestrator-theo-review.md`): đường tắt vé theo việc còn
    chờ (4.5), ranh giới trả lời từ `shown` (4.4 luật 1), lấy tiếp kết quả (4.3), câu hỏi và lời mời có cấu trúc (4.4
    luật 7), AC-AGT-07 trong đề xuất.
  - Sửa theo review lần 2 (`history/2026-10-12-sua-plan-orchestrator-theo-review-2.md`): số liệu chỉ qua placeholder ở
    mọi lượt (4.4 luật 1), chỉ chèn khối vé còn hiệu lực và một câu hỏi (luật 6), bỏ lời mời thắng tạo lời mời (luật 7).
  - Sửa theo review lần 3 (`history/2026-10-12-sua-plan-orchestrator-theo-review-3.md`): chỉ thay câu hỏi lại của vé
    khi khai `replaces` và code xác nhận cùng yêu cầu (luật 6); placeholder so với mốc ghi rõ việc (luật 1).
  - B5–B10 hoàn thành sau cờ ngày 2026-10-12; xem `history/2026-10-12-ap-dung-orchestrator-b5-b10.md`.
  - B11–B13 chưa làm theo phạm vi đã chốt; cờ mặc định vẫn off.
- Hướng đã chọn (người dùng, 2026-10-12, `history/2026-10-12-chinh-thiet-ke-orchestrator.md`):
  - **Một orchestrator (LLM) làm đầu mối hội thoại.** Nó hiểu câu, trả lời, hỏi lại, hoặc yêu cầu thực thi.
  - **Code thực thi đúng phạm vi và trả dữ liệu đúng:** `explore` là nhóm tool, `fare` tính vé; code cũng gác cổng.
  - Lập lịch giữ nhánh hiện tại, kể cả `narrate`.
  - Không có worker `converse`, không có LLM riêng trong `explore`.
  - Đo và test hồi quy làm sau.
- Lệch PRD:
  - B5–B9 được phép theo đề xuất đã chốt, đã áp dụng vào PRD và chuyển vào `update-archive/` (AGENTS.md §8).
  - B1–B3 hiện thực đúng PRD hiện hành.

Đường dẫn code dưới đây tương đối với `src/backend/app/` trừ khi ghi đầy đủ.

## 0. Đọc trước khi làm

**Thứ tự.**

| # | Bước | Chờ chốt PRD? |
|---|---|---|
| 1 | B1 `cheaper` của vé | Không (FR-AGT-07 đã ghi "chuyến rẻ hơn") |
| 2 | B2 state `shown` → B3 khối ngữ cảnh chung | Không (`architecture.md` §3 "Ngữ cảnh cho LLM", "Hội thoại") |
| 3 | B4 tạo đề xuất PRD từ mục 6, hỏi các điểm ở mục 8, **dừng** | Tạo đề xuất |
| 4 | B5 thực thi việc + rút gọn kết quả → B6 gác cổng → B7 orchestrator → B8 vòng lặp → B9 câu cố định → B10 kiểm nhanh, tài liệu | Đã chốt |
| 5 | B11–B13 luật kiểm, bộ đo, chuyển mặc định, gỡ regex | Làm sau, khi người dùng yêu cầu test |

**Quy tắc làm việc** (AGENTS.md + memory người dùng):
- Đầu phiên: đọc theo AGENTS.md §1 (bảng "Itinerary Agent"); ghi xác nhận §1.3 trước lần sửa code đầu.
  Không dùng skill khi chưa được yêu cầu. B5–B10 cùng một task có entry lịch sử riêng.
- Không commit khi chưa được yêu cầu; commit đứng tên người dùng, **không** `Co-Authored-By`.
- Lúc code chỉ chạy `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain`; cả bộ
  backend để cuối (`WEAVIATE_URL` trỏ cổng đóng, `SEARCH_PREWARM=false`, ~25 giây).
- Chạy `inprocess` hoặc backend với `HF_HUB_OFFLINE=1` (embedding e5 local; thiếu thì treo do IPv6).
- Lấy bằng chứng (giá trị thô LLM, trace) trước khi sửa; lỗi chập chờn đo bằng `--repeat`.
- **Không vá hiểu câu bằng regex hay bảng từ khoá.** Luật code chỉ cho tiền, ngày, grounding, an toàn.
- Đổi prompt hoặc state lưu làm snapshot hành vi lệch: ghi lại bằng
  `HF_HUB_OFFLINE=1 .venv/bin/python -m src.backend.tests.unit.agents.behavior_snapshot.record [--only ...]` (cần
  `docker compose up -d --wait postgres weaviate`), đọc diff `snapshot.json` trước khi coi là xong.
- Mọi code mới sau cờ, mặc định giữ hành vi cũ tới khi đo (mục 4.7).

**Tái hiện một đoạn chat với LLM thật** (script để scratchpad, không thêm vào repo):

```python
# Bật ITINERARY_ORCHESTRATOR=on và các biến model/provider/reasoning trước khi chạy.
# PYTHONPATH=$PWD HF_HUB_OFFLINE=1 SEARCH_PREWARM=false .venv/bin/python repro.py '["hà nội","đi rồi"]' out.json
import asyncio, json, sys
from types import SimpleNamespace
from src.backend.app.core.config import Settings
from src.backend.app.main import _itinerary_runtime
from src.backend.tests.unit.agents.behavior_snapshot.record import inprocess_app

class RecordedModel:
    def __init__(self, inner):
        self.inner, self.outputs = inner, []

    def with_structured_output(self, schema):
        runnable = self.inner.with_structured_output(schema)
        async def ainvoke(prompt):
            result = await runnable.ainvoke(prompt)
            self.outputs.append({"schema": schema.__name__, "output": result.model_dump(mode="json")})
            return result
        return SimpleNamespace(ainvoke=ainvoke)

async def main(turns, out):
    rows, conversation = [], None
    async with inprocess_app() as app:
        settings = Settings()
        assert settings.itinerary_orchestrator == "on"
        recorder = RecordedModel(app.state.itinerary_orchestrator_llm)
        app.state.itinerary_orchestrator_llm = recorder
        planner = _itinerary_runtime(app, settings, None).planner()
        for query in turns:
            state = await planner.ainvoke({"query": query, "conversation_id": conversation, "language": "vi"})
            conversation = state["conversation_id"]
            rows.append({key: state.get(key) for key in
                         ("query", "events", "response", "shown", "turn_jobs", "latency_ms", "http_status")})
    with open(out, "w") as f:
        json.dump({"turns": rows, "llm": recorder.outputs}, f, ensure_ascii=False, indent=1, default=str)

asyncio.run(main(json.loads(sys.argv[1]), sys.argv[2]))
```

Dùng composition root thật để cờ và model riêng có hiệu lực. Harness snapshot cũ mặc định tắt orchestrator.
Giữ log chạy cạnh JSON: lỗi provider có thể xảy ra trước khi có đầu ra model để ghi vào `llm`.

## 1. Bối cảnh và bằng chứng

Luật kiểm "kết quả lượt này trùng lượt liền trước" trên 57 hội thoại của
`src/backend/tests/unit/agents/behavior_snapshot/snapshot.json`: 15/39 cặp lượt lặp; 11 lặp hợp lý (hỏi tiếp về đúng
chuyến vừa xem, thẻ cũ vẫn đúng tiêu chí mới, lịch giữ hoạt động khi đổi vé). Lỗi thật cùng một kiểu, câu nói về **quan
hệ với kết quả lượt trước**:

| Hội thoại | Người dùng | Agent trả | LLM `classify` |
|---|---|---|---|
| Báo lỗi 1 | "hà nội" → "ngoài ra còn gì nữa" | Đúng 4 thẻ cũ | Không có trường "muốn thêm" |
| X13-che lượt 2 | "cứ chọn đại" (chọn Nha Trang) → "chán, đi rồi" | 4 thẻ cũ, lời dẫn "thay vì lặp lại những điểm đã đi…" | Không có trường chê; `_REJECT` cần tên nơi |
| Báo lỗi 2 | "hà nội" → "đi rồi" | 4 thẻ cũ, lời dẫn "Ừ, bạn đi Hà Nội rồi, mình nhớ" | Thô: `route=explore, city="Hà Nội"` |
| messy-M11 lượt 3 | "chuyến bay về mấy giờ" → "có chuyến nào rẻ hơn ko" | Câu y hệt từng chữ | Hiểu `fare.cheaper=true`, code bỏ qua |

Đo thêm 12/10 trên code hiện tại (B1–B3, LLM thật, script mục 0), câu hỏi về thẻ vừa xem sau "hà nội" (2 điểm tham
quan, 2 khách sạn: Luxury Backpackers, Proverb Hotel Hanoi):

- "khách sạn thứ hai giá bao nhiêu" → tìm lại, ra 4 khách sạn khác, báo giá của Classyc Hotel thay vì Proverb Hotel.
- "mấy chỗ lúc nãy cái nào có hồ bơi" → 4 khách sạn mới có hồ bơi, bỏ qua Proverb Hotel (có hồ bơi).
- Ở Đà Nẵng, "giá tính theo người hay theo gói" → tìm lại đúng 4 thẻ cũ, trả lời theo thẻ vừa tra.

Cả ba đều đi `explore` tìm lại, nên giá là giá mới, không lấy từ khối `already_shown`. Lỗi là sai phạm vi: không có cách
nói "chỉ xét đúng các thẻ này" (`about_shown`, 4.3).

Báo lỗi 2 tái hiện trên `feat/agent` `e4f0bb86`. Cùng đoạn chat, "tạm biệt", "khách sạn", "Đà Nẵng có gì chơi?" sai ở
môi trường người dùng nhưng đúng trên local: môi trường đó chưa có luật dừng (`8a1c4d35` có ở `release-mvp-v2`, chưa ở
`main`), dữ liệu giá khác local → deploy `release-mvp-v2` rồi test lại.

## 2. Nguyên nhân gốc

**Lỗi lặp:**
1. `CARRIED` (`agents/steps/phase.py:20`) không lưu thẻ/vé đã hiện; `pick()` (`agents/steps/exploration.py:328`) dùng
   hai câu tìm cố định ("điểm tham quan nổi tiếng", "khách sạn được đánh giá tốt"), 50 kết quả mỗi loại → cùng 4 thẻ.
2. `TurnRoute` (`agents/models.py:95`) chỉ có `route`, `place`, `city`, `focus`, `price`, `fare`, `plan_request`,
   `form_request`, `other_questions`: LLM hiểu mà không truyền được "muốn thêm / chê".
3. Chê nơi bằng regex `_REJECT`/`rejected_places` (`agents/steps/classification.py:37`, `:84`).
4. Ghi chú lượt khám phá chỉ ghi tên 3 thẻ (`agents/steps/turn_notes.py` `NOTE_CARDS = 3`); ghi chú lịch trình chỉ "gửi
   lịch trình Hà Nội 3 ngày", sản phẩm chỉ ở `previous_selection` của lịch gần nhất.
5. `fares.answer_text` (`agents/steps/fares.py:162`) chỉ xét `cheaper` ở nhánh `else` cuối; có ngày đi thì bỏ qua.
6. Snapshot chỉ kiểm "không đổi"; X13 và M11 được ghi với hành vi sai.

**Cứng nhắc nói chung:** AC-AGT-06 là kịch bản 6.524 ký tự (mỗi câu thành một luật); vòng chat thử → vá (~20 commit
`fix(agent)` và 7 đề xuất PRD agent trong 10–12/10, 47 chú thích "chat thử/LLM thật/kịch bản"); LLM chỉ viết lời
(`architecture.md` §3 "lý do chọn thẻ do code tính"; `agents/steps/messages.py` 942 dòng câu cố định); ~30 regex đoán ý
(`consent.py` `_YES` `_PLAN`; `classification.py` `_REJECT` `_ELSEWHERE` `_DELEGATE` `_OPTION_PICK`; `exploration.py`
`_HOTEL_FOCUS` `_WHERE` `_POOL` `_AROUND` `_PRICE_ASKED` `_NEAR_PHRASE`; `changes.py` 7; `tool_planning.py` `_GOLF`); skill
`building-itinerary-agent` bước 3 "ưu tiên luật tất định hơn LLM". `classify` chọn đúng một nhánh mỗi tin: câu hỏi thứ hai
thành nút gợi ý (`other_questions`). LangGraph không phải nguyên nhân (~190 dòng framework so với 6.807 dòng
`agents/steps/` và 2.525 dòng `domain/itinerary/`).

## 3. Kiến trúc đích

```
Tin nhắn
  │
intake ── nạp hội thoại, shown; dựng khối ngữ cảnh (code, 4.1)
  │
luật trước LLM ── code, giữ nguyên: guardrails, luật dừng, đổi khách sạn/chuyến bay, chọn phương án, nút vé
  │
ORCHESTRATOR (LLM) ── đọc tin nhắn + ngữ cảnh; mỗi vòng trả ĐÚNG MỘT hành động:
  ├─ answer: tự viết câu trả lời (trò chuyện, giải thích khả năng, nhắc lại đã gợi ý gì) ──────┐
  ├─ ask: một câu hỏi lại có khai loại (question.about) + nút ─────────────────────────────────┤
  ├─ plan: code kiểm đồng ý (plan_reason, pending_offer) rồi vào nhánh lập lịch hiện tại       │
  │        extract → clarify | tool → evaluate → filter → compose → narrate ─► finalize        │
  └─ execute: 1..N việc độc lập (explore | fare), mỗi việc có intent, refers_to, phạm vi;      │
     kèm pending (việc còn chờ kết quả vòng này) và fare_only                                  │
        │                                                                                      │
     CODE thực thi song song (tool chỉ đọc; fare tính sẵn, khối câu vé do code viết)           │
        │  bản đầy đủ giữ ở code; orchestrator nhận bản rút gọn: #n + dữ kiện, unlisted,       │
        │  source_more                                                                         │
        ├─ đường tắt: vòng 1, một việc fare, fare_only, pending rỗng ─► câu vé ─► finalize     │
        ▼                                                                                      │
     ORCHESTRATOR (vòng sau, nhận results + pending): execute tiếp | answer | ask              │
        (phanh do code: ≤ 3 vòng thực thi, ngân sách thời gian, trần lời gọi tool, chặn việc   │
         trùng; chạm phanh thì buộc answer và nói rõ việc chưa làm)                            │
  ◄────────────────────────────────────────────────────────────────────────────────────────────┘
GÁC CỔNG (code, 4.4): mã thẻ có trong kết quả lượt này, số chỉ qua placeholder của mã đã tra (mọi lượt), luật lặp
                      theo intent, giới hạn số thẻ, nhãn "nhất", điền số, chỉ khối vé còn hiệu lực, một câu hỏi,
                      lời mời lập lịch (bỏ thắng tạo)
  │
finalize ── kiểm contract + grounding, lưu hội thoại, cập nhật shown (chỉ thẻ có trong response cuối)
```

| Việc | Ai làm |
|---|---|
| Hiểu câu; quyết trả lời, hỏi lại, lập lịch hay thực thi; chọn cách tìm (ý tìm, loại, phạm vi, sắp xếp, quanh nơi nào); khai việc còn chờ (`pending`), khi nào câu vé là đủ (`fare_only`), loại câu hỏi, lời mời lập lịch; chọn thẻ trong kết quả; viết lời (trừ lời lịch trình và khối câu vé) | **Orchestrator (LLM)** |
| Chạy tool; giữ kết quả đầy đủ và con trỏ; rút gọn; cấp mã `#n`; thực thi theo intent (loại thẻ đã xem, giá so với thẻ đang nói, giữ điều kiện cũ); khoảng cách; khối câu vé; đường tắt vé; kiểm đồng ý trước nhánh lập lịch, cập nhật `pending_offer`; luật lặp, ranh giới dữ kiện, giới hạn thẻ, nhãn "nhất", điền giá/giờ; phanh | **Code** |
| Lập lịch: trích intent, hỏi thông tin, tìm, xếp lịch, chọn vé, tổng tiền, viết lời lịch (`narrate`) | **Nhánh lập lịch hiện tại** (giữ nguyên) |

Orchestrator quyết **cần làm gì**; code bảo đảm **thực thi đúng phạm vi và trả dữ liệu đúng**. Gác cổng chỉ bắt
**bịa** và **sai phạm vi**. Lặp thẻ được xét theo ý định, không cấm chỉ vì thẻ đã nằm trong `shown`.

## 4. Thiết kế chi tiết

### 4.1. State `shown` và khối ngữ cảnh (đã làm ở B2–B3)

**`shown`** (`agents/steps/shown.py`; nằm trong `phase.CARRIED`, khai báo ở `agents/state.py`):
- Dạng: `{turn, seq, items: [{ref "#n", productId, taxonomy, name, place, turn, where, facts}]}`, mục cũ trước. `place`
  là điểm đến, hoặc tuyến `"<nơi đi>→<nơi đến>"` với vé.
- Ghi **một chỗ**: `finalize`, từ response đã qua kiểm tra. Chỉ thứ người dùng thật sự thấy mới được ghi; response lỗi
  giữ nguyên.
- Mã `#n` giữ suốt hội thoại: hiện lại thì giữ mã cũ, mã không dùng lại. Tối đa 40 mục mỗi `place`, bỏ cũ nhất.
- `facts` là một dòng thông tin lưu lúc hiện, để nhận ra sản phẩm. Không tra lại `get_product_detail` mỗi lượt (sẽ tốn
  tới 40 lời gọi tool); chỉ các mã người dùng hỏi tới mới được tra lại (`about_shown`, 4.3).
- Hội thoại lưu trước đó đọc ra rỗng (`phase.carried`).

**Khối `already_shown`** (`shown.context`, đưa vào `history.llm_context` ngay sau `known_constraints`), mỗi sản phẩm một
dòng, đủ để LLM nhận ra người dùng đang nói tới thẻ nào ("cái có hồ bơi", "cái rẻ nhất lúc nãy", "cái thứ hai", "mấy chỗ
đó") và chọn ý định, phạm vi. Khối là trí nhớ, không phải nguồn của câu trả lời: dữ kiện nêu ra phải tra lại (4.4 luật 1).

| Loại | Dòng |
|---|---|
| Chung | `#n`; tên ngắn (vé: hãng + số hiệu); loại; khu vực (quận/huyện, phường/xã) lấy từ địa chỉ; lượt và chỗ đã hiện ("khám phá", "vé máy bay", "lịch, ngày 2 chiều") |
| Khách sạn | giá kèm đơn vị theo `priceUnit`; hạng sao; điểm và số đánh giá làm tròn ("8.9 điểm (4,7k đánh giá)"); tối đa 5 tiện ích (khoá chuẩn của Search) |
| Điểm tham quan, tour, combo | "tham quan tự do, không mất vé", hoặc giá kèm đơn vị ("/khách", "/gói"); giờ mở ngắn; thời lượng; tối đa 3 nhãn |
| Vé máy bay | tuyến; ngày; giờ cất cánh; hạng nếu khác Phổ thông; giá/khách; "giá minh hoạ" nếu có |
| Lịch gần nhất (`current_plan`) | chỉ mã: "khách sạn #1 (đêm 1–2); ngày 1: sáng #2, chiều #3" |

- **Không đưa:** mô tả dài, địa chỉ đầy đủ, ảnh, tổng tiền lịch.
- **Giá lúc gợi ý:** trường `about` nói giá là giá lúc gợi ý, không phải ngân sách hay yêu cầu của người dùng. Prompt
  `extract` dặn không chép vào ràng buộc, vì `turn_notes.py` từng gặp LLM chép giá cũ thành ràng buộc.
- **Độ dài:** các dòng sản phẩm tối đa 2.000 ký tự; quá thì bỏ lượt cũ nhất trước, giữ lượt gần nhất và sản phẩm của lịch
  gần nhất.
- **Ghi chú lượt khám phá:** bỏ `NOTE_CARDS`. Ghi chú chỉ ghi số nơi ("giới thiệu 4 nơi ở Hà Nội (xem already_shown)"),
  tên nằm ở khối.
- **Chưa làm, để B6–B7:**
  - bỏ `productId` khỏi ngữ cảnh LLM: `previous_selection` vẫn kèm id vì `extract` (`exclude_products`) và Similar cần;
  - nhãn "rẻ nhất/nhiều đánh giá nhất" trong dòng, vì response chưa mang `reasons`;
  - ranh giới "nhắc lại / tra lại" (4.4 luật 1) nằm trong `ORCHESTRATOR_PROMPT`. `ABOUT` của khối giữ nguyên để cờ `off`
    không đổi payload (snapshot). Đo 12/10 ở mục 1: đường cũ hỏi về thẻ đã xem đều tìm lại, không dùng dữ kiện của khối.
    Chú thích trong `shown.py`, `history.py` đã sửa theo ranh giới (2026-10-12).

~~Thứ tự payload: tin nhắn hiện tại xuống cuối (tránh *lost in the middle*).~~ **Bác bỏ bằng số đo (2026-10-12, B3):**
đo lặp `classify` với payload cũ và mới trên 4 ca:

- "vé nha trang đi phú quốc bao nhiêu" hỏi lại loại vé (AC-AGT-08) 24/24 lần ở thứ tự cũ, còn 10/24 khi tin nhắn ở cuối;
- "đi đâu cũng được, miễn đắt nhất" sau một câu báo giá hiểu đúng 8/10, còn 4/10 khi tin nhắn ở cuối;
- thêm khối `already_shown` ngay sau `known_constraints` thì không đổi kết quả (20/30 cả hai; bản cuối 15/16 so với
  11/16).

Vì vậy giữ thứ tự cũ (tin nhắn đầu payload) và chỉ thêm khối. Orchestrator (B7) có prompt mới nên đo lại thứ tự cho nó
ở B12.

### 4.2. Orchestrator — đầu ra mỗi vòng

Thay `TurnRoute` khi cờ bật (4.7). Mỗi vòng LLM trả một `OrchestratorTurn` (`agents/models.py`), prompt
`ORCHESTRATOR_PROMPT` (`agents/steps/prompts.py`):

```python
class Job(StrictModel):
    kind: Literal["explore", "fare"]
    intent: Literal["new", "more", "about_shown", "cheaper", "dearer"] = "new"
    refers_to: list[str] = []            # mã #n đang được hỏi tới ("cái thứ hai", "chỗ đó", "rẻ hơn mấy cái này")
    continue_from: int | None = None     # số của một việc đã chạy trong lượt: lấy tiếp kết quả việc đó (4.3)
    replaces: int | None = None          # việc vé: thay câu hỏi lại của việc số đó khi vừa có thông tin nó thiếu (4.4 luật 6)
    # Phạm vi và điều kiện tìm (explore); để trống thì code lấy theo thẻ ở refers_to hoặc việc trước (4.3)
    destination: str | None = None       # điểm đến catalog; code đối chiếu như hiện tại
    taxonomy: Literal["attraction", "hotel", "combo", "golf"] | None = None
    query: str | None = None             # ý tìm như lời người dùng ("khách sạn có hồ bơi", "chỗ chơi buổi tối")
    near: str | None = None              # mã #n hoặc tên nơi để tìm quanh
    sort: Literal["relevance", "price_asc", "price_desc"] = "relevance"
    fare: FareQuestion | None = None     # kind="fare": giữ model hiện có

class Pending(StrictModel):
    kind: Literal["explore", "fare"]
    goal: str                            # việc cần kết quả vòng này mới làm được ("khám phá nơi có vé rẻ nhất ở việc 1")

class Question(StrictModel):
    # Không có số ngày, ngày đi, số người, ngân sách: chỉ nhánh lập lịch hỏi các câu đó, sau khi đồng ý (4.4 luật 7)
    about: Literal["destination", "trip_kind", "which_place", "other"]

class PlanOffer(StrictModel):
    destination: str                     # điểm đến catalog được mời lập lịch
    text: str                            # một câu mời; code quyết có chèn hay không (4.4 luật 7)

class OrchestratorTurn(StrictModel):
    action: Literal["answer", "ask", "plan", "execute"]
    # execute
    jobs: list[Job] = []                 # tối đa số việc mỗi vòng (mục 8)
    pending: list[Pending] = []          # việc còn chờ kết quả vòng này; rỗng: sau vòng này chỉ còn viết câu trả lời
    fare_only: bool = False              # câu vé do code viết đã trả lời đủ tin nhắn (đường tắt, 4.5)
    # answer / ask
    title: str | None = None
    message: str | None = None           # [Tên](#n), placeholder số (4.4 luật 1), [[fare_block:<i>]]
    refers_to: list[str] = []            # mã #n câu trả lời nói tới (code tra lại khi câu có dữ kiện, 4.4 luật 1)
    cards: list[str] = []                # mã #n hiện thành thẻ
    question: Question | None = None     # bắt buộc khi action="ask"
    offer: PlanOffer | None = None       # lời mời lập lịch
    suggestions: list[str] = []          # tối đa 3 nút
    # plan: vì sao người dùng đồng ý lập lịch; code kiểm trước khi vào nhánh (4.4 luật 7)
    plan_reason: Literal["accepts_offer", "asks_plan", "trip_details", "form"] | None = None
    # mọi hành động
    rejected: list[str] = []             # điểm đến hoặc mã #n bị chê ("đi rồi" sau lượt giới thiệu Hà Nội → ["Hà Nội"])
    declines_offer: bool = False         # "để sau", "chưa" khi đang có lời mời (`pending_offer`)
    stop: bool = False                   # không muốn đi hay lên lịch nữa (AC-AGT-01): như nhãn `stop` của `TurnRoute`
```

- **Không bắt mọi tin sinh danh sách việc.** Trò chuyện, giải thích khả năng và nhắc lại đã gợi ý gì là `answer`, một lời
  gọi LLM. Câu hỏi về dữ kiện của thẻ đã xem (giá, đơn vị giá, giờ, tiện ích, còn chỗ) là `execute` `about_shown` rồi mới
  `answer`, kể cả khi dòng trong `already_shown` đã có (4.4 luật 1). Như vậy cần hai lời gọi LLM, bằng `classify` +
  `explore` hiện nay.
- **`plan` không ghép với việc khác:** câu trả lời lập lịch là `COMPLETED`. Các ý khác trong cùng tin thành `suggestions`
  như `other_questions` hiện tại.
- **Việc còn chờ và đường tắt vé do orchestrator khai** (`pending`, `fare_only`). Code không suy từ số việc của vòng (4.5).
- **Map sang state hiện có** để nhánh lập lịch không đổi:
  - `plan` → `decision="travel"` sau khi code kiểm đồng ý theo `plan_reason` (4.4 luật 7); `plan_reason="form"` →
    `form_request`. Hai trường này thay `plan_request`, `form_request` của `TurnRoute`. Giữ `_YES`/`_PLAN` song song tới
    B13, vì chúng tránh một lượt chờ LLM;
  - `declines_offer` → xoá `pending_offer`, như `_not_knowing` hiện nay;
  - `rejected` → `_rejection_update`, thay `_REJECT`/`_ELSEWHERE`;
  - `stop` → như `classification.stopped`: không nút, không form, xoá lời mời; luật `_STOP` vẫn chạy trước LLM;
  - `declines_offer`, `stop` và `rejected` ghi vào state ngay ở `orchestrate`, nên mọi đường đều giữ, kể cả đường tắt vé.
    Câu mời và nút lập lịch do gác cổng xử lý, theo thứ tự ưu tiên ở 4.4 luật 7;
  - "cứ chọn đại": orchestrator tự chọn điểm đến trong `catalog_destinations` rồi `execute`; bỏ dần `_DELEGATE`.
- **Ngữ cảnh** là `llm_context` (4.1), tin nhắn đặt **đầu** payload (số đo B3), cộng dữ kiện code đưa vào thay cho
  worker `converse`:
  - `catalog_destinations`, `plan_consent`, `pending_offer`, `rejected_destinations`, `open_question`, `dont_know_level`,
    `previous_suggestions`, `today`;
  - từ vòng 2: `results` là kết quả rút gọn của các việc đã chạy (4.3), và `pending` của vòng trước;
  - chế độ buộc trả lời (4.5): thêm `unfinished`, các việc còn chờ chưa làm được.

### 4.3. Thực thi việc và rút gọn kết quả (code)

Module mới `agents/steps/jobs.py` nhận các `Job` của một vòng, chạy song song (`asyncio.gather`) qua
`ItineraryToolGateway`/`ToolExecutorPort`. Không thêm LLM ở đây.

**Explore** — code chọn thao tác theo trường của việc:

| Việc | Thao tác |
|---|---|
| `intent="about_shown"` | Tra lại chi tiết đúng các mã `refers_to` (`get_product_detail`; giá, còn chỗ mới nhất). Không tìm thêm. |
| có `near` | Lấy mốc (mã `#n`, hoặc tên tra catalog như `_place_candidates`), tìm trong điểm đến + loại, lọc `within_km`/`near_cards` theo bán kính hiện có (3 km điểm chơi, 1,5 km khách sạn), xếp theo khoảng cách. Mỗi việc đúng một mốc, ghi trong bản rút gọn. |
| `sort=price_asc/price_desc` | `list_products` theo giá như `price_listing` hiện tại |
| còn lại | `search_products(query, taxonomy, destination, …)` |
| `intent="more"` | Chạy lại điều kiện của việc đã sinh ra các thẻ trong phạm vi (`via`; không có thì điểm đến + loại + ý tìm của việc), **loại thẻ đã có trong `shown` ở phạm vi đó**, lấy theo thứ tự kết quả từ đầu: dùng hết ứng viên chưa hiện ở trang đã tải rồi mới tải trang kế (`offset`). Giá, còn chỗ là của lượt này. |
| `continue_from=k` | Lấy tiếp các mục việc `k` đã tìm mà chưa đưa vào bản rút gọn, không gọi tool; hết thì tải trang kế của nguồn (`offset + limit`; Search và `list_products` đều nhận `limit`/`offset`, Search trả `total`). |
| `intent="cheaper"/"dearer"` | Mốc là đúng một thẻ: thẻ có giá thấp nhất (hoặc cao nhất) trong `refers_to`, ghi trong bản rút gọn. Không có `refers_to` thì xét thẻ cùng loại của lượt gần nhất. Kết quả phải rẻ hơn (hoặc đắt hơn) hẳn mốc; giá của cả mốc lẫn kết quả đều tra lại ngay lượt này. **Giữ mọi điều kiện người dùng chưa đổi** (điểm đến, loại, ý tìm, quanh nơi nào) bằng cách lấy từ việc đã sinh ra các thẻ đó (`via`, bên dưới). |

**Fare:** gọi lại logic `fares.answer`. Kết quả gồm `fare_block` (tiêu đề + câu vé do code viết, nguyên văn), các chuyến
thành thẻ `flight`, nút và `pending_fare` như hiện tại. `status` của việc vé:
- `answered`: báo giá, kể cả "chưa có chuyến nào của tuyến";
- `asked`: code hỏi lại nơi đi, nơi đến hoặc loại vé, kèm nút như hiện tại;
- `unavailable`: không tra được catalog (câu `fare_unavailable`).

Cả ba đều là câu hoàn chỉnh do code viết. "Đi đâu cũng được" trả thêm nơi rẻ (hoặc đắt) nhất (`pending_fare.best`) để vòng
sau khám phá. Câu hỏi lại (`asked`) của một việc vé có thể bị việc sau trong lượt thay, khi việc sau khai `replaces` và
code xác nhận là cùng yêu cầu vừa có thêm thông tin; khi đó nó thành `superseded` và không được chèn (4.4 luật 6).

**Mã `#n` và "đã xem":**
- Sản phẩm đã có trong `shown` giữ mã cũ. Sản phẩm mới nhận mã tiếp theo từ `shown.seq + 1` trong lượt (`turn_codes`,
  `TURN_ONLY`).
- **Mã của kết quả vừa tìm chưa có nghĩa là đã xem.** `finalize` chỉ ghi vào `shown` những mã có trong response cuối.
- Mã cấp trong lượt mà không hiện thì không dùng lại (`seq` tăng qua chúng), để câu chữ không nhầm mã.
- `shown.record` (B2) nhận `turn_codes` và ghi thêm `via`: điều kiện của việc đã sinh ra thẻ, để `more`, `cheaper`,
  `dearer` lượt sau kế thừa.

**Bản rút gọn cho orchestrator** — code giữ bản đầy đủ trong `turn_jobs` (`TURN_ONLY`):

```
{job: 1, kind, intent, status: ok|empty|failed (vé: answered|asked|unavailable), scope: "Hà Nội · khách sạn · có hồ bơi",
 anchor: "#7 Hồ Gươm" (việc near) | "#5, giá thấp nhất trong các thẻ đang nói" (việc cheaper/dearer) | null,
 items: ["#12 Tên — <facts như 4.1>"], unlisted: 12, source_more: true, note: "đã loại 4 thẻ đã xem"}
```
- `anchor` là mốc duy nhất của việc; placeholder so với mốc (`distance`, `price_diff`) phải ghi số việc (4.4 luật 1).
- Tối đa K mục mỗi việc và tổng độ dài có trần (khởi đầu 8 mục, 1.500 ký tự mỗi việc, 3.000 ký tự mỗi vòng; đặt lại ở
  B12).
- **Còn kết quả**, hai loại khác nhau:
  - `unlisted`: số mục code đã tìm và đang giữ nhưng chưa đưa vào bản rút gọn. Lấy bằng `continue_from`, không tốn lời
    gọi tool.
  - `source_more`: nguồn còn trang chưa tải (`offset` + số mục trả về < `total`). `continue_from` chỉ tải trang kế khi
    `unlisted` đã hết.
  - Con trỏ (vị trí trong danh sách đã tìm, `offset` của nguồn) code giữ trong `turn_jobs`; LLM không ghi số trang.
  - Hết cả hai thì `status=empty`, `note` "đã hết kết quả trong phạm vi này".
- Nhãn code tính trên toàn bộ kết quả của việc ("rẻ nhất", "nhiều đánh giá nhất") gắn sẵn vào dòng.
- Việc `fare` trả `fare_block` kèm dòng tóm tắt (chuyến, ngày, giá) để orchestrator viết phần dẫn.

### 4.4. Gác cổng

Hàm thuần `domain/itinerary/gatekeeper.py` (unit test, bao phủ ≥ 80% theo DoD), chạy trên `answer`/`ask` trước
`finalize`; phần đồng ý của luật 7 cũng chạy cho `plan` trước khi vào nhánh lập lịch:
1. **Nguồn và ranh giới trả lời từ `shown`.**
   - Thẻ, link `[Tên](#n)` và placeholder (`[[price:#n]]`…) chỉ dùng được cho mã có trong `items` của một bản rút gọn
     **lượt này**, tức orchestrator đã thấy dòng của nó. Code map `#n` → `productId` và lấy sản phẩm từ bản đầy đủ. Link
     tới mã khác thì bỏ link, giữ tên; thẻ tới mã khác thì bỏ; placeholder tới mã khác là vi phạm (bên dưới).
   - **Nhắc lại, không cần tra:** được nói lúc trước đã gợi ý gì, bằng tên viết thường (không link) và nói rõ là lúc
     trước ("Lúc nãy mình gợi ý Proverb Hotel Hanoi và Luxury Backpackers"), và vị trí trong lịch ("khách sạn đêm 1–2").
   - **Phải tra lại ngay lượt này** (`execute` `about_shown`): mọi dữ kiện của sản phẩm, gồm giá, đơn vị giá, còn phòng,
     giờ mở, tiện ích, hạng sao, điểm, địa chỉ, khoảng cách, kể cả khi dòng trong `already_shown` đã có. Hiện lại thẻ cũng
     phải tra lại.
   - **Số liệu chỉ qua placeholder, ở mọi lượt.** Mọi số liệu sản phẩm trong lời orchestrator viết là placeholder gắn
     với mã có trong bản rút gọn của lượt này. Mỗi placeholder phải xác định đúng một phép tính:
     - **thuộc tính của chính sản phẩm:** `[[price:#n]]` (giá kèm đơn vị), `[[hours:#n]]`, `[[rating:#n]]`,
       `[[reviews:#n]]`, `[[stars:#n]]`. Hai việc trong lượt trả hai giá trị khác nhau cho cùng mã thì phải ghi thêm
       việc, ví dụ `[[price:job1:#n]]`;
     - **phép so với một mốc, bắt buộc ghi việc:** `[[distance:job2:#12]]` là khoảng cách từ #12 tới mốc của việc 2
       (`near`); `[[price_diff:job3:#12]]` là chênh giá giữa #12 và thẻ làm mốc của việc 3 (`cheaper`/`dearer`). Bản
       rút gọn của việc ghi rõ mốc (4.3). Ví dụ #12 có trong việc "gần Hồ Gươm" lẫn việc "gần Văn Miếu": chỉ mã việc
       cho biết điền khoảng cách tới nơi nào.

     Code chỉ điền khi xác định được đúng một giá trị: việc có trong lượt và còn hiệu lực, mã có trong kết quả của việc
     đó, việc có đúng một mốc. Không xác định được (thiếu mã việc ở phép so, việc không có mốc, mã không thuộc việc, hai
     giá trị khác nhau mà không ghi việc) thì là vi phạm và sửa như bên dưới; code không đoán. Sản phẩm thiếu giá trị
     (không có giờ mở) thì bỏ cụm, như `_fill` hiện nay. Lượt đã gọi tool không phải bằng chứng cho cả câu trả lời: luật
     này chạy bất kể lượt có bao nhiêu kết quả.
   - **Code kiểm** phần chữ orchestrator viết, sau khi bỏ placeholder, link và chỗ đặt khối vé:
     - có số tiền, giờ, điểm, số đánh giá, hạng sao hay khoảng cách viết thẳng là vi phạm. Nhận ra như
       `narration.RAW_MONEY` và `conversation._FACT_NUMBER`, thêm điểm, sao, km;
     - số người dùng vừa nêu cũng không được viết thẳng: nhắc lại mức giá người dùng muốn thì nói bằng chữ ("trong mức
       bạn muốn"), như `narrate` dùng `[[budget]]` thay cho số;
     - placeholder tới mã chưa tra trong lượt là vi phạm.
   - **Khối vé do code viết được miễn:** code thay `[[fare_block:<i>]]` sau bước kiểm, nên số trong khối không bị quét.
   - **Vi phạm thì sửa theo thứ tự**, mỗi bước tính vào phanh:
     1. mã ở placeholder hoặc `refers_to` chưa tra trong lượt: code chạy `about_shown` cho các mã đó;
     2. gọi orchestrator một lần ở chế độ buộc trả lời, kèm ghi chú vi phạm;
     3. vẫn vi phạm, hoặc hết phanh: lời dự phòng từ kết quả đã có (câu cố định hiện tại của khám phá và vé), như
        `narrate` dùng `fallback_message` khi gặp `raw_money`.
   - **`finalize` kiểm lại** cùng phép quét trên bản trước khi điền (gác cổng giữ bản này trong `TURN_ONLY`). Lọt tới đây
     là lỗi của gác cổng: ghi `assistant.grounding` mức WARNING, thay câu bằng lời dự phòng như nhánh guardrail, giữ các
     thẻ đã qua kiểm.
   - Dữ kiện không có số ("có hồ bơi", "gần biển") code không bắt được, nên dựa vào prompt và luật kiểm B11.
2. **Lặp theo intent, không theo `shown`:**
   - `new` được hiện lại nơi đã xem nếu khớp câu hỏi;
   - `more` không có thẻ đã xem trong cùng phạm vi;
   - `about_shown` chỉ đúng các mã ở `refers_to`;
   - `cheaper`/`dearer` chỉ thẻ rẻ hơn hoặc đắt hơn hẳn mốc giá của việc.

   Thẻ sai phạm vi thì bỏ, kèm lý do trong event.
3. **Giới hạn số thẻ** mỗi loại (mục 8; contract cho tối đa 4 mỗi loại).
4. **Nhãn "nhất"** chỉ khi code tính trên toàn bộ kết quả ra đúng thẻ đó. Câu nói "rẻ nhất/nhiều đánh giá nhất" cho thẻ khác
   thì thay bằng câu trung tính.
5. **Điền số:** placeholder của luật 1 (`_fill`, mở rộng cho các loại số ở đó), bỏ link tới mã không có thẻ
   (`_unlink_unknown`), bỏ cụm khen lặp (`once_praise`).
6. **Khối vé: chỉ chèn kết quả còn hiệu lực.**
   - **Bị thay** chỉ khi việc sau khai `replaces=k` **và** code xác nhận đó là cập nhật của cùng yêu cầu. Đủ ba điều kiện:
     1. việc `k` là việc vé `asked`, tức đang hỏi lại nơi đi, nơi đến hoặc loại vé;
     2. việc sau điền trường việc `k` đang hỏi (nơi đi, nơi đến, hoặc rõ loại vé: `kind_unclear` thành false);
     3. mọi trường `FareQuestion` khác (`origin`, `destination`, `anywhere`, `dearest`, `return_leg`, `other_days`,
        `cheaper`, `day`, `time_of_day`, `why`, `availability`) giống hệt việc `k`, kể cả trường để trống. Thêm ngày bay
        mà việc `k` không có là câu hỏi khác.

     Ví dụ vòng 1 hỏi lại nơi đi, vòng 2 có nơi đi và khai `replaces=1`: khối hỏi của vòng 1 không được chèn. Không đủ ba
     điều kiện thì code bỏ qua `replaces`, ghi event, và cả hai kết quả còn hiệu lực. Code **không** tự thay chỉ vì trùng
     điểm đến hay kiểu hỏi: "so vé từ Sài Gòn và Đà Nẵng ra Hà Nội" là hai yêu cầu, hai khối đều được chèn; hai ngày bay
     khác nhau cũng vậy. Khối trả lời (`answered`) không bao giờ bị thay. Khối bị thay không chèn, thẻ của nó không được
     chọn.
   - **Khối trả lời** (`answered`, `unavailable`) còn hiệu lực: mỗi khối có `[[fare_block:<i>]]` đúng một lần. Code thay
     bằng câu vé nguyên văn; thiếu thì chèn vào cuối. Lời dẫn không viết số của vé (luật 1).
   - **Khối hỏi lại** (`asked`) còn hiệu lực: chèn tối đa một, của việc có số nhỏ nhất. Đó là câu hỏi của lượt (luật 7);
     nút của nó ("Từ TP. Hồ Chí Minh") đứng trước nút của orchestrator, tổng tối đa 3. Các việc `asked` còn lại không
     chèn mà chuyển vào `waiting_jobs`.
   - **`waiting_jobs`** (`CARRIED`) giữ đúng một lượt:
     - lượt sau người dùng bấm nút trả lời: nút vé vẫn đi thẳng nhánh vé, không qua LLM (AC-AGT-08). Code điền trường vừa
       có (nơi đi, nơi đến hoặc loại vé) vào các việc chờ còn thiếu đúng trường đó, rồi chạy cùng lúc, mỗi việc một khối;
     - trả lời bằng chữ: orchestrator nhận `waiting_jobs` trong payload và tự chạy lại các việc đó;
     - việc còn thiếu trường khác thì hỏi tiếp, mỗi lượt một câu, và được ghi lại vào `waiting_jobs`;
     - hết lượt sau thì xoá, dù có dùng hay không.
   - `pending_fare` lưu theo khối hỏi lại được chèn; không có thì theo khối trả lời cuối cùng, vì hiện nay chỉ giữ một.
7. **Câu hỏi, lời mời và đồng ý lập lịch.** Kiểm trên trường có cấu trúc, không đọc câu chữ.
   - **Không hỏi thông tin chuyến, không form:**
     - `ask` phải có `question.about`. Loại này không có số ngày, ngày đi, số người, ngân sách: các câu đó và form chỉ
       do nhánh lập lịch hỏi, sau khi đồng ý.
     - `ask` thiếu `question` là đầu ra lỗi: thử lại, rồi lời dự phòng.
   - **Một câu hỏi mỗi lượt.** Có thể có ba câu: câu hỏi của một khối vé `asked` (luật 6), `question`, câu mời
     (`offer.text`). Có hơn một thì giữ một theo thứ tự đó. Câu mời bị bỏ thì vẫn giữ nút lập lịch.
   - **Lời mời** (`offer`) chỉ được chèn khi đủ năm điều kiện:
     - chưa đồng ý lập lịch;
     - điểm đến có trong catalog;
     - điểm đến không bị chê;
     - chưa mời bằng câu cho điểm đến đó (`offered_destinations`);
     - lượt này không có `declines_offer`, `stop` hay luật dừng.

     Không đủ thì chỉ giữ nút "Lập lịch <nơi>", như `_closing` hiện nay.
   - **`pending_offer`** đổi theo bảng dưới: xét từ trên xuống, gặp dòng khớp đầu tiên thì dừng. Bỏ lời mời thắng tạo lời
     mời trong cùng lượt. Gác cổng tính, `finalize` lưu qua `CARRIED`.
   - **Chỉ câu mời được chèn mới tạo lời mời đang chờ.** Nút "Lập lịch <D>" không tạo, cũng không khôi phục lời mời đã
     bỏ: người dùng vẫn bấm được (đi đường `asks_plan`), nhưng "ok" sau đó không còn là đồng ý. Đường cũ khác chỗ này:
     `_closing` đặt `pending_offer` ở mọi lượt khám phá chưa đồng ý, kể cả ngay sau khi người dùng từ chối.
   - **Đồng ý trước `extract`:** `plan` chỉ vào nhánh lập lịch khi đạt điều kiện ở bảng thứ hai. Không đạt thì không vào
     nhánh mà trả lời theo luật lời mời ở trên:
     - đủ năm điều kiện thì chèn câu mời cố định (`explore_offer`);
     - không đủ (đã mời, vừa từ chối) thì một câu cố định ngắn chỉ cách bắt đầu, kèm nút "Lập lịch <D>";
     - chưa có điểm đến thì hỏi điểm đến.
   - Câu chữ khác loại đã khai (khai `destination` mà lại hỏi số ngày) code không bắt được, nên đo bằng luật kiểm B11.

   | Trong lượt (xét theo thứ tự) | `pending_offer` sau lượt |
   |---|---|
   | `declines_offer` ("để sau", "chưa", "không biết" khi đang có lời mời), `stop` hoặc luật dừng | Xoá. Không chèn câu mời nào trong lượt |
   | `plan` được nhận (đồng ý) | Xoá. D ghi vào chuyến nếu chuyến chưa có điểm đến (`consent_update`) |
   | Câu mời cho E được chèn | `{destination: E}`; E vào `offered_destinations` |
   | `rejected` có điểm đến đang mời, hoặc lượt nói về điểm đến khác (nút "Lập lịch <E>", E khác điểm đến đang mời) | Xoá: lời mời cũ không còn đúng chỗ đang nói |
   | Còn lại, kể cả lượt chỉ có nút "Lập lịch <D>" cho đúng điểm đến đang mời | Giữ nguyên |

   Ví dụ "chán Hà Nội rồi, Đà Nẵng thì sao": câu mời cho Đà Nẵng được chèn (dòng 3), nên lời mời đang chờ đổi sang Đà
   Nẵng; Hà Nội không được mời lại vì đã bị chê.

   | `plan_reason` | Code kiểm trước `extract` | Không đạt |
   |---|---|---|
   | `accepts_offer` ("ok", "được" sau lời mời) | Có `pending_offer` | Trả lời theo luật lời mời |
   | `asks_plan` ("lập lịch Hà Nội cho mình", bấm nút lập lịch) | Không cần thêm. `_PLAN` vẫn chạy trước LLM tới B13 | — |
   | `trip_details` ("Hà Nội 3 ngày", "đi 2 người") | Sang `extract`. Đồng ý khi trích được số ngày, ngày đi, số người hoặc ngân sách (`planning_implied`), như hiện nay | Không trích được: trả lời theo luật lời mời, không vào `clarify`/`tool` |
   | `form` ("cho mình cái form") | Không cần thêm: xin form là đồng ý (FR-AGT-06) | — |

   Đã đồng ý từ trước (`plan_consent`) thì `plan` đi thẳng vào nhánh, như hiện nay.
8. **Nơi bị chê** không thành thẻ hay nút, trừ khi việc lượt này nhắm đúng nơi đó (người dùng hỏi lại tên, bỏ khỏi
   `rejected` như `_rejection_update` hiện nay).
9. Thẻ còn lại thành `searchResults` (nhóm theo taxonomy, `summary()`) và `candidates` để `finalize` kiểm.

`finalize` chỉ thêm bước quét số của luật 1, còn lại giữ nguyên, và vẫn là nơi duy nhất cập nhật `shown`.

### 4.5. Vòng lặp và phanh

- **Vòng 1:** orchestrator trả `answer`/`ask` thì xong, sang gác cổng rồi `finalize` (một lời gọi LLM). `plan` thì kiểm
  đồng ý rồi sang `extract`. `execute` thì sang node `run_jobs`.
- **`run_jobs`** (`agents/nodes.py`) chạy các việc của vòng, gộp `turn_jobs`, `turn_codes`, `candidates`, `events`, rồi
  quay về `orchestrate` kèm `results` và `pending`, trừ khi đi đường tắt vé.
- **Đường tắt vé** chỉ khi câu vé đã trả lời **toàn bộ** tin nhắn. Code xét đủ năm điều kiện, không suy từ số việc:
  1. đang ở vòng 1;
  2. vòng có đúng một việc, và là `fare`;
  3. orchestrator khai `fare_only=true`;
  4. `pending` rỗng;
  5. việc vé có câu do code viết (`answered`, `asked` hoặc `unavailable`).

  Đủ thì trả câu vé như hiện tại, không gọi orchestrator vòng 2, nên độ trễ không đổi. Khai `fare_only` mà thiếu điều kiện
  khác (ví dụ còn `pending`) thì code bỏ qua cờ và gọi vòng sau.
- **Việc còn chờ** (`pending`) đi cùng `results` sang vòng sau. Vòng sau phải `execute` các việc đó hoặc trả lời. Chạm phanh
  khi còn việc chờ thì chế độ buộc trả lời nhận `unfinished`: câu trả lời nói rõ phần chưa làm và có nút để hỏi tiếp.
- **Song song hay nối tiếp tuỳ phụ thuộc** (orchestrator quyết):
  - "vé đi Hà Nội bao nhiêu, Hà Nội có gì chơi" → một vòng hai việc, chạy song song; không đi đường tắt vì có hai việc.
  - "đi đâu vé rẻ, chỗ đó có gì chơi":
    - vòng 1 `fare` (so tuyến), `pending=[explore nơi có vé rẻ nhất]`, `fare_only=false`;
    - vòng 2 `explore` nơi rẻ nhất (`pending_fare.best`);
    - vòng 3 `answer` gồm khối vé và thẻ.
  - "vé sg ra hn bao nhiêu" → vòng 1 `fare`, `fare_only=true` → đường tắt.
  - "bạn giúp được gì" → `answer`, không việc nào.
- **Phanh do code** (đặt lại số ở B12):
  - tối đa 3 vòng `execute` mỗi lượt;
  - ngân sách thời gian cả lượt;
  - trần tổng lời gọi tool, khởi đầu 10;
  - việc trùng loại, tham số và vị trí con trỏ với việc đã chạy thì bỏ. `continue_from` dời con trỏ nên không bị coi là
    trùng; hết cả `unlisted` lẫn `source_more` thì việc trả `empty`;
  - vòng không có việc mới thì dừng.

  Chạm phanh: gọi orchestrator một lần ở chế độ **buộc trả lời** (`execute` không hợp lệ). LLM vẫn trả `execute` hoặc lỗi
  thì code ghép lời dự phòng từ kết quả đã có (câu cố định hiện tại của khám phá và vé).
- **Một câu hỏi mỗi lượt:** `ask` chỉ một câu; ý hỏi khác thành nút (4.4 luật 7).
- **Graph:** cờ bật thì `precheck` (phần luật đầu vào giữ nguyên, đổi tên trace ngày 12/10) → `orchestrate` → `route_after_orchestrate`:
  - `answer`/`ask` → `gatekeep` → `finalize`;
  - `plan` → kiểm đồng ý (4.4 luật 7) → `extract`; `trip_details` kiểm sau `extract`. Không đạt thì `gatekeep` với câu
    mời;
  - `execute` → `run_jobs` → `route_after_jobs`: đường tắt vé → `finalize`, còn lại → `orchestrate`.

  Cờ tắt thì giữ nguyên topology hiện tại.
- **Response:** `NEEDS_CLARIFICATION` với `question`, `searchResults` gộp (`flight`, `attraction`, `hotel`…),
  `suggestions` ≤ 3. Không đổi contract (`schemas/itinerary-agent.yaml` 1.24.0–1.25.0). Nếu thấy cần trường mới thì sửa
  fragment OpenAPI **trước** và chạy `validate_contract.py`.

### 4.6. Câu cố định thành lời LLM

Các câu sau trong `agents/steps/messages.py` do orchestrator viết:
- lời mời lập lịch (`explore_offer`), qua `offer.text`; code quyết có chèn hay không (4.4 luật 7);
- câu tạm biệt của luật dừng;
- tiêu đề khám phá;
- "chưa có điểm đến".

Câu cố định giữ làm dự phòng khi LLM lỗi. Câu vé có số liệu vẫn do code viết. Lời lịch trình vẫn do `narrate` viết.

### 4.7. Cờ và model của orchestrator

- **Cờ:** `ITINERARY_ORCHESTRATOR=off|on`, đọc trong `agents/runtime_dependencies.py`/config như các cờ itinerary hiện có.
  Mặc định `off` tới khi B12 đạt ngưỡng. Cờ `off` thì snapshot hành vi không đổi.
- **Model riêng cho orchestrator.** Người dùng chọn **GPT-6.1 Sol** của OpenAI (ra mắt 29/09/2026, phân khúc cân bằng
  năng lực và chi phí của dòng GPT-6, 2026-10-12). Cấu hình như sau:
  - Biến cấu hình trong `core/config.py` `Settings`:
    - `ITINERARY_ORCHESTRATOR_MODEL`: model ID;
    - `ITINERARY_ORCHESTRATOR_PROVIDER` (`gemini|openai|anthropic`): ghi rõ, không đoán provider từ tên model;
    - `ITINERARY_ORCHESTRATOR_REASONING_EFFORT` (tuỳ chọn, như `ITINERARY_LLM_REASONING_EFFORT`).
  - Bỏ trống thì orchestrator dùng chung model với các node khác (`ITINERARY_LLM_MODEL`).
  - `main.py` dựng thêm `app.state.itinerary_orchestrator_llm` trong `lifespan` bằng `infrastructure/llm/build_orchestrator_model`
    với tham số provider/model. Lỗi hoặc thiếu khoá thì ghi cảnh báo và dùng model chung, không làm hỏng app.
  - Các node khác (`extract`, `tool`, `filter`, `narrate`) giữ model nhanh hiện tại.
  - Model được chọn phải hỗ trợ structured output (JSON schema, `with_structured_output`) qua tích hợp LangChain của
    provider đó. Provider ngoài Gemini/OpenAI/Anthropic thì phải thêm adapter trong `infrastructure/llm/client.py`.
  - Model này ra sau mốc kiến thức của agent viết plan. Ở B7 phải kiểm trên tài liệu OpenAI và bằng một lời gọi thật:
    - model ID chính xác trên API;
    - có nhận `temperature` không (model reasoning của OpenAI thường không nhận);
    - `reasoning_effort` nào để structured output và độ trễ chấp nhận được;
    - structured output theo JSON schema qua `ChatOpenAI.with_structured_output`.
  - Cần `OPENAI_API_KEY` ngoài khoá của model chung: một lượt có thể gọi hai provider. PRD đã liệt kê OpenAI làm provider
    (`architecture.md` §1).
  - Nhiệt độ và mức reasoning chọn bằng số đo ở B12: so GPT-6.1 Sol với model chung trên cùng bộ đo về pass, độ trễ
    p50/p95 và chi phí mỗi lượt. Orchestrator gọi 1–4 lần mỗi lượt, nên model chậm làm tăng độ trễ đúng theo số vòng.
  - Thêm cờ và các biến model trên vào `.env.example`, `src/backend/README.md` và `docs/prd/deployment-plan.md` §2 (qua
    đề xuất).

### 4.8. Hành vi mong đợi (case cho B11–B12, không cài cứng)

| Người dùng | Orchestrator | Kết quả |
|---|---|---|
| "ngoài ra còn gì nữa", "thêm vài chỗ" sau lượt khám phá | `execute` explore `intent=more` | Nơi chưa xem cùng phạm vi, mở bằng ý "ngoài những nơi trên…". `empty` (hết cả `unlisted` lẫn `source_more`) thì nói rõ đã giới thiệu hết những nơi nổi bật, mời lập lịch hoặc đổi nơi |
| "còn nữa không" lặp lại nhiều lượt | mỗi lượt `intent=more` | Mỗi lượt nơi chưa xem, tới khi hết thì nói rõ; không lặp thẻ |
| "chán, đi rồi", "chỗ khác đi" sau lượt giới thiệu một nơi | `rejected=[nơi đó]`, rồi `ask` (gợi nơi khác) hoặc `execute` nơi khác | Không gợi ý lại nơi bị chê |
| "mấy chỗ này không hợp" | `execute` `intent=more` giữ điểm đến | Nơi khác cùng điểm đến |
| "có chỗ nào rẻ hơn" | `execute` `intent=cheaper` `refers_to` các thẻ vừa xem | Chỉ nơi rẻ hơn hẳn, cùng loại và điều kiện; không có thì nói thẳng |
| "cái nào có hồ bơi", "cái thứ hai thế nào", "khách sạn thứ hai giá bao nhiêu" | `execute` `intent=about_shown` `refers_to` các thẻ được hỏi | Chỉ xét đúng các thẻ đó, dữ kiện tra lại ngay lượt này (đo 12/10 ở mục 1: hiện nay tìm lại ra thẻ khác) |
| "giá tính theo người hay gói" | `execute` `intent=about_shown` | Trả lời theo `priceUnit` vừa tra lại |
| "lúc nãy bạn gợi ý những khách sạn nào" | `answer`, nhắc lại tên | Tên viết thường, không link, không thẻ, không số; muốn xem lại thẻ thì `about_shown` |
| Nêu đúng tên một nơi đã xem, hoặc câu hỏi mới có nơi đã xem khớp | `execute` `intent=new` | Thẻ nơi đó vẫn hiện |
| "vé sg ra hn bao nhiêu" | vòng 1 `fare`, `fare_only=true` | Đường tắt: câu vé như hiện tại, một lời gọi LLM |
| "vé sg ra hn bao nhiêu, hà nội có gì chơi" | một vòng: `fare` + `explore` | Một câu trả lời: khối vé nguyên văn + thẻ Hà Nội |
| "vé ra hn bao nhiêu, hà nội có gì chơi" (thiếu nơi đi) | một vòng: `fare` (`asked`) + `explore` | Thẻ Hà Nội + câu hỏi nơi đi của khối vé, nút "Từ <nơi>" trước; không thêm câu mời |
| "vé ra hà nội và đà nẵng bao nhiêu" (chưa biết nơi đi) | hai việc `fare`, cả hai `asked` | Một câu hỏi nơi đi (việc 1), việc 2 vào `waiting_jobs`. Bấm "Từ TP. Hồ Chí Minh" thì code báo giá cả hai tuyến, không qua LLM |
| "vé sg ra hn bao nhiêu, mà khách sạn lúc nãy giá nhiêu nhỉ" | `fare` + `about_shown` | Giá khách sạn qua `[[price:#n]]` của lần tra lại. Viết thẳng giá cũ thì bị chặn, dù lượt đã có kết quả vé |
| "so vé từ Sài Gòn và Đà Nẵng ra Hà Nội" | hai việc `fare`, khác nơi đi | Hai khối vé để so; không khối nào bị thay |
| "khách sạn gần Hồ Gươm và gần Văn Miếu" | hai việc `explore` có `near` | Khoảng cách điền theo mốc của đúng việc (`[[distance:job1:#n]]`, `[[distance:job2:#n]]`), kể cả khi một khách sạn có trong cả hai |
| "chán Hà Nội rồi, Đà Nẵng thì sao" sau lời mời Hà Nội | `rejected=["Hà Nội"]` + `explore` Đà Nẵng kèm `offer` | Lời mời đang chờ đổi sang Đà Nẵng |
| "đi đâu cũng được miễn vé rẻ, chỗ đó có gì chơi" | vòng 1 `fare` kèm `pending`, vòng 2 `explore` nơi rẻ nhất, vòng 3 `answer` | Không đi đường tắt. Khối vé + thẻ nơi rẻ nhất |
| "ok" sau lời mời | `plan`, `plan_reason=accepts_offer` | Code thấy `pending_offer` rồi mới sang `extract` |
| "để sau" sau lời mời | `answer`, `declines_offer=true` | Xoá lời mời, không mời lại bằng câu. Nút vẫn còn để tự bấm, nhưng "ok" ngay sau đó không phải đồng ý |
| "bạn giúp được gì", "cảm ơn" | `answer` | Không gọi tool |

## 5. Các bước

**B1 — `cheaper` của vé** ✓ (2026-10-12).

**B2 — State `shown`** ✓ (2026-10-12; khác thiết kế ở 4.1).

**B3 — Khối ngữ cảnh chung** ✓ (2026-10-12). Thứ tự payload giữ như cũ (số đo ở 4.1).

**B4 — Đề xuất PRD, dừng.** Đề xuất `docs/prd/update-archive/2026-10-12-orchestrator-va-kham-pha-llm.md` (viết lại theo hướng ở
mục 3 ngày 2026-10-12). Chờ người dùng chốt, kèm các điểm ở mục 8.

Sau khi chốt:
- sửa `docs/prd/requirements.md` và `docs/prd/architecture.md` trước;
- đổi trạng thái đề xuất;
- `git mv` đề xuất sang `docs/prd/update-archive/`.

**B5 — Thực thi việc và rút gọn kết quả** (sau chốt). Như 4.3: `agents/steps/jobs.py`, `turn_codes`, `turn_jobs`,
`shown.record` nhận `turn_codes` và `via`. Unit test (tool giả):
- mỗi loại thao tác gọi đúng tool và tham số;
- `more` chạy lại `via`, loại thẻ đã xem đúng phạm vi, dùng hết ứng viên chưa hiện của trang đã tải rồi mới tải trang kế;
- `continue_from` lấy mục đã tìm mà chưa liệt kê, không gọi tool; hết thì tải trang kế (`offset`); hết cả hai thì `empty`;
- `unlisted` và `source_more` đúng với số mục đã giữ và `total` của nguồn;
- `cheaper`/`dearer`: mốc giá đúng, giữ điều kiện cũ, không có thì `empty`;
- `about_shown` chỉ tra lại các mã được hỏi;
- việc vé trả `answered`, `asked`, `unavailable` kèm `fare_block`;
- bản rút gọn có đúng một `anchor` cho việc `near`, `cheaper`, `dearer`, và giá của mốc được tra lại;
- mã cũ giữ nguyên, mã mới nối tiếp, không dùng lại;
- trần số mục và độ dài;
- tool lỗi thì `failed`, không lỗi lượt.

**B6 — Gác cổng.** Như 4.4. Unit test từng luật, đặc biệt:
- luật lặp theo intent;
- luật 1:
  - thẻ, link tới mã ngoài bản rút gọn của lượt bị bỏ; câu chỉ nhắc lại tên thì giữ;
  - lượt **có** kết quả vé mà câu viết thẳng giá cũ của khách sạn vẫn bị chặn;
  - số trong khối vé không bị quét; số người dùng vừa nêu viết thẳng vẫn là vi phạm;
  - placeholder tới mã chưa tra thì chạy `about_shown` rồi buộc trả lời; vẫn vi phạm thì lời dự phòng;
  - #12 có trong việc 2 (gần Hồ Gươm) và việc 3 (gần Văn Miếu): `[[distance:job2:#12]]` điền khoảng cách tới Hồ Gươm,
    `[[distance:#12]]` (thiếu mã việc) là vi phạm; `[[price_diff:job3:#12]]` dùng mốc của việc 3; mã không thuộc việc
    được ghi là vi phạm;
  - hai việc trả hai giá khác nhau cho cùng mã mà `[[price:#n]]` không ghi việc thì vi phạm;
  - `finalize` bắt lại số viết thẳng khi gác cổng bỏ sót;
- luật 6:
  - `replaces` hợp lệ (việc trước `asked`, việc sau chỉ khác ở trường đang hỏi, nay đã điền) thì khối hỏi không được
    chèn; việc sau thêm ngày bay mà việc trước không có thì `replaces` bị bỏ qua;
  - không tự thay: "so vé từ Sài Gòn và Đà Nẵng ra Hà Nội" ra hai khối; hai ngày bay khác nhau cùng tuyến ra hai khối;
    cả hai vẫn đúng khi orchestrator khai nhầm `replaces`; `replaces` trỏ tới khối `answered` bị bỏ qua;
  - hai việc vé `asked` thì chỉ một câu hỏi, việc kia vào `waiting_jobs`; nút của khối hỏi lại đứng trước;
- luật 7:
  - `ask` thiếu `question` bị từ chối; hai câu hỏi thì giữ một theo thứ tự; năm điều kiện chèn câu mời;
  - mọi dòng của hai bảng `pending_offer` và `plan_reason`, theo đúng thứ tự xét;
  - "để sau" trong lượt có nút lập lịch thì `pending_offer` vẫn rỗng; lượt sau chỉ có nút cũng không khôi phục;
  - chuyển sang điểm đến khác không có câu mời thì xoá lời mời cũ.

**B7 — Orchestrator vòng 1.** Như 4.2, sau `ITINERARY_ORCHESTRATOR=on`: schema, prompt, node `orchestrate`, map sang state,
model riêng theo 4.7 (bỏ trống thì dùng model chung). Unit test (LLM giả):
- `answer`/`ask` đi gác cổng rồi `finalize`;
- `plan` qua kiểm đồng ý rồi đi `extract` với state như `route_result` hiện tại; không đạt thì trả câu mời;
- `rejected`, `declines_offer`, `plan_reason` (kể cả `form` → `form_request`) map đúng;
- prompt nói rõ ranh giới "nhắc lại / tra lại" (4.4 luật 1);
- cờ `off` thì snapshot không đổi.

**B8 — Vòng lặp.** Như 4.5: `run_jobs`, `route_after_jobs`, đường tắt vé, phanh. Unit test (LLM giả):
- "vé sg ra hn bao nhiêu, hà nội có gì chơi" ra một response có `flight` + thẻ Hà Nội, khối vé nguyên văn;
- "đi đâu cũng được miễn vé rẻ, chỗ đó có gì chơi": vòng 1 `fare` kèm `pending` không đi đường tắt, vòng 2 `explore` nơi
  rẻ nhất, response có cả khối vé lẫn thẻ;
- đường tắt vé: đủ năm điều kiện thì không gọi orchestrator vòng 2; thiếu một điều kiện (còn `pending`, hai việc, vòng 2,
  không khai `fare_only`) thì có vòng sau;
- `rejected`, `declines_offer`, `stop` vẫn được ghi khi đi đường tắt;
- có `waiting_jobs` mà người dùng bấm nút vé: code chạy cả việc của nút lẫn các việc chờ thiếu cùng trường, không gọi
  LLM; lượt sau đó `waiting_jobs` rỗng;
- `continue_from` không bị phanh chống trùng chặn khi con trỏ đã dời;
- có `plan` thì ý khác thành `suggestions`;
- dừng ở 3 vòng, ở trần lời gọi tool, khi hết thời gian, khi việc trùng;
- buộc trả lời khi chạm phanh; còn việc chờ thì payload có `unfinished` và response có nút hỏi tiếp.

**B9 — Câu cố định thành lời LLM.** Như 4.6.

**B10 — Kiểm nhanh và tài liệu — đã hoàn thành 2026-10-12.**

Backend: 2.935 pass / 36 skip; contract hợp lệ; gatekeeper đạt 82,4% line coverage bằng stdlib trace.
Kiểm nhanh LLM thật với `gpt-6.1-sol`, reasoning low: muốn thêm không lặp thẻ, chê không gợi lại nơi,
vé rẻ hơn trả đúng mốc, hỏi giá/hồ bơi chỉ xét thẻ đã xem, tin nhiều việc trả cả vé lẫn khám phá.
Lượt kiểm cuối xác nhận Hà Nội có 3 thẻ tham quan + 2 khách sạn, hỏi khách sạn thứ hai tra đúng REY Hotel Hanoi.
Có một lần provider trả HTTP 500 và fallback an toàn; chạy lại thành công. Đây là smoke test backend,
chưa phải đánh giá nhiều lần, thống kê latency hay kiểm giao diện trình duyệt. B11–B13 giữ nguyên việc còn lại.

- Unit test agent + domain; cả bộ backend.
- Với cờ bật, chạy script mục 0 cho 4 đoạn chat mục 1 và "vé sg ra hn bao nhiêu, hà nội có gì chơi", ghi kết quả vào
  `history/` (chưa phải bộ đo).
- Tài liệu:
  - `docs/spec/agent/langgraph-nodes.md` (orchestrator, `run_jobs`, gác cổng);
  - `docs/spec/agent/state-fields.md` (`turn_jobs` kèm con trỏ, `turn_codes`, `turn_pending`, bản trước khi điền số,
    `via`; `waiting_jobs` trong `CARRIED`; cách `pending_offer` đổi theo 4.4 luật 7);
  - `docs/spec/agent/nghiep-vu/tro-chuyen-va-kham-pha.md`, `vong-doi-mot-luot.md`;
  - `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`;
  - `docs/spec/agent/working-context.md` §3 (bản đồ runtime).
- Skill `.agents/skills/building-itinerary-agent/SKILL.md` bước 3: "luật code cho tiền, ngày, grounding, an toàn, phạm vi
  thực thi; hiểu câu sửa bằng prompt/ngữ cảnh + case trong bộ đo".

**B11 — Luật kiểm và kịch bản lỗi** (làm sau).
- `src/backend/tests/unit/agents/test_followup_properties.py` đọc `snapshot.json`.
- Thêm vào `behavior_snapshot/scenarios.json`: `["hà nội","ngoài ra còn gì nữa"]`, `["hà nội","đi rồi"]`,
  `["Đà Nẵng có gì","có ks nào rẻ hơn không"]`, `["vé sg ra hn bao nhiêu, hà nội có gì chơi"]`,
  `["hà nội","khách sạn thứ hai giá bao nhiêu"]`, `["hà nội","mấy chỗ lúc nãy cái nào có hồ bơi"]`,
  `["tao ở sài gòn, đi đâu cũng được miễn vé máy bay rẻ, chỗ đó có gì chơi"]`.
- Luật kiểm:
  - thẻ có trong kết quả tool;
  - lượt không gọi tool thì không nêu dữ kiện sản phẩm, chỉ nhắc lại tên (4.4 luật 1);
  - lặp thẻ đúng theo intent (4.4);
  - không hỏi thông tin chuyến khi chưa đồng ý, và câu hỏi đúng loại đã khai (`question.about`);
  - không gợi ý nơi bị chê;
  - tối đa một câu hỏi;
  - số thẻ trong giới hạn;
  - tin nhiều việc trả lời đủ các việc.

**B12 — Bộ đo** (làm sau; chạy cho cờ cũ và mới):
1. Đọc 50–100 trace LangSmith gần nhất (connector cần người dùng cấp quyền lại), gom lỗi thành loại, đếm; lỗi mới phải gán
   vào một loại.
2. Hội thoại nhiều lượt (lỗi lặp chỉ lộ ở lượt sau): *tầng 1* lượt 1 cố định ("hà nội", "cứ chọn đại", vé "sg ra hn"), LLM
   sinh 20 cách nói cho lượt 2 của mỗi dòng bảng 4.8 và cho tin nhiều việc; chuỗi "hà nội" → "còn gì nữa" → "còn nữa
   không"… tới khi hết. Dataset có version trong `src/evaluation/datasets/`, chạy qua golden (case `turns:`,
   `docs/spec/agent/golden-run.md`). *Tầng 2* LLM đóng vai khách có mục tiêu và tính cách, 5–8 lượt; luật kiểm mọi lượt,
   LLM chấm cả hội thoại; chạy nhiều lần, đọc trace lần fail; bộ giả lập viết mới trong `src/evaluation/agent/`.
3. LLM chấm theo tiêu chí (đúng câu hỏi, tự nhiên, không lặp, ngắn); người đọc mẫu 20 hội thoại mỗi lần.
4. Báo: pass luật kiểm, điểm giám khảo, grounding (100%), latency p50/p95, số lời gọi LLM/tool. Biên bản
   `src/evaluation/reports/eval-YYYY-MM-DD-<slug>.md` (AGENTS.md §7).

**B13 — Chuyển và gỡ luật** (làm sau). Bật mặc định khi grounding 100%, luật kiểm và điểm giám khảo không thấp hơn đường
cũ, latency trong mục tiêu đã chốt. Gỡ regex từng nhóm, đo lại mỗi lần: `exploration.py` → `classification.py`
(`_REJECT`, `_ELSEWHERE`, `_DELEGATE`) → `consent.py` (chỉ khi latency cho phép). Giữ `guardrails.py` và `_STOP`. Xoá
đường cũ sau một vòng chat thử không hồi quy; ghi lại snapshot.

## 6. Bản nháp đề xuất PRD (B4)

Đề xuất đầy đủ ở `docs/prd/update-archive/2026-10-12-orchestrator-va-kham-pha-llm.md`. Tóm tắt:

- **FR-AGT-06**, thêm một gạch đầu dòng:
  - trợ lý nhớ đã gợi ý gì (thẻ, vé, lịch) và tự quyết tìm gì theo câu hỏi;
  - nơi đã xem được hiện lại hay không là theo ý người dùng: muốn thêm thì nơi chưa giới thiệu cùng phạm vi; hỏi về thẻ
    vừa xem thì chỉ các thẻ đó, dữ kiện tra lại ngay lượt đó; rẻ hơn/đắt hơn thì so với thẻ đang nói và giữ các điều kiện
    khác; câu hỏi mới vẫn có thể gặp lại nơi đã xem nếu khớp;
  - chê một nơi không cần nêu tên;
  - một tin nhiều việc được trả lời đủ trong một câu trả lời, kể cả việc cần kết quả của việc khác, trừ yêu cầu lập lịch.
- **AC-AGT-06:** viết lại ô theo nguyên tắc kiểm được, như mục "Luật kiểm" của B11, thêm nguyên tắc về đồng ý (trả lời
  đúng lời mời đang chờ; từ chối thì lời mời hết hiệu lực, nút vẫn bấm được). Các nước đi cụ thể hiện có chuyển thành
  case trong bộ đo.
- **AC-AGT-07:** chỉ đổi câu "lý do chọn thẻ … do code tính …, LLM chỉ viết câu và không viết số". LLM chọn thẻ trong kết
  quả của lượt; code tính nhãn so sánh và điền số. Các phần khác (nút, vị trí và câu dẫn của thẻ, giọng điệu, khó hiểu,
  khó tính, cộc lốc, không quen công nghệ, ngoài phạm vi) giữ nguyên.
- **AC-AGT-08:** giữ nguyên. Ghi rõ thêm: tin chỉ hỏi vé thì câu vé do code viết là toàn bộ câu trả lời; tin có vé và
  việc khác thì LLM chỉ viết phần dẫn, khối câu vé chèn nguyên văn; nhiều tuyến cùng thiếu thông tin thì chỉ hỏi một câu.
- **`architecture.md` §3:**
  - `ClassifyTurn` thành Orchestrator: một LLM làm đầu mối, mỗi vòng trả lời, hỏi lại, chuyển lập lịch hoặc yêu cầu
    thực thi;
  - `explore`/`fare` là khả năng do code thực thi, trả kết quả rút gọn có mã `#n`;
  - vòng lặp có phanh;
  - nhánh lập lịch (kể cả `narrate`) giữ nguyên; code kiểm đồng ý lập lịch từ trường có cấu trúc trước khi vào nhánh;
  - gác cổng bằng code, `shown` chỉ cập nhật ở `finalize`;
  - Tiêu chuẩn Grounding đổi câu "lý do chọn thẻ do code tính, LLM chỉ viết câu", và thêm ranh giới: trả lời không gọi
    tool chỉ được nhắc lại đã gợi ý gì; thẻ, link, giá và mọi dữ kiện của sản phẩm phải từ tool của chính lượt đó; mọi số
    liệu sản phẩm trong câu LLM viết đi qua placeholder, ở mọi lượt, trừ câu vé do code viết;
  - câu vé vẫn do code viết, orchestrator chỉ viết phần dẫn;
  - mục tiêu dưới 3 giây của lượt khám phá đặt lại sau khi đo.
- **Model riêng cho orchestrator** (GPT-6.1 Sol); các bước khác giữ model nhanh. `deployment-plan.md` §2 thêm
  `ITINERARY_ORCHESTRATOR`, `ITINERARY_ORCHESTRATOR_MODEL`, `ITINERARY_ORCHESTRATOR_PROVIDER`.

## 7. Invariant

- Mọi sản phẩm, giá, `productId` trong response đến từ kết quả tool của **chính lượt đó**. `shown` và khối ngữ cảnh chỉ để
  nhớ, loại, so và nhận ra thẻ được nói tới; không hiện sản phẩm từ state (`finalize` kiểm).
- Câu trả lời không tra lại chỉ được nhắc lại tên đã gợi ý. Không link, không thẻ, không số, không dữ kiện (4.4 luật 1).
- Mọi số liệu sản phẩm trong lời LLM viết đi qua placeholder gắn với mã đã tra trong lượt, ở mọi lượt, bất kể đã gọi bao
  nhiêu tool. Khối vé do code viết được miễn. Mỗi placeholder xác định đúng một giá trị; phép so với mốc ghi rõ việc;
  không xác định được thì code không điền (4.4 luật 1).
- Đường tắt vé chỉ khi orchestrator khai câu vé là đủ và code thấy đủ năm điều kiện (4.5); việc còn chờ không bị bỏ.
- Mỗi lượt tối đa một câu hỏi, kể cả khi nhiều việc vé cùng hỏi lại. Chỉ câu hỏi lại mới bị thay, khi việc sau khai
  `replaces` và code xác nhận cùng yêu cầu; hai yêu cầu khác nhau đều được trả lời (4.4 luật 6).
- Không vào nhánh lập lịch khi code chưa thấy đồng ý hợp lệ. Bỏ lời mời thắng tạo lời mời; nút lập lịch không tạo lời
  mời đang chờ (4.4 luật 7).
- Mã của kết quả vừa tìm chưa phải "đã xem". Chỉ thẻ có trong response cuối mới vào `shown`, và chỉ ở `finalize`.
- LLM chỉ nhắc sản phẩm qua mã `#n` và số qua placeholder; code điền. Khối câu vé chèn nguyên văn.
- Lập lịch (`compose`), chọn vé, tổng tiền, ngày, khoảng cách: tất định như hiện tại; mọi nhánh qua `finalize`.
- Guardrails và luật dừng chạy trước mọi LLM.
- Không log prompt có secret/JWT; khối ngữ cảnh không chứa dữ liệu cá nhân.
- Hội thoại lưu trước khi deploy vẫn đọc được (`phase.carried` cho giá trị đầu).

## 8. Các mức đã chốt và rủi ro

- **Người dùng đã chốt ngày 2026-10-12, áp dụng cả bốn mức sau:**
  - **Số thẻ.** Đề xuất: tối đa 3 điểm tham quan hoặc tour; 2 khách sạn khi hỏi chung, 4 khi hỏi riêng chỗ ở;
    orchestrator được chọn ít hơn. Con số 4 hiện nay đến từ AC-AGT-06: khung chat hẹp, 2–3 câu mỗi thẻ.
  - **Phạm vi "đã xem" khi `intent=more`.** Đề xuất: cả hội thoại, theo điểm đến + loại.
  - **Số việc tối đa mỗi vòng.** Đề xuất 3.
  - **Số vòng `execute`.** Đề xuất 3.
- **Số khởi đầu, đặt lại ở B12:** 8 mục / 1.500 ký tự mỗi việc trong bản rút gọn; 10 lời gọi tool mỗi lượt; ngân sách thời
  gian (tính theo model orchestrator được chọn).
- **Model của orchestrator:** GPT-6.1 Sol (OpenAI) theo lựa chọn của người dùng. Model ID, tham số hỗ trợ và độ trễ thật
  kiểm ở B7 và đo ở B12 (4.7).
- X02 lượt 4 "đắt nhất thì sao" trả đúng chuyến vừa báo rẻ nhất: kiểm tuyến Nha Trang → Phú Quốc có một chuyến không.
- **Rủi ro:**
  - Lượt khám phá vẫn hai lời gọi LLM (`execute` rồi `answer`), như hiện nay (`classify` + lời dẫn). Câu hỏi về thẻ đã
    xem cũng hai lời gọi (`about_shown` rồi `answer`). Việc nối tiếp thêm vòng: "đi đâu vé rẻ, chỗ đó có gì chơi" cần ba.
  - Dữ kiện không có số trong câu không tra lại ("có hồ bơi") code không bắt được; dựa vào prompt và luật kiểm B11.
  - Luật "số chỉ qua placeholder" chặt hơn lời khám phá hiện nay: prompt `explore` đang cho chép nguyên giá vé vào câu.
    Orchestrator viết sai thì tốn thêm một vòng buộc trả lời; B12 đếm số lần vi phạm và số lần phải dùng lời dự phòng.
  - Orchestrator quên khai `replaces` thì câu hỏi lại cũ vẫn được chèn cạnh câu trả lời mới. Code cố ý không tự thay, để
    không xoá nhầm yêu cầu độc lập; prompt dặn, B11–B12 đo tần suất.
  - Khai báo có cấu trúc (`question.about`, `fare_only`, `pending`) có thể lệch với câu chữ. Code kiểm các điều kiện cứng
    quanh nó (4.4, 4.5); phần lệch đo ở B11–B12.
  - Cả hai lời gọi đều đi qua model mạnh hơn (GPT-6.1 Sol), thay vì model nhanh như hiện nay, nên lượt khám phá có thể
    chậm hơn rõ. Phải đo ở B12 trước khi đặt ngân sách thời gian và trước khi bật cờ.
  - Kết quả dao động giữa các lần chạy: đo pass^k bằng `--repeat`.
  - Phụ thuộc model (`infrastructure/llm/client.py`, mặc định Gemini 2.5 Flash): thử đúng model staging.
  - Đổi prompt phải ghi lại cả snapshot.
  - Thứ tự payload của prompt mới phải đo như B3 đã làm với `classify`.
  - Chưa đo thì không bật cờ mặc định.
- **Khi nào tách `explore` thành agent LLM riêng:** chỉ khi B12 cho thấy phần khám phá đủ phức tạp (nhiều chặng, so nhiều
  điểm đến), hoặc kết quả làm ngữ cảnh orchestrator quá lớn.
