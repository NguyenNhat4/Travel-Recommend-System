# Xoay vòng ID Trip.com trên VM console

- Ngày: 2026-09-24
- Tác giả: người dùng / Codex
- Nhánh: codex/fresh-trip-catalog-release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Hướng dẫn luồng cào mới chạy trên Google Cloud VM chỉ có console, cấu hình 2 CPU và 4 GB RAM, với lô giá hữu hạn và lịch xoay vòng ID.

## File thay đổi

- `src/data_collection/README.md` — sửa: ghi giới hạn lượt full/daily, biến cấu hình phù hợp VM và quy tắc giá Trip quá hạn.
- `history/2026-09-24-xoay-vong-id-trip-tren-vm.md` — thêm: entry này.

## Quyết định

- Bám FR-CAT-03: giá/phòng theo ngày chỉ phản ánh mốc đã hỏi; crawler ở repo `tripcom-hotel-crawler` giữ thời điểm thử theo ID để xoay vòng. Không đổi schema hay contract.
- Mặc định 2 tab Chromium trong Xvfb và 4 worker HTTP cho VM 2 CPU/4 GB; cần đo tải thật trên VM trước khi tăng.
- Các khách sạn cũ vẫn nằm trong DB; giá Trip.com gốc quá 7 ngày chưa được hỏi lại chuyển sang trạng thái chưa khả dụng.

## Kiểm tra

- Crawler: `python -m unittest discover -s tests` trong `vsf2`: 130 tests pass; `bash -n scripts/run_catalog_vm.sh`: pass.
- Chưa chạy trên Google Cloud VM thật.

## Còn lại / rủi ro

- Số ID tăng làm chu kỳ làm mới dài ra ở ngân sách 60 khách sạn/ngày. Vùng tìm kiếm 300 ID/thành phố cần tăng khi đã hết ID mới.
