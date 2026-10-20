# Tìm nhanh trên toàn database ở tab DB của monitor

- Ngày: 2026-10-13
- Người đề xuất: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Trạng thái: đã áp dụng (PRD `docs/prd/deployment-plan.md` §5 và source cập nhật 2026-10-13)
- Chốt bởi / ngày: Phạm Nguyễn Đăng Khôi, 2026-10-13 ("chốt, làm phần tìm nhanh tab DB luôn đi")
- PRD bị ảnh hưởng: `docs/prd/deployment-plan.md` §5, mục "Xem DB trên monitor job cào (tab "DB")"
- Mã FR/NFR: không đổi FR/NFR; công cụ vận hành, giữ ngoại lệ đọc `cdp.*` của `docs/prd/requirements.md` (dòng "công cụ vận
  hành 'xem DB' trên monitor") và NFR-SEC-01 (cột bí mật không hiện, không tìm được)

## Lý do

Người dùng (13/10): tìm dữ liệu ở tab DB "hơi gò bó", muốn "search data nào là ra nó ngay". Hiện phải chọn đúng bảng trước;
ô tìm của bảng ghép mọi cột thành chuỗi rồi `ILIKE`, phân biệt dấu ("ba na" không ra "Bà Nà"), chỉ chạy khi bấm, và đếm cả
bảng nên bảng lớn (`cdp.products` ~40 nghìn dòng, cột `attributes` nặng) dễ chạm giới hạn 5 giây.

## Nội dung đề xuất

`docs/prd/deployment-plan.md` §5, mục "Xem DB trên monitor job cào (tab "DB")":

Hiện tại: "danh sách schema / bảng kèm số dòng; xem từng bảng có phân trang, lọc, sắp xếp; …"

Thay bằng: "danh sách schema / bảng kèm số dòng; **ô tìm nhanh chung cho cả database**: gõ là hiện kết quả (không cần
chọn bảng, không cần bấm), không phân biệt hoa thường và dấu tiếng Việt; mã dạng UUID khớp đúng ở mọi cột UUID của mọi
bảng (sản phẩm, người dùng, đơn, hồ sơ và sự kiện CDP…); chuỗi khác tìm trong các cột chữ ngắn của từng bảng (tên, điểm đến,
`source_ref`, email, mã đơn…), mỗi bảng tối đa 10 kết quả, mỗi bảng chịu riêng giới hạn 5 giây (bảng quá giờ báo "quá giờ",
bảng khác vẫn hiện); bấm một kết quả mở dòng đó kèm liên kết như hiện nay. Xem từng bảng có phân trang, lọc (ô lọc của bảng
cũng không phân biệt dấu và tìm khi đang gõ), sắp xếp; …"

Phần còn lại của mục giữ nguyên: chỉ đọc, `statement_timeout` 5 giây, chỉ database `vota`, cột bí mật không tìm được.

## Thay đổi source sau khi chốt

- `src/data_collection/db_browser.py`: hàm tìm chung (UUID khớp đúng; chữ: so sánh không dấu bằng `translate()` trên các cột
  chữ ngắn, không cần extension `unaccent`); ô lọc bảng không phân biệt dấu.
- `src/data_collection/monitor.py`: route `GET /api/dbx/search?q=`.
- `src/data_collection/monitor_ui/index.html`: ô tìm nhanh ở đầu tab DB (chờ ~0,3 giây sau phím cuối), kết quả nhóm theo
  bảng; ô lọc bảng tìm khi đang gõ.
- `src/data_collection/tests/` test cho tìm chung và ô lọc; `src/data_collection/README.md` phần monitor.
- Kiểm tra trên Postgres local (`make demo-db` hoặc bản sao catalog) trước khi merge; không chạy trên production trước khi
  người dùng cho phép.
