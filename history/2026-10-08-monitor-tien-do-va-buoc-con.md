# Monitor: % hoàn thành từng ô và bung bước con của Bảo trì / Gộp / Kiểm tra / Nạp DB / Index, log theo bước

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: fix/full-refresh-stable (worktree `Travel-Recommendation-Product-fullrefresh`)
- Trạng thái: hoàn thành (chưa commit, chưa deploy)
- Phạm vi: data

## Mục tiêu

Người dùng muốn monitor job cào hiện các bước nhỏ (chuẩn hoá có nhiều bước con, các bước kiểm tra trước khi nạp DB, nạp DB,
index) như một tiến trình liền với các ô kia, mỗi ô thấy đầu vào / đầu ra bao nhiêu, và tô màu theo % hoàn thành (90% thì tô
khoảng 90%); mỗi phần có log riêng. Phục vụ vận hành job cào (FR-CAT-03, NFR-REL-01; công cụ monitor theo
`docs/prd/deployment-plan.md` §5). Không lệch PRD: PRD không quy định giao diện monitor.

Lựa chọn của người dùng (hỏi 08/10): bấm ô lớn mới bung chuỗi ô con ngay trong sơ đồ; đang chạy tô theo tiến độ, xong tô theo
tỉ lệ thành công (bước lọc / gộp trùng không tính là thất bại); tách bước con cho Kiểm tra (từng luật), Nạp DB, Index và Bảo trì
DB; làm chung nhánh với phần làm mới cả catalog.

## File thay đổi

- `src/data_collection/stage_log.py` — thêm: `Stages` (bước con: tên, trạng thái, giây, in/out, `changed`, ok/total, ghi chú,
  lỗi; ghi vào `detail.substeps`, lưu run.json mỗi lần đổi) và `substep_line` (dòng log `catalog.substep name=<bước>:<con> …`).
- `src/data_collection/fresh_catalog_db.py` — sửa: `maintain_catalog(stages=…)` 7 bước con (đọc catalog, danh sách làm mới, hết
  hạn giá Trip, cuộn cửa sổ, ghi DB, vé thương gia mô phỏng, parse combo); `load_into_db(stages=…)` 8 bước con (đọc catalog lượt
  này, thuộc tính combo, đọc DB, ghép với DB, cửa sổ 30 ngày, ghi cdp.products, parse combo, vé thương gia).
- `src/data_collection/fresh_catalog.py` — sửa: `substeps(detail, name)`; `validate_run(stages=…)` mỗi luật một bước con (khách
  sạn Trip đủ mốc ngày, 13 trường, id/sourceRef/hiển thị, đủ nhóm sản phẩm) + `validate_step` thêm "catalog không giảm quá
  ngưỡng", "độ phủ làm mới"; `index_substeps` suy từ báo cáo embed_products; `normalise_step` ghi dòng log cho từng bước con của
  normalise.StepClock.
- `src/data_collection/monitor.py` — sửa: `LogScan` đọc thêm tiến độ Agoda (dòng kế hoạch, "Agoda giá: n/t", "Agoda API: {…}"),
  Vinpearl ("Vinpearl n/N", "Vinpearl tour: n/N"), dòng cuối `Trạng thái: {...}` của crawl.py; `percent`, `substep_view`,
  `node_progress`, `FreshMonitor._progress/_big`: `node.progress` (done/total/percent/kind) cho mọi ô, `node.substeps` cho ô
  lớn và chuẩn hoá theo nguồn, `node.refresh` (làm mới khách sạn đang có).
- `src/data_collection/monitor_ui/index.html` — sửa: tô nền theo %, sọc chạy khi đang chạy chưa biết tổng, dòng "x% · đã/tổng",
  dòng làm mới; bấm ô có bước con thì bung / thu chuỗi ô con (xuống dòng sau 3 ô, cột rộng theo); ô con là nút mở tab Log lọc
  `name=<bước>:<con>`; tab Log của ô lớn lọc `name=<bước>`; nhãn cảnh báo `coverage`.
