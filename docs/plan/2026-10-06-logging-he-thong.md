# Plan: log hệ thống cho frontend, backend, crawler

Phục vụ monitoring/logging. Schema và quy tắc dữ liệu nhạy cảm: `docs/spec/logging-schema.md`.

## Vì sao

Log container vào Cloud Logging không có `severity` nên metric `staging_error_logs` chỉ đếm lỗi của Ops Agent; metric requests đếm cả health check (298/301 dòng trong 1 giờ đo ngày 2026-10-06); ba app log ba kiểu khác nhau, không có `request_id` để nối.

## Luồng nhánh

`khoa/logging` (nhánh tích hợp, chứa schema) ← `khoa/logging-backend`, `khoa/logging-frontend`, `khoa/logging-crawler`, `khoa/logging-monitoring` (mỗi nhánh một worktree, PR base = `khoa/logging`). Merge đủ rồi test tích hợp trên `khoa/logging`, sau đó một PR duy nhất vào `release-mvp-v2`.

## Phạm vi từng nhánh

| Nhánh | Nội dung |
|---|---|
| `khoa/logging-backend` | `core/logging_config.py` (JSON formatter, `ts` +07:00, redact), `http.request` ở middleware, sự kiện nghiệp vụ theo schema, `--no-access-log` ở `Dockerfile.backend` |
| `khoa/logging-frontend` | `src/lib/logger.ts` bằng pino, `bff.proxy`, phiên, stream, `render.error`, `instrumentation.ts`; không đụng Express |
| `khoa/logging-crawler` | `src/data_collection/log.py`, thay `print`, `flow`/`step`/`run_id` theo `pipeline_graph.py`; giữ `job.log`, `run.json`, chuỗi `fresh-catalog.exit=3` |
| `khoa/logging-monitoring` | `ops-agent-staging.yaml` parse hai tầng, filter metric ở `infra/monitoring/main.tf`, panel log ở `dashboard.tf`, test filter. Làm sau ba nhánh trên |

## Rủi ro

- Không deploy backend JSON trước khi sửa metric (SLO/requests sẽ về 0): deploy cùng lúc nhánh monitoring.
- Chi phí: đo ngày 2026-10-06, 1.920 entry/giờ (~379 KB/giờ). Mỗi request có body tăng ~15 lần dung lượng so với dòng access hiện tại; chạy tải ~50 req/s ≈ 195 GB/tháng nếu liên tục, nên tắt `LOG_BODIES` khi chạy tải.

## Ngoài phạm vi

Nhóm VM HA (COS, để sau), server Express, log phía trình duyệt.
