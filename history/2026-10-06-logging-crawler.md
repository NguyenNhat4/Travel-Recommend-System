# Logging JSON cho crawler

- Ngày: 2026-10-06
- Tác giả: Khoa / Claude (agent)
- Nhánh: khoa/logging-crawler
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Thay `print()` rải rác của job cào (`src/data_collection`) bằng logger JSON một dòng theo `docs/spec/logging-schema.md` (mục crawler) để Ops Agent đọc stdout của container, mà không đổi `job.log`, `run.json` và các regex monitor đang đọc. Kế hoạch: `docs/plan/2026-10-06-logging-he-thong.md`. Người dùng cho phép bỏ qua PRD cho task này.

## File thay đổi

- `src/data_collection/log.py` — thêm: logger JSON (`ts` +07:00 ms, `ts_utc`, `severity`, `service=crawler`, `event`, `message`, `run_id`, `flow`, `step`, `source`), `LOG_LEVEL`, `redact()` (khoá và mẫu giá trị mục 4 schema, URL chỉ giữ host + path), `say()`, `scope()`, `step()`, `use_stream()`.
- `src/data_collection/fresh_run_log.py` — sửa: `Tee.stream_only/file_only`; `RunRecorder` đặt `run_id`/`flow` (full|daily|index|resume), phát `step.start`/`step.end` (duration_ms, status, records, source theo `pipeline_graph`). Chữ trong job.log giữ nguyên.
- `src/data_collection/fresh_catalog.py` — sửa: `say()` đi qua log.py; `catalog.due`, `catalog.schedule.skip`, `catalog.lock.busy`, `resume.plan`, `run.start`, `run.end` (message chứa `fresh-catalog.exit=N`), `run.summary`, `catalog.index.start/complete/failed`, `alert.*`, `run.failed/stopped`; dòng của tiến trình con thành `source.output`; con chạy với `CRAWL_LOG_PLAIN=1`.
- `src/data_collection/daily.py` — sửa: các dòng `[daily]` thành event (`daily.*`, `step.start/end` theo stage, `run.end`, `catalog.lock.busy`), `flow=daily`.
- `src/data_collection/alerts.py`, `pipeline_runtime.py`, `index_backlog.py`, `collectors/live_control.py`, `collectors/trip_live.py` — sửa: dùng logger (`trip.meta`, `trip.price` mang `source=tripHotels`).
- `src/data_collection/tests/test_log.py` — thêm: 13 test (schema, +07:00, `LOG_LEVEL`, redact, step.start/end, job.log giữ text, stdout `due`, `run.end`).
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: test đếm `catalog.group.done` đếm theo trường `event` của JSON.

## Quyết định

- job.log giữ nguyên: monitor (`LogScan`, `STEP_RE`, `fresh-catalog.exit`) đọc text có giờ và tiền tố `[nhóm]`. Khi stdout là `Tee`, JSON chỉ đi ra luồng gốc (container) và `message` được ghi riêng vào job.log như `print` cũ, nên không lặp dòng.
- Tiến trình con (`crawl.py`, `normalise.py`) in text như cũ (`CRAWL_LOG_PLAIN=1`); cha bọc từng dòng thành JSON `source.output` (đã redact, bỏ query URL). Tránh bọc hai lớp và giữ regex của monitor.
- Lệnh có stdout là dữ liệu (`due` → tên chế độ, `status`, báo cáo JSON của `index_backlog.py`, các lệnh list/diff của `daily.py`, `crawl.py status`) giữ nguyên stdout; log của `due`/`index_backlog` đi stderr.
- Giá trị trần không có khoá đi kèm chỉ che được khi khớp mẫu (email, SĐT, thẻ, JWT, DSN, Bearer, key Stripe); mật khẩu/API key phải đi kèm khoá (`password=`, `api_key`).

## Kiểm tra

- `pytest src/data_collection/tests` (bỏ các test cần numpy/argon2 và test seed): 367 passed, 18 skipped, 4 failed. 4 failed giống hệt trên `khoa/logging` gốc (docker runner x3, `test_deadline_stops_the_source_and_its_children`), không do thay đổi này.
- `pytest src/data_collection/tests/test_log.py`: 13 passed.
- Chưa chạy lượt cào thật, chưa build image.

## Còn lại / rủi ro

- Chưa đối chiếu với metric trên GCP (`jsonPayload.message:"fresh-catalog.exit=3"`): shell `run_daily_docker.sh` cũng ghi dòng này ra file, nên nếu cùng đọc cả hai nguồn thì đếm đôi.
- Log nội bộ của `normalise.py`/collector chạy trong tiến trình con vẫn là text, chỉ được bọc ở mức dòng (`source.output`), không có trường `records` riêng.
- `crawl.py` CLI, `fresh_catalog_schedule.py` còn `print` vì là output của lệnh.
