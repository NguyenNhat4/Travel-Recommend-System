# Sửa plan orchestrator theo review lần 2: số liệu chỉ qua placeholder, khối vé còn hiệu lực, bỏ lời mời thắng tạo

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Thay thế: `2026-10-12-sua-plan-orchestrator-theo-review.md` (một phần: chỉ chặn số viết thẳng khi lượt không có kết
  quả việc nào; chèn mọi khối vé kể cả `asked`; nút lập lịch tạo `pending_offer`)
- Bị thay thế bởi: `2026-10-12-sua-plan-orchestrator-theo-review-3.md` (một phần: tự thay việc vé theo điểm đến và kiểu
  hỏi; placeholder so với mốc không ghi việc)

## Mục tiêu

Người dùng gửi review lần 2 cho plan `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`, 3 điểm:

1. [P1] Chỉ cần lượt có một kết quả tool là phép kiểm số mất tác dụng: lượt tra vé mà LLM viết thêm giá cũ của khách
   sạn từ `shown` thì không bị chặn; `finalize` cũng không đối chiếu số trong câu chữ.
2. [P2] Bắt chèn mọi khối vé mâu thuẫn với giới hạn một câu hỏi: hai việc vé cùng thiếu nơi đi thành hai câu hỏi; câu
   hỏi của vòng trước vẫn bị chèn dù vòng sau đã trả lời được.
3. [P2] `pending_offer` bị tạo lại ngay sau khi người dùng từ chối, vì lượt "để sau" vẫn giữ nút lập lịch và nút lại
   tạo lời mời; "ok" tiếp theo thành đồng ý.

## File thay đổi

- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — sửa:
  - phần đầu: dòng trạng thái trỏ tới entry này;
  - mục 3: dòng gác cổng trong sơ đồ;
  - 4.2: `Job.replaces`, `OrchestratorTurn.stop`; `message` trỏ tới danh sách placeholder ở 4.4; `stop` map như
    `classification.stopped`;
  - 4.3: kết quả việc vé có thể bị thay (`superseded`);
  - 4.4 luật 1: số liệu chỉ qua placeholder ở mọi lượt, khối vé được miễn, thứ tự sửa khi vi phạm, `finalize` kiểm lại;
    luật 5; luật 6 viết lại (khối còn hiệu lực, một khối hỏi lại, `waiting_jobs`, `pending_fare`); luật 7 (điều kiện thứ
    năm của câu mời, bảng `pending_offer` xét theo thứ tự, chỉ câu mời tạo lời mời, câu trả lời khi đồng ý không đạt);
  - 4.8: thêm 3 dòng, sửa dòng "để sau";
  - mục 5 (test B5, B6, B8; tài liệu B10), 6, 7, 8.
- `docs/prd/update/2026-10-12-orchestrator-va-kham-pha-llm.md` — sửa, vẫn `chờ chốt`:
  - AC-AGT-06: nguyên tắc về đồng ý và từ chối lời mời;
  - AC-AGT-08: nhiều tuyến cùng thiếu thông tin thì chỉ hỏi một câu;
  - `architecture.md` §3: gác cổng và Tiêu chuẩn Grounding thêm luật số liệu chỉ qua placeholder ở mọi lượt; một câu
    hỏi khi nhiều việc cùng cần hỏi lại; từ chối làm lời mời hết hiệu lực ngay trong lượt.
- `history/2026-10-12-sua-plan-orchestrator-theo-review.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.

## Quyết định

- **Số liệu chỉ qua placeholder, ở mọi lượt.** Theo cách `narration.render` đang làm (bỏ lời lịch trình khi có số tiền
  viết thẳng, `RAW_MONEY`, dù lượt đã gọi tool):
  - giá, chênh giá, giờ, điểm, số đánh giá, hạng sao, khoảng cách trong lời orchestrator viết phải là placeholder gắn với
    mã đã tra trong lượt; code điền;
  - code quét phần chữ sau khi bỏ placeholder, link và chỗ đặt khối vé; số người dùng vừa nêu cũng không được viết thẳng,
    như `narrate` dùng `[[budget]]`;
  - khối vé do code viết được miễn, vì code chèn sau bước kiểm;
  - vi phạm: tra lại mã chưa tra, buộc trả lời một lần, rồi lời dự phòng;
  - `finalize` quét lại bản trước khi điền; lọt tới đây thì thay câu bằng lời dự phòng như nhánh guardrail, giữ thẻ.
- **Khối vé còn hiệu lực:**
  - việc sau khai `replaces`, hoặc cùng điểm đến và kiểu hỏi, thì thay việc trước; khối bị thay không chèn;
  - nhiều khối hỏi lại thì chỉ chèn một (việc số nhỏ nhất); các việc còn lại vào `waiting_jobs` (`CARRIED`, một lượt).
  - Bấm nút trả lời thì code điền trường vừa có vào các việc chờ và chạy luôn, không qua LLM, để giữ AC-AGT-08 (nút vé đi
    thẳng nhánh vé).
- **Bỏ lời mời thắng tạo lời mời:**
  - bảng `pending_offer` xét theo thứ tự; `declines_offer`, `stop`, luật dừng đứng đầu;
  - chỉ câu mời được chèn mới tạo lời mời đang chờ; nút không tạo, cũng không khôi phục;
  - lượt chuyển sang điểm đến khác mà không có câu mời thì xoá lời mời cũ, để "ok" không lập lịch nhầm nơi;
  - thêm `OrchestratorTurn.stop` cho luật dừng do LLM nhận ra, như nhãn `stop` của `TurnRoute` hiện nay;
  - đồng ý không đạt thì trả lời theo luật lời mời: không mời lại bằng câu nếu đã mời hoặc vừa từ chối.

## Kiểm tra

- Đọc code để làm căn cứ: `narration.render` (`RAW_MONEY`, `unknown_placeholder`, `fallback_message`),
  `exploration._PLACEHOLDER` (hiện có `price`, `rating`, `reviews`), `conversation._FACT_NUMBER`,
  `exploration._closing` (đặt `pending_offer` ở mọi lượt khám phá chưa đồng ý), `models.TurnRoute.route` (có `stop`).
- Không chạy test: chỉ sửa tài liệu.

## Còn lại / rủi ro

- **Dừng chờ người dùng duyệt plan và chốt đề xuất**, kèm 4 điểm (số thẻ, phạm vi "đã xem", số việc mỗi vòng, số vòng).
  Chưa chốt thì không làm B5–B10.
- Luật "số chỉ qua placeholder" chặt hơn lời khám phá hiện nay (prompt `explore` cho chép nguyên giá vé vào câu); B12 phải
  đếm số lần vi phạm và số lần dùng lời dự phòng.
