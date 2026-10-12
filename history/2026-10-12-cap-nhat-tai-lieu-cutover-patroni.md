# Cập nhật tài liệu sau cutover sang cụm Patroni

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/vm-night-schedule-2359-0830
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu cập nhật các tài liệu còn ghi trạng thái cũ "chưa cutover" của `db.vota.internal`, vì chúng gây hiểu lầm cho trạng thái hiện tại. Đã kiểm 2026-10-12: `gcloud dns record-sets list --zone=vota-ha-internal --name=db.vota.internal.` trả `10.148.0.34` (ILB). Primary cũ `v-ota-db-dev` (`10.148.0.2`) và replica cũ `vota-staging-db-replica` (`10.148.0.4`) đều `TERMINATED`. Cutover thực tế xảy ra 2026-10-08 (`history/2026-10-08-phase3-di-tru-db.md`).

## File thay đổi

- `docs/guide/van-hanh-db-patroni.md` — sửa: thêm dòng trạng thái đầu mục 3 (runbook đã dùng 2026-10-08); đánh dấu ảnh chụp 2026-10-08 là lịch sử; thêm mục "Trạng thái hiện tại (cập nhật 2026-10-12)"; thay các gạch đầu dòng ghi "chưa cutover" và "157 dòng khác" ở mục 7 bằng trạng thái đúng.
- `docs/plan/2026-10-07-ha-vung-crawler-rolling.md` — sửa: thêm ghi chú cập nhật vào dòng DNS/ghi của bảng kiểm (plan giữ nguyên lịch sử, chỉ bổ sung trạng thái).
- `docs/plan/2026-10-08-hoan-thanh-todo-ha.md` — sửa: dòng quyết định A ghi "đã thực hiện 2026-10-08"; tiêu đề Phase 3 ghi "đã hoàn thành" thay vì "chưa bắt đầu". Các ô checklist giữ nguyên, có ghi chú.

## Quyết định

- Không sửa `docs/prd/`: `docs/prd/deployment-plan.md` (§ di trú, DNS rollback) vẫn mô tả trạng thái cũ. PRD chỉ đổi qua đề xuất đã chốt (AGENTS.md mục 8), nên không sửa ở đây.
- Không sửa `history/` cũ (quy tắc `history/README.md`).
- Không sửa code/config (Makefile, `scripts/tunnel.ps1`, `scripts/run_tunnel.ps1`, `infra/terraform/environments/staging-ha/staging-ha.tfvars(.example)`): đây là thay đổi hành vi, cần quyết định riêng. Xem "Còn lại".
- Ảnh chụp cũ (17522/157 dòng khác, leader pg-b) được giữ làm lịch sử, có ghi chú rõ là ảnh chụp và không còn đúng.

## Kiểm tra

- `gcloud dns record-sets list --zone=vota-ha-internal --name=db.vota.internal. --project=vinpearl-508801` → `10.148.0.34`, TTL 30.
- `gcloud compute instances list` → `v-ota-db-dev`, `vota-staging-db-replica`: `TERMINATED`; `vota-ha-pg-a/b/w`: `RUNNING`, không có NAT IP.
- Tài liệu không có chạy kiểm thử tự động.

## Còn lại / rủi ro

- **Đường vào DB từ laptop (cập nhật sau entry này):** đã có bastion public, xem `history/2026-10-12-bastion-ssh-mat-khau.md`. Các mục dưới đây là trạng thái trước đó. `Makefile` (`TUNNEL_PRIMARY`, dòng 23), `scripts/tunnel.ps1`, `scripts/run_tunnel.ps1` và `README.md` (dòng 106) vẫn SSH tới `vota-dev@35.197.148.180` rồi forward `10.148.0.2`. Máy đó đã dừng và không có IP public, nên các lệnh này không hoạt động. Cần quyết định đường vào (IAP tới node Patroni, hoặc bastion (chưa có đề xuất; bản nháp đã xoá theo yêu cầu)) trước khi sửa.
- **`staging-ha.tfvars` và `.example` còn `db_primary_ip = "10.148.0.2"`.** Theo runbook mục 3 bước 6, phải đổi sang IP ILB sau khi ổn định. Chưa đổi vì đây là biến Terraform có thể ảnh hưởng plan; cần kiểm `terraform plan` trước.
- **PRD lệch thực tế:** `docs/prd/deployment-plan.md` (dòng ~32, ~173–178) mô tả di trú và quay lại bằng `db.vota.internal` như còn đang chờ. Cần đề xuất trong `docs/prd/update/` để chốt.
- Checklist các ô `[ ]` trong `docs/plan/2026-10-08-hoan-thanh-todo-ha.md` mục Phase 3 chưa được tick. Người vận hành cần tick hoặc bỏ theo kết quả thực tế.
- Leader Patroni hiện tại chưa xác nhận trong entry này. Cần `patronictl list` trên một node.
