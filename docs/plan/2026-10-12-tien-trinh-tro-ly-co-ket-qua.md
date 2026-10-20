# Tiến trình của trợ lý hiện kết quả từng bước

- Ngày: 2026-10-12
- Người yêu cầu / phân tích: Nguyễn Minh Nhật / Claude Code.
- Phục vụ: FR-AGT-01, FR-AGT-02, FR-AGT-03, FR-AGT-06, FR-AGT-07, NFR-PERF-02, NFR-REL-01, NFR-SEC-01
  (`docs/prd/requirements.md`). AC mới đề xuất: AC-AGT-09.
- Trạng thái: plan đã sửa theo review lần 1 (`history/2026-10-12-sua-plan-tien-trinh-theo-review.md`), lần 2
  (`history/2026-10-12-sua-plan-theo-review-2.md`), lần 3 (`history/2026-10-12-sua-plan-theo-review-3.md`), và theo
  hướng ưu tiên demo (`history/2026-10-12-plan-uu-tien-demo.md`) ngày 12/10. Người dùng chốt orchestrator mặc định và
  Q1–Q6 ngày 13/10 (`history/2026-10-13-chot-orchestrator-mac-dinh.md`). Phần A/C đã triển khai ngày 13/10; xem mục tiến độ cập nhật.
- **Ưu tiên (người dùng, 12/10):** demo thật tốt cho sếp, chưa tối ưu production. Tiến trình phải phản ánh việc thật và
  số liệu thật. Plan chia hai phần: **trước demo** và **sau demo** (mục 0).
- **Phạm vi: chỉ luồng orchestrator.** Người dùng chọn hướng trong tin nhắn ngày 12/10: orchestrator là luồng chính.
  Ngày 13/10 người dùng chốt gỡ hẳn luồng cũ (`classify` bằng LLM, node `explore` cũ, `converse` bằng LLM) và cờ
  `ITINERARY_ORCHESTRATOR`; đã gỡ cùng ngày. Plan chung là
  [2026-10-12-go-luong-cu-orchestrator-chinh.md](2026-10-12-go-luong-cu-orchestrator-chinh.md).
  - Plan này cần baseline kiểm thử ổn định trên orchestrator: snapshot D3 của plan chung, đã ghi ngày 13/10, chờ người
    dùng duyệt.
  - Không còn luồng cũ để thêm tiến trình hay quay về.
- Lệch PRD: **có**. Cần chốt:
  - `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md`, chia ba phần:
    - Phần A, trước demo: khung tiến trình, dòng tóm tắt, chẩn đoán mức 1 trong `DebugPanel`. `DebugPanel` là chức năng
      UI mới, PRD chưa có căn cứ để làm.
    - Phần B, sau demo: chẩn đoán mức 2.
    - Phần C, kết quả từng phần: chỉ xin chốt nếu số đo D1 đạt tiêu chí ở 3.5.
  - Đề xuất orchestrator là mặc định: **đã chốt** ngày 13/10/2026 và đã áp dụng
    (`docs/prd/update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`).

  Phần A/C đã chốt ngày 13/10/2026; trạng thái chi tiết ở mục tiến độ cập nhật. Số đo thời gian (trước đây là B0) đã gộp vào D1 của plan chung.
- **Người dùng chỉ đạo trực tiếp (12/10):** preview sau `compose` chỉ giữ nếu đo thấy có ích. Tiêu chí đo ở 3.5 do plan
  đặt ra, chờ người dùng xác nhận.
- **Phương án reviewer đề xuất, người dùng chấp nhận ngày 13/10** (mục 8):
  - Không tự đặt ngân sách khi người dùng chưa nêu (Q2).
  - Bước xếp lịch chỉ nêu tiêu chí thật (Q3).
  - Chưa làm kết quả từng phần cho lượt khám phá (Q6).
  - Dòng tóm tắt trên lời diễn giải và các thẻ (Q1); chẩn đoán mức 2 theo khoá và danh sách cho phép (Q5).

Đường dẫn backend tương đối với `src/backend/app/`, frontend tương đối với `src/frontend/src/`, trừ khi ghi đầy đủ.

## Tiến độ cập nhật 13/10/2026

Người dùng xác định lại trọng tâm: gỡ code cũ và hoàn thiện UI tiến trình; chốt “Chốt cả A và C, thêm thẻ xem trước”. Phần A/C đã áp dụng PRD; Phần B còn chờ, đề xuất giữ trong `update/`. Entry: `history/2026-10-13-hoan-thien-ui-tien-trinh-agent.md`.

- B1, B3: đã cập nhật PRD, contract 1.27.0, kiểu sinh tự động, 8 fixture stream và kiểm hợp đồng.
- B2, B7, B8: đã triển khai mô hình cập nhật theo nhóm/thông báo, khung theo loại lượt, dòng tóm tắt và chẩn đoán mức 1. Thẻ preview chỉ xem, đợi mốc 5 giây, gỡ khi kết thúc/dừng/lỗi.
- B4, B5, B6: đã nối activity và bộ đếm tại nơi lọc; preview chỉ sau compose đã kiểm nguồn. Collector tách khỏi graph state, request độc lập. Không sửa hành vi T1–T4 hoặc prompt D5; D4 vẫn là việc riêng. Theo trọng tâm mới của người dùng, instrument bộ lọc hiện có trước D4; D4 sau này phải giữ hoặc cập nhật bộ đếm cùng test.
- Không ước lượng khi không đếm được đúng phạm vi: câu vé kèm ngày/khung giờ mà thẻ bao gồm ngày/giờ lân cận bỏ số; job không khai taxonomy và trả nhiều loại không gán giả một loại.
- B10 local: contract, snapshot offline, unit/contract/architecture, build và trình duyệt được kiểm; số và caveat trong history. B10a trên staging với LLM thật/trace cùng request chưa chạy; không coi fixture là bằng chứng staging hoặc SLA.
- B9 chưa làm vì Phần B chưa chốt. Baseline D3 giữ nguyên; không ghi lại snapshot hoặc coi các lỗi D1/D3 đã đạt AC.

## 0. Đọc trước khi làm

**Thứ tự.** Thứ tự chung của cả hai plan nằm ở mục 0 của plan chung. Phần của plan này:

Trước demo:

| # | Bước | Chờ gì? |
|---|---|---|
| 1 | B1 người dùng chốt Phần A đề xuất tiến trình; áp dụng vào PRD (đề xuất orchestrator mặc định đã chốt 13/10) | Chính là bước chốt |
| 2 | B3 contract 1.27.0 (chưa có `run.preview` nếu Phần C chưa chốt) | B1; D3 của plan chung (baseline) |
| 3 | B7 mô hình và hiển thị tiến trình → B8 thu gọn thành dòng tóm tắt (frontend) | B3. Song song D4, D5 được |
| 4 | B4 dữ kiện và số đếm tại chỗ lọc → B5 việc con đang chạy (backend) | B3 và **D4 xong** |
| 5 | B2 chẩn đoán mức 1 trong `DebugPanel` | B3 |
| 6 | B6 kết quả từng phần (backend) và phần preview của B8 (frontend) | Số đo D1 đạt tiêu chí ở 3.5 **và** người dùng chốt Phần C. Không đạt thì bỏ khỏi trước demo |
| 7 | B10a kiểm tiến trình trên backend thật (gộp vào D6 của plan chung) | Tất cả |

Sau demo: B9 chẩn đoán mức 2 (Phần B); B10b tài liệu còn lại; kết quả từng phần cho lượt khám phá (Q6); B6 nếu trước demo
không làm mà người dùng vẫn muốn.

Vì sao B4 chờ D4: D4 sửa bộ lọc trong `jobs.py` (`_page`, `_explore`, `_one`, `execute`) và luồng tra vé trong
`fares.py`. B4 thêm bộ đếm vào đúng các chỗ đó. Làm B4 trước thì phải đếm lại sau D4.

Sau B3, frontend (B7, B8) chạy song song với D4, D5 của plan chung. Contract là ranh giới, và fixture stream của B3 là
dữ liệu chung.

**Quy tắc làm việc** (AGENTS.md và memory người dùng):
- Đầu phiên đọc theo AGENTS.md §1: các hàng "API", "Backend", "Frontend", "Itinerary Agent". Ghi xác nhận §1.3 trước lần
  sửa code đầu. Mỗi bước có entry `history/` riêng.
- Không commit khi chưa được yêu cầu. Commit đứng tên người dùng, **không** thêm `Co-Authored-By`.
- Lúc code chỉ chạy test nhanh. Cả bộ backend để cuối: `WEAVIATE_URL` trỏ cổng đóng, `SEARCH_PREWARM=false`, khoảng 25
  giây. Chạy backend với `HF_HUB_OFFLINE=1` (embedding e5 local; thiếu biến này thì treo do IPv6).
- Đụng API của Next.js thì đọc `src/frontend/node_modules/next/dist/docs/` trước (`src/frontend/AGENTS.md`).
- Task này không có việc "hiểu câu" mới. Mọi dữ kiện tiến trình là code đọc state hoặc đếm tại chỗ xử lý kết quả, nên
  không có prompt mới và không có regex mới.
- **Lưới chống đổi hành vi.** Từ D3 của plan chung, snapshot hành vi chạy bằng orchestrator, có đồng hồ ảo và phát lại
  offline được (`tests/unit/agents/test_behavior_snapshot.py`).
  - D4, D5 đổi hành vi có chủ ý và ghi lại phần snapshot lệch.
  - Mỗi bước của plan này so với snapshot đang có trên nhánh lúc làm bước đó.

  Snapshot cùng `test_orchestrator_jobs.py`,
  `test_orchestrator_runtime.py`, `test_shown.py` và `tests/unit/domain/test_orchestrator_gatekeeper.py` phải xanh mà
  không ghi lại snapshot. Tiến trình không được đổi `message`, node path, response, state lưu, payload LLM hay tham số
  tool. B4 tách bộ lọc thành hàm có tên để đếm; snapshot là bằng chứng việc tách không đổi kết quả. Snapshot lệch thì
  dừng lại và xem lại, không ghi lại snapshot.

## 1. Bối cảnh và bằng chứng

Đọc code tại commit `a50c5e62` (12/10). Review cùng ngày đã xác nhận ý 2.

1. Web vẽ 3 bước cố định (`features/itinerary/widget/widgetProgressView.ts`): Hiểu yêu cầu → Tìm sản phẩm phù hợp →
   Sắp xếp lịch trình. Bước chỉ đi tiếp theo bảng `AFTER_NODE`, gồm `extract`, `tool`, `retry`, `evaluate`, `compose`.
