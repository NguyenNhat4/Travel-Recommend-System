# Chi tiết checklist và bàn giao Day 4 cho hai người

- Ngày: 2026-10-01
- Tác giả: Người dùng / Codex
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Cập nhật trực tiếp file chia việc Day 4 thành checklist cụ thể, xác định file bàn giao và cung cấp lệnh commit/push. Phục vụ FR-SRC-01..04, FR-REC-01..04, NFR-PERF-01; liên quan AC-SRC-01, AC-REC-01 và test-plan §2.5.

## File thay đổi

- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa bản untracked đã có: chuyển 16 task thành checklist thực hiện/nghiệm thu/bàn giao; bổ sung checklist model/scorer, điều kiện phối hợp và bảng bàn giao tại §5.
- `history/2026-10-01-checklist-ban-giao-day4.md` — thêm: entry cho lần cập nhật này.

## Quyết định

- Dùng chính file chia việc làm file bàn giao; report và history được liên kết làm bằng chứng.
- Giữ S/R chưa điền tên, không tự giảm phạm vi Day 4 khi chưa có xác nhận; phần chưa xong ghi blocker/bước tiếp theo.
- Giữ quyết định mốc v5 theo entry `2026-10-01-chia-task-day4-search-rec.md`; entry cũ không sửa.
- Làm rõ: không chia 100/100 từ 131 câu; tài liệu gold đặt ở docs/spec/bench thay vì tạo README mới trong src; tái lập metric không yêu cầu latency giống từng chữ số; đủ đặc tả mới triển khai scorer thiếu nguồn; danh sách collection thay cho ngưỡng đếm mâu thuẫn.
- Nhãn máy D4a đã được duyệt toàn bộ theo lịch sử, vì vậy không gọi duyệt mẫu là quy trình D4a.
- Chỉ chỉnh kế hoạch, không chạy task benchmark, không đổi code/contract/DDL/PRD hay model production. Không có thay đổi lệch PRD trong lần này.

## Kiểm tra

- `git status --short`: trước sửa có file phân công và history phân công cũ ở trạng thái untracked; bảo toàn history cũ.
- Kiểm tra cấu trúc bằng Python: đủ 16 mục S1–S8/R1–R8, mỗi mục có thực hiện/nghiệm thu/bàn giao; có §5 bàn giao; không còn split 100/100 như một chỉ dẫn thực thi hoặc đường dẫn gold/README.md.
- Kiểm tra whitespace bằng `git diff --no-index --check /dev/null <file>` cho hai file của lần cập nhật này.
- Không chạy test code, contract hoặc benchmark vì chỉ cập nhật Markdown. Chưa commit/push; người dùng yêu cầu cung cấp lệnh tự push.

## Còn lại / rủi ro

- Cần điền tên S/R, xác nhận precision bge-m3, bổ sung nguồn đặc tả scorer và owner lỗi cloud; đã có checklist riêng tại §5.5.
- Trạng thái task cần người thực hiện điền bằng artifact thật; lần sửa tài liệu này không xác nhận task benchmark hoàn thành.
- Khi commit file phân công mới, kèm cả history phân công cũ đang untracked và entry này để giữ đầy đủ nguồn gốc.
