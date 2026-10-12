# Kích hoạt tầng DB HA Patroni cho staging-ha

- Ngày: 2026-10-08
- Người đề xuất: người dùng / Codex
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: người dùng, 2026-10-08
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §1, §5, §6
- Mã FR/NFR: NFR-REL-02, NFR-PERF-01

## Lý do

PRD hiện mô tả PostgreSQL của Staging Cloud ở mức khái quát và chưa ghi rõ cụm Patroni, witness etcd, load balancer nội bộ hoặc ranh giới state `staging-ha`. Người dùng đã chốt triển khai tầng HA này trong môi trường staging-ha để giảm thời gian gián đoạn khi mất node DB, giữ kết nối ghi tại leader và bảo toàn dữ liệu giao dịch theo NFR-REL-02.

## Nội dung đề xuất

Đoạn mô tả hiện tại chỉ ghi:

> Cơ sở dữ liệu | PostgreSQL Cloud

Đoạn bổ sung đã áp dụng:

> `staging-ha` là một Terraform root và state riêng (`infra/staging-ha`), không dùng state `infra/staging` và không tự thay đổi workflow CI/CD hiện hữu. Khi được bật có chủ đích, staging-ha dùng hai node PostgreSQL + Patroni ở hai zone, một witness etcd ở zone thứ ba và ILB private chỉ gửi kết nối ghi tới node trả `200` ở `/primary`. `create_patroni = false` vẫn là mặc định.

Việc di trú từ primary cũ là một cửa sổ vận hành riêng: dừng ghi, clone một lần từ primary cũ vào node Patroni đầu tiên, đối chiếu dữ liệu và replication lag, sau đó mới cutover DNS/ILB và mở lại ghi. Primary cũ được giữ nguyên để rollback có điều kiện; dữ liệu phát sinh sau cutover không tự quay ngược về primary cũ.

## Thay đổi source sau khi chốt

- `docs/prd/deployment-plan.md` — ghi rõ kiến trúc, ranh giới state, điều kiện bật và rollback của staging-ha.
- `infra/terraform/environments/staging-ha/` — thêm backend GCS khai báo rõ, sửa truyền clone host chỉ cho node `a`, cập nhật test cấu trúc và cấu hình triển khai thực tế.
- `docs/plan/2026-10-07-ha-vung-crawler-rolling.md` và `docs/guide/van-hanh-db-patroni.md` — cập nhật trạng thái và điều kiện vận hành.
- Không sửa `infra/terraform/environments/staging`, các workflow CI/CD hiện hữu hoặc contract/API/DDL.
