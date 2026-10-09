# Rút ngắn CD staging-ha: chấp nhận downtime khi thay VM

- Ngày: 2026-10-09
- Người đề xuất: người dùng / agent (Claude)
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: người dùng, trong chỉ đạo phiên 2026-10-09 ("chấp Service downtime để đổi lại tốc độ"), 2026-10-09
- Áp dụng: `docs/prd/deployment-plan.md` §6.1 (2026-10-09); source và entry `history/2026-10-09-cd-nhanh-chap-nhan-downtime.md`
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §6.1 bước 3 ("hỗ trợ Zero-downtime rolling update")
- Mã FR/NFR: không có FR/NFR riêng; không đổi NFR nào trong `docs/prd/requirements.md`

## Lý do

Số đo từ GitHub Actions ngày 2026-10-09:

- **Staging-HA Backend CD** (run 37915686042): job Verify chờ `wait-until --stable` 937 giây (15,6 phút). Toàn run 45 phút, trong đó khoảng 25 phút xếp hàng sau run Frontend CD đang giữ concurrency group `staging-ha-cd`.
- **Staging-HA Frontend CD** (run 37915676125): chờ MIG ổn định 8 phút rồi lỗi `Internal error` từ API của Google; rollback thêm 1,5 phút.
- Nguyên nhân trong Terraform (`infra/terraform/environments/staging-ha/main.tf`, `update_policy`): `max_surge_fixed = 3` và `min_ready_sec = var.boot_to_ready_seconds` (mặc định 360 giây). Cấu hình này giữ được zero-downtime nhưng mỗi lần triển khai phải chờ thêm 6 phút sau khi VM qua liveness. Boot-to-ready đo ~230 giây.

Đánh đổi: mỗi lần triển khai, toàn bộ app (tối đa 2 VM) ngừng nhận traffic từ lúc VM cũ bị xoá tới khi VM mới đạt `/health/ready`, ước vài phút. Kết nối SSE đang chạy bị cắt. DB và Patroni không đổi.

## Nội dung đề xuất

Đoạn hiện tại (`deployment-plan.md` §6.1 bước 3):

> 3. Triển khai phiên bản Backend mới (hỗ trợ Zero-downtime rolling update).

Đoạn thay thế:

> 3. Triển khai phiên bản Backend mới. Staging-HA thay toàn bộ VM app một lượt và chấp nhận downtime ngắn (vài phút) để rút ngắn thời gian phát hành; không dùng VM surge. Cổng sẵn sàng là LB báo đủ VM HEALTHY và `/health/ready` qua public endpoint đạt 6 lần liên tiếp. Quyết định này áp dụng cho staging-HA; production chưa có quyết định riêng.

## Thay đổi source sau khi chốt

- `infra/terraform/environments/staging-ha/main.tf` (`update_policy`): `max_surge_fixed = 0`, `max_unavailable_fixed = 3` (MIG regional ba zone chỉ nhận 0 hoặc ≥ 3), `min_ready_sec = 0`.
- `infra/terraform/environments/staging-ha/variables.tf` (mô tả `boot_to_ready_seconds`): bỏ "min_ready_sec của rolling update".
- `scripts/deploy-staging-ha-app.sh`: `APP_SURGE` mặc định `0` (không còn cần quota cho VM surge).
- `.github/workflows/staging-ha-backend-cd.yml` và `.github/workflows/staging-ha-frontend-cd.yml`: bước Verify chờ LB báo đủ HEALTHY tối đa 10 phút, thay vì kiểm một lần ngay sau `wait-until --stable`. Lý do: không còn `min_ready_sec`, nên MIG có thể báo stable trước khi VM mới nạp xong RecSys.
- `.github/workflows/frontend-ci-cd.yml`: tách bước Docker build test thành job `docker_test` chạy song song với `quality`; `build_vm` đợi cả `e2e` và `docker_test`, giữ nguyên cổng không publish khi build lỗi.

## Ước lượng tác động (chưa đo lại trên CD thật)

- Rolling update của MIG: 937 giây → ước khoảng 5 phút (boot ~230 giây, cộng thời gian xoá VM cũ và kiểm LB). Cả Backend CD và Frontend CD đều được rút ngắn vì cùng một MIG.
- Frontend CI trên PR: critical path của `quality` ~9,5 phút → ~5,5 phút (Docker test 253 giây chạy song song). Chỉ đạt được khi có ít nhất hai runner tự host chạy song song.

## Rủi ro cần kiểm khi chạy thử

- `max_unavailable_fixed = 3` lớn hơn targetSize (2): cần kiểm `terraform plan` trên staging-HA thật, nếu GCP từ chối thì chọn giá trị khác ≥ 3.
- Nếu VM mới không lên trong 10 phút, Verify thất bại và rollback cũng đi qua rolling update có downtime.
- `ops/loadtest/ha-rolling-update-drill.sh` mô tả kịch bản rolling; cần rà soát nếu nó giả định không có downtime. Chưa sửa trong thay đổi này.
- Lỗi `Internal error` của Google khi chờ MIG (run Frontend CD 37915676125) không thuộc đề xuất này và chưa có nguyên nhân gốc.
