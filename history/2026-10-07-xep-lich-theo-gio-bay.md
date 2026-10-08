# Xếp hoạt động của lịch trình theo giờ máy bay

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Thay thế: history/2026-10-07-de-xuat-xep-lich-theo-gio-bay.md

## Mục tiêu

Áp dụng đề xuất `docs/prd/update-archive/2026-10-07-xep-lich-theo-gio-bay.md`, Nguyễn Minh Nhật chốt ngày 2026-10-07.
Mã liên quan: FR-AGT-03, AC-AGT-02.

Lỗi gốc ghi ở `history/2026-10-06-ve-may-bay-trong-lich-trinh.md`: chặng đi VJ505 cất cánh 19:50 ngày 1 mà Bà Nà vẫn
được xếp vào sáng ngày 1, vì `compose` xếp lịch trước rồi mới gắn vé.

## File thay đổi

**PRD**
- `docs/prd/requirements.md` — sửa AC-AGT-02: thêm luật xếp lịch theo giờ bay.
- `docs/prd/update/2026-10-07-xep-lich-theo-gio-bay.md` → `docs/prd/update-archive/` — chuyển, trạng thái `đã áp dụng`.

**Backend**
- `src/backend/app/domain/itinerary/flights.py` — thêm `flight_times`: giờ hạ cánh chặng đi và giờ cất cánh chặng về theo
  giờ Việt Nam. Vé khứ hồi lấy giờ về từ `returnFlight.departureAt`.
- `src/backend/app/domain/itinerary/planning.py` — sửa:
  - thêm `PERIODS`, `ACTIVITY_TIMES`, `ARRIVAL_BUFFER` (90 phút), `DEPARTURE_BUFFER` (150 phút) và `day_windows`;
  - `compose_plan(..., windows)`: chỉ dùng buổi trong cửa sổ, thêm slot `TRANSFER`;
  - thêm `NOTES` `ARRIVAL`/`DEPARTURE`;
  - `validate_plan` báo `schedule` khi hoạt động nằm ngoài cửa sổ.
- `src/backend/app/agents/steps/composition.py` — sửa:
  - chọn vé trước `compose_plan`;
  - `with_flights` nhận các chặng đã chọn;
  - bỏ `DAY_WITHOUT_PRODUCTS` cho ngày mà giờ bay không chừa buổi nào.
- `src/backend/app/agents/steps/narration.py` — sửa: bản fallback in dòng di chuyển theo thứ tự slot.
- `src/backend/app/agents/steps/prompts.py` — sửa `NARRATE_PROMPT`: slot `TRANSFER` là dòng di chuyển; ngày chỉ có dòng
  này không phải ngày tự do.

**Test**
- `src/backend/tests/unit/domain/test_itinerary_flights.py` — sửa: thêm 8 test (`day_windows` và `validate_plan`).
- `src/backend/tests/unit/domain/test_itinerary_composition.py` — sửa: thêm `FlightWindowComposeTests` (6 test).
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: thêm test end-to-end cho chuyến hạ cánh muộn.
- `src/backend/tests/unit/agents/test_narration.py` — sửa: thêm test dòng di chuyển trong bản fallback.
- `src/frontend/tests/unit/widgetDays.test.tsx` — sửa: thêm test hiển thị slot `TRANSFER`.

**Spec**
- `docs/spec/agent/langgraph-nodes.md` §5 — sửa mục 4 (luật cửa sổ giờ) và mục 7 (ngoại lệ slot `TRANSFER`).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7 — thêm mục "Xếp lịch theo giờ bay".

**History**
- `history/2026-10-07-de-xuat-xep-lich-theo-gio-bay.md` — thêm dòng `Bị thay thế bởi`.

## Quyết định

- **Khung buổi do agent đặt, được chốt cùng đề xuất:** sáng 08:00–12:00, trưa 12:00–13:30, chiều 13:30–17:00, tối
  18:00–21:00. Trước đó code chỉ có nhãn buổi, không có giờ.
- **Hoạt động vẫn chỉ xếp sáng và chiều.** Compose chưa đọc `openingHours` (có ở 413/610 điểm tham quan).
- **So theo datetime, không theo giờ trong ngày**, để chuyến hạ cánh sau nửa đêm rơi đúng vào ngày hôm sau.
- **Hoạt động cả ngày chỉ vào ngày còn đủ mọi buổi.** Ngày về cất cánh 19:45 mất buổi tối nên không nhận hoạt động cả ngày.
- **`validate_plan` đọc thời lượng từ `candidates`**, vì `summary` không giữ `durationMinutes`.
- **Không đổi contract và frontend.** Dùng `SlotTime` và `ActivityType.TRANSFER` sẵn có; widget đã vẽ được slot này.
- **Giữ nguyên thứ tự chọn vé** theo lựa chọn của người dùng.

## Kiểm tra

**Fixture và tất định**
- Test mới chạy trên code cũ: fail. Domain lỗi import `day_windows`; runtime vẫn xếp hoạt động vào ngày 1.
- `pytest -q src/backend/tests` → 1758 passed, 32 skipped.
- `validate_contract.py` → PASS (111 schema, 87 fixture; CDP clone 12 schema).
- Frontend: `vitest run` → 64 file, 628 passed; `tsc --noEmit` sạch.

**LLM thật** (backend local `inprocess`, Postgres local)

Câu thử: `POST /api/v1/assistant/itineraries` "Lên lịch trình 3 ngày ở Đà Nẵng từ ngày 8/10/2026, 2 người lớn, ngân sách
10 triệu, đi từ Hà Nội" → `COMPLETED`.

- Vé: VJ505 bay 08/10 19:50, hạ cánh 21:10; VJ518 cất cánh 10/10 19:45.
- Ngày 1: chỉ có "Buổi tối — Di chuyển từ sân bay, nhận phòng."
- Ngày 2: Sun World Bà Nà Hills buổi sáng (cả ngày).
- Ngày 3: "Buổi tối — Ra sân bay."
- Tổng 4.060.000 ₫, `WITHIN_BUDGET`.
- Ngày 3 không có hoạt động vì hết ứng viên: 14 sản phẩm bị loại theo ngày (`PRODUCT_DROPPED_DATE`) và khách sạn Đà Nẵng
  chỉ mở từ 15/10. Không phải do cửa sổ giờ.

## Còn lại / rủi ro

- `durationMinutes` là mức thấp nhất của khoảng nguồn ghi ("1–3 tiếng" thành 60'). Một hoạt động 4–6 giờ ở buổi chiều
  ngày về vẫn có thể kéo dài quá giờ ra sân bay; khoảng đệm 150 phút chỉ giảm rủi ro này.
- LLM có lúc thêm chữ vào dòng di chuyển ("…nhận phòng để bắt đầu chuyến đi nhẹ nhàng"). Không sai dữ liệu.
- Chưa thêm golden case cho chuyến hạ cánh muộn.
