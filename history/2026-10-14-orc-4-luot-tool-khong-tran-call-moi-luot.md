# Orc v2: 4 lượt gọi tool, bỏ trần số tool mỗi lượt, 6 lần gọi model

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Mã FR/NFR: FR-AGT-02, FR-AGT-03, AC-AGT-02, AC-AGT-06
- Đề xuất: `docs/prd/update-archive/2026-10-14-orc-4-luot-tool-khong-tran-call-moi-luot.md`

## Mục tiêu

Hội thoại thử 14/10 (Đà Nẵng: "lịch trình tiết kiệm thôi" → "thêm vé máy bay đi từ hcm" → các nút sửa): trợ lý không
tự sửa lịch mà xin khách bấm nút, có lượt báo đã hết khả năng kiểm tra thêm. Người dùng muốn agent tự chủ động.
Sau khi xem số liệu, người dùng chốt: không giới hạn số tool trong một lần gọi, nâng số lần gọi tool lên 4.

## File thay đổi

- `docs/prd/update-archive/2026-10-14-orc-4-luot-tool-khong-tran-call-moi-luot.md` — thêm: đề xuất, ghi chốt trong chat,
  trạng thái đã áp dụng (file mới chưa track nên chuyển bằng `mv`).
- `docs/prd/architecture.md` — sửa §3: 4 batch, không trần call/batch, 6 model calls; call vượt nguồn trả TOOL_LIMIT.
- `docs/prd/requirements.md` — sửa AC-AGT-06: baseline 4 batch, 6 model calls.
- `src/backend/app/agents/orc_v2.py` — sửa: `MAX_BATCHES=4`, `MAX_MODEL_CALLS=6`, bỏ nhánh `TOO_MANY_CALLS`; docstring
  và `PROMPT` (gọi nhiều tool song song, gộp tra cứu độc lập để dành lượt sửa lịch, lượt ba/bốn để sửa violations).
- `src/backend/tests/unit/agents/test_orc_loop.py` — sửa: 4 lượt rồi chỉ còn respond, 6 lần model, 5 call một lượt đều
  chạy, `remaining.tool_rounds` bắt đầu từ 4.
- `docs/spec/agent/working-context.md` — sửa §3.1 giới hạn mỗi lượt.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa §v2 giới hạn mỗi lượt.
- `history/2026-10-14-orc-4-luot-tool-khong-tran-call-moi-luot.md` — thêm: entry này.

## Quyết định

- Bằng chứng (`.logs/web-demo.log` từ 13/10, không tìm thấy đúng hội thoại trong ảnh — có thể chạy ở môi trường khác):
  19 lượt có `plan_itinerary`; lịch đầu lỗi 10/19; 6/19 hết 3 lượt mà lịch vẫn lỗi, 4 trong đó chưa được sửa lần nào;
  sửa một lần thành công 5/8. Không lần nào `TOO_MANY_CALLS`, nên trần 3 tool/lượt không chặn gì thực tế.
- Model call lên 6 là hệ quả bắt buộc của 4 lượt (4 quyết định tool + 1 trả lời + 1 sửa câu trả lời); deadline lượt và
  timeout model giữ nguyên. Trần 10 request nguồn giữ nguyên và là giới hạn thật cho số tool một lần.
- Model biết giới hạn qua prompt và `remaining` trong ToolMessage (lấy từ hằng số nên tự cập nhật).

## Kiểm tra

- `test_orc_loop.py` trên code cũ với test mới: 4 failed, 26 passed.
- `pytest -q src/backend/tests/unit/agents src/backend/tests/unit/application src/backend/tests/unit/domain
  src/backend/tests/contract/test_assistant_v2_contract.py src/backend/tests/architecture`: 2661 passed, 3 xfailed
  (model giả; không chứng minh model thật sửa lịch tốt hơn).
- `git diff --check`: pass. Không đổi contract nên không chạy `validate_contract.py`.
- Chưa chạy model thật; backend :8000 cần khởi động lại để nhận thay đổi.

## Còn lại / rủi ro

- Chưa sửa các nguyên nhân hành vi đã phân tích: prompt "Hết lượt vẫn lỗi: … một nút cách sửa" khiến orc xin phép
  khách; "giữ refs đã chốt" bị hiểu là mọi điểm trong lịch; vòng `DUPLICATE_PLACE` ↔ `TOO_FEW_ACTIVITIES`
  (`TOO_FEW_ACTIVITIES` trả `refs: []`, còn tính điểm trả phí khi khách muốn tiết kiệm). Thêm lượt không gỡ các lỗi này.
- Lượt lập lịch có lỗi chậm thêm một lần gọi model (khoảng 10–15 giây).
- Cần đo lại chuỗi Đà Nẵng trên model thật.