- `src/data_collection/README.md` — sửa: mục "Monitor của cron mới" mô tả % và bước con.
- `src/data_collection/tests/test_monitor_progress.py` — thêm: 12 test (Stages, dòng log, luật kiểm tra, index, quy tắc %,
  ánh xạ bước con, đọc log tiến độ, đồ thị khi chạy / khi xong).

## Quyết định

- % khi xong: Booking theo `Trạng thái: {'done', 'gone', ...}` (dòng tiến độ cộng lượt thử lại vào tổng: 120/135 → đúng là
  120/127); Agoda có giá + hết phòng là đạt; Trip KS: completed/requested; Kiểm tra: luật đạt / luật kiểm (bỏ luật "skipped");
  Nạp DB: "ghép với DB"; Index: "embed mới / đổi text". Bước biến đổi xong tô đủ; dưới 90% tô vàng.
- Bước chỉ sửa dòng có sẵn (cửa sổ, ghi cdp.products, parse combo, vé thương gia, hết hạn giá) ghi `changed` và hiện
  "N dòng · M đổi", tránh hiện "bớt N" như bước lọc. "Danh sách làm mới" không ghi số vào (chọn, không lọc).
- Index không có số giai đoạn khi đang chạy (job embed_products báo một lần cuối) nên ô hiện sọc chạy.

## Kiểm tra

- `pytest -q tests` trong `src/data_collection` (vsf2, `PYTHONPATH=<worktree>/src`): 578 passed, 27 skipped.
- Test chạy Postgres thật trên Postgres sandbox của worktree (DB tạm, đã xoá sau): `STREAM_TEST_ADMIN_URL` (stream_feed_db,
  combo_items_sync_db), `SIMULATED_TEST_DATABASE_URL`, `RELEASE_TEST_DATABASE_URL` (DB rỗng: 6 passed),
  `CATALOG_TEST_DATABASE_URL`: mọi test chạm `load_into_db`/`maintain_catalog` xanh trừ 2 test đỏ **giống hệt trên code gốc**
  (worktree newcrawl, decccec): `test_stream_feed_db::test_rows_loaded_separately_then_merged_leave_one_visible` (khách sạn
  mẫu không có phòng bị tắt theo quy tắc `noBookableRoom` 06/10, test viết trước quy tắc) và
  `test_simulated_business::test_fresh_maintenance_follows_the_env_switch` ("0 not greater than 0"). `DBX_TEST_DATABASE_URL` cần
  DB đã seed — không chạy (db_browser không đổi).
- Trình duyệt (monitor local trên bộ `refresh`, cổng 8766):
  - lượt `full-20261008T040337Z-68351` chạy lại từ normalise bằng code mới: 30 dòng `catalog.substep`; Booking 94,5% · 120/127,
    "làm mới 98/105"; bung Gộp (11), Kiểm tra (6 luật, độ phủ 96% · 170/177), Nạp DB (8), Index (5); bấm ô con "ghép với DB"
    → tab Log 1/637 dòng đúng dòng đó; tab Log ô Nạp DB 14 dòng (start/done + bước con).
  - lượt sống ngắn (Booking + Agoda, 3 khách sạn, 15:20–15:26): Agoda đang chạy 0/3, Nạp DB đang chạy 6/8 (75%), Index sọc; xong
    mọi ô ok với %; ô chờ không còn sọc (đã sửa). Cấu hình bộ `refresh` khôi phục sau lượt.
  - màn hình 375px: không tràn ngang, chuỗi con 2 ô mỗi hàng.

## Còn lại / rủi ro

- Lượt đã chạy trước bản này không có `detail.substeps` cho Bảo trì / Kiểm tra / Nạp DB / Index (chỉ có bước con chuẩn hoá).
- Hai test DB đỏ có sẵn nêu trên chưa sửa (ngoài phạm vi).
