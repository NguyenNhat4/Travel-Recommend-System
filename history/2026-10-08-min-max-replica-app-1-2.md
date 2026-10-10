# Nhóm app HA: min 1, max 2 VM; gỡ ràng buộc HA (N-1)/N

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành
- Phạm vi: infra | ops | docs

## Mục tiêu

Người vận hành chốt quy tắc: DB 1 primary + 1 replica (+ witness, tổng 3 máy); app tối thiểu 1 VM, tối đa 2 VM. Lý do: ngân sách kết nối với 4 VM là 106 > `max_connections` 100 trên primary cũ; với 2 VM là 58.

## File thay đổi

- `infra/terraform/environments/staging-ha/variables.tf` — sửa: `min_replicas` mặc định 1 (validation `>= 1`), `max_replicas` mặc định 2 (validation `>= min_replicas`); gỡ validation `cpu_target` và `memory_target_percent` theo công thức (N-1)/N, thay bằng khoảng giá trị hợp lệ.
- `infra/terraform/environments/staging-ha/tests/test_resilience.py` — sửa: thay test "sống sót khi mất 1 VM" bằng test khẳng định mặc định min 1 / max 2 và validation không còn chặn min 1.
- `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` — sửa: comment min/max theo quy tắc mới.
- `ops/check-db-direct.sh` — sửa: `VMS` mặc định 4 → 2.
- `ops/loadtest/ha-rolling-update-drill.sh` — sửa: `MIN_HEALTHY` mặc định 3 → 1.
- `docs/plan/2026-10-08-hoan-thanh-todo-ha.md` — thêm: plan cập nhật toàn bộ, thay các ghi chú kế hoạch rải rác.
- `history/2026-10-08-min-max-replica-app-1-2.md` — thêm: entry này.

`staging-ha.tfvars` (local, không commit) cũng được cập nhật comment min/max.

## Quyết định

- Chấp nhận có chủ đích: mất VM app duy nhất là mất dịch vụ app. Đây là hệ quả của `min = 1`, không phải lỗi.
- Không đổi `cpu_target` mặc định (0.55) và `memory_target_percent` (60). Với 1–2 VM vẫn hợp lệ.
- Không đổi cấu hình DB Patroni (2 node dữ liệu + witness đã khớp quy tắc).

## Kiểm tra

- `unittest discover staging-ha/tests`: 51 test OK.
- `terraform validate`: OK.
- `terraform plan`: `0 to add, 3 to change, 0 to destroy` (autoscaler + 2 alert policy).
- `terraform apply` plan đã review: thành công. Sau apply, VM `vota-ha-app-l482` bị MIG xoá (scale-in về 2 VM).
- `bash -n` cho `ops/check-db-direct.sh` và `ops/loadtest/ha-rolling-update-drill.sh`: OK.

## Còn lại / rủi ro

- Không kiểm tra PRD theo yêu cầu người vận hành (bỏ qua PRD). Nếu PRD có ràng buộc min ≥ 2, cần đề xuất riêng theo AGENTS.md mục 8.
- Ngưỡng alert "dưới min_replicas" với min 1 chỉ báo khi 0 VM.
- Rolling update MIG vẫn chưa `isStable`.