2. Các node của orchestrator (`precheck`, `orchestrate`, `run_jobs`, `gatekeep`) không có trong bảng. Vì vậy lượt khám
   phá, hỏi vé và trò chuyện đứng ở "Đang hiểu yêu cầu của bạn…" cho tới khi có câu trả lời, đúng như ảnh người dùng gửi.
   Một lượt khám phá còn có thể chạy nhiều vòng `orchestrate` → `run_jobs`.
3. Đường đi của một lượt khi orchestrator bật (`agents/graph.py`, `agents/routing.py`, `precheck_node_async`):
   - `intake` → `precheck`, gồm các luật chạy trước LLM:
     - guardrail hoặc tin rác → `converse` (bỏ qua LLM) → `finalize`.
     - nút vé → `orchestration.fare_button_turn` → `run_jobs`.
     - "không đi nữa" → `orchestrate` với `turn_stop`.
     - chọn phương án, `intentOverride` không có tin nhắn, hoặc xin lập lịch khi đã đồng ý → `extract`.
     - còn lại → `orchestrate`.
   - `orchestrate` ra một trong bốn hành động: `answer` hoặc `ask` → `gatekeep`; `execute` → `run_jobs`; `plan` →
     `extract`.
   - `run_jobs` → `orchestrate`, `gatekeep`, hoặc `run_jobs` lần nữa. `gatekeep` → `finalize`, hoặc `orchestrate` để
     sửa câu.
   - Nhánh lập lịch: `extract` → `clarify` | `tool` → `evaluate` → (`retry`) → `filter` → `compose` → `narrate` →
     `finalize`.
   - Hỏi vé đi job `fare`: `jobs._fare` gọi `fares.answer()`.
4. SSE chỉ phát `node.completed` sau khi một node xong (`api/v1/routes/assistant.py`; `agents/runtime_dependencies.py`
   dùng `stream_mode="values"`). Bên trong một node không có tín hiệu nào. Có hai node làm nhiều việc liền nhau:
   - `tool`: lập tool plan bằng LLM, gọi Search/Recommendation, tra vé, lấy chi tiết giá và lịch trống.
   - `run_jobs`: chạy song song tối đa 3 job, mỗi job có thể lấy nhiều trang.

   Suốt thời gian đó Web không biết node đang làm gì.
5. `node.completed` chỉ mang `sequence, nodeId, outcome, message, durationMs`. Route bỏ các số liệu đã có trong
   `event(..., **metadata)` (`calls`, `verified`, `jobs`, `rounds`, `issues`). `message` là chuỗi debug tiếng Anh, và
   Web không hiện nó (hợp đồng frontend §6).
6. `tests/contract/test_assistant_contract.py::test_stream_never_leaks_prompt_state_or_credentials` khoá đúng 5 khoá trên.
   Thêm khoá thì phải sửa test này có chủ ý, cùng lúc với contract.
7. **Số đếm không có sẵn ở nơi tưởng là có.** Không được suy ngược số đếm từ danh sách cuối.
   - `agents/steps/jobs.py::_page`: `total` của Search chỉ dùng để tính `source_more`, rồi bị bỏ. `total` là tổng của câu
     tìm trên cả điểm đến, chưa áp các bộ lọc tiếp theo của job: còn phòng, gần mốc, rẻ hay đắt hơn, đã xem, trùng nơi.
     Vì vậy không dùng `total` cho câu như "khách sạn gần Hồ Gươm".
   - `row["excluded"]` là danh sách mọi thẻ đã xem trong hội thoại, không phải số kết quả thật sự bị loại ở lần tìm này.
   - Nhánh lập lịch: `retrieval.collect` biết lý do loại của từng sản phẩm (`dropped`), nhưng
     `evaluation._preferred_stays` bỏ khách sạn không hợp sở thích mà không ghi lại bỏ bao nhiêu.
8. Job được đánh số theo thứ tự trong lượt. Job "lấy tiếp" (`continue_from`) có số mới nhưng `source_job` trỏ về job gốc,
   và `execute` cập nhật `cursor`, `offset`, `products` của job gốc. Job trùng chữ ký bị bỏ. Job vé có thể bị thay
   (`replaces`; job cũ thành `status = superseded`).
9. Thẻ của lượt khám phá do LLM của orchestrator chọn trong kết quả job, và `gatekeep` kiểm (AC-AGT-06).
10. Tiến trình bị reset mỗi lượt và không gắn vào tin nhắn trong transcript, nên khi xong không còn gì để thu gọn. Web
    cũng không lưu `runId`/`requestId` của `run.started`.
11. Latency thật (`src/evaluation/reports/eval-2026-10-10-agent-test-cases.md`, đo trên luồng cũ): p50 5.323 ms, p95
    26.080 ms.
    - Lần chạy thử orchestrator ngày 12/10 (plan chung mục 1.3; một lần, trong tiến trình, LLM thật): lượt chỉ trả lời
      7–14 giây, lượt có job 17–39 giây.
    - Trong lúc đó khung hiện tại đứng ở bước đầu, nên tiến trình là thứ người xem thấy rõ nhất khi demo.
    - Số theo từng node do D1 của plan chung đo.
12. LangGraph 1.2.11 phát được dữ liệu từ bên trong node bằng `get_stream_writer()` với
    `stream_mode=["values", "custom"]`. Đã thử bằng script ở scratchpad ngày 12/10:
    - Node sync và node async đều phát được.
    - `ainvoke` vẫn chạy bình thường; khi đó writer không làm gì.
    - Gọi writer ngoài graph thì ném `RuntimeError`, nên helper phải nuốt lỗi này.
13. Chỉ route stream gọi `ItineraryPlanner.astream`. BFF (`services/server/proxy.ts`) chuyển mọi header lên backend, trừ
    `STRIPPED_REQUEST_HEADERS`.

## 2. Yêu cầu và cách hiểu

| # | Người dùng yêu cầu | Plan hiểu thành | Giới hạn: chỉ nói điều agent thật sự làm |
|---|---|---|---|
| 1 | Bước hiểu yêu cầu nhắc lại những gì agent đã hiểu | Một dòng dữ kiện lấy từ `intent` hoặc từ job. Phần agent tự quyết đánh dấu riêng | Thiếu ngân sách thì hiện "Ngân sách: chưa nêu → không giới hạn theo giá". Không tự đặt mức trung bình (Q2, người dùng chốt 13/10) |
| 2 | Tìm kiếm tách theo loại, có số lượng | Mỗi nhóm tìm kiếm một dòng: "tìm thấy N, chọn K", kèm số bị loại theo lý do | Định nghĩa số đếm ở 3.3. Số được đếm ngay tại chỗ lọc |
| 3 | Việc con đang chạy ("Đang kiểm tra giá phòng ngày 17/10…") | Thêm sự kiện mới phát từ bên trong node | Chỉ phát ở những điểm code thật sự làm việc đó (3.4) |
| 4 | Sắp xếp lịch nêu tiêu chí chính | Các tiêu chí `compose` đã áp dụng | Không ghi "buổi chiều nghỉ ngơi", vì `compose` không dùng `pace` (Q3, người dùng chốt 13/10) |
| 5 | Lỗi và ngoại lệ nói thẳng | Dòng ⚠ theo lý do loại, không tra vé, thử lại, hết kết quả | Gộp theo lý do; không liệt kê từng mã sản phẩm |
| 6 | Không hiện tên tool, API, query thô, JSON | Backend gửi mã, số và tên lấy từ catalog hoặc intent; Web tự viết câu | `query` tự do không hiện cho người dùng, và không có trong chẩn đoán |
| 7 | Đang chạy: spinner, ✓ kèm kết quả, bước chưa tới để mờ | Giữ cách hiện tại | Bước chưa chắc sẽ chạy thì **không** hiện mờ trước (3.2) |
| 8 | Xong thì thu gọn thành 1 dòng | Một dòng tóm tắt ở đầu câu trả lời, bấm để mở lại các bước | Câu của người dùng bị cắt (Q1) |
| 9 | Chạy quá khoảng 5 giây thì hiện kết quả từng phần | Thẻ các sản phẩm của lịch đã xếp xong, hiện trước khi có lời tư vấn | Chỉ làm nếu số đo D1 cho thấy có ích (3.5; người dùng chỉ đạo 12/10). Chỉ nhánh lập lịch (Q6, người dùng chốt 13/10) |
| 10 | Nhà phát triển cần biết chi tiết agent đang làm gì | Hai mức chẩn đoán (3.8) | Mức 1 trước demo. Mức 2 sau demo, chỉ gửi cho request có khoá và chỉ gửi trường có trong danh sách cho phép |

## 3. Thiết kế

### 3.1. Nguyên tắc

- Dữ kiện tiến trình do code tính từ state, hoặc đếm ngay tại chỗ lọc kết quả. LLM không viết chữ nào trong tiến trình.
- Backend gửi dữ liệu có cấu trúc: mã, số, ngày ISO, tên lấy từ catalog. Web sở hữu câu chữ, giống nhãn hiện nay.
- Module thuần `agents/steps/progress.py` gom số đếm và dựng `progress`; wrapper `timed()` trong `agents/graph.py` gọi
  nó sau mỗi node. Code xử lý kết quả chỉ được thêm một **bộ đếm tuỳ chọn** (mặc định không làm gì) và tách điều kiện lọc
  thành hàm có tên. Không đổi kết quả lọc.
- Số đếm nằm trong khoá state mới `progress_counts`. Khoá này không vào `working_state` mà `finalize` lưu (danh sách cho
  phép ở `agents/nodes.py`), và không vào payload LLM. `_brief` của job chỉ chọn trường cố định nên không mang số đếm.
- Không có ✓ giả. Một bước chỉ được ✓ khi node tương ứng đã xong thật. Bước chưa chắc sẽ chạy thì không hiện.
- Không đổi response cuối, `message`, node path hay state lưu. JSON route (`POST /assistant/itineraries`) không đổi.

### 3.2. Các bước theo loại lượt

Code xác định loại lượt (`turnKind`) từ các trường đã có trong state, rồi gửi kèm danh sách bước.

| `turnKind` | Nhận diện theo | Bước |
|---|---|---|
| `fare` | `precheck` ra nút vé (`fare_button_turn`); hoặc `orchestrate` ra `execute` mà mọi job là `fare` | understand → search (vé) |
| `explore` | `orchestrate` ra `execute` có ít nhất một job `explore`. Job vé đi kèm thành một nhóm trong bước search | understand → search → write |
| `plan` | `precheck` ra `travel` (chọn phương án, `intentOverride`, xin lập lịch khi đã đồng ý) hoặc đổi chuyến bay bằng luật; `orchestrate` ra `plan`; sau đó `extract` ra `tool` | understand → search → arrange → write |
| `clarify` | `extract` ra `missing_info` | understand, kèm dòng "Còn thiếu: …" |
| `converse` | `orchestrate` ra `answer` hoặc `ask` mà không chạy job nào; "không đi nữa" (`turn_stop`) | understand |
| `blocked` | guardrail hoặc tin rác ở `precheck`; `dead_letter` | Không ✓ bước nào; câu trả lời hoặc lỗi hiện như hiện nay |

