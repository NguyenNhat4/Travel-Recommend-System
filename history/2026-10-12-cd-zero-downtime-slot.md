# CD staging-ha không làm sập app: chạy song song hai bản trong cùng một VM (slot blue/green)

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu, giữ `min_replicas = 1`) / Claude Code (agent)
- Nhánh: khoa/cd-zero-downtime-slot
- Trạng thái: dang dở (code xong, test cấu trúc qua; chưa chạy trên VM thật)
- Phạm vi: infra (CI/CD staging-ha, VM app, giám sát)

## Mục tiêu

Mỗi lần CD đổi template, MIG `vota-ha-app` (`PROACTIVE`, `max_surge_fixed = 0`) xoá hết VM rồi mới tạo VM mới. Ngày 2026-10-12 `https://praxis.io.vn/` trả 503 ("unconditional drop overload": LB không còn backend HEALTHY) nhiều lần. Yêu cầu: CD không được là nguyên nhân gây sập.

## Cách làm

- Trên mỗi VM chạy hai "slot" (blue: backend :8001, frontend :3001; green: :8002, :3002) và một proxy nginx cục bộ giữ cổng 3000 (cổng LB đang dùng, health check không đổi).
- Deploy: kéo image, dựng slot còn lại, đợi `/health/ready` của slot đó (3 lần liên tiếp, tối đa 600 s), đổi upstream của proxy bằng `nginx -s reload` (worker cũ giữ kết nối đang chạy, kể cả SSE), kiểm lại qua cổng 3000, rồi rút slot cũ sau 110 s (nền). Bản mới không ready thì bỏ bản mới, bản cũ không bị đụng.
- Terraform chỉ đổi template (mang image mới nhất để VM tạo sau này dùng đúng image). `update_policy.type = OPPORTUNISTIC` nên đổi template không tự thay VM. `min_replicas` giữ 1, không tốn thêm VM.
- CD: (1) `pin-staging-ha-mig-opportunistic.sh` đặt policy OPPORTUNISTIC trước khi apply, để lần chuyển đổi đầu tiên (MIG còn PROACTIVE) không tự thay VM; (2) `deploy-staging-ha-app.sh` apply template như cũ; (3) `roll-staging-ha-app-slots.sh` đẩy `slot-deploy.sh` lên từng VM qua IAP SSH và chạy `deploy`, kiểm VM chạy đúng image đích; (4) verify (VM RUNNING, LB HEALTHY, readiness công khai) và rollback (template + roll lại về last-good).
- VM kiểu cũ (một stack ở 3000/8000) được chuyển sang slot ở lần deploy đầu: dựng slot mới, đợi ready, cho frontend cũ tắt êm để nhả cổng 3000, bật proxy. Có một khoảng ngắn (vài giây, một lần duy nhất) giữa lúc frontend cũ nhả cổng và proxy bind cổng. Nếu cổng không được nhả sau 150 s thì khôi phục stack cũ.
- `refresh_config` làm mới env từ Secret Manager mỗi lần deploy trên VM dựng từ template mới (có `slot.env`); VM kiểu cũ giữ env hiện có. Lý do: trước đây thay VM đồng thời nạp lại env, giờ không còn.
- Watcher giám sát: dừng êm slot cũ (exit 0/143) là `planned_stop`, không phải `die`, để alert "service container stopped" không kêu ở mỗi deploy.

## File thay đổi

