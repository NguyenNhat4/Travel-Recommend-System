# Bỏ khoá concurrency `staging-ha-app` của Backend CD và Frontend CD

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/bo-concurrency-staging-ha
- Trạng thái: dang dở (chưa chạy hai deploy chồng nhau trên CI thật)
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-10-12-cd-zero-downtime-slot.md`, `2026-10-12-sua-reload-proxy-slot.md`

## Mục tiêu

Khoá `concurrency: staging-ha-app` (`cancel-in-progress: false`) ở job deploy của hai workflow bắt các deploy chạy nối tiếp. GitHub chỉ giữ MỘT job đang chờ trong một nhóm, nên job chờ cũ hơn bị huỷ khi có job mới vào (annotation: "Canceling since a higher priority waiting request for staging-ha-app exists"). Đã xảy ra với run `38229454334` và `38222592672`. Yêu cầu: bỏ khoá.

## File thay đổi

- `.github/workflows/staging-ha-backend-cd.yml`, `staging-ha-frontend-cd.yml` — sửa: xoá khối `concurrency` của job deploy, cập nhật chú thích đầu file.
- `infra/terraform/environments/staging-ha/slot-deploy.sh` — sửa: `acquire_lock` (`flock -w 1800` trên `/var/lock/vota-slot-deploy.lock`) ở mode `boot` và `deploy`; tiến trình drain nền đóng fd khoá (`9>&-`) để không giữ khoá sau khi script thoát.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — thêm: 3 test (không còn `concurrency:` ở hai workflow, script có flock ở hai mode, drain nền không giữ khoá).

Không đổi `staging-ha-crawler-cd.yml` (nhóm `staging-ha-crawler` riêng).

## Quyết định

- Bù cho phần an toàn mất đi bằng `flock` trên từng VM, vì hai lần roll chồng lên cùng một VM sẽ tranh slot, proxy và `active-slot`. Terraform đã có khoá state (`-lock-timeout=10m`).

## Kiểm tra

- `bash -n`, parse YAML hai workflow: OK. `pytest infra/terraform/environments/staging-ha/tests`: 107 passed.
- Chưa chạy hai deploy chồng nhau trên CI.

## Còn lại / rủi ro

- **Rollback có thể chạy nhầm:** nếu deploy B đợi khoá state Terraform quá 10 phút thì bước apply lỗi, `if: failure()` kích rollback, và rollback áp last-good đè lên những gì deploy A đang làm. Trước đây khoá concurrency ngăn tình huống này.
- **last-good bị ghi đè:** bước "Record ... as last good" đọc rồi ghi cả file JSON; hai deploy kết thúc gần nhau có thể làm mất cập nhật của nhau (backend_ref và frontend_ref).
- Deploy chồng nhau cùng đọc last-good làm tham chiếu của thành phần kia; deploy chạy sau có thể dùng tham chiếu cũ của thành phần mới vừa được deploy.
- Không còn run nào bị huỷ do bị thay thế: mọi run đều chạy đến cùng, số run xếp hàng trên runner tự host có thể tăng.
