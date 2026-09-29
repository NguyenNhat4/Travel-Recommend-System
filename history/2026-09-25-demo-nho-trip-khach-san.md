# Kiểm tra Trip khách sạn và chạy luồng demo nhỏ

- Ngày: 2026-09-25
- Tác giả: Đăng Khôi / Codex
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data (vận hành demo local)

## Mục tiêu

Kiểm tra monitor http://127.0.0.1:8765/, phân biệt vấn đề Trip khách sạn/giá phòng với hiển thị UI, chạy luồng nhỏ để trình bày output từng bước trong 15 phút. Phục vụ FR-CAT-01..03 và FR-SRC-02; dùng chức năng hiện có, không sửa source hoặc thay đổi PRD.

## File thay đổi

- `history/2026-09-25-demo-nho-trip-khach-san.md` — thêm: ghi nhận cấu hình vận hành và kết quả thật.
- Dữ liệu runtime ignored tại `src/data_collection/data/local_crawl_demo/` được monitor/job cập nhật: `state/settings.json`, `state/trip_targets.json`, `state/trip_schedule.json`, marker/lịch sử lượt và hai thư mục `runs/full-20260925T090555Z-186774/`, `runs/full-20260925T090724Z-188511/` (raw, browser state, interim, báo cáo, catalog, stages, DB/index detail). Không thêm các artifact runtime vào Git.
- Những file source đang modified/untracked khi bắt đầu task thuộc công việc có sẵn; task này không sửa chúng.

## Quyết định

- Lượt cũ `full-20260925T080534Z-135475` đã tìm 68 ID, nhưng thứ tự trong nhóm Trip là discovery → flights → attractions → prices. Bị dừng khi attractions đang chạy; chưa hỏi giá và chưa đến đoạn lưu targets sau DB. Do đó monitor hiện 0 ID xoay vòng và daily báo chưa có ID là phù hợp.
- Chạy riêng Trip khách sạn, tắt Vinpearl, Booking, Agoda, Trip flights và attractions bằng trang Cấu hình. Không đổi delay, worker, thuật toán hay schema.
- Lượt 1: Phú Quốc, 3 khách sạn, ba mốc 14/30/60; thất bại sau 9 giây do HTML nguồn hiện 0 nơi lưu trú. HTML cũ cùng thành phố/ngày có 1.272 nơi lưu trú và 12 card; không kết luận thực sự không có khách sạn.
- Lượt 2: Nha Trang + Phú Quốc, tối đa 1 ID/thành phố, scan 12, dailyHotels 2, giữ mốc 14/30/60. Nha Trang trả 0; Phú Quốc trả 5 card và chọn 1. Giữ cấu hình này cho demo. Đây là quan sát gợi ý vấn đề trang đầu/phiên mới, chưa chứng minh nguyên nhân gốc.
- Toàn bộ dữ liệu mới ghi vào `vota_crawl_demo` và `ProductCrawlDemo` trên localhost qua pipeline hiện có. Không dùng lại snapshot hoặc dữ liệu giá cũ.

## Kiểm tra

- Dùng browser mở, chỉnh cấu hình và chạy monitor thật.
- Đọc `run.json` và `job.log` của các lượt; so HTML raw bằng gzip + BeautifulSoup.
- `full-20260925T090724Z-188511`: status ok, exitCode 0, 23 giây.
- VARIA Hotel Phu Quoc, Trip ID 128030105: metadata HTTP 200; 2026-10-09 và 2026-10-25 có 7 offers; 2026-11-24 nguồn xác nhận sold_out.
- Normalize + validate thành công: 1 property + 7 room = 8 sản phẩm; DB ghi 8 dòng mới.
- Cohere embed-multilingual-v3.0:catalog-text-v2: 1 search unit, 1 embedded, không xoá vector mồ côi.
- UI đã kiểm: Tổng quan Xong/23s/8 sản phẩm/1 Trip; Raw/interim có 6 file và 1 bản ghi; Chuẩn hoá có 5 bước đều 8 dòng; Catalog cuối có tên và giá 7 hạng phòng; Nạp DB có 8 dòng new; Embedding có 1 vector.
- Không sửa code/contract/schema/seed; không chạy unit test, validate_contract.py hoặc db/verify.sql. Pipeline tự chạy validate cho catalog mới.

## Còn lại / rủi ro

- Trang đầu Trip trả rỗng trong các lượt đã quan sát; chưa sửa collector và chưa xác định nguyên nhân gốc. Không bảo đảm lượt tiếp theo luôn có dữ liệu.
- Header chi tiết lượt có lúc giữ nhãn Đang chạy dù dữ liệu cuối đã có; về Tổng quan rồi mở lại lượt hiện Xong. Không sửa UI trong task này.
- Monitor báo COHERE_API_KEY chưa đặt theo env tiến trình nhưng index thực tế thành công (backend có thể đọc .env); không dùng nhãn này để kết luận index hỏng.
- Chưa commit.
