# Khôi phục link công khai cho monitor (`monitor` và `fresh-monitor`) và ghi vào guide deploy

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data (script VM), docs

## Mục tiêu

Người yêu cầu muốn deploy "như cũ": có một trang để mở bằng link và bấm chạy, không cần SSH; bảo mật tính sau.

Bản cũ (`f3f7795`, 25/09, entry `2026-09-25-public-monitor-dashboard.md`) mở monitor ra IP ngoài bằng
`MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1`. Sau các lần merge, lệnh `monitor` của `run_daily_docker.sh` (lệnh CD gọi) không còn
truyền hai biến này; chỉ `fresh-monitor` còn.

## File thay đổi

- `src/data_collection/run_daily_docker.sh` — sửa:
  - tách hàm `monitor_flags` (dựng `--host` / `--allow-public-host` từ `MONITOR_HOST` / `MONITOR_PUBLIC`);
  - `monitor` và `fresh-monitor` cùng dùng hàm này;
  - chú thích đầu file.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa:
  - bước "Restart crawler monitor" chạy `fresh-monitor` với hai biến public;
  - kiểm sau deploy qua link;
  - thêm mục "Monitor: link để xem và bấm chạy": firewall TCP 8765, cảnh báo chưa có đăng nhập, cách tắt.
- `history/2026-09-29-monitor-public-lai.md` — thêm: entry này.

## Quyết định

- Mặc định vẫn là `127.0.0.1`. Public chỉ bật khi đặt hai biến, như quyết định ngày 25/09.
- Không thêm đăng nhập hay giới hạn IP (người yêu cầu: "bảo mật tính sau"); guide ghi rõ rủi ro và cách giới hạn.
- Không sửa `.github/workflows`: đội deploy sửa theo guide (quyết định trước đó).

## Kiểm tra

- `bash -n src/data_collection/run_daily_docker.sh`: ok.
- Chạy với `docker` giả in tham số:
  - `monitor` mặc định → `--host 127.0.0.1`;
  - `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1 monitor` → `--host 0.0.0.0 --allow-public-host`;
  - `fresh-monitor` mặc định và public (`yes`, kèm `--port 9000`) cho kết quả tương tự;
  - `MONITOR_PUBLIC=maybe` bị từ chối.
- `tests/test_monitor_public.py`: 2 passed.
- `scripts/tests/test-backend-vm-cd-sync.sh`: passed.

## Còn lại / rủi ro

- Monitor công khai không có đăng nhập: ai có link đều điều khiển được job trên DB thật.
- Đội deploy thêm hai biến vào bước "Restart crawler monitor" và mở firewall TCP 8765 nếu bản 25/09 chưa mở.
- Chưa commit.
