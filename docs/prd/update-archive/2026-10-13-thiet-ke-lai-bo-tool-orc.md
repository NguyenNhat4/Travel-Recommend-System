# Thiết kế lại bộ tool của orc: bỏ tool thừa, gộp tool chồng nhau, sửa tool tốn lượt

- Ngày: 2026-10-13
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13 (chốt A–G và triển khai toàn bộ trong chat)
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §3 (Công cụ, lập lịch và hai loại ngân sách), `docs/prd/requirements.md` §1.4 (FR-AGT-02)
- Mã FR/NFR: FR-AGT-02, FR-AGT-03, NFR-REL-01

Đề xuất chia 7 phần (A–G), chốt được từng phần. Phần A trùng đề xuất
`2026-10-13-diem-den-trong-system-prompt-bo-tool-destinations.md`; chốt A ở đây thì đề xuất kia chuyển archive cùng lúc.

## Lý do

Đo trên model thật (13/10/2026) thấy bộ 8 tool hiện tại làm hỏng lượt theo những cách lặp lại:

- Tool chồng nhau (`search_products`, `list_products`, `get_recommendations`, `get_similar_products`) nên prompt phải
  giải thích dài khi nào dùng cái nào, model vẫn chọn sai.
- Lập lịch qua đêm cần: tìm khách sạn → liệt kê hạng phòng → build. Hết 3 lượt gọi tool trước khi kịp sửa vi phạm.
- Sản phẩm trong lịch sử phải đọc lại từng cái một (`get_product_detail`), sửa lịch 5–6 sản phẩm tốn một lượt và gần
  hết 10 request.
- `lookup_flights` một lời gọi tốn tới 5 request (1 tuyến + 4 trang), khứ hồi có thể hết cả 10 request.
- `build_itinerary` chỉ kiểm: model phải tự tính giờ từng phút, đệm sân bay 90/150 phút, số phòng. Đây là chỗ model
  sai nhiều nhất và code làm đúng chắc chắn.

## Nội dung đề xuất

**A. Bỏ Destinations.** Tên điểm đến catalog đặt sẵn trong system prompt (code đọc từ catalog, cache ngắn, không tính
ngân sách lượt).

**B. Gộp Search và Catalog list thành `find_products`.** Lọc theo điểm đến, loại, giá, sao, ngày còn chỗ, loại trừ, sắp
xếp, phân trang. Có `query` thì xếp theo độ khớp (Search); không có `query` thì duyệt theo sort (Catalog list);
`parent_ref` liệt kê hạng phòng. Không đổi thuật toán Search/Catalog, chỉ đổi cách orc gọi.

**C. Detail nhận nhiều sản phẩm.** `get_products(refs, include_rooms)`: tối đa 10 ref một lần gọi, tính một request
nguồn mỗi sản phẩm như hiện tại nhưng chỉ một lượt gọi tool; `include_rooms` trả kèm hạng phòng của khách sạn.

**D. Gộp Similar vào Recommendation.** `recommend(destination, taxonomy, like_ref, k)`: không `like_ref` là gợi ý theo
khách (giữ strategy popular/personalized); có `like_ref` là sản phẩm tương tự. Thêm lọc `taxonomy`, `exclude_refs`.

**E. `build_itinerary` tự tính giờ.** Orc đưa: mỗi ngày những ref nào, thứ tự, buổi mong muốn (tuỳ chọn), lưu trú, chuyến
bay. Code tính giờ bắt đầu/kết thúc từ thời lượng, giờ mở cửa, đệm sân bay; tính số phòng, tổng tiền; trả lịch đã tính
cùng violations/warnings. Code vẫn không thêm, bỏ hay thay sản phẩm; orc vẫn chọn sản phẩm và thứ tự. Orc có thể đặt giờ
cố định cho một hoạt động (giữ nguyên).

**F. Mỗi ngày 2–3 hoạt động.** Ngày trọn vẹn có 2–3 hoạt động (sáng, chiều, có thể tối); ngày đến/về theo giờ bay
có thể ít hơn. build_itinerary báo vi phạm khi một ngày quá 3 hoạt động. Thay câu PRD "Không áp trần hai hoạt
động/ngày" (architecture §3).

