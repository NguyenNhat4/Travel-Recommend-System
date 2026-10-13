# Refactor Itinerary Agent giữ nguyên hành vi

- Ngày: 2026-10-11
- Người yêu cầu / thực hiện: Nguyễn Minh Nhật / Claude Code
- Phục vụ: FR-AGT-01..07, NFR-REL-01 (`docs/prd/requirements.md`). Chỉ đổi cấu trúc code trong `src/backend/app/agents`;
  graph giữ nguyên 15 node, contract và prompt không đổi, nên không lệch PRD.

## Mục tiêu

Code agent dễ đọc và dễ sửa hơn **mà người dùng không thấy khác gì**. Đánh giá kiến trúc ngày 11/10 chỉ ra bốn điểm nợ:

1. Quyết định rẽ nhánh nằm rải trong `steps/classification.py` (642 dòng). Việc "đã đồng ý lập lịch chưa" được xét ở cả
   `classify` (`plan_consented`) lẫn `extract` (`extract_result`, `planning_implied`).
2. Khoảng 76 field state phẳng. Các cờ hội thoại (`pending_offer`, `pending_fare`, `open_question`, `explore_pick`…) tự
   dọn ở nhiều chỗ (`_fare_settled`…). Cờ cũ không bị dọn đúng lúc là kiểu lỗi hay gặp ở chat thử.
3. `steps/exploration.py` (936 dòng) chứa cả khám phá lẫn nhánh tư vấn vé. *(Đánh giá này sai: nhánh vé đã nằm riêng ở
   `steps/fares.py`; `explore` chỉ có 5 dòng chuyển sang đó.)*
4. Mỗi node có bản sync và async gần giống nhau trong `nodes.py`.

## Nguyên tắc

- **Không đổi hành vi.** Response, đường đi qua node, state được lưu và **payload gửi LLM** phải giống từng byte trước và
  sau mỗi bước.
- **Không sửa kỳ vọng của test sẵn có.** Test phải sửa kỳ vọng nghĩa là hành vi đổi: dừng lại, xem lý do. Chỉ được sửa
  đường import.
- **Mỗi bước phải xanh trước khi sang bước sau.** Không commit khi người dùng chưa yêu cầu.
- **Hội thoại đã lưu trước khi deploy vẫn đọc được.** Đổi hình dạng state lưu trong Redis/Postgres thì phải có hàm đọc dạng
  cũ, kèm test.
- **Không gộp việc đổi hành vi.** Thay regex bằng LLM (`_DELEGATE`, `_REJECT`, `exploration.py`) là việc riêng, có đánh giá
  trước và sau.

## Lưới an toàn (bước 0)

| Lớp | Nội dung |
|---|---|
| Unit test sẵn có | 581 test agent (`tests/unit/agents`), LLM giả bằng `ScriptedLlm`, chạy khoảng 9 giây |
| Snapshot hành vi | Mới. Chạy các hội thoại thật qua graph runtime. Tool (Search, Recommendation, Similar, Catalog) và LLM được ghi một lần từ chế độ `inprocess` trên dữ liệu thật và LLM thật, **trên code trước refactor**, rồi phát lại. "Hôm nay" cố định 2026-10-11, uuid tất định. So response, node path, state lưu, lời gọi LLM và tool với snapshot đã ghi |
| LLM thật | `chat_replay`, golden: chạy một lần ở cuối, đọc bằng mắt |

Cassette LLM khoá theo hash của schema và toàn bộ payload gửi LLM; cassette tool khoá theo tên tool và tham số. Đầu vào đổi
thì không tìm thấy bản ghi và test fail, nên lưới bắt được cả việc vô tình đổi đầu vào LLM hoặc tool. Phát lại không cần
DB hay mạng, nên không lệch khi catalog được nạp lại và chạy được trong CI.

Kịch bản lấy từ `chat_messy_v1`, `chat_review_v1`, `agent_scenarios_v5`, `agent_test_cases_nhat`, rồi thêm 14 kịch bản cho
lịch có vé và khách sạn, chọn phương án, đổi chuyến bay, hỏi vé, guardrail, form, ngày ngoài cửa sổ, ngoài catalog. Kịch bản được chép vào thư mục
snapshot để dataset eval đổi không làm hỏng lưới.

## Các bước

