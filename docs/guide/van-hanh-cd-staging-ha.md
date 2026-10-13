# Vận hành CD staging-ha (cập nhật image không gián đoạn)

Phục vụ `docs/prd/deployment-plan.md` §6.1. Nguồn sự thật là mã: `infra/terraform/environments/staging-ha/slot-deploy.sh`, `scripts/roll-staging-ha-app-slots.sh`, `scripts/set-staging-ha-desired-images.sh`, `scripts/verify-staging-ha-app.sh`, `scripts/ci/*.sh` và các workflow `staging-ha-{app,crawler,infra}-cd.yml`, `staging-ha-image-build.yml`, `{backend,frontend,crawler}-ci-cd.yml`.

## 1. Cách hoạt động

### Luồng PR → merge → CD

- **PR:** Backend CI, Frontend CI, Crawler CI và HA CI chạy theo đường dẫn đổi. Build Docker trên PR không đẩy image: WIF chỉ nhận ref `main`/`release-mvp-*`. Thay vào đó, build chạy trên builder BuildKit cố định của runner (`scripts/ci/buildx-builder.sh`) và làm nóng cache cho build sau merge. Push mới vào PR huỷ run CI cũ.
- **Merge → `staging-ha-app-cd.yml`:**
  1. `plan` tính content key của backend và frontend (`scripts/ci/image-key.sh`: hash các thư mục mà Dockerfile COPY) và so với key trong last-good. Thành phần không đổi thì bỏ qua cả CI, build và migration.
  2. Gọi lại Backend CI / Frontend CI (`workflow_call`) làm cổng. CI đỏ thì không build, không deploy.
  3. `staging-ha-image-build.yml`: image có tag `key-<key>` đã có thì dùng lại digest, không build.
  4. `deploy`: migration (nếu backend đổi) → pin MIG `OPPORTUNISTIC` → ghi image mong muốn vào all-instances config của MIG → roll hai pha → verify → ghi last-good (ref, key, `git_sha`). Không chạy Terraform.
- **Khoá:** `concurrency: staging-ha-app` ở mức workflow. GitHub chỉ giữ một run chờ, và run mới hơn thay run chờ cũ. Điều này không làm mất thay đổi, vì run mới so key với last-good chứ không với commit trước.
- **Infra:** Terraform chỉ chạy ở `staging-ha-infra-cd.yml` (khoá `staging-ha-infra`, cổng `allowed_changes`, không roll VM). Image trong template chỉ là dự phòng.
- **Crawler:** `staging-ha-crawler-cd.yml` chạy cùng mẫu (key, CI gate, build-hoặc-tái-dùng), khoá và last-good riêng. Image crawler copy toàn bộ `src/backend`, nên mọi thay đổi backend đều làm đổi key của crawler.

### Trên VM (`slot-deploy.sh`)

- Mỗi VM app chạy **hai slot**: blue (backend `:8001`, frontend `:3001`) và green (`:8002`, `:3002`). Proxy nginx giữ cổng `3000`, là cổng LB và health check dùng. Mỗi lúc chỉ một slot nhận traffic.
- URL gọi ngược chính backend (`ITINERARY_SERVICE_BASE_URL`, `ASSISTANT_API_BASE_URL`) được ghi đè theo port của slot trong `compose.slot.yml` (service `backend`). Secret `vota-ha-backend-env` vẫn giữ `:8000` của kiểu cũ và không cần đổi, vì blue và green dùng hai port khác nhau. URL loopback mới của backend khai báo ở cùng chỗ đó.
- `prepare`, chạy song song trên mọi VM: dựng slot còn lại, chép `/_next/static` của image frontend vào kho `/etc/vota/proxy/static-store`, rồi đợi `/health/ready`. Slot đó được ghi vào `/etc/vota/pending-slot`. Prepare lỗi trên một VM thì `abort` trên mọi VM; slot đang phục vụ không bị đụng.
- `switch`, chạy trên VM đầu (canary) rồi các VM còn lại song song: đổi upstream nginx (`nginx -c … -s reload`), kiểm qua `:3000`, rút slot cũ sau 110 s (chạy nền). Lỗi thì đổi lại slot cũ.
- Kho tĩnh: nginx trả `/_next/static/*` từ kho trước, thiếu mới hỏi frontend. Asset của mọi phiên bản trong 14 ngày (`STATIC_KEEP_DAYS`) đều còn, nên trình duyệt đang chạy bản cũ không bị 404 chunk.
- Script slot được gửi qua **stdin** kèm checksum; VM chỉ ghi lại khi nội dung khác. Trước đây gửi trong tham số `--command`: mỗi VM chờ 240 s giữa lúc mở phiên SSH và lệnh `sudo` đầu tiên (journal của VM ngày 12/10). Log roll in `REMOTE_START` và mốc `[roll +Ns]` để đo.
- VM do autoscaler hoặc autohealing tạo đọc `vota-backend-image` và `vota-frontend-image` từ metadata (all-instances config). Thiếu hoặc sai dạng thì dùng image trong template. Sau switch, roll liệt kê lại MIG: VM mới cũng được đưa về image đích, và mọi VM phải báo đúng image (mode `report`).
- Lỗi hoặc run bị huỷ thì bước rollback (`failure() || cancelled()`) ghi lại image mong muốn = last-good và roll về đó.
- **Migration** chạy trước roll, và bản cũ vẫn phục vụ trong lúc roll. Vì vậy migration phải tương thích ngược: thêm cột hay bảng ở lần phát hành này, chỉ xoá hoặc đổi ở lần sau khi không còn bản cũ đọc chúng.
- **Đo gián đoạn:** `scripts/probe-staging-ha.sh` gọi `/health/ready` và `/` qua public endpoint mỗi giây trong lúc deploy, rồi ghi tóm tắt vào Summary của run. Nó chỉ đo, không làm job lỗi.
- Staging-HA chạy **24/7**: không gắn lịch tắt/bật vào VM (xác nhận 2026-10-12). Job Cloud Scheduler tắt app đang `PAUSED`; hai job `alert-mute` chỉ tắt cảnh báo ban đêm.
- **Runner:** mọi CI/CD chạy trên một VM `vota-ci-runner` (7 tiến trình runner). Alert `CI: runner tự host không chạy` báo khi VM không gửi metric uptime trong 10 phút.

