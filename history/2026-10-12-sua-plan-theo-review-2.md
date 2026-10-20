# Sửa plan gỡ luồng cũ và plan tiến trình theo review lần 2

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs (plan, đề xuất PRD cho agent)
- Bị thay thế bởi: `2026-10-12-sua-plan-theo-review-3.md` (một phần: trạng thái chốt của các câu hỏi)

## Mục tiêu

Sửa 5 điểm của review lần 2 cho hai plan và hai đề xuất. Ghi lại các quyết định người dùng đã chốt trong review: R1, R2,
R3, Q1, Q5. Q7 chờ người dùng xác nhận rõ.

## File thay đổi

- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa: viết lại thành hai giai đoạn. Giai đoạn đổi hành vi
  (G2 bật mặc định và chuyển cạnh cũ; G3 làm ý AC còn thiếu; G4 ghi snapshot, phát lại offline, duyệt baseline). Giai
  đoạn gỡ (G5 chuyển, G6 xoá cùng test) không đổi hành vi. Thêm G1 cho snapshot kiểm soát thời gian; bảng AC ba trạng
  thái ở G0; phanh `plan` lặp; G7 tổng kiểm.
- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: quy tắc cập nhật `notices` theo khoá, thay bằng số cộng
  dồn, ẩn theo nhóm `superseded`; schema `AssistantProgressNotice`; fixture 2 → 5 và `stream-fare-superseded.json`; test
  tương ứng; tham chiếu G0–G7; Q1, Q5 đã chốt, Q7 chờ xác nhận.
- `docs/prd/update/2026-10-12-orchestrator-thanh-luong-chinh.md` — sửa: không bỏ AC nào; ý AC chỉ luồng cũ đáp ứng phải
  làm trên orchestrator trước khi xoá; tạm bỏ phải có đề xuất riêng; bỏ đo so sánh hai kiến trúc nhưng giữ kiểm AC và
  hồi quy bắt buộc.
- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: AC-AGT-09 và `user-flow.md` §4.2 ghi rõ dòng tóm
  tắt nằm trên lời diễn giải và thẻ, và hội thoại mở lại từ lịch sử không hiện lại khung tiến trình (giới hạn Q7).
- `history/2026-10-12-sua-plan-theo-review-2.md` — thêm: entry này.

## Quyết định

- Điểm 1 (R3): đúng. Đề xuất ghi "không đổi FR/NFR" mà plan lại cho gỡ dù mất AC, hai điều này mâu thuẫn. Sửa: G0 lập
  bảng AC ba trạng thái (đạt / chưa có test / không đạt); ý "chưa có test" phải viết test để biết đạt hay không; ý "không
  đạt" làm ở G3 trước khi xoá.
- Điểm 2: đúng. Chuyển `extract → explore/simple` sang `orchestrate` là đổi hành vi, nên đưa vào G2, trước khi ghi
  baseline. Thêm phanh: mỗi lượt đi `plan` → `extract` tối đa một lần, lần hai thì buộc trả lời; có test LLM luôn trả
  `plan`.
- Điểm 3: đúng với code. Orchestrator đo ngân sách bằng `time()` (`nodes.py:89`, `orchestration.py:125, 129, 149, 211`,
  `jobs.py:32, 384`) và chờ model `min(timeout, remaining)`. Harness chỉ cố định `datetime` và uuid, không bật
  orchestrator, không bọc model riêng của nó. `record.py` dùng lại cassette cũ nếu không có `--fresh`. Sửa: G1 thêm
  `agents/clock.py` để tiêm đồng hồ; snapshot dùng đồng hồ ảo cùng ngân sách và timeout lớn; khoá cassette có tên model;
  `record.py` từ chối bản ghi có event hết giờ; test hết giờ tách riêng. G4 ghi bằng `--fresh` và phải phát lại offline
  xanh trước khi đưa người dùng duyệt.
- Điểm 4: đúng. Test đi cùng ký hiệu trong cùng bước (G5 chuyển, G6 xoá); G7 chỉ tổng kiểm. Thay `compileall` bằng import
  thật `src.backend.app.main` và `pytest --collect-only`.
- Tự soát thêm: G1 chỉ cho harness **khả năng** dựng orchestrator; harness vẫn theo cờ, nên snapshot cũ còn xanh. Khoá
  cassette cũ đọc tương thích. Từ G2 tới G4, `test_behavior_snapshot.py` đỏ có chủ ý; G2–G4 vào cùng một commit.
- Điểm 5: đúng. `notices` cập nhật theo khoá `(code, groupId, date)`, bản mới thay bản cũ, `count` là số cộng dồn do
  backend tính; nhóm `superseded` ẩn thông báo của nó.

## Kiểm tra

- Chưa sửa source, chưa chạy test.
- Đọc code: `tests/unit/agents/behavior_snapshot/harness.py` (`frozen_world`, `CassetteLlm`, `run_scenario`),
  `record.py`, `agents/steps/orchestration.py` (`orchestrate_node`, `run_jobs_node`, `gatekeep_node`),
  `agents/steps/jobs.py` (`BudgetTools`, `execute`), `agents/nodes.py:89`.

## Còn lại / rủi ro

- Chờ người dùng xác nhận Q7 và chốt hai đề xuất.
- G0, G1 (plan gỡ) và B0 (plan tiến trình) làm được ngay, không đổi hành vi.
- G3 có thể lớn nếu job khám phá của orchestrator chưa làm đủ các luật khám phá của luồng cũ; G0 sẽ cho biết trước khi
  chốt.
- Chưa commit.
