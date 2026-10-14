# Cảnh báo RAM, đĩa, CPU cho cụm DB và VM job cào, thêm ô đĩa và CPU vào dashboard HA

- Ngày: 2026-10-14
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/canh-bao-tai-nguyen-db-crawler (PR vào release-mvp-v2)
- Trạng thái: hoàn thành (đã apply lên GCP `vinpearl-508801`; đã commit và tạo PR)
- Phạm vi: infra (staging-ha), scripts (allowlist CD), docs (guide vận hành)
- Liên quan: `2026-10-13-canh-bao-bo-nho-va-dia-app-ha.md` (cảnh báo RAM, đĩa cho nhóm app), `2026-10-12-monitor-ha-do-tre-va-log.md` (dashboard), `2026-10-09-crawler-disk-15gb.md` (đĩa boot 15 GB của máy cào)

## Mục tiêu

Trước đó, cảnh báo RAM và đĩa chỉ có cho nhóm app. Cụm DB (pg-a, pg-b, pg-w) và VM job cào không có cảnh báo RAM, đĩa, CPU nào, và dashboard không có ô đĩa. Yêu cầu: thêm cảnh báo RAM, đĩa, CPU cho cụm DB và job cào; thêm ô đĩa theo VM và ô CPU cho crawler và pg vào dashboard. Toàn bộ chữ hiển thị bằng tiếng Việt.

## Số liệu căn cứ (chỉ đọc, 7 ngày đến 2026-10-14, theo giờ)

Đo bằng chuỗi thời gian Monitoring, aligner ALIGN_MEAN hoặc ALIGN_MAX theo giờ. Giờ hiển thị theo giờ Việt Nam.

| VM | RAM (min / p95 / max) | Đĩa đỉnh | CPU (p95 / max) |
|---|---|---|---|
| vota-ha-pg-a | 8,8 / 64,6 / 66,6 % | /dev/sda1 19,5 % | 8,4 / 12,6 % |
| vota-ha-pg-b | 9,9 / 64,6 / 65,7 % | /dev/sda1 19,3 % | 6,8 / 10,2 % |
| vota-ha-crawler | 15,9 / 31,8 / 57,8 % | /dev/sda1 77,7 % (13/10 10:00) | 65,4 / 101,1 % |

- Máy cào: CPU lên gần 100% đúng một giờ mỗi lượt, quanh 09:00 (các ngày 12, 13, 14/10). Không có chuỗi giờ liên tiếp nào trên 95%.
- Máy cào: đĩa 15 GB, đang dùng 43% sau khi pull image; mỗi image khoảng 3 GB (`2026-10-09-crawler-disk-15gb.md`).
- pg-w không có dữ liệu RAM, đĩa vì không cài Ops Agent (`patroni-node.sh.tftpl`: khối cài nằm trong nhánh `ROLE=db`). Không sửa việc này trong entry này.

## File thay đổi

- `infra/terraform/environments/staging-ha/variables.tf`: thêm 7 biến ngưỡng, mô tả tiếng Việt: `alert_db_memory_percent` (85), `alert_db_disk_percent` (80), `alert_db_cpu_percent` (70), `alert_crawler_memory_percent` (85), `alert_crawler_disk_percent` (80), `alert_crawler_cpu_percent` (95), `alert_crawler_cpu_minutes` (180).
- `infra/terraform/environments/staging-ha/patroni_monitoring.tf`: thêm locals `db_memory_filter`, `db_disk_filter`, `db_cpu_filter` và ba policy `db_memory_high`, `db_disk_high`, `db_cpu_high` (count = `var.create_patroni`).
- `infra/terraform/environments/staging-ha/crawler_monitoring.tf`: thêm locals `crawler_instance_id` (try), `crawler_memory_filter`, `crawler_disk_filter`, `crawler_cpu_filter` và ba policy `crawler_memory_high`, `crawler_disk_high`, `crawler_cpu_sustained` (count = `local.crawler_enabled`).
- `infra/terraform/environments/staging-ha/dashboard.tf`: thêm hai ô ở `yPos 41`: "CPU từng node DB và máy cào (tên VM, 1 = 100%)" và "Đĩa đã dùng từng VM (mã instance · thiết bị, %)". Ghi cách đối chiếu mã instance với tên VM trong ô mô tả đầu trang. Cập nhật comment đầu file.
- `infra/terraform/environments/staging-ha/tests/test_alerts.py`: thêm lớp `DbAndCrawlerResourceAlerts` (9 test).
- `infra/terraform/environments/staging-ha/tests/test_dashboard.py`: thêm 3 test (ô đĩa, ô CPU, ô mô tả); sửa test "RAM không có tên VM" để chỉ cắt đến ô CPU container (ô CPU mới ở cuối file làm test cũ sai).
- `scripts/deploy-staging-ha-app.sh`: thêm 6 địa chỉ `|create` vào `allowed_changes` (policy mới). `google_monitoring_dashboard.ha|update` đã có sẵn.
- `docs/guide/van-hanh-db-patroni.md`: thêm mục 8 "Cảnh báo RAM, đĩa, CPU của node DB" (bảng ngưỡng, việc đầu tiên, giới hạn).
- `docs/guide/van-hanh-crawler-db-noi-bo.md`: thêm ba cảnh báo tài nguyên vào mục 2.
- `history/2026-10-14-canh-bao-tai-nguyen-db-va-crawler.md`: entry này.

