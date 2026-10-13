# Đổi tên workflow backend CI: `backend-ci-cd.yml` → `backend-ci.yml`

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/xoa-monitoring-staging-cu
- Trạng thái: hoàn thành
- Phạm vi: CI (workflows), docs

## Mục tiêu

Yêu cầu: đổi `backend-ci-cd.yml` thành `backend-ci.yml`, tên hiển thị là `Backend CI`. Workflow này chỉ còn CI (đã gỡ deploy VM cũ), nên tên `CI/CD` không còn đúng. Tên hiển thị trong file đã là `Backend CI` (từ release); giữ chữ B viết hoa để khớp `Frontend CI` và `Crawler CI/CD`.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` → `.github/workflows/backend-ci.yml` — đổi tên (`git mv`); trigger tự tham chiếu đổi theo.
- `.github/workflows/staging-ha-app-cd.yml` — sửa: path trigger và `uses:` của job `backend-ci` trỏ tới `backend-ci.yml`.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — sửa: danh sách workflow reusable và kiểm `uses:` của cổng CI backend (backend dùng `backend-ci.yml`, frontend giữ `frontend-ci-cd.yml`).
- `docs/spec/bench/recsys-offline-eval.md` — sửa: tham chiếu tới workflow hiện hành.
- `history/2026-10-13-doi-ten-backend-ci.md` — thêm: entry này.

Không sửa, có chủ ý: `docs/plan/`, `docs/spec/2026-09-24-*`, `docs/prd/update-archive/`, `history/` cũ. Đây là tài liệu theo ngày, ghi lại trạng thái lúc đó. Các tham chiếu đó vẫn đúng với thời điểm viết.

## Kiểm tra

- Parse YAML `backend-ci.yml` và `staging-ha-app-cd.yml`: pass.
- `test_slot_deploy.py`: 42/44 pass; 2 test lỗi do `mapfile` của bash 3.2 trên máy local (đã biết, CI chạy bash 5).
- Các test staging-ha khác: pass.
- Không còn tham chiếu `backend-ci-cd.yml` trong workflow, test hay tài liệu hiện hành.

## Còn lại / rủi ro

- Check trên PR dựa vào tên job (`CI checks`, `Build images`), không đổi. Khi merge, staging-ha-app-cd gọi `backend-ci.yml` mới.
