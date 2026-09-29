# Giải quyết conflict PR #43 và #44

- Ngày: 2026-09-29
- Tác giả: Khoa15 / Codex
- Nhánh: `khoa/workflow-pr-push-triggers`
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Đồng bộ nhánh PR với `release-mvp-v2` sau khi target branch có các commit mới; giữ lại cả thay đổi readiness/CI của PR và thay đổi upstream.

## File thay đổi

- `.gitignore` — sửa: giữ đồng thời quy tắc ignore Terraform và search benchmark/Streamlit.
- `src/backend/tests/unit/api/test_backend_wiring.py` — sửa: giữ readiness test và import `ToolError` từ upstream.
- `history/2026-09-29-resolve-pr-43-44-conflicts.md` — thêm: ghi quyết định xử lý conflict.

## Quyết định

- Dùng merge commit từ `release-mvp-v2`, không rewrite lịch sử.
- Hợp nhất nội dung cả hai phía tại các vùng conflict; không bỏ thay đổi upstream.

## Kiểm tra

- `git diff --check`: PASS.
- `git diff --cached --check` trên các file conflict: PASS.
- Kiểm tra trạng thái merge của PR sau push: chưa chạy.
- Test suite: chưa chạy.

## Còn lại / rủi ro

- Xác nhận GitHub báo PR mergeable sau khi push merge commit.

## Đồng bộ bổ sung với target mới

- Target đã tiến lên `origin/release-mvp-v2` tại `67c384c` (merge PR #44 và #45).
- Giữ event gating, digest pinning và readiness checks của nhánh hiện tại trong hai workflow CI/CD.
- Giữ các cập nhật guide từ target; conflict add/add của history được hợp nhất vào entry này.
