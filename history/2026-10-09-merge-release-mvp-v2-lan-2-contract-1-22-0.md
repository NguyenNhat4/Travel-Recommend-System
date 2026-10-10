# Merge release-mvp-v2 lần 2, nâng contract lên 1.22.0

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: contract | backend | docs

## Mục tiêu

PR #124 báo xung đột sau khi `release-mvp-v2` nhận thêm PR #131 (search 1.18.0 + gộp 1.20.0) và #133 (CI staging-ha).

## File thay đổi

- `src/shared/contracts/openapi.yaml`, `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py` — sửa: `version` 1.22.0.
- `src/backend/tests/contract/test_search_llm_contract.py` — sửa: kỳ vọng version 1.22.0 (đang cứng 1.20.0 từ release).
- `src/shared/contracts/schemas/search.yaml` — sửa: thêm dòng changelog 1.22.0.
- Còn lại là nội dung release (search gazetteer/entity/duration, bench gold_v6, workflow CI) tự gộp, không xung đột.

## Quyết định

- Hai nhánh cùng dùng số 1.20.0 cho hai thay đổi khác nhau (release: gộp search 1.18+1.19; feat/agent: stayOptions 1.20.0, estimatedTotal 1.21.0). Không có field nào đè nhau, nên chọn 1.22.0 làm phiên bản gộp, không đổi số đã ghi trong mô tả field của agent.

## Kiểm tra

- `validate_contract.py`: PASS.
- `tsc --noEmit` frontend: sạch.
- Backend `tests/contract tests/architecture`: 121 passed.
- Chưa chạy lại toàn bộ backend unit và frontend unit sau lần merge này (lần merge trước đã pass).

## Còn lại / rủi ro

- Nếu release lại tăng version contract trước khi PR được merge, sẽ xung đột lại ở ba file version.
