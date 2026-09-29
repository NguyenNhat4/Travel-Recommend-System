# Hỏi ngày đi trước khi lập lịch trình

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, contract, frontend, evaluation, docs
- Thay thế: 2026-09-25-khong-luu-vertical-bi-loai-va-de-xuat-hoi-ngay-di.md (phần hỏi ngày đi)

## Mục tiêu

Người dùng chốt đề xuất `docs/prd/update-archive/2026-09-25-hoi-ngay-di-truoc-khi-lap-lich.md` (chốt kèm yêu cầu sửa golden dataset): khi người dùng không nói ngày đi thì đi qua `clarify` để hỏi ngày đi, thay vì để LLM tự điền ngày hôm nay (lỗi "1 ngày thôi" ra FALLBACK vì khách sạn không mở bán vào ngày đó). Phục vụ FR-AGT-01, FR-AGT-03, AC-AGT-01.

Mục "sửa lỗi 1" (vertical Recommendation bỏ không lưu sang lượt sau) làm trong cùng đợt; xem entry tiền nhiệm.

## File thay đổi

- `docs/prd/requirements.md` — sửa: AC-AGT-01 mô tả trợ lý hỏi ngày đi một lần rồi mới lập lịch.
- `docs/prd/update-archive/2026-09-25-hoi-ngay-di-truoc-khi-lap-lich.md` — thêm (đề xuất, trạng thái `đã áp dụng`, đã lưu trữ).
- `src/shared/contracts/schemas/itinerary-agent.yaml` — sửa: thêm `startDate` vào enum `ItineraryNeedsClarification.missingFields` (thêm, không phá vỡ).
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract (`missingFields` có thêm `startDate`).
- `src/backend/app/agents/state.py`, `models.py` — sửa: field `start_date_asked`; `Extraction.start_date_undecided`.
- `src/backend/app/agents/steps/classification.py` — sửa: mốc `today` gửi cho LLM là ngày theo giờ Việt Nam (`vietnam_today`, UTC+7), không còn `date.today()` theo giờ máy chạy backend; đủ điểm đến + số ngày, chưa có ngày, chưa hỏi, không phải chip sửa tay thì `route=missing_info`, `missing_fields=["startDate"]`.
- `src/backend/app/agents/steps/prompts.py`, `messages.py`, `conversation.py` — sửa: prompt cấm tự điền `startDate` và nhận biết "chưa chốt ngày"; câu hỏi vi/en; câu cố định khi LLM lỗi.
- `src/backend/app/agents/nodes.py` — sửa: `start_date_asked` được khôi phục ở `intake` và lưu ở `finalize` theo hội thoại; docstring `evaluate`.
- `src/backend/app/agents/steps/evaluation.py` — sửa: vertical Recommendation bỏ chỉ lọc lượt hiện tại, không ghi vào `constraints`.
- `src/backend/tests/unit/agents/test_classify.py`, `test_itinerary_runtime.py`, `tests/contract/test_assistant_contract.py` — sửa: fixture mặc định đặt `start_date_undecided=True`; thêm test hỏi ngày (6 test ở `classify`, 2 test qua graph) và test không lưu vertical bị loại.
- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: 41 case nhóm khác chèn lượt hỏi ngày + lượt trả lời "chưa chốt ngày đi" (kỳ vọng kết quả dời sang lượt trả lời; đánh số lại `excludeProductsFromTurn`); 12 case `clear_request` (G-001..G-012 trừ G-005, và G-051) thêm ngày đi vào chính câu bằng placeholder (`{today+N}`) và kiểm `intent.startDate` chính xác, vẫn một lượt; G-005 giữ "từ ngày mai"; giữ nguyên 75 case (không thêm case mới theo yêu cầu của người dùng).
- `src/evaluation/agent/golden.py` — sửa: `--sweep` thêm lượt "chưa chốt ngày đi"; thêm `resolve_dates` thay placeholder ngày (`{today+N}`, `{today+N:iso}`) trong `message` và `expect` lúc chạy, theo `vietnam_today()`.
- `src/evaluation/tests/test_golden.py` — sửa: thêm test mọi lượt hỏi ngày không gọi tool và có ít nhất 40 case hỏi ngày (số case vẫn 75); test `clear_request` dùng placeholder và kiểm `startDate`; test mọi placeholder được thay; 5 test cho `resolve_dates`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/agent/state-fields.md`, `field-review.md`, `langgraph-nodes.md`, `golden-dataset-how-to-add-more-case.md`, `golden-run.md`, `evaluation-plan.md`, `README.md` — sửa: quy tắc hỏi ngày, field mới, số case/lượt golden.
- `history/2026-09-25-khong-luu-vertical-bi-loai-va-de-xuat-hoi-ngay-di.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.

## Quyết định

