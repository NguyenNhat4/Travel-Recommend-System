# Thêm spec tra cứu AgentState theo field

- Ngày: 2026-09-23
- Tác giả: nhatutc2@gmail.com / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng cần một file markdown riêng trong `docs/spec/agent/` liệt kê từng trường của `AgentState`, node nào ghi/đọc và dùng để làm gì — bổ sung góc nhìn theo field bên cạnh bảng theo node đã có ở `langgraph-nodes.md` mục 6.1.

## File thay đổi

- `docs/spec/agent/state-fields.md` — thêm: bảng field-level đầy đủ 36 trường của `AgentState` (state.py), đối chiếu `nodes.py`/`routing.py` để xác định node ghi/đọc từng field và mục đích.
- `docs/spec/agent/README.md` — sửa: thêm dòng trỏ tới `state-fields.md` trong bảng chỉ mục.

## Quyết định

- Trích dẫn FR-AGT-01/02/03/04 (`docs/prd/requirements.md` §1.4) ở đầu file theo yêu cầu mục 7 AGENTS.md (spec mới phải ghi mã FR/NFR phục vụ) — tài liệu chỉ mô tả lại hành vi code hiện có, không thêm field/route mới nên không phải đề xuất lệch PRD.
- Giữ nguyên bảng theo node ở `langgraph-nodes.md` (không xóa), file mới là góc nhìn bổ sung theo field, tránh trùng lặp mục đích với tài liệu cũ.
- Đặt tên file `state-fields.md` (chữ thường, gạch nối, không dấu) đúng quy ước mục 7.

## Kiểm tra

- Không có thay đổi contract/schema/seed nên không cần chạy `validate_contract.py` hay `db/verify.sql`.
- Đối chiếu thủ công từng dòng bảng với `nodes.py`/`routing.py` hiện tại (đọc trực tiếp, không suy đoán).

## Còn lại / rủi ro

- Bảng là bản chụp tại thời điểm viết; khi `state.py`/`nodes.py`/`routing.py` đổi field hoặc logic đọc/ghi phải cập nhật lại bảng trong cùng thay đổi.
