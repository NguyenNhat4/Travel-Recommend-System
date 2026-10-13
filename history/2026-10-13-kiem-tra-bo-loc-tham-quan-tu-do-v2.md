# Kiểm tra bộ lọc tham quan tự do v2 và lời chat lộ catalog

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: agent, backend, docs

## Mục tiêu

Người dùng báo không tìm được điểm miễn phí, lời chat/Think nói về catalog và phân trang; làm rõ điểm miễn phí
là điểm tham quan tự do. FR-AGT-02/04/06, NFR-REL-01, AC-AGT-04/06/07.

## File thay đổi

- `docs/prd/update/2026-10-13-tham-quan-tu-do-trong-bo-loc-v2.md` — thêm: đề xuất đồng nhất ý nghĩa tham quan tự do cho v2.
- `history/2026-10-13-kiem-tra-bo-loc-tham-quan-tu-do-v2.md` — thêm: entry này.
- `src/backend/app/agents/orc_v2.py` — sửa: lời chat/Think không nói nội bộ và hướng dẫn tra tiếp khi chưa có kết quả.
- `src/backend/app/domain/itinerary/orc_guardrails.py` — sửa: final guard chặn chi tiết nội bộ trong chat/nút/disclosure/Think.
- `src/backend/tests/unit/domain/test_orc_guardrails.py` — sửa: hồi quy lời chat/nút/Think và câu giới hạn xác minh hợp lệ.
- `src/backend/tests/unit/agents/test_orc_loop.py` — sửa: kiểm repair và tiến trình không lộ catalog/phân trang.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: lời hiển thị và xử lý kết quả rỗng còn cursor.

## Quyết định

- Đọc PRD v2 hiện hành và đối chiếu lịch sử v1: quy ước giá null của hai phiên bản khác nhau.
- Truy vấn chỉ đọc `GET /api/v1/products` trên backend local, không gọi LLM; giữ yêu cầu không đo model của người dùng.
- 50 attraction TP.HCM còn mở: 41 có giá đứng trước, 9 không giá/ticketed không có đứng sau; filter sau trang nhỏ
  không thấy điểm phù hợp. Không nhận toàn bộ 9 điểm là miễn phí đã xác minh.
- Chờ chốt phần lệch PRD về attraction/golf không giá. Phần sửa lời hiển thị và lọc trước phân trang được chuẩn bị.
- Đã sửa lời hiển thị bằng prompt + guard, không thay lựa chọn sản phẩm hay tự thêm lời gọi tool.
- C2 của contract lược bỏ attributes=false, gồm ticketed=false: đề xuất metadata entryPolicy giữ căn cứ vào cửa
  mà không đổi quy tắc C2. Không sửa C2 hay dữ liệu nguồn trước khi chốt.
- Giữ toàn bộ thay đổi chưa commit của task trước và file evaluation/history có sẵn.

## Kiểm tra

- Truy vấn local `/api/v1/products?destination=TP.%20Hồ%20Chí%20Minh&taxonomy=attraction&availableOnly=true&sort=popular&limit=50`: 200, total=50.
- Kiểm thử local `test_orc_guardrails.py` + `test_orc_loop.py`: 31 passed; dùng model giả, không gọi provider.
- Ruff check bốn file Python đã sửa trong task này: PASS; `git diff --check`: PASS.

## Còn lại / rủi ro

- Áp dụng đề xuất khi người dùng chốt; sửa filter và lời hiển thị, bổ sung hồi quy và hoàn tất entry này.
- Dữ liệu không giá vẫn có thể là điểm thu phí chưa cập nhật; giữ cảnh báo giả định và không sửa unitPrice của nguồn.
