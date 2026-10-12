# Apply Phase 2 staging-ha: template mới đã tạo, rolling update MIG bị chặn bởi hạn mức CPU

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra

## Mục tiêu

Người dùng duyệt apply Phase 2 (thêm log-opts cho compose HA, Phase 1.4). Entry này ghi kết quả apply và việc rolling update bị treo.

## Đã làm

- `terraform plan` lại (plan cũ đã lưu có thể bị cũ), rồi `terraform apply` plan mới: `1 added, 1 changed, 1 destroyed`.
  - Tạo instance template mới `vota-ha-app-20261008150219495000000001` (có log-opts).
  - Đặt MIG `vota-ha-app` sang template mới (`SUBSTITUTE`, `max_surge = 3`, `max_unavailable = 0`).
  - Xoá template cũ `vota-ha-app-20261008022340588700000001` sau khi MIG không còn dùng.
- Output sau apply: `db_host = db.vota.internal`, `lb_ip = 34.111.252.145`, `patroni_ilb_ip = 10.148.0.34`, `patroni_node_ips = {a: 10.148.0.35, b: 10.148.0.37, w: 10.148.0.36}`, `redis_host = 10.146.196.252`.

## Vấn đề

- Rolling update treo: 3 VM mới ở trạng thái `CREATING` hơn 20 phút, MIG `isStable = false`.
- Nguyên nhân: `QUOTA_EXCEEDED` — hạn mức `CPUS_ALL_REGIONS` là 16, đang dùng 16/16. Các VM đang chạy gồm `vota-ha-app` (3 × e2-standard-2), `vota-ha-pg-a/b/w`, `vota-backend-crawler-recsys` (e2-medium), `data-oh-my-god` (e2-standard-2), `v-ota-db-dev` (e2-small), `vota-staging-db-replica` (e2-small).
- Ảnh hưởng: 3 VM app cũ vẫn RUNNING (`max_unavailable = 0`), nên dịch vụ chưa bị gián đoạn. Các VM mới chưa tạo được nên không có VM nào lỗi trong tiến trình.

## Lựa chọn để người dùng quyết

1. Tăng hạn mức `CPUS_ALL_REGIONS` (IAM & Admin → Quotas) lên ít nhất 24 để rolling update có đủ chỗ surge. Đây là lựa chọn khuyến nghị vì giữ được `max_surge = 3`.
2. Không tăng hạn mức: đổi chính sách MIG sang `max_surge = 0`, `max_unavailable = 1` (thay từng VM, tạm còn 2 VM app trong lúc thay). Cần Terraform apply lại.
3. Huỷ thay đổi template (không khuyến nghị): cần apply ngược lại, thêm một lần rolling khác.

## Phase 3 (di trú dữ liệu) — chưa bắt đầu

- Hướng đã chọn: A — lấy dữ liệu từ primary cũ `10.148.0.2` sang cụm HA. Primary cũ là nơi crawler và app đang ghi.
- Yêu cầu: MIG phải ổn định trước; có cửa sổ dừng ghi trên primary cũ; người dùng chốt thời điểm cửa sổ.
- Trạng thái cụm HA hiện tại (theo `docs/guide/van-hanh-db-patroni.md` mục 3, ngày 08/10): leader `vota-ha-pg-b`, replica `vota-ha-pg-a`, lag 0, `cdp.products` lệch 157 dòng so với primary cũ. Cụm không nhận ghi vì `db.vota.internal` vẫn trỏ `10.148.0.2`.
- Bước phải làm theo runbook: dừng ghi (crawler cron, backend), đặt `patroni_clone_from_host = 10.148.0.2` và xoá dữ liệu PGDATA trên HA để clone lại (clone chỉ chạy khi PGDATA trống), cutover DNS `db.vota.internal` → `10.148.0.34`, kiểm tra `ops/check-db-direct.sh`, mở lại app và crawler. Quay lại: DNS về `10.148.0.2`.
- Rủi ro cần chốt: xoá PGDATA HA là thao tác không hoàn tác; chỉ làm sau khi xác nhận primary cũ là nguồn đúng.

## Kiểm tra

- `terraform plan` (lần 2): `1 to add, 1 to change, 1 to destroy`, khớp với plan lần 1.
- `terraform apply`: thành công cho ba resource kể trên.
- Trạng thái MIG sau apply: `isStable = false`, `versionTarget.isReached = false` (treo do quota).

## Còn lại / rủi ro

- Quyết định hạn mức hoặc chính sách MIG (xem lựa chọn trên).
- Phase 3 và Phase 4 chưa làm.
- Phase 2.4 (kiểm trên VM) và 2.5 (Ops Agent) chưa làm.
- Đề xuất PRD ghi đường dẫn `infra/staging-ha` (đúng là `infra/terraform/environments/staging-ha`), không sửa vì đã chốt.
