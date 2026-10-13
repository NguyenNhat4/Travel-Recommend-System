# Orchestrator là luồng duy nhất: chuẩn bị demo, gỡ luồng cũ

- Ngày: 2026-10-12
- Người yêu cầu / phân tích: Nguyễn Minh Nhật / Claude Code.
- Phục vụ: FR-AGT-01, FR-AGT-06, FR-AGT-07, NFR-REL-01, NFR-PERF-02, NFR-SEC-04 (`docs/prd/requirements.md`). Không
  thêm và không bỏ FR, NFR hay AC nào.
- Trạng thái: plan. Sửa theo hướng ưu tiên demo ngày 12/10 (`history/2026-10-12-plan-uu-tien-demo.md`); người dùng chốt
  orchestrator mặc định và R1–R3 ngày 13/10 (`history/2026-10-13-chot-orchestrator-mac-dinh.md`). Các lần sửa trước:
  `history/2026-10-12-sua-plan-theo-review-2.md`, `history/2026-10-12-sua-plan-theo-review-3.md`. Đã chạy thử một lần
  trước D1 (mục 1.3). Tiến độ các bước ghi trong entry history của từng bước.
- Lệch PRD:
  - Orchestrator là mặc định, luồng cũ chỉ còn để quay về khi sự cố: **đã chốt** ngày 13/10/2026, đã áp dụng vào PRD
    (`docs/prd/update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`).
  - Gỡ cờ và code luồng cũ **ngay**, không chờ sau demo: **đã chốt** ngày 13/10/2026, đã áp dụng
    (`docs/prd/update-archive/2026-10-13-go-luong-cu-sau-demo.md`). Gỡ xong 13/10
    (`history/2026-10-13-go-luong-cu-orchestrator-duy-nhat.md`). Phần G0–G7 bị ảnh hưởng ghi ở mục 4.
- **Người dùng nói trực tiếp (12/10):**
  - Orchestrator là luồng chính. Gỡ code chỉ luồng cũ dùng, để đồng đội không test hay tối ưu trên luồng đó.
  - Ưu tiên hiện tại là demo thật tốt cho sếp, chưa tối ưu production. Tách việc demo khỏi việc gỡ code cũ: demo chạy
    orchestrator, việc xoá sạch luồng cũ hoãn tới sau demo.
  - Có ghi chú để nhóm không nhầm mà đi tối ưu luồng cũ.
  - 13/10: dùng orchestrator làm mặc định; code cũ chưa xoá thì phải ghi rõ là không dùng (D0). Hoàn thiện plan rồi tự
    làm.
  - 13/10, sau D2: "code không dùng thì gỡ khỏi nodes và graph để không phải đọc trùng". Khi được hỏi, người dùng chọn
    "Gỡ hẳn ngay, bỏ cờ". Không còn cờ để quay về luồng cũ.
  - Kiểm chứng demo trước khi code lớn. Kiểm chứng rồi mới sửa các vấn đề gọi tool. Không tăng giới hạn tool hay timeout
    một cách mù quáng. Không coi tra cứu thất bại là không có dữ liệu.
  - Giữ kiểm tra hành vi và grounding. Không giảm AC. Không dùng dữ liệu dựng sẵn để che lỗi demo.
  - Preview sau `compose` chỉ giữ nếu đo thấy có ích.
- **Phương án reviewer đề xuất, người dùng chấp nhận ngày 13/10:**
  - **R1.** Bỏ việc đo so sánh hai kiến trúc làm cổng chuyển. Vẫn bắt buộc: các ý AC liên quan có bằng chứng đạt trên
    orchestrator, và kiểm tra hồi quy (snapshot, golden).
  - **R2.** Người dùng duyệt bảng khác biệt của snapshot, sau khi baseline đã phát lại được (D2, D3).
  - **R3.** Không mặc định chấp nhận mất AC. Hành vi AC còn thiếu được làm trên orchestrator **trước** khi xoá phần code
    cũ tương ứng. Muốn tạm bỏ ý nào thì nêu đúng ý AC đó và xin chốt riêng.
- Thay cho B12 (chuyển mặc định) của `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`. B11 (bộ đo so sánh) không còn là cổng
  chuyển (R1). B13 (gỡ regex) vẫn là việc riêng, trừ regex chỉ luồng cũ dùng: các regex đó đã gỡ cùng luồng cũ (13/10).
- Plan tiến trình `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` **không** chờ G0–G7. Nó bắt đầu sau D3 và chỉ
  làm cho orchestrator.

Đường dẫn backend tương đối với `src/backend/app/` trừ khi ghi đầy đủ.

## 0. Thứ tự thực hiện

Mục này là thứ tự chung cho cả plan này và plan tiến trình. Bước có chữ B nằm ở plan tiến trình.

**Trước demo.**

| # | Bước | Đổi hành vi? | Chờ gì? |
|---|---|---|---|
| 1 | D0 ghi chú "luồng cũ đóng băng" ở tài liệu và code (comment, log cảnh báo) — **xong 13/10**, comment và log đã gỡ cùng luồng cũ | Không | — |
| 2 | D1 kiểm chứng demo: 6 kịch bản nối tiếp và cách diễn đạt khác, LLM thật; ghi lỗi và thời gian — **xong 13/10** | Không (không sửa source) | — |
| 3 | D2 mã nguyên nhân cho câu dự phòng; đồng hồ tiêm được; snapshot kiểm soát thời gian (trước đây là G1) — **xong 13/10** | Không (refactor runtime) | — |
| 4 | D3 orchestrator thành luồng duy nhất (gỡ cờ và luồng cũ, người dùng chốt 13/10); ghi baseline snapshot, phát lại offline — **ghi xong 13/10, chờ người dùng duyệt** | **Có** | D2 xong (đề xuất đã chốt 13/10) |
| 5 | D4 kiểm chứng rồi sửa 4 vấn đề gọi tool | **Có**, có chủ ý | D1 (bằng chứng), D3 (baseline) |
| 6 | D5 sửa lỗi demo theo danh sách D1 (mức "chặn demo" và "xấu") | **Có**, có chủ ý | D1, D3 |
| 7 | B1 chốt Phần A đề xuất tiến trình → B3 contract → B7, B8 frontend | Không đổi hành vi agent | Chốt Phần A; D3. Song song D4, D5 được |
| 8 | B4 số đếm tại chỗ lọc → B5 việc con đang chạy → B2 chẩn đoán mức 1 | Không đổi hành vi agent | **D4 xong** (cùng sửa `jobs.py`, `fares.py`) |
| 9 | B6 kết quả từng phần (preview) | Không đổi hành vi agent | Chỉ làm khi số đo D1 đạt tiêu chí ở plan tiến trình 3.5 và người dùng chốt Phần C |
| 10 | D6 tổng duyệt trên staging; kiểm tiêu chí nghiệm thu (mục 3) | Không | Mọi bước trên |

Sau D3, hai nhánh chạy song song được: agent (D4 rồi D5) và giao diện tiến trình (B3, B7, B8). B4 phải chờ D4, vì cả hai
cùng sửa bộ lọc trong `jobs.py` và luồng tra vé trong `fares.py`. Làm D4 trước thì B4 chỉ thêm bộ đếm vào code đã ổn
định.

**Sau demo** (mục 4). G5, G6 và phần tài liệu của G7 đã làm ngày 13/10 khi gỡ luồng cũ. Còn lại: G0 bảng AC ba trạng thái
→ G2 phanh `plan` lặp → G3 hành vi AC còn thiếu → G4 ghi lại baseline → G7 tổng kiểm. Cùng lúc, ở plan tiến trình: B9
chẩn đoán mức 2, kết quả từng phần cho lượt khám phá (Q6), và B6 nếu trước demo chưa làm.

**Quy tắc làm việc** (AGENTS.md và memory người dùng):
- Đọc theo AGENTS.md §1 (hàng "Itinerary Agent", "Backend", "Môi trường"). Ghi xác nhận §1.3 trước lần sửa code đầu. Mỗi
  bước một entry `history/`.
- Không commit khi chưa được yêu cầu. Commit đứng tên người dùng, không thêm `Co-Authored-By`.
- Chạy backend với `HF_HUB_OFFLINE=1`. Lúc code chỉ chạy test nhanh; cả bộ backend để cuối (`WEAVIATE_URL` cổng đóng,
  `SEARCH_PREWARM=false`).
- Sửa hành vi theo skill `building-itinerary-agent`: LLM hiểu câu; code kiểm dữ liệu, phạm vi và phanh. Không vá bằng
  regex.
- **Không che lỗi demo:**
  - Demo chạy dữ liệu thật của catalog (`ITINERARY_DATA_MODE=inprocess` hoặc `http`), không chạy `fixture`.
  - Không có câu trả lời dựng sẵn cho câu của kịch bản.
  - Không đưa nguyên văn câu kịch bản vào prompt làm ví dụ. Mỗi lần sửa phải đạt cả trên các cách diễn đạt khác của D1.
  - Không giảm AC. Không nới kiểm tra grounding.
- Sau mỗi bước, test thu thập được và xanh. Riêng D3 đổi mặc định và ghi lại snapshot trong cùng một bước, nên snapshot
  chỉ đỏ trong lúc làm, không đỏ giữa hai commit.

## 1. Hiện trạng

### 1.1. Code (đọc tại `a50c5e62`)

Mục 1.1–1.4 tả code **trước khi gỡ** luồng cũ (13/10), giữ lại làm lý do cho các bước. Graph hiện nay:
`docs/spec/agent/nghiep-vu/vong-doi-mot-luot.md`.

**Hai luồng cùng tồn tại.** `agents/graph.py` dựng graph theo `orchestrator_enabled`:
- Cờ tắt (mặc định ở `core/config.py`, `.env.example`, `docker-compose.yml`): `intake` → `classify` (luật, rồi LLM
  `TurnRoute`) → `converse`, `explore`, `extract`, `clarify`, `tool`.
