# Sửa sau merge #192: cổng E2E đụng nhau, allowlist alert group_at_max

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: claude/cicd-fix-e2e-port-allowlist
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD)
- Liên quan: `2026-10-13-cd-staging-ha-mot-luong-hai-pha.md`

## Mục tiêu

Hai CD đầu tiên sau khi merge #192 (`cabbfa22`) lỗi:

1. **Staging-HA App CD** (run 38340468294): cổng CI chặn deploy vì Frontend E2E báo `http://127.0.0.1:3100 is already used`. E2E của PR #191 chạy cùng lúc trên cùng VM runner, và Playwright dùng cổng cố định 3100. Cổng CI làm đúng việc: không build frontend, không deploy.
2. **Staging-HA Infra CD** (run 38340468098, và trước đó run 38339358612 của chính commit `10aa9488`): cổng `allowed_changes` dừng trước apply ở `google_monitoring_alert_policy.group_at_max|update`. Commit `10aa9488` nâng `cpu_target` từ 0.55 lên 0.9, và alert này dùng `var.cpu_target` làm ngưỡng.

## File thay đổi

- `.github/workflows/frontend-ci-cd.yml` — sửa: E2E lấy một cổng trống cho `PLAYWRIGHT_PORT` (biến này `playwright.config.ts` đã hỗ trợ).
- `scripts/deploy-staging-ha-app.sh` — sửa: allowlist `google_monitoring_alert_policy.group_at_max|update`, kèm chú thích nguồn gốc.

## Quyết định

- Thêm đúng địa chỉ bị chặn vào allowlist, không nới cổng. Thay đổi là hệ quả có chủ đích của `10aa9488`: chỉ ngưỡng `threshold_value` đổi.
- Cổng E2E được chọn động thay vì tách runner: mọi runner chung một VM, nên không thể dựa vào cổng cố định.

## Kiểm tra

- Ghi kết quả CI của PR này và kết quả CD sau merge trong báo cáo đánh giá ở phần trả lời của phiên làm việc.

## Còn lại / rủi ro

- Các cổng cố định khác trên runner chung VM (ví dụ Postgres `5432` của `ha-checks` crawler-lock) cũng có thể đụng nhau khi hai job chạy cùng lúc.