## Quyết định

- **Lọc RAM và đĩa theo nhãn, không theo tên.** DB: `metadata.user_labels.component="database"` và `role="patroni"` (nhãn có sẵn trên pg-a, pg-b, đã kiểm). Crawler không có nhãn, nên lọc theo `instance_id` lấy từ Terraform (`try(google_compute_instance.crawler[0].instance_id, "")`). Không sửa VM để thêm nhãn.
- **Tách theo mã instance (và thiết bị cho đĩa) bằng `group_by`.** Khác với nhóm app (không `group_by`, xem `2026-10-13-canh-bao-bo-nho-va-dia-app-ha.md`), node DB cố định nên không đổi tên khi thay VM. Email nêu đúng node.
- **CPU DB gồm cả pg-w** (lọc theo tiền tố `vota-ha-pg-`). CPU đo từ hypervisor, không cần Ops Agent, và witness cũng là một phần của cụm.
- **Crawler CPU: 95% liên tục 180 phút**, không phải vài phút. Lượt cào bình thường chạm gần 100% khoảng 1 giờ mỗi ngày, nên ngưỡng ngắn sẽ kêu mỗi ngày. Alert chỉ kêu khi tiến trình treo.
- **Crawler đĩa 80% sát đỉnh 77,7%.** Chọn 80% để cảnh báo trước khi đầy. Có thể kêu vào ngày cào lớn; xử lý bằng việc tăng đĩa, không nâng ngưỡng.
- **Absent (không có dữ liệu) cho RAM và đĩa**, mỗi cái 5–10 phút, cùng mẫu với nhóm app. Không có absent cho CPU vì CPU lấy từ hypervisor.
- **Kênh dùng chung `local.alert_channels`**, nên lịch mute 23:55–08:35 cũng áp dụng cho các alert mới. Đây là quyết định đã chốt 2026-10-12 (giữ mute cho mọi alert HA). Lưu ý: lượt cào quanh 09:00 nằm ngoài khung mute, nên alert CPU và đĩa của máy cào hoạt động trong lượt cào.
- **Không đổi PRD.** Đây là chi tiết vận hành, theo tiền lệ các entry monitor trước (`deployment-plan.md` §5 không quy định ngưỡng).

## Đã apply

- `terraform plan -target=...` (7 địa chỉ: 6 policy mới, dashboard): **6 to add, 1 to change, 0 to destroy**. Không có VM hay resource nào khác trong plan.
- `terraform apply` từ plan đã lưu: **6 added, 1 changed, 0 destroyed**.
- Đọc lại từ API: sáu policy đúng ngưỡng, đúng `duration`, đúng `group_by`, đều có một kênh. Dashboard có 18 ô (trước là 16), gồm ô đĩa và ô CPU mới.
- Tfvars dựng lại từ GCP (image digest của template và pg-a, service account, kênh email) nằm trong scratchpad của phiên, **ngoài repo**. Không ghi giá trị secret hay email vào entry.

## Kiểm tra

- `python3 infra/terraform/environments/staging-ha/tests/test_alerts.py`: 27 test OK.
- `python3 infra/terraform/environments/staging-ha/tests/test_dashboard.py`: 16 test OK.
- `terraform -chdir=infra/terraform/environments/staging-ha fmt -check -recursive`: sạch.
- `terraform validate` (sau `init -backend=false`): "The configuration is valid."
- Filter kiểm trên API trước khi viết Terraform (30 phút, chỉ đọc): RAM/đĩa theo nhãn chỉ khớp pg-a, pg-b; CPU theo tiền tố khớp pg-a, pg-b, pg-w; CPU theo tên và RAM theo `instance_id` của máy cào khớp đúng một VM.
- Số liệu sau apply (chỉ đọc): RAM DB 33–35% (app), 62–65% (pg), máy cào 66%; đĩa cao nhất 19,5% (DB) và 43% (máy cào); không có ngưỡng nào vượt tại thời điểm apply.

## Còn lại

- **pg-w chưa có RAM, đĩa, log.** Cần quyết định riêng: bật Ops Agent cho witness (đổi template của node quorum, cần plan và rollout có kiểm).
- **Chưa kiểm được alert kêu thật.** Các ngưỡng mới chưa có sự kiện thật. Theo dõi lượt cào ngày kế tiếp: ngưỡng đĩa máy cào (80%, đỉnh 77,7%) có thể kêu.
- **Ô đĩa dashboard** hiển thị cả VM đã xoá (ví dụ mã instance cũ của app và ci-runner) cho đến khi dữ liệu cũ hết hạn trong cửa sổ hiển thị.
- **Doc lệch GCP (không sửa entry cũ):** `2026-10-13-canh-bao-bo-nho-va-dia-app-ha.md` ghi "chưa apply" nhưng hai policy RAM và đĩa nhóm app đã có trên GCP.
- **CI apply sau merge:** sáu policy đã nằm trong state, nên lần plan CD sau merge không còn thay đổi cho chúng; allowlist đã sửa để không bị chặn nếu CD tạo lại từ đầu.
