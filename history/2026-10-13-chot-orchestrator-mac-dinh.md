# Người dùng chốt orchestrator làm mặc định; áp dụng vào PRD; ghi chú luồng cũ đóng băng

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs (PRD, đề xuất, spec agent, quy tắc agent)
- Thay thế: `2026-10-12-sua-plan-theo-review-3.md` (phần ghi R1–R3, Q1–Q6 là "chờ người dùng chốt")

## Mục tiêu

Người dùng nhắn "chốt làm đi". Khi được hỏi phạm vi chốt, người dùng trả lời:
- "dùng orchestrator làm mặc định, code cũ nếu chưa xoá thì cần làm rõ không dùng".
- Chấp nhận tất cả phương án reviewer: R1–R3, Q1–Q6.

Sau đó người dùng nhắn "hoàn thiện plan xong và tự làm".

## File thay đổi

- `docs/prd/architecture.md` §3 — sửa: câu "Cờ mặc định tắt; chỉ chuyển sau bộ đo đạt ngưỡng" thay bằng đúng đoạn đã
  chốt:
  - Orchestrator là mặc định.
  - Luồng cũ chỉ còn để quay về khi sự cố, không dùng, không sửa, ghi rõ là không dùng tới khi gỡ.
  - Bỏ đo so sánh hai kiến trúc.
  - Kiểm tra bắt buộc gồm kịch bản demo, AC và snapshot phát lại offline.
- `docs/prd/deployment-plan.md` §2 — sửa: dòng `ITINERARY_ORCHESTRATOR` thành `on` mặc định, `off` chỉ để quay về.
- `docs/prd/requirements.md` §3 — sửa: câu "hành vi mới sau cờ mặc định tắt tới khi đạt ngưỡng" trong AC-AGT-06 đổi thành
  "hành vi này là của orchestrator, luồng mặc định từ 2026-10-13". Câu cũ trái với quyết định vừa chốt; thấy khi đọc PRD
  để áp dụng, nên ghi thêm vào đề xuất (mục 3) và báo người dùng.
- `docs/prd/update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md` — đổi chỗ từ `docs/prd/update/` (file chưa
  được git theo dõi, nên dùng `mv`) và sửa: chỉ còn phần mặc định, trạng thái `đã áp dụng`, chốt bởi Nguyễn Minh Nhật
  ngày 2026-10-13.
- `docs/prd/update/2026-10-13-go-luong-cu-sau-demo.md` — thêm: phần gỡ cờ và code luồng cũ sau demo, `chờ chốt`.
- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: ghi luồng orchestrator đã là mặc định. Cả ba phần
  vẫn `chờ chốt`, vì người dùng không chọn Phần A, B.
- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa:
  - Đề xuất mặc định đã chốt; R1–R3 người dùng chấp nhận 13/10.
  - D3 chỉ còn chờ D2.
  - Phần sau demo chờ đề xuất gỡ.
- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: Q1–Q6 người dùng chốt 13/10; Q7 vẫn chờ cùng Phần A;
  B1 và mục 7 trỏ tới đề xuất đã lưu trữ.
- `AGENTS.md` §3 — sửa: thêm quy tắc "luồng phân loại cũ đã đóng băng". Ghi rõ phần đóng băng và phần vẫn dùng chung;
  trước D3 chạy local với `ITINERARY_ORCHESTRATOR=on`.
- `docs/spec/agent/working-context.md` §2, §3 — sửa: hàng "Tune orchestrator" (`ORCHESTRATOR_PROMPT`, `orchestration.py`,
  `jobs.py`, `fares.py`, `gatekeeper.py`); hàng tune classify/converse ghi rõ phần đóng băng; ghi chú đầu §3.
- `.agents/skills/building-itinerary-agent/SKILL.md` — sửa: bảng "Chọn lớp" trỏ tới `orchestration.py`; một dòng trỏ về
  AGENTS.md §3.
- `history/2026-10-12-sua-plan-theo-review-3.md` — sửa: thêm dòng "Bị thay thế bởi".
- `history/2026-10-13-chot-orchestrator-mac-dinh.md` — thêm: entry này.

## Quyết định

- Người dùng không chọn Phần A, Phần B của đề xuất tiến trình, và không chọn phần gỡ code. Các phần đó vẫn `chờ chốt`;
  không suy rộng câu "chốt làm đi" sang chúng.
- Q7 không nằm trong câu hỏi về Q1–Q6, nên vẫn chờ cùng Phần A.
- Đề xuất cũ có hai phần mà chỉ một phần được chốt. Vì vậy tách đôi:
  - Phần đã chốt áp dụng vào PRD rồi lưu trữ (AGENTS.md §8 bước 3–4).
  - Phần chưa chốt thành đề xuất mới.
- PRD đổi trước; code đổi mặc định ở D3, sau D2, để snapshot không đỏ giữa hai commit. Trong lúc chờ, AGENTS.md dặn chạy
  local với cờ `on`.
- "Làm rõ code cũ không dùng" được làm ở hai lớp:
  - Tài liệu: AGENTS.md, `working-context.md`, skill (trong lượt này).
  - Code: comment ở mọi ký hiệu chỉ luồng cũ dùng và log cảnh báo khi dựng graph với cờ tắt (D0).

## Kiểm tra

- Đối chiếu đoạn PRD mới với đề xuất đã lưu trữ: khớp từng chữ (`architecture.md` §3, `deployment-plan.md` §2).
- `grep -n "ORCHESTRATOR_PROMPT" src/backend/app/agents/steps/prompts.py`: có ở dòng 418, đúng như hàng mới của
  `working-context.md`.
- Chưa sửa source trong entry này.

## Còn lại / rủi ro

- Làm tiếp D0, D2, D1 theo plan chung; mỗi bước một entry riêng.
- Chờ chốt:
  - `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md`: Phần A cần trước B2–B8; Q7 nằm trong Phần A.
  - `docs/prd/update/2026-10-13-go-luong-cu-sau-demo.md`: sau demo.
- Code vẫn mặc định `off` tới D3, trong khi PRD đã ghi `on`. Người chạy local theo `.env.example` sẽ ở luồng cũ cho tới
  D3.
