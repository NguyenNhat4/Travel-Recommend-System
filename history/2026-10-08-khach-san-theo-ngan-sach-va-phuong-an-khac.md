# Chọn khách sạn theo ngân sách, luôn kèm phương án khác "thêm X ₫ → bớt Y km"

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs, evaluation
- Thay thế: history/2026-10-07-de-xuat-quy-doi-km-ra-tien.md, history/2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md
  (làm nốt phần dang dở: spec và report)

## Mục tiêu

Áp dụng đề xuất `docs/prd/update-archive/2026-10-08-khach-san-theo-ngan-sach-va-phuong-an-khac.md`. Nguyễn Minh Nhật chốt
ngày 2026-10-08. Mã: FR-AGT-03, NFR-REL-01, AC-AGT-04.

Góp ý của người dùng:
- trợ lý đưa ra lịch tối ưu nhất theo ngân sách, hoặc theo mặc định khi không có ngân sách;
- luôn kèm các phương án khác, kiểu "bỏ thêm bao nhiêu thì đỡ đi bao nhiêu km", vì người dùng thường cân nhắc nâng
  ngân sách.

Khi chốt, người dùng chọn thêm:
- "ưu tiên gần nhưng trong budget nếu có", không dùng đơn giá quy đổi km ra tiền;
- câu trả lời cuối có phân tích tăng X giảm Y;
- phương án khác chỉ hiện trong chat.

## File thay đổi

PRD và đề xuất:
- `docs/prd/update/2026-10-07-quy-doi-km-ra-tien.md` → `docs/prd/update-archive/2026-10-08-khach-san-theo-ngan-sach-va-phuong-an-khac.md`.
  File chưa từng commit, nên dùng `mv`. Nội dung viết lại theo góp ý; trạng thái `đã áp dụng`, có mục "Sửa khi áp dụng".
- `docs/prd/requirements.md` AC-AGT-04:
  - câu "Gần trước, rẻ sau…" thành "Gần trước, trong ngân sách nếu có…", kèm mục Phương án khác;
  - câu về số km sửa lại;
  - thêm trỏ tới đề xuất.

Code:
- `src/backend/app/domain/itinerary/routing.py`:
  - `optimize(..., budget_left)` trả `Planned(route, options)`;
  - khoá so theo ngân sách: lịch vừa đứng trước; không lịch nào vừa thì lịch rẻ nhất thắng;
  - `_options` lấy phương án khác từ các lịch không bị lịch nào hơn cả về tiền lẫn km;
  - thêm 3 khách sạn rẻ nhất vào danh sách đem ra so;
  - vòng thay điểm không biến một lịch đang vừa ngân sách thành vượt;
  - hằng số mới `CHEAP_STAYS`, `OPTION_MIN_KM`, `MAX_OPTIONS`, `OPTIONS_PER_SIDE`.
- `src/backend/app/domain/itinerary/planning.py`: `compose_plan(..., fixed_cost)` (tiền vé). Proposal thêm `distance_km`
  và `options`.
- `src/backend/app/domain/itinerary/types.py`: thêm `ProposedOption`, `Proposal.distance_km`, `Proposal.options`.
- `src/backend/app/agents/steps/composition.py`:
  - trừ tiền vé vào ngân sách;
  - câu tiêu chí có ngân sách;
  - warning `STAY_OPTIONS` (`_stay_options`, `_options_text`);
  - trả `stay_options` vào state.
- `src/backend/app/agents/steps/messages.py` (vi, en): thêm `plan_criteria_budget`, `section_options`, `options_total`,
  `option_closer`, `option_cheaper`, `option_over_budget`, `options_pick`, hàm `distance`.
- `src/backend/app/agents/steps/narration.py`: thêm `_options_block`, chèn sau mục tiêu chí ở cả bản LLM và bản dựng bằng
  luật; payload LLM có `options_shown_separately`.
- `src/backend/app/agents/steps/prompts.py`: thêm luật không viết lại mục Phương án khác.
- `src/backend/app/agents/steps/classification.py`: thêm `picked_option`; "phương án N" đặt `specific_hotel` = tên khách
  sạn đêm 1.
- `src/backend/app/agents/nodes.py`:
  - `_option_pick` trong `classify` (không gọi LLM);
  - `intake` reset `stay_options`, nạp `previous_options`;
  - `finalize` lưu `previous_options`.
- `src/backend/app/agents/state.py`: thêm `stay_options`, `previous_options`.

Test:
- `src/backend/tests/unit/domain/test_itinerary_routing.py`: thêm `BudgetTests` (6 test) và `OptionTests` (5 test).
- `src/backend/tests/unit/agents/test_composition_plan_criteria.py`: thêm `StayOptionsTests` (4 test).
- `src/backend/tests/unit/agents/test_narration.py`: thêm `StayOptionsTests` (3 test).
- `src/backend/tests/unit/agents/test_classify.py`: thêm `StayOptionPickTests` (6 test).

