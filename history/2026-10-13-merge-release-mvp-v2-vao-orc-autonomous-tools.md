# Merge release-mvp-v2 vào codex/orc-autonomous-tools trước khi đưa lên release

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: docs, agent

## Mục tiêu

Đưa code assistant v2 lên `release-mvp-v2` trước khi chuyển orc sang function calling. Merge `origin/release-mvp-v2`
(31 commit mới) vào nhánh để release nhận được bằng fast-forward.

## File thay đổi

- `docs/prd/architecture.md` — xung đột ở §3: release sửa câu cuối đoạn "Orchestrator có model riêng…" (bỏ yêu cầu
  snapshot hành vi); nhánh đã viết lại §3 theo orc v2 (chốt 13/10, đoạn đó không còn). Giữ bản của nhánh; bản này cũng
  không còn yêu cầu snapshot nên ý của release vẫn giữ.
- Các file khác của release vào bằng auto-merge.

## Quyết định

- Merge (không rebase) để giữ lịch sử đã push của cả hai nhánh.

## Kiểm tra

- Backend `pytest src/backend/tests` (WEAVIATE_URL cổng đóng, SEARCH_PREWARM=false): 3050 passed, 42 skipped, 3 xfailed.
  `test_behavior_snapshot` đã được release gỡ (commit 1ecf30ca) nên hai fail trước đó không còn.
- Frontend `vitest run`: 89 file, 936 test passed; `tsc --noEmit`: sạch.
- `validate_contract.py`: PASS (assistant v2 và contract chính).

## Còn lại / rủi ro

- Không có.
