# Giao diện chạy bộ test case của Itinerary Agent

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng cần một giao diện để chạy evaluation thay cho CLI. Yêu cầu:

- thấy test đang tới đâu;
- thấy case nào fail và vì sao, case nào pass;
- chạy case tự chọn hoặc cả bộ;
- thêm case mới bằng form có hướng dẫn rõ từng trường;
- chạy lại sau khi tune để chắc case cũ vẫn đạt.

Phục vụ `docs/prd/test-plan.md` §2.4, FR-AGT-01..05 và NFR-REL-01. Đây là công cụ trong `src/evaluation/`, không đổi hành vi agent, contract hay DDL, nên không lệch PRD.

## File thay đổi

- `src/evaluation/agent/eval_app.py` — thêm: app Streamlit riêng, gồm sidebar và bốn tab.
  - Sidebar: trạng thái backend, tuỳ chọn chạy, tiến độ của lần đang chạy.
  - Tab Chạy: chọn case, chạy, dừng, xem từng lượt cùng finding tất định và finding giám khảo.
  - Tab Lịch sử & so sánh: ma trận case × lần chạy, đánh dấu hồi quy hoặc đã sửa.
  - Tab Thêm case: form, xem trước YAML, kiểm tra, lưu, chạy thử.
  - Tab Hướng dẫn: bảng các khoá `expect`.
- `src/evaluation/agent/eval_runs.py` — thêm: mở tiến trình con runner, dừng, đọc `progress.jsonl` thành trạng thái từng case, `compare_runs`, `latest_results`.
- `src/evaluation/agent/case_builder.py` — thêm:
  - `FIELD_HELP` cho mọi khoá `expect`;
  - danh sách giá trị hợp lệ lấy từ contract và graph;
  - `case_to_yaml`, `validate_block`, `append_case` (chỉ nối vào cuối file), `dataset_raw_case`.
- `src/evaluation/agent/golden.py` — sửa:
  - `run_case(on_event=, repetition=)` phát event `turn_start`, `turn_done`, `case_done`;
  - cờ `--progress-file` (JSONL, thêm event `start`, `sweep_start`, `done`, `failed`) và `--report-dir`.
  - Không cờ mới thì CLI chạy như cũ.
- `src/evaluation/tests/test_golden.py` — sửa: test event tiến độ (thứ tự, timeout bỏ lượt sau) và `progress_writer`.
- `src/evaluation/tests/test_case_builder.py`, `test_eval_runs.py`, `test_eval_app.py` — thêm: test builder/validate/append, đọc tiến độ/trạng thái/so sánh, tiến trình con thật bị dừng, AppTest (backend tắt, run fail, lưu case, nạp mẫu 5 case).
- `Makefile` — sửa: target `agent-eval` (dùng lại backend đang chạy hoặc bật như `chat`, rồi mở app ở `:8503`).
- `.gitignore` — sửa: bỏ qua `.logs/` (thư mục lần chạy `.logs/agent-eval/`).
- `docs/spec/agent/golden-run.md` — sửa: mục 2.1 "Chạy bằng giao diện", thêm hai cờ mới vào bảng, test cần chạy khi sửa giao diện.
- `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — sửa:
  - mục 7 thêm cách thêm case bằng form;
  - mục 4 sửa giá trị `missingFieldsInclude` (thiếu `startDate`, `party`, `budget`), thêm node `narrate` và tên tool;
  - mục 9: thêm khoá mới thì phải thêm hướng dẫn và widget.
- `docs/spec/agent/working-context.md` — sửa: hàng "Eval hành vi Agent" trỏ tới `golden.py`, `eval_app.py`.
- `src/evaluation/agent/README.md` — sửa: dòng chỉ tới `make agent-eval`.

## Quyết định

- **App riêng, không gộp vào demo chat.** Người dùng chọn phương án này.
- **App không tự chấm.** Mỗi lần chạy là tiến trình `python -m src.evaluation.agent.golden`, nên CLI vẫn là nguồn sự thật duy nhất cho luật chấm. Tiến độ đi qua file JSONL, nên tải lại trang không mất lần chạy. Mỗi lúc chỉ cho chạy một lần, để hai lần không tranh backend và LLM.
- **Chạy từ giao diện mặc định ghi biên bản vào thư mục lần chạy.** Lý do: `--only` sẽ ghi đè biên bản chính thức `eval-<ngày>-agent-test-cases.md` đã commit. Muốn biên bản chính thức thì tick "Ghi biên bản chính thức" rồi bấm Chạy tất cả.
- **Thư mục lần chạy là `.logs/agent-eval/`** (gitignored), không đặt trong `src/evaluation/reports/`, vì đây là kết quả tạm khi tune. `meta.json` ghi commit và cờ `dirty`, vì tune thường chạy trên working tree chưa commit.
- **Thêm case chỉ nối vào cuối file**, không ghi lại cả file: comment lỗi gốc của các case cũ giữ nguyên. Sửa hoặc xoá case cũ vẫn làm trong YAML.
- **Kiểm tra trước khi lưu dùng đúng `load_dataset` của runner** cộng các kiểm của `test_golden.py`. Id từng có trong lịch sử git của dataset thì chỉ cảnh báo, không chặn.
- **Giá trị trên form lấy từ nguồn sự thật**, không gõ tay:
  - `missingFields`, `errorCode`, `PartyType`, `Pace` lấy từ contract;
  - tên node lấy từ `build_graph().get_graph()`;
  - tên tool lấy từ `tool_contracts.OPERATIONS`;
  - mã FR lấy từ `requirements.md`.
  - Riêng mã warning không có enum trong contract, nên là danh sách gợi ý và vẫn gõ được mã khác.
- Test ép `FIELD_HELP` phủ đủ `EXPECT_KEYS`: thêm khoá mới vào runner thì buộc phải viết hướng dẫn.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py src/evaluation/tests/test_case_builder.py src/evaluation/tests/test_eval_runs.py src/evaluation/tests/test_eval_app.py src/backend/tests/unit/agents/test_guardrails.py`: 117 passed.
- Lỗi tìm được khi kiểm tay rồi sửa: "Nạp mẫu" làm mất khối `intent` (ô tick nhóm Ý định chưa được bật). Thêm test nạp mẫu cả 5 case, so YAML sinh ra với case gốc.
- `make agent-eval` thật trên máy local:
  - backend `inprocess`, LLM live, 3183 sản phẩm; app trả HTTP 200 ở `:8503`;
  - chạy TC-02 qua `eval_runs.start_run` (cùng đường với nút trong app): tiến độ 0/2 → 1/2 → 2/2, TC-02 PASS 2/2, latency 9,4 s và 6,0 s, Structured Output 1.0, Tool Calling 1.0;
  - biên bản nằm trong thư mục lần chạy; `src/evaluation/reports/` không đổi;
  - AppTest trên dữ liệu thật đó hiện đúng expander, metric và trạng thái backend.
- Chưa bấm thử trên trình duyệt; tương tác chỉ kiểm qua AppTest.

## Còn lại / rủi ro

- Phát hiện tiến trình còn sống dựa vào `/proc` khi app khởi động lại (Linux). Trên macOS không có `/proc`, nhánh đó coi pid còn trả lời `os.kill(pid, 0)` là còn sống.
- Tab Lịch sử gộp case `SWEEP-*` như case thường; chạy sweep nhiều lần thì ma trận dài.
- Không có nút sửa hoặc xoá case cũ trên giao diện (có chủ đích).
