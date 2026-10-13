# Cập nhật PRD theo các đề xuất đã chốt, bỏ giá minh hoạ khi so vé, chat thử lần 3

- Ngày: 2026-10-11
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, agent, frontend, evaluation

## Mục tiêu

Phần sau của task `history/2026-10-11-tu-van-ve-may-bay-va-sua-loi-chat-thu-lan-3.md`.
- Người dùng giao: "về phần technical PRD mình cho bạn quyết định mọi thứ xong update docs cho mình".
- Áp dụng vào PRD các đề xuất đã chốt mà PRD chưa có, chốt nốt phần còn treo, ghi đề xuất cho đợt sửa 11/10.
- Chạy lại hội thoại thật để kiểm, và sửa các lỗi chạy lại phát hiện.

Phục vụ FR-AGT-01, FR-AGT-05, FR-AGT-06, FR-AGT-07, NFR-REL-01, NFR-SEC-04.

## File thay đổi

PRD:
- `docs/prd/requirements.md` — sửa:
  - FR-AGT-01: khám phá trước, lập lịch khi người dùng đồng ý.
  - FR-AGT-05: hỏi vé sau khi có lịch.
  - Thêm FR-AGT-06 và FR-AGT-07.
  - Sửa AC-AGT-01 và AC-AGT-02; thêm AC-AGT-05 đến AC-AGT-08.
  - NFR-SEC-04: luật "gõ bậy" chỉ xét tin đầu của hội thoại.
- `docs/prd/architecture.md` — sửa §3:
  - nhánh `Explore` và luật đồng ý;
  - `SuggestForm` khi xin form;
  - grounding của câu trả lời vé;
  - response 1.24.0 và 1.25.0.
- `docs/prd/user-flow.md` — sửa:
  - §3.2: nhánh đồng ý lập lịch, khám phá, hỏi vé;
  - §4.2: thẻ khám phá, hàng thẻ ngày–giá, nút gợi ý (kể cả `COMPLETED`), form chỉ sau khi đồng ý hoặc khi xin.
- `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` → `docs/prd/update-archive/` — đổi tên và sửa:
  - đã áp dụng vào PRD;
  - giữ dòng chốt của Nguyễn Minh Nhật 10/10, thêm dòng chốt uỷ quyền 11/10.
- `docs/prd/update/2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich.md` → `docs/prd/update-archive/` — đổi tên và sửa:
  - **Duyệt:** hỏi vé sau khi có lịch trả lời bằng luật, lịch giữ nguyên; câu đổi đi luồng đổi hiện có.
  - **Từ chối:** node `follow_up`, trả lời từ dữ liệu đã lưu, đổi một món không lập lại lịch. Luồng hiện có đã đáp ứng.
- `docs/prd/update-archive/2026-10-11-tu-van-ve-may-bay-va-sua-loi-chat-thu-lan-3.md` — thêm:
  - đề xuất cho FR-AGT-07, AC-AGT-08, các bổ sung FR-AGT-06 và contract 1.25.0;
  - trạng thái "đã áp dụng" (agent chốt theo uỷ quyền);
  - gồm cả quyết định về giá minh hoạ ở dưới.

Sửa sau chat thử lần 3:
- `src/backend/app/agents/steps/fares.py` — sửa:
  - `_one_way` chỉ dùng chuyến giá minh hoạ (`attributes.simulated`) khi tuyến không còn chuyến giá thật;
  - `_flight_text` ghi hạng ghế khác Phổ thông;
  - `why_text` nêu khác hạng ghế và giá minh hoạ;
  - nút khách sạn ở câu trả lời chiều về dùng điểm đến của chuyến.
