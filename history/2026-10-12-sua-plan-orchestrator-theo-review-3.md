# Sửa plan orchestrator theo review lần 3: nhận diện cùng một yêu cầu vé, nguồn của số so với mốc

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Thay thế: `2026-10-12-sua-plan-orchestrator-theo-review-2.md` (một phần: việc vé sau tự thay việc trước khi cùng điểm
  đến và kiểu hỏi; placeholder `[[distance:#n]]`, `[[price_diff:#n]]` chỉ gắn mã sản phẩm)

## Mục tiêu

Người dùng gửi review lần 3 cho plan `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`, 2 lỗi:

1. [P1] Luật "hai việc vé cùng điểm đến và kiểu hỏi thì việc sau thay việc trước" xoá nhầm yêu cầu độc lập: "so vé từ
   Sài Gòn và Đà Nẵng ra Hà Nội" mất một tuyến.
2. [P2] `[[distance:#n]]`, `[[price_diff:#n]]` không nói so với mốc nào: khách sạn #12 có trong việc "gần Hồ Gươm" lẫn
   "gần Văn Miếu" thì code không biết điền khoảng cách tới đâu.

## File thay đổi

- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — sửa:
  - phần đầu: dòng trạng thái trỏ tới entry này;
  - 4.2: chú thích `Job.replaces` chỉ dùng cho câu hỏi lại của việc vé;
  - 4.3: việc `near`, `cheaper`/`dearer` có đúng một mốc; giá của mốc cũng tra lại; bản rút gọn có `anchor`; đoạn vé
    nói rõ chỉ câu hỏi lại mới bị thay;
  - 4.4 luật 1: placeholder thuộc tính và placeholder so với mốc (bắt buộc ghi việc, ví dụ `[[distance:job2:#12]]`);
    code chỉ điền khi xác định được đúng một giá trị;
  - 4.4 luật 6: ba điều kiện để `replaces` có hiệu lực; không tự thay theo điểm đến, kiểu hỏi;
  - 4.8: thêm hai dòng; mục 5 (test B5, B6); mục 7.
- `docs/prd/update/2026-10-12-orchestrator-va-kham-pha-llm.md` — sửa, vẫn `chờ chốt`: gác cổng nói rõ câu hỏi lại chỉ bị
  bỏ khi việc sau cập nhật đúng yêu cầu đó; Tiêu chuẩn Grounding thêm câu về số so với mốc.
- `history/2026-10-12-sua-plan-orchestrator-theo-review-2.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.

## Quyết định

- **Cùng một yêu cầu vé** chỉ khi việc sau khai `replaces=k` và đủ ba điều kiện:
  - việc `k` là `asked`;
  - việc sau điền trường việc `k` đang hỏi (nơi đi, nơi đến, loại vé);
  - mọi trường `FareQuestion` khác giống hệt, kể cả trường để trống.

  Không đủ thì bỏ qua `replaces` và giữ cả hai. Khối `answered` không bao giờ bị thay. Không có luật tự thay theo điểm
  đến hay kiểu hỏi.
- **Số so với mốc ghi rõ việc:** `[[distance:jobK:#n]]`, `[[price_diff:jobK:#n]]`. Mỗi việc `near`, `cheaper`, `dearer`
  có đúng một mốc, ghi trong bản rút gọn (`anchor`). Placeholder thuộc tính (`price`, `hours`…) chỉ cần ghi việc khi hai
  việc trả hai giá trị khác nhau cho cùng mã. Không xác định được đúng một giá trị thì là vi phạm, code không đoán.
- Không đổi kiến trúc, không thêm tầng xử lý, theo đúng ý người dùng.

## Kiểm tra

- Đọc `agents/models.py` `FareQuestion` để liệt kê đúng các trường dùng khi so hai câu hỏi vé.
- Không chạy test: chỉ sửa tài liệu.

## Còn lại / rủi ro

- **Dừng chờ người dùng duyệt plan và chốt đề xuất**, kèm 4 điểm (số thẻ, phạm vi "đã xem", số việc mỗi vòng, số vòng).
  Chưa chốt thì không làm B5–B10.
- Orchestrator quên khai `replaces` thì câu hỏi lại cũ vẫn được chèn cùng câu trả lời mới. Prompt phải dặn, và B11–B12
  đo tần suất.
