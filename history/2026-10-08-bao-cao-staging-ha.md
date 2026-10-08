# History: báo cáo chi tiết `staging-ha`

- **Ngày:** 2026-10-08
- **Báo cáo đầy đủ:** [`docs/plan/2026-10-08-bao-cao-trien-khai-staging-ha.md`](../docs/plan/2026-10-08-bao-cao-trien-khai-staging-ha.md)
- **Vì** cần lưu một record không thay thế được, **do đó** tạo history entry riêng, **mà** báo cáo dài và command ledger nằm ở tài liệu linked để tránh duplicate toàn bộ nội dung.
- **Phạm vi:** Patroni/replication/ILB/failover thật trong `staging-ha`, secret sync role `replicator`, reset/rejoin node HA, data compare và boundary audit.
- **Kết luận:** HA runtime/failover đã xác minh; `cdp.products` còn 157 dòng khác nội dung, **do đó** chưa cutover DNS và chưa mở ghi HA; staging primary/replica/app và CI/CD không bị can thiệp.
