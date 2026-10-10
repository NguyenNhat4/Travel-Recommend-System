# Sửa đề xuất gợi ý trước khi lập lịch: hỏi người dùng có muốn lập lịch, đồng ý mới hỏi thông tin chuyến

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs, agent
- Thay thế: 2026-10-09-de-xuat-goi-y-truoc-khi-lap-lich.md

## Mục tiêu

Người dùng xem kịch bản mô phỏng và chỉnh lại luật:

- Trợ lý phải hỏi người dùng có muốn lập lịch không. Chỉ khi người dùng đồng ý ("ok"...) mới hỏi ngân sách, ngày đi, số
  ngày, số người.
- Chưa có điểm đến thì gợi ý nhẹ: nói tên nơi muốn đến (ví dụ Hà Nội, TP. Hồ Chí Minh) thì trợ lý kể được ở đó có gì;
  không ép.

Bản đề xuất trước coi câu có số ngày, ngày đi, số người... là lập lịch luôn. Luật này bị thay.

## File thay đổi

- `docs/prd/update/2026-10-09-goi-y-truoc-khi-lap-lich.md` — sửa:
  - thêm bước hỏi "có muốn lập lịch không" và định nghĩa thế nào là đồng ý;
  - mời nói điểm đến, không ép;
  - viết lại AC-AGT-06, FR-AGT-01, FR-AGT-06, sơ đồ architecture §3 và user-flow §3.2;
  - thêm ba bậc xử lý câu "không biết" khi chưa có điểm đến;
  - thêm ba điểm cần chốt: thế nào là đồng ý, hỏi lời mời bao nhiêu lần, cách xử lý "không biết";
  - ghi rõ đổi framework, A2A nằm ngoài phạm vi.
- `history/2026-10-09-de-xuat-goi-y-truoc-khi-lap-lich.md` — sửa: chỉ thêm dòng `Bị thay thế bởi`.
- `history/2026-10-09-sua-de-xuat-hoi-truoc-khi-lap-lich.md` — thêm: entry này.

## Quyết định

- Câu tự yêu cầu lập lịch ("lập lịch Hà Nội 3 ngày cho mình") vẫn được coi là đồng ý, nên ví dụ của AC-AGT-01 vẫn ra
  lịch như cũ.
- Câu chỉ nêu thông tin chuyến khi chưa có lời mời ("Hà Nội 3 ngày") được ghi lại, rồi trợ lý hỏi có muốn lập lịch không.
  Nếu trợ lý vừa mời mà người dùng trả lời bằng thông tin chuyến ("3 ngày thôi") thì tính là đồng ý, để người dùng không
  phải nhắn thêm một lượt. Phương án chặt hơn ghi ở điểm cần chốt 1.
- "ok" khi vừa có lời mời được nhận bằng luật, vì hiện nay "ok" đang bị coi là câu không thêm được thông tin và dẫn tới
  form.
- Người dùng hỏi thêm: chào xong mà người dùng nói "không biết" thì sao. Hiện nay câu đó cũng dẫn tới form. Đề xuất thêm
  ba bậc, không bậc nào hỏi thông tin chuyến hay hiện form:
  1. hỏi loại nơi (biển, nơi mát, thành phố) kèm nút;
  2. tự chọn điểm đến nhiều sản phẩm nhất và giới thiệu luôn;
  3. ngừng hỏi, giữ nút.

  "Không biết" khi được hỏi có muốn lập lịch thì coi như để sau. Sau khi đã đồng ý lập lịch thì vẫn hiện form như
  AC-AGT-01.
- Phân tích framework (người dùng hỏi về A2A) để ngoài đề xuất này:
  - Đo trong code: chỉ 5 file import LangGraph/LangChain.
  - Phần phụ thuộc framework khoảng 1.000 dòng: `graph.py`, `routing.py`, `runtime_dependencies.py`, các lượt gọi LLM
    trong `nodes.py`, `infrastructure/llm/client.py`, checkpointer.
  - Luật gây cứng nằm trong `steps/` và domain, khoảng 6.700 dòng Python thường, giữ nguyên dù đổi framework.
  - Kết luận gửi người dùng: giữ LangGraph, chưa tách A2A.

## Kiểm tra

- Chỉ sửa tài liệu, không chạy test. Đã đối chiếu các đoạn trích PRD trong đề xuất với PRD hiện tại.
- Số dòng code đo bằng `wc -l`, danh sách import bằng `grep` trong `src/backend/app`.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất và bảy điểm mở. Sau khi chốt: cập nhật PRD trước, rồi contract 1.24.0, rồi backend,
  frontend, spec, test.
- Nên lấy trace LangSmith của hội thoại "Hà Nội" → "Hà Nội có gì?" và "ok" khi chuyến còn thiếu thông tin để xác nhận
  nguyên nhân trước khi code.
- Working tree vẫn có thay đổi chưa commit của task khác; không chạm vào.
