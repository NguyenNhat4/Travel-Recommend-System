# CD staging-ha: một luồng ứng dụng có CI gate, image ngoài Terraform, roll hai pha

- Ngày: 2026-10-13
- Người đề xuất: hp09.com@gmail.com / Claude Code (agent)
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: hp09.com@gmail.com, 2026-10-13. Căn cứ là tin nhắn "Tôi muốn áp dụng tất cả giải pháp và gom PR 1, 2, 3 thành một PR duy nhất… đừng hỏi gì tôi", gửi ngay sau bản review có nêu PR 3 cần đề xuất PRD.
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §6.1 (bước 1, 3, 4)
- Mã FR/NFR: NFR-REL-02 (kế thừa); không thêm mã mới

## Lý do

Số đo ngày 12/10 (run 38281842451, 38281939005):
- Từ lúc merge tới khi bản mới chạy mất 16–21 phút, phần lớn là roll tuần tự từng VM (666–690 s).
- Deploy backend bị huỷ ba lần khi đang chờ, vì ba CD dùng chung một khoá và mỗi CD chỉ build phần đổi trong commit của nó.
- CD không đợi CI pass.
- Mỗi deploy ứng dụng chạy `terraform apply`, nên drift hạ tầng chặn được deploy ứng dụng.
- Hai VM lệch phiên bản khoảng 6 phút, đủ để trình duyệt nhận chunk Next.js của bản khác.

## Nội dung đề xuất

`deployment-plan.md` §6.1, bước 1. Hiện tại:

> 1. Xác nhận toàn bộ automated tests và contract validation đều PASS trên CI.

Thay bằng:

> 1. CI chạy trên mọi PR. Sau khi merge, CD gọi lại đúng CI đó (`workflow_call`) làm cổng: CI đỏ thì không build và không deploy.

Bước 3. Hiện tại là đoạn "Staging-HA cập nhật image không gián đoạn: … Terraform chỉ đổi template (MIG `OPPORTUNISTIC`, không thay VM). Mỗi lần chỉ một deploy chạy (khoá concurrency `staging-ha-app` và `flock` trên VM). Cổng sẵn sàng là LB báo đủ VM HEALTHY và `/health/ready` qua public endpoint đạt 6 lần liên tiếp. …"

Thay bằng:

> 3. Triển khai backend và frontend trong **một** luồng CD (`staging-ha-app-cd.yml`).
>    - CD so *content key* của từng thành phần (hash các thư mục đầu vào của image) với bản đang chạy (last-good). Chỉ thành phần đổi mới qua CI và build. Image có key đã tồn tại thì không build lại.
>    - Run mới nhất luôn chứa trọn mọi thay đổi chưa deploy, nên run đang chờ bị thay thế mà không mất thay đổi nào. Khoá `concurrency: staging-ha-app` đặt ở mức workflow và giữ `flock` trên VM.
>    - Image mong muốn được ghi vào *all-instances config* của MIG (metadata `vota-backend-image`, `vota-frontend-image`), để VM do autoscaler hoặc autohealing tạo khởi động đúng bản. Deploy ứng dụng **không chạy Terraform**; Terraform chỉ chạy ở `staging-ha-infra-cd.yml`.
>    - Roll theo hai pha. Pha `prepare` chạy song song trên mọi VM: dựng slot mới, đợi `/health/ready`, chép `/_next/static` vào kho tĩnh của proxy. Pha `switch`: đổi proxy trên VM đầu trước (canary), rồi các VM còn lại song song.
>    - Kho tĩnh giữ asset của các phiên bản gần đây, để trình duyệt đang chạy bản cũ không bị 404 chunk.
>    - Cổng sẵn sàng: mọi VM chạy đúng image đích, LB báo đủ VM HEALTHY, và `/health/ready` qua public endpoint đạt 3 lần liên tiếp (cách 5 s).
>    - Lỗi hoặc run bị huỷ thì đưa image mong muốn và các VM về last-good.
>    - Migration phải tương thích ngược với bản đang chạy (expand trước, contract ở lần phát hành sau), vì bản cũ và bản mới cùng chạy trong lúc roll.
>
>    Quyết định này áp dụng cho staging-HA; production chưa có quyết định riêng.

Bước 4. Hiện tại: "Triển khai phiên bản Frontend mới tương ứng."

Thay bằng:

> 4. Frontend đi cùng luồng ở bước 3; không còn CD frontend riêng.

## Thay đổi source sau khi chốt

- Workflow:
  - `.github/workflows/staging-ha-app-cd.yml`: thêm, thay cho `staging-ha-backend-cd.yml` và `staging-ha-frontend-cd.yml` (xoá).
  - `staging-ha-{backend,frontend}-build.yml` và `staging-ha-crawler-build.yml` (thêm): build-hoặc-tái-dùng theo content key, builder BuildKit cố định trên runner.
  - `{backend,frontend,crawler}-ci-cd.yml`: thêm `workflow_call`; bỏ `push` và `closed`.
  - `staging-ha-crawler-cd.yml`: CI gate và content key.
  - `staging-ha-infra-cd.yml`: khoá riêng, không roll.
  - `ha-checks.yml`: cùng phiên bản Terraform với CD.
- Script:
  - `infra/terraform/environments/staging-ha/slot-deploy.sh`: thêm mode `prepare`, `switch`, `abort`, `report` và kho tĩnh.
  - `scripts/roll-staging-ha-app-slots.sh`: roll hai pha, gửi script qua stdin.
  - Thêm `scripts/set-staging-ha-desired-images.sh`, `scripts/verify-staging-ha-app.sh`, `scripts/probe-staging-ha.sh`, `scripts/ci/*.sh`.
- Terraform:
  - `startup.sh.tftpl`: đọc image mong muốn từ metadata.
  - `main.tf`: MIG `ignore_changes = [all_instances_config]`.
  - `monitoring.tf`: alert khi runner CI không chạy.
  - `scripts/deploy-staging-ha-app.sh`: bổ sung allowlist.
- Image:
  - `Dockerfile.backend`, `src/frontend/Dockerfile.web`: dùng cache mount.
  - `Dockerfile.fresh-catalog`, `src/backend/jobs/requirements.txt`: ghim torch và transformers giống backend, tách stage model.
- Tài liệu: `docs/guide/van-hanh-cd-staging-ha.md`.