Quy tắc:
- Trước khi biết loại lượt, chỉ có một dòng "Đang hiểu yêu cầu của bạn…" kèm spinner, không có bước mờ nào. Biết loại
  lượt rồi thì các bước sau mới hiện mờ.
- Loại lượt có thể đổi giữa chừng. Ví dụ `orchestrate` vòng 1 ra `execute` (khám phá), vòng 2 ra `plan`; hoặc `extract`
  thấy chưa đồng ý lập lịch nên đi `gatekeep`. Khi đó Web dựng lại danh sách bước mờ, nhưng không bao giờ xoá một dòng
  đã ✓.
- Lượt `execute` nhiều vòng: mỗi vòng thêm hoặc cập nhật nhóm ở bước search theo `groupId` (3.3), không quay lại bước 1.
- `gatekeep` trả về `orchestrate` để sửa câu: không thêm bước, chỉ đổi dòng đang chạy (3.4).
- `retry`: bước search chạy lại, kèm dòng ⚠ "Tìm kiếm chưa phản hồi, đang thử lại".
- `apply_option` (chọn phương án khách sạn qua nút) đi qua JSON route, không qua stream, nên không có tiến trình.
- B4 phải liệt kê đủ mọi giá trị `decision` mà `precheck`, `orchestrate`, `extract`, `run_jobs`, `gatekeep` có thể ghi
  (theo `agents/routing.py` sau khi gỡ luồng cũ) và có test cho từng giá trị. Giá trị không xếp được vào bảng thì coi là
  `converse`.

### 3.3. Dữ kiện của từng bước

**understand.** Lượt `plan` và `clarify` lấy dữ kiện từ `intent` sau `extract`. Lượt `explore` và `fare` lấy từ `Job`
(`spec`) và `FareQuestion` của job.

| Dữ kiện | Nguồn | Web hiện (ví dụ) |
|---|---|---|
| Điểm đến, ngày đi, số ngày, đoàn, nơi đi, ngân sách, sở thích (tối đa 3, phần còn lại "+n"), nhịp đi | `intent` | "Đà Nẵng · 17/10 · 3 ngày · 2 người lớn · từ Hà Nội · thích biển, hải sản · nhịp thư thả" |
| Còn thiếu | `missing_fields` | "Còn thiếu: ngày đi, số người" |
| Việc khám phá | `Job`: `taxonomy`, `destination`, `near`, `sort`, `intent` | "Khách sạn ở Hà Nội · gần Hồ Gươm · giá thấp trước"; "Thêm điểm tham quan ở Đà Nẵng"; "Xem lại 2 thẻ bạn hỏi" |
| Việc hỏi vé | `FareQuestion` của job | "Vé TP. Hồ Chí Minh → Hà Nội · 20/10 · rẻ nhất" |

`Job.query` và mọi chuỗi tự do do LLM điền đều không hiện ở đâu.

**Điều agent tự quyết** (`assumptions`). Mỗi mã chỉ phát khi đúng điều kiện ghi ở cột hai.

| Mã | Điều kiện (nguồn) | Web hiện |
|---|---|---|
| `NO_BUDGET` | `turnKind = plan` và `intent.budget` là null | "Ngân sách: chưa nêu → không giới hạn theo giá" |
| `NO_ORIGIN` | `flights.skip_reason` = `NO_ORIGIN` | "Nơi đi: chưa nêu → chưa tìm vé máy bay" |
| `DAY_TRIP` | `skip_reason` = `DAY_TRIP` | "Đi trong ngày → không kèm vé máy bay" |
| `FLIGHT_EXCLUDED` | `skip_reason` = `EXCLUDED` | "Không cần vé máy bay → không tìm vé" |
| `SAME_CITY` | `skip_reason` = `SAME_CITY` | "Nơi đi trùng điểm đến → không cần vé" |
| `NAME_MATCHED` | `tool` ghi `changed` có `destination` hoặc `origin`; giá trị cũ lấy từ state trước node, giá trị mới từ update | "“Sài Gòn” → TP. Hồ Chí Minh" |
| `KIDS_COUNT_UNKNOWN` | `normalize_party` đặt `party_type_hint = FAMILY_WITH_KIDS` | "Gia đình có trẻ nhỏ: chưa rõ số trẻ" |
| `ROOM_MIN_GUESTS` | `ceil(tổng khách / 9) > 1` (FR-AGT-01) | "Đoàn 12 người → tìm phòng từ 2 khách để đủ tối đa 9 phòng" |

`KIDS_COUNT_UNKNOWN` chỉ nêu điều đã biết, không tự nói agent tính số người thế nào.

**search: nhóm tìm kiếm và số đếm.**

Mỗi dòng ở bước search là một **nhóm tìm kiếm**. `groupId` ổn định trong cả lượt:

| Đường | `groupId` | Phạm vi của nhóm |
|---|---|---|
| Lập lịch | `plan:<taxonomy>` | Loại sản phẩm, điểm đến |
| Lập lịch, vé | `plan:flight` | Nơi đi, nơi đến, ngày đi, ngày về |
| Job khám phá | `job:<số job gốc>` (`source_job` nếu có, nếu không thì `job`) | Đúng `spec` của job: loại, điểm đến, gần đâu, sắp xếp, ý định |
| Job vé | `job:<số job>` | Tuyến, ngày, khung giờ của `FareQuestion` |

Như vậy hai job cùng loại, cùng điểm đến nhưng khác điều kiện là hai nhóm khác nhau. Job "lấy tiếp" ở vòng sau cập nhật
đúng nhóm gốc.

Số đếm của một nhóm (`counts`). Mỗi sản phẩm nhận về rơi vào **đúng một** ô, theo điều kiện đầu tiên nó không đạt trong
thứ tự cố định: ngoài phạm vi → hết chỗ → đã xem → trùng nơi → hợp lệ.

| Số | Định nghĩa | Ai thấy |
|---|---|---|
| `sourceTotal` | Tổng nguồn báo (`total` của Search hoặc listing) của trang cuối đã lấy. Không áp bộ lọc của nhóm | Chỉ chẩn đoán |
| `received` | Số `productId` khác nhau thực sự nhận về trong các trang đã lấy | Chỉ chẩn đoán |
| `outOfScope` | `{lý do: số}`: sai điểm đến, sai loại, là vé, ngoài tập của câu tìm (`query_ids`), xa mốc, không rẻ hơn hoặc không đắt hơn mốc, người dùng loại trừ, và `NOT_SUPPLY_REASONS` ở nhánh lập lịch | Chỉ chẩn đoán |
| `inScope` | `received` trừ tổng `outOfScope` | Người dùng: "tìm thấy" |
| `dropped` | `{lý do: số}` sản phẩm đúng phạm vi nhưng bị loại ở **lần tìm này**: hết chỗ hoặc không bán ngày đó (`PRODUCT_DROPPED_DATE`, `PRODUCT_DROPPED_UNAVAILABLE`, khách sạn `available` khác true), giá, tiện ích, yêu cầu theo tên, đã xem (`SEEN`, chỉ đếm sản phẩm có trong trang và bị bỏ), trùng nơi (`DUPLICATE`), không hợp sở thích khách sạn (`PREFERENCE`) | Người dùng: dòng ⚠ |
| `eligible` | Số còn lại sau mọi lọc | Chỉ chẩn đoán (kiểm tổng) |
| `chosen` | Số phần tử của **giao** giữa `productId` của nhóm và `productId` có trong response cuối | Người dùng: "chọn" hoặc "giới thiệu" |
| `sourceMore` | Nguồn còn trang chưa lấy | Web ghi "tìm thấy 12+" |

Bất biến kiểm trong test: `received = inScope + Σ outOfScope`; `inScope = eligible + Σ dropped`; `chosen ≤ eligible`.

Nơi đếm. Mọi chỗ đều đếm **ngay tại chỗ lọc**, bằng cùng hàm điều kiện mà bộ lọc dùng:

| Đường | Nơi đếm | Cách |
|---|---|---|
| Lập lịch | `application/itinerary/retrieval.py::collect` (đã có `dropped` theo từng sản phẩm); `agents/steps/evaluation.py::_preferred_stays`; `filter` (`dropped_duplicates`) | `collect` nhận thêm tham số `counts` tuỳ chọn và ghi theo taxonomy. `_preferred_stays` ghi số khách sạn bị bỏ vào `PREFERENCE` |
| Lập lịch, vé | `application/itinerary/flights.py::flight_options` | Số chuyến nhận về và số chuyến hợp lệ theo ngày, ghi qua tham số `counts` tuỳ chọn |
| Job khám phá | `agents/steps/jobs.py::_page`, cùng các nhánh `about_shown`, `cheaper`/`dearer`, `near` trong `_explore` | Tách điều kiện lọc của `_page` thành hàm có tên: đúng điểm đến, đúng loại, không phải vé, còn phòng, trong `query_ids`, chưa xem, gần mốc, so giá. Bộ lọc vẫn là "đạt mọi điều kiện", nên kết quả không đổi. Bộ đếm xếp mỗi sản phẩm vào ô theo thứ tự ở trên. Số cộng dồn vào `row["counts"]` qua các trang và qua job lấy tiếp (cập nhật nhóm gốc như `execute` đã làm với `cursor`) |
| Job vé | `agents/steps/fares.py` (`answer` và hàm tra chuyến nó gọi) | Số chuyến còn bán trong phạm vi câu hỏi; `chosen` = số chuyến trong `searchResults.flight` của câu trả lời |

B4 đọc kỹ từng hàm trên trước khi đặt điểm đếm. Nhánh nào không đếm được đúng định nghĩa thì không gửi số đó (để trống),
không ước lượng.

Web hiện:
- Lập lịch: "Khách sạn: tìm thấy 42, chọn 3". Trước `compose` thì chỉ có "Khách sạn: tìm thấy 42".
- Lập lịch, vé: "Vé Hà Nội → Đà Nẵng 17/10: 7 chuyến, chọn 1".
- Khám phá: "Khách sạn ở Hà Nội · gần Hồ Gươm: tìm thấy 8, giới thiệu 2", kèm ⚠ "bỏ 2 hết phòng, 4 bạn đã xem".
- Vé: "Vé TP. Hồ Chí Minh → Hà Nội: 8 chuyến".
- Nhóm `status = superseded` (câu hỏi vé được thay) thì Web ẩn dòng của nhóm đó.

**arrange.** Chỉ có ở lượt lập lịch, sau `compose`.

