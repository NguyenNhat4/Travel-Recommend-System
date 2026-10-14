# Đánh giá CD staging-ha sau khi merge #192, #195, #197, #198, #199

- Ngày: 2026-10-13
- Tác giả: hp09.com@gmail.com (yêu cầu) / Claude Code (agent)
- Nhánh: claude/history-danh-gia-cd
- Trạng thái: hoàn thành
- Phạm vi: infra (CI/CD)
- Liên quan: `2026-10-13-cd-staging-ha-mot-luong-hai-pha.md`, `2026-10-13-sua-e2e-cong-va-allowlist-group-at-max.md`, `2026-10-13-roll-script-qua-metadata.md`, `2026-10-13-proxy-mime-types.md`, `2026-10-13-cd-slot-key.md`

## Mục tiêu

Ghi kết quả các lần CD thật sau khi merge, để đối chiếu với các tiêu chí CI/CD mà người dùng đặt ra.

## File thay đổi

- `history/2026-10-13-danh-gia-cd-staging-ha-sau-merge.md` — thêm.

## Kết quả đo

| Run | Commit | Kết quả |
|---|---|---|
| App CD 38340468294 | `cabbfa22` (#192) | Cổng CI chặn: Frontend E2E đụng cổng 3100 với một job khác. Không build frontend, không deploy. |
| Crawler CD 38340468448 | `cabbfa22` | Thành công trong 8,5 phút. |
| Infra CD 38340468098, 38343644234 | `cabbfa22`, `ace25eea` | Cổng `allowed_changes` chặn `group_at_max|update` và `ci_runner_down|update`. Cả hai do thay đổi của người khác; đã thêm vào allowlist ở #195 và #197. |
| App CD 38343644399 | `ace25eea` (#195) | Prepare lỗi trên `9bbx` (upload qua IAP bị đứt), `abort` trên mọi VM, rollback. Probe: 990 request, 0 khác 200. Mỗi lần SSH mất 240 s. |
| App CD 38347400998 | `4ae56702` (#197) | **Thành công**, 12,5 phút từ lúc merge (CI gate khoảng 7 phút, image tái dùng 24–26 s, deploy 170 s). Roll: prepare 86 s, switch 16 s, report 4 s. Probe: 212 request, 0 khác 200. Infra CD: thành công, 130 s. |
| App CD 38350386248 | `f9252021` (#198) | Bỏ qua deploy, vì chỉ `slot-deploy.sh` đổi; sửa ở #199 (key `slot`). |
| App CD 38351239308 | `3367f551` (#199, gồm cả #196) | Cổng CI chặn: Backend CI đỏ do `test_behavior_snapshot.py` (`CassetteMiss`). PR #196 được merge lúc 05:20 dù CI của nó đỏ. Không deploy. |

Trạng thái lúc 05:40 UTC:
- MIG có 1 VM (`fn9m`), vì autoscaler thu nhỏ nhóm sau khi `cpu_target` lên 0,9.
- Image trên VM khớp last-good và all-instances config: backend `257c7a43`, frontend `a0a0596d`.
- Kho tĩnh có 128 file.
- Alert `ci_runner_down` đã tạo.
- Proxy chưa nạp `mime.types` (JS từ kho ra `text/plain`); sẽ được nạp ở lần App CD kế tiếp qua được cổng CI.

## Quyết định

- Không sửa test agent của #196: ngoài phạm vi CI/CD và thuộc người khác.

## Kiểm tra

- Số liệu lấy từ GitHub Actions API (thời gian job, log), journal VM, `gcloud` (MIG, last-good, alert) và `curl` tới public endpoint.

## Còn lại / rủi ro

- Backend CI trên `release-mvp-v2` đang đỏ (#196). Mọi deploy ứng dụng bị chặn cho tới khi có người sửa.
- Cần bật branch protection (required checks) để PR có CI đỏ không merge được. Repo private gói free không hỗ trợ; cần nâng gói hoặc làm repo công khai.
- Luồng hai VM song song đã chạy thật hai lần: một lần chạy tay lúc 02:47, và lần abort của run 38343644399. Lần deploy thành công chỉ có 1 VM vì autoscaler đã thu nhỏ nhóm.
