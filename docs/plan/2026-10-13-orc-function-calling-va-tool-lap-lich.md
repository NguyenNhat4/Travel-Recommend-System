# Chuyển orc v2 sang function calling, tập trung tool lập lịch

- Ngày: 2026-10-13
- Người yêu cầu / lập plan / thực hiện: Nguyễn Minh Nhật / Claude Code / Codex
- Trạng thái: hoàn thành triển khai và kiểm kỹ thuật; dừng đo model theo yêu cầu người dùng
- Phục vụ: FR-AGT-02 (orc tự gọi công cụ), FR-AGT-03 (lịch theo ngày, chia buổi), NFR-REL-01 (grounding 100%)
- Phụ thuộc: đề xuất A–G đã chốt Nguyễn Minh Nhật ngày 2026-10-13 trong chat và áp dụng vào PRD, lưu tại
  `docs/prd/update-archive/2026-10-13-thiet-ke-lai-bo-tool-orc.md`.

## 1. Vấn đề

Đo trên model thật ngày 13/10 ("Lên lịch chuyến đi Đà Nẵng 3 ngày từ 25/10" → "mình đi một mình", ×3):

- 1/3 ra lịch. Lịch đó có 1–2 hoạt động/ngày và 3 đêm cho chuyến 3 ngày.
- 1/3 hết 3 lượt gọi tool (tìm → lấy hạng phòng → build báo `OUTSIDE_OPENING_HOURS`), chỉ trả danh sách thẻ.
- Orc tự tính giờ từng phút và tự ghi ngày nhận/trả phòng: đây là chỗ sai nhiều nhất.

Cách gọi tool hiện tại (structured output `OrcDecision`) làm việc này nặng thêm:

- Model phải điền `null` cho mọi tham số không dùng (khoảng 14 ở `search_products`).
- Mỗi vòng gửi lại toàn bộ prompt, kết quả và sản phẩm dưới dạng một khối JSON mới: 15.000 → 24.000 token, 5–7 giây
  mỗi vòng, cache prompt chỉ trúng phần system.
- Mô tả tool nằm sâu trong `anyOf`, model khó chọn đúng tool.

## 2. Mục tiêu