| Trường | Nguồn | Web hiện |
|---|---|---|
| `criteria` | `SHORTEST_DISTANCE` khi lịch có từ 2 điểm có toạ độ; `MAX_TWO_ACTIVITIES_PER_DAY` luôn có; `FLIGHT_TIMES` khi có chặng bay; `STAY_PREFERENCE` khi `counts.dropped.PREFERENCE > 0` | "Tối ưu theo: tổng quãng đường ngắn nhất · tối đa 2 hoạt động mỗi ngày · khớp giờ bay · ưu tiên khách sạn có hồ bơi" |
| `distanceKm` | `stayOptions.distanceKm` hoặc quãng đường của lịch | "(khoảng 38 km)" |
| `stayOptions` | Số phương án trong `stayOptions` | "3 phương án khách sạn để so sánh" |
| `budgetStatus` | `budgetSummary.status` (enum `BudgetStatus`) | Chỉ hiện ⚠ khi `OVER_BUDGET` |

**write.** Không có dữ kiện. Dòng đang chạy là "Đang viết lời tư vấn…" (lập lịch) hoặc "Đang viết câu trả lời…".
Narration dùng câu dự phòng (`reason ≠ llm`) hay `gatekeep` dùng câu dự phòng thì chỉ hiện ở chẩn đoán.

**Thông báo ⚠** (`notices`) dựng từ `counts.dropped` và các nguồn sau:

| Mã | Nguồn | Web hiện |
|---|---|---|
| `PRODUCT_DROPPED_DATE`, `PRODUCT_DROPPED_UNAVAILABLE` | `counts.dropped` | "2 khách sạn không còn chỗ ngày 17/10, đã bỏ qua" |
| `PRODUCT_DROPPED_PRICE`, `PRODUCT_DROPPED_PRICE_BASIS`, `PRODUCT_DROPPED_ATTRIBUTES`, `PRODUCT_DROPPED_NAMED_REQUIREMENT` | `counts.dropped` | B7 viết câu sau khi B4 ghi lại đúng nghĩa từng mã trong `retrieval._drop_reason`. Không đoán nghĩa từ tên mã |
| `SEEN` | `counts.dropped` | "Bỏ 4 khách sạn bạn đã xem" |
| `DUPLICATE` | `counts.dropped` | "Bỏ 2 điểm tham quan trùng nhau" |
| `RETRYING` | node `retry` | "Tìm kiếm chưa phản hồi, đang thử lại" |
| `NO_FLIGHT` | `flight_options` đã tra nhưng không có chuyến | "Không có chuyến Hà Nội → Đà Nẵng ngày 17/10" |
| `NOT_ON_SALE` | `evaluate` ghi `nearest_open_date` (lịch tham khảo) | "Ngày 17/10 chưa mở bán, đây là lịch tham khảo" |
| `OVER_BUDGET` | `budgetSummary.status` | "Tổng chi phí vượt ngân sách" |
| `NOTHING_NEW` | job `explore` có `status = empty`, `intent = more` | "Đã hết khách sạn mới ở Hà Nội" |
| `PLACE_NOT_FOUND` | ghi chú "điểm đến không có trong catalog" của job | "Chưa có dữ liệu về nơi này" |

### 3.4. Việc con đang chạy

Thêm sự kiện SSE mới `node.activity` với dữ liệu `{nodeId, code, round?, groupId?, kinds?, destination?, origin?, date?}`.

| Phát ở | Mã | Web hiện |
|---|---|---|
| `timed()`, lúc node bắt đầu (mọi node; `timed` nhận thêm tên node từ `build_graph`) | `STARTED` | Câu mặc định theo node (bảng ở B7). Riêng `orchestrate`: vòng 1 là "Đang hiểu yêu cầu của bạn…"; từ vòng 2, hoặc sau khi `gatekeep` trả về, là "Đang xem kết quả và soạn câu trả lời…" (`round` lấy từ số vòng đã chạy) |
| `tool_node`, trước `build_plan` | `PLANNING_SEARCH` | "Đang chọn những thứ cần tìm cho chuyến đi…" |
| `tool_node`, trước `run_calls`; `kinds` lấy từ plan | `SEARCHING` | "Đang tìm khách sạn, điểm tham quan ở Đà Nẵng…" |
| `flight_options`, trước khi tra (qua callback) | `SEARCHING_FLIGHTS` | "Đang tra vé Hà Nội → Đà Nẵng ngày 17/10…" |
| `tool_node`, trước `hydrate` | `CHECKING_AVAILABILITY` | "Đang kiểm tra giá và lịch trống ngày 17/10…" |
| `run_jobs` (`jobs._one`), trước mỗi job, kèm `groupId` | `SEARCHING` (job khám phá), `SEARCHING_FLIGHTS` (job vé), `READING_SHOWN` (`about_shown`) | "Đang tìm khách sạn ở Hà Nội…"; "Đang tra vé TP. Hồ Chí Minh → Hà Nội…"; "Đang xem lại thẻ bạn hỏi…" |

Cách làm:
- Helper `progress.notify(code, **params)` gọi `get_stream_writer()` trong `try/except RuntimeError`; ngoài graph thì
  không làm gì. Chỉ nhận khoá cho phép ở bảng trên. Giá trị lấy từ intent, plan, job hoặc catalog, không bao giờ là
  `query`.
- Tầng `application` không được import `agents`. Vì vậy `flight_options` và `retrieval.collect` nhận callback hoặc bộ đếm
  qua tham số tuỳ chọn, mặc định không làm gì (architecture §2; `tests/architecture/test_import_rules.py` sẽ bắt lỗi).
- Port `ItineraryPlanner.astream` phát cặp `("state", state)` hoặc `("event", payload)`.
  `runtime_dependencies.astream` dùng `stream_mode=["values", "custom"]`. Route đổi `("event", …)` thành `node.activity`
  hoặc `run.preview` (3.5).
- Phanh: không phát hai activity giống hệt liên tiếp; tối đa 30 activity mỗi lượt. Activity không ghi log riêng, vì
  `assistant.node` đã đủ.
- Có thể có nhiều activity cùng lúc (tối đa 3 job song song; Search và tra vé song song). Web hiện activity mới nhất;
  chẩn đoán hiện tất cả kèm mốc thời gian.
- Đồng hồ "Đang lâu hơn thường lệ" (12 giây) được đặt lại khi có `node.completed` **hoặc** `node.activity`. Cập nhật
  `docs/spec/product.md` §6.6 cho đúng điều này.

### 3.5. Kết quả từng phần

- **Làm hay không: quyết bằng số đo D1, trước khi code.** Người dùng chỉ đạo (12/10): preview chỉ giữ nếu đo thấy có
  ích. Plan đặt tiêu chí dưới đây; người dùng xác nhận tiêu chí khi chốt Phần C.
  - D1 ghi hai mốc cho mỗi lượt lập lịch: `t_compose` (lúc `compose` xong) và `t_final` (lúc `run.completed`).
  - Preview hiện từ `max(5 giây, t_compose)`, nên khoảng có ích là `t_final − max(5 giây, t_compose)`.
  - **Làm trước demo** nếu khoảng này từ 2 giây trở lên ở ít nhất một nửa số lượt lập lịch của D1 (3 lần chạy và bản
    diễn đạt khác). Không đạt thì không làm trước demo, và báo người dùng số đo để quyết bỏ hay để sau.
  - D6 đo lại: nếu đã làm mà khoảng có ích ở staging không còn đạt tiêu chí, thì báo người dùng để quyết giữ hay gỡ.
- **Khi nào phát.** `compose` trả `COMPLETED`. Lúc đó lịch đã xếp xong bằng luật, chỉ còn `narrate` gọi LLM.
- **Gửi gì.** Sự kiện `run.preview` với dữ liệu `{runId, products: ProductSummary[]}`, tối đa 6 sản phẩm, theo thứ tự:
  khách sạn của lịch theo đêm; điểm tham quan và golf theo ngày rồi theo buổi; combo và gói nhiều ngày. Không gửi vé máy
  bay, vì dòng vé ở bước search đã đủ. Hàm thuần `progress.preview(state, update)` dựng payload và phát qua writer trong
  `timed()` của `compose`.
- **Grounding.** Mọi `productId` phải có trong `sources` (đã kiểm ở `evaluate`) và trong response của `compose`. Mọi
  trường lấy nguyên từ sản phẩm trong response, giống `searchResults`. Không đạt thì không gửi preview và không báo lỗi.
- **Web.** Chỉ hiện khi lượt đã chạy từ `PREVIEW_AFTER_MS = 5000` tính từ lúc gửi. Nhận preview trước mốc này thì giữ
  lại, tới mốc mới hiện. `run.completed` tới trước mốc thì preview không bao giờ hiện, nên màn hình không nháy. Thẻ gọn
  chỉ để xem: bấm vào mở panel chi tiết có sẵn; không có nút Thêm hay Đặt ngay. Tiêu đề: "Đã chọn xong, đang viết lời tư
  vấn".
- **Khi xong.** `run.completed` thì bong bóng tiến trình, cùng preview, được thay bằng câu trả lời. `run.failed` hoặc
  người dùng dừng sau khi đã có preview thì preview biến mất cùng tiến trình, và lỗi hoặc ghi chú đã dừng hiện như hiện
  nay.
- **Không áp dụng cho lượt khám phá và lượt vé** (Q6, người dùng chốt 13/10; để giới hạn phạm vi). Ở lượt khám phá, LLM của
  orchestrator chọn thẻ sau khi đọc kết quả job, nên trước lúc đó chưa có thẻ cuối để hiện; chỉ hiện số lượng.

### 3.6. Thu gọn khi xong

- Khi `run.completed`, Web chụp `ProgressView` cuối vào tin nhắn trợ lý (`AssistantTranscriptItem.progress`). Không gọi
  thêm API nào.
- Ở đầu câu trả lời, trên lời diễn giải và các thẻ, hiện một dòng gồm ✓, câu tóm tắt và nút "Xem các bước"
  (`aria-expanded`). Mở ra là danh sách bước đã xong, không có spinner.
- Câu tóm tắt:
  - Lập lịch: `{điểm đến} · {ngày} · {số ngày} · {đoàn} — {N} khách sạn → {K}, {N} điểm tham quan → {K}, vé {K} chuyến`.
    Có thông báo ⚠ thì thêm "· {n} lưu ý".
  - Khám phá: "Khách sạn ở Hà Nội · tìm thấy 24, giới thiệu 2".
  - Vé: "Vé TP. Hồ Chí Minh → Hà Nội · 8 chuyến".
  - Trò chuyện, hỏi lại, lượt bị chặn: **không có dòng**, vì không có gì để tóm tắt.
