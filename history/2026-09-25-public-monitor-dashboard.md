# Mở public dashboard monitor crawler theo opt-in

- Ngày: 2026-09-25
- Tác giả: Người yêu cầu / Codex
- Nhánh: `dev`
- Trạng thái: hoàn thành phần source và image kiểm tra local; chưa push Artifact Registry hoặc restart VM
- Phạm vi: data, CI/CD

## Mục tiêu

Cho phép dashboard monitor crawler nghe trên external interface của VM trong thời gian tạm thời, không giới hạn IP theo yêu cầu vận hành. Chế độ mặc định vẫn chỉ nghe loopback.

## File thay đổi

- `src/data_collection/monitor.py` — thêm `--host`, `--allow-public-host` và host policy public opt-in.
- `src/data_collection/run_daily_docker.sh` — thêm `MONITOR_HOST` và `MONITOR_PUBLIC`, truyền cờ public vào monitor container.
- `src/data_collection/README.md` — ghi lệnh public với image Artifact Registry đang dùng và rủi ro của các POST endpoint điều khiển.
- `src/data_collection/tests/test_monitor_public.py` — thêm test local/public host policy.
- `history/2026-09-25-public-monitor-dashboard.md` — ghi quyết định và bằng chứng kiểm tra.

## Quyết định

- Giữ mặc định `127.0.0.1` và host validation local để không đổi hành vi an toàn hiện tại.
- Chỉ khi đặt `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1` thì monitor mới bind public và chấp nhận Host public.
- Không thêm giới hạn IP hoặc đăng nhập trong thay đổi này theo yêu cầu tạm thời; dashboard có POST endpoint điều khiển job, pipeline và token nên đây là cấu hình vận hành có rủi ro.
- Không đưa data, secret hoặc env file vào image. `Dockerfile.daily` đã COPY source monitor; build lại image là đủ.

## Kiểm tra

- Test đỏ trước khi sửa: `test_monitor_public.py` lỗi đúng vì chưa có `monitor.host_allowed`.
- `PYTHONPATH=src/data_collection python3 -m unittest src/data_collection/tests/test_monitor_public.py -v` → 2/2 PASS.
- `bash -n src/data_collection/run_daily_docker.sh` → PASS.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile src/data_collection/monitor.py src/data_collection/tests/test_monitor_public.py` → PASS.
- `docker build -f Dockerfile.daily -t vota-daily-monitor-public-test .` → PASS, image digest local `sha256:ca709ecbe56b2793d1bcd28ddedb2f82f7dac9fedd2d16f688333004d28f3ae3`.
- Smoke test Docker bind `0.0.0.0` với request `Host: 203.0.113.10:18766` tới `/api/health` → trả JSON health `200`.
- Chạy wrapper trong Linux container giả lập VM với `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1` → lệnh chứa `--host 0.0.0.0 --allow-public-host`.

## Còn lại / rủi ro

- Image kiểm tra mới chỉ tồn tại local với tag `vota-daily-monitor-public-test`; cần publish tag `latest`/SHA vào Artifact Registry trước khi VM pull.
- VM cần restart `vota-daily-monitor` sau khi pull image mới; crawler đang chạy không cần dừng.
- Khi hết nhu cầu public, restart monitor không đặt `MONITOR_HOST`/`MONITOR_PUBLIC` để quay về loopback.
