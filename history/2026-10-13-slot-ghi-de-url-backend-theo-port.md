# Ghi đè URL gọi ngược backend theo port của slot

- Ngày: 2026-10-13
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: release-mvp-v2
- Trạng thái: hoàn thành (đã kiểm tra cấu trúc và render compose; chưa deploy lên VM)
- Phạm vi: infra (CI/CD staging-ha)
- Liên quan: `2026-10-12-cd-zero-downtime-slot.md`, `2026-10-12-sua-reload-proxy-slot.md`

## Mục tiêu

Trên VM staging-ha, hai URL gọi ngược chính backend trong env là `ITINERARY_SERVICE_BASE_URL` và `ASSISTANT_API_BASE_URL` đang trỏ `:8000` (port của kiểu cũ), lấy từ secret `vota-ha-backend-env`. Slot mới chạy ở `8001` (blue) hoặc `8002` (green). Cần URL đúng port của slot đang dựng.

## Phát hiện trong Secret Manager

Chỉ đọc tên khoá và host:port của URL, không in giá trị khác:

- `ITINERARY_SERVICE_BASE_URL` = `http://127.0.0.1:8000`
- `ASSISTANT_API_BASE_URL` = `http://127.0.0.1:8000/api/v1`
- `ITINERARY_DATA_MODE` = `inprocess`, nên hiện chưa dùng `ITINERARY_SERVICE_BASE_URL` (chỉ đọc ở mode `http`). `ASSISTANT_API_BASE_URL` chỉ `src/evaluation/agent/streamlit_app.py` đọc.
- Các URL còn lại trong secret không trỏ loopback của backend (Redis, DB qua pgbouncer `127.0.0.1:6432`, PUBLIC_WEB_URL, LANGSMITH_ENDPOINT), nên không cần ghi đè.

## Quyết định

- Ghi đè trong `compose.slot.yml` ở `environment:` của service `backend`, không đổi secret và không ghi lại `backend.env`. Compose cho `environment:` thắng `env_file:`, nên mỗi slot nhận đúng port khi container được tạo.
- Không đổi secret: blue và green dùng port khác nhau nên không có một giá trị nào đúng cho cả hai. Đổi giá trị secret dùng chung là việc của người chốt (`AGENTS.md` mục 3).
- Container đang chạy giữ env đã baked lúc tạo. Env mới áp dụng cho slot được dựng lại (đổi image, hoặc slot mới khi deploy).
- Thêm một khối `environment:` mới ở đúng service backend, không đổi `BACKEND_BASE_URL` của frontend (đã đúng từ trước).

## File thay đổi

- `infra/terraform/environments/staging-ha/slot-deploy.sh` — thêm: hai dòng `ITINERARY_SERVICE_BASE_URL` và `ASSISTANT_API_BASE_URL` trỏ `127.0.0.1:${BACKEND_PORT}` (có comment) trong service `backend` của `compose.slot.yml`.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py` — thêm: `test_backend_service_urls_follow_the_slot_port` (hai URL nằm trong khối backend, và không còn `127.0.0.1:8000` trong script).
- `docs/guide/van-hanh-cd-staging-ha.md` — thêm: một gạch đầu dòng ở mục "Cách hoạt động" về cách ghi đè URL theo slot.
- `history/2026-10-13-slot-ghi-de-url-backend-theo-port.md` — thêm: entry này.

## Kiểm tra

- `bash -n infra/terraform/environments/staging-ha/slot-deploy.sh`: OK.
- `python3 -m pytest infra/terraform/environments/staging-ha/tests`: 114 passed (gồm test mới).
- Sau khi merge `release-mvp-v2` (a10dd0a4): 125 passed, 2 failed. Hai test `RollVisitsEveryVm` (`test_every_running_vm_is_prepared_switched_and_checked`, `test_failed_prepare_aborts_everywhere_and_switches_nothing`) cũng lỗi trên chính `release-mvp-v2`, không do thay đổi này.
- `docker compose config` trên compose đã tách ra từ heredoc, với `backend.env` giả chứa `:8000` (không đụng VM): service `backend` của blue ra `ITINERARY_SERVICE_BASE_URL=http://127.0.0.1:8001` và `ASSISTANT_API_BASE_URL=http://127.0.0.1:8001/api/v1`; của green ra `8002`. Lệnh `--port` của uvicorn cũng khớp port slot.

## Còn lại / rủi ro

- Chưa deploy lên VM. Sau merge, `roll-staging-ha-app-slots.sh` đẩy script mới lên mỗi VM và chạy `prepare`/`switch`. `prepare` trả noop khi image không đổi, nên slot đang chạy chỉ nhận env mới ở lần đổi image kế tiếp (khi `prepare` dựng slot chờ).
- Secret `vota-ha-backend-env` vẫn giữ `:8000`. Không đổi cho tới khi người chốt quyết định. Nếu muốn xoá hai khoá để tránh nhầm, đó là một version mới của secret và cần xác nhận trước.
- `APP_PORT=8000` trong secret không thấy code nào đọc (`src/backend/app/core/config.py` chỉ khai báo). Không đổi.
- Chưa có kiểm thử trên VM thật: cần một lần roll (hoặc deploy app) để xác nhận `/health/ready` và env của slot mới.
