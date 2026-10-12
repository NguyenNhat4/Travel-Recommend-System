# Dừng VM staging-ha để giải phóng quota cho rolling update; VM staging không dừng

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra

## Mục tiêu

Người dùng yêu cầu dừng các VM thuộc `staging-ha` để giải phóng quota `CPUS_ALL_REGIONS` (16/16), cho rolling update của `vota-ha-app` tiếp tục. Các VM thuộc `staging` không được dừng.

## Phân loại VM

- Thuộc `staging-ha` (dừng): `vota-ha-app-5v5g` (a), `vota-ha-app-xstn` (b), `vota-ha-app-jlb1` (c), `vota-ha-pg-a` (a), `vota-ha-pg-b` (b), `vota-ha-pg-w` (c).
- Thuộc `staging` (không dừng): `vota-staging-db-replica` (label `environment: staging`).
- Không thuộc `staging-ha` và không có trong yêu cầu (không dừng): `v-ota-db-dev`, `vota-backend-crawler-recsys`, `data-oh-my-god`.

## Đã thực hiện

- `gcloud compute instances stop` thành công: `vota-ha-app-5v5g` (asia-southeast1-a), `vota-ha-app-xstn` (asia-southeast1-b), `vota-ha-app-jlb1` (asia-southeast1-c), `vota-ha-pg-a` (asia-southeast1-a). Trạng thái: TERMINATED.
- Sau khi quota được giải phóng, MIG tạo được 3 VM mới theo template có log-opts: `vota-ha-app-l482`, `vota-ha-app-1z6c`, `vota-ha-app-jg7z`. Trạng thái: RUNNING, đang VERIFYING.
- MIG đang xoá 3 VM đã dừng (DELETING). Lỗi `QUOTA_EXCEEDED` trong danh sách là lỗi cũ.

## Chưa thực hiện

- `vota-ha-pg-b` và `vota-ha-pg-w` vẫn RUNNING. Lệnh dừng hai VM này bị bộ phân loại an toàn chặn, nên không thực hiện.

## Lệnh người dùng tự chạy (nếu vẫn muốn dừng hai VM này)

```bash
gcloud compute instances stop vota-ha-pg-b --zone=asia-southeast1-b --project=vinpearl-508801
gcloud compute instances stop vota-ha-pg-w --zone=asia-southeast1-c --project=vinpearl-508801
```

## Cần quyết định

- Ba VM app mới (`l482`, `1z6c`, `jg7z`) là VM staging-ha đang chạy. Nếu muốn dừng chúng theo yêu cầu, rolling update sẽ dừng ở giữa chừng và MIG có thể tạo lại VM. Cần xác nhận trước khi dừng.
- Dừng `vota-ha-pg-b` (leader hiện tại) và `vota-ha-pg-w` (witness): cụm Patroni còn lại không có quorum đầy đủ nếu cả hai dừng. Cụm HA không nhận traffic hiện tại (`db.vota.internal` vẫn trỏ primary cũ), nên ảnh hưởng là cụm HA ngừng hoạt động, không ảnh hưởng staging.

## Kiểm tra

- `gcloud compute instances list`: các VM staging (`vota-staging-db-replica`, `v-ota-db-dev`, `vota-backend-crawler-recsys`, `data-oh-my-god`) vẫn RUNNING.

## Còn lại / rủi ro

- Rolling update chưa xong (`isStable = false` tại thời điểm ghi entry).
- Phase 3 (di trú dữ liệu) và Phase 4 chưa làm.