- Cờ bật: `intake` → `precheck` → `orchestrate` ↔ `run_jobs` → `gatekeep` → `finalize`, cùng nhánh lập lịch.
- Staging (`docs/prd/deployment-plan.md` §1: môi trường kiểm thử tích hợp và demo) không đặt biến này, nên đang chạy luồng
  cũ.

**Orchestrator còn dựa vào code của luồng cũ:**
- `precheck_node(_async)` gọi `classify_node(_async)` với `orchestrator_active = True` để dùng lại các luật trước LLM:
  `_travel_without_message`, `_guardrail_blocked_input`, `_guardrail_junk_input`, `_stop_rule`, `_option_pick`,
  `changes.detected`, `fares.chip_reply`, và `consent.plan_consented`, `asks_for_plan`, `says_yes`.
- Guardrail và tin rác ra `decision = simple` → node `converse`, node này bỏ qua LLM khi đã bị chặn.
- `extract` vẫn có thể ra `explore` hoặc `simple`, và `route_after_extract` vẫn trỏ tới `explore`/`converse`. Đọc code
  thì trên đường orchestrator, `extract` chạy khi đã đồng ý lập lịch, nên hai cạnh này có vẻ không xảy ra; lần chạy thử
  (1.3) cũng không thấy. D1 xác nhận thêm.
- `orchestration.py` dùng `exploration.once_praise`, `exploration.checked_suggestions`, `consent.*`,
  `classification.vietnam_today`, `tool_planning.catalog_destinations`.
- `jobs.py` dùng `fares` (job vé gọi `fares.answer`), `shown`, `classification.vietnam_today`, và
  `domain/itinerary/exploration.py`.

**Snapshot hiện chưa phát lại được cho orchestrator** (D2 sửa):
- `tests/unit/agents/behavior_snapshot/harness.py`: `frozen_world` chỉ cố định `datetime` và uuid. Orchestrator đo ngân
  sách bằng `time()` (`nodes.py:89`, `orchestration.py:125, 129, 149, 211`, `jobs.py:32, 384`) và chờ model tối đa
  `min(timeout_seconds, remaining)`. Khi ghi bằng LLM thật, một lượt có thể hết giờ và rơi vào câu dự phòng; khi phát lại
  thì chạy rất nhanh, nên đi nhánh khác.
- Harness không bật orchestrator và không có model riêng của nó.
- `record.py` mặc định dùng lại cassette cũ; `--fresh` mới ghi lại toàn bộ. Khoá cassette không có tên model.

### 1.2. Bốn vấn đề gọi tool (đọc code; D4 kiểm chứng bằng test và số đo)

Mọi lời gọi của các job trong một lượt dùng chung một bộ đếm `BudgetTools`: tối đa `MAX_TOOL_CALLS = 10` lời gọi, và
không quá ngân sách thời gian của lượt (`jobs.py:18, 25–38`). Lời gọi lấy danh sách điểm đến ở vòng đầu cũng tính vào bộ
đếm này (`orchestration.py:118–122`).

| # | Vấn đề | Chỗ trong code | Hậu quả |
|---|---|---|---|
| T1 | Tra vé nhiều điểm đến hết ngân sách trước khi lấy chuyến | `fares._anywhere` → `_origin_routes` (`fares.py:301–317`). Mỗi điểm đến trong catalog: liệt kê tuyến (tối đa 4 trang, `flights._all`), rồi liệt kê chuyến (tối đa 4 trang). Mọi điểm đến chạy song song, cùng một bộ đếm | Bộ đếm hết thì `JOB_BUDGET_EXHAUSTED` bị `except Exception` nuốt và trả `[]`. Điểm đến đó biến mất khỏi kết quả như thể không có chuyến. Điểm nào kịp tra là do may rủi |
| T2 | Job tìm nhiều trang dùng hết ngân sách trước khi trả kết quả | `_explore` (`jobs.py:189–207`): sắp theo giá kèm câu tìm thì quét **mọi** trang Search để lập `query_ids`. Sau đó `_page` lặp tiếp khi trang toàn thẻ đã xem (`:208–211`; job lấy tiếp `:280–283`) | Hết bộ đếm giữa chừng thì `_one` bắt lỗi và trả `status = failed`. Kết quả đã lấy được bị bỏ. Job khác cùng vòng có thể không còn lời gọi nào |
| T3 | Job lỗi tạm thời bị chặn thử lại vì đã ghi dấu trùng | `execute` (`jobs.py:387–395, 436`) ghi chữ ký job vào `turn_signatures` **trước khi chạy**, bất kể kết quả | Job hỏng vì quá giờ ở vòng 1 thì vòng 2 không chạy lại được. `jobs_progress = False` buộc trả lời ngay |
| T4 | Lấy chi tiết tuần tự hoặc lặp lại trong cùng lượt | `_explore`: `about_shown` (`:146–151`), `cheaper`/`dearer` (`:173`), mốc `near` (`:183`) gọi `get_product_detail` lần lượt từng thẻ. Không có bộ nhớ trong lượt. `fares.answer` liệt kê tuyến tới điểm đến ở `_routes`, rồi `flight_options` liệt kê lại đúng danh sách đó | Mỗi thẻ thêm một khoảng chờ tool. Cùng sản phẩm, cùng danh sách bị gọi lại ở vòng sau hoặc job khác, mỗi lần tốn một lời gọi của bộ đếm |

### 1.3. Chạy thử ngày 12/10 (trước D1, chỉ là tín hiệu)

Script ở scratchpad chạy 22 hội thoại (48 lượt) lấy từ ví dụ của AC (FR-AGT-06, AC-AGT-01, 05–08), mỗi hội thoại **một
lần**:
- Cờ orchestrator bật, `ITINERARY_DATA_MODE=inprocess`, LLM thật.
- Gọi `ItineraryPlanner.ainvoke` trong tiến trình, không qua HTTP hay Web. Chạy trên máy local, không phải staging.

LLM không tất định, và mỗi ca chỉ chạy một lần. D1 phải đo lại.

- **Thời gian mỗi lượt** (giây):
  - Lượt chỉ trả lời hoặc hỏi lại: 7–14.
  - Lượt có job: 17–39. Chậm nhất là "có chỗ nào rẻ hơn không" (39,4) và "chùa Thiên Mụ ở đâu" (28,8).
  - Hỏi vé: 8–14. Nút vé: 0,1.
  - Hỏi lại của nhánh lập lịch: 5–15.
- **Đường đi:** không lượt nào lỗi HTTP. Không lượt nào đi vào `classify` hay `explore`. Guardrail và tin rác vào
  `converse` (0,0 giây, không gọi LLM).
- **Lỗi thấy được:**
  - A08b "tao ở sài gòn, đi đâu cũng được miễn vé rẻ": trả lời "chưa thấy chuyến bay còn vé nào từ TP. Hồ Chí Minh trong
    30 ngày tới", 0 thẻ. Cùng lúc đó, A08a tìm được vé TP. Hồ Chí Minh → Hà Nội. Khớp với T1, nhưng chưa xác nhận nguyên
    nhân bằng log hay trace (D4).
  - F06f lượt 3 "có chỗ nào rẻ hơn không" (sau khi hỏi hồ bơi của khách sạn đầu):
    - 39,4 giây, hai vòng `run_jobs` và một lần `gatekeep` trả về để sửa câu.
    - 0 thẻ; câu trả lời là "chưa có thông tin các lựa chọn rẻ hơn".
    - Có thể do T2–T4; chưa xác nhận.
  - A08a lượt 1 chào vé bay 05:05 ngày 12/10, trong khi script chạy lúc gần 24 giờ cùng ngày. Cần xem có lọc chuyến đã
    cất cánh không.
  - A07d (người dùng cộc lốc) và A01a: câu trả lời hoặc câu hỏi lại dài, hỏi 5 thông tin trong một câu. "Đà Nẵng có gì
    chơi?" chỉ ra 1 thẻ (hai lần chạy).
- **Kiểm kê ký hiệu** (đọc cây gọi bằng AST và theo dõi lời gọi khi chạy test orchestrator):
  - Khoảng 68 hàm chỉ đến được từ node cũ. Hai thứ trong số đó vẫn được `converse` dùng khi chặn tin rác trên đường
    orchestrator, nên phải chuyển chứ không xoá: `unclear_input_reply` và thông điệp `UNCLEAR_INPUT`.
  - Test phải chuyển, không xoá: `test_guardrails.py`, `test_fares.py`, và hai ca trong `test_shown.py` còn đi luồng cũ.

  G0 làm đầy đủ sau demo.

### 1.4. Ghi chú "luồng cũ đóng băng" cho nhóm

Đã thay ngày 13/10: luồng cũ đã gỡ, nên các ghi chú bên dưới đổi thành "orchestrator là luồng duy nhất, không tạo lại luồng
cũ hay cờ" (`AGENTS.md` §3, `working-context.md` §2–3, skill bước 3). Comment và log cảnh báo của D0 đã gỡ cùng code.

Người dùng yêu cầu có ghi chú để nhóm không nhầm mà đi tối ưu luồng cũ. Luồng cũ là phần chỉ chạy khi
`ITINERARY_ORCHESTRATOR=off`:
- Phần LLM của `classify_node` (`TurnRoute`, `CLASSIFY_PROMPT`).
- `explore_node` cùng các hàm chỉ nó dùng trong `agents/steps/exploration.py` (`EXPLORE_PROMPT`, `ExploreNarration`).
- Phần trả lời bằng LLM của `converse_node`.

Orchestrator vẫn dùng chung, nên **không** đóng băng:
- Các luật trước LLM nằm trong `classify_node` mà `precheck` gọi.
- `converse` khi guardrail chặn.
- `clarify` và nhánh lập lịch.

