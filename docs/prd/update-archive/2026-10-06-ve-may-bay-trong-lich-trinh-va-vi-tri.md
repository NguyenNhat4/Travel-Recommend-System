# Thêm vé máy bay vào lịch trình của trợ lý, hỏi nơi đi và cho dùng vị trí trình duyệt

- Ngày: 2026-10-06
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-06
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 (FR-AGT-01, FR-AGT-02, FR-AGT-03), §3 (AC-AGT-01, thêm AC mới);
  `docs/prd/architecture.md` §3 (sơ đồ StateGraph, chuẩn grounding); `docs/prd/user-flow.md` §4.2 (widget trợ lý, form gợi ý)
- Mã FR/NFR: FR-AGT-01, FR-AGT-02, FR-AGT-03, FR-AGT-04; AC mới — cần cấp mã (đề xuất AC-AGT-02)

## Lý do

PRD đã coi vé máy bay là một phần của lịch trình: `project-brief.md` §2.2 nói trợ lý chỉ dùng "phòng nghỉ, chuyến bay
thực sự có thể đặt được", và `user-flow.md` §4.2 có nút "Đặt ngay" cho vé máy bay trong lịch trình. Nhưng luồng trợ lý
không có cách lấy vé:
- chuyến đi không có trường **nơi đi**;
- sơ đồ `architecture.md` §3 chỉ tìm "phòng & tour";
- form gợi ý không có ô nơi đi.

Hiện agent chỉ tìm hotel, attraction và golf, nên lịch trình không bao giờ có vé.

Catalog đã có dữ liệu đủ dùng (Postgres local 06/10/2026): 113 tuyến, 1.594 chuyến, 19 thành phố đi. Có cả vé khứ hồi
(`tripType = roundTrip`, kèm `returnFlight`/`returnDate`) và toạ độ sân bay đi (`originLatitude`/`originLongitude`).
`/search` đã nhận tham số `origin` (FR-SRC-03), và `GET /products?parentProductId=` liệt kê chuyến của một tuyến.

Người dùng muốn có vé máy bay và cho phép **xin quyền vị trí** để gợi ý nơi đi. Vị trí là dữ liệu cá nhân mà PRD
chưa nhắc tới, nên cần chốt cách dùng.

## Nội dung đề xuất

### 1. `requirements.md` §1.4

**FR-AGT-01.** Hiện tại: "làm rõ nhu cầu du lịch (thời gian, địa điểm, số người, ngân sách, phong cách du lịch)".
Thay bằng: "làm rõ nhu cầu du lịch (thời gian, địa điểm, **nơi đi**, số người, ngân sách, phong cách du lịch)".

**FR-AGT-02.** Hiện tại: "các công cụ: tìm kiếm sản phẩm, kiểm tra lịch trống, tính toán chi phí dự kiến".
Thay bằng: "các công cụ: tìm kiếm sản phẩm, **tìm chuyến bay theo tuyến và ngày**, kiểm tra lịch trống, tính toán chi
phí dự kiến".

**FR-AGT-03.** Hiện tại: "bao gồm địa điểm, thời gian di chuyển ước tính và danh sách sản phẩm đề xuất".
Thay bằng: "bao gồm địa điểm, thời gian di chuyển ước tính, danh sách sản phẩm đề xuất và **chặng bay đi/về khi đủ điều
kiện (AC-AGT-02)**".

### 2. `requirements.md` §3 — AC

**AC-AGT-01 (sửa).**
- Hiện tại, câu hỏi gộp gồm "ngày đi, số người và ngân sách". Thay bằng "ngày đi, số người, ngân sách và **nơi đi**".
- Hiện tại, form có các ô "điểm đến, số ngày, ngày khởi hành, số người, ngân sách". Thay bằng "điểm đến, số ngày, ngày
  khởi hành, số người, ngân sách, **nơi đi**".
- Thêm câu: "Nơi đi không bắt buộc, như ngân sách: thiếu thì vẫn lập lịch, chỉ không có vé máy bay."

**AC-AGT-02 (mới — vé máy bay trong lịch trình).**

*Có chặng bay* khi đủ cả 5 điều kiện:
1. Biết nơi đi.
2. Catalog có tuyến từ nơi đi đến điểm đến.
3. Người dùng không loại trừ vé máy bay ("đã có vé", "đi ô tô").
4. Có chuyến còn bán và có giá đúng ngày: đi ngày khởi hành, về ngày cuối chuyến. Ưu tiên vé khứ hồi, không có thì ghép
   hai chặng một chiều.
5. Chuyến đi từ 2 ngày trở lên. Chuyến 1 ngày chỉ có vé khi người dùng hỏi rõ.

*Thứ tự chọn chuyến:* bay thẳng, rồi giá thấp, rồi giờ hợp lý (đi sớm, về muộn).

*Tiền:* giá vé × số khách được tính vào tổng. Vé không bị bỏ vì vượt ngân sách; khi đó lịch trình báo "vượt ngân sách".

