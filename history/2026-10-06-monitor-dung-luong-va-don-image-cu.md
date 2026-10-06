# Monitor theo dõi dung lượng và dọn lượt cào cũ; deploy job cào tự xoá image cũ

- Ngày: 2026-10-06
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành (chưa chạy trên VM)
- Phạm vi: data, CI

## Mục tiêu

Người dùng báo ổ đĩa VM (34.142.132.251 — chạy chung backend, frontend, job cào, monitor) đang đầy; cần monitor theo dõi dung lượng và xoá được data cũ. Người dùng quyết không cần đề xuất PRD cho phần này ("Phần dung lượng không cần viết đề xuất đâu").

Đo qua monitor (chỉ đọc): các lượt cào còn giữ chỉ ~715 MB (7 lượt — image 30/09 còn `runs.keep` mặc định 7). Nguyên nhân chính nghi là image Docker cũ của job cào: deploy backend/frontend có `prune_old_images`, deploy job cào chỉ `docker pull` image mới mà không xoá bản cũ (mỗi bản vài GB).

## File thay đổi

- `src/data_collection/monitor.py` — sửa: `storage()` (đĩa VM qua `shutil.disk_usage`, dung lượng từng thư mục con của `/data`, từng lượt cào, lượt đang chạy), `storage_cleanup(keep)` (dùng `prune_runs`, luôn giữ lượt đang chạy, báo dung lượng giải phóng); route `GET /api/storage`, `POST /api/storage/cleanup` (cùng chốt `X-Requested-With` như các POST khác).
- `src/data_collection/monitor_ui/index.html` — sửa: tab "Dung lượng" (KPI đĩa, bảng thư mục, bảng lượt, form xoá lượt cũ có xác nhận).
- `src/data_collection/run_daily_docker.sh` — sửa: lệnh `prune-images <image>` giữ image vừa deploy + bản trước của cùng repository, xoá phần còn lại, `docker image prune -f`.
- `.github/workflows/crawler-ci-cd.yml` — sửa: sau khi monitor mới chạy, gọi `prune-images` (lỗi không làm hỏng deploy).
- `src/data_collection/README.md` — sửa: mục Dung lượng.
- Test: `src/data_collection/tests/test_monitor_storage.py` (4), `tests/test_runner_prune_images.py` (2).

## Kiểm tra

- `pytest src/data_collection/tests`: 508 passed, 21 skipped. `scripts/tests/test-install-vota-cron.sh`: pass. YAML workflow parse được.
- Monitor chạy local trên thư mục tạm: `/api/storage` trả đĩa + thư mục + lượt; cleanup giữ 2 xoá lượt cũ nhất (giải phóng 3 MB); POST thiếu header bị 403. Script trang qua `node --check`.

## Còn lại / rủi ro

- Lần deploy hôm nay vẫn phải kéo image mới khi đĩa đầy: cần dọn tay trước (`run_daily_docker.sh cleanup` qua SSH vào 34.142.132.251) — người dùng chưa có SSH vào VM này.
- Monitor public (cổng 8765, chưa đăng nhập) nay có thêm nút xoá lượt cũ; cùng mức rủi ro với các nút chạy/dừng hiện có.
