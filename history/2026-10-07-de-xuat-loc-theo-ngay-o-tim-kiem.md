# Đề xuất PRD: lọc theo ngày ở tìm kiếm

- Ngày: 2026-10-07
- Tác giả: mihhquan / Claude
- Nhánh: feat/fix-bug
- Trạng thái: dang dở (đã tạo đề xuất; chờ chốt)
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu ô ngày và số khách ở tấm tìm kiếm của `/hotels`, `/experiences`, `/combos` phải là tiêu chí tìm thật. Số khách đã có sẵn ở Backend (`travelContext.guests`, contract 1.16.0). Ngày thì Backend chưa đọc `checkIn/checkOut`, nên cần thêm bộ lọc ở backend và contract. Người dùng chọn lọc mạnh (loại khách sạn kín lịch), lệch FR-CAT-03 ("lịch chỉ để tham khảo, không dùng để chặn"), nên phải có đề xuất đã chốt trước khi sửa source (AGENTS.md mục 8).

## File thay đổi

- `docs/prd/update/2026-10-07-loc-theo-ngay-o-tim-kiem.md` — thêm: đề xuất sửa FR-SRC-03, FR-CAT-03 và thêm AC-SRC-03; trạng thái "chờ chốt".
- `history/2026-10-07-de-xuat-loc-theo-ngay-o-tim-kiem.md` — thêm: entry này.

## Quyết định

- Không tự chốt; chưa sửa PRD, contract, backend (AGENTS.md mục 8, bước 2). Phần số khách không lệch PRD nên làm riêng, không chờ đề xuất này.
- Lịch chỉ dùng cho bộ lọc tìm kiếm; đặt phòng vẫn theo FR-CAT-03 hiện hành (lịch không chặn).
- Căn cứ khảo sát: sản phẩm tìm được là khách sạn (property, lịch nằm ở các hạng phòng con), vé tham quan, golf, combo; vé máy bay không có trong `/search` của Web.

## Kiểm tra

- Chỉ có thay đổi tài liệu; không chạy lệnh kiểm tra.

## Còn lại / rủi ro

- Chờ mihhquan chốt (hoặc yêu cầu sửa). Khi chốt: sửa `docs/prd/` trước, rồi contract 1.19.0, backend, frontend, test, spec, chuyển đề xuất sang `update-archive/`.
- Rủi ro đã nêu trong đề xuất: số `0` trong lịch có thể là "không có giá"; lịch chỉ phủ 30 ngày; tìm kiếm và đặt phòng không còn cùng luật.
