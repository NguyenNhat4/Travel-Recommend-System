# Guardrail tầng 1 chặn spam có dấu tiếng Việt nối bằng dấu câu

- Ngày: 2026-10-02
- Tác giả: nhatnm / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Người dùng gửi dồn chuỗi như `pưaiegapòigấ;sldááđăsdpưaiegapòigấ;…` (lặp nhiều lần). Luật `gibberish` của `input_quality`
(NFR-SEC-04) cho qua, nên mỗi tin vẫn tốn lượt `classify` + `converse` của LLM và bot trả "Ngoài phạm vi hỗ trợ" khác nhau.
Rate limit 10 tin/phút và `maxLength: 1000` đã có từ entry `2026-10-01-guardrail-tang-1-rule-based`, không đổi.

## File thay đổi

- `src/backend/app/agents/steps/guardrails.py` — sửa: `_pronounceable` thêm giới hạn độ dài token (≤ 14) và cấm cụm ≥ 4 nguyên âm liền.
- `src/backend/tests/unit/agents/test_guardrails.py` — sửa: thêm hai chuỗi spam vào bảng `gibberish`.
- `docs/spec/agent/langgraph-nodes.md` — sửa: mô tả token Latin "đọc được" khớp luật mới.
- `history/2026-10-02-guardrail-chan-spam-co-dau-noi-dau-cau.md` — thêm: entry này.

## Quyết định

- Nguyên nhân: các mẩu spam dài 12–21 ký tự có nguyên âm, không dồn ≥ 5 phụ âm, không gõ dọc hàng phím nên bị fallback
  coi là tên riêng. Tên riêng/thương hiệu ngoài từ điển ngắn hơn nhiều, nên chặn theo độ dài và cụm nguyên âm.
- Không đổi contract, PRD hay ngưỡng rate limit: chỉ hiện thực chặt hơn NFR-SEC-04.

## Kiểm tra

- `.venv/bin/python -m pytest backend/tests/unit/agents backend/tests/contract/test_assistant_rate_limit.py -q` (từ `src/`): pass,
  gồm bài "không câu nào trong golden bị chặn nhầm".
- Chưa chạy qua trình duyệt hay LLM thật.

## Còn lại / rủi ro

- Spam gồm từ tiếng Việt hợp lệ ghép ngẫu nhiên vẫn qua tầng 1 và tới LLM; chỉ rate limit chặn được.
- Tên riêng dài hơn 14 ký tự viết liền, không có trong từ điển, sẽ bị coi là rác.
