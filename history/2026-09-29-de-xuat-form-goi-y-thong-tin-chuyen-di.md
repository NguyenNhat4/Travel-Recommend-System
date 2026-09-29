# Đề xuất: form gợi ý thông tin chuyến đi thay cho hỏi lại bằng câu chữ

- Ngày: 2026-09-29
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Phạm vi: docs, agent, contract, frontend
- Thay thế: `2026-09-29-de-xuat-so-ngay-mac-dinh.md`

## Mục tiêu

Người dùng đổi hướng so với bản nháp sáng nay (chỉ lấy mặc định `days` ngầm): sau **một** lượt người dùng trả lời mà vẫn không rõ,
trợ lý hiển thị ngay trong khung chat một **form đã điền sẵn giá trị gợi ý cho mọi trường bắt buộc** kèm câu mời tinh chỉnh; form có
giới hạn (số ngày ≤ 7, ngày khởi hành không trước hôm nay); bấm xác nhận thì dựng một prompt hoàn chỉnh từ form và lập lịch.

Lệch PRD (AC-AGT-01, sơ đồ `architecture.md` §3, wireframe `user-flow.md` §4.2) và cần thêm field contract, nên theo `AGENTS.md`
mục 8 và mục 3: viết đề xuất, **chưa sửa source**, chờ chốt. Phục vụ FR-AGT-01, FR-AGT-03, FR-AGT-05.

## File thay đổi

- `docs/prd/update/2026-09-29-so-ngay-mac-dinh-khi-nguoi-dung-khong-chot.md` — đổi tên thành
  `docs/prd/update/2026-09-29-form-goi-y-thong-tin-chuyen-di.md` và viết lại toàn bộ theo hướng form.
- `history/2026-09-29-de-xuat-form-goi-y-thong-tin-chuyen-di.md` — thêm: entry này.

## Quyết định

- Ngưỡng hiện form: đếm `clarification_rounds` theo hội thoại; lượt 1 hỏi bằng câu chữ, từ lượt 2 trả form.
- Form phủ mọi trường bắt buộc (`destination`, `days`, `startDate`, `party`, `budget`), không chỉ `days` như bản nháp cũ.
- Giá trị điền sẵn: `destination` từ `supported_destinations` (catalog, không do LLM bịa), `days` = 1, `startDate` = hôm nay giờ VN,
  `party` = 2 người lớn, `budget` để trống.
- Xác nhận form → dựng **message** hoàn chỉnh (mẫu `tripStarterMessage()`), không dùng `intentOverride`, vì `intentOverride` là chip
  sửa từng field và đang bị loại khỏi luật hỏi chi tiết (`classification.py:174`).
- Contract: thêm field **tuỳ chọn** `clarificationForm` vào `ItineraryNeedsClarification` — tương thích ngược, giữ v1; `suggestedValues`
  không đổi.
- Ràng buộc `startDate` ≥ hôm nay chỉ áp cho giá trị đến từ form; câu chat tự do giữ hành vi cũ (spec hiện ghi ngày quá khứ không bị
  từ chối) để không phá golden case đang có.
- Ghi nhận từ khảo sát code: widget nổi hiện **không** render gì cho `NEEDS_CLARIFICATION` ngoài `question` dạng text
  (`useFloatingWidget.ts:62-88`, `WidgetChat.tsx:22-30`) — đây là phần việc FE lớn nhất, vì chính widget là nơi người dùng gặp kẹt vòng.

## Kiểm tra

- Chưa chạy lệnh nào: mới là tài liệu, chưa chạm `src/`, `db/` hay contract.
- Khảo sát trước khi viết (đọc, không sửa): `src/shared/contracts/schemas/itinerary-agent.yaml` (`ItineraryRequest`, `TripIntent`,
  `TripIntentPatch`, `ItineraryNeedsClarification`), `src/backend/app/agents/steps/classification.py`, `conversation.py`, `nodes.py`,
  `state.py`, `src/backend/app/application/itinerary/contracts.py`, `src/frontend/src/components/assistant/*`,
  `src/frontend/src/features/itinerary/widget/*`, `src/frontend/src/context/AssistantProvider.tsx`,
  `docs/prd/requirements.md`, `architecture.md` §3, `user-flow.md` §4.2, `docs/prd/update/` (3 đề xuất chờ chốt), `history/README.md`.

## Còn lại / rủi ro

- **Chờ người dùng chốt đề xuất.** Chốt rồi mới: cập nhật `docs/prd/`, sửa contract, sinh lại `api.gen.ts`, rồi mới code BE/FE.
- Đề xuất `2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` vẫn chờ chốt và chồng lấn phần `startDate`; chốt đề xuất form thì
  nên xử lý (áp dụng hoặc từ chối) đề xuất kia cùng lúc để hai quy tắc ngày đi không đá nhau.
- Rủi ro người dùng bấm xác nhận nguyên giá trị gợi ý và nhận lịch cho điểm đến mình không chủ động chọn.
