# Plan: bỏ chờ đợi giữa các bước của job cào (P1–P4)

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs (data)

## Mục tiêu

Người yêu cầu hỏi pipeline đã giống Airflow ở đâu, bước nào đang đợi bước nào, và vì sao chưa chạy song song. Sau khi
nghe phân tích, người yêu cầu yêu cầu viết plan cho 4 đề xuất:
1. chuẩn hoá theo nguồn thay vì theo nhóm site;
2. chạy thật chế độ chạy liên tục rồi bật mặc định;
3. khai báo đồ thị bước ở một chỗ;
4. hạn giờ theo nguồn và cào lại một nguồn.

## File thay đổi

- `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` — thêm: plan P1–P4, mục "Cần chốt", bảng đối chiếu Airflow cập nhật.

## Quyết định

- Căn cứ số đo của lượt `full-20260928T073959Z-221577` (sandbox):
  - chuẩn hoá `trip_flights` đợi `trip-attractions` 1 phút 49 giây;
  - gộp, kiểm tra, nạp DB đợi Vinpearl ~16 phút sau khi mọi nguồn khác xong.
- Không tách nhóm Trip thành các luồng song song: cùng site, tăng nguy cơ bị chặn.
- Không chạy song song bên trong Vinpearl: chậm do cố ý giãn 2 giây giữa hai request tới cùng host
  (`collectors/vinpearl.py:82`).
- Phát hiện khi đọc code: `fresh_catalog.py` không có hạn giờ nào.
  - `MAX_HOURS` chỉ truyền cho `daily.py` (`run_daily_docker.sh:77`).
  - Bảng đối chiếu Airflow của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` ghi `dagrun_timeout` là "có": sai
    với job mới.
  - Bảng đó cũng còn ghi CP6–CP8 là "chưa" dù đã xong.
  - Plan mới ghi bảng thay thế; **chưa sửa** plan cũ.
- Hạn giờ mặc định, nơi chạy lượt kiểm P2, mặc định của `stream.index`, cào lại tay hay tự động, và cách xử lý khách sạn
  Trip là **đề xuất của agent**, ghi ở mục "Cần chốt".
- Không lệch PRD: PRD không quy định cách job cào sắp xếp bước.

## Kiểm tra

- Chỉ viết tài liệu; không chạy test.
- Đã đọc:
  - `fresh_catalog.py`: `crawl_sites`, `Previewer`, `crawl_and_load`, `resume_run`, `run_source`, `normalize`;
  - `monitor.py`: hằng số sơ đồ, `graph()`;
  - `fresh_run_log.py`: `RunRecorder.resume`, `terminate_children`;
  - `fresh_settings.py`: `stream.*`, `crawl.parallelSites`;
  - `crawl.py`, `collectors/vinpearl.py`, `run_daily_docker.sh`, `run_fresh_catalog_container.sh`;
  - `run.json` của 3 lượt full trong `data/local_crawl/runs`;
  - entry `history/` L1–L6.

## Còn lại / rủi ro

- Chờ người yêu cầu duyệt plan và chốt 5 mục "Cần chốt".
- Chờ quyết định có sửa bảng đối chiếu Airflow trong plan 28/09 hay không.
- Chưa commit.
