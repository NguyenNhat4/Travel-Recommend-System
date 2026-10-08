# HA: replica khác zone, Patroni, crawler độc lập, readiness mất-DB, rolling update và tắt êm

- Ngày: 2026-10-07
- Tác giả: người dùng (yêu cầu trực tiếp) / Claude
- Nhánh: khoa/ha-multizone-patroni-crawler
- Trạng thái: hoàn thành (code, test, tài liệu); chưa apply lên GCP
- Phạm vi: docs | backend | data | infra

## Mục tiêu

Giải quyết các điểm yếu HA còn lại của plan `2026-10-05-ha-load-balancing.md`: replica cùng zone với primary; failover do người, RTO 10–30 phút so với giữ chỗ 30 phút; script chỉ promote nên sau đó chỉ còn một DB; crawler chạy cron trên VM cũ qua tunnel IP cố định; `READY_REQUIRES_DB` loại mọi VM khi DB chết toàn cục; rolling update không chờ VM ready; `min_replicas 2` × `cpu_target 0.6` quá tải khi mất 1 VM; cooldown 180s < boot 360s; SSE 90s bị cắt khi scale-in. Use case có số liệu: `docs/plan/2026-10-07-ha-vung-crawler-rolling.md`.

## File thay đổi

- `docs/plan/2026-10-07-ha-vung-crawler-rolling.md` — thêm: plan, 8 use case, phần đã kiểm / chưa kiểm
- `docs/plan/2026-10-05-ha-load-balancing.md` — sửa: nghiệm thu rolling update ghi rõ chưa kiểm chứng; mất zone trỏ plan mới
- `docs/guide/van-hanh-db-patroni.md` — thêm: dựng, di trú (clone), kiểm tra, dựng lại replica, sự cố
- `docs/guide/van-hanh-crawler-db-noi-bo.md` — thêm: nối `db.vota.internal`, khoá chống chồng, cảnh báo
- `docs/guide/van-hanh-db-replica.md` — sửa: replica khác zone, mục 6.1 dựng lại replica sau promote
- `infra/terraform/environments/staging/{main,variables}.tf` — sửa: `db_replica_zone` (khác `zone`, validation)
- `infra/monitoring/{data,variables}.tf` — sửa: `db_replica_zone` cho data source của replica
- `.github/workflows/{infra-terraform-staging,monitoring-terraform-staging}.yml` — sửa: truyền `GCE_DB_REPLICA_ZONE`
- `ops/ci-db-replication.sh`, `ops/promote-db-replica.sh` — sửa: zone riêng cho replica; promote in khung "KHÔNG CÒN REPLICA" và các bước dựng lại
- `infra/terraform/environments/staging-ha/{main,variables,versions,provider,compose.ha,startup.sh.tftpl,outputs}` — sửa: `min_ready_sec`, cooldown, draining, `min_replicas 3`, `cpu_target 0.55`, `memory 60`, chuỗi tắt êm, provider `google-beta` cho hai resource, output Patroni
- `infra/terraform/environments/staging-ha/.terraform.lock.hcl` — sửa: thêm `google-beta` 6.50.0
- `infra/terraform/environments/staging-ha/{patroni.tf,patroni-node.sh.tftpl,patroni_ops_agent.yaml,patroni_monitoring.tf}` — thêm: cụm Patroni 2 zone + witness + ILB + giám sát (tắt mặc định)
- `infra/terraform/environments/staging-ha/crawler_monitoring.tf` — thêm: ba cảnh báo crawler
- `infra/terraform/environments/staging-ha/staging-ha.tfvars.example` — sửa: biến mới
- `infra/terraform/environments/staging-ha/tests/test_resilience.py` — thêm: test cấu trúc
- `ops/patroni/{Dockerfile,patroni.yml,bootstrap-clone.yml,entrypoint.sh,clone-from-primary.sh,cluster_probe.py}` — thêm: image và cấu hình Patroni, probe cụm
- `ops/tests/{test_patroni_failover.sh,test_patroni_clone_bootstrap.sh,test_cluster_probe.py}` — thêm: test Docker thật và test probe
- `ops/loadtest/ha-rolling-update-drill.sh` — thêm: diễn tập rolling update dưới tải (chưa chạy)
- `Dockerfile.backend` — sửa: `UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN` thay cờ cứng 30
- `src/backend/app/infrastructure/persistence/db_peer_registry.py` — thêm: sổ "VM nào còn DB" trong Redis
- `src/backend/app/{main,core/config}.py` — sửa: `health_ready` phân biệt mất DB một VM / mọi VM; `READY_DB_OUTAGE_KEEPS_READY`, `READY_DB_PEER_TTL_SECONDS`
- `src/backend/tests/unit/api/test_db_outage_readiness.py` — thêm: 9 test
- `src/backend/README.md` — sửa: mô tả readiness và biến tắt êm
- `src/data_collection/catalog_run_lock.py` — thêm: khoá DB một-lượt-chạy và `lock_file`
- `src/data_collection/{fresh_catalog,monitor,pipeline_runtime}.py` — sửa: khoá DB, `CATALOG_LOCK_DIR`, `catalog.freshness`
- `src/data_collection/fresh-catalog.env.example`, `src/data_collection/README.md` — sửa: `db.vota.internal`, khoá, freshness
- `src/data_collection/tests/{test_catalog_run_lock,test_fresh_catalog_job,test_fresh_monitor,test_pipeline_graph,test_timeouts_recrawl}.py` — thêm/sửa: test khoá DB, freshness; tắt khoá DB trong test cũ bằng `CATALOG_DB_RUN_LOCK=off`
- `.github/workflows/ha-checks.yml` — thêm: CI cho staging-ha, Patroni (Docker), probe, khoá DB crawler; trước đây không workflow nào chạy các phần này
- `history/2026-10-07-ha-vung-crawler-rolling.md` — thêm: entry này