Spec:
- `docs/spec/agent/nghiep-vu/xep-lich.md`: viết lại mục Chỗ ở và mục "Tối ưu quãng đường". Mục này gồm hàm mục tiêu,
  chuỗi khách sạn, cách giải chính xác hoặc gần tối ưu, khoá chọn theo ngân sách, phương án khác và đổi khách sạn. Luồng
  chính và mục Code liên quan cũng sửa theo.
- `docs/spec/agent/nghiep-vu/glossary.md`: sửa "Chỗ ở"; thêm "Quãng đường của chuyến", "Đổi khách sạn", "Lịch vừa ngân
  sách", "Phương án khác".
- `docs/spec/agent/nghiep-vu/sua-lich-qua-nhieu-luot.md`: thêm `previous_options`, luật "chọn phương án khác", hai ⚠️.
- `docs/spec/agent/langgraph-nodes.md` §5, `docs/spec/agent/state-fields.md`: hai field mới.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7: nhiều khách sạn, ngân sách, `STAY_OPTIONS`.
- `docs/spec/hop-dong-tich-hop-frontend.md`: `stays`, `fromNight`, check-in từng khách sạn.

Đánh giá:
- `src/evaluation/agent/routing_bench.py` (mới): mô phỏng `compose_plan` trên Postgres, chỉ đọc.
- `src/evaluation/reports/eval-2026-10-08-toi-uu-quang-duong.md` (mới). Entry cũ ghi dự kiến tên
  `eval-2026-10-07-…`; tên thật theo ngày chạy.

History:
- File này.
- Dòng `Bị thay thế bởi` trong `history/2026-10-07-de-xuat-quy-doi-km-ra-tien.md` và
  `history/2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md`.

## Quyết định

- **Không có ngân sách thì giữ luật cũ** (gần trước, chênh dưới 2 km thì rẻ hơn), theo câu trả lời "ưu tiên gần". Vì
  vậy các test cũ không phải đổi kỳ vọng nào.
- **Ngân sách so với tiền lịch + tiền vé.** Vé như nhau giữa các lịch, nên trừ vé vào ngân sách trước. Vé chưa rõ giá
  thì dùng luật không ngân sách, vì không chứng minh được lịch nào vừa.
- **Phương án khác chỉ đổi khách sạn**, giữ nguyên các điểm của lịch đã chọn. Đổi khách sạn có thể kéo theo cách ghép
  ngày. Km để so và để hiện là km thật, không cộng phạt đổi khách sạn.
- **Chọn phương án bằng luật, không qua LLM.**
  - "phương án N" / "option N" (so không dấu) chỉ nhận N có trong `previous_options`.
  - Tên khách sạn lấy từ phương án đã hiện, ghi đè giá trị LLM trích (grounding).
  - Sau đó đi luồng `specific_hotel` sẵn có, không thêm field contract.
- **Mục Phương án khác do code dựng**, giống `PLAN_CRITERIA`. Số tiền, số km và tên khách sạn không qua LLM.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (117 schemas, 94 fixtures).
- `.venv/bin/python -m pytest -q src/backend/tests/unit src/backend/tests/architecture`: 1777 passed, 2 skipped.
- `.venv/bin/python -m pytest -q src/backend/tests`: 1884 passed, 35 skipped (274 s; integration Postgres bỏ qua vì không đặt `RUN_POSTGRES_INTEGRATION`).
- `DATABASE_URL=… .venv/bin/python -m src.evaluation.agent.routing_bench --samples 30 --seed 42`:
  - 100% mẫu vừa ngân sách;
  - 60–97% mẫu có phương án khác (Huế 0%, vì toạ độ tâm thành phố);
  - `compose_plan` p95 ≤ 63 ms.

  Bảng đầy đủ ở report.
- Frontend không đổi trong đợt này (contract không đổi), nên không chạy lại vitest/tsc.

## Còn lại / rủi ro

- **Chưa chạy agent end-to-end với LLM thật**, vì cần khoá OpenAI. Cần thử "Phú Quốc 5 ngày, 2 người lớn, ngân sách 10
  triệu", rồi "lấy phương án 1".
- **Chọn phương án hai khách sạn chỉ giữ khách sạn đêm 1.** Lịch dựng lại chạy Search lại, nên km và tiền có thể lệch
  chút so với dòng đã hiện. Đã ghi ⚠️ trong `sua-lich-qua-nhieu-luot.md`.
- **Km là đường chim bay.** OSRM là việc sau.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.2: ví dụ response chưa có `stays`. Mock
  `createItinerary.200-completed-two-stays.json` đã có ví dụ này.
- Artifact "Bàn thử xếp lịch" chưa cập nhật theo thuật toán mới.
