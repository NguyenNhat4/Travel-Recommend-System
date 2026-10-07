# TC-10 kiểm route sang clarify

- Ngày: 2026-10-05
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: evaluation
- Bị thay thế bởi: 2026-10-05-form-den-khi-du-truong-bat-buoc.md

## Mục tiêu

Người dùng trả lời mơ hồ ("không biết") khi còn thiếu thông tin chuyến đi thì graph phải đi tới `clarify` và hiện form, không lập lịch. Trước khi sửa code, golden TC-10 phải fail vì sai route và vì không có form.

## File thay đổi

- `src/evaluation/datasets/agent_test_cases_nhat.yaml` — sửa: cả hai lượt của TC-10 thêm `nodesInclude: [classify, clarify]`. Lượt 2 vẫn giữ `formMatchesAnswer: true`, khoá này fail khi response không có `clarificationForm`.

## Quyết định

- Kỳ vọng chỉ kiểm graph có đi qua `clarify`, không kiểm `clarify` được gọi thẳng từ `classify`. Topology hiện tại (`classify → extract → clarify`) và đề xuất đã chốt `2026-10-05-form-khi-chua-chot-chi-tiet` (luật tất định trong `extract_result`) đều thoả kỳ vọng này.
- Người dùng muốn `classify` dựa vào lịch sử hội thoại để route sang `clarify` khi thiếu bất kỳ trường nào (điểm đến, số ngày, ngày đi, số người, ngân sách, khách sạn, hoạt động). Yêu cầu này lệch PRD: `architecture.md` §3 và đề xuất đã chốt chọn luật tất định, còn AC-AGT-01 cho lập lịch khi đã đủ điểm đến và số ngày. Chưa có đề xuất cho phần lệch này nên chưa sửa code.

## Kiểm tra

- `.venv/bin/python -m pytest -q src/evaluation/tests/test_golden.py`: 65 passed.
- Chưa chạy TC-10 với LLM thật; người dùng tự chạy baseline (`.venv/bin/python -m src.evaluation.agent.golden --only TC-10`).

## Còn lại / rủi ro

- Baseline mong đợi ở lượt 2: `status=COMPLETED`, `thiếu node 'clarify' trong trace`, `tool có chạy`, `không có clarificationForm`.
- Chờ người dùng chọn cách sửa: theo đề xuất đã chốt (luật trong `extract_result`) hoặc đề xuất mới để `classify` route sang `clarify`.
