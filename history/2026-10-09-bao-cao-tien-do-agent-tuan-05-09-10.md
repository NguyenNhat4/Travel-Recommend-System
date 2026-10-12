# Báo cáo tiến độ Itinerary Agent tuần 05–09/10 (nguồn làm slide demo)

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: docs, agent

## Mục tiêu

Hôm nay có buổi demo tiến độ agent. Người dùng cần một file markdown tổng hợp các thay đổi từ thứ 7 03/10 đến 09/10, dựa
trên lịch sử commit và docs, để dùng làm slide. Dàn ý đã được người dùng duyệt: bỏ 3 slide ("Tuần này trong một slide",
"Hiểu ý và hỏi lại", "Công cụ cho dev"), thêm ví dụ thật cho phần lọc trùng, và lấy số đánh giá từ LangSmith.

## File thay đổi

- `docs/spec/agent/slide/bao-cao-tien-do-tuan-05-09-10.md` — thêm: dàn ý 12 slide, nội dung từng slide, phụ lục commit.

## Quyết định

- Đặt trong `docs/spec/agent/slide/` theo yêu cầu người dùng. File chỉ tổng hợp những gì đã làm, không đổi yêu cầu, nên
  không lệch PRD.
- Số latency lấy từ LangSmith (project `nhat-10-1`, `nhat-agent-tc`, `nhat-10-7`, 05/10 đến 09/10 07:33 UTC): 403 root
  run và khoảng 1.900 span node. Phân loại lượt theo node có trong trace (`compose`, `clarify`, `converse`,
  `apply_option`, `dead_letter`).
- PASS/FAIL lấy từ biên bản runner (`.logs/agent-eval/`, `src/evaluation/reports/`), vì LangSmith không lưu kết quả chấm.
- Ví dụ lọc trùng lấy từ output `dropped_duplicates` của node `filter` trên LangSmith: 24 lượt, 129 mục bị loại (62 do
  luật, 67 do LLM).
  - Người dùng nhớ ví dụ là "hòn tằm", trace ghi "Hòn Thơm"; file dùng tên trong trace.
  - Không tìm thấy cặp "VinWonders miễn phí + VinWonders kèm set ăn nhanh". File dùng cặp có thật: "Vé Vào Cửa Tiêu
    Chuẩn" và "Vé Vào Cửa + Buffet 350k".

## Kiểm tra

- Không có code thay đổi nên không chạy test.
- Đối chiếu số liệu với `git log`, các entry `history/`, report eval và LangSmith.

## Còn lại / rủi ro

- Script đo LangSmith chạy ngoài repo, chưa commit.
- Người dùng cần xác nhận ví dụ VinWonders trước khi dựng slide.
