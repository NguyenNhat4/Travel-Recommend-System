# Chỉnh thiết kế: một orchestrator làm đầu mối hội thoại, code thực thi theo ý định

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Thay thế: `2026-10-12-de-xuat-orchestrator-kham-pha-llm.md` (nội dung đề xuất), `2026-10-12-plan-nho-ket-qua-da-xem.md`
  (phần thiết kế orchestrator–worker)
- Bị thay thế bởi: `2026-10-12-sua-plan-orchestrator-theo-review.md` (một phần: trả lời từ `already_shown`, đường tắt vé)

## Mục tiêu

Người dùng chọn thiết kế cho bản đầu, thay cho bản orchestrator–worker trong plan và đề xuất PRD đang chờ chốt:

- **Orchestrator** (một LLM) làm đầu mối hội thoại: hiểu câu, trả lời, hỏi lại, chuyển lập lịch hoặc yêu cầu thực thi.
- **Code** bảo đảm thực thi đúng phạm vi và trả dữ liệu đúng.

Viết lại plan và đề xuất theo hướng đó.

## File thay đổi

- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — sửa, viết lại:
  - phần đầu và bảng thứ tự;
  - mục 3 (sơ đồ);
  - 4.1 (mô tả lại đúng phần B2–B3 đã làm, bỏ thiết kế cũ của `shown`);
  - 4.2 (`OrchestratorTurn`, `Job`);
  - 4.3 (thực thi việc, rút gọn kết quả, mã `#n`);
  - 4.4 (gác cổng, luật lặp theo ý định);
  - 4.5 (vòng lặp, phanh, đường tắt vé);
  - 4.6–4.7;
  - 4.8 mới (hành vi mong đợi);
  - mục 5 (B4–B11), 6, 7, 8.
- `docs/prd/update/2026-10-12-orchestrator-va-kham-pha-llm.md` — sửa: viết lại nội dung đề xuất theo thiết kế mới; thêm
  mục 4 (model riêng cho orchestrator, biến môi trường); giữ trạng thái `chờ chốt`.
- `history/2026-10-12-de-xuat-orchestrator-kham-pha-llm.md`, `history/2026-10-12-plan-nho-ket-qua-da-xem.md` — sửa: chỉ
  thêm dòng `Bị thay thế bởi`.

## Quyết định

Theo lựa chọn của người dùng (2026-10-12):

- **Bỏ worker `converse`.** Orchestrator tự trò chuyện, giải thích khả năng, trả lời từ `already_shown`. Mỗi vòng nó trả
  đúng một hành động `answer | ask | plan | execute`, không bắt mọi tin sinh danh sách 1–3 việc.
- **`explore` là nhóm tool do code thực thi theo việc có cấu trúc,** không có LLM riêng ở bản đầu. Chỉ tách thành agent
  khi phần khám phá đủ phức tạp hoặc ngữ cảnh quá lớn. `fare` trả dữ liệu đã tính và `fare_block`.
- **Rút gọn kết quả tool:**
  - code giữ bản đầy đủ; orchestrator nhận `#n` + dữ kiện, có trần số mục và độ dài, kèm `has_more` / `next_page`;
  - mã của kết quả vừa tìm chưa có nghĩa là đã xem; chỉ vào `shown` khi có trong response cuối, ở `finalize`.
- **Vé do code viết:** `fare_block` chèn nguyên văn. Orchestrator viết phần dẫn; code kiểm khối được chèn đủ. Đường tắt:
  chỉ một việc `fare` thì trả như hiện tại, không thêm lời gọi LLM.
- **Giữ `narrate`:** nhánh lập lịch giữ nguyên. Orchestrator chỉ quyết chuyển vào nhánh, không viết lại lời lịch trình.
- **Việc thực thi có trường có cấu trúc:** `intent` (`new | more | about_shown | cheaper | dearer`), `refers_to`, phạm vi
  và điều kiện tìm.
- **Luật lặp theo ý định, không theo `shown`** (người dùng chỉnh):
  - `new` được gặp lại nơi đã xem;
  - `more` loại thẻ đã xem trong cùng phạm vi;
  - `about_shown` chỉ đúng các thẻ được nhắc;
  - `cheaper`/`dearer` so với mốc giá của thẻ đang nói và giữ các điều kiện người dùng chưa đổi (code lưu `via`, tức điều
    kiện đã sinh ra thẻ).
- **Một cờ duy nhất** `ITINERARY_ORCHESTRATOR`; bỏ `ITINERARY_EXPLORE_MODE`.
- **Model riêng cho orchestrator:** người dùng chọn GPT-6.1 Sol (OpenAI, ra mắt 29/09/2026).
  - Cấu hình bằng `ITINERARY_ORCHESTRATOR_MODEL` / `_PROVIDER` / `_REASONING_EFFORT`; bỏ trống thì dùng model chung.
  - Các node khác giữ model nhanh hiện tại.
  - Model ra sau mốc kiến thức của agent, nên model ID, tham số hỗ trợ và độ trễ phải kiểm ở B7 và đo ở B12.
  - Đề xuất PRD thêm mục 4 và `deployment-plan.md` §2 (ba biến mới).

## Kiểm tra

- Không có. Chỉ có tài liệu.

## Còn lại / rủi ro

- **Dừng chờ người dùng chốt đề xuất**, kèm 4 điểm:
  - số thẻ;
  - phạm vi "đã xem" khi muốn thêm;
  - số việc mỗi vòng;
  - số vòng thực thi.

  Chưa chốt thì không làm B5–B10.
- Lượt khám phá vẫn hai lời gọi LLM như hiện nay. Thứ tự payload của prompt orchestrator phải đo lại như B3.