| Nơi ghi | Làm ở | Nội dung |
|---|---|---|
| `AGENTS.md` §3 | Lượt này (tài liệu) | Quy tắc cho mọi người và mọi coding agent: không sửa, tune, tối ưu, thêm test hay tính năng cho luồng cũ; làm việc trên orchestrator. Trước D3, chạy local với `ITINERARY_ORCHESTRATOR=on` |
| `docs/spec/agent/working-context.md` §2, §3 | Lượt này | Hàng "Tune classify/clarify/converse" chỉ rõ phần nào đóng băng; thêm hàng "Tune orchestrator"; sơ đồ cờ tắt ghi là luồng cũ |
| Skill `building-itinerary-agent` bước 3 | Lượt này | Một dòng trỏ về AGENTS.md §3 |
| Code (D0, xong 13/10) | D0 | Comment cho từng phần ở danh sách trên. Log cảnh báo `startup.itinerary_legacy_flow_active` lúc khởi động khi cờ tắt. Đoạn "không thêm ca mới" ở docstring các file test chỉ của node `explore` cũ |

### 1.5. Ca test đã xoá cùng luồng cũ (13/10), phải kiểm lại ý AC trên orchestrator

Người dùng chốt gỡ hẳn luồng cũ ngay (13/10, `history/2026-10-13-go-luong-cu-orchestrator-duy-nhat.md`). Các ca dưới đây
kiểm node `classify`, `explore` hoặc phần LLM của `converse` nên bị xoá cùng code. Ý AC trong đó **không bị bỏ**:
- Ý nào chạm kịch bản demo thì kiểm ở D1, D6 và sửa ở D5.
- Ý còn lại vào bảng AC của G0, làm ở G3.

Bản cũ của từng ca còn trong git (`a50c5e62`).

| Ý AC | Ca đã xoá |
|---|---|
| Hỏi về một nơi cụ thể: nơi đó đứng đầu, chỉ trả lời nơi đó, có giờ mở cửa (FR-AGT-06, AC-AGT-06) | `test_explore_asked_place.py` (8 ca); `test_exploration.py::NamedPlaceTests::test_the_named_place_comes_first_with_its_opening_hours_for_the_llm`; `test_place_facts.py::AskedPlaceAnswerTests`, `PlaceSearchTests` (2 ca tên LLM đọc ra) |
| Quanh một nơi, khách sạn trong bán kính của mốc (FR-AGT-06) | `test_open_question.py::test_hotels_near_the_old_quarter_are_those_within_the_radius_of_it`, `test_the_place_to_be_near_is_read_from_the_question`. Lỗi D1-01 ("gần Hồ Gươm" ra 0 thẻ) thuộc ý này |
| Nơi có ở nhiều thành phố thì hỏi lại kèm nút từng nơi; nhớ câu hỏi còn dở (AC-AGT-07 "khó hiểu") | `test_open_question.py` (6 ca còn lại); `test_place_facts.py::UnderstoodCityTests` |
| Lời dẫn kể chuyện, đủ ý, cụm khen một lần (AC-AGT-07 "Thẻ") | `test_explore_storytelling.py` (phần `once_praise`, `about` chuyển sang `test_replies.py`); `test_exploration.py::ChatTextTests`; `test_messy_replies.py::FallbackLineTests` |
| Đồng ý lập lịch theo nhiều cách nói, điểm đến trống thì khám phá trước (FR-AGT-01, FR-AGT-06) | `test_exploration.py::ConsentTests` (6 ca), `ExploreFlowTests`; `test_itinerary_runtime.py::test_dont_know_after_the_trip_details_question_shows_the_prefilled_form` |
| Không gợi ý lại nơi bị chê (AC-AGT-07 "khó tính") | `test_exploration.py::RejectedPlaceTests` |
| Lọc khách sạn theo sở thích (hồ bơi), rẻ trước cho cả thành phố (FR-AGT-06) | `test_exploration.py::HotelPreferenceTests::test_the_soft_filter_keeps_matching_hotels_only_when_enough_remain`, `HotelPriceOrderTests`, `AmenityTests`; `test_place_facts.py::CheapFirstTests` |
| Tra cứu lỗi nói "chưa tải được", không nói "không có" (invariant, T1–T4) | `test_exploration.py::ExploreSearchFailureTests` |
| Câu "không biết" sau câu hỏi thông tin chuyến thì hiện form (AC-AGT-01) | `test_itinerary_runtime.py::test_a_vague_answer_goes_from_classify_to_the_form_without_extracting` |
| Ngoài phạm vi trả lời 200 kèm nút; chào hỏi không hỏi số ngày (AC-AGT-07) | `test_itinerary_runtime.py::test_refusal_never_calls_product_tools`, `test_greeting_uses_llm_answer_without_calling_product_tools`, `test_conversation_label_goes_to_converse_without_extracting` |
| Câu hỏi khác trong cùng tin nhắn vé thành nút (AC-AGT-08) | `test_fares.py::test_other_questions_in_the_same_message_become_buttons`, `FareRouteTests` |
| Nút "tiếp tục lập lịch" chỉ khi chuyến chưa đủ (AC-AGT-07 "Nút") | `test_exploration.py::PlanChipTests` |
| Nhãn của LLM phân loại (không còn ý AC riêng) | `test_extract.py` (đổi tên từ `test_classify.py`): `RouteTests`, `ClassifyPromptTests`, `test_an_unmatched_stop_is_still_read_by_the_llm` |

Ý AC đã thấy **không đạt** khi chạy test trên orchestrator, mang `xfail(strict=True)`:
- AC-AGT-08, nút do code tạo cho câu trả lời vé ("Đắt nhất thì sao?", "<nơi> có gì chơi?") bị mất, chỉ còn nút lập lịch.
- Test tương ứng: `test_fares_followups.py` (2 ca), `test_fares_messy.py` (1 ca). Sửa ở D5.

## 2. Trước demo

### D0. Đánh dấu luồng cũ trong code (chỉ comment và log, không đổi hành vi) — xong 13/10

Entry: `history/2026-10-13-d0-danh-dau-luong-cu.md`. Comment, log cảnh báo và đoạn đóng băng trong test đã gỡ cùng luồng
cũ ngày 13/10.

- Phần tài liệu ở mục 1.4 đã làm trong lượt sửa plan này.
- Phần code: comment theo một mẫu, bắt đầu bằng `LUỒNG CŨ — ĐÓNG BĂNG (chốt 13/10/2026)` (grep được). Mỗi comment ghi
  chỉ chạy khi `ITINERARY_ORCHESTRATOR=off`, không sửa, không tune, gỡ sau demo, và trỏ về AGENTS.md §3.
  - Chỗ thêm:
    - `nodes.py`: `classify_node(_async)` (ghi rõ chỉ phần LLM; các luật trước LLM vẫn dùng chung qua `precheck`);
      `converse_node(_async)` (chỉ phần LLM; hai nhánh câu cố định vẫn dùng chung); `explore_node(_async)`.
    - `classification.py`: `route_input`, `route_result`, `understood`.
    - `models.py`: `TurnRoute`, `ExploreNarration`.
    - `prompts.py`: `CLASSIFY_PROMPT`, `EXPLORE_PROMPT`.
    - `routing.py`: `route_after_classify`, `route_after_explore`; hai đích cũ của `route_after_extract`.
  - Với model Pydantic (`TurnRoute`, `ExploreNarration`), ghi chú là comment `#` đặt trên class, **không** vào
    docstring. Lý do: docstring thành mô tả trong JSON schema gửi LLM, nên sửa nó là đổi payload. Đã so JSON schema
    trước và sau: không đổi. Prompt chỉ có comment ngoài chuỗi.
  - `agents/steps/exploration.py`: đầu module liệt kê phần còn dùng chung (`once_praise`, `checked_suggestions`,
    `CATALOG_HINT`, `conversation_templates`, `about`); phần còn lại đóng băng.
- Log cảnh báo `startup.itinerary_legacy_flow_active` một lần lúc khởi động khi cờ khác `on`. Log đặt ở `main.py`, cạnh
  các log `startup.*` khác, thay vì `graph.py` như bản plan trước: graph được dựng lại mỗi request, còn startup chạy một
  lần mỗi tiến trình.
- Test chỉ của node `explore` cũ: `test_explore_storytelling.py`, `test_open_question.py`, `test_explore_asked_place.py`
  thêm đoạn đóng băng vào docstring module, "không thêm ca mới". Các file trộn phần dùng chung (`test_classify.py`,
  `test_exploration.py`, `test_routing.py`, `test_itinerary_runtime.py`, `test_place_facts.py`) không đánh dấu.
- Kiểm tra:
  - Unit agents, domain, architecture: 2112 passed, có snapshot luồng cũ, không ghi lại.
  - Cả bộ backend: 2938 passed, 36 skipped.

### D1. Kiểm chứng demo (không sửa source) — xong 13/10

**Môi trường.** Staging là môi trường demo. Staging nhận mặc định mới ở D3, sau khi snapshot đã kiểm soát được (D2).
Vì vậy:
- Trước D3: chạy trên máy local dựng giống staging. Cùng snapshot catalog, cùng model và provider, cùng các
  timeout `ITINERARY_*_TIMEOUT_SECONDS`, `ITINERARY_DATA_MODE=inprocess`, cờ bật bằng biến môi trường của shell. Lệnh
  dựng:
  - `make demo-db`, với `--as-of` đủ gần ngày chạy để ngày trong kịch bản nằm trong cửa sổ bán 30 ngày (AGENTS.md §6.2).
  - `docker compose up -d --wait postgres weaviate`.
  - Backend: `HF_HUB_OFFLINE=1 ITINERARY_ORCHESTRATOR=on make backend-local`.
  - Web: `npm run dev` trong `src/frontend`.
- Sau D3: D6 chạy lại toàn bộ trên staging.

**Kịch bản.** Mỗi kịch bản là một hội thoại nhiều lượt. Ngày ghi tương đối với ngày chạy; ví dụ dưới đây ứng với ngày
12/10.