| # | Việc | Kiểm |
|---|---|---|
| 0 | Dựng lưới snapshot: harness, cassette ghi bằng LLM thật, snapshot, test phát lại; chạy hai lần với `PYTHONHASHSEED` khác nhau để chắc lưới tất định | Test snapshot xanh trên code hiện tại |
| 1 | Gom quyết định đồng ý lập lịch về một module (`steps/consent.py`), `classify` và `extract` cùng gọi | 581 test + snapshot |
| 2 | Gom cờ hội thoại: một chỗ khai báo cờ nào sống qua lượt nào, một hàm dọn chung thay cho dọn rải rác; hình dạng state lưu giữ nguyên | 581 test + snapshot + test đọc state cũ |
| 3 | Tách nhánh tư vấn vé khỏi `steps/exploration.py`; vẫn là nhánh của node `explore` (node riêng đã bị từ chối 11/10) | 581 test + snapshot |
| 4 | Bỏ bản sync của node, nếu runtime và test không còn dùng; còn dùng thì bỏ qua bước này | 581 test + snapshot + cả bộ backend |
| 5 | Cập nhật `langgraph-nodes.md`, `state-fields.md`, `nghiep-vu/` (mục "Code liên quan"), entry `history/` | Link hợp lệ |

Sau bước 5: chạy cả bộ test backend, `chat_replay` với LLM thật, rồi ghi kết quả vào history.

## Kết quả (2026-10-11)

| # | Trạng thái | Ghi chú |
|---|---|---|
| 0 | Xong | Ghi trên worktree tạm ở HEAD `95438116` (code trước refactor) với `inprocess` + LLM thật: 57 kịch bản, 166 lượt, 365 bản ghi LLM, 199 bản ghi tool, không lượt nào 5xx hay timeout. Phát lại trên code gốc và trên code đã refactor: xanh với 3 giá trị `PYTHONHASHSEED`. Thử gây lỗi: thêm một dấu cách vào prompt planner làm 15/57 kịch bản lệch. Bỏ luật "ok" sau lời mời: 0 kịch bản lệch, vì ở các câu đó LLM cũng báo `plan_request` nên hành vi không đổi |
| 1 | Xong | `steps/consent.py`. `classification` giữ tên cũ (import lại) cho test và code khác |
| 2 | Xong | `steps/phase.py`: `CARRIED`, `TURN_ONLY`, `carried`, `turn_defaults`, `settled`. Hình dạng state lưu không đổi. Thêm `test_phase.py` cho bản ghi dạng cũ |
| 3 | Bỏ qua | Test gọi trực tiếp khoảng 15 hàm private của `exploration.py` (`_fill`, `_card_input`…). Tách file thì phải giữ lớp re-export hoặc sửa test; lợi ích không đáng |
| 4 | Bỏ qua | 116 chỗ trong test gọi bản sync của node; `intake_node` sync còn là phần của bản async |
| 5 | Xong | `langgraph-nodes.md`, `state-fields.md`, `working-context.md` §5A, `nghiep-vu/tro-chuyen-va-kham-pha.md` |

Không chạy `chat_replay` với LLM thật: snapshot đã chứng minh payload gửi LLM giống từng byte, nên lần chạy LLM thật không
cho thêm thông tin nào về việc refactor có đổi hành vi hay không.

Snapshot chưa phủ: `retry`, `dead_letter`, `NO_RESULTS`, `FALLBACK` (dữ liệu và kịch bản hiện có không dẫn tới các nhánh
này). Các nhánh đó dựa vào unit test. `apply_option` có 2 lượt.

Dung lượng: `tools.json.gz` khoảng 4,7 MB (kết quả Search 50 sản phẩm mỗi lời gọi, sản phẩm trùng chỉ lưu một lần),
`snapshot.json` khoảng 2,4 MB, `cassette.json` khoảng 300 KB. Mỗi lần ghi lại toàn bộ thêm chừng đó vào lịch sử git.

## Ngoài phạm vi

- Thay regex bằng LLM, giảm độ trễ, Redis chịu lỗi, giá vé mô phỏng: việc riêng (đánh giá ngày 11/10).
- Đổi topology graph, prompt, contract.

## Rủi ro

- Snapshot chỉ phủ những nhánh có trong kịch bản; nhánh không có kịch bản dựa vào 581 unit test.
- Cassette cần ghi lại khi chủ ý đổi prompt hoặc hành vi: `record` trong harness, cần Postgres và Weaviate local đã nạp
  catalog. Engine `inprocess` lọc theo ngày thật, nên ghi lại vào ngày khác thì phải đổi `FROZEN_TODAY` và ngày trong
  `scenarios.json` cho khớp.
