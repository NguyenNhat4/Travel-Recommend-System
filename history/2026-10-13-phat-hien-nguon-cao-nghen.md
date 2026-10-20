# Phát hiện nguồn cào bị nghẽn; bật cào song song 2 site

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: fix/crawl-stall-watchdog (worktree `~/code/trp-crawl-stall`, tách từ `origin/release-mvp-v2` 71333eee)
- Trạng thái: dang dở — code + test xong, đã commit + push nhánh, chưa PR/deploy (người dùng: test local, mai merge)
- Phạm vi: data

## Mục tiêu

Người dùng: job cào phải "gọi song song và luôn ổn định nếu 1 luồng nghẽn hoặc error", "nếu có 1 đỏ cũng được nhưng các
bước sau phải xanh hết", "ok đổi parallelSites lên 2 và làm phần phát hiện nghẽn". Lượt full 11/10: Booking hết giờ sau 10 giờ
(làm mới 1.375/1.822), các bước sau (chuẩn hoá, kiểm tra, DB, index) vẫn xanh — đúng thiết kế, nhưng một nguồn treo giữ
các bước sau tới hết hạn giờ của nó (`timeout.booking` 600 phút) vì chỉ có hạn giờ tổng, không có kiểm tra "không tiến triển".
Lượt 09/10 và 10/10 hỏng cả lượt do lịch tắt VM 23:59 (đã gỡ bằng PR #180, CD gỡ lịch 13/10 00:11).

## File thay đổi

- `src/data_collection/fresh_catalog.py` — sửa: `run_source` theo dõi lần cuối nguồn in log hoặc ghi thêm interim
  (`interim_sizes`, đọc kích thước mỗi min(5 s, ngưỡng/4)); quá `timeout.stallMinutes` thì dừng riêng cây tiến trình của nguồn,
  trả `EXIT_STALLED`. `crawl_sites`: nghẽn được thử lại như lỗi tạm thời; hết lượt thử thì bước kết thúc `timeout` với
  `detail.errorKind = stalled`, `detail.stalls`, `detail.reason`, phần đã cào được chốt và chuẩn hoá.
- `src/data_collection/pipeline_errors.py` — sửa: loại lỗi `stalled` ("nghẽn"), mã thoát 76, `classify_exit`, `strategy` (thử
  lại như transient), bảng chiến thuật ở docstring.
- `src/data_collection/fresh_settings.py` — sửa: setting `timeout.stallMinutes` (mặc định 30, 0 = tắt).
- `src/data_collection/alerts.py` — sửa: cảnh báo "Nguồn nghẽn" thay cho "Nguồn quá hạn giờ" khi `errorKind = stalled`.
- `src/data_collection/tests/test_timeouts_recrawl.py` — sửa: 7 test (nguồn im lặng bị dừng cùng tiến trình con; log hoặc
  interim lớn dần giữ nguồn chạy; 0 = tắt; phân loại + chiến thuật; thử lại rồi giữ phần đã cào, nguồn khác chạy tiếp; cả
  lượt `partial`, chuẩn hoá/kiểm tra/DB/index đều chạy, có cảnh báo `stalled`).
- `src/data_collection/README.md` — sửa: đoạn "Nghẽn" ở mục "Hạn giờ và phục hồi khi nghẽn".
- `history/2026-10-13-phat-hien-nguon-cao-nghen.md` — thêm: entry này.

Cùng worktree, entry riêng: `src/data_collection/monitor_ui/index.html` (`history/2026-10-13-doi-ten-monitor-sang-sota.md`),
`docs/prd/update/2026-10-13-tim-nhanh-tab-db-monitor.md` (`history/2026-10-13-de-xuat-tim-nhanh-tab-db.md`).

## Quyết định

- Ngưỡng mặc định 30 phút: lần nghỉ dài nhất hợp lệ của collector là 900 s (`BlockBreaker.cooldown`, có log trước khi nghỉ);
  bộ đếm tiến độ in log 30 s/lần; các lượt local trong `data/local_crawl*` im lặng dài nhất ~2 phút.
- Hoạt động = dòng log HOẶC interim lớn thêm: collector im lặng nhưng vẫn ghi dữ liệu không bị coi là nghẽn.
- Nghẽn hết lượt thử kết thúc `timeout` (trạng thái monitor đã biết, có nút "Cào lại nguồn này"), không phải `error`; trạng
  thái nhóm site giữ như quá giờ. Không lệch PRD: PRD không quy định nội bộ job cào; README đã mô tả hạn giờ từng nguồn.
- Bước trong tiến trình (khách sạn Trip) chưa có kiểm tra nghẽn: vẫn theo hạn giờ của bước (ghi trong README).
- Cấu hình VM (người dùng đồng ý 13/10 00:42): `crawl.parallelSites` 1 → 2 qua `POST /api/settings` của monitor production;
  đọc lại: `crawl.parallelSites = 2`, các khoá đã lưu khác giữ nguyên. Không đổi `booking.tabs` (vẫn 1).

## Kiểm tra

- `cd src && python -m pytest -q data_collection/tests/test_timeouts_recrawl.py data_collection/tests/test_pipeline_errors.py`:
  38 passed.
- `cd src && python -m pytest -q data_collection/tests` (vsf2): 666 passed, 27 skipped (trước 659 + 7 test mới).
- Chưa chạy lượt cào thật với code này (DB production tắt từ 13/10 00:45; người dùng: test local, mai merge).

## Còn lại / rủi ro

1. PR vào `release-mvp-v2`, Crawler CD — khi người dùng bảo.
2. `crawl.parallelSites = 2` trên VM e2-medium 4 GB (giới hạn container `FRESH_MEMORY` 2,5 GB): theo dõi RAM ở lượt full đầu.
3. Booking vẫn chậm (1 tab, ~26 s/khách sạn) và tìm theo điểm đến trả 0 ở 8 điểm đến: người dùng chấp nhận một nguồn đỏ.
4. VM DB/crawler/bastion do Khoa tắt tay 13/10 00:44–00:45, lịch bật 08:30 đã gỡ: phải bật tay.
