# Điểm đến catalog nằm sẵn trong system prompt, bỏ tool Destinations của orc

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (Công cụ, lập lịch và hai loại ngân sách), `docs/prd/requirements.md` §1.4 (FR-AGT-02)
- Mã FR/NFR: FR-AGT-02

## Lý do

Orc đoán tên điểm đến theo cách khách viết ("Sài Gòn", "HCM", "Hồ Chí Minh") trong khi catalog lưu "TP. Hồ Chí Minh",
nên lọc theo điểm đến ra rỗng (trace LangSmith 13/10/2026). Khi orc nghĩ tới việc gọi `list_destinations` thì thường đã
hết 3 lượt gọi tool. Số điểm đến trong catalog ít (vài chục), nên đưa sẵn cả danh sách vào system prompt rẻ hơn và chắc
hơn một tool: orc dùng đúng tên ngay lượt đầu, không tốn lượt gọi tool hay request nguồn.

Danh sách vẫn lấy từ catalog (code đọc `GET /destinations` lúc chạy, cache trong process), không viết cứng, vì catalog
đổi theo job cào hằng ngày.

## Nội dung đề xuất

`docs/prd/architecture.md` §3:

- Hiện tại: "Tám tool: Search, Recommendation, Similar, Detail, Destinations, Catalog list, Flights và build_itinerary."
- Thay bằng: "Bảy tool: Search, Recommendation, Similar, Detail, Catalog list, Flights và build_itinerary. Tên điểm đến
  của catalog do code đọc từ catalog (cache ngắn trong process, không tính ngân sách lượt) và đặt sẵn trong system prompt;
  orc dùng đúng tên đó cho mọi tham số điểm đến. Không lấy được danh sách thì lượt vẫn chạy, orc dùng tên khách nói."

`docs/prd/requirements.md` FR-AGT-02:

- Hiện tại: "…Search, Recommendation, Similar, Catalog/Detail/Destinations, tra vé và build_itinerary."
- Thay bằng: "…Search, Recommendation, Similar, Catalog/Detail, tra vé và build_itinerary. Danh sách điểm đến của
  catalog có sẵn trong hướng dẫn của orc."

## Thay đổi source sau khi chốt

- `src/backend/app/application/itinerary/orc_contracts.py`: bỏ `DESTINATIONS` khỏi `TOOLS`.
- `src/backend/app/application/itinerary/orc_dispatch.py`: bỏ `_list_destinations` và `list_destinations` khỏi
  `CATALOG_TOOLS`.
- `src/backend/app/agents/orc_v2.py`: bỏ câu "Chỉ gọi list_destinations khi hướng dẫn không kèm danh sách", bỏ
  `destinations` khỏi `KINDS`.
- Tests `test_orc_contracts.py`, `test_orc_tool_dispatch.py`, `test_orc_loop.py`; `docs/spec/agent/working-context.md` §3.1.
- Port `list_destinations` và route `/destinations` giữ nguyên (code và frontend vẫn dùng).
