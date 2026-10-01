# CI tự nối replication primary và replica

- Ngày: 2026-10-01
- Tác giả: Khoa / Claude
- Nhánh: khoa/infra-db-replication-ci
- Trạng thái: hoàn thành
- Phạm vi: docs (hạ tầng, CI/CD)

## Mục tiêu

Bước 2/2: hai DB thật sự connect với nhau mà không ai chạy lệnh tay. Sau khi hạ tầng được apply, CI chuẩn bị primary, dựng replica, cài giám sát và kiểm tra replication. Xếp chồng trên PR #75 (nhánh `khoa/infra-adopt-vms`).

## File thay đổi

- `ops/ci-db-replication.sh` — thêm: chạy trên runner, điều phối các script bootstrap qua IAP SSH, idempotent, có bước verify.
- `.github/workflows/infra-terraform-staging.yml` — sửa: thêm job `replication_staging` chạy sau apply; mở rộng `paths` của push để thay đổi script replication cũng chạy workflow.
- `ops/tests/test_infra_layout.sh` — sửa: kiểm tra script CI (không restart container, không in mật khẩu, có verify, có job trong workflow).
- `docs/guide/van-hanh-db-replica.md` — sửa: mục 1 mô tả luồng tự động thay cho các bước chạy tay.

## Quyết định

- Job trong cùng workflow infra, không dùng `workflow_run`: `workflow_run` chỉ dùng file workflow ở nhánh mặc định (`main`), trong khi các nhánh release cần chạy độc lập; `needs` giữ đúng thứ tự sau apply.
- Điều phối nằm trong `ops/ci-db-replication.sh` thay vì YAML dài, để kiểm cú pháp và đọc dễ hơn.
- Lấy IP bằng `gcloud compute instances describe`, không hard-code.
- Mật khẩu replicator đi qua pipe giữa hai lệnh `gcloud compute ssh` trên runner, `set +x`, không ghi file, không in ra log.
- Bỏ qua bootstrap khi primary đã thấy replica `streaming` và replica `pg_is_in_recovery()=t`: chạy lại không đụng gì.
- Primary chỉ nhận `pg_reload_conf()`, không restart.

## Kiểm tra

- `bash -n ops/ci-db-replication.sh`: pass.
- `bash ops/tests/test_infra_layout.sh`: PASS.
- Parse YAML workflow: ok.
- Chưa chạy end-to-end: chỉ chạy được trên GitHub sau khi PR #75 được merge và apply xong.

## Còn lại / rủi ro

- `gcloud compute ssh` vào primary (không bật OS Login) cần ghi khoá vào metadata; nếu service account CI thiếu quyền, bước preflight báo lỗi rõ ràng trước khi đổi bất cứ thứ gì.
- Lần chạy đầu cần cho phép `DB_IMAGE` đúng image primary (mặc định đã khớp `pgvector/pgvector:0.8.6-pg18-bookworm`).
- Alert replica cần biến `GCE_DB_REPLICA_INSTANCE` (đã có) và chạy lại workflow monitoring sau khi replica streaming.
- App chưa đọc từ replica (cần tunnel thứ hai và `READ_DATABASE_URL`); làm ở feature riêng.
