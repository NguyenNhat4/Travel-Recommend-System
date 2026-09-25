# Đổi tên nhánh cào mới thành test/newcrawl

- Ngày: 2026-09-24
- Tác giả: người dùng / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người dùng yêu cầu nhánh cào mới trong Travel-Recommendation-Product có tên chính xác `test/newcrawl` để tự push.

## File thay đổi

- `src/data_collection/README.md` — sửa: cập nhật tên nhánh đang chứa luồng cào mới.
- `history/2026-09-24-rename-newcrawl-branch.md` — thêm: ghi nhận việc đổi tên nhánh và tài liệu.

## Quyết định

- Đổi tên nhánh local từ `codex/fresh-trip-catalog-release-mvp-v1` sang `test/newcrawl`; giữ nguyên lịch sử commit và không push.
- Giữ nguyên các entry lịch sử trước đó vì chúng phản ánh tên nhánh tại thời điểm được viết.

## Kiểm tra

- `git branch --show-current`: `test/newcrawl`.
- `git diff --check`: pass.

## Còn lại / rủi ro

- Người dùng tự push nhánh `test/newcrawl` lên remote.