## Quyết định

- **Không có đề xuất `docs/prd/update/`**: PRD không có NFR HA; như plan 2026-10-05, làm theo yêu cầu trực tiếp của người dùng. Mặc định mọi thứ mới tắt (`create_patroni`, `crawler_alerts_enabled`); thay đổi có hiệu lực ngay khi apply `staging-ha` là `min_replicas 3`, `cpu_target`, `memory`, `min_ready_sec`, cooldown, draining. Cần PRD khớp thì tạo đề xuất sau.
- Patroni thay vì promote tay: 2 node ở 2 zone + witness etcd ở zone thứ ba, ILB nội bộ trỏ leader (không đổi DNS khi failover), `synchronous_mode` không nghiêm ngặt, `pg_rewind`. Image tự dựng từ cùng image Postgres hiện tại để clone dữ liệu chạy ngay.
- `min_ready_sec` chỉ có ở `google-beta` (kiểm schema google 6.50): hai resource (MIG, backend service ILB) dùng `provider = google-beta`.
- Readiness: dùng sổ Redis thay vì chọn một chế độ cho cả nhóm, vì cần phân biệt "một VM" với "tất cả". Redis không đọc được thì coi là mất toàn cục (loại hết là kết cục tệ hơn). Quyết định chung với nhánh `khoa/backend-db-unavailable-degraded` ghi ở plan §3: chưa merge nhánh đó, giữ cờ `READY_REQUIRES_DB` làm công tắc.
- Cảnh báo "catalog không đổi quá X giờ": X là `sla.maxCatalogAgeHours` của job, tính trong job và phát `catalog.freshness` (cảnh báo vắng mặt của GCP tối đa 23,5 giờ nên không đặt thẳng X ở Terraform). Nhận định ban đầu "crawler ghi lỗi âm thầm khi failover" được sửa lại sau khi đọc `infra/monitoring/main.tf`: trên VM đã có cảnh báo container thoát khác 0; điểm thật là các cảnh báo đó chỉ nhìn container VM nên mất khi sang và tick rảnh không chạm DB.
- Cloud Run Job đã bỏ theo yêu cầu (2026-10-07): crawler giữ cron trên VM, chỉ đổi URL DB, thêm khoá DB và cảnh báo.

