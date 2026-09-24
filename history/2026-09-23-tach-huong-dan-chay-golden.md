# Tách hướng dẫn chạy bộ golden dataset thành một file riêng

- Ngày: 2026-09-23
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, evaluation

## Mục tiêu

Người dùng hỏi tài liệu hướng dẫn chạy bộ golden ở đâu. Hướng dẫn đang rải ở ba chỗ
(`docs/spec/agent/README.md`, `golden-dataset.md` mục 7, file bàn giao mục 3), không chỗ nào đủ các bước
chuẩn bị môi trường và cách đọc kết quả. Người dùng yêu cầu tách thành một file riêng.

## File thay đổi

- `docs/spec/agent/golden-run.md` — thêm: test nhanh, chuẩn bị Postgres và backend (biến `.env`, đợi recsys),
  bảng cờ của runner, cách đọc kết quả và biên bản, lỗi thường gặp.
- `docs/spec/agent/README.md` — sửa: mục lục và mục "Chạy đánh giá tự động" trỏ tới `golden-run.md`.
- `docs/spec/agent/golden-dataset.md` — sửa: dòng mở đầu trỏ tới `golden-run.md`.
- `docs/plan/2026-09-23-golden-dataset-handoff.md` — sửa: mục 3 trỏ tới `golden-run.md`.
- `history/2026-09-23-tach-huong-dan-chay-golden.md` — thêm: entry này.

## Quyết định

- Đặt ở `docs/spec/agent/` cạnh `golden-dataset.md` theo AGENTS.md §7. Tách "chạy" khỏi "thêm case" vì hai
  việc có người đọc khác nhau: người chạy trước demo không cần biết khoá `expect`.
- Giữ nguyên đoạn lệnh ngắn trong README để người lướt qua vẫn chạy được; bản đầy đủ nằm ở file mới.
- Bảng cờ và giá trị mặc định lấy từ `argparse` trong `src/evaluation/agent/golden.py`.

## Kiểm tra

- Các link `.md` nội bộ trong `golden-run.md` trỏ tới file có thật.
- Không chạy test: chỉ đổi tài liệu.

## Còn lại / rủi ro

Không có.