## 2. Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| `Error acquiring the state lock` ở bước apply | Lock mồ côi (vd. `terraform plan` tay bị dừng) | Đọc `gcloud storage cat gs://<bucket>/infra/staging-ha/default.tflock`, chắc không còn tiến trình terraform nào giữ nó, rồi `terraform force-unlock <generation của object>` (số, không phải UUID trong nội dung). Không apply/plan tay trên state chung khi CD có thể đang chạy |
| `Plan có thay đổi ngoài phạm vi cho phép` | Mã khác state: ai đó apply tay, commit chưa có trong nhánh đang deploy, hoặc thay đổi hạ tầng mới | Chạy `terraform plan` chỉ đọc, xem thuộc tính nào đổi. Nếu đúng ý thì thêm địa chỉ vào `allowed_changes` của `scripts/deploy-staging-ha-app.sh` kèm chú thích; nếu không thì đưa mã về khớp state. Không nới allowlist để "cho qua" |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | VM bị MIG tạo lại, khoá SSH host mới | Đã xử lý bằng `--strict-host-key-checking=no` trong script roll |
| Bước roll chỉ cập nhật một VM | `ssh` nuốt stdin của vòng lặp | Đã xử lý bằng `< /dev/null` và test hành vi |
| `403 Forbidden` / `failed to fetch anonymous token` khi đẩy image | Các runner chung một HOME nên `docker logout` của job khác xoá đăng nhập | Mỗi job build dùng `DOCKER_CONFIG` riêng (bước "Isolate Docker credentials per job") |
| VM app trở về bố cục kiểu cũ (`vota-backend`, không proxy) | Autohealing tạo lại VM từ template mà instance đang giữ | Lần roll kế chuyển lại sang slot; kiểm `compute.instances.repair.recreateInstance` trong audit log |
| `Canceling since a higher priority waiting request for staging-ha-app exists` | Khoá concurrency chỉ giữ một run chờ | Bình thường: run mới hơn so content key với last-good nên gồm cả thay đổi của run bị thay. Cần roll lại dù key không đổi thì `workflow_dispatch` với `force` |
| Hai VM chạy hai image khác nhau | Runner chết giữa lúc roll (rollback không chạy được) | `workflow_dispatch` `staging-ha-app-cd.yml` với `force`; roll đưa mọi VM về image đích |
| Mọi run CI/CD nằm `queued` | VM `vota-ci-runner` tắt | `gcloud compute instances start vota-ci-runner --zone asia-southeast1-b`; alert runner báo sau 10 phút |
| `prepare lỗi; mọi VM vẫn phục vụ bằng bản cũ` | Slot mới không ready (`READY_TIMEOUT` 600 s) hoặc thiếu RAM | Xem log `[vm prepare]` trong bước roll; slot đang phục vụ không bị đụng |

## 3. Kiểm tra nhanh trạng thái

```bash
gcloud compute instance-groups managed list-instances vota-ha-app --region asia-southeast1 --project <project>
gcloud storage cat gs://<bucket>/deploy/staging-ha-last-good.json | jq
gcloud compute ssh <vm> --zone <zone> --tunnel-through-iap --command 'sudo docker ps --format "{{.Names}} {{.Status}}"; cat /etc/vota/proxy/upstream.conf; cat /etc/vota/active-slot'
```

Trạng thái đúng: `upstream.conf` và `active-slot` khớp nhau, không còn `/etc/vota/pending-slot`, chỉ slot đang hoạt động còn chạy (slot cũ bị rút sau khoảng 2 phút), và image backend/frontend của mọi VM trùng last-good và trùng all-instances config:

```bash
gcloud compute instance-groups managed describe vota-ha-app --region asia-southeast1 --format='json(allInstancesConfig)'
```

## 4. Giới hạn đã biết

- Kết nối SSE dài hơn thời gian drain (100 s) vẫn bị cắt khi chuyển slot.
- Hai bản backend chạy song song trên VM 8 GB: script từ chối deploy nếu `MemAvailable` < 2200 MB; đỉnh RAM lúc nạp RecSys chưa đo.
- Mất hoặc thay VM duy nhất ngoài CD (host lỗi, đổi `machine_type`, boot image) vẫn là gián đoạn.
- Replica Patroni `pg-b` từng lệch timeline vì leader xoá WAL; chưa có WAL archive. Xử lý: `patronictl reinit` (xem `docs/guide/van-hanh-db-patroni.md` §5).
