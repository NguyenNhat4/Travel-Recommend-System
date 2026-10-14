# Đề xuất: lịch 2–3 hoạt động/ngày, số đêm = số ngày − 1 (bổ sung đề xuất bộ tool)

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: docs, evaluation

## Mục tiêu

Người dùng lập lịch Đà Nẵng nhưng nhận danh sách thẻ thay vì lịch theo buổi; đề xuất mỗi ngày 2–3 hoạt động, 3 ngày
2 đêm, tính phòng theo số người. Trace LangSmith của lượt 21:29 không có (backend đã tắt, không có run sau 21:03), nên
tái hiện bằng LLM thật.

## File thay đổi

- `docs/prd/update/2026-10-13-thiet-ke-lai-bo-tool-orc.md` — sửa: thêm phần F (2–3 hoạt động/ngày, thay câu "không
  áp trần") và G (số đêm = số ngày − 1, cách tính phòng/ngân sách), kèm bằng chứng.
- `src/evaluation/agent/assistant_v2_cases.py` — thêm ca `plan-danang`.

## Quyết định

- Giao diện đã chia lịch theo ngày/buổi khi response có `itinerary`; lỗi là orc không ra được lịch (hết lượt tool khi
  build còn vi phạm) nên v2 trả thẻ với `planEffect=keep`. Sửa gốc nằm ở C, E của đề xuất; F, G lệch PRD nên chờ chốt.

## Kiểm tra

- LLM thật, backend local cổng 8001, `plan-danang` ×3: #1 hết lượt sau `OUTSIDE_OPENING_HOURS` → partial/keep, không lịch;
  #2 hỏi thêm trẻ em sau khi đã biết đi một mình, không lịch; #3 ra lịch 3 ngày, hoạt động [1, 2, 1], 3 đêm (25→28),
  rooms null, tổng chưa xác định (thiếu giá 3 sản phẩm).

## Còn lại / rủi ro

- Chờ chốt A–G. Hỏi lại trẻ em khi khách đã nói "một mình" là lỗi hiểu câu riêng, chưa sửa.
