# Gợi ý phương án tiết kiệm hơn khi đã có lịch

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Bấm "Tìm phương án tiết kiệm hơn" sau khi có lịch (Vũng Tàu, ngân sách 5 triệu) chỉ ra thẻ phòng rẻ hơn kèm "chưa thể
thay lịch". Người dùng muốn trợ lý gợi ý được lịch rẻ hơn. FR-AGT-03/06, AC-AGT-04, NFR-REL-01.

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa: `PROMPT` mục Lập lịch thêm luồng dựng lại lịch rẻ hơn.
- `src/backend/tests/unit/agents/test_orc_loop.py` — sửa: hồi quy ref cũ STALE_REF khi chưa tra lại; tra lại + tìm
  free_only rồi plan_itinerary thay lịch.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: mô tả luồng phương án tiết kiệm.
- `history/2026-10-14-goi-y-phuong-an-tiet-kiem-hon.md` — thêm: entry này.

## Quyết định

- Nguyên nhân chính đã sửa ở `history/2026-10-14-sua-freeonly-gateway-va-cau-ngoai-pham-vi.md` (gateway chặn
  `freeOnly`). Entry này bổ sung phần prompt: trước đây không có hướng dẫn dựng lại lịch ở lượt sau, model chỉ tìm thẻ
  rồi dừng khi một tra cứu lỗi.
- Đúng PRD: FR-AGT-06 "muốn rẻ hơn thì so với thẻ đang nói, giữ điều kiện chưa đổi"; architecture §3 đổi dòng đắt
  theo costs.share/savings. Chỉ sửa prompt, không thêm luật cứng hay tự thay sản phẩm trong code.
- Luồng: lượt một get_products ref lịch định giữ + find_products cho dòng tốn nhất; lượt hai plan_itinerary;
  respond itinerary/replace, chi phí mới qua fact, không tự trừ số tiết kiệm. Vừa trần ba call/lượt.

## Kiểm tra

- `pytest test_orc_guardrails.py test_orc_loop.py test_orc_contracts.py test_orc_tool_dispatch.py
  test_itinerary_tools.py test_assistant_v2_final.py test_assistant_v2_use_case.py test_assistant_v2_contract.py
  tests/architecture`: 133 passed, 1 warning có sẵn (model giả; chỉ chứng minh code chạy đúng luồng, không chứng
  minh model thật làm theo).
- Chưa thử model thật; cần khởi động lại backend.

## Còn lại / rủi ro

- Thử lại hội thoại Vũng Tàu trên giao diện; nếu model vẫn không dựng lại lịch thì xem log `plan_checked`.
- Lỗi tool tầng dưới vẫn trả cho model chỉ mã, không lý do.
