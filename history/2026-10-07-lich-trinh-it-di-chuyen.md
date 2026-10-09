# Lịch trình ít di chuyển: gom điểm gần nhau theo ngày, khách sạn gần các điểm

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Thay thế: history/2026-10-07-de-xuat-lich-trinh-it-di-chuyen.md

## Mục tiêu

Áp dụng đề xuất `docs/prd/update-archive/2026-10-07-lich-trinh-it-di-chuyen.md`, Nguyễn Minh Nhật chốt ngày 2026-10-07.
Mã liên quan: FR-AGT-03, NFR-REL-01, AC-AGT-04 (mới).

Trước đây `compose_plan` không xét vị trí: chọn khách sạn và hoạt động rẻ nhất, rải theo số lượng. Hai điểm cách nhau
40 km (Bắc và Nam Phú Quốc) có thể nằm cùng một ngày.

## File thay đổi

**PRD**
- `docs/prd/requirements.md` — sửa: thêm dòng AC-AGT-04.
- `docs/prd/update/2026-10-07-lich-trinh-it-di-chuyen.md` → `docs/prd/update-archive/` — chuyển, trạng thái `đã áp dụng`.
  Trước khi chốt, đề xuất được bổ sung luật "chưa rõ vị trí" (toạ độ tâm thành phố) sau khi đo trên database staging.
  Đề xuất chưa từng được commit nên được chuyển bằng `mv`, không phải `git mv`.

**Backend**
- `src/backend/app/domain/itinerary/geo.py` — thêm: `coords`, `located` (bỏ toạ độ tâm thành phố), `haversine_km`,
  `medoid`, `band` (bậc 2 km).
- `src/backend/app/domain/itinerary/planning.py` — sửa:
  - `_activity_order`/`_stay_order` nhận thêm mức khoảng cách, đứng sau nguồn (và sau "cả ngày trước" của hoạt động),
    trước giá;
  - `compose_plan`: mốc = medoid hoạt động rõ vị trí; chọn hoạt động gần mốc; chọn khách sạn **sau** hoạt động theo
    khoảng cách trung bình tới các hoạt động đã xếp; gom ngày bằng `_group_by_distance`; proposal có
    `criteria = "DISTANCE"` khi luật được dùng.
- `src/backend/app/domain/itinerary/types.py` — sửa: `Proposal.criteria`.
- `src/backend/app/agents/steps/composition.py` — sửa: warning `PLAN_CRITERIA` khi `criteria == "DISTANCE"`.
- `src/backend/app/agents/steps/messages.py` — sửa: thêm `section_criteria`, `plan_criteria` (vi, en).
- `src/backend/app/agents/steps/narration.py` — sửa: mục "Cách mình xếp lịch" chèn trước mục chi phí ở cả bản LLM và
  bản fallback; payload có `criteria_shown_separately`.
- `src/backend/app/agents/steps/prompts.py` — sửa `NARRATE_PROMPT`: LLM không tự viết mục tiêu chí, không nêu khoảng
  cách hay thời gian di chuyển.

**Test**
- `src/backend/tests/unit/domain/test_itinerary_geo.py` — thêm (11 test).
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — sửa: thêm `DistanceComposeTests` (13 test). 7 test hành
  vi fail trên code cũ trước khi sửa. Không test cũ nào phải đổi kỳ vọng.
- `src/backend/tests/unit/agents/test_composition_plan_criteria.py` — thêm (3 test).
- `src/backend/tests/unit/agents/test_narration.py` — sửa: thêm `PlanCriteriaTests` (3 test).

**Spec**
- `docs/spec/agent/nghiep-vu/xep-lich.md` — sửa: thứ tự chọn, mục "Gom theo khoảng cách", ⚠️ toạ độ tâm thành phố.
- `docs/spec/agent/nghiep-vu/glossary.md` — sửa: thêm mốc, mức khoảng cách, rõ vị trí.
- `docs/spec/agent/langgraph-nodes.md` §5 — sửa.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7 — sửa: thêm mục "Lịch trình ít di chuyển".

