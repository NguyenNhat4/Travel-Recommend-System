# Monitor: số lượng theo thành phố của từng nguồn

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người dùng hỏi vì sao chưa xem được mỗi thành phố đang có bao nhiêu sản phẩm theo từng nguồn. Monitor chỉ có tổng theo nguồn
và bộ lọc thành phố trong Catalog. Thêm bảng thành phố × nguồn cho demo "cào vài thành phố trước". Phục vụ FR-CAT-01..04.
Không đổi PRD, contract, DDL. Nối tiếp `history/2026-09-25-chuan-hoa-nhap-khi-site-xong.md`.

## File thay đổi

- `src/data_collection/monitor.py` — sửa: `/api/cities` (tham số `preview=1`); `product_type()`, `interim_city()`, `InterimTally` (đếm interim theo thành phố, đọc tăng dần).
- `src/data_collection/monitor_ui/index.html` — sửa: tab "Theo thành phố".
  - Bảng catalog: thành phố × loại × nguồn + số dòng gộp nhiều nguồn, dòng tổng. Bấm tên thành phố để mở Catalog đã lọc.
  - Bảng interim: thành phố × nguồn, tự cập nhật 5 giây khi lượt đang chạy.
- `src/data_collection/tests/test_live_monitor.py` — sửa: 2 test (ma trận catalog; interim đếm tăng dần, dòng dở, file bị ghi lại; bản nháp).
- `src/data_collection/README.md` — sửa: mô tả tab.
- `history/2026-09-25-monitor-so-luong-theo-thanh-pho.md` — thêm: entry này.

## Quyết định

- Số chính xác theo thành phố lấy từ catalog đã chuẩn hoá (trường `destination`), bản nháp hoặc chính thức. Interim không có trường thành phố thống nhất:
  - booking, agoda, điểm tham quan Trip có `plan.destination`;
  - vé máy bay có `toCity`;
  - vé Vinpearl có `destinationName`;
  - khách sạn Trip có `city`;
  - khách sạn Vinpearl không có trường nào.

  Bảng interim dùng các trường đó qua `collectors.geo.normalise_destination`; bản ghi không có thì xếp "chưa rõ — xác định khi chuẩn hoá".
- Cột nguồn của bảng catalog tính theo `sourceRef` (nguồn thắng khi gộp trùng); cột "gộp nhiều nguồn" đếm dòng có `sameAs`.
- `InterimTally` chỉ parse phần mới thêm của file interim, bỏ dòng đang ghi dở, và đếm lại khi file bị ghi lại (booking/trip ghi lại interim cuối nguồn). Nhờ vậy tự cập nhật 5 giây không phải parse lại cả file lớn.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -q -p no:cacheprovider tests` (env `vsf`): **358 passed, 3 skipped**.
- `git diff --check`: sạch.
- Monitor phụ cổng 8766 trên bản sao lượt lỗi `full-20260925T073016Z` (thư mục tạm):
  - Bản nháp Vinpearl 120 dòng: Nha Trang 53 (6 khách sạn, 47 hạng phòng), Phú Quốc 19…
  - Bảng interim: 16 bản ghi khách sạn Vinpearl ở dòng "chưa rõ".

## Còn lại / rủi ro

- Bảng cho thấy một dòng có thành phố "Vinpearl Onsen Resort Tuyên Quang": normalise không map được điểm đến nên dùng tên sản phẩm. Lỗi dữ liệu có từ trước, chưa sửa trong task này.
- Monitor người dùng đang mở phải khởi động lại để có tab mới.
- Chưa commit.
