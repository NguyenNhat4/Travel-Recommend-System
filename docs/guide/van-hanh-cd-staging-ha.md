# Vận hành CD staging-ha (cập nhật image không gián đoạn)

Phục vụ `docs/prd/deployment-plan.md` §6.1. Nguồn sự thật là mã: `infra/terraform/environments/staging-ha/slot-deploy.sh`, `scripts/roll-staging-ha-app-slots.sh`, `scripts/pin-staging-ha-mig-opportunistic.sh`, `scripts/deploy-staging-ha-app.sh` và hai workflow `staging-ha-{backend,frontend}-cd.yml`.

## 1. Cách hoạt động

- Mỗi VM app chạy **hai slot** (blue: backend `:8001`, frontend `:3001`; green: `:8002`, `:3002`) và một proxy nginx giữ cổng `3000` (cổng LB và health check). Chỉ một slot nhận traffic.
- CD chạy theo thứ tự: pin MIG `OPPORTUNISTIC` → apply Terraform (chỉ đổi template) → `roll-staging-ha-app-slots.sh` đổi image từng VM (qua IAP SSH) → verify (VM RUNNING, LB HEALTHY, readiness công khai) → ghi last-good. Lỗi sau apply thì rollback (apply lại last-good và roll lại).
- Trên VM, `deploy`: dựng slot còn lại → đợi `/health/ready` → đổi upstream nginx (`nginx -c … -s reload`, kèm `-c`) → kiểm qua `:3000` → rút slot cũ sau 110 s (nền). Slot mới không ready thì giữ nguyên slot cũ.
- Hai lớp ngăn deploy chạy chồng: khoá `concurrency: staging-ha-app` ở job deploy (GitHub chỉ giữ MỘT job chờ, job chờ cũ hơn bị huỷ) và `flock` trên từng VM.
- Staging-HA chạy **24/7**: không gắn lịch tắt/bật vào VM (xác nhận 2026-10-12). Job Cloud Scheduler tắt app đang `PAUSED`; hai job `alert-mute` chỉ tắt cảnh báo ban đêm.

## 2. Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| `Error acquiring the state lock` ở bước apply | Lock mồ côi (vd. `terraform plan` tay bị dừng) | Đọc `gcloud storage cat gs://<bucket>/infra/staging-ha/default.tflock`, chắc không còn tiến trình terraform nào giữ nó, rồi `terraform force-unlock <generation của object>` (số, không phải UUID trong nội dung). Không apply/plan tay trên state chung khi CD có thể đang chạy |
| `Plan có thay đổi ngoài phạm vi cho phép` | Mã khác state: ai đó apply tay, commit chưa có trong nhánh đang deploy, hoặc thay đổi hạ tầng mới | Chạy `terraform plan` chỉ đọc, xem thuộc tính nào đổi. Nếu đúng ý thì thêm địa chỉ vào `allowed_changes` của `scripts/deploy-staging-ha-app.sh` kèm chú thích; nếu không thì đưa mã về khớp state. Không nới allowlist để "cho qua" |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | VM bị MIG tạo lại, khoá SSH host mới | Đã xử lý bằng `--strict-host-key-checking=no` trong script roll |
| Bước roll chỉ cập nhật một VM | `ssh` nuốt stdin của vòng lặp | Đã xử lý bằng `< /dev/null` và test hành vi |
| `403 Forbidden` / `failed to fetch anonymous token` khi đẩy image | Các runner chung một HOME nên `docker logout` của job khác xoá đăng nhập | Mỗi job build dùng `DOCKER_CONFIG` riêng (bước "Isolate Docker credentials per job") |
| VM app trở về bố cục kiểu cũ (`vota-backend`, không proxy) | Autohealing tạo lại VM từ template mà instance đang giữ | Lần roll kế chuyển lại sang slot; kiểm `compute.instances.repair.recreateInstance` trong audit log |
| `Canceling since a higher priority waiting request for staging-ha-app exists` | Khoá concurrency chỉ giữ một job chờ | Bình thường; push sau chứa trọn thay đổi của push trước. Cần deploy ngay thì `workflow_dispatch` |
| Hai VM chạy hai image khác nhau | Run bị huỷ giữa lúc roll | Chạy một deploy mới (không chồng run khác) để đưa cả hai về last-good |

## 3. Kiểm tra nhanh trạng thái

```bash
gcloud compute instance-groups managed list-instances vota-ha-app --region asia-southeast1 --project <project>
gcloud storage cat gs://<bucket>/deploy/staging-ha-last-good.json | jq
gcloud compute ssh <vm> --zone <zone> --tunnel-through-iap --command 'sudo docker ps --format "{{.Names}} {{.Status}}"; cat /etc/vota/proxy/upstream.conf; cat /etc/vota/active-slot'
```

Trạng thái đúng: `upstream.conf` và `active-slot` khớp nhau, chỉ slot đang hoạt động còn chạy (slot cũ bị rút sau ~2 phút), image backend/frontend của mọi VM trùng last-good.

## 4. Giới hạn đã biết

- Kết nối SSE dài hơn thời gian drain (100 s) vẫn bị cắt khi chuyển slot.
- Hai bản backend chạy song song trên VM 8 GB: script từ chối deploy nếu `MemAvailable` < 2200 MB; đỉnh RAM lúc nạp RecSys chưa đo.
- Mất hoặc thay VM duy nhất ngoài CD (host lỗi, đổi `machine_type`, boot image) vẫn là gián đoạn.
- Replica Patroni `pg-b` từng lệch timeline vì leader xoá WAL; chưa có WAL archive. Xử lý: `patronictl reinit` (xem `docs/guide/van-hanh-db-patroni.md` §5).
