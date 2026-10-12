# Đổi tên workflow cho khớp việc nó làm (CI / CD / CI/CD)

- Ngày: 2026-10-12
- Tác giả: Khoa15 (yêu cầu) / Claude Code (agent)
- Nhánh: khoa/doi-ten-workflows-ci-cd
- Trạng thái: hoàn thành
- Phạm vi: docs (CI/CD)

## Mục tiêu

Tên workflow phải đúng với việc làm: chỉ CI thì "CI", chỉ CD thì "CD", có cả hai thì "CI/CD". Trước đó `Backend CI/CD` và `Crawler CI/CD` mang tên CI/CD nhưng job publish/deploy bị tắt (`if: ${{ false }}`) hoặc chỉ build/publish ảnh, không deploy.

## File thay đổi

- `.github/workflows/backend-ci-cd.yml` — sửa `name`: `Backend CI/CD` → `Backend CI` (publish và deploy tắt cứng).
- `.github/workflows/crawler-ci-cd.yml` — sửa `name`: `Crawler CI/CD` → `Crawler CI` (deploy tắt cứng; chỉ publish ảnh SHA).
- `.github/workflows/ha-checks.yml` — sửa `name`: `HA checks` → `HA CI` (chỉ kiểm tra).
- `.github/workflows/infra-terraform-staging.yml` — sửa `name`: `Staging Infra Terraform` → `Staging Infra CI/CD` (validate + plan/apply).
- `.github/workflows/monitoring-agent-cd-staging.yml` — sửa `name`: `Staging Monitoring Agent CD` → `Staging Monitoring Agent CI/CD` (validate + deploy).
- `.github/workflows/monitoring-terraform-staging.yml` — sửa `name`: `Staging Monitoring Terraform` → `Staging Monitoring Terraform CI/CD` (validate + apply); sửa một thông điệp cảnh báo nhắc tên workflow Infra.
- `docs/guide/trien-khai-job-cao-du-lieu.md`, `docs/guide/van-hanh-db-replica.md` — sửa: tên workflow trong hướng dẫn.

## Quyết định

- Chỉ đổi `name:` cấp workflow. Không đổi tên file, tên job, trigger hay `concurrency`. Tên job là ngữ cảnh của status check, nên rule bảo vệ nhánh (nếu có) không bị ảnh hưởng.
- Giữ `Frontend CI` (đã đúng: build_vm/publish_vm/deploy_vm tắt cứng) và các workflow `Staging-HA * CD` (build + deploy thật).
- Không đụng entry history cũ, vì chúng ghi tên lúc đó.

## Kiểm tra

- Liệt kê dòng 1 của mọi workflow sau khi đổi. Chưa chạy workflow nào.
- Hai mục `Frontend CI` (id 366147580) và `IaC plan` còn trong danh sách Actions nhưng file đã không còn trong repo; chưa xử lý.

## Còn lại / rủi ro

- Các run cũ vẫn hiển thị tên cũ.
- Mọi liên kết ngoài repo (wiki, dashboard) theo tên cũ cần cập nhật tay.