| # | Kịch bản | Các lượt | Kiểm gì |
|---|---|---|---|
| K1 | Khám phá → hỏi thêm → khách sạn gần một nơi → rẻ hơn → lập lịch → đổi phương án | "Hà Nội có gì chơi?" · "chỗ thứ hai mở cửa mấy giờ, vé bao nhiêu?" · "tìm khách sạn gần Hồ Gươm" · "có chỗ nào rẻ hơn không?" · "ok lên lịch 3 ngày từ thứ 7 này cho 2 người, đi từ TP. Hồ Chí Minh" · bấm phương án khách sạn khác · mở chi tiết một thẻ | FR-AGT-06, AC-AGT-06, AC-AGT-01; T2, T4 |
| K2 | Hỏi vé → hỏi tiếp → vé nhiều điểm đến → lập lịch | "vé sg ra hn bao nhiêu" · "ngày 24/10 thì sao, đi buổi sáng" · "từ Hà Nội đi đâu rẻ nhất?" · "lên lịch chỗ rẻ nhất đó 3 ngày cho mình" | AC-AGT-08, AC-AGT-05; T1, T4 |
| K3 | Lập lịch đủ thông tin ngay rồi đổi phương án | "Hà Nội đi Đà Nẵng 3 ngày từ 24/10, 2 người lớn, thích biển, ngân sách 10 triệu" · "đổi sang khách sạn có hồ bơi" · "bỏ vé máy bay, mình tự đi" · "thêm 1 ngày nữa" | AC-AGT-01, AC-AGT-05, FR-AGT-07 |
| K4 | Khách sạn theo điều kiện, nhiều trang | "khách sạn có hồ bơi ở Đà Nẵng, rẻ nhất trước" · "xem thêm" · "đắt hơn chút cũng được, chỗ nào đẹp nhất?" · "chỗ thứ hai còn phòng ngày 24/10 không?" | FR-AGT-06; T2, T3, T4 |
| K5 | Người dùng mơ hồ, cộc lốc | "không biết đi đâu" · "cứ chọn đại" · "chán, đi rồi" · "ok lên lịch đi" | AC-AGT-07, AC-AGT-06 |
| K6 | Gia đình có trẻ nhỏ | "gia đình mình 2 người lớn 2 bé đi Nha Trang cuối tuần này" · "đi từ TP. Hồ Chí Minh, ngân sách 15 triệu" · "khách sạn gần biển hơn được không?" | FR-AGT-01, AC-AGT-01 |
| K7 | Lỗi và chậm (chỉ chạy ở local) | K1 lượt 3 và K2 lượt 3, chạy trong hai điều kiện: dừng Weaviate; đặt `ITINERARY_TOOL_TIMEOUT_SECONDS` rất nhỏ | Câu trả lời nói rõ chưa tra được và gợi ý thử lại; không nói "không có", không lộ chữ kỹ thuật |

**Cách diễn đạt khác.** Mỗi kịch bản K1–K6 có thêm một bản cùng ý, khác chữ: không dấu, viết tắt, sai chính tả, câu
dài nhiều ý, tiếng lóng. Ví dụ: "ha noi co gi choi", "ks gần hồ gươm", "vé sg-hn bn tiền", "rẻ hơn tí đc ko", "nhà
mình 4 người, 2 đứa nhỏ, muốn đi biển gần gần".

**Cách chạy.**
- K1–K6: bản chính chạy **3 lần**, bản diễn đạt khác chạy 1 lần. Chạy qua `POST /api/v1/assistant/itineraries/stream`
  bằng script ở scratchpad đọc SSE. Script ghi mốc thời gian của từng `node.completed` và thời điểm `run.completed`.
- Mỗi kịch bản chạy thêm một lần trên Web, có quay màn hình, để xem tiến trình, thẻ, panel chi tiết và đổi phương án như
  sếp sẽ thấy.

**Ghi cho mỗi lượt:**
- `requestId`, tổng thời gian, thời gian từng node, số vòng `orchestrate`, số lời gọi tool.
- `message` của các event có chữ "budget", "fallback", "unavailable" (sau D2 thì ghi mã nguyên nhân).
- Status, số thẻ theo loại, gợi ý, form.
- Đạt hay không theo AC mà kịch bản ghi.
- Lỗi hoặc điều khó chịu nhìn thấy (ảnh chụp).

Với lượt lập lịch, ghi riêng mốc `compose` xong và mốc có câu trả lời. Plan tiến trình 3.5 dùng hai mốc này để quyết có
làm preview hay không.

**Danh sách lỗi.** Mỗi lỗi gồm: mã (`D1-nn`), kịch bản và lượt, triệu chứng, bằng chứng (`requestId`, trace LangSmith),
lớp nghi ngờ theo skill, AC liên quan, và mức độ:
- **chặn demo**: sai dữ liệu, vi phạm grounding, lỗi 5xx hoặc `run.failed`, lộ chữ kỹ thuật, tra cứu thất bại mà nói
  không có dữ liệu, chi tiết hoặc đổi phương án không chạy.
- **xấu**: trả lời dài hoặc lan man, thiếu lý do chọn, ít thẻ dù catalog có, chậm mà không có phản hồi, hỏi lại thừa.
- **nhỏ**: còn lại.

Với T1–T4 (mục 1.2), ghi lượt nào chạm tới và có ảnh hưởng thấy được không.

**Kết quả.**
- Số liệu thô ghi vào `src/evaluation/reports/eval-YYYY-MM-DD-demo-orchestrator.md` theo AGENTS.md §7: commit, cấu hình,
  bảng số nguyên văn, lệnh tái sinh.
- Danh sách lỗi và mức độ ghi vào mục "Kết quả D1" của plan này.
- Có entry history.
- Báo người dùng trước khi sang D4, D5.

**Xong khi:**
- Mỗi lượt của mọi lần chạy có một dòng số liệu. Lượt lỗi hoặc timeout cũng ghi, không bỏ.
- Mỗi lỗi có mức độ và bằng chứng.
- Có số đo để quyết về preview.

**Kết quả D1 (xong 13/10).** Báo cáo: `src/evaluation/reports/eval-2026-10-13-demo-orchestrator.md`.
- 100 lượt, 0 lỗi HTTP hay `run.failed`. p50 12,7 giây, p95 24,0 giây, max 34,2 giây. Lượt có job p50 18,6 giây.
- Preview: 9/9 lượt lập lịch có từ 2 giây trở lên giữa `max(5 giây, t_compose)` và câu trả lời. Tiêu chí ở plan tiến trình
  3.5 đạt; người dùng có thể chốt Phần C.
- Lỗi cần sửa trước demo (D4, D5):

| Mã | Mức | Việc | Bước |
|---|---|---|---|
| D1-01 | chặn demo | "gần Hồ Gươm" không ra mốc, 0 thẻ: mốc `near` khớp tên bằng từ chung | D5 |
| D1-02 | chặn demo | "từ Hà Nội đi đâu rẻ nhất" nói không có chuyến | D4 (T1) |
| D1-03 | chặn demo | Hỏi còn phòng thẻ thứ hai: câu dự phòng 7 từ, không trả lời | D5 |
| D1-04 | chặn demo | "đổi sang khách sạn có hồ bơi" sau khi có lịch: chỉ khám phá, không đổi lịch | D5 |
| D1-05 | xấu | "bỏ vé máy bay" sau khi có lịch: không lập lại lịch | D5 |
| D1-06 | xấu | Mất nút của câu trả lời vé (AC-AGT-08; 3 test `xfail` strict) | D5 |
| D1-07 | xấu | Lượt mơ hồ, chê không có nút gợi ý (AC-AGT-07) | D5 |
| D1-08 | xấu | Hỏi riêng khách sạn mà chỉ 1–2 thẻ | D5 (xem dữ liệu trước) |
| D1-09 | xấu | Lời diễn giải lịch 186–364 từ | D5 |
| D1-10 | xấu | "cuối tuần này" lúc hiểu 2 ngày, lúc hỏi lại | D5 |
| D1-11..13 | nhỏ | Hỏi ngân sách một lần (đúng AC-AGT-01); chọn phương án khi chưa có lịch; thiếu giờ mở cửa trong dữ liệu | Sau demo |

- Kịch bản K1 nên nêu ngân sách (hoặc "không có ngân sách") để demo đi thẳng tới lịch. Đây là chỉnh kịch bản, không che
  lỗi: hỏi ngân sách một lần là hành vi AC-AGT-01.

### D2. Mã nguyên nhân cho câu dự phòng, và snapshot kiểm soát thời gian (refactor runtime, không đổi hành vi) — xong 13/10

Entry: `history/2026-10-13-d2-ma-nguyen-nhan-va-dong-ho.md`.

**Vấn đề.** Trước D2, một event gộp nhiều nguyên nhân khác nhau:
- `run_jobs` ghi `execution budget exhausted` cho trần vòng (`MAX_ROUNDS = 3`), trần tool (`MAX_TOOL_CALLS = 10`) và
  hết thời gian.
- `orchestrate` đặt `force_answer` cho cả ba mà không ghi nguyên nhân, và gộp mọi lỗi model thành
  `model unavailable, fallback`.
- `BudgetTools._call` ném `JOB_BUDGET_EXHAUSTED` cho cả trần tool lẫn hết thời gian.
- `gatekeep` cho sửa câu hay không cũng tuỳ ba điều kiện đó.

Trần vòng và trần tool là hành vi tất định; hết giờ và quá giờ phụ thuộc tốc độ mạng và model, nên không phát lại được.

**Đã làm.**
- `agents/steps/limits.py`: mã `TIME_LIMIT`, `ROUND_LIMIT`, `TOOL_LIMIT`, `MODEL_TIMEOUT`, `MODEL_ERROR`, `TOOL_TIMEOUT`;
  tập `UNREPLAYABLE` (bốn mã phụ thuộc thời gian hoặc provider).
