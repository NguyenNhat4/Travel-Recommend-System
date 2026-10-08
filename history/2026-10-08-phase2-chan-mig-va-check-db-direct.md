# Phase 2: chẩn đoán MIG chưa ổn định và kiểm tra nối DB trực tiếp (2.4) bị chặn

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra | ops

## Mục tiêu

Người dùng yêu cầu hoàn thành Phase 2: tìm nguyên nhân MIG `vota-ha-app` chưa ổn định, và chạy kiểm tra nối DB trực tiếp (2.4) trên VM.

## Kết quả chẩn đoán MIG

- `targetSize = 3`; `versionTarget.isReached = True`; `isStable = False`.
- Ba VM mới `vota-ha-app-l482`, `vota-ha-app-1z6c`, `vota-ha-app-jg7z`: RUNNING, `currentAction = VERIFYING`, health check liveness `vota-ha-app-live` = HEALTHY.
- Load balancer `vota-ha-app` (backend service global): cả ba VM HEALTHY.
- Serial output của `vota-ha-app-l482`: startup script thoát với mã 0; các container `vota-pgbouncer`, `vota-backend`, `vota-frontend` đều đã Started.
- `updatePolicy` đọc từ cloud: `maxSurge = 3`, `maxUnavailable = 0`, `minReadySec = 360`, `replacementMethod = SUBSTITUTE`. Chính sách này khớp với code.
- Chưa tìm được điều kiện cụ thể đang giữ MIG ở `isStable = False`. Các VM đã HEALTHY lâu hơn `minReadySec`.

## Kết quả 2.4 (`ops/check-db-direct.sh`)

- Chưa chạy. Script cần `DB_PASSWORD_FILE` chứa mật khẩu role DB và cần `psql`; VM COS không có `psql`. Mật khẩu nằm trong secret, mà tôi không được phép đọc.

## Lệnh người dùng chạy (từ máy có `psql`, có route tới `db.vota.internal`)

Ghi mật khẩu vào file chỉ người dùng đọc được. Thay `<PASSWORD>` bằng mật khẩu role `vota_app_login` (không in ra màn hình):

```bash
umask 077 && printf '%s' '<PASSWORD>' > /tmp/vota_db_pw
```

Chạy kiểm tra:

```bash
cd /Users/mac/Documents/VSF/vinpearl/Travel-Recommendation-Product && DB_HOST=db.vota.internal DB_PASSWORD_FILE=/tmp/vota_db_pw POOLED=1 ops/check-db-direct.sh
```

Xoá file mật khẩu sau khi chạy:

```bash
rm -f /tmp/vota_db_pw
```

## Còn lại

- Tìm nguyên nhân MIG chưa ổn định: cần xem thêm (autohealing, lịch sử thao tác MIG, log readiness của VM mới).
- Phase 2.4 (kiểm tra DB trực tiếp trên VM): cần lệnh ở trên.
- Phase 2.5 (Ops Agent trên VM staging) và 2.6 (plan `infra/monitoring`): chưa làm.
- Phase 3 và Phase 4: chưa làm.
