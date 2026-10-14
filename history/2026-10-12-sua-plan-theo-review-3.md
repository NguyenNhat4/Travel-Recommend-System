# Sửa plan gỡ luồng cũ và plan tiến trình theo review lần 3

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs (plan, đề xuất PRD cho agent)
- Bị thay thế bởi: `2026-10-13-chot-orchestrator-mac-dinh.md` (một phần: R1–R3, Q1–Q6 nay người dùng đã chốt)
- Thay thế (một phần): `2026-10-12-sua-plan-theo-review-2.md`, phần ghi R1, R2, R3, Q1, Q5 là "người dùng đã chốt";
  `2026-10-12-sua-plan-tien-trinh-theo-review.md`, phần ghi Q2, Q3, Q4, Q6 là "người dùng đã chốt" trong plan.

## Mục tiêu

Sửa 3 điểm của review lần 3, rồi chạy G0 của plan gỡ luồng cũ để biết khối lượng thật.

## File thay đổi

- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa:
  - G1 thêm mã nguyên nhân `TIME_LIMIT`, `ROUND_LIMIT`, `TOOL_LIMIT`, `MODEL_TIMEOUT`, `MODEL_ERROR`, `TOOL_TIMEOUT` cho
    mọi chỗ ra câu dự phòng, và hàm `record.unreplayable` chỉ loại mã phụ thuộc thời gian; mỗi nguyên nhân một test.
  - G0 đổi thành "kiểm kê và bổ sung test, không sửa hành vi runtime"; test của ý AC "không đạt" mang
    `xfail(strict=True)`; tách bằng chứng code quyết và LLM quyết.
  - G1 ghi rõ là refactor runtime, cần đọc tài liệu và xác nhận §1.3 trước khi code.
  - R1, R2, R3 đổi thành đề xuất chờ người dùng chốt.
- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: Q1–Q6 đổi thành phương án reviewer đề xuất, chờ người
  dùng chốt; giữ quyết định người dùng nói trực tiếp (orchestrator là luồng chính, gỡ luồng cũ, cần plan trước).
- `docs/prd/update/2026-10-12-orchestrator-thanh-luong-chinh.md` — sửa: câu thay thế trong PRD dùng `<ngày chốt>` thay
  cho ngày cố định.
- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — không đổi ở lượt này.
- `history/2026-10-12-sua-plan-theo-review-2.md` — sửa: thêm dòng "Bị thay thế bởi".
- `history/2026-10-12-sua-plan-tien-trinh-theo-review.md` — sửa: thêm dòng "Bị thay thế bởi".
- `history/2026-10-12-sua-plan-theo-review-3.md` — thêm: entry này.

## Quyết định

- Điểm 1 (P1): đúng với code, và mình đã nhận xét sai ở lượt trước khi coi đây chỉ là lỗi thứ tự bước.
  - `run_jobs_node` ghi `execution budget exhausted` cho cả trần vòng (`MAX_ROUNDS = 3`), trần tool
    (`MAX_TOOL_CALLS = 10`) và hết thời gian (`orchestration.py:146–151`).
  - `orchestrate_node` bắt mọi lỗi model, kể cả `TimeoutError`, thành `model unavailable, fallback` (`:134–140`).
  - `BudgetTools._call` ném `JOB_BUDGET_EXHAUSTED` cho cả trần tool lẫn hết hạn (`jobs.py:31–38`).

  Cách sửa: mỗi chỗ gắn đúng một mã nguyên nhân vào metadata; không đổi `message`, node path hay mã lỗi trả ra ngoài.
  Snapshot chỉ so `node` và `message` của event, nên không lệch. Danh sách 18 chỗ `wait_for`/`TimeoutError` lấy bằng grep
  `agents/` và `application/itinerary/`.
- Điểm 2 (P2): đúng. Dùng `xfail(strict=True)` cho test tái hiện ý AC "không đạt", để bộ test vẫn xanh và có danh sách
  chính xác; G3 làm xong thì `strict` buộc gỡ dấu. Thêm: ý AC do LLM quyết thì unit test với LLM ghi sẵn không đủ làm bằng
  chứng, phải chạy golden với LLM thật.
- Điểm 3: đúng. R1–R3 và Q1–Q6 là phương án reviewer đề xuất (nằm trong bài review được dán vào), không phải lời chốt của
  người dùng. Đã sửa trong cả hai plan. Chỉ giữ là quyết định người dùng: những gì người dùng nhắn trực tiếp (orchestrator
  là luồng chính, gỡ code chỉ luồng cũ dùng, cần plan trước).

## Kiểm tra

- Đọc code: `agents/steps/orchestration.py:116–216`, `agents/steps/jobs.py:25–52`; grep `wait_for|TimeoutError`.
- Chưa sửa source.

## Còn lại / rủi ro

- Người dùng chốt R1–R3, Q1–Q7 và hai đề xuất.
- G0: xem entry riêng của G0.