- `orchestration.limit_reason(state, budget_seconds)`: phanh đầu tiên đã chạm, đúng thứ tự điều kiện cũ (vòng, tool,
  thời gian). `orchestrate`, `run_jobs`, `gatekeep` dùng chung hàm này; điều kiện tương đương hệt bản cũ.
- Gắn mã vào metadata `reason` của event và vào `turn_limit_reason` (chỉ trong lượt, không lưu, không vào payload LLM):
  - `orchestrate`: hết giờ trước khi gọi model → `TIME_LIMIT`; model quá hạn → `MODEL_TIMEOUT`; lỗi khác →
    `MODEL_ERROR`; chạm phanh → `turn_limit_reason`.
  - `run_jobs`: phanh trước khi chạy → `ROUND_LIMIT`/`TOOL_LIMIT`/`TIME_LIMIT`; vòng này chạm trần vòng hoặc trần
    tool → `turn_limit_reason`; event "jobs executed" có `failed_reasons`.
  - `gatekeep`: event cuối có `reason` khi không được sửa câu vì phanh.
  - `BudgetTools`: `ToolError("JOB_BUDGET_EXHAUSTED", reason=TOOL_LIMIT|TIME_LIMIT)`. Quá hạn vẫn ném `TimeoutError`
    như cũ, có thêm thuộc tính `reason = TOOL_TIMEOUT`. Job hỏng ghi `reason` riêng, mã `error` giữ nguyên.
  - `nodes._llm_failed`: event `LLM_UNAVAILABLE` có `reason` lấy từ lỗi đang xử lý.
- Dòng log `itinerary.turn_limit` (WARNING, có `request_id`, `node`, `reason`) mỗi lần dừng sớm, để đọc nguyên nhân từ log
  backend (D1, D6) mà không phải mở state.
- Không đổi chữ của `message`, node path hay mã lỗi trả ra ngoài.
- `agents/clock.py` (`now()`); `nodes.py`, `orchestration.py`, `jobs.py` đọc giờ qua module này. Chạy thật không đổi
  giá trị nào.

**Harness.**
- `frozen_world` cho `clock.now` đứng yên, nên không lượt nào chạm `TIME_LIMIT` khi ghi hay phát lại.
- Orchestrator có ngân sách 600 giây trong snapshot, giống nhau khi ghi và khi phát lại.
- Harness dựng graph theo **mặc định của cờ trong code** (`Settings`), không theo `.env` của máy chạy. Lý do: `.env` của
  máy dev đang bật cờ, nếu harness theo `.env` thì CI và máy dev phát lại hai graph khác nhau.
- Model riêng của orchestrator bọc trong `CassetteLlm(model="orchestrator")`. Khoá cassette của nó có thêm tên model;
  model chung giữ khoá cũ, nên cassette cũ đọc được nguyên.

**Ghi.**
- Khác plan cũ, không gắn mã ở 13 chỗ `wait_for` còn lại của nhánh lập lịch. Thay vào đó, lúc ghi, `CassetteLlm` và
  `ToolCassette` tự ghi nhận mọi lời gọi thật bị quá hạn hoặc lỗi. Cách này phủ mọi chỗ gọi, kể cả chỗ thêm sau này, và
  không phải sửa code runtime ở các chỗ đó.
- `harness.unreplayable(events, failures)` gộp mã trong event và lời gọi thật hỏng.
- `record.py` từ chối kịch bản có lượt như vậy và ghi lại tối đa 3 lần. Vẫn bị từ chối thì dừng, in tên kịch bản cùng
  nguyên nhân, và không lưu snapshot. `ROUND_LIMIT`, `TOOL_LIMIT` được giữ.

**Test** (`tests/unit/agents/test_turn_limits.py`, 20 ca):
- Thứ tự mã khi nhiều điều kiện cùng đúng.
- `run_jobs`: trần vòng, trần tool, hết giờ, và trần vòng chạm trong vòng này.
- `orchestrate`: hết giờ trước khi gọi model, model chậm, model lỗi, trả lời trong hạn.
- `BudgetTools`: trần tool, hết hạn, tool chậm (kể cả `reason` của job hỏng).
- `_llm_failed`.
- `unreplayable` và `record.rejected`.
- Khoá cassette theo model; ghi nhận lời gọi thật quá hạn; đồng hồ đứng yên.

**Kiểm tra.**
- Unit agents, domain, architecture: 2132 passed.
- Snapshot luồng cũ phát lại khớp, không ghi lại. Đây là bằng chứng D2 không đổi hành vi.

### D3. Orchestrator thành luồng duy nhất và ghi baseline (đổi hành vi) — ghi xong 13/10, chờ người dùng duyệt

Chờ: D2 xong. Đề xuất đã chốt ngày 13/10 và đã áp dụng vào PRD (AGENTS.md §8).

**Đã làm khác bản plan trước.** Plan định bật cờ `itinerary_orchestrator = "on"` và giữ luồng cũ để quay về. Sau D2,
người dùng chốt gỡ hẳn luồng cũ và cờ (đầu plan). Vì vậy D3 gồm luôn phần xoá của G5, G6 và phần tài liệu của G7 (mục 4).
Không còn cờ để quay về khi sự cố; quay về bằng cách triển khai lại bản trước (`a50c5e62`). Entry:
`history/2026-10-13-go-luong-cu-orchestrator-duy-nhat.md`.

- Thêm 6 kịch bản K1–K6 (bản chính) vào `scenarios.json` của snapshot: 63 kịch bản.
- Kịch bản chạm trần tool: không cần thêm. Sáu lượt của bản ghi chạm `TOOL_LIMIT`, gồm demo-K2 lượt 3. Harness giữ mã
  `ROUND_LIMIT`/`TOOL_LIMIT` trong event để snapshot kiểm chúng. Chưa lượt nào chạm `ROUND_LIMIT`; trần vòng có unit
  test `test_turn_limits.py`.
- Ghi lại toàn bộ bằng `inprocess`, LLM thật, `--fresh`: 191 lượt, không kịch bản nào bị từ chối.
- Phát lại offline xanh, `cassetteMiss` và `toolMiss` rỗng.
- Bảng tóm tắt từng hội thoại, đánh giá theo AC:
  `src/evaluation/reports/eval-2026-10-13-d3-snapshot-orchestrator.md`.

**Kết quả so với luồng cũ** (57 kịch bản có bản trước):
- Tốt hơn: hỏi vé trả lời bằng vé thật; nêu một nơi thì khám phá có thẻ thay vì hỏi thông tin chuyến.
- Kém hơn, có tính hệ thống:
  - Nút gợi ý: trung bình 2,23 → 1,00 mỗi lượt hỏi lại hoặc khám phá; lượt không nút 13 → 39 (D1-07 rộng hơn).
  - Đổi khách sạn có hướng sau khi có lịch ("rẻ hơn", "có hồ bơi") không đổi lịch (D1-04 rộng hơn, AC-AGT-05).
  - Chê nơi vừa gợi ý thì chỉ hỏi chọn, không thẻ (D3-04).
- Lỗi mới: D3-01 (chặn demo: trả lời câu hỏi lại bằng điểm đến bị coi là khám phá, lượt sau hỏi lại điểm đến), D3-02,
  D3-03 (xấu), D3-05 (nhỏ).
- T1 xác nhận và phát lại được: năm lượt vé "đi đâu cũng được" chạm `TOOL_LIMIT` rồi nói không có chuyến.

Đã kiểm: các lượt kém hơn đi đúng các luật trước LLM như orchestrator lúc còn cờ (`precheck` giống hệt nhánh
`orchestrator_active` tại `a50c5e62`). Đây là hành vi sẵn có của orchestrator, không do việc gỡ code gây ra.

**Dừng** chờ người dùng duyệt (R2). Snapshot đã duyệt là baseline cho D4, D5 và plan tiến trình. Các lỗi D3-xx vào danh
sách của D5.

### D4. Kiểm chứng rồi sửa bốn vấn đề gọi tool (đổi hành vi có chủ ý)

**Nguyên tắc chung:**
- **Kiểm chứng trước.**
  - Mỗi vấn đề có một test tái hiện, fail trên code hiện tại, và có số liệu từ D1 cho biết kịch bản nào bị ảnh hưởng.
  - Riêng A08b và F06f (1.3), xem log hoặc trace của đúng lượt để biết lời gọi nào hỏng hay bị bỏ và vì sao, trước khi
    sửa.
  - Vấn đề không ảnh hưởng kịch bản demo nào, kể cả bản diễn đạt khác, thì ghi lại và hoãn tới sau demo.
- **Không tăng giới hạn mù quáng.** Không đổi `MAX_TOOL_CALLS`, `MAX_ROUNDS`, các timeout hay ngân sách thời gian trong
  lúc sửa. Sau khi sửa, đếm số lời gọi thật của từng kịch bản. Nếu một kịch bản hợp lệ vẫn cần nhiều hơn giới hạn, thì
  báo người dùng kèm số đếm, rồi mới đổi.
- **Thất bại khác với không có.** Kết quả tra cứu có trạng thái riêng cho từng trường hợp: `ok`, `empty` (tra xong, không
  có), `partial` (tra được một phần), `failed` (không tra được, kèm mã nguyên nhân của D2).
  - Câu do code viết (vé) không bao giờ nói "không có" khi trạng thái là `failed` hoặc `partial`.
  - Bản rút gọn gửi LLM ghi rõ trạng thái này.
  - Ý do LLM viết thì kiểm bằng golden case chạy LLM thật (K7).
- Mỗi lần sửa: snapshot chỉ được lệch ở các hội thoại dự kiến. Ghi lại phần lệch bằng `record` không `--fresh`, để lời
  gọi LLM không đổi được phát lại từ cassette. Entry history liệt kê hội thoại nào lệch và vì sao.

