# CD staging-ha một luồng có CI gate, image ngoài Terraform, roll hai pha

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: claude/cicd-review-53f208 (PR vào release-mvp-v2, gộp chung với `2026-10-13-go-ci-cd-staging-cu.md`)
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD), docs
- Liên quan: `docs/prd/update-archive/2026-10-13-cd-staging-ha-mot-luong-hai-pha.md`, `2026-10-13-go-ci-cd-staging-cu.md`, `2026-10-13-toi-uu-ci-cd-staging-ha.md`

## Mục tiêu

Áp dụng mọi giải pháp của bản review CI/CD ngày 13/10 trong một PR. Các tiêu chí người dùng đặt ra:
- PR nào cũng chạy CI; merge xong mới chạy CD.
- Biết có nên build lại image của PR đã merge không.
- Cả hai VM (mỗi VM có frontend và backend) đều nhận bản mới nhất.
- Deploy nhanh, downtime thấp, image gọn, không có bước thừa hay chỗ gây kẹt.

## Số đo trước khi sửa (run 38281842451, 38281939005; GCP và Artifact Registry ngày 12–13/10)

- Từ lúc merge tới khi bản mới chạy: backend khoảng 16 phút, frontend khoảng 21 phút. Bước roll 2 VM tuần tự mất 666 và 690 s. Build frontend mất 448 s, trong đó 210 s chỉ để tải cache GHA.
- Mỗi VM chờ đúng 240 s giữa lúc phiên SSH mở và lệnh `sudo tee` đầu tiên. Journal của `vota-ha-app-fn9m`: session mở lúc 17:12:37.29, `sudo tee` chạy lúc 17:16:37.55. Không tái hiện được ngoài CI: SSH từ runner (user `runner`, có cả script 27 KB) chỉ mất 3–6 s. Trong CI, Crawler CD với lệnh nhỏ qua stdin mất khoảng 4 s mỗi lần SSH. Đã đổi sang gửi script qua stdin; log có `REMOTE_START` để đo lại.
- Deploy backend bị huỷ khi đang chờ trong group `staging-ha-app` ba lần (run 38272248211, 38275384939, 38281939121). Last-good lúc đo vẫn là backend `sha256:bf620ec6…` (commit `123c6799`), tức PR #174 chưa lên staging.
- VM `vota-ci-runner` bị dừng lúc 17:44 UTC ngày 12/10 (operation `stop`). Lệnh này giết run 38285276104 giữa lúc roll, và rollback không chạy vì chỉ có `if: failure()`. Sau đó 15 run nằm `queued`. Agent đã bật lại VM lúc khoảng 02:14 UTC ngày 13/10.
- Image nén: backend 678 MB, frontend 103 MB, crawler 1116 MB. Crawler dùng `transformers>=4.44,<5` và `torch>=2.3` không ghim, trong khi backend dùng `transformers==5.18.0` và `torch==2.14.1`.

## File thay đổi

