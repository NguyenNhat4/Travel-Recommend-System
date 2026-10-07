# Gỡ bộ golden cũ (G-NNN) của Itinerary Agent

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: evaluation, agent, docs

## Mục tiêu

Người dùng yêu cầu xoá `itinerary_agent_golden.yaml` và mọi thứ liên quan vì là bộ cũ; bộ đang dùng là `agent_test_cases_nhat.yaml` (TC-NN).

## File thay đổi

- `src/evaluation/datasets/itinerary_agent_golden.yaml` — xóa: bộ golden 79 case.
- `src/evaluation/reports/eval-2026-09-23-golden.md`, `eval-2026-09-24-golden.md` — xóa: biên bản chạy bộ cũ (hai file `.json` gitignored cùng tên cũng xoá khỏi máy).
- `docs/plan/2026-09-23-golden-dataset-handoff.md` — xóa: bàn giao riêng cho bộ cũ.
- `src/evaluation/agent/golden.py` — sửa: bỏ `FULL_GOLDEN_DATASET`, bỏ slug `golden`, ví dụ dùng TC-NN.
- `src/evaluation/tests/test_golden.py` — sửa: test dataset chạy trên `agent_test_cases_nhat.yaml`; bỏ test khoá bố cục 14 case, test lượt hỏi ngày, test G-076.
- `src/backend/tests/unit/agents/test_guardrails.py` — sửa: test "không câu nào bị tầng 1 chặn nhầm" đọc `agent_test_cases_nhat.yaml` (đổi tên class/test).
- `docs/spec/agent/golden-run.md`, `golden-dataset-how-to-add-more-case.md`, `README.md`, `langgraph-nodes.md`, `presentation-slides.html` — sửa: bỏ mô tả, bảng category và id G-NNN; dẫn sang bộ TC.
- `.agents/skills/building-itinerary-agent/references/eval-loop.md` — sửa: chỉ còn một dataset, id `TC-NN`.
- `docs/plan/2026-09-28-summary-search-recsys-benchmark.md`, `docs/spec/agent/presentation-script.md` — sửa: con trỏ tới biên bản 24/09 đã xoá.
- `docs/prd/update/2026-10-02-hoi-tiep-khi-cau-hoi-bi-cat-ngang.md` — sửa: đường dẫn golden case sang `agent_test_cases_nhat.yaml`.
- `docs/prd/update/2026-10-05-go-golden-dataset-cu.md` — thêm: đề xuất sửa `test-plan.md` §2.4 (chờ chốt).

## Quyết định

- Entry `history/2026-10-02-chay-tu-dong-test-case-nguoi-dung-va-llm-giam-khao.md` từng giữ bộ cũ vì `docs/prd/test-plan.md` §2.4 ghi benchmark 50 câu. Gỡ bộ cũ lệch PRD này, nên tạo đề xuất và chưa commit; thay đổi nằm trong working tree.
- Giữ tên file `golden-dataset-how-to-add-more-case.md` để không gãy link; chỉ sửa nội dung cho bộ TC.
- Không sửa `history/` và `docs/prd/update-archive/`.

## Kiểm tra

- `.venv/bin/python -m pytest src/evaluation/tests/test_golden.py src/backend/tests/unit/agents/test_guardrails.py -q`: 85 passed.
- Chưa chạy runner với LLM thật.

## Còn lại / rủi ro

- Chờ người dùng chốt `docs/prd/update/2026-10-05-go-golden-dataset-cu.md`; nếu từ chối thì khôi phục bằng `git checkout HEAD -- <file đã xoá>`.
- Slide 11–12 và kịch bản nói vẫn trình bày số liệu và id G-NNN của lần chạy 24/09 như tư liệu lịch sử; muốn bỏ hẳn thì phải dựng lại hai slide đó.