**History**
- `history/2026-10-07-de-xuat-lich-trinh-it-di-chuyen.md` — thêm dòng `Bị thay thế bởi`.

## Quyết định

- **Gom ngày bằng ghép cặp ngắn nhất trước**, không đổi số hoạt động mỗi ngày. Luật rải ngày và cửa sổ giờ bay vẫn quyết
  định *bao nhiêu*; khoảng cách chỉ quyết định *điểm nào* đi cùng nhau. Nhờ vậy AC-AGT-02 không bị ảnh hưởng.
- **Khách sạn chọn sau hoạt động.** Để không chọn cả khách sạn lẫn hoạt động cùng sản phẩm cha, khách sạn bỏ các sản phẩm
  có cha trùng hoạt động đã chọn. Trước đây chiều loại trừ là ngược lại. Hai loại khác taxonomy nên trường hợp này gần
  như không xảy ra.
- **Không điểm nào rõ vị trí thì giữ luật cũ.** Mọi mức khoảng cách là 0, không gom ngày, không có `PLAN_CRITERIA`.
- **Số ứng viên chung toạ độ đếm trong ứng viên của lượt**, vì domain không đọc catalog. Ngưỡng 5 giữ đúng PRD.
- **Không đổi contract.** `warnings[].code` là chuỗi tự do. Widget không hiển thị `warnings`, nên không sửa frontend.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain`: 1126 passed.
- `.venv/bin/python -m pytest -q src/backend/tests -x -p no:cacheprovider`: 1842 passed, 35 skipped (gồm
  `tests/architecture`).
- Mô phỏng tất định (tầng fixture, không phải agent thật).
  - Cách chạy: script trong scratchpad lấy 30 lần ngẫu nhiên (seed 42), mỗi lần 10 điểm tham quan + 10 khách sạn có giá
    của một điểm đến, từ `src/data_collection/snapshots/2026-09-30/products.jsonl.gz`. Mỗi mẫu được xếp lịch 3 ngày, 2
    người lớn bằng `compose_plan` của HEAD và của bản mới.
  - Đại lượng đo: km/chuyến là tổng đường chim bay khách sạn → điểm → khách sạn mỗi ngày; giá trung vị là giá trung vị
    của các hoạt động đã xếp, tính bằng ₫.

  | Điểm đến | km/chuyến cũ | km/chuyến mới | xa nhất trong ngày cũ | xa nhất trong ngày mới | giá trung vị cũ | giá trung vị mới |
  |---|---|---|---|---|---|---|
  | Phú Quốc | 149.7 | 15.6 | 22.4 | 3.3 | 386,687 | 441,500 |
  | Nha Trang | 38.4 | 22.3 | 4.3 | 0.3 | 392,483 | 462,667 |
  | Hà Nội | 58.8 | 49.4 | 9.2 | 0.3 | 942,509 | 1,100,467 |
  | Hội An | 80.5 | 76.2 | 0.3 | 0.0 | 424,433 | 431,267 |

  Giá hoạt động tăng khoảng 2–18%: đây là đánh đổi theo luật "gần trước, rẻ sau".
- Đã định chạy mô phỏng trên database staging, nhưng tunnel `localhost:15432` bị ngắt giữa phiên.
- Chưa chạy golden case với LLM thật và chưa chạy agent end-to-end trên backend local.

## Còn lại / rủi ro

- Chạy golden case Đà Nẵng (`--only TC-NN`) và một lượt thật "Phú Quốc 3 ngày" để xem mục "Cách mình xếp lịch" trong
  chat.
- Toạ độ tâm thành phố: luật nhận diện chỉ là cách tạm. Cần nguồn đánh dấu độ chính xác (`attributes.geoPrecision`).
- Để đợt sau, mỗi việc một đề xuất riêng:
  - quãng đường bộ thật (OSRM) và hiện km/phút;
  - nâng hạng khách sạn theo ngân sách.
