# Phase 2.4: kiểm tra nối DB trực tiếp từ cấu hình cloud; phần xác thực do người dùng chạy

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra | ops
- Thay thế: `2026-10-08-phase2-chan-mig-va-check-db-direct.md` (lệnh chạy cần mật khẩu và `psql`; đã thay bằng các lệnh đọc cấu hình tôi chạy được và lệnh xác thực người dùng chạy)

## Mục tiêu

Phase 2.4: xác nhận VM nhóm HA nối được DB trực tiếp (firewall, DNS, `pg_hba`) và đủ chỗ cho số kết nối dự kiến (`ops/check-db-direct.sh`).

## Những gì đã kiểm chứng (chỉ đọc cấu hình, không vào VM)

Chạy từ máy làm việc, không SSH vào VM:

```bash
gcloud dns record-sets list --zone=vota-ha-internal --project=vinpearl-508801 --format='table(name,type,ttl,rrdatas)'
gcloud compute firewall-rules list --project=vinpearl-508801 --format='table(name,direction,sourceRanges.list(),allowed[].map().firewall_rule().list(),targetTags.list(),disabled)'
```

Kết quả:
- `db.vota.internal.` A `10.148.0.2` (TTL 30). Đây là primary cũ, chưa cutover sang ILB `10.148.0.34`.
- `db-replica.vota.internal.` A `10.148.0.4`.
- `default-allow-internal`: INGRESS từ `10.128.0.0/9`, mọi cổng TCP/UDP. VM HA (`10.148.x.x`) được phép tới `10.148.0.2:5432`.
- `vota-ha-pg-clients`: INGRESS `tcp:5432` vào target tag `vota-ha-pg`. Không có `sourceRanges` trong kết quả liệt kê, cần kiểm `sourceTags` nếu cần.

Kết luận từ cấu hình: đường mạng từ VM app tới DB đã được cho phép. Chưa kiểm chứng trên VM thật, vì không SSH được.

## Chưa kiểm chứng (cần chạy trên VM hoặc máy trong VPC)

- `pg_hba` và xác thực role `vota_app_login`: cần mật khẩu. Đây là việc người dùng chạy.
- Ngân sách kết nối (`POOLED=1`): cần kết quả xác thực ở trên.

## Lệnh người dùng chạy (xác thực + ngân sách kết nối)

Yêu cầu: máy có `psql` và có route tới VPC `10.148.0.0/16` (ví dụ một VM HA hoặc máy đã kết nối VPC). Tạo file mật khẩu chỉ người dùng đọc được (thay `<PASSWORD>`, không in ra màn hình):

```bash
umask 077 && printf '%s' '<PASSWORD>' > /tmp/vota_db_pw
```

Chạy kiểm tra từ thư mục gốc repo:

```bash
cd /Users/mac/Documents/VSF/vinpearl/Travel-Recommendation-Product && DB_HOST=db.vota.internal DB_USER=vota_app_login DB_PASSWORD_FILE=/tmp/vota_db_pw POOLED=1 ops/check-db-direct.sh
```

Xoá file mật khẩu:

```bash
rm -f /tmp/vota_db_pw
```

Kết quả mong đợi: `OK: kết nối vota_app_login@db.vota.internal:5432/vota` và dòng ngân sách `max_connections=... trần có pooler=...`, thoát mã 0. Gửi lại output (không kèm mật khẩu) để tôi ghi vào entry.

## Không làm được trong phiên này

- SSH vào VM app (`gcloud compute ssh ... --tunnel-through-iap`): bị bộ phân loại an toàn chặn.
- Đọc secret chứa mật khẩu DB: không được phép.

## Còn lại

- Phase 2.4 phần xác thực và ngân sách: lệnh ở trên.
- MIG `vota-ha-app` chưa `isStable`: nguyên nhân chưa xác định (xem `2026-10-08-phase2-chan-mig-va-check-db-direct.md`).
- Phase 2.5, 2.6, Phase 3, Phase 4: chưa làm.
