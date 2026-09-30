# CP6: chạy lại một lượt từ bước sau cào (không cào lại)

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

CP6 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`: lỗi ở normalize, kiểm tra, nạp DB hay index thì chạy lại
từ bước đó, dùng lại raw / interim / checkpoint / catalog của chính lượt. Tương đương "Clear" task của Airflow.

## File thay đổi

- `src/data_collection/fresh_run_log.py` — sửa: thêm `RunRecorder.resume`:
  - mở lại `run.json`, giữ các bước cũ, thêm mục `resumes` (từ bước, lúc, trạng thái / lỗi / số giây cũ);
  - không nhận lượt đang chạy; `seconds` cộng dồn.
- `src/data_collection/fresh_catalog.py` — sửa:
  - tách `normalise_step`, `validate_step`, `db_step` (luồng thường dùng lại, hành vi không đổi);
  - `normalize(..., merge_only)`;
  - thêm `RESUME_STEPS`, `resume_run`;
  - `run_job(mode='resume', run_id, from_step)` dùng khoá chung và cấu hình của chính lượt;
  - CLI `fresh_catalog.py resume <mã lượt> --from normalise|merge|validate|db|index`.
- `src/data_collection/monitor.py` — sửa: thêm `FreshMonitor.resume` (khởi chạy như nút Cào, trả 409 khi đang có lượt chạy),
  `POST /api/resume`; ô Gộp / Kiểm tra / Nạp DB / Index của lượt đã kết thúc có `resume`; `graph()` trả `resumes`.
- `src/data_collection/monitor_ui/index.html` — sửa:
  - nút "Chạy lại từ bước này" (ô Gộp thêm "Chỉ gộp lại từ checkpoint") có hộp xác nhận;
  - đầu lượt hiện các lần đã chạy lại.
- `src/data_collection/local_crawl.sh` — sửa: thêm `run resume <mã lượt> <bước>`, cập nhật trợ giúp (dòng 2–20).
- `src/data_collection/tests/test_fresh_catalog_job.py`, `tests/test_monitor_graph.py` — sửa: thêm test.
- `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` — sửa: tiến độ.

## Quyết định

- Không bảo trì DB và không cào ở lần chạy lại; bước index luôn chạy ở cuối như luồng thường.
- Lượt `full` chạy lại qua được bước nạp DB thì ghi `full.last_success` bằng `startedAt` của lượt gốc.
- **Không** cập nhật trạng thái xoay vòng khách sạn Trip (`trip_targets.json`, `trip_schedule.json`), vì danh sách ID của
  bước tìm ID không được lưu trong lượt. Khách sạn Trip chỉ nạp khi lượt có `trip_price_coverage.json`.
- Chỉ bước sau cào mới chạy lại được. Chạy lại phần cào là một lượt mới.
- `run_daily_docker.sh fresh-run` (VM) **chưa** có `resume`; trên VM chạy qua nút của monitor hoặc lệnh `fresh_catalog.py`
  trong container.

## Kiểm tra

- `pytest tests` (env `vsf`): **454 passed, 5 skipped**.
- Test mới:
  - chạy lại từ db / validate / normalise / index gọi đúng các bước sau đó, không cào, không bảo trì;
  - `run.json` giữ bước cũ, thêm 4 mục `resumes`, `seconds` ≥ lượt gốc;
  - `merge` gọi normalize chỉ gộp; thiếu `products.jsonl` thì báo "chạy lại từ normalise" (index vẫn chạy);
  - lượt đang chạy, đang có khoá, hoặc mã lượt lạ thì bị từ chối; CLI thiếu tham số thì lỗi;
  - monitor: ô có nút chạy lại đúng bước; lượt `index` chỉ chạy lại index; lượt đang chạy bị từ chối (409);
    lệnh khởi chạy đúng.
- Chạy thật trên bản sao lượt `full-20260925T091848Z-201309` (scratchpad), `resume --from normalise`, normalize và validate
  thật, nạp DB / index giả lập:
  - exit 0; trạng thái failed → ok; thêm 4 bước;
  - `products.jsonl` (631 dòng) trùng sha256 bản cũ; nạp nhận 631 dòng.
- `bash -n local_crawl.sh`: sạch; `run resume` thiếu tham số báo đúng cú pháp.

## Còn lại / rủi ro

- Chưa bấm nút chạy lại trên monitor với lượt thật và DB thật. Chưa commit.
