# Chốt đề xuất cổng bằng chứng `/search`, cập nhật PRD, lưu trữ đề xuất 2026-10-06

- Ngày: 2026-10-13
- Tác giả: tqanh123 / Claude Code
- Nhánh: docs/search-evidence-gate-plan
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md`. Theo AGENTS §8 bước 3: cập nhật PRD đúng nội dung đã chốt trước khi sửa source.

## File thay đổi

- `docs/prd/requirements.md` — sửa: FR-SRC-04 (nhãn "Kết quả gần nhất", trả rỗng khi residual toàn bộ là tên lạ hoặc cả câu vô nghĩa, bỏ cụm lạ không phải tên, khớp từ khoá theo cụm giữ dấu); FR-SRC-03 thêm ý lọc thời lượng vé/combo, không loại khách sạn.
- `docs/prd/deployment-plan.md` — sửa: dòng `SEARCH_CUTOFF` bỏ "giới hạn đã biết"; thêm dòng `SEARCH_NO_DIACRITICS_MODE` (giá trị `restore`) và dòng 5 cờ mới mặc định `false`.
- `docs/prd/update/2026-10-13-search-evidence-gate-no-answer.md` — sửa: trạng thái `đã chốt`, chốt bởi tqanh123 2026-10-13; đường dẫn đề xuất bị thay thế trỏ sang `update-archive/`.
- `docs/prd/update-archive/2026-10-06-search-hybrid-min-coverage-rrf.md` — đổi tên (từ `docs/prd/update/`) + sửa trạng thái `từ chối (thay bằng 2026-10-13-search-evidence-gate-no-answer.md)`.
- `docs/plan/2026-10-13-search-evidence-gate-no-answer.md` — sửa: trạng thái Bước 1 đã chốt.

## Quyết định

- Đề xuất mới **giữ ở `docs/prd/update/`** với trạng thái `đã chốt`: source chưa sửa, máy làm tiếp cần đọc nó (AGENTS §1.1 mục 2). Chuyển sang `update-archive/` + trạng thái `đã áp dụng` khi plan làm xong.
- Mục 5 của đề xuất (architecture §5, trường BM25 mới) chỉ áp vào PRD khi làm P1; chưa sửa `architecture.md`.
- Các tài liệu cũ nhắc đường dẫn `update/2026-10-06-…` (plan 07/10, report 06/10) là bản ghi lịch sử, không sửa.

## Kiểm tra

- Chỉ đổi tài liệu; không chạy test.

## Còn lại / rủi ro

- Máy khác làm plan từ Bước 0. Bước 0.3 vượt ngưỡng chặn nhầm 2 % thì phải mở đề xuất sửa trước khi code Bước 5.
- Khi làm P1: cập nhật `docs/prd/architecture.md` §5 theo mục 5 của đề xuất.
