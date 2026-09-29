# Gỡ code cũ không còn dùng của data_collection

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người yêu cầu: "những code nào cũ của data-collection, không còn dùng thì thôi". Sau đó chọn xoá cả ba nhóm được hỏi, và
"xóa các file thừa, các file phiên bản cũ". Job hiện hành là `fresh_catalog.py`; job cũ `daily.py` + `cron_daily.sh`
**giữ lại** vì CI/CD (`crawler-ci-cd.yml`, `Dockerfile.daily`) vẫn triển khai nó.

## File thay đổi

- Xoá — luồng demo cũ: `src/data_collection/pipeline_demo.py`, `api_sources.py`, `apify_source.py`, `cron_run.sh`,
  `tests/test_pipeline_demo.py`, `tests/test_api_sources.py`.
- Xoá — script chạy tay cũ: `overnight.py`, `retry_unpriced.py`, `deepen_jobs.py`, `run_extra_queue.sh`, `run_forever.sh`,
  `stop_crawl.sh`, `cron_hotels_daily.sh`, `tests/test_overnight.py`, `tests/test_retry_unpriced.py`,
  `tests/test_deepen_jobs.py`.
- Xoá — bộ tạo gói bàn giao: `make_handover.py`, `make_docs.py`, `make_template.py`, `make_sample.py`,
  `finalize_catalog.sh`, `tests/test_make_sample.py`.
- Xoá — file thừa / bản cũ:
  - `load_catalog.py`, `parse_combos.py`: CLI tương thích, gọi sang `seed/`;
  - `batch.py`: bộ chia lô theo thành phố / tháng, chỉ script đã xoá dùng;
  - `catalog.py`: công cụ tách template cũ;
  - `run_fresh_catalog_vm.sh`: wrapper tương thích;
  - `tests/test_batch.py`;
  - `docs/spec/data-collection/RUN_BY_CITY.md`: hướng dẫn bộ chạy theo lô đã xoá.
- Sửa tài liệu:
  - `src/data_collection/README.md`: bỏ khối `pipeline_demo`, wrapper, `make_template` / `make_sample`, `run_forever`;
    thay bằng hướng dẫn job mới / cào lại nguồn;
  - `src/data_collection/sample/README.md`, `docs/spec/data-collection/schema.md`, `docs/spec/data-collection/ban-giao.md`:
    ghi rõ công cụ sinh đã gỡ, tài liệu giữ để tra cứu.
- Sửa comment (không đổi logic): `collectors/vinpearl.py`, `collectors/common.py`, `crawl.py`, `normalise.py`.
- `history/2026-09-29-go-code-cu-data-collection.md` — thêm: entry này.

## Quyết định

- "Còn dùng" = được import / gọi bởi job mới, CI/CD, Makefile, Dockerfile, module khác, hoặc test của module còn giữ. Kiểm
  bằng import thật (không chỉ khớp chữ): các tham chiếu còn lại tới file bị xoá chỉ là comment / tài liệu.
- `seed/parse_combos.py` và `seed/load_products.py` (module thật, AGENTS.md §6.5) giữ nguyên; chỉ xoá CLI tương thích ở gốc.
- Không đụng `history/` và `docs/plan/` cũ (ghi lịch sử).

## Kiểm tra

- `python -m compileall -q src/data_collection` (vsf2): ok.
- `pytest tests` (vsf2, từ `src/data_collection`): **409 passed, 3 skipped**. Trước khi xoá là 526 passed, 5 skipped; phần
  chênh là test của chính các file bị xoá.
- `grep` tên các file đã xoá trong `src`, `docs`, `AGENTS.md`, `README.md`, `Makefile`, `.github`: chỉ còn trong
  `history/`, `docs/plan/` và các dòng ghi "đã gỡ".

## Còn lại / rủi ro

- CI/CD vẫn chỉ build `Dockerfile.daily` (job cũ); job mới `Dockerfile.fresh-catalog` chưa được CI build / đẩy lên. Người
  yêu cầu để đội deploy làm.
- Chưa push (người yêu cầu tự push `test/newcrawl` và mở PR vào `release-mvp-v2`).