- `src/backend/app/agents/steps/messages.py` — sửa: `fare_why_no_reason` (dữ liệu có hạng ghế), thêm `fare_why_cabin`, `fare_why_simulated`, `fare_cabin` (vi, en).
- `src/backend/app/domain/itinerary/planning.py` — sửa: `cabinClass`, `simulated` vào thuộc tính tóm tắt sản phẩm (để thẻ vé ghi được).
- `src/backend/tests/unit/agents/test_fares_followups.py`, `test_fares_messy.py` — sửa: test bỏ giá minh hoạ, hạng ghế trong "tại sao đắt", nút khách sạn chiều về.
- `src/frontend/src/features/itinerary/widget/WidgetFareDays.tsx` — sửa: thẻ ghi "Thương gia · giá minh hoạ".
- `src/frontend/tests/unit/widgetNarration.test.tsx` — sửa: test hạng ghế trên thẻ.
- `docs/spec/agent/langgraph-nodes.md` — sửa: giá minh hoạ và hạng ghế trong nhánh vé.
- `src/evaluation/reports/eval-2026-10-11-chat-thu-lan-3.md` — thêm: báo cáo chat thử lần 3 (R01–R08, M01–M16), bảng Tốt/Tạm/Lỗi, toàn văn.

## Quyết định

- **Không đưa "chỉ tiếng Việt" (tạm thời) vào PRD.** Đề xuất gợi ý trước khi lập lịch giữ nó là quyết định tạm thời.
- **AC-AGT-06 vẫn ghi mức "dưới 3 giây".**
  - Lượt khám phá đo được 3,7–7,1 giây.
  - Người dùng nói mức latency của BRD/PRD chỉ là gợi ý (11/10).
  - Có nới mức này hay không là việc còn mở, xem dưới.
- **Giá minh hoạ.** Catalog có 797/1.707 chuyến hạng Thương gia giá mô phỏng.
  - So chung với giá thật thì "đắt nhất" luôn là vé mô phỏng: chat thử ra 2.385.000 ₫, còn người dùng trước đó thấy 13.590.000 ₫.
  - Vì vậy chỉ tính giá mô phỏng khi tuyến không còn giá thật. Khi có, ghi rõ hạng ghế và "giá minh hoạ".
  - Đây cũng là câu trả lời có dữ liệu cho "tại sao đắt".

## Kiểm tra

- `pytest src/backend/tests/unit src/backend/tests/contract` (bỏ `ITINERARY_LLM_REASONING_EFFORT`, `AUTH_REDIS_URL` của container), chạy sau khi sửa giá minh hoạ: 2768 passed, 2 skipped.
- Sau khi sửa nút chiều về và thêm test:
  - `pytest src/backend/tests/unit/agents`: 581 passed;
  - `test_fares_followups.py`: 15 passed.
- `npx vitest run tests/unit/widgetNarration.test.tsx`: 15 passed. `npx tsc --noEmit -p .`: sạch.
- `validate_contract.py`: PASS (120 schemas, 96 fixtures).
- Hội thoại thật (`chat_replay`, backend local, LLM thật), chi tiết trong báo cáo:
  - R01–R08: 7 Tốt, 1 Tốt/Tạm.
  - M01–M16: 13 Tốt, 3 Tạm.
  - R02 chạy lại sau khi sửa giá minh hoạ: "Đắt nhất thì sao?" → 900.000 ₫ (vé thật). "Tại sao đắt" → cao hơn 43% vé rẻ nhất, 3% giá phổ biến.

## Còn lại / rủi ro

- AC-AGT-06 "dưới 3 giây" chưa khớp số đo; cần người dùng quyết nới hay bỏ.
- M11: câu "có chuyến nào rẻ hơn ko" ngay sau "chuyến bay về mấy giờ" lặp lại cùng câu trả lời.
- R04: nơi không có trong catalog ("chùa trấn quốc") được gợi ý theo thành phố của lượt trước (Huế), dù nơi đó ở Hà Nội.
- `docs/prd/user-flow.md`:
  - sơ đồ §3.2 dùng lại id nút `H` hai lần;
  - tiêu đề §4.3/§4.4 bị lặp.

  Cả hai có từ trước, chưa sửa.
- Search vẫn chưa lọc khách sạn theo ngày đi (việc 5 của plan 10/10).