- Hội thoại mở lại từ lịch sử (`GET /assistant/conversations/{id}`) không có tiến trình, nên không có dòng (Q7).
- Dòng "So sánh các phương án tìm được…" của hàng thẻ khách sạn giữ nguyên.

### 3.7. Ví dụ hiển thị

Đang chạy, lượt lập lịch (giây thứ 6):

```
Trợ lý du lịch V-OTA
✓ Đà Nẵng · 17/10 · 3 ngày · 2 người lớn · từ Hà Nội
    Ngân sách: chưa nêu → không giới hạn theo giá
✓ Khách sạn: tìm thấy 42 · Điểm tham quan: tìm thấy 15
  Vé Hà Nội → Đà Nẵng 17/10: 7 chuyến
  ⚠ 2 khách sạn không còn chỗ ngày 17/10, đã bỏ qua
✓ Tối ưu theo: tổng quãng đường ngắn nhất (khoảng 38 km) · tối đa 2 hoạt động mỗi ngày · khớp giờ bay
⟳ Đang viết lời tư vấn…
  Đã chọn xong, đang viết lời tư vấn
  [thẻ KS A] [thẻ Bà Nà] [thẻ Ngũ Hành Sơn] …
```

Lượt khám phá có hai job cùng loại khác điều kiện, đang ở vòng 2:

```
✓ Khách sạn ở Hà Nội · gần Hồ Gươm  |  Khách sạn ở Hà Nội · rẻ hơn thẻ #2
✓ Khách sạn gần Hồ Gươm: tìm thấy 8   ⚠ bỏ 2 hết phòng
  Khách sạn rẻ hơn thẻ #2: tìm thấy 5
⟳ Đang xem kết quả và soạn câu trả lời…
```

Khi xong:

```
✓ Đà Nẵng · 17/10 · 3 ngày · 2 người lớn — 42 khách sạn → 3, 15 điểm tham quan → 4, vé 1 chuyến · 1 lưu ý  [Xem các bước ▾]
**Đà Nẵng 3 ngày thư thả** …
```

### 3.8. Chẩn đoán cho nhà phát triển

**Mức 1** (B2, B7; trước demo). Không cần khoá server, vì chỉ dùng dữ liệu stream đã gửi cho mọi người dùng.
- Trong `components/common/DebugPanel.tsx` (bật bằng Shift+D) thêm mục "Trợ lý — lượt gần nhất":
  - `runId` và `requestId` lấy từ `run.started`; `turnKind`.
  - Bảng node: thứ tự, `nodeId`, `outcome`, `message`, `durationMs`, mốc cộng dồn; vòng của `orchestrate`.
  - Các activity kèm mốc thời gian.
  - Số đếm đầy đủ của từng nhóm (`sourceTotal`, `received`, `outOfScope`, `eligible`, `chosen`).
  - Thời điểm có preview và có kết quả.
  - Nút sao chép `requestId`, dùng để lọc trace LangSmith theo metadata `request_id` (`docs/spec/agent/README.md`).
- Khi `debugMode` bật, `WidgetProgress` hiện thêm dưới mỗi bước một dòng chữ đơn cách nhỏ: `nodeId · ms`.

**Mức 2** (B9; sau demo, Phần B của đề xuất). Chi tiết lời gọi tool và LLM.
- **Ai nhận.** Chỉ request mang header `X-Assistant-Debug-Token` khớp biến bí mật `ASSISTANT_STREAM_DEBUG_TOKEN` của
  server (so sánh thời gian hằng). Biến trống thì tính năng tắt. Không khớp thì không có `debug` và không báo lỗi. Như
  vậy client thường không bao giờ nhận `debug`, kể cả khi server có khoá; `DebugPanel` đóng hay mở không quyết định
  điều này.
- **Web.** `DebugPanel` có ô nhập khoá, lưu trong `sessionStorage`. Header chỉ được gửi khi `debugMode` bật và có khoá.
  BFF chuyển header này lên backend (nó không nằm trong `STRIPPED_REQUEST_HEADERS`). B9 thêm test BFF, và kiểm logger
  của BFF không ghi header.
- **Gửi gì.** `node.completed.debug` gồm:
  - `toolCalls[]`: `name`, `durationMs`, `outcome`, `code`, `resultCount`, `args`.
  - `llmCalls[]`: đúng 4 khoá `schema`, `model`, `durationMs`, `outcome`.
  - `metadata`: metadata của event (đều là số, mã, hoặc boolean; B9 kiểm).
- **Danh sách trường được phép theo từng tool** (hằng số trong code, không có danh sách cấm):
  - `search_products`: `destination`, `taxonomy`, `limit`, `offset`, `availableOnly`, `sort`, và các trường ngày hoặc số
    của `SearchRequest`.
  - `get_recommendations`: `k`/`limit`, `destination`, `taxonomy`.
  - `get_similar_products`, `get_product_detail`: `productId`, `limit`.
  - `list_products`: `destination`, `taxonomy`, `sort`, `limit`, `offset`, `availableOnly`.
  - Tra chuyến: `parentProductId`, `availableOnly`, ngày.
  - Tool không có trong danh sách: chỉ `name`, `durationMs`, `outcome`, `resultCount`.
- **Quy tắc với dữ liệu.**
  - Danh sách cho phép áp theo đường dẫn đầy đủ. Đối tượng lồng nhau chỉ giữ đường dẫn có trong danh sách; mọi khoá khác
    bị bỏ, kể cả `api_key` nằm sâu bên trong.
  - Giá trị chỉ giữ khi đúng kiểu: số, boolean, ngày ISO, giá trị enum của contract, hoặc `productId`. Chuỗi tự do (như
    `query`) bị bỏ mặc định. Muốn xem câu tìm thì dùng LangSmith (môi trường dev cá nhân).
  - Test xác nhận mọi trường trong danh sách cho phép đều có kiểu không tự do trong schema OpenAPI của tool (`tool_contracts.py`
    đọc schema từ contract).
- Thu thập bằng collector theo request (contextvar):
  - Lời gọi tool ghi ở `agents/tools/itinerary_gateway.py` (gồm cả `list_products`, `get_product_detail` mà job gọi thẳng).
  - Lời gọi LLM ghi ở `_LoggedStructured` (`agents/steps/messages.py`), gồm cả lời gọi của orchestrator.
- Không bao giờ gửi: prompt, output thô của LLM (kể cả `OrchestratorTurn`), JWT, header, chuỗi tự do.
- Môi trường: `ASSISTANT_STREAM_DEBUG_TOKEN` chỉ đặt ở dev local và staging; production để trống (Q5). Staging chạy
  `APP_ENV=production` (`infra/terraform/environments/staging-ha/compose.ha.yml`), nên chặn bằng khoá chứ không bằng
  `APP_ENV`.

### 3.9. Contract (1.26.0 → 1.27.0, chỉ thêm)

Sửa `src/shared/contracts/schemas/itinerary-agent.yaml` và mô tả trong `paths/itinerary-agent.yaml`, rồi tăng `version`
trong `openapi.yaml`. Theo `docs/prd/api-contract.md` §3: chỉ thêm khoá tuỳ chọn và thêm giá trị enum cho sự kiện;
không đổi nghĩa trường cũ. Web là client duy nhất, và đã bỏ qua sự kiện lạ. `debug` không có schema chi tiết trong
contract công khai: nó chỉ dành cho người có khoá, và được kiểm bằng test backend.

Bản trước demo chỉ gồm phần đã chốt:
- Không có `run.preview` và `AssistantRunPreview` nếu Phần C chưa chốt.
- Không có khoá `debug`, vì Phần B làm sau demo.

Phần nào chốt sau thì thêm ở bản phụ tiếp theo (1.28.0), cũng chỉ thêm. Fixture tương ứng (`stream-plan.json` có
preview) cũng thêm cùng lúc.

```yaml
AssistantStreamEvent:      # thêm giá trị vào enum event
  event: [run.started, graph.topology, node.activity, node.completed, run.preview, run.completed, run.failed]

AssistantNodeCompletedData:          # mới: mô tả data của node.completed
  required: [sequence, nodeId, outcome, message, durationMs]
  additionalProperties: false
  properties:
    sequence: {type: integer, minimum: 1}
    nodeId: {type: string}
    outcome: {type: string}
    message: {type: string}          # chuỗi chẩn đoán, Web không hiện cho người dùng
    durationMs: {type: integer, minimum: 0}
    progress: {$ref: AssistantProgressUpdate}   # tuỳ chọn
    debug: {type: object}            # chỉ khi request mang khoá chẩn đoán hợp lệ

AssistantProgressUpdate:
  additionalProperties: false
  properties:
    turnKind: {enum: [plan, clarify, explore, fare, converse, blocked]}
    steps: {type: array, maxItems: 4, items: {enum: [understand, search, arrange, write]}}
    completedStep: {enum: [understand, search, arrange, write]}
    understood: {$ref: AssistantUnderstood}
    searches: {type: array, maxItems: 12, items: {$ref: AssistantSearchGroup}}
    arranged: {$ref: AssistantArrangeSummary}
    notices: {type: array, maxItems: 10, items: {$ref: AssistantProgressNotice}}

AssistantProgressNotice:
  required: [code]
  additionalProperties: false
  properties: {code: {enum: [...mã ở 3.3]}, groupId: {type: string}, kind: {$ref: Taxonomy},
               count: {type: integer, minimum: 1}, date: {type: string, format: date}}   # count là số cộng dồn

AssistantSearchGroup:
  required: [groupId, kind, status]
  additionalProperties: false
  properties:
    groupId: {type: string, pattern: '^(plan:[a-z]+|job:[1-9][0-9]*)$'}
    kind: {$ref: Taxonomy}
    scope:                           # chỉ trường cấu trúc; không có query
      destination, near, sort, intent, origin, date, returnDate
    status: {enum: [running, ok, empty, failed, superseded]}
    counts:
      sourceTotal, received, inScope, eligible, chosen: {type: integer, minimum: 0}
      outOfScope, dropped: {type: object, additionalProperties: {type: integer, minimum: 0}}   # khoá là mã lý do (enum)
      sourceMore: {type: boolean}

AssistantNodeActivity:     # data của node.activity
  required: [nodeId, code]
  properties: {nodeId, round, groupId, code: {enum: [STARTED, PLANNING_SEARCH, SEARCHING, SEARCHING_FLIGHTS,
               CHECKING_AVAILABILITY, READING_SHOWN]}, kinds: [Taxonomy], destination, origin, date}

AssistantRunPreview:       # data của run.preview
  required: [runId, products]
  properties: {runId: string, products: {type: array, maxItems: 6, items: {$ref: ProductSummary}}}
```

