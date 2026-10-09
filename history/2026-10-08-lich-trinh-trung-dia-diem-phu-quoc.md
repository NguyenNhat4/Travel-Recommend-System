# Lịch trình trùng địa điểm (Hòn Thơm, Water Taxi): đề xuất dùng LLM lọc trùng trước khi xếp lịch

- Ngày: 2026-10-08
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: agent, docs

## Mục tiêu

Người dùng báo lịch trình của câu "Lên lịch trình 3 ngày tại Phú Quốc, bắt đầu từ ngày 2026-10-08, cho 2 người lớn, đi từ
trung quoc." bị trùng sản phẩm (ví dụ Cáp treo Hòn Thơm). Tra trace LangSmith tìm nguyên nhân; người dùng chọn cách sửa: sau
bước lọc tất định, đưa danh sách mã + tên cho LLM chỉ ra cặp trùng, giữ một trong hai; output eval có mục "Đã loại".

## File thay đổi

- `docs/prd/update/2026-10-08-loc-trung-lap-bang-llm.md` — thêm: đề xuất node `dedupe` (luật cùng tên + LLM trả cặp mã trùng),
  cảnh báo `PRODUCT_DROPPED_DUPLICATE`, mục "Đã loại" trong eval.

## Quyết định

- Trace `01a11adf-0747-72c0-9dd6-b302e00a4c20` (project `nhat-10-7`), output `compose_node`: ngày 1 "hòn Thơm" + "Sun World
  Hòn Thơm", ngày 2 "Cáp Treo Hòn Thơm" (850.000 ₫ như Sun World), ngày 3 hai sản phẩm cùng tên "[Grand World Phú Quốc] - Vé
  đi thuyền Venice (Water Taxi)" (`e35d0af0…`, `f540ef2f…`). `compose_plan` chỉ khử trùng theo `productId`/`parentProductId`.
  Lỗi tất định, không do LLM.
- Đo trên catalog local (912 điểm tham quan còn mở, script tạm ở scratchpad): luật tên lồng nhau bỏ sót cặp Sun World/Cáp
  Treo Hòn Thơm; luật hai từ cuối gộp nhầm VinWonders với Safari; luật cùng toạ độ gộp 17 hoạt động khác nhau của Grand World.
  Người dùng chọn LLM chỉ ra cặp trùng.
- Cho LLM chọn sản phẩm lệch `docs/prd/architecture.md` §3 (LLM chỉ phân tích ý định, viết lời; `compose` tất định) nên tạo
  đề xuất riêng và dừng, chưa sửa code (AGENTS.md §8). Thiết kế giữ grounding: LLM chỉ trả mã có trong danh sách, giữ mã nào
  do luật quyết định.
- Có lúc đã thêm luật theo tên vào `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md`; đã hoàn nguyên, file
  đó không đổi so với commit trước.

## Kiểm tra

- Không chạy test: chưa sửa code.

## Còn lại / rủi ro

- Chờ người dùng chốt `2026-10-08-loc-trung-lap-bang-llm.md`; chốt xong cập nhật PRD rồi mới code theo mục "Thay đổi source".
- Thêm khoảng 1–2 giây mỗi lượt lập lịch; lịch có thể khác giữa các lần chạy nếu LLM nhận cặp khác nhau.
