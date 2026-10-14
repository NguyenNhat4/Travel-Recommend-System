# Job cào: nối DB nội bộ, chống chồng lượt, cảnh báo

Kế hoạch: `docs/plan/2026-10-07-ha-vung-crawler-rolling.md` §4. Job vẫn chạy bằng cron trên VM (`scripts/install-vota-cron.sh`).

## 1. Nối `db.vota.internal`
Trong env crawler: `CLOUD_SEED_DATABASE_URL=postgresql://<user>:<pass>@db.vota.internal:5432/vota` (mẫu: `src/data_collection/fresh-catalog.env.example`). Nối thẳng, **không qua pgbouncer** (khoá DB là advisory lock mức session). VM cùng VPC với zone `vota.internal`; kiểm bằng `nc -z db.vota.internal 5432`. Khi bật Patroni, gắn network tag `vota-crawler` cho VM để firewall `*-pg-clients` cho phép tới 5432.

## 2. Chống chồng lượt và cảnh báo
- Khoá tệp (một máy) + khoá DB `pg_try_advisory_lock(7791025)`; tick đến sau thoát với `catalog.lock.busy scope=database`. `CATALOG_DB_RUN_LOCK=off` chỉ để chạy thử không có Postgres.
- Mỗi tick phát `catalog.freshness`. Bật `crawler_alerts_enabled = true` (staging-ha) **sau khi** crawler bản mới đã chạy một tick: 
  - JOB CÀO KHÔNG CHẠY: vắng dòng này 60 phút → kiểm cron/VM.
  - CATALOG KHÔNG ĐỔI QUÁ HẠN: `state=late` theo `sla.maxCatalogAgeHours` (mặc định 48 giờ, đặt trong monitor).
  - LƯỢT CÀO THẤT BẠI: `run.end status=failed` → xem log `catalog.failed`.
- Failover DB làm mất khoá DB (kết nối đứt); giao dịch nạp vẫn tuần tự nhờ khoá giao dịch nên chỉ có rủi ro cào đôi.
- Tài nguyên VM máy cào (không phụ thuộc `crawler_alerts_enabled`, chỉ cần VM có tồn tại):
  - RAM máy cào cao: RAM đã dùng > 85% trong 10 phút. Đỉnh 7 ngày 57,8%.
  - Đĩa máy cào đầy: một thiết bị > 80% trong 5 phút. Đĩa boot 15 GB, mỗi image khoảng 3 GB; đỉnh 7 ngày 77,7% (sát ngưỡng). Nếu kêu mỗi ngày thì cần tăng đĩa, không nên nâng ngưỡng. Đổi kích thước đĩa boot buộc thay VM.
  - CPU máy cào kéo dài: CPU > 95% liên tục 180 phút. Lượt cào bình thường chạm gần 100% khoảng 1 giờ mỗi ngày (quanh 09:00 giờ Việt Nam), nên ngưỡng thời gian dài hơn lượt bình thường. Kêu tức là lượt bị treo.
