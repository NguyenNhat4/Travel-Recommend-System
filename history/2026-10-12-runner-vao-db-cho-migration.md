# Cho runner CI tới Postgres staging-HA (chuẩn bị chạy migration trong CD)

- Ngày: 2026-10-12
- Tác giả: Khoa15 / Claude (agent), theo chỉ đạo người vận hành (mục 2 trong lựa chọn về migration)
- Nhánh: release-mvp-v2
- Trạng thái: dang dở
- Phạm vi: infra

## Mục tiêu

Guard `staging-ha-backend-build.yml` chặn commit có thay đổi `db/migrations` vì CD chưa chạy migration (hiện tại: migration `0010_combo_only_va_price_share.sql` từ PR #162 đang chặn build). Để CD tự chạy migration, runner tự host `vota-ha-runner`/`vota-ci-runner` (tag `ci-runner`, IP `10.148.0.50`) phải tới được Postgres ILB `10.148.0.34:5432`. Firewall `vota-ha-pg-clients` hiện chỉ cho tag `vota-ha-app`, `vota-crawler` và `db_client_tags`.

## File thay đổi

- `infra/terraform/environments/staging-ha/variables.tf` — sửa: `db_client_tags` mặc định `["ci-runner"]`.
- `scripts/deploy-staging-ha-app.sh` — sửa: thêm `google_compute_firewall.patroni_clients[0]|update` vào danh sách thay đổi được phép của guard.

## Quyết định

- Chỉ mở cho tag `ci-runner`, không mở cho nguồn rộng hơn.
- Guard được nới đúng một thay đổi (firewall này), không nới loại thay đổi khác.
- Chưa tạo credential migration và chưa thêm bước migration vào workflow. Phần này đang chờ quyết định về role DB (superuser hay role DDL riêng) và secret GitHub.

## Kiểm tra

- `terraform validate`: đạt.
- Plan local: `google_compute_firewall.patroni_clients[0]` đổi `source_tags` từ `["vota-crawler","vota-ha-app"]` thành `["ci-runner","vota-crawler","vota-ha-app"]`. Plan local còn các thay đổi monitoring khác do tfvars local khác secret CI; CD trên `3c82c937` đã success nên plan CI không có các thay đổi đó.

## Còn lại / rủi ro

- Bước migration trong CD chưa có. Migration `0010` chưa được áp lên DB staging-HA.
- Runner không có credential DB; mở mạng không cấp quyền đăng nhập.
- Nếu một VM khác có tag `ci-runner` xuất hiện, nó cũng sẽ tới được 5432 của Patroni.