**Quy tắc cập nhật** (ghi trong mô tả schema):
- Mỗi `progress` là một bản cập nhật theo khoá.
- `understood`, `arranged`, `turnKind`, `steps`: bản mới thay bản cũ.
- `searches`: cập nhật theo `groupId`. Nhóm có trong bản cập nhật **thay toàn bộ** nhóm cùng `groupId` mà Web đang giữ;
  nhóm không có thì giữ nguyên. Backend luôn gửi số cộng dồn của nhóm, Web không tự cộng. Không có thao tác xoá; nhóm bị
  thay thì gửi `status = superseded`.
- `notices`: cập nhật theo khoá `(code, groupId, date)`. Thông báo không gắn nhóm (`RETRYING`, `NOT_ON_SALE`,
  `OVER_BUDGET`) dùng `groupId` rỗng trong khoá.
  - Thông báo cùng khoá **thay** bản Web đang giữ; không nối thêm, không cộng. `count` luôn là số cộng dồn do backend
    tính. Ví dụ: vòng 1 gửi `SEEN` của `job:1` với `count = 2`; job lấy tiếp ở vòng 2 gửi lại cùng khoá với `count = 5`;
    Web hiện "Bỏ 5 khách sạn bạn đã xem", không hiện 2 và 5, không hiện 7.
  - Khoá mới thì thêm.
  - Nhóm chuyển `status = superseded` thì mọi thông báo có `groupId` của nhóm đó bị ẩn cùng nhóm.
  - Backend gửi lại thông báo của một nhóm mỗi khi số của nhóm đổi, trong cùng bản cập nhật với nhóm đó.

**Fixture mới** trong `src/shared/mocks/itinerary-agent/`. Mỗi fixture là danh sách `{event, data}`, ghi theo đúng thứ
tự node của orchestrator:
- `stream-plan.json`: `precheck` → `orchestrate(plan)` → `extract` → `tool` → `evaluate` → `filter` → `compose` →
  `narrate` → `finalize`, có preview và ⚠.
- `stream-explore-jobs.json`: hai job khách sạn cùng Hà Nội khác điều kiện (gần Hồ Gươm; rẻ hơn một thẻ) thành hai nhóm;
  một job lấy tiếp ở vòng 2 cập nhật đúng nhóm gốc, kèm thông báo `SEEN` của nhóm đó đổi từ `count = 2` (vòng 1) sang
  `count = 5` (vòng 2); có một vòng `gatekeep` → `orchestrate` để sửa câu.
- `stream-fare-superseded.json`: job vé bị thay ở vòng sau; nhóm cũ và thông báo của nó chuyển `superseded`.
- `stream-fare-job.json`: hỏi vé qua job `fare`.
- `stream-fare-button.json`: nút vé đi thẳng `precheck` → `run_jobs`.
- `stream-clarify.json`, `stream-answer.json` (`orchestrate` ra `answer`, không job), `stream-blocked.json` (guardrail).

Ghi vào `src/shared/mocks/index.json`. `validate_contract.py` kiểm từng `data` theo schema của sự kiện. E2E của Web dùng
chính các fixture này.

**Sửa spec cùng lúc:**
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` mục "API stream cho UI demo": sự kiện mới, `progress`, quy tắc cập
  nhật, `debug` và khoá; vẫn giữ câu "không chứa raw state, prompt, token".
- `docs/spec/hop-dong-tich-hop-frontend.md` dòng "Tiến độ" (§9.6) và bảng D9.
- `docs/spec/product.md` §6.1 (thay 3 bước cố định bằng bước theo loại lượt; sửa dòng "Hiện trạng code") và §6.6 (đồng
  hồ chậm, kết quả từng phần).
- `docs/spec/agent/response-and-errors.md` nếu có mục mô tả stream.

### 3.10. Frontend

| File | Việc |
|---|---|
| `services/assistantStream.ts` | Thêm `node.activity`, `run.preview` vào union sự kiện. Gửi header khoá chẩn đoán khi có |
| `context/assistantState.ts` | `AssistantProgress` thêm `progress?`, `debug?`. State thêm `run: {runId, requestId, startedAt}`, `activities[]`, `preview`, và `progressModel` đã gộp theo quy tắc cập nhật. Action mới: `run-started`, `node-activity`, `run-preview`. Khi `completed`, chép `ProgressView` cuối vào tin nhắn trợ lý |
| `context/AssistantProvider.tsx` | Đọc sự kiện mới (thay `nodeProgress` bằng hàm đọc có kiểm kiểu). Đặt lại đồng hồ chậm khi có activity. Đồng hồ preview 5 giây |
| `features/itinerary/widget/progressModel.ts` (mới) | Hàm thuần gộp các bản cập nhật theo đúng quy tắc ở 3.9. Đây là nơi duy nhất áp quy tắc này |
| `features/itinerary/widget/widgetProgressView.ts` | Viết lại thành hàm thuần: (model, activity, preview, bây giờ) → `{turnKind, steps: [{key, status, title, lines[], notices[]}], current, summary, showPreview}`. Xoá bảng `AFTER_NODE` |
| `features/itinerary/widget/widgetProgressLabels.ts` (mới) | Mã → câu tiếng Việt. Ngày dd/mm theo giờ Việt Nam, số người, tiền `vi-VN`, tên loại sản phẩm. Thiếu câu cho một mã thì bỏ dòng đó, không hiện mã |
| `features/itinerary/widget/WidgetProgress.tsx` | Vẽ dòng kết quả dưới mỗi bước, ⚠ màu hổ phách, hàng thẻ preview, dòng `nodeId · ms` khi `debugMode` |
| `features/itinerary/widget/WidgetProgressSummary.tsx` (mới) | Dòng tóm tắt và phần mở rộng |
| `features/itinerary/widget/WidgetChat.tsx` | Dòng tóm tắt ở đầu tin nhắn trợ lý; preview trong bong bóng tiến trình |
| `components/common/DebugPanel.tsx` | Chẩn đoán mức 1; ô nhập khoá và hiện `debug` của mức 2 |

- Trợ năng: `role=status` chỉ đọc câu đang làm, và đọc "Xong: {tóm tắt bước}" đúng một lần khi một bước xong; không đọc
  lại cả danh sách. Mỗi ⚠ chỉ đọc một lần. Nút mở rộng có `aria-expanded` và `aria-controls`. Spinner dùng
  `motion-safe:animate-spin`.
- Màn 390 px: dòng dài thì xuống dòng, không cuộn ngang; mỗi bước tối đa 4 dòng kết quả, phần còn lại ghi "+n".

## 4. Các bước

Mỗi bước: viết test trước và test phải fail trên code cũ, rồi sửa, rồi chạy lệnh kiểm tra, rồi ghi entry `history/`.

### B0. Đo thời gian từng node — đã gộp vào D1

Bước này đã chuyển thành D1 của plan chung: 6 kịch bản nối tiếp, chạy 3 lần qua `/stream`, có bản diễn đạt khác. D1 ghi
`nodeId`, `durationMs` của mọi `node.completed`, số vòng `orchestrate`, và hai mốc `t_compose`, `t_final` của lượt lập
lịch dùng cho 3.5.

### B1. Chốt đề xuất PRD

- Đề xuất orchestrator là mặc định: người dùng **đã chốt** ngày 13/10/2026, đã áp dụng vào PRD
  và chuyển sang `docs/prd/update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`. Đây là điều kiện để plan này
  chỉ làm cho orchestrator.
- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md`: **Phần A/C đã áp dụng 13/10; Phần B chờ chốt**. Phần A cần chốt trước B2–B8;
  Q7 nằm trong Phần A. Phần C chỉ xin chốt khi có số đo D1.
- Khi một phần được chốt: cập nhật `docs/prd/` đúng nội dung đã chốt **trước**, ghi ngày và người chốt vào đề xuất.
  Khi mọi phần đã áp dụng hoặc bị từ chối, đổi trạng thái đề xuất và `git mv` sang `docs/prd/update-archive/`
  (AGENTS.md §8).

### B2. Chẩn đoán mức 1 (frontend)

- Sửa: `context/assistantState.ts` (lưu `runId`, `requestId`, `startedAt` từ `run.started`), `context/AssistantProvider.tsx`,
  `components/common/DebugPanel.tsx`.
- Test trước:
  - `tests/unit/assistantState.test.ts`: `run.started` lưu hai id.
  - Test mới `tests/unit/debugPanelAssistant.test.tsx`: debug bật thì có bảng node (`nodeId`, `durationMs`, mốc cộng dồn)
    và nút sao chép `requestId`; debug tắt thì không render gì của trợ lý.
- Kiểm tra: `cd src/frontend && node_modules/.bin/vitest run && node_modules/.bin/tsc --noEmit`.
- Xong khi: test xanh; mở trang, bấm Shift+D, gửi một câu và thấy bảng node của lượt.

### B3. Contract 1.27.0

- Sửa: `src/shared/contracts/schemas/itinerary-agent.yaml`, `src/shared/contracts/paths/itinerary-agent.yaml`,
  `src/shared/contracts/openapi.yaml` (`version`), 8 fixture stream, `src/shared/mocks/index.json`,
  `src/shared/contracts/tests/validate_contract.py`.
- Negative check trong `validate_contract.py`: khoá lạ trong `progress`; mã ngoài enum; `products` quá 6; `groupId` sai
  mẫu; `counts` âm; `scope` có `query`.
- Sinh lại `src/frontend/src/types/api.gen.ts` bằng `npm run generate:api-types` (trong `src/frontend`); không sửa tay.
- Sửa spec theo 3.9.
- Kiểm tra: `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` (từ repo root).
- Xong khi: validate PASS; các schema mới có fixture dương và fixture âm.

### B4. Dữ kiện và số đếm tại chỗ xử lý (backend)

- Mới: `agents/steps/progress.py`:
  - `Counts`: bộ đếm theo nhóm, xếp mỗi sản phẩm vào đúng một ô theo thứ tự ở 3.3.
  - `for_node(node, state_before, update)`: dựng `progress` theo 3.2 và 3.3.
  - `notify()`: theo 3.4.
- Sửa ở nơi lọc (chỉ thêm tham số tuỳ chọn, tách điều kiện thành hàm có tên, không đổi kết quả):
  - `application/itinerary/retrieval.py::collect`.
  - `agents/steps/evaluation.py::_preferred_stays`.
  - `application/itinerary/flights.py::flight_options`.
  - `agents/steps/jobs.py::_page`, `_explore`, `_one` (job lấy tiếp), `execute` (cập nhật nhóm gốc).
  - `agents/steps/fares.py`.
- Sửa:
  - `agents/state.py`: `LabEvent` thêm `progress: dict | None = None`; `AgentState` thêm `progress_counts`.
  - `agents/graph.py`: `timed()` nhận tên node và gắn `progress` vào event cuối của update.
  - `api/v1/routes/assistant.py`: đưa `progress` vào `node.completed` khi có.
