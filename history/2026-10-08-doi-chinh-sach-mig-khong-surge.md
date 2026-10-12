# Đổi chính sách rolling update MIG vota-ha-app: không thể bỏ surge trên MIG regional

- Ngày: 2026-10-08
- Tác giả: Khoa15 / Claude (agent)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở
- Phạm vi: infra

## Mục tiêu

Rolling update của `vota-ha-app` bị treo vì `QUOTA_EXCEEDED` (`CPUS_ALL_REGIONS` 16/16; xem `history/2026-10-08-apply-staging-ha-quota-chan-rolling.md`). Người dùng không tăng được hạn mức, yêu cầu đổi chính sách để không cần surge.

## Kết quả thử nghiệm

- `max_surge_fixed = 0`, `max_unavailable_fixed = 1`: `terraform apply` thất bại với `Error 400: Fixed updatePolicy.maxUnavailable for regional managed instance group has to be either 0 or at least equal to <số zone>`.
- `max_surge_fixed = 0`, `max_unavailable_percent = 34`: thất bại với `Percent updatePolicy.maxUnavailable for regional managed instance group is only allowed for regional managed...` (API chỉ cho phép percent với MIG zonal).
- Kết luận: MIG regional trên 3 zone chỉ nhận `max_unavailable` = 0 hoặc ≥ 3. Không có cấu hình nào thay từng VM một mà không surge. `max_unavailable = 3` sẽ thay cả ba VM app cùng lúc (dừng app trong khoảng boot ~6 phút), nên không áp dụng.

Các lần thử đều thất bại ở bước cập nhật MIG, trước khi có thay đổi nào trên cloud. Cấu hình trong repo đã được hoàn nguyên về `max_surge_fixed = 3`, `max_unavailable_fixed = 0`, khớp với cloud (`terraform plan`: No changes; `unittest`: 51 OK).

## Trạng thái cloud hiện tại

- `vota-ha-app`: 3 VM cũ RUNNING (`5v5g`, `xstn`, `jlb1`), 3 VM mới ở trạng thái CREATING và thất bại do quota (`l482`, `1z6c`, `jg7z`). `isStable = false`.
- Dịch vụ không bị gián đoạn vì `max_unavailable = 0`.

## Lựa chọn còn lại (cần người dùng quyết)

1. Giải phóng quota ít nhất 6 vCPU cho ba VM surge: tạm dừng VM không thiết yếu. Cần người dùng xác định VM được phép dừng. Không tự dừng VM.
2. Thay thủ công từng VM app cũ (`gcloud compute instance-groups managed recreate-instances`), mỗi lần một VM, sau khi xác nhận VM mới healthy. Rủi ro: các VM surge đang CREATING có thể tranh quota với VM được tạo lại. Cần xử lý các VM CREATING trước.
3. Chuyển MIG sang zonal hoặc giới hạn `distribution_policy_zones` còn một zone rồi đặt `max_unavailable = 1`. Đây là thay đổi kiến trúc, không làm trong entry này.

## Phase 3 (hướng A) — chưa bắt đầu

Cần người dùng cung cấp:
- thời điểm cửa sổ dừng ghi trên primary cũ `10.148.0.2`;
- VM nào đang chạy cron crawler (repo không ghi rõ tên VM);
- VM staging đơn (`vota-backend-env`) có đang ghi vào primary cũ không.

Lệnh đầy đủ cho Phase 3 sẽ được viết sau khi ba điểm trên được xác nhận.

## Kiểm tra

- `python3 -m unittest discover -s infra/terraform/environments/staging-ha/tests -p 'test_*.py'`: 51 OK.
- `terraform validate`: OK.
- `terraform plan` (cấu hình hiện tại): No changes.

## Còn lại / rủi ro

- Rolling update vẫn treo; các VM CREATING có thể tiếp tục thử tạo lại.
- Phase 2.4, 2.5, 2.6; Phase 3; Phase 4.
- Đề xuất PRD `2026-10-08-staging-ha-patroni` ghi đường dẫn `infra/staging-ha` (đúng là `infra/terraform/environments/staging-ha`).
