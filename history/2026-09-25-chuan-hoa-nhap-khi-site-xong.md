# Chuẩn hoá nháp mỗi khi một site cào xong (xem trước trên monitor)

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Lượt cào lớn chạy 4 site song song, nhưng normalise → validate → nạp DB → index chỉ chạy một lần sau khi mọi site xong.
Người dùng chọn "cách A": khi một site xong thì chuẩn hoá nháp phần đã có để xem sớm trên monitor trong lúc các site khác
còn cào; nạp DB và index vẫn đợi đủ. Phục vụ FR-CAT-01..04. Không đổi PRD, contract, DDL; nối tiếp
`history/2026-09-25-monitor-cao-local-real-time.md`.

## File thay đổi

- `src/data_collection/fresh_catalog.py` — sửa: thêm `Previewer` và `normalise_args()` dùng chung cho bản chính thức và bản nháp; `crawl_sites()` nhận `previewer`, kích hoạt khi một nhóm xong mà còn nhóm khác chưa xong, hoặc khi lượt đã lỗi; nhóm cuối của lượt không lỗi thì bỏ.
- `src/data_collection/fresh_settings.py` — sửa: thêm khoá `normalise.preview` (mặc định bật).
- `src/data_collection/monitor.py` — sửa:
  - Tham số `preview=1` cho `/api/products`, `/api/product`, `/api/normalise*`; `/api/run` trả `preview`.
  - `FileCache` phân biệt kiểu đọc. Trước đây bảng nguồn đếm dòng interim và truy vết sản phẩm đọc interim dùng chung một khoá cache, nên bảng nguồn làm hỏng truy vết (`'int' object is not iterable`).
- `src/data_collection/monitor_ui/index.html` — sửa: công tắc Nháp / Chính thức ở tab Chuẩn hoá và Catalog cuối; dòng trạng thái bản nháp ở tab Luồng & nguồn; lọc log "Chuẩn hoá nháp".
- `src/data_collection/tests/test_live_monitor.py` — sửa: 5 test mới:
  - bản nháp thật trên interim của một site đã xong;
  - gộp các lần kích hoạt dồn dập;
  - dừng bản nháp khi bản chính thức sắp chạy;
  - khi nào kích hoạt trong lượt sạch và lượt lỗi;
  - monitor đọc bản nháp;
  - kiểm thêm lỗi cache.
- `src/data_collection/README.md` — sửa: mô tả bản nháp.
- `history/2026-09-25-chuan-hoa-nhap-khi-site-xong.md` — thêm: entry này.

## Quyết định

- Bản nháp chạy `normalise.py` trong tiến trình con, không gọi trong tiến trình job. Lý do: normalise cấu hình lại logging gốc, còn job có luồng khác đang chạy. Tham số giống hệt bản chính thức (`normalise_args`).
- Chỉ lấy interim của các site đã xong, qua hard link. Site đang chạy vẫn ghi dở interim của nó, nên không đưa vào.
  - Bản nháp được dựng trong `preview.next/` rồi đổi tên thành `preview/`, nên monitor không đọc phải bản dở.
  - `preview/` nằm trong thư mục lượt, nên bị dọn cùng lượt theo `runs.keep`.
- Mỗi lúc một bản nháp. Site xong trong lúc đang chạy nháp thì chạy lại một lần với tập mới nhất.
- Bản chính thức sắp chạy (mọi site xong, không lỗi) thì dừng bản nháp đang chạy. Lượt lỗi thì đợi bản nháp cuối xong, để vẫn xem được dữ liệu đã cào dù lượt không nạp DB. Người vận hành bấm Dừng thì bản nháp bị dừng cùng tiến trình con.
- Bản nháp được ghi thành bước `normalise.preview` (nhóm `preview`) trong run.json. Lỗi của bản nháp không làm hỏng lượt.
- Có công tắc tắt trong Cấu hình, dành cho VM yếu.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -q -p no:cacheprovider tests` (env `vsf`): **356 passed, 3 skipped**.
- `git diff --check`: sạch.
- Monitor phụ ở cổng 8766 trên bản sao của lượt lỗi `full-20260925T073016Z` (thư mục tạm):
  - Bản nháp của Vinpearl: 120 dòng trong 0,3 giây.
  - Tab Luồng & nguồn hiện dòng bản nháp. Catalog và Chuẩn hoá tự chuyển sang Nháp vì lượt chưa có bản chính thức.
  - Chi tiết sản phẩm truy về raw/interim; truy vết qua 5 bước khớp 1 dòng mỗi bước; DB để trống.
- Bộ demo (`vota_crawl_demo`) và monitor của người dùng ở cổng 8765 không bị đụng.

## Còn lại / rủi ro

- Monitor người dùng đang mở phải khởi động lại để nạp API mới. Lượt mới do monitor mở tự dùng code mới.
- Chưa đo thời gian chuẩn hoá nháp ở phạm vi đầy đủ. Mỗi bản nháp chuẩn hoá lại toàn bộ interim của các site đã xong, chạy song song với các site còn đang cào.
- Chưa commit.
