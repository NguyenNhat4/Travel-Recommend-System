# Cào song song theo site và lệnh theo dõi job cào, backend trên console VM

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, deployment

## Mục tiêu

Người dùng muốn lượt cào chạy đa luồng, và muốn xem được log cào cùng tình trạng backend bằng lệnh console trên VM (backend
chạy bằng docker compose trên cùng VM). Làm tiếp trên working tree chưa commit của
`history/2026-09-24-luong-cao-index-backend-sau-audit.md`. Phục vụ FR-CAT-01/03 (catalog tươi) và vận hành theo
`docs/prd/deployment-plan.md` §3, §5.

## File thay đổi

- `src/data_collection/fresh_catalog.py` — sửa: lượt full chạy 4 nhóm site (`SITE_GROUPS`: trip, vinpearl, booking, agoda)
  song song, tối đa `CRAWL_PARALLEL` (mặc định 2); trong nhóm tuần tự như trước, nhóm trip gồm tìm ID khách sạn → vé máy
  bay → điểm tham quan → giá phòng; `run_source` gắn tiền tố `[nhóm]` cho từng dòng log của `crawl.py`; mốc
  `catalog.group.start/done/skip`; `status` in thêm số site song song.
- `src/data_collection/run_daily_docker.sh` — sửa: lệnh `logs [-f] [-n SỐ_DÒNG] [LƯỢT]`, `report [SỐ_LƯỢT]`,
  `backend [logs [-f] [-n SỐ_DÒNG]]`; `run status` in thêm lượt đang chạy (từ lúc nào, nhóm đang cào, CPU/RAM) và lượt
  gần nhất; mỗi log ghi dòng `fresh-catalog.start` và `fresh-catalog.exit=N finished=…`; cập nhật phần hướng dẫn đầu file.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: thêm `CrawlSitesTests` (tối đa 2 site cùng lúc, thứ tự trong
  nhóm trip, 1 site = tuần tự như cũ, mã 75 được chấp nhận còn nguồn lỗi làm bỏ site chưa bắt đầu, lượt full gọi đủ nguồn).
- `src/data_collection/README.md` — sửa: mục lượt full song song, biến `CRAWL_PARALLEL` trong env mẫu của VM, khối lệnh theo
  dõi trên console và ý nghĩa cột RESULT của `report`.
- `history/2026-09-25-cao-song-song-va-lenh-theo-doi.md` — thêm: entry này.

## Quyết định

- Người dùng chọn tối đa 2 site cùng lúc: Vinpearl, Booking, Agoda và giá phòng Trip đều mở Chromium, VM 2 vCPU/4 GB.
  `CRAWL_PARALLEL=1` trở về lượt tuần tự cũ.
- Người dùng dặn tạm bỏ qua giới hạn lịch sự của spec và giữ theo code: tốc độ trong từng site giữ nguyên (không thêm
  worker, không giảm delay), chỉ song song giữa các site khác nhau, nên số request đồng thời tới từng domain không đổi.
  Cách chạy này theo mẫu `daily.py` (worker theo site, cùng thư mục dữ liệu, SQLite WAL).
- Một nguồn lỗi (mã khác 0/75) thì các site chưa bắt đầu bị bỏ, site đang chạy chạy xong, rồi lượt dừng trước khi nạp DB —
  giống lượt tuần tự cũ dừng ở nguồn lỗi đầu tiên. Bước index vẫn chạy trong `finally` như trước.
- Theo dõi backend chỉ bằng lệnh console (người dùng chọn): gọi `/health` hiện có, đọc `docker logs` của container có nhãn
  compose `service=backend` (dòng `startup.recsys.*`, `catalog.refresh.*`, `recsys.vectors.out_of_sync`, lỗi 1 giờ). Không
  thêm `/health/ready`, nên không đổi OpenAPI hay backend.
- `report` là bash thuần (grep/awk trên log của runner) để VM chỉ cần Docker và file runner; cột cố định dùng ASCII vì
  `printf` căn theo byte.

## Kiểm tra

- `cd src/data_collection && PYTHONPATH=<repo>/src python -m pytest -q tests`: 315 passed, 3 skipped (thêm 4 test).
- `bash -n run_daily_docker.sh run_fresh_catalog_container.sh`, `git diff --check`: sạch.
- Lệnh console trên 4 log mẫu (daily ok, full lỗi ở booking, index lỗi 429, full đang chạy) và container giả đang chạy:
  `report 10` ra đúng mode/phút/kết quả/dòng mới-làm mới/embed-xoá/ghi chú; `logs 2 -n 4` đúng lượt trước; `run status` in
  thời điểm bắt đầu, CPU/RAM, nhóm đang cào `booking, trip`; tham số sai in cách dùng, mã 1.
- `backend` với container giả mang nhãn compose `service=backend`: in health, trạng thái container, CPU/RAM, 4 dòng RecSys,
  2 dòng lỗi; `backend logs -n 3` đúng 3 dòng; không có backend thì báo không phản hồi và không thấy container, mã 0.
- `docker build -f Dockerfile.fresh-catalog -t vota-fresh-catalog:review-fix .`: pass; `status` với `CRAWL_PARALLEL=3` in
  `parallel sites (full): 3`. Container giả đã xoá.
- Chưa chạy lượt full thật ở chế độ song song.

## Còn lại / rủi ro

- Cần xem RAM ở lượt full đầu tiên trên VM (`run status`); thiếu RAM thì đặt `CRAWL_PARALLEL=1`.
- Lượt daily chỉ cào Trip nên không nhanh hơn.
- Bước tìm ID và hỏi giá phòng của Trip chạy trong tiến trình chính nên dòng log của chúng không có tiền tố `[trip]` và có
  thể xen với site khác; mốc `catalog.group.*` vẫn cho biết nhóm nào đang chạy.
- Log tạo trước bản runner này không có dòng `fresh-catalog.exit`, `report` hiện `?` ở cột RESULT.
- `/health/live`, `/health/ready`, `/metrics` của `deployment-plan.md` §5 vẫn chưa có (tồn đọng từ trước).
- Bộ cào Trip hiện giả dạng trình duyệt (`impersonate='chrome124'`) trên đường dẫn robots.txt cấm và vượt mức
  `data-collection-spec.md` §8 — tồn đọng từ trước, không đổi trong task này.
- Chưa commit; working tree còn chung thay đổi của entry 2026-09-24.
