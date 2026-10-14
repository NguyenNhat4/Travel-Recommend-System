# Orc v2: bỏ trần số request nguồn mỗi lượt

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs
- Mã FR/NFR: FR-AGT-02, AC-AGT-02, AC-AGT-06
- Đề xuất: `docs/prd/update-archive/2026-10-14-bo-tran-request-nguon.md`
- Tiếp theo: `history/2026-10-14-orc-4-luot-tool-khong-tran-call-moi-luot.md`

## Mục tiêu

Sau khi nâng lên 4 lượt tool, đo chuỗi Đà Nẵng của chat 14/10 thì lượt "thêm vé máy bay đi từ hcm" 0/3 có vé. Người dùng
chốt bỏ trần số request nguồn (ban đầu đồng ý 25, đổi thành không giới hạn trước khi commit).

## File thay đổi

- `docs/prd/update-archive/2026-10-14-bo-tran-request-nguon.md` — thêm: đề xuất, ghi chốt trong chat, đã áp dụng.
- `docs/prd/architecture.md` — sửa §3: không trần request nguồn, chặn bằng deadline; request sau deadline trả TIME_LIMIT.
- `docs/prd/requirements.md` — sửa AC-AGT-06: không trần request nguồn.
- `src/backend/app/application/itinerary/orc_dispatch.py` — sửa: `SourceBudget(limit=None)` mặc định không trần, vẫn
  kiểm deadline; truyền `limit` vẫn chặn được (test dispatcher dùng).
- `src/backend/app/agents/orc_v2.py` — sửa: docstring, `PROMPT` (không còn số request, chỉ refresh ref thật sự dùng);
  `remaining` bỏ `source_requests`, `flight_max_source_requests`.
- `src/backend/tests/unit/agents/test_orc_loop.py` — sửa: `remaining` không còn `source_requests`.
- `src/evaluation/agent/assistant_v2_cases.py` — thêm ca `save-then-flight` (đúng chuỗi chat, 16/10) và
  `save-then-flight-17` (3 ngày từ 17/10, ngày catalog local có chuyến hai chiều).
- `docs/spec/agent/working-context.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa giới hạn mỗi lượt.
- `history/2026-10-14-bo-tran-request-nguon.md` — thêm: entry này.

## Quyết định

- Bằng chứng trước khi sửa (backend tạm :8001 cùng env :8000, model thật, catalog local, code 4 lượt + trần 10),
  `save-then-flight` ×3: lượt thêm vé cả ba lần dùng 10/10 request; `get_products` tra lại 8–9 điểm của lịch (mỗi ref
  một request, `orc_dispatch.py` `_get_products`) nên `lookup_flights` còn 0–2 request, trả `TOOL_LIMIT`/`partial`
  0 chuyến. Mức 10 chép từ orchestrator cũ làm baseline đo (plan 2026-10-13), không tính cho tra lại lịch kèm vé.
- Bỏ trần đếm, giữ deadline lượt, 4 lượt tool, 6 lần model; đây là giới hạn còn lại.
- Catalog local không có chuyến TP. Hồ Chí Minh → Đà Nẵng ngày 16/10 (có 14, 17–20/10), nên ca 16/10 trả đúng "chưa tìm
  thấy chuyến"; chuyến 12:30 trong chat gốc đến từ dữ liệu môi trường khác. Thêm ca 17/10 để đo đường có vé.

## Kiểm tra

- Test mới trên code trần 25: 1 failed (`source_requests` còn trong `remaining`).
- `pytest -q src/backend/tests/unit/agents src/backend/tests/unit/application src/backend/tests/unit/domain
  src/backend/tests/contract/test_assistant_v2_contract.py src/backend/tests/architecture`: 2661 passed, 3 xfailed.
- `git diff --check`: pass.
- Model thật, backend tạm :8001 (đã dừng) khởi động lại sau khi sửa, cùng env :8000, catalog local,
  `assistant_v2_cases --repeat 3 save-then-flight-17 save-then-flight`:
  - `save-then-flight-17` (3 ngày từ 17/10): lượt thêm vé 3/3 có vé khứ hồi, `lookup_flights` ok hai chiều, mỗi lượt
    13 request nguồn (quá mức 10 cũ), 3–4 lượt tool; trợ lý tự dời Sơn Trà sang buổi/ngày khác cho khớp giờ bay, không
    hỏi khách. Lượt tiết kiệm 3/3 dựng lại lịch rẻ hơn (`itinerary/replace`), 10–12 request, có lần dùng lượt tool thứ 4.
  - `save-then-flight` (4 ngày từ 16/10): lượt thêm vé 3/3 `lookup_flights status=empty` (catalog local không có chuyến
    ngày này, không còn bị cắt), giữ lịch và nói chưa tìm thấy chuyến; lượt tiết kiệm 3/3 dựng lại lịch rẻ hơn.
  - Thời gian lượt 26–50 giây; lượt thêm vé 30–47 giây.
  - Lần đo trước đó (cùng ca 17/10) vô tình chạy trên backend còn trần 25 vì backend mới không chiếm được cổng; không
    dùng số đó.

## Còn lại / rủi ro

- Lượt có vé chậm hơn vì đọc đủ trang chuyến bay; chỉ deadline chặn.
- Chưa sửa: prompt "Hết lượt vẫn lỗi: … một nút cách sửa", "giữ refs đã chốt" bị hiểu rộng, vòng
  `DUPLICATE_PLACE` ↔ `TOO_FEW_ACTIVITIES` (xem entry 4 lượt).
- Backend :8000 cần khởi động lại để nhận thay đổi.