- `docs/prd/update-archive/2026-10-13-cd-staging-ha-mot-luong-hai-pha.md` — thêm: đề xuất, trạng thái đã áp dụng.
- `docs/prd/deployment-plan.md` — sửa §6.1 bước 1–4 và sơ đồ luồng.
- `docs/guide/van-hanh-cd-staging-ha.md` — sửa: mô tả luồng mới, thêm sự cố runner tắt và prepare lỗi.
- `.github/workflows/staging-ha-app-cd.yml` — thêm: CD gộp backend và frontend (plan theo content key, CI gate, build-hoặc-tái-dùng, migration, image mong muốn, roll hai pha, probe, verify, last-good kèm key, rollback khi `failure() || cancelled()`).
- `.github/workflows/staging-ha-image-build.yml` — thêm: build-hoặc-tái-dùng image theo key, builder BuildKit cố định.
- `.github/workflows/staging-ha-{backend,frontend}-cd.yml`, `staging-ha-{backend,frontend}-build.yml` — xoá.
- `.github/workflows/{backend,frontend,crawler}-ci-cd.yml` — sửa: thêm `workflow_call`; bỏ `push` và `closed`; build trên PR dùng builder cố định; phụ thuộc Python cài vào thư mục riêng; thêm timeout; frontend thêm path `src/shared/mocks`; crawler thêm path `src/backend/**`.
- `.github/workflows/staging-ha-crawler-cd.yml` — sửa: plan theo key, CI gate, image qua `staging-ha-image-build.yml`, thêm path `src/backend/**` và `ops-agent-crawler.yaml`, last-good ghi thêm key.
- `.github/workflows/staging-ha-infra-cd.yml` — sửa: khoá riêng `staging-ha-infra`, bỏ roll, verify bằng script, thêm path `infra/monitoring/**`.
- `.github/workflows/ha-checks.yml` — sửa: Terraform `1.15.8` (cùng bản với CD), timeout, phụ thuộc Python cài vào thư mục riêng.
- `infra/terraform/environments/staging-ha/slot-deploy.sh` — sửa: thêm mode `prepare`/`switch`/`abort`/`report`; `deploy` = prepare + switch; thêm kho `/_next/static` (`stash_static`, location nginx).
- `infra/terraform/environments/staging-ha/startup.sh.tftpl` — sửa: đọc image mong muốn từ metadata của instance, dự phòng bằng template.
- `infra/terraform/environments/staging-ha/main.tf` — sửa: MIG `ignore_changes = [target_size, all_instances_config]`.
- `infra/terraform/environments/staging-ha/monitoring.tf`, `variables.tf` — sửa: alert `ci_runner_down`, biến `ci_runner_instance_name`.
- `infra/terraform/environments/staging-ha/crawler.tf` — sửa ghi chú.
- `infra/terraform/environments/staging-ha/tests/test_slot_deploy.py`, `test_resilience.py` — sửa test theo luồng mới; thêm test hai pha, abort, kho tĩnh, CD không chạy Terraform, CI gate, content key phủ mọi COPY.
- `scripts/roll-staging-ha-app-slots.sh` — viết lại: hai pha, gửi script qua stdin kèm checksum, kiểm cả VM mới, mốc thời gian.
- `scripts/set-staging-ha-desired-images.sh`, `scripts/verify-staging-ha-app.sh`, `scripts/probe-staging-ha.sh` — thêm.
- `scripts/ci/image-key.sh`, `scripts/ci/buildx-builder.sh`, `scripts/ci/py-deps.sh` — thêm.
- `scripts/deploy-staging-ha-app.sh` — sửa: allowlist `google_monitoring_alert_policy.ci_runner_down|create`, ghi chú "chỉ infra CD gọi".
- `scripts/deploy-staging-ha-crawler.sh` — sửa ghi chú.
- `Dockerfile.backend`, `src/frontend/Dockerfile.web` — sửa: cache mount cho pip, npm và `.next/cache`.
- `Dockerfile.fresh-catalog`, `src/backend/jobs/requirements.txt` — sửa: ghim torch và transformers giống backend, tách stage model, cache mount, kiểm embed lúc build.

## Quyết định

- Image không đẩy lên từ PR, vì WIF provider chỉ nhận ref `main`/`release-mvp-*` (`attributeCondition`). Sửa điều kiện này là đổi cấu hình bảo mật, nên agent không làm. Thay vào đó:
  - PR build trên builder BuildKit cố định của runner để làm nóng cache;
  - CD tái dùng image theo content key, và chỉ build thành phần có key đổi so với last-good.
- Image mong muốn đặt ở all-instances config của MIG, không đặt ở bucket GCS: CI SA không có quyền tạo bucket, và tránh cấp thêm IAM.
- Chống lệch chunk Next.js bằng kho tĩnh trên mỗi VM, trong thư mục proxy đã mount sẵn, nên không phải tạo lại proxy. Asset của bản mới được chép vào ở pha prepare trên mọi VM, trước khi VM nào switch.
- Không làm, kèm lý do:
  - ONNX/int8 thay torch: vector đổi, cần chạy bench search và reindex `ProductE5` theo quy trình đánh giá. Đây là task riêng.
  - Base `node:alpine` cho frontend: lợi khoảng 40 MB, có rủi ro với module native.
  - Tách runner CI và runner CD: cần quyền admin repo để đăng ký runner (API trả 404). Thay bằng alert runner không chạy.
  - `terraform plan` trên PR: PR không xác thực được qua WIF.
- Probe chỉ đo, không làm job lỗi, để một lần chập chờn qua Cloudflare không kích hoạt rollback.

## Kiểm tra

- (cập nhật sau khi chạy)

## Còn lại / rủi ro

- (cập nhật sau khi chạy)