- Test trước, file mới `tests/unit/agents/test_progress.py`:
  - Mỗi giá trị `decision` của `precheck`, `orchestrate`, `extract`, `run_jobs`, `gatekeep` ra đúng `turnKind`. Nút vé ra
    `fare`. `execute` có cả job khám phá và job vé ra `explore`. Loại lượt đổi được (explore → plan qua hai vòng).
  - Đủ 8 mã `assumptions`, mỗi mã có ca đúng điều kiện và ca sát điều kiện mà không phát.
  - Bất biến đếm trên mọi fixture: `received = inScope + Σ outOfScope`; `inScope = eligible + Σ dropped`;
    `chosen ≤ eligible`.
  - `_page`:
    - Câu "gần Hồ Gươm": khách sạn xa mốc vào `outOfScope`, không vào `inScope`.
    - Khách sạn vừa xa vừa hết phòng chỉ đếm một lần, ở `outOfScope`.
    - `SEEN` chỉ đếm sản phẩm thật sự có trong trang và bị bỏ, không đếm độ dài `excluded`.
    - `sourceTotal` không bao giờ thành "tìm thấy".
    - Kết quả lọc trước và sau khi tách điều kiện giống hệt nhau trên cùng đầu vào.
  - Hai job khách sạn cùng Hà Nội khác điều kiện ra hai nhóm `job:1`, `job:2`. Job lấy tiếp (`continue_from`) cập nhật
    `job:<gốc>` với số cộng dồn, không sinh nhóm mới. Job vé bị thay ra `superseded`.
  - Thông báo: job lấy tiếp gửi lại `SEEN` của nhóm gốc với `count` cộng dồn (2 ở vòng 1, 5 ở vòng 2), cùng bản cập nhật
    với nhóm; nhóm `superseded` gửi kèm trạng thái để Web ẩn thông báo của nó.
  - `chosen` của mỗi nhóm = giao `productId` của nhóm với response cuối. Hai nhóm có chung một sản phẩm thì mỗi nhóm đều
    đếm nó, đúng định nghĩa giao; Web không cộng hai nhóm để ra tổng (B7 test).
  - `criteria` chỉ có tiêu chí thật: lịch không có chặng bay thì không có `FLIGHT_TIMES`.
  - **Không có chữ do LLM:** duyệt mọi chuỗi trong `progress`; mỗi chuỗi phải là mã enum, ngày ISO, hoặc giá trị lấy từ
    intent, job hay catalog trong fixture. Không chuỗi nào là `query`, `message` hay chữ của `OrchestratorTurn`.
- Sửa `tests/contract/test_assistant_contract.py`: tập khoá cho phép thêm `progress`; kiểm `progress` theo schema; thêm
  test "khoá `debug` vắng mặt khi không có khoá chẩn đoán". Giữ nguyên kiểm `secret-token`.
- Kiểm tra:
  - `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/contract src/backend/tests/architecture`.
  - Snapshot (baseline D3 của plan chung, cùng phần đã ghi lại ở D4, D5) xanh mà không ghi lại.
- Xong khi: test xanh; snapshot không đổi; route JSON không đổi.

### B5. Việc con đang chạy (backend)

- Sửa:
  - `application/ports/itinerary_planner.py` và `agents/runtime_dependencies.py`: phát cặp `(kind, payload)`, dùng
    `stream_mode=["values", "custom"]`.
  - `agents/graph.py`: `timed()` phát `STARTED` (kèm `round` cho `orchestrate`).
  - Điểm phát ở 3.4: `agents/nodes.py` (`tool_node`), `application/itinerary/flights.py` (callback),
    `agents/steps/jobs.py` (`_one`).
  - Route: `node.activity`.
- Test trước (graph nhỏ với tool giả, theo mẫu `tests/unit/agents/test_itinerary_tools.py` và
  `test_orchestrator_runtime.py`; chạy `astream`):
  - Lập lịch: `STARTED(tool)` → `PLANNING_SEARCH` → `SEARCHING` → `CHECKING_AVAILABILITY` → `node.completed(tool)`.
    `SEARCHING_FLIGHTS` phát được từ trong `asyncio.gather` (contextvar có sang task con).
  - Khám phá: `STARTED(orchestrate, round 1)` → `STARTED(run_jobs)` → `SEARCHING` mỗi job (đúng `groupId`) →
    `STARTED(orchestrate, round 2)` → `STARTED(gatekeep)`.
  - Nút vé: `STARTED(precheck)` → `STARTED(run_jobs)` → `SEARCHING_FLIGHTS`.
  - Gọi `tool_node`, `run_jobs_node` trực tiếp ngoài graph không lỗi.
  - Phanh 30 activity; hai activity giống nhau liên tiếp chỉ phát một.
  - Test contract: mọi `node.activity` hợp schema; tên sự kiện nằm trong enum.
- Kiểm tra: như B4.
- Xong khi: test xanh, snapshot không đổi.

### B6. Kết quả từng phần (backend)

- Sửa: `agents/steps/progress.py` (`preview()`), `agents/graph.py` (`timed` của `compose` phát preview), route
  (`run.preview`).
- Test trước:
  - Có preview khi `COMPLETED`; tối đa 6 sản phẩm; đúng thứ tự ở 3.5.
  - Mọi `productId` của preview nằm trong response cuối của lượt (kiểm qua stream đầy đủ với LLM ghi sẵn).
  - Response `FALLBACK`, `NO_RESULTS`, lượt khám phá, lượt vé: không có preview.
  - Sản phẩm không có trong `sources` thì không có preview.
- Xong khi: test xanh, snapshot không đổi.

### B7. Mô hình và hiển thị tiến trình (frontend)

- Sửa và thêm file theo 3.10, trừ phần thu gọn và preview.
- Test trước:
  - `tests/unit/progressModel.test.ts` (mới): đúng quy tắc cập nhật ở 3.9.
    - Nhóm thay toàn bộ theo `groupId`; nhóm vắng thì giữ; `superseded` thì ẩn; Web không tự cộng số.
    - Thông báo `SEEN` của `job:1` đổi 2 → 5 (`stream-explore-jobs.json`): Web giữ đúng một thông báo với số 5.
    - Thông báo của nhóm `superseded` bị ẩn (`stream-fare-superseded.json`).
    - Thông báo không gắn nhóm (`RETRYING`) gửi hai lần chỉ hiện một lần.
  - Viết lại `tests/unit/widgetProgress.test.ts` theo bảng, đầu vào là 8 fixture stream của B3:
    - Lập lịch: đủ 4 bước, có dòng kết quả, có ⚠.
    - Khám phá: hai nhóm cùng loại hiện hai dòng; nhóm lấy tiếp cập nhật đúng dòng; vòng sửa câu không thêm bước.
    - Job vé và nút vé: `turnKind = fare`, không có bước viết.
    - Hỏi lại có "Còn thiếu"; `answer` chỉ có bước 1; lượt bị chặn không có ✓.
    - `retry`; lượt đổi loại giữa chừng không mất dòng ✓.
    - Trước khi biết loại lượt thì không có bước mờ.
    - **Không lộ thông tin kỹ thuật:** chuỗi hiển thị không chứa `nodeId`, tên tool, `message`, `sourceTotal` hay `query`.
    - Mã không có câu thì dòng bị bỏ.
  - Sửa `tests/unit/floatingWidgetOpening.test.tsx` và `tests/unit/assistantProvider.test.tsx` (đồng hồ chậm đặt lại khi
    có activity).
- Kiểm tra: `vitest run`, `tsc --noEmit`, ESLint trên các file đã sửa.
- Xong khi: test xanh. Chụp màn hình 1024 px và 390 px bằng một spec tạm (xoá sau khi chụp), phát fixture stream theo thời
  gian.

### B8. Thu gọn khi xong và kết quả từng phần (frontend)

- Sửa: `WidgetProgressSummary.tsx` (mới), `WidgetChat.tsx`, `assistantState.ts` (chép tiến trình vào tin nhắn), đồng hồ
  preview trong `AssistantProvider.tsx`.
- Test trước (dùng fake timers):
  - Preview tới lúc 3 giây, `run.completed` lúc 4 giây: preview không bao giờ hiện.
  - Preview tới lúc 3 giây, chưa xong lúc 5 giây: hiện đúng lúc 5 giây.
  - Preview tới lúc 7 giây: hiện ngay.
  - Bấm thẻ preview mở panel chi tiết; thẻ preview không có nút đặt.
  - `run.failed` sau preview: preview biến mất, hiện thông báo lỗi.
  - Dòng tóm tắt chỉ có ở lượt lập lịch, khám phá, vé; nút mở rộng có `aria-expanded`.
  - Hội thoại tải từ lịch sử không có dòng tóm tắt.
- E2E: thêm vào `tests/e2e/widget-opening.spec.ts` một ca phát `stream-plan.json`: thấy dòng kết quả, thấy preview sau
  5 giây, thấy dòng tóm tắt sau khi xong.
- Kiểm tra: `vitest run`, `tsc --noEmit`, `npm run build:web`, rồi Playwright cho `widget-opening.spec.ts` và
  `widget-detail.spec.ts`.

### B9. Chẩn đoán mức 2 (khoá server)

- Sửa:
  - `core/config.py`: `assistant_stream_debug_token: str = ""`.
  - Collector contextvar, danh sách trường cho phép theo tool, hàm lọc theo đường dẫn và kiểu. Đặt trong một module riêng
    ở `agents/`.
  - `agents/tools/itinerary_gateway.py` và `agents/steps/messages.py` (`_LoggedStructured`): ghi vào collector.
  - Route: so khoá bằng `hmac.compare_digest`; khớp thì gắn `debug` vào `node.completed`.
  - Web: `services/assistantStream.ts` gửi header; `DebugPanel.tsx` có ô nhập khoá và hiện `debug`.
  - `docs/prd/deployment-plan.md` §2 (đúng nội dung đã chốt) và `.env.example`.
- Test trước:
  - Khoá server trống: không có `debug`, kể cả khi request có header.
  - Header sai hoặc thiếu: không có `debug`, response không khác gì request thường.
  - Đúng khoá:
    - `toolCalls` có đủ khoá cho phép.
    - `args` lồng nhau chứa `api_key`, `token`, `query` có bí mật, hay chuỗi tự do đều bị bỏ.
    - `llmCalls` có đúng 4 khoá; không có chữ của `OrchestratorTurn`.
    - `secret-token` của header `Authorization` không xuất hiện ở đâu.
  - Mọi trường trong danh sách cho phép có kiểu không tự do trong schema tool.
  - **Hai request chạy đồng thời** (`asyncio.gather` hai stream, một có khoá, một không): request có khoá chỉ thấy lời gọi
    của chính nó; request không khoá không có `debug`.
  - BFF: header khoá được chuyển lên; logger của BFF không ghi header (`tests/api/proxy-stream.test.ts`).
