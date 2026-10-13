# Tối ưu CI/CD: huỷ CI cũ trên PR, cache registry, tách CD hạ tầng staging-ha

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD)

## Mục tiêu

Theo đánh giá CI/CD ngày 2026-10-13, người dùng chốt: (1) CI trên PR huỷ run cũ; (4) chuyển cache GHA sang registry; (7+9) hạ tầng staging-ha có CD riêng, hai CD ứng dụng không còn chạy theo đường dẫn hạ tầng, không cần reviewer vì đã duyệt trước khi merge.

## File thay đổi

- `.github/workflows/{backend,frontend,crawler}-ci-cd.yml` — sửa: `cancel-in-progress` = true chỉ khi `pull_request`.
- `.github/workflows/staging-ha-frontend-build.yml` — sửa: cache `type=gha` → `type=registry` (`<frontend image>:buildcache`).
- `.github/workflows/staging-ha-crawler-cd.yml` — sửa: cache `type=gha` → `type=registry` (`$GAR_FRESH_IMAGE:buildcache-ha`, tag riêng để không ghi đè `:buildcache` của crawler-ci-cd).
- `.github/workflows/staging-ha-backend-cd.yml`, `staging-ha-frontend-cd.yml` — sửa: bỏ path `infra/terraform/environments/staging-ha/**`.
- `.github/workflows/staging-ha-infra-cd.yml` — thêm: apply Terraform staging-ha, ref ứng dụng lấy từ last-good, dùng chung cổng `allowed_changes` và khoá `staging-ha-app`, không ghi last-good, không rollback tự động.
- `.github/workflows/backend-ci-cd.yml` (`publish`, `deploy`), `frontend-ci-cd.yml` (`build_vm`, `publish_vm`, `deploy_vm`), `crawler-ci-cd.yml` (`deploy`) — xoá: job `if: ${{ false }}` của VM staging cũ.
- `scripts/tests/test-backend-vm-cd-sync.sh` — sửa: bỏ các kiểm tra chuỗi trong workflow đã xoá; giữ kiểm tra compose, script deploy VM và action sync env.
- `docs/guide/van-hanh-cd-staging-ha.md` — sửa: mô tả CD hạ tầng.

## Quyết định

- Không lệch PRD: `deployment-plan.md` §6.1 không quy định workflow nào kích hoạt khi đổi Terraform; không cần đề xuất `docs/prd/update/`.
- Giữ cổng `allowed_changes` cho CD hạ tầng: thay đổi ngoài danh sách vẫn dừng trước apply.
- Không rollback tự động ở CD hạ tầng vì ref ứng dụng không đổi.
- Lịch tắt VM và `window-guard` đã gỡ từ trước (`2026-10-12-tat-lich-vm-va-bo-chan-cd.md`); không làm thêm trong lần này.

## Kiểm tra

- Parse YAML mọi workflow: pass. `scripts/tests/test-backend-vm-cd-sync.sh`: pass.
- Test cấu trúc staging-ha: xem kết quả `unittest` ở phần trả lời; chưa chạy workflow thật trên GitHub.

## Còn lại / rủi ro

- Ngoài repo: đã xoá snapshot `vota-ci-runner-dr-202610121646` (gcloud, 2026-10-13, theo yêu cầu) sau khi người dùng đổi scope VM `ai-agent-on-edge` sang `cloud-platform`. Còn lại `vota-ci-runner-clone`, không đụng.
- Job `publish` của crawler-ci-cd vẫn đẩy image crawler dù không còn job nào dùng (staging-ha tự build); chưa gỡ.
- Cache `buildcache` / `buildcache-ha` phải tồn tại trong Artifact Registry; lần build đầu cache miss.