*Không có chặng bay* thì câu trả lời luôn nói lý do:

| Trường hợp | Câu trả lời |
|---|---|
| Chưa có nơi đi | Mời người dùng cho biết nơi đi để thêm vé |
| Không có tuyến trong catalog | "Chưa có chuyến bay từ X đến Y" |
| Không có chuyến đúng ngày | Gợi ý đổi ngày |
| Chỉ có một chiều | Hiện chặng tìm được và báo thiếu chặng còn lại |

*Lượt sửa lịch:* chỉ chọn lại vé khi nơi đi, ngày đi, số ngày hoặc điểm đến đổi.

**AC-AGT-03 (mới — vị trí trình duyệt).**
- Ô nơi đi của form và câu hỏi gộp có nút "Dùng vị trí hiện tại". Trình duyệt chỉ hỏi quyền **khi người dùng bấm**,
  không tự hỏi khi mở trợ lý.
- Được phép thì Web đổi toạ độ thành thành phố có sân bay gần nhất trong catalog và điền vào ô nơi đi. Người dùng vẫn sửa được.
- **Toạ độ không rời trình duyệt.** Chỉ tên thành phố được gửi lên. Toạ độ không được lưu, ghi log hay gửi tới LLM, CDP hoặc Insider.
- Từ chối hoặc lỗi thì giữ ô để gõ tay.

### 3. `architecture.md` §3

Sơ đồ StateGraph:
- `AnalyzeIntent --> CheckClarification: Trích xuất thông tin (Điểm đến, Ngày, Số người, Ngân sách)`
  → `(Điểm đến, Nơi đi, Ngày, Số người, Ngân sách)`.
- `SearchCandidates --> ToolCatalogSearch: Gọi Tool tìm kiếm phòng & tour thật (và Similar khi đổi món)`
  → `Gọi Tool tìm kiếm phòng, tour và chuyến bay thật (và Similar khi đổi món)`.

Chuẩn grounding: thêm một gạch đầu dòng.
> **Vé máy bay** chỉ lấy từ chuyến bay thật của catalog. `compose` chọn chuyến bằng luật tất định (AC-AGT-02), LLM không
> chọn hay tạo chuyến. Vị trí trình duyệt chỉ dùng ở Web để gợi ý nơi đi; toạ độ không vào state của agent.

### 4. `user-flow.md` §4.2

Đoạn "Form gợi ý thông tin chuyến đi":
- Hiện tại, danh sách ô là "(điểm đến …, số ngày 1–7, ngày khởi hành không trước hôm nay, số người, ngân sách)". Thêm
  "**nơi đi** (không bắt buộc, có nút "Dùng vị trí hiện tại")".

Đoạn "Thẻ trong khung chat":
- Hiện tại là "(khách sạn, hoạt động, gói nhiều ngày gợi ý riêng)". Thay bằng "(khách sạn, **chặng bay**, hoạt động,
  gói nhiều ngày gợi ý riêng)".
- Thêm câu: "Thẻ chặng bay hiện hãng, số hiệu, giờ đi/đến, bay thẳng hay nối chuyến, giá × số khách và nút [Đặt ngay]."

## Thay đổi source sau khi chốt

- **Contract** (thêm field, tương thích v1), sửa trước khi code, file `src/shared/contracts/schemas/itinerary-agent.yaml`:
  - `TripIntent.origin` và `TripIntentPatch.origin`;
  - `missingFields` thêm `origin`;
  - form gợi ý thêm ô `origin`;
  - `Itinerary.flights { outbound, return }`, mỗi chặng là `ProductSummary` kèm `source`;
  - chạy `validate_contract.py`.
- **Backend agent:**
  - `agents/models.py` (`IntentUpdate.origin`);
  - `agents/steps/prompts.py` (EXTRACT: trích nơi đi; TOOL_PLAN: lời gọi vé máy bay);
  - `agents/steps/tool_planning.py` (chuẩn hoá `origin` theo `originCity` của catalog; search `taxonomy=flight, origin`);
  - tool mới liệt kê chuyến của tuyến qua `GET /products?parentProductId=` ở `application/itinerary/tool_contracts.py`,
    `engine_tools.py` và `infrastructure/clients/*`;
  - `domain/itinerary/planning.py` (chọn chặng theo AC-AGT-02, `totals` tính vé × số khách);
  - `domain/itinerary/search_hints.py` (gợi ý cho flight: bay thẳng, hãng, buổi).
- **Frontend:** `src/frontend/src/features/itinerary/widget/` (ô nơi đi, nút vị trí, đổi toạ độ ra thành phố gần nhất,
  thẻ chặng bay).
- **Spec:** `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/agent/langgraph-nodes.md`,
  `docs/spec/agent/state-fields.md`, `docs/spec/hop-dong-tich-hop-frontend.md`.
- **Test:**
  - unit chọn chặng và tổng tiền;
  - contract;
  - golden case "Hà Nội → Đà Nẵng 3 ngày, 2 người lớn";
  - test Web: toạ độ không có trong request.
