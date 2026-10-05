# Failover DB một lệnh (6.2)

- Ngày: 2026-10-05
- Tác giả: Khoa / Claude
- Nhánh: khoa/ha-load-balancing
- Trạng thái: hoàn thành
- Phạm vi: ops | docs

## Mục tiêu

Failover tay từ nhiều bước (sửa tunnel và `DATABASE_URL` trên từng VM, deploy lại) thành một lệnh có kiểm điều kiện, nhờ DB nay có tên ổn định `db.vota.internal`.

## File thay đổi

- `ops/promote-db-replica.sh` — thêm: dry run mặc định, `--yes` để chạy: kiểm standby, tắt primary, chờ replay, `pg_promote`, đổi DNS
- `ops/tests/test_promote_db_replica.sh` — thêm: 4 ca trên cặp Postgres 16 primary/replica streaming thật (gcloud giả)
- `docs/guide/van-hanh-db-replica.md` — sửa: mục 6 thêm đường một lệnh, giữ đường tay cho app VM đơn
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: use case và dòng 6.2

## Quyết định

- Không failover tự động: người vận hành quyết định (đã ghi rõ; Patroni/Cloud SQL HA là quyết định riêng).
- Luôn tắt hẳn primary trước khi promote để tránh hai primary cùng ghi.
- Từ chối chạy khi replica không còn là standby (không làm gì thêm, an toàn chạy lại).
- Use case: primary chết 20:03 khi có 8 đơn đang chờ thanh toán (plan §3b).

## Kiểm tra

- `bash ops/tests/test_promote_db_replica.sh`: PASS (dry run, thiếu biến, failover thật theo thứ tự dừng → promote → DNS, dữ liệu còn nguyên và ghi được, chạy lại từ chối). Cục bộ 2 giây. Lần chạy đầu lộ hai lỗi của chính test (thứ tự tham số `env`, chỉ số đối số gcloud giả), đã sửa.
- Chưa chạy: trên GCP thật (dừng VM, DNS Cloud, SSH vào replica).

## Còn lại / rủi ro

- Mất dữ liệu tối đa bằng độ trễ replication lúc primary chết; script in số byte WAL chưa replay.
- Sau failover phải dựng replica mới tay (guide mục 5); script nhắc nhưng không tự làm.
