# Khung tiến trình của trợ lý hiện kết quả thật của từng bước

- Ngày: 2026-10-12
- Người đề xuất: Nguyễn Minh Nhật / Claude Code
- Trạng thái: chờ chốt (chỉ Phần B). Phần A và C đã áp dụng vào PRD ngày 2026-10-13
  - Phần A, trước demo: khung tiến trình, dòng tóm tắt, chẩn đoán mức 1.
  - Phần B, sau demo: chẩn đoán mức 2.
  - Phần C, kết quả từng phần trước lời tư vấn: chỉ xin chốt khi số đo D1 đạt tiêu chí. Tiêu chí ở
    `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` §3.5.
- Chốt bởi / ngày: Nguyễn Minh Nhật, 2026-10-13 — “Chốt cả A và C, thêm thẻ xem trước”
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §3 (thêm AC-AGT-09); `docs/prd/user-flow.md` §4.2; `docs/prd/architecture.md`
  §3 ("Tiêu chuẩn Grounding"); `docs/prd/deployment-plan.md` §2 (chỉ Phần B)
- Mã FR/NFR: mới — cần cấp mã AC-AGT-09; phục vụ FR-AGT-01, FR-AGT-06, NFR-PERF-02, NFR-REL-01, NFR-SEC-01

## Lý do

Khung tiến trình của trợ lý chỉ ghi tên bước chung chung ("Đang hiểu yêu cầu", "Tìm sản phẩm phù hợp"). Người dùng không
biết trợ lý đã hiểu đúng chưa, đang tìm gì, tìm được bao nhiêu, hay bỏ qua gì. Với lượt khám phá và hỏi vé, khung còn
đứng yên ở bước đầu tới khi có câu trả lời.

Orchestrator nay là luồng mặc định (chốt 13/10). Lần chạy thử ngày 12/10 đo 7–14 giây cho lượt chỉ trả lời và 17–39 giây
cho lượt có tìm kiếm. Người xem chờ lâu mà không biết đang có chuyện gì, nhất là khi demo. Nhà phát triển cũng không có
chỗ xem nhanh trợ lý đang ở bước nào và mất bao lâu. PRD hiện không mô tả khung này, nên mọi thay đổi ở đây là hành vi
mới.

## Nội dung đề xuất

### Phần A — trước demo

**A1. `requirements.md` §3: thêm dòng sau AC-AGT-08**

| **AC-AGT-09** | Người dùng gửi tin nhắn cho trợ lý và chờ câu trả lời: lập lịch, khám phá hoặc hỏi vé | Khung tiến trình hiện kết quả thật của từng bước, không chỉ tên bước. Bước hiểu yêu cầu nhắc lại điểm đến, ngày, số ngày, số người, nơi đi, ngân sách, sở thích đã hiểu; điều trợ lý tự quyết được đánh dấu riêng (ví dụ chưa nêu ngân sách thì không giới hạn theo giá; chưa nêu nơi đi thì chưa tìm vé). Bước tìm kiếm ghi số tìm thấy và số chọn cho từng nhóm tìm kiếm (theo loại sản phẩm và điều kiện) và cho chặng bay. Bước xếp lịch chỉ ghi tiêu chí hệ thống thật sự áp dụng. Sản phẩm bị loại, hoặc tra cứu không thành công, thì ghi rõ lý do và số lượng; tra cứu không thành công không được ghi là không có kết quả. Mọi số liệu do hệ thống đếm tại chỗ xử lý kết quả của chính lượt đó, không do LLM viết; không hiện tên công cụ, API, câu truy vấn hay dữ liệu thô. Bước đang chạy có biểu tượng chờ và câu việc đang làm, bước xong có ✓ kèm kết quả, bước sắp tới hiện mờ; chỉ hiện những bước chắc chắn sẽ chạy. Khi xong, khung thu gọn thành một dòng tóm tắt ở đầu câu trả lời, trên lời diễn giải và các thẻ, bấm để xem lại các bước; lượt trò chuyện và hỏi lại không có dòng này. Tiến trình không lưu ở server: hội thoại mở lại từ lịch sử không hiện lại khung tiến trình hay dòng tóm tắt. |

**A2. `user-flow.md` §4.2: thêm đoạn trước mục 4 "Ngoài phạm vi"**

> **Khung tiến trình** (AC-AGT-09): khi trợ lý đang trả lời, bong bóng của trợ lý hiện các bước của lượt đó. Lập lịch có
> 4 bước: hiểu yêu cầu → tìm sản phẩm → sắp xếp lịch → viết lời tư vấn. Khám phá có 3 bước: hiểu → tìm → viết câu trả
> lời. Hỏi vé có 2 bước: hiểu → tra vé. Mỗi bước xong ghi kết quả thật, ví dụ "✓ Đà Nẵng · 17/10 · 2 người lớn",
> "Khách sạn: tìm thấy 42, chọn 3", "⚠ 2 khách sạn không còn chỗ ngày 17/10, đã bỏ qua". Xong thì khung thu gọn thành
> một dòng ở đầu câu trả lời, trên lời diễn giải và các thẻ. Hội thoại mở lại từ lịch sử không hiện lại khung này.
>
> **Chẩn đoán cho nhà phát triển:** bảng chẩn đoán có sẵn (Shift+D) có thêm mục "Trợ lý — lượt gần nhất": mã request để
> tìm trace, từng bước kèm thời gian và số liệu đầy đủ. Mục này chỉ dùng dữ liệu stream đã gửi cho mọi người dùng.

