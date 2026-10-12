# Đề xuất PRD: orchestrator dạng vòng lặp và lượt khám phá do LLM dẫn

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Bị thay thế bởi: `2026-10-12-chinh-thiet-ke-orchestrator.md`

## Mục tiêu

Bước B4 của plan `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`. B5–B10 lệch PRD:

- `architecture.md` §3: `ClassifyTurn` một nhánh; "lý do chọn thẻ do code tính".
- AC-AGT-06: kịch bản cố định.

Theo AGENTS.md §8, phải có đề xuất đã chốt trước khi sửa source.

## File thay đổi

- `docs/prd/update/2026-10-12-orchestrator-va-kham-pha-llm.md` — thêm: đề xuất, trạng thái `chờ chốt`. Gồm:
  - FR-AGT-06 thêm một gạch đầu dòng: nhớ đã gợi ý gì, tự quyết tìm gì, tin nhiều việc được trả lời đủ;
  - AC-AGT-06 viết lại thành nguyên tắc kiểm được;
  - `architecture.md` §3: orchestrator dạng vòng lặp, explore do LLM dẫn, gác cổng;
  - ba điểm cần chốt kèm: số thẻ, phạm vi "đã xem", số việc mỗi tin.

## Quyết định

- Nội dung lấy từ mục 6 của plan. Các câu hỏi ở mục 8 đưa vào đề xuất thành mục "Cần chốt kèm", mỗi câu kèm phương án đề
  xuất. Lần trước người dùng đã từ chối trả lời các câu này qua hộp hỏi riêng.
- Số thẻ đề xuất theo ý người dùng đã nêu ("tối đa 3 điểm tham quan"): tối đa 3 điểm tham quan hoặc tour; 2 khách sạn khi
  hỏi chung, 4 khi hỏi riêng chỗ ở.
- Mọi code mới nằm sau cờ, mặc định giữ hành vi cũ tới khi bộ đo (B12) đạt ngưỡng.

## Kiểm tra

- Không có. Chỉ có tài liệu.

## Còn lại / rủi ro

- **Người dùng gửi hướng chỉnh thiết kế** (cùng ngày, sau khi đề xuất được tạo), so với đề xuất hiện tại:
  - một orchestrator làm đầu mối hội thoại;
  - bỏ worker `converse`;
  - mỗi vòng orchestrator chỉ trả lời, hỏi lại hoặc yêu cầu thực thi, không bắt buộc 1–3 task;
  - bản đầu, `explore` là nhóm tool do orchestrator gọi trực tiếp, chưa có LLM riêng;
  - `fare` trả dữ liệu đã tính;
  - lập lịch giữ workflow hiện tại;
  - code giữ gác cổng và các phép tính.

  Đề xuất và plan (mục 3–5) cần viết lại theo hướng này **trước khi chốt**. Chưa sửa, chờ người dùng xác nhận.
- **Dừng chờ người dùng chốt.** Chưa chốt thì không làm B5–B10.
- Sau khi chốt:
  - sửa `docs/prd/requirements.md` và `docs/prd/architecture.md` trước;
  - đổi trạng thái đề xuất;
  - `git mv` đề xuất sang `docs/prd/update-archive/`.
