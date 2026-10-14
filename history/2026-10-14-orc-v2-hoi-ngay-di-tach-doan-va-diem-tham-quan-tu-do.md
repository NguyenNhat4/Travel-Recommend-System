# Orc v2: hỏi ngày đi thay vì phác lịch bằng chữ, tách đoạn theo sản phẩm, điểm tham quan tự do

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, evaluation, docs
- Mã FR/NFR: FR-AGT-01, FR-AGT-03, FR-AGT-06; AC-AGT-01, AC-AGT-07

## Mục tiêu

Người dùng gửi ảnh web local (v2): "gợi ý lịch trình 3 ngày 2 đêm ở đà nẵng phù hợp cặp đôi khách sạn nào được yêu
thích nhất" ra một đoạn chữ "Ngày đầu… ngày thứ hai…" kèm thẻ xếp thành danh sách cuối câu trả lời, không có lịch.
Điểm không bán vé (biển, cầu, bán đảo) bị nói như vé, kèm câu "giả định miễn phí, chưa xác minh" lặp ở từng điểm.

## Bằng chứng nguyên nhân

- Log `.logs/web-demo.log` lượt 23:44 (13/10): orc chỉ gọi `find_products` ×2 rồi `respond`; lượt 23:46 có "ngày mai
  đi" thì gọi `plan_itinerary` và ra lịch. Không có trace LangSmith cho khung giờ này.
- Gửi lại đúng câu tới backend v2 local (model thật) 2/2 lần: `turnKind=answer`, `itinerary=null`, lời đáp phác lịch theo
  ngày bằng chữ, toàn bộ trong một dòng nên widget (đặt thẻ sau dòng đầu nhắc sản phẩm) dồn mọi thẻ xuống cuối.
- Không phải lỗi tool: thiếu ngày đi nên `plan_itinerary` không chạy được; AC-AGT-01 yêu cầu hỏi gộp một câu nhưng orc
  tự phác lịch. Prompt chỉ coi "lập lịch/lên lịch" là đồng ý, chưa có "gợi ý lịch trình".
- Khung chi tiết dùng `TaxonomyBadge` theo taxonomy nên ghi "Vé tham quan" cả cho điểm tham quan tự do.

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa `PROMPT`: "xin/gợi ý lịch trình" là đồng ý; "cặp đôi" là 2 người lớn; thiếu
  trường bắt buộc thì `clarification` một câu, không phác lịch bằng chữ; mỗi sản phẩm một đoạn; fact phải có chữ đi kèm;
  điểm free/assumed_free giới thiệu là điểm tham quan tự do, không lặp câu phí giả định (code thêm một câu chung).
- `src/backend/app/application/itinerary/v2_final.py` — sửa `_join`: xuống đoạn sau câu chứa sản phẩm và trước sản phẩm
  đứng đầu câu, để thẻ đứng ngay sau câu nhắc nó (AC-AGT-07).
- `src/backend/tests/unit/application/test_assistant_v2_final.py` — thêm 3 test tách đoạn.
- `src/frontend/src/components/common/TaxonomyBadge.tsx` — sửa: prop `freeToVisit` → nhãn "Điểm tham quan".
- `src/frontend/src/features/itinerary/widget/WidgetProductDetail.tsx` — sửa: truyền `freeToVisit` vào nhãn.
- `src/frontend/tests/unit/widgetProductDetail.test.tsx` — sửa: kiểm nhãn "Điểm tham quan"/"Vé tham quan".
- `src/evaluation/agent/assistant_v2_cases.py` — thêm ca `plan-no-date` (file đã bẩn từ phiên trước; chỉ thêm ca này).
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa §4.7: tách đoạn, thiếu ngày đi, điểm tham quan tự do.

## Quyết định

- Không lệch PRD: AC-AGT-01 đã yêu cầu hỏi gộp một câu khi thiếu ngày đi; AC-AGT-07 đã yêu cầu thẻ đứng sau câu đầu
  nhắc nó. Giữ cảnh báo `FREE_ENTRY_ASSUMED` theo đề xuất đã chốt `update-archive/2026-10-13-tham-quan-tu-do-trong-bo-loc-v2.md`
  (chỉ bỏ phần lặp trong lời orc), không nói "miễn phí đã xác minh".
- Hiểu câu sửa bằng prompt; code chỉ định dạng (tách đoạn theo dấu câu/chữ hoa), không đoán ý.
- Chưa làm: nút "Điền thông tin chuyến đi" cho v2 — contract v2 chưa có dữ liệu điền sẵn form; cần thay đổi contract riêng.
- Không làm phần lệch PRD người dùng chưa chốt: lập lịch khi chưa có ngày đi; nói thẳng "miễn phí" bỏ cảnh báo.

## Kiểm tra

- Model thật, backend tạm cổng 8001 (`ITINERARY_DATA_MODE=inprocess`, Postgres/Weaviate local), đã dừng sau khi đo:
  - Bản prompt mới, câu trong ảnh ×3: 3/3 `clarification`, hỏi ngày đi, không phác lịch theo ngày; điểm tự do nói "ghé
    thăm tự do", một câu lưu ý chung.
  - Hội thoại 2 lượt (câu trong ảnh → "ngày mai đi") ×3: lượt 1 3/3 hỏi ngày đi; lượt 2 3/3 `itinerary`/`replace`.
    Lời đáp đã tách đoạn theo câu chứa sản phẩm; 1/3 vẫn còn một đoạn dài do orc tách dấu chấm thành mảnh riêng — đã
    sửa thêm trường hợp này bằng test, chưa đo lại bằng model thật. 1/3 lượt 2 orc vẫn viết "phí vào cửa… là giả định".
- `pytest src/backend/tests/unit/agents src/backend/tests/unit/domain src/backend/tests/unit/application
  src/backend/tests/architecture src/backend/tests/contract/test_assistant_v2_contract.py`: 2647 passed, 3 xfailed.
- Frontend `vitest run`: 89 file, 936 passed; `tsc --noEmit`: pass.
- `git diff --check` trên file đã sửa: pass. Ruff không có trong môi trường, chưa chạy.
- Không đổi contract nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Orc đôi khi đặt nhiều sản phẩm liền nhau không có câu dẫn ("[A] [B] [C]") ở lượt lịch trình; chưa sửa.
- Nút điền form cho v2 (AC-AGT-01) cần thay đổi contract v2.