- Hỏi ngày ở `classify` (không ở `tool`) để đi qua đúng node `clarify` như người dùng yêu cầu và giữ nguyên đồ thị. Hệ quả đã biết: điểm đến ngoài catalog ("Paris 2 ngày") cũng bị hỏi ngày trước rồi mới nhận 422. Muốn tránh thì phải hỏi ngày sau khi kiểm tra điểm đến (ở `tool`), đổi routing và ngữ nghĩa "tool không chạy khi còn thiếu field" của golden.
- Mốc `today` theo UTC+7 cố định thay vì `zoneinfo`: Việt Nam không có giờ mùa hè và không phụ thuộc gói `tzdata` trên image Docker nhỏ. LLM vẫn tự tính "ngày mai", "tuần sau" từ mốc đó; backend không kiểm tra lại giá trị.
- Chỉ hỏi một lần mỗi hội thoại (`start_date_asked` lưu trong store); "chưa chốt/linh hoạt" tính là đã trả lời, lập lịch với `startDate = null` (không lọc theo ngày).
- Không có luật code chặn LLM điền `startDate` sai; chỉ có prompt. Nếu LLM vẫn tự điền ngày thì không bị hỏi và vẫn lọc theo ngày đó; cần theo dõi bằng golden (các case chèn lượt và nhóm `clear_request`).
- Golden: nhóm `clear_request` là yêu cầu đầy đủ nên nêu ngày đi trong câu (theo góp ý của người dùng: "thêm ngày đi vào chúng"), dùng placeholder ngày (`{today+N}`) do runner thay lúc chạy thay cho cách nói tương đối, vì "tuần sau" không có một đáp án đúng duy nhất nên không kiểm được ngày đã trích, còn ngày cứng thì cũ đi và có thể ra ngoài cửa sổ đặt chỗ của catalog. Hệ quả: câu gửi cho agent là ngày tường minh dạng dd/mm/yyyy, nên các case này không kiểm được khả năng hiểu "ngày mai", "tuần sau" (chỉ G-005 còn kiểm). Các nhóm còn lại chèn lượt trả lời "chưa chốt ngày đi", để giữ nguyên câu người dùng thật và không bị lọc theo cửa sổ mở bán của catalog. Rủi ro: cửa sổ mở bán khách sạn hiện rất hẹp nên các case `clear_request` có ngày có thể ra `FALLBACK` (đã nằm trong `status` cho phép, trừ G-051 chỉ cho `COMPLETED`).
- Slide 11–12 và kịch bản vẫn ghi số liệu golden cũ (75 case, commit 601f112) vì đó là kết quả của lần chạy đó; chạy golden mới thì cập nhật.
- Không có case riêng cho "trả lời một ngày cụ thể sau khi bị hỏi", "chưa chốt ngày ngay câu đầu" và "hỏi ngày bằng tiếng Anh" như đã định (G-076..G-080 bị bỏ để giữ 75 case). Ba tình huống này chỉ được phủ gián tiếp: nêu ngày ở câu đầu (G-001..G-012, G-005, G-055), hỏi ngày rồi trả lời "chưa chốt" (41 case), hỏi ngày tiếng Anh (G-062); phần "chỉ hỏi một lần" có unit test ở backend.

## Kiểm tra

- `pytest src/backend/tests/unit/agents src/backend/tests/contract src/backend/tests/architecture`: 161 passed (chạy lại sau khi đổi `vietnam_today`, gồm 2 test mới cho múi giờ).
- `validate_contract.py`: PASS. `npm run generate:api-types` rồi `npx tsc --noEmit`: pass.
- `load_dataset` nạp được dataset mới: 75 case, 130 lượt, 41 case có lượt hỏi ngày.
- `pytest src/evaluation/tests/test_golden.py`: 50 passed. Người dùng dặn bỏ test evaluation ở lượt trước; tôi chỉ chạy lại đúng file này sau khi sửa `golden.py` vì nó không gọi LLM hay database. **Chưa chạy** golden thật (cần LLM và catalog, tốn phí), nên chưa biết agent đạt các kỳ vọng mới bao nhiêu.
- Chưa chạy unit test và E2E của frontend sau khi sinh lại `api.gen.ts`.

## Còn lại / rủi ro

- Chạy golden thật để đo, đặc biệt 41 case đã chèn lượt (LLM phải nhận "chưa chốt ngày đi" là đã trả lời) và 12 case `clear_request` (LLM phải hiểu "từ ngày mai", "tuần sau").
- Web hiện không có chip cho `startDate`; người dùng gõ câu trả lời.
- Việc còn lại ngoài phạm vi: `itinerary.title` chưa được điền; cửa sổ mở bán khách sạn Hà Nội 15–16/10 cần báo team Data; `excludedVerticals` theo chuyến ở thành phố khác (RecSys).

Bị thay thế bởi: 2026-09-25-rut-gon-golden-14-case.md (phần golden dataset: số case, cách nêu ngày đi)
