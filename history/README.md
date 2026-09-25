# Lịch sử thay đổi

Nơi ghi lại mọi thay đổi trong `src/` và `docs/`, để người và agent sau biết đã đổi gì, vì sao và còn gì dang dở. Git cho biết dòng nào đổi; file ở đây ghi **lý do, quyết định và việc còn lại**.

## Quy tắc

- Mỗi thay đổi (một task/feature/fix) là **một file riêng**, không sửa chung một file lớn, để tránh conflict khi nhiều người làm song song.
- Tên file: `YYYY-MM-DD-<slug-ngan>.md`, ví dụ `2026-09-16-cdp-event-dispatcher.md`. Trùng ngày và slug thì thêm hậu tố `-2`.
- Ghi trong **cùng commit/PR** với thay đổi code hoặc tài liệu.
- Không sửa entry cũ để viết lại lịch sử. Nếu quyết định cũ bị thay thế, tạo entry mới và ghi `Thay thế: <tên file cũ>`; chỉ được sửa entry cũ để thêm dòng `Bị thay thế bởi: <tên file mới>`.
- Không ghi secret, token, dữ liệu cá nhân.
- Thay đổi chỉ nằm trong `history/` không cần entry.

## Cách đọc nhanh

```bash
ls history/ | grep -v README | sort | tail -10          # 10 entry mới nhất
grep -l "src/backend/app/application/booking" history/*.md  # entry từng chạm vào một đường dẫn
grep -l "Trạng thái: dang dở" history/*.md               # việc còn dang dở
```

## Mẫu

Chép khối dưới vào file mới và điền đủ các mục. Mục không có nội dung thì ghi `Không có`.

```markdown
# <Tiêu đề ngắn>

- Ngày: YYYY-MM-DD
- Tác giả: <người yêu cầu> / <agent hoặc người thực hiện>
- Nhánh: <tên nhánh>
- Trạng thái: hoàn thành | dang dở
- Phạm vi: <workstream: backend | frontend | agent | contract | cdp | data | evaluation | insider | docs>

## Mục tiêu

<Yêu cầu gốc là gì, vì sao cần.>

## File thay đổi

- `đường/dẫn/file` — thêm | sửa | xóa | đổi tên: <tóm tắt một dòng>

## Quyết định

- <Lựa chọn đã đưa ra và lý do; tài liệu/quy tắc căn cứ.>

## Kiểm tra

- <Lệnh đã chạy và kết quả, ví dụ validate_contract.py: pass. Chưa chạy thì ghi rõ.>

## Còn lại / rủi ro

- <Việc chưa làm, câu hỏi chờ xác nhận, điểm cần người sau chú ý.>
```
