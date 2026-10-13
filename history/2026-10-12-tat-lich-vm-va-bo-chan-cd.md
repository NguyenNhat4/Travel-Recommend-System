# Vô hiệu lịch tắt VM ban đêm và bỏ cổng chặn CD staging-ha

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: Khoa15/khoa-disable-shutdown-schedule (rebase lên `release-mvp-v2` 9290aa3a), PR #180 vào `release-mvp-v2`, chưa merge
- Trạng thái: dang dở (đã commit và push; PR chưa merge; GCP đã gỡ lịch; MIG app còn template chưa roll xong; xem mục Sự cố)
- Phạm vi: infra (CI/CD staging-ha)
- Thay thế: 2026-10-10-lich-tat-mo-vm-2359-0830.md
- Liên quan: 2026-10-12-staging-ha-cd-khong-chay.md (điều tra cổng khung giờ; entry này chọn bỏ hẳn cổng, không chọn (a), (b) hay (c) ở đó); 2026-10-12-allowlist-resource-policies.md (PR #178, sự cố dưới đây)

## Mục tiêu

Người vận hành yêu cầu hai việc: (1) vô hiệu lịch tắt VM ban đêm của staging-ha (lịch 23:59 tắt, 08:30 bật chốt 10/10); (2) bỏ chặn CI/CD trong khung 23:59–08:30. Việc (2) thực tế là gỡ job `window-guard` (đang chặn 23:45–08:40), vì cổng đó chỉ tồn tại để chờ VM và runner bật lại sau khi tắt ban đêm. Nếu VM không tắt nữa thì cổng không còn lý do.

## File thay đổi

- `.github/workflows/staging-ha-backend-cd.yml` — sửa: bỏ job `window-guard`; `build` và `deploy` không còn `needs`/`if` phụ thuộc nó.
- `.github/workflows/staging-ha-frontend-cd.yml` — sửa: như trên cho `build` và `deploy`.
- `.github/workflows/staging-ha-crawler-cd.yml` — sửa: bỏ `window-guard`; `images`, `deploy_crawler`, `verify` không còn `needs`/`if` phụ thuộc nó.
- `infra/terraform/environments/staging-ha/scheduler.tf` — sửa: bỏ năm `google_cloud_scheduler_job` tắt/bật (`app_autoscaler_off`, `app_resize_zero`, `app_autoscaler_on`, `crawler_extra_start`, `crawler_extra_stop`) cùng biến và locals chỉ phục vụ chúng. Giữ ba `google_compute_resource_policy` lịch (`patroni_schedule`, `weaviate_schedule`, `bastion_schedule`) để xoá ở PR sau, và giữ service account, IAM, role `votaHaOpsScheduler`, `ops_schedule_timezone` (alert_mute còn dùng).
- `infra/terraform/environments/staging-ha/crawler.tf` — sửa: bỏ `resource_policies` của VM crawler. Giữ resource `crawler_schedule` và biến lịch của nó để xoá ở PR sau.
- `infra/terraform/environments/staging-ha/patroni.tf` — sửa: bỏ `resource_policies` (`patroni_schedule`) khỏi `google_compute_instance.patroni`.
- `infra/terraform/environments/staging-ha/bastion.tf` — sửa: bỏ `resource_policies` (`bastion_schedule`).
- `infra/terraform/environments/staging-ha/weaviate.tf` — sửa: bỏ `resource_policies` (`weaviate_schedule`).
- `infra/terraform/environments/staging-ha/alert_mute.tf` — sửa: comment đầu file (không đổi lịch mute 23:55–08:35).
- `scripts/deploy-staging-ha-app.sh` — sửa: thêm vào allowlist năm địa chỉ `google_cloud_scheduler_job.*|delete` (xem Quyết định); sửa chú thích hai dòng `bastion[0]`, `crawler[0]` (chúng giờ chỉ bỏ `resource_policies`).
- `history/2026-10-10-lich-tat-mo-vm-2359-0830.md` — sửa: thêm dòng `Bị thay thế bởi`.
- `history/2026-10-12-tat-lich-vm-va-bo-chan-cd.md` — thêm: entry này.

Ngoài repo, thực hiện bằng gcloud trước 23:57 ngày 12/10 (giờ VN). Terraform không chạy:

- Gỡ instance schedule khỏi 6 VM, không dừng VM nào (`gcloud compute instances remove-resource-policies`):
  - `vota-ci-runner` (asia-southeast1-b): `vota-ci-runner-schedule`
  - `vota-ha-crawler` (asia-southeast1-a): `vota-ha-crawler-schedule`
  - `vota-ha-pg-a` (asia-southeast1-a), `vota-ha-pg-b` (asia-southeast1-b), `vota-ha-pg-w` (asia-southeast1-c): `vota-ha-patroni-schedule`
  - `vota-ha-bastion` (asia-southeast1-c): `vota-ha-bastion-schedule`
- Tạm dừng 5 job Cloud Scheduler (`gcloud scheduler jobs pause`, location asia-southeast1): `vota-ha-app-autoscaler-off`, `vota-ha-app-resize-zero`, `vota-ha-app-autoscaler-on`, `vota-ha-crawler-extra-start`, `vota-ha-crawler-extra-stop`.
- Không đổi: `vota-ha-alert-mute-on/off` (vẫn ENABLED), các resource policy snapshot, `vota-ci-runner-start` (đã mồ côi từ 10/10, chưa xoá).

## Sự cố sau khi PR #178 merge vào release-mvp-v2 (12/10, giờ VN)

- 21:52: PR #178 (`27a3a42d`) merge vào `release-mvp-v2`, thêm `google_compute_instance.bastion[0]|update` và `crawler[0]|update` vào allowlist cổng plan để CD gắn lại `resource_policies` lịch tắt (commit a8ef14f3 trên `release-mvp-v2` còn khai các attachment này). Push lên `release-mvp-v2` kích `Staging-HA Backend CD` và `Staging-HA Frontend CD` (path `scripts/deploy-staging-ha-app.sh`).
- ~22:00: `Staging-HA Frontend CD` (38266237899) apply Terraform và gắn lại lịch tắt cho `vota-ha-crawler`, `vota-ha-bastion`, `vota-ha-pg-a/b/w`. Nếu không xử lý, 5 VM này, gồm 3 node Patroni, sẽ dừng lúc 23:59 tối nay.
- 22:03: huỷ `Staging-HA Backend CD` (38266237856) đang pending (`gh run cancel`). Chưa có apply nào từ run này.
- 22:11: `Staging-HA Frontend CD` kết thúc `failure`. Bước "Roll app VMs" lỗi trên `vota-ha-app-fn9m` khi dựng slot green: nginx báo `open() "/run/nginx.pid" failed (2: No such file or directory)`; script ghi "VM này vẫn phục vụ bằng bản cũ, các VM sau chưa bị đụng". Bước "Roll back frontend to last good" cũng lỗi cùng kiểu lúc 15:11 UTC. Terraform đã đổi target template của MIG sang `vota-ha-app-20261012150437925200000001`; hai instance vẫn chạy template cũ `vota-ha-app-20261012103652436300000001`; MIG chưa stable.
- 22:12: `https://praxis.io.vn/health/live` và `/health/ready` đều trả 200.
- ~22:13: gỡ lại lịch khỏi 5 VM bằng gcloud, đọc lại xác nhận không VM nào còn gắn lịch. Scheduler job vẫn PAUSED.
- Nguyên nhân: config Terraform trên `release-mvp-v2` vẫn khai `resource_policies`, state không khớp với GCP sau khi gỡ ngoài TF, và allowlist của PR #178 cho phép plan gắn lại. Mọi lần CD chạy trên `release-mvp-v2` cho đến khi PR này được merge sẽ gắn lại lịch.
- Chưa điều tra lỗi nginx `/run/nginx.pid` trên slot script. Lỗi này sẽ làm CD roll tiếp theo có thể fail lại.

## Quyết định

- "Tắt VM" hiểu là mọi lịch có hành động stop/start VM hoặc resize MIG, gồm cả khung cào thêm 01:45–04:00 (đã để lại chờ xử lý từ 10/10). Lý do: lịch 04:00 tắt crawler mỗi đêm.
- Bỏ hẳn `window-guard`, không đổi khung thành 23:59–08:30: cổng không còn lý do tồn tại khi VM và runner không tắt nữa.
- Gỡ lịch khỏi GCP bằng gcloud trước khi merge, vì lịch 23:57/23:59 chạy tối nay. Ghi nhận rằng gỡ ngoài TF chỉ bền khi config TF không còn khai lịch; PR này là cách làm config khớp.
- Nới cổng plan đúng năm địa chỉ `google_cloud_scheduler_job.*|delete` (bản đầu của PR là sáu, sai số đếm). Lý do: CD không bị chặn bởi destroy của job, và job không có VM nào tham chiếu nên không có ràng buộc thứ tự.
- Không nới cổng cho ba `google_compute_resource_policy` lịch. Chúng được giữ trong config và sẽ xoá ở PR sau. Lý do: lần 10/10 xoá policy cùng lúc với bước gỡ attachment khỏi VM đã lỗi `resourceInUseByAnotherResource` vì thứ tự không được đảm bảo. Chưa có plan thật để chứng minh thứ tự an toàn.
- Mô phỏng cổng với plan dự kiến (xem Kiểm tra): năm job delete và năm update VM đều pass; delete policy vẫn bị chặn (đối chứng).
- Không tạo đề xuất trong `docs/prd/update/`: PRD (`docs/prd/`) không quy định lịch tắt VM ban đêm hay cổng khung giờ CD. Quyết định 10/10 và entry này chỉ nằm trong `history/`.

## Kiểm tra

- Ba workflow parse YAML OK (python `yaml.safe_load`); `grep` không còn `window-guard`, `23:45`, `08:40` trong `.github/workflows/staging-ha-*-cd.yml`.
- `terraform -chdir=infra/terraform/environments/staging-ha fmt -check`: pass.
- `terraform validate`: `Success! The configuration is valid.`
- `bash -n scripts/deploy-staging-ha-app.sh`: pass.
- Mô phỏng cổng: đọc `allowed_changes` từ script, kiểm tra từng dòng plan dự kiến (`patroni a/b/w|update`, `bastion[0]|update`, `crawler[0]|update`, năm `google_cloud_scheduler_job.*|delete`). Cả 10 pass. Đối chứng: `google_compute_resource_policy.patroni_schedule[0]|delete` và `google_compute_instance.weaviate[0]|update` bị chặn. Địa chỉ state lấy bằng `terraform state list` (chỉ đọc): ba policy `[0]`, năm job, không có `weaviate_schedule` (count 0).
- `python3 -m pytest tests -q` (staging-ha): 104 passed.
- Không chạy `terraform plan`: worktree không có `*.tfvars` (secret CI). Plan thật chỉ biết khi CD chạy.
- Trạng thái GCP sau khi gỡ lần cuối (đọc lại 22:14): 6 VM đều RUNNING, không VM nào còn resource policy lịch; 5 job PAUSED; MIG `vota-ha-app` size 2 (instance trên template cũ), autoscaler mode ON, min 1, max 2, ACTIVE.
- PR tạo vào `release-mvp-v2`: các workflow `pull_request` không apply gì. `infra-terraform-staging` chỉ apply khi `push`, root `staging`. `monitoring-terraform-staging` chỉ apply khi PR đã merge, root `infra/monitoring`.
- Chưa kiểm chứng thật qua 23:57, 23:59 và 04:00 tối nay. Đó là phép thử thật.

## Rollback

- Gắn lại lịch cho từng VM: `gcloud compute instances add-resource-policies <vm> --resource-policies=<policy> --zone=<zone>`, cặp như mục "Ngoài repo".
- Bật lại job: `gcloud scheduler jobs resume <id> --location=asia-southeast1`.
- Repo: `git revert` các commit của nhánh này.

## Còn lại / rủi ro

1. **Chưa merge PR #180.** Merge là push vào `release-mvp-v2` và kích lại CD staging-ha. Sau thay đổi này, plan dự kiến không còn destroy ngoài allowlist. Plan thật chưa chạy được ở đây, nên CD có thể vẫn dừng nếu có thay đổi khác chưa biết. Merge cũng là cách để config không còn khai lịch (chặn việc gắn lại).
2. **Target template MIG `vota-ha-app` đang khác instance.** Cần xử lý trước khi CD frontend/backend chạy lại. Nguyên nhân roll fail là slot nginx trên `vota-ha-app-fn9m` (`/run/nginx.pid`), chưa điều tra.
3. **Mute cảnh báo HA 23:55–08:35 vẫn ENABLED.** Tối nay email cảnh báo HA sẽ bị mute dù VM đang chạy. Cần quyết định: bỏ mute (xoá `alert_mute.tf` và hai job) hoặc giữ có chủ đích. Đây không nằm trong hai việc được yêu cầu nên chưa đụng.
4. **Phase 2: xoá ba resource policy lịch** (`patroni_schedule`, `bastion_schedule`, `crawler_schedule`, và `weaviate_schedule` nếu có) cùng biến lịch liên quan, sau khi PR này merge và plan xác nhận không VM nào còn attachment. Khi đó thêm ba địa chỉ `|delete` vào allowlist.
5. **Quyền thừa của scheduler SA**: role `votaHaOpsScheduler` và service account `scheduler` vẫn có quyền start/stop VM và cập nhật autoscaler/MIG, không còn job nào dùng. Nên thu hẹp chỉ còn `monitoring.notificationChannels.update`, và đổi mô tả role đã lỗi thời. Chưa làm vì đổi role là update thêm trong plan.
6. **Runner `vota-ci-runner`** nằm ngoài Terraform: lịch đã gỡ bằng gcloud như lần trước. Cần kiểm tra runner nhận job tối nay.
7. **Crawler**: lịch khung cào thêm đã tắt, nên VM crawler không còn start/stop. Cron trong VM vẫn theo lịch riêng; kiểm tra lượt cào tối nay.
8. **Orphan**: `vota-ci-runner-start` (không gắn VM) và các resource policy snapshot chưa xoá.
9. Entry `2026-10-12-staging-ha-cd-khong-chay.md` vẫn ghi `dang dở` ở các mục khác (lệch state Patroni, lock Terraform). Mục cổng khung giờ đã xử lý bằng entry này.