**G. Số đêm = số ngày − 1.** Chuyến N ngày lưu trú tối đa N − 1 đêm, trả phòng ngày cuối (3 ngày → 2 đêm). Tiền phòng
= giá/đêm × số đêm × số phòng; số phòng = ceil(số khách / số người giá phòng đã gồm), thiếu dữ liệu thì dùng sức chứa
và cảnh báo. Ngân sách chuyến = tổng phòng + vé tham quan theo người + combo (giá gói hoặc theo người như hiện tại) +
vé bay; vẫn chỉ là cảnh báo khi vượt.

Bằng chứng F–G (LLM thật, 13/10, "Lên lịch chuyến đi Đà Nẵng 3 ngày từ 25/10" → "mình đi một mình", ×3): 1/3 ra lịch;
lịch đó có 1–2 hoạt động/ngày và 3 đêm (trả phòng ngày 28 cho chuyến 25–27). 1/3 hết 3 lượt tool (tìm → hạng phòng →
build bị OUTSIDE_OPENING_HOURS) nên chỉ trả danh sách thẻ, đúng như ảnh người dùng gửi; C và E bỏ được lượt hạng phòng
và lỗi giờ mở cửa.

Ngoài ra (không lệch PRD, làm cùng): chi phí request của `lookup_flights` báo rõ cho orc trong `remaining`; lỗi
`CURSOR_MISMATCH` nêu tham số đã đổi.

Đoạn PRD thay thế, `docs/prd/architecture.md` §3:

- Hiện tại: "Tám tool: Search, Recommendation, Similar, Detail, Destinations, Catalog list, Flights và build_itinerary."
- Thay bằng: "Năm tool: find_products (Search + Catalog list), recommend (Recommendation + Similar), get_products
  (Detail nhiều sản phẩm, kèm hạng phòng), Flights và build_itinerary. Tên điểm đến catalog đặt sẵn trong system prompt."
- Hiện tại: "Orc chọn refs và phác ngày/giờ. build_itinerary chỉ kiểm, tính tiền, tối ưu trong quyền được cấp…"
- Thay bằng: "Orc chọn refs, thứ tự trong ngày và buổi mong muốn. build_itinerary tính giờ từ thời lượng, giờ mở cửa và
  đệm sân bay, kiểm, tính tiền, tối ưu trong quyền được cấp…" (phần còn lại giữ nguyên).

`docs/prd/requirements.md` FR-AGT-02: đổi danh sách công cụ theo đúng năm tool trên.

## Thay đổi source sau khi chốt

- `src/backend/app/application/itinerary/orc_contracts.py`: schema năm tool.
- `src/backend/app/application/itinerary/orc_dispatch.py`, `flight_lookup.py`: thực thi tool mới; port
  `ItineraryTools`/gateway giữ nguyên (gộp ở tầng orc, không đổi API Search/Catalog/Recommendation).
- `src/backend/app/domain/itinerary/draft_validation.py`: tính giờ (E).
- `src/backend/app/agents/orc_v2.py`: `PROMPT` (bỏ đoạn chọn giữa các tool chồng nhau, cập nhật thứ tự lập lịch), `KINDS`.
- Frontend `widgetProgressView.ts` (nhãn theo kind), contract `ActivityData.kind` nếu đổi giá trị kind.
- Tests `test_orc_*`, `test_assistant_v2_*`; ca `assistant_v2_cases.py` chạy lại ×3 trên model thật trước/sau.
- `docs/spec/agent/working-context.md` §3.1, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`.

## Chi tiết áp dụng theo plan đã duyệt

Tool lập lịch mang tên `plan_itinerary`; orc chọn morning/afternoon/evening, code tính giờ, đêm, phòng và chi phí.
Hội thoại nối thêm bằng function calling; `update_trip` có evidence, `respond` giữ cấu trúc final, không tính lượt nghiệp vụ.
Số phòng tính theo tổng khách; thiếu cơ sở giá dùng sức chứa và công bố cảnh báo. Combo chỉ gợi ý riêng.
Giữ giới hạn ba tool nghiệp vụ/lượt; luồng mẫu có combo và vé đồng thời phải chia sang lượt sau hoặc bỏ lời gọi
không cần, không vượt giới hạn để ép đủ ứng viên. Không đổi response/SSE v2 hoặc API các engine.
