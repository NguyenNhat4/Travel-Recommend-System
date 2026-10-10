# Search/similar/recommendations trả rating và reviewCount

- Ngày: 2026-10-01
- Tác giả: người dùng / Claude
- Nhánh: feat/booking
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Card sản phẩm ở search hiện chip hạng sao thay vì dòng điểm đánh giá như landing, dù dữ liệu có `reviewScore`. Nguyên nhân: `hit()` ở search không đưa `rating`/`reviewCount` vào response, trong khi contract `ScoredProduct` = `ProductSummary` + `score`.

## File thay đổi

- `src/backend/app/application/search/use_cases.py` — sửa: `hit()` thêm `rating` và `reviewCount` (dùng chung cho /search, /similar, /recommendations)
- `src/backend/tests/unit/application/test_search_hit_rating.py` — thêm: test có điểm (8.2/10 → 4.1, 128 đánh giá) và test không có điểm (null)

## Quyết định

- Sửa tại `hit()` để một chỗ phủ cả ba endpoint. Không đổi contract: `ProductSummary` đã có hai trường này; đây là đưa backend về đúng contract, không lệch PRD.

## Kiểm tra

- `pytest src/backend/tests`: 545 passed, 21 skipped; test mới 2 passed sau khi làm test tự chứa (bản đầu giả định fixture có reviewScore nên fail, đã sửa).
- `validate_contract.py`: PASS (contract không đổi).
- Chưa xem trên trình duyệt; backend đang chạy cần khởi động lại để nhận thay đổi.

## Còn lại / rủi ro

- Dòng "★ N sao" thêm ở variant `tile` (`history/2026-10-01-thong-nhat-the-tile-theo-dong-danh-gia.md`) vẫn còn cho sản phẩm không có điểm; bỏ nếu không cần.
- Mock `src/shared/mocks` chưa kiểm tra xem kết quả search có `rating` hay không.
