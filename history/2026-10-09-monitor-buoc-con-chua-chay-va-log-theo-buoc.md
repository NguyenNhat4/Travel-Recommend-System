# Monitor: bước con chưa chạy, log theo bước, tab DB tự làm mới

- Ngày: 2026-10-09
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Theo dõi lượt cào đầu tiên trên VM cào mới (vota-ha-crawler): ô bước lớn chưa chạy không bung được bước con, tab Log của
ô bước lớn không thấy bước con đang chạy, tab DB phải bấm tải lại tay. Entry này ghi phần thay đổi monitor làm trong phiên
trước cùng ngày (chưa có entry); phần lọc log của ô Gộp ghi riêng ở
`2026-10-09-monitor-o-gop-hien-log-catalog-dang-gop.md`.

## File thay đổi

- `src/data_collection/pipeline_graph.py` — sửa: thêm `SUBSTEPS` (danh sách bước con theo thứ tự của maintain, normalise,
  validate, db, index), `SUBSTEP_EXTRAS`, `MERGE_ONLY_FROM`, `planned_substeps()`.
- `src/data_collection/monitor.py` — sửa: `EXPECTED_SUBSTEPS` suy từ `SUBSTEPS`; `with_plan()` hiện đủ chuỗi bước con (bước
  chưa có số liệu là ô `planned` mang trạng thái chờ / không chạy); bước Gộp nháp chỉ có chuỗi từ "đọc checkpoint"; tab bước
  con của Gộp hiện sẵn các bước sẽ chạy trước lần gộp đầu.
- `src/data_collection/stage_log.py` — sửa: `Stages` ghi một dòng `status=running` khi bước con bắt đầu (trước chỉ ghi lúc xong).
- `src/data_collection/monitor_ui/index.html` — sửa: ô bước con `planned` (mờ, viền đứt), lọc log theo bước / bước con
  (`S.log.step/sub`, chip "Đang lọc theo bước" + nút bỏ lọc), tab DB có "Tải lại" và "Tự làm mới mỗi 10 giây".
- `src/data_collection/tests/test_monitor_progress.py`, `src/data_collection/tests/test_pipeline_graph.py` — sửa: test cho các
  hành vi trên, kể cả đối chiếu `SUBSTEPS` với tên bước con trong code.
- `src/data_collection/README.md` — sửa: đoạn "Bước con chưa chạy và log theo bước (09/10/2026)".

## Quyết định

- Danh sách bước con khai báo một chỗ (`pipeline_graph.SUBSTEPS`), test bắt lệch với code để ô chưa chạy vẫn đúng.
- Chỉ đổi monitor và log của job, không đổi dữ liệu catalog; không lệch PRD.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q data_collection/tests` (env vsf2, từ `src/`): 646 passed, 27 skipped.

## Còn lại / rủi ro

- Có hiệu lực trên VM sau khi PR vào `release-mvp-v2` được merge và workflow `staging-ha-crawler-cd.yml` deploy.
