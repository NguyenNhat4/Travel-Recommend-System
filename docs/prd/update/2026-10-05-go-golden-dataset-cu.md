# Gỡ bộ golden cũ, giữ bộ test case người dùng tái hiện làm benchmark của Itinerary Agent

- Ngày: 2026-10-05
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/test-plan.md` §2.4
- Mã FR/NFR: FR-AGT-01..05, NFR-REL-01, NFR-SEC-01

## Lý do

Người dùng yêu cầu xoá `src/evaluation/datasets/itinerary_agent_golden.yaml` (bộ case `G-NNN`) và mọi thứ liên quan, vì đây là bộ cũ; bộ đang dùng là `src/evaluation/datasets/agent_test_cases_nhat.yaml` (TC-NN). Entry `history/2026-10-02-chay-tu-dong-test-case-nguoi-dung-va-llm-giam-khao.md` từng quyết định giữ bộ cũ vì `test-plan.md` §2.4 ghi benchmark là "Tập 50 câu prompt"; bộ TC hiện chỉ có 4 case. Gỡ bộ cũ nghĩa là hệ thống không còn bộ nào đạt mô tả đó, nên cần chốt lại PRD.

## Nội dung đề xuất

`docs/prd/test-plan.md` §2.4, mục "Bộ dữ liệu kiểm thử":

- Hiện tại: "Tập 50 câu prompt đa dạng: từ yêu cầu rõ ràng đến các câu hỏi mơ hồ, câu hỏi có điều kiện ngân sách ngặt nghèo, hoặc các yêu cầu cố tình bẫy địa danh không có trong catalog."
- Đề xuất: "Tập test case do người dùng tái hiện lỗi thật của agent (`src/evaluation/datasets/agent_test_cases_nhat.yaml`), mở rộng dần mỗi khi có lỗi mới; mỗi case có kiểm tra tất định và, khi cần, tiêu chí cho LLM giám khảo. Không đặt số lượng cố định."

Ba chỉ số (Tool Calling Accuracy, Grounding Rate, Structured Output Integrity) giữ nguyên.

Phương án khác nếu không muốn bỏ con số 50: khôi phục file `itinerary_agent_golden.yaml` từ git (commit trước thay đổi này) và đưa nó về làm bộ hồi quy chạy bằng `--dataset`.

## Thay đổi source sau khi chốt

Đã làm sẵn trong working tree theo yêu cầu của người dùng, chưa commit; nếu bị từ chối thì hoàn tác bằng `git checkout`:

- Xoá `src/evaluation/datasets/itinerary_agent_golden.yaml`, `src/evaluation/reports/eval-2026-09-23-golden.md`, `eval-2026-09-24-golden.md`, `docs/plan/2026-09-23-golden-dataset-handoff.md`.
- Sửa `src/evaluation/agent/golden.py`, `src/evaluation/tests/test_golden.py`, `src/backend/tests/unit/agents/test_guardrails.py`, `docs/spec/agent/{golden-run,golden-dataset-how-to-add-more-case,README,langgraph-nodes}.md`, `.agents/skills/building-itinerary-agent/references/eval-loop.md`.