**T1. Tra vé nhiều điểm đến.**
- Kiểm chứng:
  - Test với catalog giả 8 điểm đến và bộ đếm 10 lời gọi. Kết quả hiện tại: có điểm đến bị bỏ im lặng, và câu trả lời
    không nói gì về điểm chưa tra.
  - Đếm số lời gọi thật của A08b và K2 lượt 3.
- Hướng sửa (chọn sau khi có số):
  - Lấy tuyến **một lần**: liệt kê tuyến bay, lọc `originCity` bằng code, thay cho liệt kê tuyến theo từng điểm đến.
    Trước khi dùng, kiểm `list_products` có liệt kê được mọi tuyến không cần `destination` không, và cần bao nhiêu trang.
  - Chỉ lấy chuyến của các tuyến xuất phát từ nơi đi. Thứ tự tất định (theo catalog), không để may rủi quyết.
  - Mỗi điểm đến có trạng thái `ok`, `empty` hoặc `failed`. Câu trả lời nêu điểm chưa tra được ("Chưa tra được giá đi Huế,
    Đà Lạt"), kèm gợi ý thử lại. Không gộp các điểm đó vào "không có chuyến".
  - Không đủ lời gọi cho mọi tuyến thì trả kết quả của phần đã tra và ghi rõ là chưa đủ.
- Test:
  - Có điểm đến lỗi thì câu trả lời nêu tên điểm đó, không nói "chưa thấy chuyến bay nào".
  - Đếm lời gọi trước và sau khi sửa.
  - A08b trên catalog giả có tuyến TP. Hồ Chí Minh → Hà Nội thì tìm thấy tuyến đó.

**T2. Job tìm nhiều trang.**
- Kiểm chứng:
  - Test với Search giả có `total = 400` (8 trang) cho câu "khách sạn có hồ bơi, rẻ nhất trước". Kết quả hiện tại: job
    `failed`, kết quả đã lấy bị bỏ, job khác cùng vòng không còn lời gọi.
  - Đo số trang thật cần cho K4 trên catalog.
- Hướng sửa:
  - Kiểm `search_products` có sắp theo giá trong phạm vi câu tìm không (contract `paths/search.yaml`). Có thì dùng nó,
    mỗi trang một lời gọi, bỏ việc quét hết trang.
  - Không có thì đặt số trang tối đa cho bước quét phạm vi, theo số đo ở trên. Đạt giới hạn thì ghi `partial`.
  - Hết lời gọi hoặc quá giờ giữa chừng thì trả `partial` cùng các sản phẩm đã lấy và `source_more`, không trả `failed`.
  - Các job cùng vòng chia số lời gọi còn lại; mỗi job được ít nhất một lời gọi trước khi job khác lấy trang thứ hai.
- Test:
  - Nhiều trang thì có kết quả từng phần, ghi `partial`.
  - Hai job cùng vòng đều có kết quả.
  - Kết quả của job một trang không đổi.
  - Lượt sau ("xem thêm") đi tiếp từ chỗ đã dừng.

**T3. Thử lại job lỗi tạm thời.**
- Kiểm chứng: test với tool quá giờ ở lần gọi đầu, chạy được ở lần sau, và LLM giả gửi lại đúng job đó ở vòng 2. Kết quả
  hiện tại: vòng 2 bỏ qua job, buộc trả lời.
- Hướng sửa:
  - Chỉ ghi chữ ký cho job có kết quả cuối: `ok`, `empty`, `partial`, `asked`, `answered`, `unavailable`.
  - Job `failed` vì `TOOL_TIMEOUT` hoặc lỗi tạm thời của nguồn được thử lại **tối đa một lần** mỗi lượt. Đếm số lần thử
    trong state của lượt.
  - Job `failed` vì `TOOL_LIMIT` hoặc `TIME_LIMIT` thì không thử lại, vì không còn ngân sách.
- Test:
  - Lần hai chạy và có kết quả.
  - Lỗi hai lần thì không thử lần ba, và câu trả lời nói chưa tra được.
  - Job đã `ok` gửi lại vẫn bị bỏ như hiện nay.

**T4. Lấy chi tiết và danh sách trong cùng lượt.**
- Kiểm chứng:
  - Test với tool giả trễ 1 giây cho mỗi lời gọi chi tiết. Kết quả hiện tại: "rẻ hơn" trên 4 thẻ mất khoảng 4 giây chờ
    tool và tốn 4 lời gọi.
  - Cùng sản phẩm ở vòng 2 lại tốn thêm lời gọi.
  - Đếm số lời gọi lặp trong K1, K2, K4.
- Hướng sửa:
  - Bộ nhớ đệm trong lượt cho `get_product_detail` (theo `productId`) và `list_products` (theo tham số). Lưu trong khoá
    state riêng của lượt; khoá này không vào `working_state` lưu lại, không vào payload LLM, và được xoá khi lượt mới bắt
    đầu.
  - Lỗi không được lưu vào bộ nhớ đệm. Lời gọi trúng bộ nhớ đệm không tính vào bộ đếm.
  - Các lời gọi chi tiết độc lập chạy song song bằng `asyncio.gather`. `BudgetTools` giữ chỗ trước khi chờ, nên trần
    lời gọi vẫn đúng.
  - `fares.answer` dùng lại danh sách tuyến đã lấy ở `_routes` thay vì `flight_options` gọi lại.
- Test:
  - 4 thẻ thì tổng thời gian chờ khoảng 1 giây, không phải 4.
  - Vòng 2 không gọi lại.
  - Lỗi không bị nhớ.
  - Trần 10 lời gọi vẫn đúng khi chạy song song.

**Kiểm tra sau D4:**
- Unit agents, domain xanh. Snapshot chỉ lệch ở hội thoại dự kiến.
- Chạy lại các kịch bản D1 có liên quan (3 lần): ghi số lời gọi, thời gian, và lỗi còn lại.

### D5. Sửa lỗi demo từ danh sách D1 (đổi hành vi có chủ ý)

- Danh sách: D1-xx (`src/evaluation/reports/eval-2026-10-13-demo-orchestrator.md`) và D3-xx
  (`src/evaluation/reports/eval-2026-10-13-d3-snapshot-orchestrator.md`). Lượt của snapshot là bằng chứng phát lại
  được; dùng nó làm test fail trước khi sửa khi lỗi do code quyết.
- Sửa mọi lỗi "chặn demo" và "xấu". Lỗi "nhỏ" để sau demo, trừ khi sửa rất rẻ và không chạm phần đang sửa khác.
- Thứ tự theo điều người xem thấy được (yêu cầu người dùng 12/10):
  1. Câu trả lời gọn, có lý do chọn rõ.
  2. Thẻ đẹp và đủ.
  3. Xem chi tiết và đổi phương án chạy được.
  4. Khi chậm hoặc lỗi vẫn có phản hồi hữu ích.
- Mỗi lỗi:
  - Có golden case (ý do LLM quyết) hoặc unit test (ý do code quyết), fail trước khi sửa.
  - Sửa đúng lớp theo skill `building-itinerary-agent`.
  - Kiểm lại trên bản diễn đạt khác.
- Ý AC "không đạt" mà kịch bản demo chạm tới được làm ở đây; đó là một phần của G3. Ý AC không thuộc kịch bản demo để
  G3 sau demo.
- Lỗi nằm ở giao diện (thẻ, panel chi tiết, đổi phương án) thì sửa trong `src/frontend/src/features/itinerary/widget/`.
  Có hai đề xuất đang chờ chốt chạm cùng chỗ: `2026-10-12-the-khach-san-chon-mot-cham.md` và
  `2026-10-12-lich-trinh-ban-do-man-hep.md`. Sửa nào đổi hành vi so với PRD thì đi qua đề xuất.
- Kiểm tra: unit agents, domain, contract; golden case mới chạy LLM thật 3 lần (pass^3); snapshot chỉ lệch ở hội thoại
  dự kiến.

### D6. Tổng duyệt trên staging

- Triển khai lên staging với mặc định mới.
- Chạy lại toàn bộ D1 (K1–K6: bản chính 3 lần, bản diễn đạt khác 1 lần) trên staging với LLM thật. K7 chạy ở local.
- So số với D1: thời gian theo loại lượt, số lời gọi, lỗi còn lại.
- Người dùng duyệt bảng khác biệt snapshot cộng dồn từ D3 tới nay.
- Kiểm tiêu chí ở mục 3. Ghi report `src/evaluation/reports/eval-YYYY-MM-DD-demo-orchestrator-tong-duyet.md` và entry
  history.

## 3. Tiêu chí nghiệm thu trước demo

Mọi tiêu chí kiểm ở D6, trên staging, LLM thật.

1. K1–K6 bản chính, 3 lần mỗi kịch bản:
   - Không lượt nào lỗi 5xx hay `run.failed`.
   - Mọi lượt kết thúc bằng câu trả lời hoặc câu hỏi giúp người dùng đi tiếp.
2. Không lượt nào của bản chính kết thúc bằng câu dự phòng do `TIME_LIMIT`, `MODEL_TIMEOUT` hoặc `TOOL_LIMIT`. Bản diễn
   đạt khác: ghi số, lượt nào dính thì vào danh sách lỗi.
3. Grounding 100% (NFR-REL-01): mọi `productId`, tên, giá hiển thị đều từ tool của lượt đó; `finalize` và `gatekeep`
   không ghi vi phạm nào.
4. Không lượt nào nói "không có" hay "hết" khi tra cứu thất bại (T1–T4, K7).
5. Ý AC mà các kịch bản chạm tới (FR-AGT-06, FR-AGT-07, AC-AGT-01, 05–08) đều đạt. Ý không đạt thì phải có đề xuất tạm
   bỏ đã chốt; không có ngoại lệ ngầm.
6. Mọi loại thẻ hiện trong kịch bản mở được panel chi tiết. Đổi phương án khách sạn chạy được.
7. K7: câu trả lời nói rõ chưa tra được, gợi ý thử lại, không lộ chữ kỹ thuật.
8. Tiến trình (nếu Phần A đề xuất tiến trình đã chốt): theo tiêu chí ở plan tiến trình, mục 4 "Tiêu chí trước demo".
9. Thời gian: ghi p50 và max theo loại lượt và so với D1. Không đặt ngưỡng cứng; 5 giây của PRD chỉ là gợi ý. Lượt nào
   chậm hơn D1 quá 20% thì ghi nguyên nhân.
10. Test:
    - Snapshot phát lại offline xanh.
    - Unit agents, domain, contract, architecture xanh.
    - Cả bộ backend xanh.
    - Unit frontend và `tsc` xanh.
    - Golden case của D5 đạt pass^3.
11. Luồng cũ đã gỡ: không còn node `classify`, `explore` hay cờ `ITINERARY_ORCHESTRATOR` trong code và tài liệu đang
    dùng (`src/`, `docs/spec/`, `docs/prd/`, `AGENTS.md`, `.env.example`, `docker-compose.yml`).

## 4. Sau demo

Đề xuất gỡ luồng cũ đã chốt và áp dụng ngày 13/10 (`docs/prd/update-archive/2026-10-13-go-luong-cu-sau-demo.md`).
Người dùng chọn gỡ ngay, nên G5, G6 và phần tài liệu của G7 đã làm cùng D3. Phần xoá đi trước phần bổ sung AC (R3 đòi
ngược lại): ca test bị xoá và ý AC của chúng ghi ở mục 1.5, chưa ý nào bị bỏ. G0, G3 bù lại phần này. Số thứ tự G giữ như
bản trước; G1 cũ đã thành D2.

### G0. Kiểm kê đầy đủ và bổ sung test (không sửa hành vi runtime)

Sau khi gỡ (13/10): mục 1 và 2 không cần nữa, vì không còn node cũ hay ký hiệu nào để phân loại. Còn mục 3 và 4, bắt
đầu từ bảng mục 1.5 và report D3.

1. **Đường đi.** Dựng graph với orchestrator bật, liệt kê node và cạnh đến được từ `intake`. Liệt kê mọi giá trị
   `decision` mà `precheck`, `orchestrate`, `extract`, `run_jobs`, `gatekeep`, `evaluate`, `retry` ghi được, và đích của
   từng giá trị. Đánh dấu mọi cạnh dẫn vào `classify`, `explore`, `converse`; đó là danh sách việc của G2. Dùng thêm node
   path thật của D1 và D6.
2. **Ký hiệu.** Bắt đầu từ kiểm kê sơ bộ ở 1.3. Với mỗi ký hiệu, tìm nơi dùng (grep cả `src/`, `src/evaluation/`, test)
   và phân loại:
   - **giữ**: orchestrator hoặc nhánh lập lịch dùng.
   - **chuyển**: dùng chung nhưng nằm trong module cũ.
   - **xoá**: chỉ luồng cũ hoặc test của luồng cũ dùng.

   Ghi kèm test nào import ký hiệu đó, để G5–G6 xử lý test cùng lúc với ký hiệu.
3. **Bảng AC ba trạng thái.** Với từng ý của FR-AGT-06, FR-AGT-07 và AC-AGT-01, 05, 06, 07, 08, ghi một trong ba trạng
   thái:
   - **đạt**: có test hoặc golden case chạy trên orchestrator và đang xanh. Ghi tên.
   - **chưa có test**: chưa có gì kiểm ý này trên orchestrator.
   - **không đạt**: đã có test hoặc golden case, và nó fail. Ghi đầu ra thật.

   Các ý đã kiểm ở D1, D5, D6 dùng lại kết quả đó.

   Với mỗi ý "chưa có test", chọn loại bằng chứng theo nơi quyết định hành vi:
   - **Code quyết** (luật vé, phạm vi job, `gatekeep`, số liệu): unit test với LLM ghi sẵn. Test này đủ làm bằng chứng.
   - **LLM của orchestrator quyết** (hiểu câu, chọn việc, chọn thẻ, hỏi lại): bằng chứng là golden case chạy LLM thật
     theo `golden-run.md`, lặp vài lần. Unit test với LLM ghi sẵn chưa đủ.

   Test của ý "không đạt" mang `@pytest.mark.xfail(strict=True, reason="<mã AC>: <ý> — chưa đạt trên orchestrator, làm ở
   G3")`. Bộ test vẫn xanh, và có danh sách chính xác. G3 làm xong ý nào thì test đó tự đỏ (`strict`), buộc gỡ dấu trong
   cùng thay đổi. Không thêm `xfail` cho test cũ để lách.
4. Ghi kết quả thành mục "Kiểm kê" trong plan này, cùng entry history. Báo người dùng danh sách "không đạt".

Xong khi: mỗi ký hiệu có một nhãn kèm nơi dùng và test liên quan; mỗi ý AC là "đạt" hoặc "không đạt".

### G2. Chuyển các cạnh còn vào node cũ, phanh `plan` lặp (đổi hành vi)

Phần chuyển cạnh xong 13/10. `extract` chưa đồng ý thì đi `gatekeep`, không còn đích `explore`/`converse`. Guardrail
và tin rác vẫn qua `converse`, nay là node câu cố định không gọi LLM. Còn lại: phanh `plan` lặp.

- Với **từng cạnh** G0 đánh dấu, viết test tái hiện trước (fail trên code cũ), rồi chuyển đích:
  - `extract` ra `explore` hoặc `simple` → `orchestrate`, để orchestrator trả lời bằng ngữ cảnh đã có.
  - Guardrail và tin rác: `precheck` dựng sẵn câu trả lời cố định, đi thẳng `finalize`, không qua `converse`. Câu trả lời
    giữ nguyên chữ, chỉ đổi node path.
  - Cạnh khác G0 tìm thấy: ghi cách chuyển vào entry history, có test.
- **Phanh `plan` lặp.** `extract` trả về `orchestrate` mở ra vòng lặp `orchestrate` → `plan` → `extract` →
  `orchestrate`. Code giới hạn mỗi lượt tối đa một lần đi `plan` → `extract`. Lần thứ hai thì buộc orchestrator trả lời
  hoặc hỏi lại (`force_answer`). Test:
  - LLM ghi sẵn luôn trả `plan`: lượt kết thúc bằng câu trả lời hoặc câu hỏi, không chạm ngân sách thời gian, số lần gọi
    model có giới hạn.
  - Lượt hợp lệ đi `plan` một lần không bị ảnh hưởng.

### G3. Hành vi AC còn thiếu (đổi hành vi)

- Với mỗi ý AC "không đạt" của G0: test `xfail(strict=True)` hoặc golden case đang fail là test fail trước. Làm xong thì
  gỡ dấu `xfail` trong cùng thay đổi. Sửa trên orchestrator theo skill:
  - Hiểu câu: prompt và ngữ cảnh của orchestrator.
  - Dữ liệu, phạm vi, số: job, `gatekeep`, `domain/`.
- Cách đúng là dùng lại một luật của luồng cũ (ví dụ thẻ "nơi được hỏi đứng đầu") thì chuyển hàm đó sang chỗ
  orchestrator dùng, và đổi nhãn từ "xoá" thành "chuyển".
- Muốn **tạm bỏ** một ý AC: dừng; tạo đề xuất riêng nêu đúng ý AC, lý do và ảnh hưởng; chờ chốt. Không gỡ code cũ tương
  ứng trước khi chốt.
- Xong khi: mọi ý AC của bảng G0 là "đạt", hoặc có đề xuất tạm bỏ đã chốt.

### G4. Ghi lại baseline

- Ghi lại snapshot sau G2–G3 theo cách của D3: dùng `--fresh`, phát lại offline xanh, bảng tóm tắt theo AC, người dùng
  duyệt.
- Chạy `src/evaluation/tests/test_golden.py` và golden với LLM thật (`docs/spec/agent/golden-run.md`); ghi số.
- Snapshot đã duyệt là baseline cho G5–G6.

### G5. Chuyển luật và helper dùng chung (không đổi hành vi) — xong 13/10, khác plan

Làm cùng việc gỡ luồng cũ. Khác bản dưới:
- Luật trước LLM nằm thẳng trong `precheck_node` (`agents/nodes.py`), không tách `agents/steps/precheck.py`.
- `once_praise`, `checked_suggestions` và phần dùng chung của `exploration.py` ở `agents/steps/replies.py` (đổi tên
  file bằng `git mv`). `unclear_input_reply` giữ ở `conversation.py`, `UNCLEAR_INPUT` ở `messages.py`,
  `vietnam_today` ở `classification.py`.
- Không có baseline G4 để so: kiểm "không đổi hành vi" bằng cách so `precheck` với nhánh `orchestrator_active` tại
  `a50c5e62`, và test của orchestrator.

- Tạo `agents/steps/precheck.py`, chuyển các luật trước LLM đang nằm trong `classify_node(_async)` sang đây, theo đúng
  thứ tự hiện tại: không có tin nhắn → lập lịch; guardrail; tin rác; dừng; chọn phương án; đổi bằng luật; nút vé; đồng ý
  lập lịch có sẵn. `precheck_node(_async)` gọi module này, không gọi `classify_node` nữa.
- Chuyển các helper có nhãn "chuyển" sang module hợp nghĩa. Dự kiến:
  - `vietnam_today` sang `domain/itinerary/dates.py`.
  - `once_praise`, `checked_suggestions`, `unclear_input_reply`, `UNCLEAR_INPUT` sang một module trả lời dùng chung.
- **Test đi cùng ký hiệu, trong cùng bước:**
  - Ca của `test_guardrails.py` gọi `classify_node` chuyển sang gọi `precheck`, kỳ vọng giữ nguyên.
  - Ca của `test_fares.py` gọi qua `explore_node` chuyển sang job vé hoặc gọi `fares.answer` trực tiếp.
  - Test import helper vừa chuyển thì sửa import.
- Kiểm tra: `.venv/bin/python -m pytest --collect-only -q src/backend/tests` không lỗi thu thập; unit agents, domain,
  contract, architecture xanh; snapshot G4 xanh mà không ghi lại.

### G6. Xoá cờ, node cũ và ký hiệu chỉ luồng cũ dùng (không đổi hành vi) — xong 13/10

Danh sách file và test đã xoá: `history/2026-10-13-go-luong-cu-orchestrator-duy-nhat.md`. `classification.py` giữ tên
(còn `extract` và các luật dùng chung).

- `agents/graph.py`: bỏ tham số `orchestrator_enabled`; không đăng ký `classify`, `explore`, `converse`. Bỏ tham số này ở
  `agents/runtime_dependencies.py` và `main.py`. `infrastructure/llm/client.py` bỏ điều kiện
  `settings.itinerary_orchestrator != "on"`, giữ điều kiện về `itinerary_use_llm` và model. `core/config.py`,
  `docker-compose.yml`, `.env.example` bỏ `ITINERARY_ORCHESTRATOR`; giữ `ITINERARY_ORCHESTRATOR_MODEL`, `_PROVIDER`,
  `_REASONING_EFFORT`.
- `agents/routing.py`: bỏ `route_after_classify`, `route_after_explore`; `route_after_precheck` và `route_after_extract`
  chỉ còn đích của orchestrator.
- Xoá các ký hiệu có nhãn "xoá": phần LLM của `classify`, `converse`, `explore`; các hàm của
  `agents/steps/exploration.py` chỉ node `explore` dùng; `TurnRoute`, `ExploreNarration`; `CLASSIFY_PROMPT`,
  `EXPLORE_PROMPT` (và `CONVERSATION_PROMPT` nếu G0 thấy không ai dùng); regex chỉ các hàm bị xoá dùng; log cảnh báo
  và comment đóng băng của D0.
- **Trong cùng bước, xoá hoặc sửa test của chúng** theo danh sách G0:
  - Test chỉ kiểm hành vi của luồng cũ: xoá.
  - Test kiểm một ý AC: đã có bản trên orchestrator từ D5, G0 hoặc G3; xoá bản cũ.
- Module rỗng thì xoá file. Module còn phần dùng chung thì giữ tên nếu nghĩa vẫn đúng. Tên sai nghĩa (ví dụ
  `classification.py` chỉ còn `extract`) thì đổi tên và sửa import trong cùng bước.
- Kiểm tra:
  - Grep: không còn tham chiếu nào tới ký hiệu đã xoá trong `src/`.
  - `.venv/bin/python -c "import src.backend.app.main"` chạy được.
  - `.venv/bin/python -m pytest --collect-only -q src/backend/tests src/evaluation/tests` không lỗi thu thập.
  - Cả bộ backend xanh; snapshot G4 xanh mà không ghi lại.

### G7. Tổng kiểm độ phủ AC, tài liệu, công cụ đánh giá, golden

Phần tài liệu, skill, `src/evaluation/` (tên node trong golden) đã làm 13/10. Còn: bảng AC sau G3, golden với LLM thật,
dòng trạng thái trong `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`.

- Chạy lại bảng AC của G0 trên code sau G6: mọi ý phải "đạt". Ý nào không đạt thì báo người dùng.
- PRD: đã sửa khi áp dụng đề xuất gỡ luồng cũ. Không sửa thêm.
- Spec: bỏ mô tả luồng cũ và cờ ở `docs/spec/agent/` (`langgraph-nodes.md`, `working-context.md`, `state-fields.md`,
  `response-and-errors.md`, `README.md`, `golden-run.md`, `golden-dataset-how-to-add-more-case.md`, `nghiep-vu/*`) và
  `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`. Bỏ ghi chú đóng băng ở `AGENTS.md` §3 và `working-context.md`, vì
  không còn gì để đóng băng. Ghi cách ghi và phát lại snapshot mới vào `working-context.md` §5A.
- Skill `building-itinerary-agent`: bảng "Chọn lớp" trỏ tới `orchestration.py`, `precheck.py`, `jobs.py` thay cho
  `classification.py`, `conversation.py`.
- `src/evaluation/`: bỏ tên node cũ trong `test_golden.py` và kỳ vọng golden.
- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`: thêm dòng trạng thái "B12 thay bằng plan gỡ luồng cũ".
- Chạy golden với LLM thật; báo theo tầng bằng chứng (`working-context.md` §5C). Entry history cuối gồm danh sách file
  đã xoá, đã chuyển và số thật của mọi lệnh.

## 5. Invariant

### Bổ sung ngày 13/10 — phạm vi khám phá và số lượng theo yêu cầu

- Sửa lỗi `more` lấy thành phố của thẻ cuối khi lượt trước tìm nhiều thành phố. Điều kiện kế thừa phải chung
  giữa các thẻ; `via.destination=null` vẫn là tìm toàn catalog. Orchestrator thay phạm vi bằng
  `scope_mode=replace`, loại nơi trong việc bằng `excluded_destinations`, không regex đoán ý.
- Người dùng đã chốt `update-archive/2026-10-13-so-luong-goi-y-theo-yeu-cau.md`: mức 3/2/4 là mặc định
  khi chưa nêu số lượng, tổng tối đa 20 thẻ/lượt. Số lượng trích có cấu trúc; continuation không nhân chỉ tiêu,
  phanh 3 vòng/10 tool vẫn giữ; thiếu dữ liệu hoặc budget phải nói số thực trả được và lý do.
- Unit graph kiểm đủ 10, thiếu dữ liệu, hết vòng, lỗi trang tiếp; gác cổng kiểm lại phạm vi, thẻ chưa liệt kê,
  thẻ đã xem và trần 20. Contract 1.28.0 tách schema khám phá khỏi giới hạn kết quả đi kèm lịch đã xếp.
- Bản ghi D3 dùng prompt cũ: hai test snapshot không khớp sau đổi prompt. Cần ghi lại bằng `record`, đọc diff
  và duyệt theo D6/G4; chưa thay bản ghi cũ hoặc dùng thay đổi này làm chứng cứ D4/D5 khác đã xong.
- Chi tiết kiểm tra và phần chờ model thật: `history/2026-10-13-sua-ke-thua-pham-vi-kham-pha.md`.

- Grounding không đổi: thẻ, giá, vé chỉ từ tool của lượt đó; `gatekeep` vẫn kiểm trước `finalize`; mọi nhánh qua
  `finalize`.
- Tra cứu thất bại không bao giờ được trình bày như không có dữ liệu.
- Luật trước LLM (NFR-SEC-04) giữ nguyên thứ tự và kết quả. Guardrail không gọi LLM nào, và câu trả lời cố định giữ
  nguyên chữ.
- Giới hạn tool, vòng, thời gian chỉ đổi khi có số đếm của kịch bản hợp lệ và người dùng đồng ý.
- Snapshot phát lại offline được và không phụ thuộc tốc độ mạng hay model. Trần vòng và trần tool được giữ và kiểm trong
  snapshot; hết giờ và quá giờ thì không.
- Không bỏ ý AC nào nếu không có đề xuất tạm bỏ đã chốt. Không dùng dữ liệu dựng sẵn để che lỗi.
- Không tạo lại luồng cũ hay cờ `ITINERARY_ORCHESTRATOR`.
- Sau demo: mỗi lượt đi `plan` → `extract` tối đa một lần.
- Sau mỗi bước, toàn bộ test thu thập được.

## 6. Quyết định, câu chờ chốt và rủi ro

**Người dùng đã nói trực tiếp:** xem đầu plan. Đã chốt ngày 13/10: orchestrator mặc định; R1, R2, R3.

**Chờ người dùng:**
- Duyệt baseline snapshot D3 (R2).
- Chốt đề xuất tiến trình: Phần A (trước B2–B8 của plan tiến trình), Phần B, Phần C (số đo D1 đã đạt tiêu chí).

**Rủi ro.**
- Mỗi lượt orchestrator mất 7–39 giây trong lần chạy thử (1.3), nên sếp sẽ chờ lâu. Biện pháp:
  - Tiến trình có kết quả thật (plan tiến trình) để người xem thấy trợ lý đang làm gì.
  - T4 bỏ lời gọi tuần tự và lặp lại.
  - Không tăng timeout để giấu chậm.
- D1 có thể tìm ra nhiều lỗi hơn thời gian cho phép trước demo. Biện pháp: mức độ "chặn demo", "xấu", "nhỏ"; chỉ hai mức
  đầu phải xong trước demo. Báo người dùng danh sách ngay sau D1 để cùng chọn.
- Model không tất định, nên kịch bản đạt hôm nay có thể hỏng lúc demo. Biện pháp: 3 lần chạy và bản diễn đạt khác ở D1,
  D6; golden case pass^3 cho mỗi lỗi đã sửa.
- Triển khai lên staging làm đổi hành vi cho mọi người đang dùng staging, và không còn cờ để quay về. Biện pháp: người
  dùng đã chốt; báo nhóm trước khi triển khai; sự cố thì triển khai lại bản trước (`a50c5e62`).
- Gỡ luồng cũ trước khi bổ sung đủ AC trên orchestrator (ngược R3). Biện pháp: mục 1.5 ghi từng ca đã xoá và ý AC của
  nó; D3 cho thấy các ý AC kém hơn; D5 và G3 làm lại trên orchestrator. Không ý AC nào bị bỏ.
- Sửa T1–T4 đổi số lời gọi tool, nên snapshot lệch. Biện pháp: chỉ ghi lại hội thoại dự kiến; liệt kê trong history;
  người dùng duyệt ở D6.
- Ghi snapshot bằng LLM thật vẫn có thể khác nhau giữa các lần ghi. Đồng hồ ảo chỉ bỏ được phần phụ thuộc thời gian.
  Biện pháp: bảng tóm tắt đánh giá theo AC, không theo câu chữ.
