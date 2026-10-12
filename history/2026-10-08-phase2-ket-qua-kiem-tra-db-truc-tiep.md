# Phase 2.4: kết quả kiểm tra nối DB trực tiếp từ VM HA; ngân sách kết nối vượt ở mức đỉnh

- Ngày: 2026-10-08
- Tác giả: Khoa15 / người vận hành chạy lệnh; Claude (agent) ghi kết quả
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành (kiểm tra); dang dở (quyết định xử lý ngân sách)
- Phạm vi: ops | infra
- Thay thế: không. Bổ sung cho `2026-10-08-phase2-kiem-tra-db-truc-tiep-tu-cau-hinh.md`

## Mục tiêu

Chạy `ops/check-db-direct.sh` từ VM app HA để xác nhận: kết nối được tới `db.vota.internal:5432` bằng role app, và số kết nối dự kiến không vượt `max_connections`.

## Cách chạy

Trên VM `vota-ha-app-jg7z` (zone asia-southeast1-c), trong container `postgres:16` dùng mạng của VM (`--network host`). Script và hai file tạm được copy lên `/tmp` của VM rồi xoá sau khi chạy.

## Kết quả

```
OK: kết nối vota_db_dev@db.vota.internal:5432/vota
max_connections=100 đang dùng=23 trần có pooler=106 (VM=4 × role=2 × (pool=10 + dự phòng=2) + dự trữ=10)
FAIL: dự kiến 106 kết nối vượt max_connections=100: giảm worker, tăng max_connections hoặc bật pgbouncer
```

- Kết nối và xác thực: đạt. Role đọc từ `DATABASE_URL` là `vota_db_dev`.
- Ngân sách: không đạt ở mức đỉnh. `max_replicas = 4` (`variables.tf`), nên ngân sách tính với 4 VM.
- Ở mức tối thiểu 3 VM: 3 × 2 × 12 + 10 = 82, đạt (dưới 100).

## Lưu ý

- Kiểm tra này chạy trên primary cũ `10.148.0.2`, không phải cụm Patroni. Cụm Patroni có thể có `max_connections` khác; cần kiểm lại sau khi cutover.
- `db.vota.internal` hiện trỏ về primary cũ, nên ngân sách trên là ngân sách của primary cũ.

## Các lựa chọn xử lý (chưa chốt)

1. Tăng `max_connections` trên Patroni lên ≥ 120. Cần restart PostgreSQL, nên thuộc cửa sổ bảo trì.
2. Giảm `default_pool_size` trong `infrastructure/pgbouncer.ini` (hiện 10) xuống 8. Ngân sách 4 VM còn 4 × 2 × 10 + 10 = 90.
3. Giữ nguyên và chấp nhận rủi ro khi autoscale lên 4 VM. Không khuyến nghị.

## Dọn file tạm

Chạy trên máy bạn để xoá file trên VM và trên máy:

```bash
gcloud compute ssh vota-ha-app-jg7z --zone=asia-southeast1-c --project=vinpearl-508801 --tunnel-through-iap --command 'rm -f /tmp/vota_db_pw /tmp/vota_db_user /tmp/check-db-direct.sh'
rm -f /tmp/vota_db_pw /tmp/vota_db_user
```

## Còn lại

- Chốt lựa chọn xử lý ngân sách kết nối.
- Phase 2.5 (Ops Agent trên VM staging) và 2.6 (plan `infra/monitoring`): chưa làm.
- MIG `vota-ha-app` chưa `isStable`: nguyên nhân chưa xác định.
- Phase 3 và Phase 4: chưa làm.
