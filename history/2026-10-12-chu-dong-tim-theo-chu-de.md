# Chủ động tìm theo chủ đề trước khi hỏi thành phố

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng báo “đi chùa” → “có chùa nào” bị hỏi thành phố dù catalog có chùa; yêu cầu trợ lý phải chủ động tìm,
không chờ “tìm đi”. Hiện thực FR-AGT-06, AC-AGT-06/07, NFR-REL-01 theo PRD đã chốt: tự quyết tìm theo câu hỏi,
thẻ từ tool chính lượt đó. Không thay PRD, API hay nhánh lập lịch.

## File thay đổi

- `src/backend/app/agents/steps/prompts.py` — sửa: chủ đề đủ rõ thì execute ngay; thiếu thành phố không chặn tìm;
  query gọn giữ nội dung, không tự chọn thành phố làm bộ lọc, không khẳng định thiếu dữ liệu trước khi tra;
  thẻ ở nhiều thành phố/lời mời của trợ lý không có nghĩa khách đã chọn thành phố đầu.
- `src/backend/app/agents/steps/jobs.py` — sửa: brief của tìm không giới hạn thành phố kèm destination từng mục,
  kể cả dòng dự phòng khi facts quá dài.
- `src/backend/tests/unit/agents/test_orchestrator_jobs.py` — sửa: bảo toàn kết quả nhiều thành phố và điểm đến trong brief.
- `src/backend/tests/unit/agents/test_orchestrator_runtime.py` — sửa: graph trả thẻ ngay lượt đầu không cần thành phố/form.
- `docs/spec/agent/nghiep-vu/tro-chuyen-va-kham-pha.md` — sửa: mô tả tìm chủ động theo chủ đề.
- `docs/spec/agent/langgraph-nodes.md` — sửa: trách nhiệm orchestrator và điểm đến từng kết quả.

## Quyết định

- Chỉnh hướng dẫn chung trong prompt, không regex/bảng từ khoá và không worker LLM mới.
- Không chọn thành phố thay khách khi Search hỗ trợ tìm không giới hạn; nếu đã có phạm vi đang nói thì giữ.
- Cần thông tin bắt buộc mới hỏi trước; có kết quả thì đưa thẻ rồi có thể hỏi thu hẹp một câu.
- Giữ cờ mặc định off trong source; `.env` người dùng đã bật on. Không sửa env, không commit.

## Kiểm tra

- Log chat người dùng `.logs/web-demo.log`: cả ba lượt có search_products outcome=ok; hai lượt đầu nhánh cũ,
  “tìm đi” sau restart mới dùng orchestrator. Đây chỉ là bằng chứng gọi tool, không chứng minh kết quả phù hợp.
- Search API thật, query chùa/taxonomy attraction/không giới hạn thành phố: có chùa trong kết quả.
- Baseline orchestrator thật gpt-6.1-sol/low + inprocess Search/Catalog, trước sửa:
  “di chua” chỉ ask (6952 ms), “toi muon ghe chua” chỉ ask (9791 ms), không job/thẻ;
  câu tiếp “có chùa nào” mới execute query “chùa để tham quan, chiêm bái” và trả 3 thẻ (23831 ms).
  Scratch `/tmp/orchestrator-proactive-before.json` và log cùng tên.
- Unit: `WEAVIATE_URL=http://127.0.0.1:9 SEARCH_PREWARM=false HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false
  .venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests/unit/agents src/backend/tests/unit/domain`
  → **2103 passed, 19.54 s**, gồm snapshot đường off. Log `/tmp/orchestrator-proactive-tests.log`.
- Sau sửa lần đầu: “di chua” và “toi muon ghe chua” đều execute query chùa/destination null và trả 3 thẻ ngay lượt đầu
  (15088 / 15087 ms). Follow-up tự thu hẹp vào thành phố của offer do trợ lý viết, dù khách chưa chọn: bổ sung prompt
  phân biệt thẻ nhiều nơi/lời mời với phạm vi người dùng đã chọn; không vá code hiểu câu.
- Kiểm cuối model thật + dữ liệu thật, `/tmp/orchestrator_proactive_final.py`, env on/gpt-6.1-sol/openai/low,
  HF_HUB_OFFLINE=1 SEARCH_PREWARM=false LANGSMITH_TRACING=false, output `/tmp/orchestrator-proactive-final.json`:
  “di chua” **18866 ms**; follow-up “có chùa nào” **24568 ms**; “có chùa nào” trong chat mới **20780 ms**.
  Cả ba execute query chùa/destination null, trả đúng 3 thẻ, không cần “tìm đi”. Có kiểm assert job và thẻ trong JSON.
- `git diff --check`: PASS. Không thay contract/mock/schema nên không chạy lại contract hay DB verify.
- Demo local trước đó chạy `make web` không reload. Đã dừng đúng process group 57267 (kiểm args make web) bằng SIGINT,
  chạy lại `HF_HUB_OFFLINE=1 SEARCH_PREWARM=false make web` để nạp source mới; không reset database, không sửa `.env`.
- HTTP/SSE qua Next BFF :3000, đúng endpoint widget dùng, conversation mới: chỉ gửi “di chua” → HTTP200,
  `intake → classify → orchestrate → run_jobs → orchestrate → gatekeep → finalize`, 3 thẻ Chùa Minh Thành,
  Chùa Bác Ái, Chùa Huỳnh Đạo; **23468 ms**. Request `15bbe885-c960-460c-a2ed-1191477e3093`,
  JSON `/tmp/orchestrator-proactive-http.json`; assert HTTP status/thẻ/run_jobs PASS.
- Lần gọi BFF bằng script thiếu Origin/session/CSRF bị 403 theo thiết kế. Gọi lại theo flow trình duyệt:
  GET /api/auth/session tạo phiên riêng, giữ cookie và dùng csrfToken + Origin đúng; thành công như trên.
  Không đọc session của người dùng, không in/lưu cookie/token vào scratch hoặc lịch sử.
- Không chạy lại toàn backend sau thay đổi này: phạm vi prompt/brief đã có unit agent/domain, snapshot off và smoke
  model thật + HTTP BFF. Bộ toàn backend của task trước là 2935 pass/36 skip, không trình bày nó là số của bản sửa này.

## Còn lại / rủi ro

- Không còn việc bắt buộc trong fix này; demo local đã nạp source mới. Working memory process được tạo lại khi restart;
  bài kiểm dùng chat mới. Không deploy staging/production và không thay default cờ trong source.
- Không tuyên bố độ ổn định/SLA từ smoke một lần; B11–B13 vẫn làm sau theo plan trước.
