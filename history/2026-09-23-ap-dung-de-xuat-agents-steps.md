# Áp dụng đề xuất: thêm `agents/steps/` vào cây thư mục backend trong PRD

- Ngày: 2026-09-23
- Tác giả: Nguyễn Minh Nhật (chốt) / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt đề xuất `docs/prd/update-archive/2026-09-23-agents-steps-folder.md`, được tạo trong
task `history/2026-09-23-tach-nodes-py-thanh-agents-steps.md` khi tách `agents/nodes.py`. Cập nhật
PRD theo đúng nội dung đã chốt và lưu trữ đề xuất (AGENTS.md §8 bước 3–4).

## File thay đổi

- `docs/prd/architecture.md` — sửa: §2, dòng `agents/` trong cây thư mục thêm "steps/ (luật của từng bước)".
- `docs/prd/update/2026-09-23-agents-steps-folder.md` → `docs/prd/update-archive/2026-09-23-agents-steps-folder.md`
  — đổi tên: chuyển sang lưu trữ, trạng thái `đã áp dụng`, chốt bởi Nguyễn Minh Nhật ngày 2026-09-23.

## Quyết định

- Chỉ sửa đúng một dòng đã nêu trong đề xuất, không sửa thêm mục nào khác của PRD.
- Dùng `mv` thay vì `git mv` vì đề xuất chưa từng được commit (file chưa được track).

## Kiểm tra

- `grep -n "agents/  " docs/prd/architecture.md` → dòng 111 đã có `steps/`.
- `docs/prd/update/` hiện trống.

## Còn lại / rủi ro

- Không có.