- Lập lịch rõ ràng → luôn có lịch theo ngày/buổi trong 2 lượt gọi tool, còn 1 lượt để sửa.
- Orc chọn sản phẩm và buổi; code tính giờ, số đêm, số phòng, tiền.
- Đổi transport gọi tool sang function calling mà giữ các hợp đồng: registry ref `p…`, ngân sách lượt, guard câu trả lời,
  SSE tiến trình, response v2. PRD cho phép đổi transport (đề xuất đã chốt 13/10, mục 9.1: "Về sau có thể đổi transport
  gọi tool mà giữ các hợp đồng này").

Ngoài phạm vi: vé bay qua sân bay gần, so giá combo (bàn sau).

## 3. Cơ chế mới

### 3.1. Hội thoại một lượt

```
system:    PROMPT (cố định) + tên điểm đến catalog
user:      payload lượt: message, ui_action, context, plan (rút gọn), history, known_products, language
assistant: tool_calls [c1 find_products, c2 find_products, c3 update_trip]
tool c1:   {status, refs, coverage, products: {p1: {...}, ...}}
tool c2:   ...
tool c3:   {ok: true}
assistant: tool_calls [c4 plan_itinerary]
tool c4:   {lịch đã tính giờ, chi phí, violations}
assistant: tool_calls [c5 respond]       ← câu trả lời cuối cũng là một tool, để giữ cấu trúc
```

- Gọi model bằng `bind_tools(tools, tool_choice="required", parallel_tool_calls=True, strict=True)`. Luôn phải gọi tool;
  không có câu trả lời văn bản tự do.
- Hội thoại chỉ nối thêm (append-only): lượt sau không gửi lại kết quả cũ thành khối mới, nên cache prompt trúng cả phần
  đã gửi. Sản phẩm chỉ xuất hiện một lần, trong ToolMessage của lời gọi đã trả nó.
- `remaining` (lượt tool, request nguồn, lần gọi model) và `issues` (lỗi của bước trước) đi trong ToolMessage hoặc một
  tin nhắn user ngắn trước lần gọi kế tiếp.

### 3.2. Giới hạn, giữ nguyên PRD

| Giới hạn | Cách áp |
|---|---|
| 3 lượt gọi tool | Đếm số lần model trả tool_calls nghiệp vụ. Hết lượt: lần gọi sau chỉ bind `respond` |
| 1–3 tool mỗi lượt | Quá 3 lời gọi nghiệp vụ: không chạy, trả ToolMessage lỗi `TOO_MANY_CALLS` cho từng lời gọi thừa |
| 10 request nguồn | Như hiện tại (`SourceBudget`) |
| 5 lần gọi model | Như hiện tại |
| Sửa câu trả lời 1 lần | `respond` sai thì ToolMessage trả `issues`, model gọi `respond` lại một lần |

`update_trip` và `respond` không tính vào 3 lượt gọi tool nghiệp vụ.

### 3.3. Think (lời giải thích công khai)

Mỗi tool nghiệp vụ có tham số bắt buộc `why`: một câu ghi chú công việc, không tên/giá/số. `why` của lời gọi đầu mỗi lượt
là Think của lượt đó; `respond.explanation` là Think cuối (tiêu chí chọn). Vẫn lọc qua `public_explanation`.

## 4. Định nghĩa tool

Tham số không bắt buộc thì bỏ trống được (không phải điền `null`). Riêng OpenAI strict mode đòi mọi field trong
`required`; adapter dịch sang dạng nullable khi gửi cho OpenAI, còn mô tả gửi model giữ nguyên.

### 4.1. `find_products` (gộp search_products + list_products, phần B)

```json
{
  "name": "find_products",
  "description": "Tìm sản phẩm trong catalog. Có query thì xếp theo độ khớp nghĩa (chủ đề, tiện ích); không có query thì duyệt theo sort. Khách sạn trả kèm hạng phòng đặt được.",
  "parameters": {
    "type": "object",
    "properties": {
      "why": {"type": "string", "description": "Vì sao cần lời gọi này, một câu, không tên/giá/số."},
      "destination": {"type": "string", "description": "Đúng một tên trong danh sách điểm đến của system prompt."},
      "taxonomy": {"type": "string", "enum": ["hotel", "attraction", "combo", "golf"]},
      "query": {"type": "string", "description": "Chủ đề hoặc tiện ích ngắn ('lịch sử', 'hồ bơi'). Bỏ trống để duyệt."},
      "sort": {"type": "string", "enum": ["relevance", "popular", "price_asc", "price_desc"]},
      "price_max": {"type": "integer", "description": "VND cho một đơn vị giá (đêm/người/gói)."},
      "star_rating_min": {"type": "integer", "minimum": 1, "maximum": 5},
      "check_in": {"type": "string", "format": "date"},
      "check_out": {"type": "string", "format": "date"},
      "free_only": {"type": "boolean"},
      "exclude_refs": {"type": "array", "items": {"type": "string", "pattern": "^p[0-9]+$"}},
      "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Mặc định 10."},
      "cursor": {"type": "string"}
    },
    "required": ["why", "taxonomy"]
  }
}
```

Hạng phòng trả lồng trong khách sạn: `{p5: {name, unitPrice, …, rooms: {p6: {name, unitPrice, priceAdults,
maxOccupancy}}}}`. Bỏ một lượt riêng để lấy hạng phòng (phần C).

### 4.2. `plan_itinerary` (thay build_itinerary, phần E, F, G)

```json
{
  "name": "plan_itinerary",
  "description": "Xếp và tính lịch từ khung orc chọn. Orc chọn sản phẩm cho từng buổi; tool tính giờ theo thời lượng và giờ mở cửa, số đêm (= số ngày − 1), số phòng, chi phí từng dòng, tổng so với ngân sách. Không thêm, bỏ hay thay sản phẩm.",
  "parameters": {
    "type": "object",
    "properties": {
      "why": {"type": "string"},
      "destination": {"type": "string"},
      "start_date": {"type": "string", "format": "date"},
      "days": {"type": "integer", "minimum": 1, "maximum": 7},
      "adults": {"type": "integer", "minimum": 1, "maximum": 50},
      "children": {"type": "integer", "minimum": 0, "maximum": 50},
      "budget_vnd": {"type": "integer", "minimum": 0, "description": "Ngân sách cả chuyến; vượt chỉ là cảnh báo."},
      "schedule": {
        "type": "array", "minItems": 1, "maxItems": 7,
        "description": "Đủ mọi ngày. Mỗi buổi tối đa một sản phẩm; hoạt động cả ngày đặt ở cả morning và afternoon.",
        "items": {
          "type": "object",
          "properties": {
            "day": {"type": "integer", "minimum": 1, "maximum": 7},
            "morning": {"type": "string", "pattern": "^p[0-9]+$"},
            "afternoon": {"type": "string", "pattern": "^p[0-9]+$"},
            "evening": {"type": "string", "pattern": "^p[0-9]+$"}
          },
          "required": ["day"]
        }
      },
      "stays": {
        "type": "array",
        "description": "Hạng phòng (ref trong rooms của khách sạn). Bỏ trống = không lưu trú. Một dòng = cả chuyến; hai khách sạn thì ghi from_day/to_day.",
        "items": {
          "type": "object",
          "properties": {
            "room_ref": {"type": "string", "pattern": "^p[0-9]+$"},
            "from_day": {"type": "integer"}, "to_day": {"type": "integer"},
            "rooms": {"type": "integer", "minimum": 1, "maximum": 9, "description": "Chỉ khi khách nói rõ số phòng."}
          },
          "required": ["room_ref"]
        }
      },
      "flights": {
        "type": "object",
        "description": "Chuyến tới đúng điểm đến của lịch.",
        "properties": {
          "outbound": {"type": "string", "pattern": "^p[0-9]+$"},
          "return": {"type": "string", "pattern": "^p[0-9]+$"}
        }
      },
      "locked_refs": {"type": "array", "items": {"type": "string", "pattern": "^p[0-9]+$"}}
    },
    "required": ["why", "destination", "start_date", "days", "adults", "schedule"]
  }
}
```

Không có combo trong lịch: combo gợi ý riêng ở `respond.cards.combo` (`docs/prd/user-flow.md`, thẻ trong khung chat).

Kết quả trả cho orc:

```json
{
  "plan_result_id": "c4",
  "feasibility": "feasible | provisional | infeasible",
  "days": [
    {"day": 1, "items": [
      {"slot": "afternoon", "ref": "p4", "start": "14:30", "end": "17:00", "timing": "catalog"},
      {"slot": "evening", "ref": "p9", "start": "19:00", "end": "21:00", "timing": "estimate",
       "assumption": "Chưa có thời lượng, ước tính 2 giờ"}
    ]}
  ],
  "stays": [{"room_ref": "p12", "check_in": "2026-10-25", "check_out": "2026-10-27", "nights": 2,
             "rooms": 2, "rooms_basis": "priceAdults=2 cho 3 khách"}],
  "costs": {
    "lines": [
      {"ref": "p12", "basis": "900.000 × 2 đêm × 2 phòng", "subtotal_vnd": 3600000},
      {"ref": "p2", "basis": "970.000 × 3 người", "subtotal_vnd": 2910000},
      {"ref": "p9", "basis": "chưa rõ giá", "subtotal_vnd": null}
    ],
    "known_subtotal_vnd": 6510000, "unpriced_refs": ["p9"], "estimated_total_vnd": null,
    "budget_vnd": 8000000, "over_by_vnd": null, "share": {"stay": 0.55, "activities": 0.45, "flights": 0}
  },
  "violations": [
    {"code": "OUTSIDE_OPENING_HOURS", "ref": "p7", "day": 3, "slot": "morning",
     "fix_hint": "Mở 13:00–21:00; buổi còn trống phù hợp: ngày 1 sáng"}
  ],
  "warnings": ["TIMING_ESTIMATED"],
  "savings": [
    {"replace": "p12", "with": "p14", "save_vnd": 600000, "note": "Hạng phòng khác cùng khách sạn, đã tra trong lượt"}
  ]
}
```

Luật code tính (domain `draft_validation.py`, hàm thuần, unit test):

- Giờ trong buổi: sáng 08:00–12:00, chiều 13:00–18:00, tối 18:30–22:00; thời lượng lấy `durationMinutes`, thiếu thì 2 giờ
  và ghi `assumption`; phải nằm trong giờ mở cửa; ngày bay đến bắt đầu sau hạ cánh 90 phút, ngày về xong trước cất cánh
  150 phút. Không vừa thì `violations` kèm buổi còn trống phù hợp; code không tự dời sang buổi khác.
- Tối đa 3 buổi/ngày, mỗi buổi 1 sản phẩm (phần F).
- Số đêm = số ngày − 1, nhận phòng ngày đầu, trả phòng ngày cuối (phần G). Hai khách sạn thì theo from_day/to_day.
- Số phòng = ceil(số khách / priceAdults); thiếu priceAdults thì theo maxOccupancy kèm `PRICE_CAPACITY_UNKNOWN`; tối đa 9.
- Chi phí: phòng = giá/đêm × đêm × phòng; tham quan theo `priceUnit` (người hoặc gói); vé bay = giá × số khách.
  Thiếu giá không tính bằng 0.
- `savings` chỉ lấy sản phẩm cùng loại đã tra trong lượt (registry), rẻ hơn dòng đang dùng; chỉ là gợi ý cho orc.

### 4.3. `update_trip`

```json
{
  "name": "update_trip",
  "description": "Ghi điều khách vừa nói rõ trong tin nhắn này hoặc nút vừa bấm. Không tính vào lượt gọi tool.",
  "parameters": {
    "type": "object",
    "properties": {
      "destination": {"type": "string"}, "start_date": {"type": "string", "format": "date"},
      "days": {"type": "integer"}, "adults": {"type": "integer"}, "children": {"type": "integer"},
      "origin": {"type": "string"}, "budget_vnd": {"type": "integer"}, "free_only": {"type": "boolean"},
      "planning_consent": {"type": "boolean"}, "stopped": {"type": "boolean"},
      "engagement": {"type": "string", "enum": ["rekindle", "stop", "continue"]},
      "evidence": {"type": "string", "description": "Trích nguyên văn đoạn trong tin nhắn, hoặc mã nút."}
    },
    "required": ["evidence"]
  }
}
```

Giữ kiểm `evidence` như `patch_issue` hiện tại. "Một mình" → `adults=1, children=0` (ví dụ trong prompt).

### 4.4. `respond`

Giữ đúng schema `RESPOND` hiện tại (`orc_contracts.py`): `explanation`, `turn_kind`, `answer` (đoạn text/fact/product),
`cards` theo loại (combo gợi ý riêng ở đây), `alternatives`, `plan_result_id`, `plan_effect`, `disclosures`,
`suggestions`. Bỏ `context_patch` (đã có `update_trip`). Guard (`orc_guardrails.final_issues`) và `render_final` không đổi.

### 4.5. Các tool khác

`get_products` (nhiều ref, phần C), `recommend` (gộp Similar, phần D), `lookup_flights` giữ tham số như `orc_contracts.py`,
thêm `why`, bỏ bắt buộc `null`.

## 5. Luồng lập lịch mục tiêu

| Lượt | Orc gọi (song song) | Kết quả |
|---|---|---|
| 1 | `update_trip` (nếu khách vừa nói thêm) + `find_products` attraction (limit 12) + `find_products` hotel (kèm phòng, sort theo giá nếu có ngân sách) + `find_products` combo (limit 3) + `lookup_flights` (nếu có nơi đi) | Ứng viên đủ chọn |
| 2 | `plan_itinerary` | Lịch đã tính giờ, chi phí, vi phạm |
| 3 | Chỉ khi có vi phạm hoặc vượt nhiều: `plan_itinerary` lần nữa | Lịch sửa |
| — | `respond`: `turn_kind=itinerary`, `plan_effect=replace`, combo ở `cards.combo` | |

Có ngân sách: lượt 2 orc ưu tiên chọn hợp túi tiền; vượt thì lượt 3 đổi dòng đắt nhất theo `share` và `savings`, không
đổi sản phẩm khách đã khoá. Vẫn vượt thì trả lịch, nói vượt bao nhiêu, phương án rẻ hơn vào `alternatives`.

Không ra được lịch sau lượt 3: `respond` với `turn_kind=partial`, nói lý do cụ thể (từ `violations`) và một nút đề xuất
cách sửa; không hiện danh sách thẻ như đã lập lịch.

## 6. Thay đổi code (khi được duyệt)

| Bước | File | Việc | Cần chốt |
|---|---|---|---|
| 1 | `infrastructure/llm/`, `agents/steps/messages.py` | `_LoggedModel` log cả `bind_tools`; adapter dịch schema sang strict cho OpenAI; kiểm Gemini/Anthropic cùng schema | Không |
| 2 | `application/itinerary/orc_contracts.py` | Định nghĩa tool dạng function (mục 4); `respond` = `RESPOND` bỏ `context_patch` | Không (giữ 8 tool) |
| 3 | `agents/orc_v2.py` | `decide` dùng `bind_tools`, giữ danh sách message của lượt; `dispatch` trả ToolMessage; giới hạn mục 3.2; Think từ `why` | Không |
| 4 | `application/itinerary/orc_dispatch.py` | Không đổi cách thực thi; thêm `update_trip` | Không |
| 5 | `domain/itinerary/draft_validation.py` | Tính giờ theo buổi, số đêm, số phòng, chi phí từng dòng, `savings` | E, F, G |
| 6 | `orc_contracts.py`, `orc_dispatch.py` | `find_products` (gộp), khách sạn kèm phòng, `get_products` nhiều ref | B, C |
| 7 | `agents/orc_v2.py` `PROMPT` | Bỏ đoạn chọn giữa tool chồng nhau; luồng mục 5; ví dụ "một mình" | Theo B–G |
| 8 | Frontend | Không đổi contract v2; Think từ `why` vẫn là activity `think` | Không |

Bước 1–4 làm được ngay (chỉ đổi transport, giữ 8 tool). Bước 5–7 sau khi chốt phần tương ứng.

## 7. Kiểm tra

- Unit: `test_orc_loop.py` đổi `ScriptedModel` sang trả `AIMessage(tool_calls=…)`; test giới hạn 3 lượt, quá 3 lời gọi,
  `respond` sửa một lần, `update_trip` cần evidence. Domain: test tính giờ/đêm/phòng/chi phí/savings.
- Contract: `test_assistant_v2_contract.py`, `validate_contract.py` (response v2 không đổi).
- LLM thật ×3 trước và sau (`assistant_v2_cases.py`): `plan-danang`, `over-budget`, `hue-free-day`, `fare-after-plan`,
  `explore-story`, `alias-saigon`. Ghi: tỷ lệ ra lịch, hoạt động/ngày, số đêm, số phòng, số lượt tool, token, giây.
- Đạt: lập lịch 3/3 ra lịch; ngày trọn vẹn 2–3 hoạt động; 3 ngày = 2 đêm; ≤ 2 lượt tool khi không vi phạm; tool calling
  ≥ 95% (test-plan); không kém hơn bản cũ ở các ca khám phá và hỏi vé.

## 8. Rủi ro

- Model có thể trả văn bản thay vì tool khi `tool_choice="required"` bị provider bỏ qua: coi như lỗi quyết định, nhắc gọi
  `respond`.
- Gemini/Anthropic không có strict mode: vẫn kiểm bằng `jsonschema` như hiện tại trước khi chạy.
- Đổi transport và đổi bộ tool cùng lúc khó biết cái nào gây kém đi: làm bước 1–4 và đo trước, rồi mới bước 5–7.


## 9. Tiến độ triển khai ngày 2026-10-13

- Người dùng chốt A–G và triển khai toàn bộ; PRD cập nhật trước source, cả đề xuất bộ tool và Destinations đã lưu trữ.
- Bước 1–7 đã có code: function schemas/strict adapter, hội thoại nối thêm, update_trip/guard/quota, năm tool,
  tính buổi/đêm/phòng/chi phí/savings và prompt mới. Không đổi contract hoặc source frontend ở bước 8: kind dùng enum cũ.
- Kiểm kỹ thuật cuối: 257 bài kiểm thử local qua, contract validator và lint qua. Chi tiết lệnh và giới hạn xác minh
  ở `history/2026-10-13-trien-khai-orc-function-calling-tool-lap-lich.md`.
- Người dùng yêu cầu "ko cần đo" rồi "hoàn thiện đi": dừng đo model thật, không gọi thêm OpenAI. Các phép thử thật
  trước đó là thử nghiệm trong lúc triển khai, không nghiệm thu prompt cuối. Phần đo ở mục 7 không tiếp tục;
  chưa kết luận SLA, tỷ lệ tool calling ≥95% hoặc mục tiêu lịch 3/3 từ kiểm thử local.
- Điều chỉnh kỹ thuật theo kiểm thật: gpt-6-luna trả 400 khi function tools + reasoning trên Chat Completions;
  v2 dùng bản clone model với Responses API, giữ provider/model/effort và đường structured-output v1.
- Payload có today theo giờ Việt Nam, để ngày thiếu năm dùng lần sắp tới thay hỏi năm không cần thiết.
- Luồng mẫu mục 5 có thể nêu hơn ba tool nghiệp vụ: khi triển khai luôn giữ trần ba, combo tuỳ chọn; cần vé về thì
  dùng lượt hai tra về và lượt ba dựng lịch. Không tăng quota để đạt sơ đồ mẫu.
- Internal draft giữ minutes và response feasibility=verified/provisional/infeasible theo contract hiện có. Model
  đưa buổi, tool trả giờ tính; thêm fixed_times để giữ giờ khách yêu cầu theo phần E đã chốt.
- Các refs phòng trả ở data.rooms và view riêng trong products, không lặp toàn bộ registry mỗi vòng; coverage/errors
  cho biết phần chưa đọc đủ. Find lọc giá/sao/ngày trên trang Catalog (API Catalog không có các filter này); cursor
  vẫn theo offset nguồn trước lọc. Search sort giá chỉ trong trang đã tìm, không tuyên bố rẻ nhất cả catalog.
- View sản phẩm có suitable_slots và availability_by_date từ dữ liệu nguồn. Ngày trọn vẹn thiếu hoạt động khi còn
  ứng viên phù hợp đã tra trả TOO_FEW_ACTIVITIES để orc sửa; code không tự thêm điểm. Hoạt động cả ngày chiếm hai
  buổi, ngày bị giới hạn bởi chuyến bay được ít hoạt động hơn.
- plan_itinerary báo commit_allowed/needs_update_trip, nhưng quyền lưu lịch vẫn do evidence và final guard kiểm.
  Lỗi tra phòng giữ khách sạn đã lấy dưới dạng partial; fact hỗ trợ index mảng và giờ phút được format HH:MM.
- Adapter v1 giữ nguyên tham số/provider defaults; chỉ binding v2 yêu cầu strict/parallel mới đổi wire transport.
