# App CD: key `slot` để thay đổi cơ chế deploy cũng được roll

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: claude/cd-slot-key
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD)
- Liên quan: `2026-10-13-proxy-mime-types.md`, `2026-10-13-cd-staging-ha-mot-luong-hai-pha.md`

## Mục tiêu

PR #198 (`f9252021`) chỉ sửa `slot-deploy.sh` (nạp `mime.types` cho proxy). App CD run 38350386248 được kích hoạt nhưng plan báo backend và frontend không đổi key, nên bỏ qua deploy. Cấu hình proxy mới vì vậy không tới VM. Content key chỉ phủ đầu vào của image, không phủ cơ chế deploy.

## File thay đổi

- `scripts/ci/image-key.sh` — sửa: thêm thành phần `slot` (gồm `slot-deploy.sh` và `scripts/roll-staging-ha-app-slots.sh`).
- `.github/workflows/staging-ha-app-cd.yml` — sửa: plan tính thêm `slot_key`; deploy chạy khi `slot_changed` (roll lại với image hiện có, không qua CI/build); last-good ghi thêm `slot_key`.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — sửa: thêm test.

## Quyết định

- Không thêm CI gate cho thay đổi `slot`: HA CI và Backend CI đã chạy test cấu trúc và `bash -n` trên PR. Deploy dùng image đã qua CI.

## Kiểm tra

- Xem CI của PR. Kết quả CD sau merge: ghi trong báo cáo đánh giá ở phần trả lời của phiên làm việc.

## Còn lại / rủi ro

- Không có.