- Xong khi: test xanh, snapshot không đổi.

### B10. Kiểm end-to-end, tài liệu

**B10a, trước demo (gộp vào D6 của plan chung).**
- Chạy K1–K6 của D1 trên staging kèm Web; ghi GIF hoặc ảnh chụp.
- Đối chiếu từng dòng tiến trình với trace LangSmith của cùng `requestId`: số `inScope` và `chosen` khớp với các bước lọc
  trên trace; ⚠ khớp `warnings`. Nếu đã làm preview, ghi thời điểm preview hiện so với lúc có câu trả lời (3.5).
- Báo kết quả theo tầng bằng chứng (`docs/spec/agent/working-context.md` §5C): fixture, backend local + Postgres, LLM
  thật. Ghi rõ thứ chưa kiểm.
- Cả bộ backend: `WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests`.

**Tiêu chí trước demo** (dùng ở mục 3 của plan chung, ý 8):
- Mọi lượt của K1–K6 có khung tiến trình chạy theo việc thật. Không lượt nào đứng ở "Đang hiểu yêu cầu của bạn…" sau
  khi `orchestrate` vòng 1 đã xong.
- Bước tìm kiếm của lượt khám phá, vé và lập lịch có dòng "tìm thấy N, chọn K", hoặc ghi rõ không tra được. Số khớp
  trace ở mỗi kịch bản (đối chiếu một lượt mỗi kịch bản).
- Lượt có sản phẩm bị loại hoặc tra cứu thất bại có dòng ⚠ đúng lý do.
- Khung không lộ tên tool, API, `query`, JSON hay `nodeId` khi `debugMode` tắt.
- Khi xong, lượt lập lịch, khám phá và vé thu gọn thành một dòng tóm tắt trên lời diễn giải và các thẻ.
- Màn 390 px không cuộn ngang.

**B10b, sau demo.** Cập nhật `docs/spec/agent/working-context.md` §3 (bản đồ runtime: sự kiện stream mới) và skill
`building-itinerary-agent` nếu cần thêm hàng "Hiển thị tiến trình". Entry history cuối gồm số thật của mọi lệnh đã chạy.

## 5. Ma trận kiểm thử

| Tầng | Bắt lỗi gì | Ở bước |
|---|---|---|
| Unit backend `test_progress.py` | Loại lượt sai, số đếm sai hoặc đếm lặp, nhóm bị gộp, ✓ giả, chữ do LLM | B4, B6 |
| Graph nhỏ + `astream` | Thứ tự activity, contextvar, phanh | B5 |
| Contract (`validate_contract.py`, `test_assistant_contract.py`) | Khoá lạ, mã ngoài enum, `groupId` sai, lộ secret | B3–B6, B9 |
| Snapshot hành vi (baseline D3 của plan chung) và test orchestrator | Tách bộ lọc hoặc tiến trình làm đổi hành vi | B4–B6, B9 |
| Unit backend chẩn đoán | Lọc theo danh sách cho phép, dữ liệu lồng nhau, hai request đồng thời | B9 |
| Unit frontend `progressModel`, `widgetProgress`, `assistantState`, `assistantProvider` | Quy tắc cập nhật, hiển thị theo loại lượt, lộ thông tin kỹ thuật, đồng hồ | B2, B7, B8 |
| E2E Playwright với fixture stream | Luồng thật trong trình duyệt: preview 5 giây, thu gọn | B8 |
| Backend thật + LLM thật | Số khớp trace, thời gian thật, preview có ích không | D1, D6 (plan chung), B10a |

## 6. Invariant

- Mọi dữ kiện trong `progress` do code tính từ state, hoặc đếm tại chỗ lọc kết quả của **chính lượt đó**. LLM không viết
  chữ nào. Không suy ngược số đếm từ danh sách cuối.
- Mỗi sản phẩm nhận về rơi vào đúng một ô đếm; `chosen` là giao với response cuối.
- Mọi `productId` trong `run.preview` có trong `sources` và trong response cuối; trường lấy nguyên từ tool
  (NFR-REL-01).
- Response cuối, `message`, node path, state lưu, payload LLM và tham số tool không đổi. Snapshot xanh mà không ghi lại.
- Web không hiện `nodeId`, tên tool, `message` của sự kiện hay `query`, trừ trong chế độ chẩn đoán.
- `debug` chỉ có trong stream của request mang khoá hợp lệ, và chỉ gồm trường trong danh sách cho phép. Stream không bao
  giờ chứa prompt, output thô của LLM, JWT, header hay chuỗi tự do.
- Một bước chỉ được ✓ sau khi node tương ứng đã xong thật; bước chưa chắc sẽ chạy thì không hiện.
- Tầng `application` không import `agents`; nó chỉ nhận callback hoặc bộ đếm qua tham số.
- Không tạo lại luồng cũ hay cờ `ITINERARY_ORCHESTRATOR`.

## 7. Đề xuất PRD

- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md`: Phần A/C đã áp dụng ngày 13/10, Phần B chờ chốt; chia ba phần:
  - Phần A, trước demo: AC-AGT-09 mới; đoạn "Khung tiến trình" và chẩn đoán mức 1 trong `user-flow.md` §4.2; một ý trong
    "Tiêu chuẩn Grounding" của `architecture.md` §3.
  - Phần B, sau demo: chẩn đoán mức 2; một dòng biến bí mật trong `deployment-plan.md` §2.
  - Phần C, kết quả từng phần: chỉ xin chốt khi số đo D1 đạt tiêu chí ở 3.5. D1 đã đạt (9/9 lượt lập lịch có khoảng
    3,6–4,7 giây, `src/evaluation/reports/eval-2026-10-13-demo-orchestrator.md`).
- `docs/prd/update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`: orchestrator là mặc định, **đã chốt** ngày
  13/10/2026 và đã áp dụng. Plan này chỉ làm cho orchestrator nhờ đề xuất đó. Gỡ code cũ:
  `docs/prd/update-archive/2026-10-13-go-luong-cu-sau-demo.md`, **đã chốt** và đã áp dụng ngày 13/10/2026.

Plan này làm theo nội dung đề xuất sau khi được chốt. Nếu khi chốt nội dung đổi, sửa plan cho khớp trước khi làm B2.

## 8. Quyết định của người dùng, câu còn chờ, và rủi ro

Người dùng đã nói trực tiếp:
- 12/10: orchestrator là luồng chính; gỡ code chỉ luồng cũ dùng; cần plan trước; ưu tiên demo; preview chỉ giữ nếu đo
  thấy có ích.
- 13/10: dùng orchestrator làm mặc định; code cũ chưa xoá thì phải ghi rõ là không dùng. Chấp nhận các phương án Q1–Q6
  dưới đây như plan ghi.

| # | Câu hỏi | Quyết định |
|---|---|---|
| Q1 | Dòng tóm tắt khi xong đặt ở đâu? | Trên lời diễn giải và các thẻ (kể cả hàng thẻ khách sạn), nội dung như 3.6. Người dùng chốt 13/10 |
| Q2 | Thiếu ngân sách thì sao? | Hiện đúng hành vi hiện tại: không giới hạn theo giá; không tự đặt mức trung bình. Người dùng chốt 13/10 |
| Q3 | Bước xếp lịch nêu gì? | Chỉ tiêu chí `compose` thật sự áp dụng; không dùng `pace`. Người dùng chốt 13/10 |
| Q4 | Kết quả từng phần phát khi nào? | Sau `compose`, và chỉ làm nếu số đo D1 đạt tiêu chí ở 3.5. Người dùng chỉ đạo 12/10 và chốt 13/10; tiêu chí đo đi cùng Phần C, chờ chốt khi có số |
| Q5 | Ai nhận chi tiết kỹ thuật mức 2? | Chỉ request mang khoá, chỉ trường trong danh sách cho phép (3.8). Người dùng chốt 13/10; phần PRD nằm ở Phần B, chờ chốt |
| Q6 | Lượt khám phá có kết quả từng phần không? | Chưa, để giới hạn phạm vi. Người dùng chốt 13/10 |
| Q7 | Hội thoại mở lại từ lịch sử không hiện lại khung tiến trình hay dòng tóm tắt, vì tiến trình không lưu ở server. Bạn có chấp nhận giới hạn này không? | **Chờ chốt** cùng Phần A: giới hạn này nằm thẳng trong AC-AGT-09, nên chốt Phần A là đồng ý giới hạn. Lưu tiến trình ở server là đổi lưu trữ, cần đề xuất riêng nếu muốn |

**Rủi ro.**
- Tách điều kiện lọc của `_page`, `collect` để đếm có thể vô tình đổi kết quả lọc. Biện pháp: bộ lọc vẫn là "đạt mọi
  điều kiện"; test so kết quả lọc trước và sau khi tách; snapshot phải xanh mà không ghi lại.
- Một nhánh trong `fares.py` không đếm được đúng định nghĩa. Biện pháp: để trống số đó, không ước lượng (3.3); Web bỏ
  dòng khi thiếu số.
- Payload stream lớn hơn. Biện pháp: mọi mảng có `maxItems`; preview tối đa 6 thẻ.
- Đổi port `astream` làm vỡ route. Biện pháp: route là nơi gọi duy nhất (mục 1, ý 13); test contract stream chạy ở B5.
- Plan này chạy song song với D4, D5 của plan chung, là hai bước đổi hành vi có chủ ý. Biện pháp:
  - B4 chờ D4 xong.
  - Mỗi bước của plan này so snapshot với bản đang có trên nhánh.
  - Snapshot lệch mà không do D4, D5 thì dừng lại xem.
- Phần A chưa chốt sát ngày demo thì không kịp làm tiến trình. Biện pháp: B3, B7 nhỏ và làm trước được ngay sau chốt;
  báo người dùng nếu chốt muộn.
- Hai đề xuất đang chờ chốt chạm cùng file hoặc cùng mục PRD:
  - `docs/prd/update/2026-10-12-the-khach-san-chon-mot-cham.md` sửa `WidgetChat.tsx` và `WidgetStayOptions.tsx`.
  - `docs/prd/update/2026-10-12-lich-trinh-ban-do-man-hep.md` sửa `user-flow.md` §4.2.

  Không mâu thuẫn về nghĩa, nhưng việc nào vào sau thì phải rebase lên việc vào trước.
- Đề xuất `2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md` (chờ chốt) sẽ đổi số ứng viên điểm tham quan. Số đếm sẽ đổi
  theo, nhưng định nghĩa không đổi.
