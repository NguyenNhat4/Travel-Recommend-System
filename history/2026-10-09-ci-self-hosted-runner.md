# Runner tự host cho CI/CD (vota-ci-runner) và chuyển runs-on

- Ngày: 2026-10-09
- Tác giả: người yêu cầu / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: docs (infra CI/CD; không đổi source ứng dụng)

## Mục tiêu

GitHub-hosted runner đã hết quota. Đưa toàn bộ job CI/CD sang một runner tự host nhẹ trong VPC staging-ha. Chưa đưa PRD vào thay đổi này: người yêu cầu chỉ định làm trước, không đọc `docs/prd/`. Thay đổi lệch `docs/prd/deployment-plan.md` §1.1 và chưa có đề xuất trong `docs/prd/update/`; cần tạo đề xuất và được chốt, hoặc người yêu cầu xác nhận lại, trước khi coi là hoàn thành.

## File thay đổi

- `.github/workflows/*.yml` (10 file: backend-ci-cd, frontend-ci-cd, crawler-ci-cd, ha-checks, infra-terraform-staging, monitoring-agent-cd-staging, monitoring-terraform-staging, staging-ha-backend-cd, staging-ha-frontend-cd, staging-ha-crawler-cd):
  - `runs-on: ubuntu-latest` → `runs-on: [self-hosted, vota-staging-ha]` cho mọi job.
  - Job có `if:` sẵn: gộp thêm điều kiện chặn fork PR vào `if:` cũ bằng `&&`, không thêm key thứ hai (trùng key làm YAML giữ key cuối và ghi đè điều kiện gốc).
  - Job chưa có `if:`: thêm `if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository`.
- GCP (project `vinpearl-508801`), đã tạo:
  - Service account `ci-runner@` với `roles/logging.logWriter`, `roles/monitoring.metricWriter` (project) và `secretAccessor` trên secret `ci-runner-github-pat`.
  - Secret `ci-runner-github-pat` (chưa có version).
  - VM `vota-ci-runner` (asia-southeast1-b, `e2-standard-2`, Debian 12, đĩa 50 GB pd-balanced, không external IP, shielded VM, OS Login). Startup script cài actions-runner, đăng ký ephemeral với label `vota-staging-ha` mỗi lần khởi động bằng PAT từ Secret Manager; systemd `ci-runner.service` tự khởi động lại sau mỗi job.

## Quyết định

- Runner nằm trên VPC `default`, subnet `default` asia-southeast1, đi ra Internet qua Cloud NAT `vota-ha-nat` (router `vota-ha-router`) đã có sẵn.
- Service account runner không có quyền GCP để deploy. Các job deploy tự xác thực bằng WIF như hiện tại, nên runner không giữ key nào.
- Quota: `CPUS_ALL_REGIONS` 11/24 khi tạo VM (kiểm trước khi tạo), còn trống 13 vCPU.
- Bỏ điều kiện `gh` cho runner: không dùng PAT trong workflow, chỉ dùng trong startup script.

## Kiểm tra đã chạy

- Kiểm YAML các workflow bằng PyYAML với kiểm tra key trùng: OK.
- `gcloud compute instances create` thành công, VM RUNNING, không có external IP.
- Chưa đăng ký được runner: tài khoản `Khoa15` không có quyền admin trên repo (`gh api .../actions/runners` trả 404, `permissions.admin = false`). Cần người có quyền admin cấp PAT (fine-grained, quyền Administration: write trên repo) và thêm vào secret `ci-runner-github-pat`.

## Còn lại

- Thêm PAT vào Secret Manager; kiểm `systemctl is-active ci-runner` trên VM; kiểm runner hiện Online trong Settings → Actions → Runners.
- Chạy thử `ha-checks` (workflow_dispatch, không deploy) để xác nhận runner nhận job.
- Chạy thử deploy `staging-ha-backend-cd` (workflow_dispatch) sau khi runner Online. Workflow này apply lên MIG staging-ha thật.
- Xác nhận phí $0.002/phút cho self-hosted runner trên trang Billing (nguồn mâu thuẫn).
- Tạo đề xuất `docs/prd/update/` cho việc đưa runner vào hạ tầng, theo AGENTS.md mục 8.
- Bước tạo job CD runner và cờ `Fork pull request workflows` trên repo chưa kiểm được (cần quyền admin).
