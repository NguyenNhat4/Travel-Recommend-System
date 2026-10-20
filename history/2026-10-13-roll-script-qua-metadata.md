# Roll staging-ha: script slot qua metadata instance thay vì tải lên qua IAP

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: claude/roll-script-via-metadata
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD)
- Liên quan: `2026-10-13-cd-staging-ha-mot-luong-hai-pha.md`, `2026-10-13-sua-e2e-cong-va-allowlist-group-at-max.md`

## Mục tiêu

App CD đầu tiên chạy luồng mới (run 38343644399, commit `ace25eea`) đã rollback. Prepare trên `vota-ha-app-9bbx` lỗi với `WARNING: [0] Failed to send all data from [stdin]` và `client_loop: send disconnect: Broken pipe`. `abort` chạy trên mọi VM; probe ghi 990 request, 0 khác 200 trong 603 s.

Cùng run cho thấy khoảng chờ 240 s vẫn còn **ở mọi lần SSH trong CI**, kể cả prepare noop, switch và report. Journal của `vota-ha-app-fn9m` khi rollback:
- phiên SSH mở lúc 04:18:16.0;
- lệnh `sudo cmp` (ngay sau `cat > tmp`) chạy lúc 04:22:16.2.

Vậy thời gian mất vào việc tải khoảng 27 KB lên qua IAP tunnel. Trước đó, script gửi qua tham số `--command` cũng bị đúng như vậy. Ngoài CI (gcloud trên runner, không dùng credential WIF) cùng lệnh chỉ mất 3–7 s; Crawler CD gửi tar nhỏ trong CI cũng chỉ khoảng 4 s.

Infra CD (run 38343644234) bị cổng dừng ở `google_monitoring_alert_policy.ci_runner_down|update`, vì `c8e52d98` dịch `display_name` của alert sau khi alert đã được tạo.

## File thay đổi

- `scripts/roll-staging-ha-app-slots.sh` — sửa: `push_script` ghi script slot vào metadata `vota-slot-deploy` của từng VM (`gcloud compute instances add-metadata --metadata-from-file`, song song), trước lần SSH đầu tiên. VM đọc script từ metadata server và kiểm checksum. SSH dùng `< /dev/null`; lệnh chỉ còn vài trăm byte.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — sửa: stub `add-metadata`; test mọi VM nhận metadata trước prepare; test không còn tải script qua IAP.
- `scripts/deploy-staging-ha-app.sh` — sửa: allowlist `google_monitoring_alert_policy.ci_runner_down|update`.

## Quyết định

- Không cài NumPy cho gcloud trên runner. Đó là cấu hình ngoài repo, mất khi dựng lại runner, và không chắc giải quyết được việc đứt kết nối. Metadata instance không cần thêm quyền: CI SA đã có `compute.instanceAdmin.v1`. Giới hạn 256 KB mỗi giá trị, còn script khoảng 27 KB.

## Kiểm tra

- 8 file test staging-ha chạy trên runner (Debian 12, bash 5): pass.
- Kết quả CI của PR và CD sau merge: ghi trong báo cáo đánh giá ở phần trả lời của phiên làm việc.

## Còn lại / rủi ro

- Script slot nằm trong metadata của instance, đọc được bởi ai xem được metadata VM. Script không chứa secret.
