# Guardrail tầng 1: lọc tin nhắn rác trước LLM và rate limit trợ lý

- Ngày: 2026-10-01
- Tác giả: nhatnm / Claude
- Nhánh: feat/agent-guardrail-rule-based
- Trạng thái: hoàn thành
- Phạm vi: agent

## Mục tiêu

Tin nhắn rác ("aaaaaa", "?????", "asdfjkl", toàn emoji, chửi thề) vẫn đi tới LLM ở `classify` rồi `converse`, tốn hai lượt gọi
cho câu không có nội dung, và không có giới hạn số tin một người gửi. Thêm một lớp luật tất định (< 1 ms, không gọi LLM) chạy
trước LLM, kèm rate limit theo người gửi. Đề xuất `docs/prd/update-archive/2026-10-01-guardrail-tang-1-rule-based.md`
(NFR-SEC-04), nhatnm chốt ngày 2026-10-01.

## File thay đổi

- `docs/prd/requirements.md` — sửa: thêm NFR-SEC-04.
- `docs/prd/architecture.md` — sửa: §3 sơ đồ `ClassifyTurn` và mục "Lọc đầu vào trước LLM".
- `docs/prd/update-archive/2026-10-01-guardrail-tang-1-rule-based.md` — thêm: đề xuất, trạng thái đã áp dụng (tạo ở `docs/prd/update/` trong cùng task, chuyển sang archive sau khi chốt).
- `docs/spec/agent/langgraph-nodes.md` — sửa: mục "Guardrail tầng 1" (bảng luật, token hợp lệ, hành vi khi chặn, rate limit, kiểm thử).
- `docs/spec/agent/state-fields.md` — sửa: thêm `unclear_input`, `blocked_by_guardrail` nhận `abusive:profanity`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §1 mô tả lọc rác + 429; bảng tiêu đề thêm dòng "Mình chưa hiểu ý bạn".
- `src/shared/contracts/paths/itinerary-agent.yaml` — sửa: thêm `'429'` cho `/assistant/itineraries` và `/assistant/itineraries/stream`.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại từ contract (`npm run generate:api-types`), thêm 2 dòng 429.
- `src/backend/app/agents/steps/guardrails.py` — sửa: thêm `input_quality` (rỗng/ký hiệu, ký tự lặp, tỉ lệ chữ thấp, gibberish, tục tĩu).
- `src/backend/app/agents/nodes.py` — sửa: `_guardrail_junk_input` trong `classify` (sync + async), `converse` xử lý `unclear_input`, `intake` khởi tạo field.
- `src/backend/app/agents/state.py` — sửa: thêm `unclear_input`.
- `src/backend/app/agents/steps/conversation.py` — sửa: thêm `unclear_input_reply`.
- `src/backend/app/agents/steps/messages.py` — sửa: thêm `UNCLEAR_INPUT`.
- `src/backend/app/domain/auth/rate_limits.py` — sửa: thêm luật `assistant:sender` 10 tin / 60 giây.
- `src/backend/app/main.py` — sửa: `build_auth` trả thêm `rate_limiter` để gắn vào `app.state`.
- `src/backend/app/api/v1/routes/assistant.py` — sửa: `_rate_limited` chạy đầu cả hai route, trả 429 + `Retry-After`.
- `src/backend/tests/unit/agents/test_guardrails.py` — sửa: test `input_quality`, `classify`/`converse` không gọi LLM, bộ golden không bị chặn nhầm.
- `src/backend/tests/contract/test_assistant_rate_limit.py` — thêm: 429 khai báo trong contract, cắt đúng sau ngưỡng.
- `history/2026-10-01-guardrail-tang-1-rule-based.md` — thêm: entry này.

## Quyết định

- Không chặn theo độ dài ngắn: "2", "ok", "15/10" là câu trả lời hợp lệ cho `clarify`. Độ dài tối đa đã có `maxLength: 1000` (422).
- Âm tiết tiếng Việt kiểm theo cấu trúc phụ âm đầu + vần trên chữ đã bỏ dấu, thay vì nạp danh sách ~7.000 âm tiết; câu không dấu tự hợp lệ.
- Thêm fallback "token Latin đọc được" (có nguyên âm, không dồn ≥ 5 phụ âm, không gõ dọc hàng phím): chạy trên 254 câu thật trong repo (golden agent, gold/latency/parity search bench, query template, literal trong test) thì bản chỉ dùng từ điển chặn nhầm 6 câu ("VinWonders", "tiNiWorld", "Thác Đray Nur", "Sea Links Golf & Country Club", 2 câu tiếng Anh). Sau khi thêm: 0.
- Rác → `NEEDS_CLARIFICATION` 200, câu cố định; tục tĩu thuần → nhánh `blocked_by_guardrail` sẵn có (400). Tục tĩu lẫn trong yêu cầu hợp lệ thì cho qua; phần còn lại chỉ là lời gọi ("fuck you", "đm mày") vẫn tính là tục tĩu thuần.
- Lượt "chưa hiểu" là 200 nên vẫn được lưu vào lịch sử hội thoại như mọi lượt hỏi lại.
- Rate limit dùng lại limiter của auth; route tự trả 429 với câu riêng cho trợ lý thay vì đi qua handler auth (câu "sau 15 phút" sai ngữ cảnh). Test không chạy lifespan thì không có limiter và bỏ qua.
- Test route đặt ở file mới thay vì `test_assistant_contract.py`, để không conflict với stash của nhánh `feat/itinerary-agent-guardrails`.

## Kiểm tra

- `.venv/bin/python -m pytest backend/tests -q` (từ `src/`): 1046 passed, 21 skipped.
- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS.
- Chưa chạy thử với LLM thật hay qua trình duyệt.

## Còn lại / rủi ro

- Khách được đếm theo IP: chỉ đúng khi edge proxy đặt `X-Forwarded-For` và BFF/edge nằm trong `TRUSTED_PROXIES`; nếu không, mọi khách sau cùng một BFF chung một bộ đếm 10 tin/phút.
- Blacklist tục tĩu và từ điển viết tắt là danh sách tay, chưa có người duyệt riêng.
- Stash `stash@{0}` của nhánh `feat/itinerary-agent-guardrails` cũng sửa `docs/spec/agent/langgraph-nodes.md`; merge hai nhánh có thể conflict ở file đó.
