# Khôi phục khoá concurrency `staging-ha-app` của Backend CD và Frontend CD

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu "bổ sung concurrency") / Claude Code (agent)
- Nhánh: khoa/khoi-phuc-concurrency-staging-ha
- Trạng thái: hoàn thành (chưa chạy trên CI; merge sẽ kích CD)
- Phạm vi: infra (CI/CD staging-ha)
- Thay thế một phần: `2026-10-12-bo-concurrency-staging-ha-app.md` (phần bỏ khoá workflow; phần `flock` trên VM giữ nguyên)

## Mục tiêu

Sau khi PR #181 bỏ khoá, tối 2026-10-12 có hai và ba lần roll chạy chồng lên cùng một VM (`fn9m`: 5 tiến trình deploy cùng lúc, `active-slot` lệch với nginx, ba image backend khác nhau). Cần lại có cơ chế ngăn deploy chạy chồng ở cấp workflow. `flock` giữ nguyên làm lớp thứ hai.

## File thay đổi

- `.github/workflows/staging-ha-backend-cd.yml`, `staging-ha-frontend-cd.yml` — sửa: khôi phục `concurrency: group: staging-ha-app, cancel-in-progress: false` ở job deploy (không ở cấp workflow, để job build không phải chờ); cập nhật chú thích đầu file.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — sửa: `NoWorkflowConcurrency` → `SerialisedDeploys`, kiểm hai workflow dùng chung nhóm ở job deploy và `cancel-in-progress: false`.

## Quyết định

- Giữ cả hai lớp: khoá workflow chặn hai run chồng nhau trong cùng nhóm; `flock` chặn trường hợp lọt khoá (vd. `workflow_dispatch` từ nhánh khác dùng workflow cũ chưa có khoá).

## Kiểm tra

- Parse YAML hai workflow: OK. `pytest infra/terraform/environments/staging-ha/tests`: 111 passed.

## Còn lại / rủi ro

- Khoá concurrency của GitHub chỉ giữ MỘT job chờ: khi có job mới vào nhóm, job chờ cũ hơn bị huỷ (annotation "Canceling since a higher priority waiting request for staging-ha-app exists"). Đã xảy ra với các run `38229454334`, `38222592672`, `38272248211`. Với hai push liền nhau, deploy của push đầu có thể không bao giờ chạy; trạng thái cuối vẫn đúng nếu push sau chứa trọn thay đổi của push trước.
- Merge PR này kích Backend CD và Frontend CD (workflow nằm trong `paths`); cần merge khi không có deploy khác đang chạy.
