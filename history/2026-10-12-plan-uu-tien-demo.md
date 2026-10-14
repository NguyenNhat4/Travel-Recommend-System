# Sửa hai plan theo hướng ưu tiên demo: kiểm chứng demo trước, gỡ luồng cũ sau demo

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs (plan agent, đề xuất PRD)

## Mục tiêu

Người dùng đổi ưu tiên: demo thật tốt cho sếp, chưa tối ưu production. Yêu cầu sửa hai plan:
- Tách việc demo khỏi việc gỡ code cũ. Plan tiến trình không chờ G0–G7.
- Thêm giai đoạn kiểm chứng demo với LLM thật trước khi code lớn.
- Kiểm chứng rồi sửa 4 vấn đề gọi tool. Không tăng giới hạn tool hay timeout một cách mù quáng; không coi tra cứu thất
  bại là không có dữ liệu.
- Ưu tiên trải nghiệm nhìn thấy được. Preview sau `compose` chỉ giữ nếu đo thấy có ích.
- Giữ kiểm tra hành vi và grounding; không giảm AC; không dùng dữ liệu dựng sẵn để che lỗi.

Cũng trong lượt này, người dùng yêu cầu có ghi chú để nhóm không nhầm mà đi tối ưu luồng cũ. Lượt này chỉ sửa tài liệu,
chưa sửa code.

## File thay đổi

- `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md` — sửa (viết lại): thành plan chung, chia trước demo và sau demo.
  - Trước demo:
    - D0 ghi chú đóng băng.
    - D1 kiểm chứng demo: 6 kịch bản nối tiếp cộng một kịch bản lỗi và chậm, bản diễn đạt khác, 3 lần chạy, mức độ lỗi.
    - D2 là G1 cũ.
    - D3 bật mặc định và ghi baseline.
    - D4 kiểm chứng và sửa T1–T4.
    - D5 sửa lỗi demo.
    - D6 tổng duyệt trên staging.
    - Tiêu chí nghiệm thu trước demo (mục 3).
  - Sau demo: G0, G2–G7.
  - Thêm mục 1.2 (bốn vấn đề gọi tool, kèm dòng code) và 1.3 (kết quả chạy thử). Thứ tự chung của hai plan ở mục 0.
- `docs/plan/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa:
  - Không chờ G0–G7; bắt đầu sau D3. B4 chờ D4, vì cùng sửa `jobs.py`, `fares.py`.
  - B0 gộp vào D1. B10 tách thành B10a (trước demo, kèm tiêu chí) và B10b.
  - Preview chỉ làm khi số đo D1 đạt tiêu chí ở 3.5. Contract trước demo không có `run.preview`, `debug`.
  - Mức 2 sau demo.
- `docs/prd/update/2026-10-12-orchestrator-thanh-luong-chinh.md` — sửa: chia Phần 1 (mặc định, trước demo) và Phần 2
  (gỡ, sau demo). Bản cuối do entry `2026-10-13-chot-orchestrator-mac-dinh.md` tách và lưu trữ.
- `docs/prd/update/2026-10-12-tien-trinh-tro-ly-co-ket-qua.md` — sửa: chia Phần A (trước demo), Phần B (chẩn đoán mức
  2, sau demo), Phần C (preview, chỉ khi đo thấy có ích); AC-AGT-09 thêm ý tra cứu không thành công không được ghi là
  không có kết quả.
- `AGENTS.md` §3 — sửa: thêm quy tắc "luồng phân loại cũ đã đóng băng".
- `docs/spec/agent/working-context.md` §2, §3 — sửa: hàng "Tune orchestrator"; hàng tune classify/converse ghi rõ phần đóng
  băng; ghi chú đầu §3; dòng trạng thái B11–B13.
- `.agents/skills/building-itinerary-agent/SKILL.md` bước 3 — sửa: hàng "Hiểu sai ý" trỏ tới `orchestration.py`; một
  dòng trỏ về AGENTS.md §3.
- `history/2026-10-12-plan-uu-tien-demo.md` — thêm: entry này.

Ba file `AGENTS.md`, `working-context.md`, `SKILL.md` được sửa sau khi người dùng chốt ngày 13/10; nội dung ghi ở cả hai
entry.

## Quyết định

- Thứ tự trước demo: D0 → D1 (song song D2) → D3 → D4 → D5 → D6. Plan tiến trình chạy song song sau D3: B3, B7, B8 trước;
  B4, B5 sau D4; B6 chỉ khi đo thấy có ích.
- Bốn vấn đề gọi tool đều có thật trong code (đọc `jobs.py`, `fares.py`, `application/itinerary/flights.py`):
  - T1: `_origin_routes` gọi song song mọi điểm đến trên cùng bộ đếm 10 lời gọi, và `except Exception` trả `[]`.
  - T2: quét mọi trang Search khi sắp theo giá kèm câu tìm; lỗi giữa chừng thì bỏ kết quả đã lấy.
  - T3: chữ ký job ghi trước khi chạy, nên job lỗi không được thử lại.
  - T4: lấy chi tiết tuần tự, không có bộ nhớ trong lượt; liệt kê tuyến hai lần trong `fares.answer`.

  Cách sửa trong D4 chỉ chọn sau khi có test tái hiện và số đo. Giới hạn chỉ đổi khi có số đếm và người dùng đồng ý.
- Môi trường demo là staging (`deployment-plan.md` §1). Trước D3, D1 chạy trên máy local dựng giống staging.
- Tiêu chí preview: `t_final − max(5 giây, t_compose)` từ 2 giây trở lên ở ít nhất một nửa số lượt lập lịch của D1.
  Plan đặt tiêu chí này; người dùng xác nhận cùng Phần C.
- Ghi chú đóng băng tách phần dùng chung (luật trước LLM trong `classify_node`, `converse` khi chặn, `clarify`) khỏi phần
  đóng băng, để nhóm không ngừng sửa nhầm phần orchestrator đang dùng.

## Kiểm tra

- Chưa sửa source.
- Chạy thử 22 hội thoại (48 lượt) từ ví dụ AC, mỗi hội thoại một lần, trong tiến trình, `ITINERARY_ORCHESTRATOR=on`,
  `ITINERARY_DATA_MODE=inprocess`, LLM thật. Script ở scratchpad (`probe.py`, `convs.json`). Kết quả:
  - 0 lỗi HTTP; không lượt nào vào `classify` hay `explore`.
  - Thời gian mỗi lượt: chỉ trả lời 7–14 giây; có job 17–39 giây; hỏi vé 8–14 giây; nút vé 0,1 giây.
  - A08b ("tao ở sài gòn, đi đâu cũng được miễn vé rẻ") trả lời không có chuyến nào, trong khi A08a tìm được vé TP. Hồ
    Chí Minh → Hà Nội. Khớp T1, chưa xác nhận nguyên nhân.
  - F06f lượt 3 ("có chỗ nào rẻ hơn không") mất 39,4 giây, 0 thẻ.

  Chi tiết ở plan chung mục 1.3.
- Kiểm kê ký hiệu bằng cây gọi AST và theo dõi lời gọi khi chạy test orchestrator: khoảng 68 hàm chỉ node cũ dùng; 2 thứ
  phải chuyển (`unclear_input_reply`, `UNCLEAR_INPUT`).

## Còn lại / rủi ro

- Người dùng chốt và bắt đầu làm: xem `2026-10-13-chot-orchestrator-mac-dinh.md`.
- Danh sách lỗi của D1 có thể dài hơn thời gian còn lại trước demo; chỉ hai mức "chặn demo" và "xấu" phải xong.
