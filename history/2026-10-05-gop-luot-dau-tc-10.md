# Gộp hai lượt đầu của TC-10 thành một

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

TC-10 nhắm vào lượt "không biết" khi còn thiếu ngày đi, số người, ngân sách. Hai lượt mở đầu "Đi Đà Nẵng" và "3 ngày" chỉ để có đủ điểm đến + số ngày; gộp thành một lượt "Đi Đà Nẵng 3 ngày" cho ca ngắn hơn và đỡ một lượt gọi LLM.

## File thay đổi

- `src/evaluation/datasets/agent_test_cases_nhat.yaml` — sửa: TC-10 bỏ lượt "Đi Đà Nẵng" (kỳ vọng thiếu `days`), lượt đầu thành "Đi Đà Nẵng 3 ngày" giữ kỳ vọng của lượt "3 ngày" cũ.

## Quyết định

- Không còn kiểm nhánh hỏi `days` trong TC-10; nhánh đó không phải mục tiêu của ca (AC-AGT-01, đề xuất `2026-10-05-form-khi-chua-chot-chi-tiet`).
- Lượt "không biết" đầu tiên giờ là lượt 2 (trước là lượt 3); comment "T3" ở đầu ca vẫn chỉ conversation gốc trên LangSmith nên giữ nguyên.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py`: 62 passed, 3 failed — đúng ba test fail có sẵn đã ghi ở `history/2026-10-05-form-khi-chua-chot-chi-tiet.md`, không do thay đổi này.
- Chưa chạy lại TC-10 với LLM thật.

## Còn lại / rủi ro

- Chạy lại golden để xác nhận lượt "Đi Đà Nẵng 3 ngày" ra `NEEDS_CLARIFICATION` với `missingFields` gồm `startDate`, `party`, `budget`.
