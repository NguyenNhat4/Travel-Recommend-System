# CP7, CP8: cảnh báo khi lượt lỗi và SLA (ghi file + hiện trên monitor, chưa gửi ra ngoài)

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

CP7 (tương đương `on_failure_callback`) và CP8 (SLA miss) của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`.
Người yêu cầu (2026-09-28): kênh gửi ra ngoài chưa có cũng được.

## File thay đổi

- `src/data_collection/alerts.py` — thêm:
  - `run_alerts`: lượt lỗi / chặn chất lượng (error); nguồn bị chặn, bản ghi lỗi dưới ngưỡng, lô nạp DB theo phần lỗi (warning);
  - `publish`: ghi `<lượt>/alerts.jsonl` và `<state>/alerts.jsonl` (giữ 2.000 dòng); `alerts_seen.json` chống báo dồn,
    cảnh báo bị chặn vẫn ghi kèm `suppressed`;
  - `on_run_finished`, `slow_step_alerts`, `sla_status`, `check_sla`;
  - `redact`: che mật khẩu trong DSN và giá trị biến có tên `*KEY|TOKEN|SECRET|PASSWORD|DATABASE_URL`.
- `src/data_collection/fresh_catalog.py` — sửa:
  - `notify_finished` sau khi lượt ghi kết thúc (cả lượt chạy lại);
  - `check_sla` ở tick rảnh (lịch chưa tới / đang có lượt), không cần biến DB;
  - cả hai là best effort.
- `src/data_collection/fresh_settings.py` — sửa: nhóm "Cảnh báo và SLA" với `alert.enabled`, `alert.includeWarnings`,
  `alert.cooldownHours` (6), `sla.enabled`, `sla.finishBy` (19:00), `sla.slowFactor` (3), `sla.maxCatalogAgeHours` (48).
- `src/data_collection/monitor.py` — sửa: `overview()` trả `alerts`, `sla`; `run()` trả `alerts`; thêm `GET /api/alerts`.
- `src/data_collection/monitor_ui/index.html` — sửa:
  - Tổng quan: thẻ "Cảnh báo và SLA" (trạng thái từng quy tắc) và bảng cảnh báo lọc theo mức / loại;
  - bấm mã lượt thì mở lượt, chọn sẵn ô của bước;
  - đầu lượt: cảnh báo của lượt.
- `src/data_collection/tests/test_alerts.py` — thêm: 8 test.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: thêm 2 test tích hợp.
- `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` — sửa: tiến độ.

## Quyết định

- Không gửi ra ngoài: không thêm secret, không cần đề xuất PRD. Chữ ký chống báo dồn = loại + bước + nguồn.
- Quy tắc SLA:
  - "xong trong ngày": hôm nay có lịch (lịch bật và hôm nay là ngày cào lớn hoặc daily bật), quá `sla.finishBy` mà chưa có
    lượt ok/partial bắt đầu trong ngày (giờ Việt Nam);
  - "catalog tươi": lần có bước `db` ok gần nhất cũ hơn ngưỡng. Chưa có lần nạp nào thì không báo;
  - mỗi quy tắc tối đa một cảnh báo mỗi ngày.
- "Bước chậm" không kiểm ở tick mà kiểm khi lượt kết thúc: so với trung vị của chính bước đó ở các lượt còn giữ, cần ≥ 3 lượt.
- Plan ghi "lượt đang chạy tự kiểm bước chậm khi mỗi bước kết thúc"; bản này kiểm khi lượt kết thúc — **khác plan**, đơn giản hơn.
- Giới hạn đã ghi trong plan: VM hoặc cron chết thì không có cảnh báo.

## Kiểm tra

- `pytest tests/test_alerts.py` (env `vsf`): **8 passed** — đủ loại cảnh báo, không lộ mật khẩu DSN / khoá API; chống báo dồn;
  bước chậm; SLA đạt / trễ / chưa tới hạn / không áp dụng; một lần mỗi ngày, ngày mới báo lại.
- `tests/test_fresh_catalog_job.py`: lượt daily lỗi ghi cảnh báo `error` vào cả hai file; tick rảnh gọi `check_sla` khi
  không có biến DB.
- `pytest tests`: **464 passed, 5 skipped**.
- Trình duyệt, monitor thử 8797 (lượt giả, cảnh báo sinh bằng chính `alerts.py`):
  - thẻ SLA hiện "Xong trong ngày: Chưa tới hạn", "Catalog tươi: Không áp dụng";
  - bảng có 2 cảnh báo; lọc "Lỗi" → 1, thêm "Bị chặn" → 0, bỏ lọc → 2;
  - bấm mã lượt → mở lượt, chọn sẵn ô `db` có nút "Chạy lại từ bước này".

## Còn lại / rủi ro

- Kênh gửi ra ngoài (Telegram / email / webhook): cần đề xuất PRD vì thêm secret.
- Chưa chạy với cron thật trên VM. Chưa commit.
