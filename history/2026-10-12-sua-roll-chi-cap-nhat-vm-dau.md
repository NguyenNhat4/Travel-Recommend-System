# Sửa bước roll chỉ cập nhật VM đầu tiên (ssh nuốt stdin)

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/fix-roll-stdin
- Trạng thái: dang dở (đã sửa, test hành vi qua; chưa chạy lại trên CI)
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-10-12-sua-ssh-hostkey-roll.md`, `2026-10-12-cd-zero-downtime-slot.md`

## Triệu chứng

Frontend CD `38270933890` (`cb81fc45`) báo `success`, nhưng sau bước roll chỉ `vota-ha-app-fn9m` có bố cục slot (proxy, `vota-*-blue`); `vota-ha-app-9bbx` vẫn kiểu cũ (`vota-backend`, `vota-frontend`, không proxy). Bước roll chỉ chạy 4 phút. Các lần trước cũng chỉ thấy `fn9m` được xử lý.

## Nguyên nhân

`scripts/roll-staging-ha-app-slots.sh` lặp VM bằng `while read -r name zone; do ... done <<< "$vms"`. `gcloud compute ssh` (như `ssh`) đọc stdin nên nuốt phần còn lại của `$vms`; vòng lặp kết thúc sau VM đầu. Trước đó tôi gán nhầm cho autoscaler việc VM thứ hai không được chuyển.

## File thay đổi

- `scripts/roll-staging-ha-app-slots.sh` — sửa: `gcloud compute ssh ... < /dev/null`, kèm chú thích.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — thêm: test hành vi chạy script thật với `gcloud` giả có ssh đọc stdin, kiểm cả 3 VM giả đều được thăm. Test fail trước khi sửa (chỉ `vm-a`), qua sau khi sửa.

## Kiểm tra

- `bash -n`: OK; `pytest infra/terraform/environments/staging-ha/tests`: 108 passed.
- Chưa chạy lại trên CI thật.

## Còn lại / rủi ro

- Hiện `9bbx` vẫn kiểu cũ và chạy image cũ, trong khi `last-good` đã ghi frontend mới: fleet đang lệch. Cần một lần CD sau khi merge để chuyển `9bbx`.
- Lần chuyển kiểu cũ → slot trên `9bbx` là lần đầu trên VM này; có khoảng vài giây một lần giữa lúc frontend cũ nhả cổng 3000 và proxy bind cổng.