- `infra/terraform/environments/staging-ha/slot-deploy.sh` — thêm: script chạy trên VM (compose của slot, cấu hình nginx, mode boot/deploy/status).
- `infra/terraform/environments/staging-ha/compose.ha.yml` — xoá: nội dung chuyển vào `slot-deploy.sh` (một nguồn duy nhất, CD đẩy được lên cả VM cũ).
- `infra/terraform/environments/staging-ha/startup.sh.tftpl` — sửa: cài script, ghi `slot.env`, chạy `boot` thay cho đoạn tự dựng compose.
- `infra/terraform/environments/staging-ha/main.tf` — sửa: `update_policy.type = OPPORTUNISTIC`; truyền `slot_deploy` thay `compose` vào startup.
- `scripts/pin-staging-ha-mig-opportunistic.sh`, `scripts/roll-staging-ha-app-slots.sh` — thêm.
- `.github/workflows/staging-ha-backend-cd.yml`, `staging-ha-frontend-cd.yml` — sửa: thêm bước pin và roll, bỏ điều kiện "VM phải ở template mới", rollback cũng roll VM, thêm hai script vào `paths`.
- `infra/monitoring/vota-docker-event-watcher.py`, `infra/monitoring/tests/test_watcher_datetime.py` — sửa/thêm: `planned_stop`.
- `infra/terraform/environments/staging-ha/tests/test_resilience.py` — sửa; `tests/test_slot_deploy.py` — thêm.

## Quyết định

- Không viết đề xuất PRD và không cập nhật `docs/prd/deployment-plan.md` §6.1 (bước 3 vẫn ghi "chấp nhận downtime ngắn", theo chốt ngày 2026-10-09): theo chỉ đạo trực tiếp của người dùng. Hiện thực khác PRD ở điểm này; cần cập nhật PRD sau.
- Không đo đỉnh RAM/CPU trước khi làm (theo chỉ đạo). Thay bằng cổng an toàn: `mode_deploy` từ chối chạy nếu `MemAvailable` < 2200 MB.
- Không đổi `min_replicas`.

## Kiểm tra

- `bash -n` cho 3 script; `terraform fmt -check` và `terraform validate`: qua.
- `pytest infra/terraform/environments/staging-ha/tests`: 104 passed (gồm `test_slot_deploy.py` mới); `pytest infra/monitoring/tests`: 18 passed.
- `terraform plan` chỉ đọc trên nhánh này (tfvars của repo, last-good refs): `1 to add, 2 to change, 1 to destroy`; thay đổi: `google_compute_instance_template.app` (create,delete), `google_compute_region_instance_group_manager.app` (update), `google_monitoring_dashboard.ha` (update). Cả ba nằm trong allowlist của `deploy-staging-ha-app.sh`, nên cổng plan qua. Không apply.
- **Chưa chạy trên VM thật.** Chưa thử: `slot-deploy.sh deploy` (cả đường slot→slot lẫn legacy→slot), proxy giữ SSE khi reload, rollback.

## Còn lại / rủi ro

- Lần deploy đầu sau khi merge là lần chuyển legacy→slot trên VM đang chạy: đây là phép thử thật đầu tiên. Có một khoảng ngắn một lần (xem trên). Theo dõi sát lần chạy đầu.
- Hai bản chạy song song trên VM 8 GB (backend giới hạn 3 GiB mỗi bản): đỉnh RAM lúc nạp RecSys chưa đo. Nếu cổng RAM chặn, deploy sẽ lỗi (VM vẫn phục vụ bản cũ), không sập.
- Nếu `PATCH` policy của `pin-staging-ha-mig-opportunistic.sh` không nhận giá trị nào đó, bước này lỗi và deploy dừng trước khi apply.
- Tên container đổi thành `vota-backend-<slot>`/`vota-frontend-<slot>`: các chuỗi thời gian trên dashboard theo `container_name` sẽ đổi tên series. Watcher/collector trên VM cũ chưa có `planned_stop` cho tới khi VM được tạo lại, nên lần chuyển đầu có thể kêu alert `container stopped` một lần.
- Peer IP mà frontend thấy là 127.0.0.1 thay vì IP của LB (proxy cục bộ). Header `X-Forwarded-*` được giữ nguyên; chưa kiểm xem code có dùng peer IP không.
- Image nginx dùng tag `nginx:1.27-alpine`, chưa pin digest.
- SSE dài hơn thời gian drain vẫn bị cắt. Mất hoặc thay VM duy nhất ngoài CD (host lỗi, đổi `machine_type`, boot image) vẫn là gián đoạn.
- Nếu autoscaler tạo VM mới giữa lúc `roll` đang chạy, VM đó khởi động từ template (đã có image mới) nên không cần roll.
