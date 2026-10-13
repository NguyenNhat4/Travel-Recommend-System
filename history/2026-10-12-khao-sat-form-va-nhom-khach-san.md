# Khảo sát form, thuộc tính sở thích và nhóm thẻ khách sạn

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Tìm hiểu yêu cầu đã làm rõ về nút mở form, sở thích linh hoạt do LLM gợi ý từ thuộc tính sản phẩm, đề xuất nhóm khách sạn để người dùng duyệt và hướng làm nổi bật combo. Task hiện tại chỉ khảo sát và đề xuất.

## File thay đổi

- `docs/prd/update/2026-10-12-form-theo-followup-va-so-thich-linh-hoat.md` — thêm: đề xuất chờ chốt cho các điểm khác PRD hiện hành.
- `history/2026-10-12-khao-sat-form-va-nhom-khach-san.md` — thêm: entry khảo sát này.

## Quyết định

- Chưa sửa code, contract, PRD hay DDL. PRD đang yêu cầu tự hiện form và giới hạn năm sở thích, khác yêu cầu mới; chờ chốt theo AGENTS.md §8.
- Đề xuất ba nhóm chính: tiết kiệm, ít di chuyển, cân bằng; hạng sao cao nhất chỉ là lựa chọn có điều kiện, chờ duyệt.
- Đối chiếu code form, bộ sở thích, từ vựng tiện ích Search, thuật toán phương án lưu trú, contract, PRD và lịch sử cập nhật PRD ngày 12/10.
- File runtime local có 340 sản phẩm, 40 hotel_property và không có mảng amenities. Snapshot 2026-09-30 có 11.718 sản phẩm, 2.321 hotel_property, thuộc tính tiện ích phong phú hơn. Đây là bằng chứng từ file local/snapshot, không phải kiểm tra database đang phục vụ hoặc production.
- Phân biệt hạng sao với điểm đánh giá; khoảng cách thuật toán hiện là đường chim bay.

## Kiểm tra

- `git status --short` trước khảo sát: sạch; trước ghi history: chỉ có đề xuất mới.
- Script Python đọc JSONL local và snapshot gzip, đếm theo taxonomy/level và tiện ích bằng `amenity_keys`: exit 0; chỉ đọc dữ liệu.
- Không chạy test ứng dụng/contract vì chưa sửa source hay contract.

## Còn lại / rủi ro

- Người dùng duyệt nhóm khách sạn và phạm vi sở thích chỉ nơi ở hay cả hoạt động. Triển khai là phần việc tiếp theo.
- Khi triển khai, tổng hợp từ catalog đang phục vụ; không dùng số liệu snapshot làm số lượng hiển thị hiện tại.
- Cần đọc đủ tài liệu/lịch sử theo phạm vi trước khi sửa code và cập nhật PRD theo đề xuất được chốt.