## Kiểm tra

- `docker build ops/patroni` + `ops/tests/test_patroni_failover.sh` (etcd + 2 node Patroni thật, `docker kill` leader): PASS, `/primary` 200 trên node mới sau 28 giây (27 giây ở lần chạy sau), không mất dòng, node cũ tự vào lại làm replica, probe `ok → no_replica → ok`. Đây là Docker local, KHÔNG phải GCP.
- `ops/tests/test_patroni_clone_bootstrap.sh` (clone từ Postgres thường, node hai vào replica, primary cũ vẫn ghi được): PASS (sau khi sửa lỗi Patroni xoá biến `PATRONI_*` khỏi môi trường script bootstrap).
- `ops/tests/test_promote_db_replica.sh`, `ops/tests/test_infra_layout.sh`, `ops/tests/test_check_db_direct.sh`: PASS.
- `python3 -m pytest ops/tests/test_cluster_probe.py`: 7 passed.
- `src/backend/tests` (cả bộ): 1703 passed, 32 skipped, gồm 9 test mới `test_db_outage_readiness.py` và kiểm kiến trúc. (Một lần chạy riêng lẻ `test_search_v116_defaults` rớt rồi qua ở lần chạy cả bộ; không đụng file nào của thay đổi này.)
- `src/data_collection/tests` (PYTHONPATH=src, cả bộ): 512 passed, 22 skipped, 4 failed. Ba test rớt giống hệt trên bản gốc (xác nhận bằng `git stash`): `test_runner_fresh_monitor` (hai test) và `test_timeouts_recrawl::RunSourceTimeoutTests::test_deadline_stops_the_source_and_its_children`. Test thứ tư `test_fresh_monitor::DockerRunnerTests` lỗi ở `run_daily_docker.sh` (file không đổi, nghi `stat -c` của macOS), chưa đối chiếu trên bản gốc. Khoá DB kiểm trên Postgres 16 thật qua `CATALOG_TEST_DATABASE_URL` (holder thứ hai bị từ chối, nhận được khi holder đầu chết).
- `terraform validate` pass cho `staging-ha`, `staging`, `infra/monitoring`; `terraform fmt -check` pass; `patroni-node.sh.tftpl` render bằng `templatefile` rồi `bash -n` pass (vai trò db và witness).
- `python3 infra/terraform/environments/staging-ha/tests/test_*.py`: 5 file OK, gồm 23 test mới `test_resilience.py`.
- Không đổi contract/mock nên không chạy `validate_contract.py`. Không đổi schema/seed nên không chạy `db/verify.sql`.
- **Chưa chạy**: `terraform plan`/`apply` (không có credential), k6 và `ha-rolling-update-drill.sh`, failover/ILB/cảnh báo thật trên GCP, stream SSE khi scale-in.

## Còn lại / rủi ro

- Apply lên GCP theo thứ tự ở plan §6; tự đo `boot_to_ready_seconds` (360 là ước tính) và chạy một failover thật để có số trên GCP.
- Đổi replica sang zone khác là thay VM replica: CI chặn trừ khi `allow_destroy=true`; replica hiện tại vẫn ở zone a.
- Di trú Patroni cần cửa sổ bảo trì có dừng ghi (bản clone là điểm thời gian); runbook ở `docs/guide/van-hanh-db-patroni.md` §3.
- Quyết định merge `khoa/backend-db-unavailable-degraded`: hai nhánh cùng sửa `health_ready` và `db_probe.py` (plan §3).
- SSE: nếu muốn bền hơn nữa thì client tự nối lại (`run.failed` kèm retry); chưa làm.
- CI chưa chạy `ops/tests/test_patroni_*.sh` (cần Docker và kéo image etcd/Postgres); nếu muốn, thêm job riêng.
