# Đề xuất: gợi ý range 1–7 ngày rồi lấy số ngày mặc định khi người dùng không chốt

- Ngày: 2026-09-29
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Bị thay thế bởi: `2026-09-29-de-xuat-form-goi-y-thong-tin-chuyen-di.md`

## Mục tiêu

Người dùng gửi ảnh chụp widget trợ lý: trả lời "bao nhiêu ngày cũng được" ba lần, trợ lý hỏi lại đúng một câu ba lần — hội thoại kẹt
vòng vì `days` là bắt buộc và không có giới hạn số lần hỏi. Yêu cầu: lượt hỏi đầu gợi ý khoảng 1–7 ngày; lượt sau vẫn không có con số
thì tự chọn mặc định, **nói rõ đã chọn giá trị nào** và **muốn đổi thì phải nêu giá trị cụ thể**.

Đây là thay đổi hành vi lệch PRD (AC-AGT-01, sơ đồ `architecture.md` §3 đang ghi thiếu số ngày là hỏi lại vô điều kiện), nên theo
`AGENTS.md` mục 8: viết đề xuất, **chưa sửa source**, chờ người dùng chốt. Phục vụ FR-AGT-01, FR-AGT-03.

## File thay đổi

- `docs/prd/update/2026-09-29-so-ngay-mac-dinh-khi-nguoi-dung-khong-chot.md` — thêm: đề xuất, trạng thái `chờ chốt`.
- `history/2026-09-29-de-xuat-so-ngay-mac-dinh.md` — thêm: entry này.

## Quyết định

- Mặc định **1 ngày** (người dùng chọn, thay vì 3 ngày khớp AC-AGT-01).
- Tối đa **hai** lượt hỏi về số ngày mỗi hội thoại, đếm bằng `days_prompts` trong state.
- Phạm vi chỉ `days`. `destination` không có mặc định — lập lịch cho thành phố người dùng chưa từng nhắc là sai nặng hơn hỏi thêm
  một lượt. `startDate` đã có đề xuất riêng `update/2026-09-25-goi-y-ngay-hom-nay-khi-chua-chot-ngay-di.md` (vẫn chờ chốt), cùng khuôn
  "gợi ý → mặc định có thông báo" nhưng không gộp.
- Câu chữ do **LLM** viết (người dùng chọn); ràng buộc "phải nêu range 1–7" và "phải báo giá trị mặc định + cách đổi" đặt trong prompt,
  và cũng phải có trong câu cố định dự phòng để LLM lỗi vẫn báo đúng.
- Contract không đổi: `missingFields`, `suggestedValues.days = [1..7]` giữ nguyên.

## Kiểm tra

- Chưa chạy lệnh nào: thay đổi chỉ là tài liệu, chưa chạm `src/`, `db/` hay contract.
- Đã đọc trước khi viết: `AGENTS.md`, `docs/prd/README.md`, `docs/prd/requirements.md` (§1.4 FR-AGT, §3 AC-AGT-01),
  `docs/prd/architecture.md` §3, `docs/prd/update/` (cả hai đề xuất đang chờ chốt), `history/README.md`,
  `history/2026-09-25-tach-classify-extract-hoi-chi-tiet-chuyen-di.md`, `src/backend/app/agents/steps/classification.py`,
  `conversation.py`, `messages.py`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §4.3, `docs/spec/agent/state-fields.md`,
  `langgraph-nodes.md`, `field-review.md`.

## Còn lại / rủi ro

- **Chờ người dùng chốt đề xuất.** Chốt rồi mới cập nhật `docs/prd/` (AC-AGT-01, sơ đồ §3), rồi mới sửa `src/backend/app/agents/*`,
  golden dataset và spec theo danh sách trong đề xuất.
- Lịch 1 ngày mỏng hơn lịch 3 ngày, dễ ít sản phẩm; cần theo dõi khi chạy golden thật.
- Rủi ro LLM không nói ra giá trị mặc định — phải có case golden `textInclude` chặn.
