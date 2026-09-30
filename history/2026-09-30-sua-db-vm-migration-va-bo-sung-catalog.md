# Áp migration và bổ sung catalog còn thiếu trên DB VM

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Người dùng yêu cầu thực hiện sửa hai lỗi nền DB đã báo: thiếu app.payments và tổng catalog dưới 11.387. Thay thế trạng thái còn lỗi DB trong entry `2026-09-30-ve-thuong-gia-that-va-import-vm.md`; các phần chưa deploy/key VM trong entry đó vẫn còn nguyên.

## File thay đổi

- `history/2026-09-30-sua-db-vm-migration-va-bo-sung-catalog.md` — thêm: kết quả thao tác DB thực tế.
- `docs/guide/ve-thuong-gia-va-index-cho.md` — sửa: cập nhật DB đã hoàn tất migration và số catalog mới.
- Không sửa source, DDL hay migration hiện có. Artifact aggregate/checksum/catalog delta/report nằm trong `src/data_collection/data/vm-repair-20260930/` ignored, không có bản xuất user/profile/event.

## Quyết định

- Phục vụ FR-BKG-05..07, FR-CAT-01/03, NFR-REL-01; không đổi PRD. Migration booking hiện thực nền dữ liệu cho AC-BKG-01..04; chưa nghiệm thu Stripe/API trong task này.
- Đọc PRD README/requirements/deployment, DB/spec/history từ task trước, đọc lại runner + 0001..0004, history migration 21/09 và booking 24/09, snapshot 29–30/09, loader và verify.
- Dùng tài khoản người dùng đã cấp qua SSH tunnel, DB vota. Không restart dịch vụ, không reset, không chạy initdb.
- Runner `db/migrations/run.py` áp đủ 0001,0002,0003,0004. Trước đó tracking rỗng; bảng vector và extension vector đều đã không tồn tại (0002 no-op). 0003 tạo payments và một payment provider seed/succeeded cho đơn confirmed cũ.
- Snapshot 2026-09-30 có 1.362 ID chưa có trên VM. Build bằng loader `--catalog-only --real-flight-dates --generate-only`; loại 31 vé không fixed-date mà loader dời departure/arrival. Chỉ nạp 1.331 ID còn thiếu bằng `seed.database.upsert_catalog`, dùng cùng outer transaction và khóa ghi catalog để không thể ghi đè ID hiện hữu. Mapping chỉ của 40 combo mới; không thay mapping combo cũ.
- Đề nghị sao lưu toàn bộ bảng bị auto-review chặn vì có dữ liệu riêng tư ngoài phạm vi yêu cầu. Không xuất payload nhạy cảm; thay bằng counts và checksum tính tại DB. Không dùng đường vòng để xuất backup đó.

## Kiểm tra

- Migration runner: 4 migration áp thành công; status sau = 4 đã áp, 0 chờ.
- Catalog: 10.930 → 12.261. Thêm 957 hotel, 39 attraction, 40 combo, 295 flight (bao gồm route); updated=0, retired=0, giữ nguyên 10.930 dòng có sẵn.
- Combo mapping: 328 → 417, thêm 89; không thay dòng cũ.
- So checksum toàn bộ các cột cũ: cdp.profiles, cdp.events, app.users, app.booking_items, sản phẩm/mapping cũ đều không đổi.
- Profiles=2.000, events=7.131, users=54, bookings=1, booking_items=1; payments=1.
- db/verify.sql: **18/18 PASS**, kiểm trong transaction trước commit; đã commit thành công.
- BUSINESS vẫn 43, tất cả available, ngày 15/10/2026: HAN-SGN 17; SGN-HAN 6; HAN-DAD 6; SGN-DAD 6; SGN-PQC 4; HAN-CXR 4.
- DB có 560 flight roundTrip, 268 ECONOMY và 292 UNKNOWN; 357 available. Một chiều 493 UNKNOWN và 43 BUSINESS; 113 route. Các dòng UNKNOWN không được suy thành economy/business.

## Còn lại / rủi ro

- 31 vé bị dời ngày không nạp; chờ dữ liệu cào thật mới. Không sửa loader trong task vận hành này.
- Chưa index các search unit bổ sung trên Weaviate: task này chỉ sửa DB, cấu hình cloud Weaviate chưa có và không restart VM. Không coi verify DB là xác nhận search vector hay Stripe hoạt động.
- Người dùng sau đó yêu cầu tự cào khi deploy; xử lý trong entry/task tiếp theo, không thay kết quả DB đã hoàn tất.