**A3. `architecture.md` §3, "Tiêu chuẩn Grounding": thêm ý**

> - **Khung tiến trình:** dữ kiện của khung tiến trình do code tính từ state hoặc đếm tại chỗ lọc kết quả tool của lượt
>   đó, gửi qua SSE dạng mã và số; Web viết câu chữ. Stream không mang prompt, output thô của LLM hay token.

### Phần B — sau demo: chẩn đoán mức 2

**B1. `user-flow.md` §4.2, nối vào đoạn "Chẩn đoán cho nhà phát triển"**

> Chi tiết lời gọi công cụ và LLM chỉ gửi cho request mang khoá chẩn đoán của server, và chỉ gồm các trường được phép
> (không câu chữ tự do, không prompt, không token).

**B2. `architecture.md` §3, nối vào ý "Khung tiến trình"**

> Chi tiết kỹ thuật cho nhà phát triển chỉ gửi khi request mang khoá `ASSISTANT_STREAM_DEBUG_TOKEN` hợp lệ, và chỉ gồm
> trường trong danh sách cho phép theo từng công cụ.

**B3. `deployment-plan.md` §2: thêm dòng**

| `ASSISTANT_STREAM_DEBUG_TOKEN` | Khoá chẩn đoán của trợ lý. Trống (mặc định) thì tắt. Có giá trị thì request mang header `X-Assistant-Debug-Token` khớp khoá này nhận thêm chi tiết kỹ thuật trong stream. Chỉ đặt ở dev và staging, không đặt ở production | Dev, Staging | Bí mật |

### Phần C — kết quả từng phần trước lời tư vấn (chỉ khi đo thấy có ích)

Người dùng chỉ đạo (12/10): chỉ giữ nếu đo thấy có ích. Phần này chỉ đưa ra chốt khi D1 đo được:
- Mốc lịch đã xếp xong (`compose`) và mốc có câu trả lời của từng lượt lập lịch.
- Khoảng thẻ có thể hiện trước câu trả lời đạt tiêu chí ở plan §3.5.

Nếu chốt:
- **AC-AGT-09**, chèn trước câu "Khi xong, khung thu gọn…": "Lượt lập lịch chạy quá 5 giây mà lịch đã xếp xong thì thẻ
  các sản phẩm đã chọn hiện trước khi có lời tư vấn; các thẻ này chỉ để xem."
- **`user-flow.md` §4.2**, chèn trước câu "Xong thì khung thu gọn…": "Lập lịch quá 5 giây thì thẻ sản phẩm đã chọn hiện
  trước lời tư vấn."
- **`architecture.md` §3**, nối vào ý "Khung tiến trình": "Thẻ hiện trước lời tư vấn chỉ gồm sản phẩm của lịch `compose`
  đã dựng và đã kiểm nguồn."

## Thay đổi source sau khi chốt

Theo `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md`:
- Phần A (B2, B3, B4, B5, B7, B8):
  - Contract 1.27.0 (`src/shared/contracts/schemas/itinerary-agent.yaml`, `paths/itinerary-agent.yaml`): sự kiện
    `node.activity`, khoá `progress` của `node.completed`, fixture stream.
  - Backend: `src/backend/app/agents/steps/progress.py` (mới), `agents/graph.py`, `agents/state.py`,
    `api/v1/routes/assistant.py`. Bộ đếm tại chỗ lọc: `application/itinerary/retrieval.py`,
    `application/itinerary/flights.py`, `agents/steps/evaluation.py`, `agents/steps/jobs.py`, `agents/steps/fares.py`.
  - Frontend: `features/itinerary/widget/` (mô hình, nhãn, `WidgetProgress`, dòng tóm tắt, `WidgetChat`),
    `context/assistantState.ts`, `context/AssistantProvider.tsx`, `services/assistantStream.ts`,
    `components/common/DebugPanel.tsx`.
  - Spec: `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`,
    `docs/spec/product.md` §6.1, §6.6.
- Phần B (B9): khoá `debug` trong contract; collector chẩn đoán; `core/config.py`; `.env.example`; header ở
  `services/assistantStream.ts` và `DebugPanel.tsx`.
- Phần C (B6 và phần preview của B8): sự kiện `run.preview` trong contract; `progress.preview()`; thẻ xem trước trong
  `WidgetProgress`.

Chỉ làm cho luồng orchestrator, đã là luồng mặc định (`update-archive/2026-10-12-orchestrator-thanh-luong-chinh.md`).
