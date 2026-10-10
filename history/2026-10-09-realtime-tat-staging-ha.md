# Tắt realtime trên staging-ha (phương án A): BACKEND_URL trống, tab báo rõ là tắt

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude Code (Haiku 5.5, thực hiện)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: dang dở (mã đã sửa và kiểm trong repo; chưa deploy monitor staging-ha)
- Phạm vi: scripts, data, docs
- Liên quan: `2026-10-09-monitor-staging-du-chuc-nang.md` (mục Realtime còn lại)

## Mục tiêu

Người yêu cầu chọn phương án A cho realtime trên staging-ha ("A nhé"): không lấy telemetry từ backend, và tab Realtime báo rõ là tắt thay vì báo lỗi kết nối tới `127.0.0.1:8000` trên VM crawler.

## Quyết định

- Phương án A chốt bởi người yêu cầu. Đích lâu dài là phương án B (Ops Agent scrape `/metrics` của backend và đẩy lên Cloud Monitoring). Chưa làm.
- Không tạo đề xuất PRD: người yêu cầu xác nhận "Không cần tạo PRD". Việc tắt realtime trên staging-ha lệch `docs/prd/deployment-plan.md` §5 (realtime là tính năng quan sát). Ghi nhận là tồn đọng có chủ đích theo quyết định này.
- Bỏ phương án ILB cho backend. Không có tài nguyên Terraform nào được tạo, nên không có gì để dọn.
- Phân biệt hai trạng thái:
  - `BACKEND_URL` đặt nhưng trống → tắt realtime (staging-ha).
  - Không đặt → mặc định `http://127.0.0.1:8000`, giữ hành vi cho máy dev (`local_crawl.sh monitor`).
- Chưa đổi kiến trúc tầng crawler (tách data disk, cutover `db.vota.internal`). Các việc này vẫn chờ người yêu cầu xác nhận riêng.

## File thay đổi

- `src/data_collection/monitor.py` — sửa `backend_calls`: `BACKEND_URL` đặt nhưng trống thì trả `{disabled: true, reason, events: []}`, không gọi mạng.
- `src/data_collection/monitor_ui/index.html` — sửa `realtimePage`: khi `disabled`, dừng polling và hiện card "Realtime đang tắt".
- `src/data_collection/run_daily_docker.sh` — sửa: `BACKEND_URL="${BACKEND_URL-…}"` (giữ giá trị rỗng); `cmd_backend` bỏ qua bước health khi `BACKEND_URL` trống.
- `scripts/deploy-staging-ha-crawler.sh` — sửa: lệnh `fresh-monitor` đặt `BACKEND_URL=''`, thêm comment trỏ tới entry này.
- `src/data_collection/README.md` — sửa: ghi Realtime đang tắt trên staging-ha và cách tắt.
- `src/data_collection/tests/test_monitor_backend_calls.py` — thêm test: `BACKEND_URL` trống không gọi mạng.
- `history/2026-10-09-realtime-tat-staging-ha.md` — thêm: entry này.

## Kiểm tra

- `python3 -m py_compile src/data_collection/monitor.py` → ok.
- `bash -n src/data_collection/run_daily_docker.sh` và `bash -n scripts/deploy-staging-ha-crawler.sh` → ok.
- Tách `<script>` của `monitor_ui/index.html` ra file tạm, `node --check` → ok.
- Venv tạm trong scratchpad (cài `src/data_collection/requirements.txt`): `tests/test_monitor_backend_calls.py`, `tests/test_monitor_public.py`, `tests/test_monitor_storage.py` → 9 tests OK.
- Bash: `${BACKEND_URL-mặc định}` khi không đặt → mặc định; khi đặt rỗng → rỗng (đã chạy thử).
- Chưa làm: mở trang Realtime trong trình duyệt; deploy lên VM; kiểm `backend` command với Docker thật.

## Còn lại / rủi ro

- Chưa deploy. VM staging-ha đang chạy image cũ, nên tab Realtime vẫn báo lỗi kết nối tới `127.0.0.1:8000` cho đến khi chạy `scripts/deploy-staging-ha-crawler.sh` với `CRAWLER_REF` mới. Việc deploy làm thay đổi monitor đang chạy, nên chưa chạy.
- Trên staging-ha, tab Realtime không dùng được cho đến khi làm phương án B. Điều này khác với yêu cầu "không API nào bị chặn". Người yêu cầu đã chọn A.
- Chưa commit.
