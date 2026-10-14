# Orc v2: 4 lượt gọi tool, bỏ trần số tool mỗi lượt

- Ngày: 2026-10-14
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-14 (trong chat: "ko có giới hạn số lượng tool model có thể gọi 1 lần",
  "nâng lên số lần gọi là 4 (số lần không phải số lượng tool)")
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (Ngân sách thực thi; function calling), `docs/prd/requirements.md` AC-AGT-06
- Mã FR/NFR: FR-AGT-02, FR-AGT-03, AC-AGT-02, AC-AGT-06

## Lý do

Hội thoại thử 14/10 (Đà Nẵng, "lịch trình tiết kiệm thôi" rồi "thêm vé máy bay đi từ hcm"): trợ lý báo lịch còn lỗi rồi
xin khách bấm nút sửa thay vì tự sửa, có lượt nói thẳng đã hết khả năng kiểm tra thêm. Log local từ 13/10: 19 lượt có
lập lịch, 10 lượt lịch đầu bị lỗi; 6 lượt hết 3 lượt tool mà lịch vẫn lỗi, 4 trong số đó chưa được sửa lần nào vì 3 lượt
đã dùng cho việc tra. Lập lịch có vé cần tra điểm + chiều đi, tra chiều về, dựng lịch, nên với 3 lượt thì lịch đầu lỗi là
hết đường sửa. Trần 3 tool mỗi lượt không có tác dụng thực tế (log không có lần nào `TOO_MANY_CALLS`); trần 10 request
nguồn mới là giới hạn thật.

## Nội dung đề xuất

`architecture.md` §3, Ngân sách thực thi:

- Hiện tại: "baseline 3 batch execute, tối đa 3 calls/batch, 10 request nguồn vật lý, 5 model calls (4 quyết định + 1
  repair)."
- Thay bằng: "baseline 4 batch execute, không giới hạn số call trong một batch, 10 request nguồn vật lý, 6 model calls
  (5 quyết định + 1 repair)."

`architecture.md` §3, function calling:

- Hiện tại: "Hết lượt chỉ bind respond; quá ba call nghiệp vụ thì call thừa trả TOO_MANY_CALLS, không thực thi."
- Thay bằng: "Hết lượt chỉ bind respond. Một batch chạy mọi call nghiệp vụ orc gửi; call vượt trần request nguồn trả
  TOOL_LIMIT, không thực thi."

`requirements.md` AC-AGT-06:

- Hiện tại: "Baseline thực thi theo architecture §3 (3 batch, 10 request nguồn, tối đa 5 model calls trong deadline)."
- Thay bằng: "Baseline thực thi theo architecture §3 (4 batch, 10 request nguồn, tối đa 6 model calls trong deadline)."

Số model call lên 6 là hệ quả bắt buộc: 4 lượt quyết định tool + 1 lần trả lời + 1 lần sửa câu trả lời. Deadline lượt
và timeout model giữ nguyên.

## Thay đổi source sau khi chốt

- `src/backend/app/agents/orc_v2.py`: `MAX_BATCHES = 4`, `MAX_MODEL_CALLS = 6`, bỏ nhánh `TOO_MANY_CALLS`, sửa docstring
  và `PROMPT` (bỏ "tối đa BA tool", lượt sửa lịch).
- `src/backend/tests/unit/agents/test_orc_loop.py`: test trần lượt, trần model, nhiều call một lượt.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §v2, `docs/spec/agent/working-context.md` §3.1.

## Ảnh hưởng

- Lượt lập lịch có lỗi chậm thêm khoảng một lần gọi model (10–15 giây); lượt suôn sẻ không đổi.
- Model gửi nhiều call một lúc vẫn bị chặn bởi trần 10 request nguồn.
- Không đổi contract HTTP/SSE.
