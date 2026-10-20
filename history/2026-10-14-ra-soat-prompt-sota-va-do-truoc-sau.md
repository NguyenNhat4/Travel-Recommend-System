# Sửa prompt Sota mục 3–4 và đo hội thoại trước/sau

- Ngày: 2026-10-14
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành
- Phạm vi: agent, evaluation, docs
- Mã FR/NFR: FR-AGT-01/06, AC-AGT-01/07, NFR-REL-01; giữ NFR-SEC-04

## Mục tiêu

Người dùng chọn chỉ sửa mục 3 và 4 của expected outcome: phân biệt mất hứng với dừng tư vấn; hiểu
`ko/không/k` theo câu hỏi ngay trước. Giao artifact có query và câu trả lời thực tế trước/sau để người
dùng test lại và tự commit. Đã được yêu cầu chạy thử model thật; không commit/push/restart backend.

## File thay đổi

- `src/backend/app/agents/orc_v2.py` — sửa: gom thứ tự hiểu dừng/phủ định/mất hứng; bỏ câu mâu thuẫn coi
  mọi “không đi nữa” là stop; phân biệt câu phủ định trả lời trẻ em và từ chối lời mời lập lịch.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: làm rõ thứ tự xử lý, không thay semantics HTTP.
- `src/evaluation/agent/sota_stop_review.py` — thêm: bảy ca model thật, ngữ cảnh seed ghi riêng, lưu nguyên văn
  final/function calls/context; replay prompt cũ qua `--prompt-from`. Dùng runtime/commit thật và gateway HTTP.
- `src/evaluation/reports/eval-2026-10-14-sota-stop-review.md` — thêm: điều kiện đo, kết quả, mọi hội thoại
  nguyên văn trước và cả ba lần sau, cách test lại, giới hạn bằng chứng.
- `docs/prd/update/2026-10-14-lich-thu-tha-khong-ep-so-hoat-dong.md` — thêm: đề xuất đã chuẩn bị trong phần
  review trước khi người dùng thu hẹp phạm vi; vẫn chờ chốt, KHÔNG áp dụng trong task này.
- `history/2026-10-14-ra-soat-prompt-sota-va-do-truoc-sau.md` — thêm: entry này.

Output local ngoài diff commit:

- `src/evaluation/reports/eval-2026-10-14-sota-stop-before.json` và `eval-2026-10-14-sota-stop-after.json`
  (gitignored theo quy ước): raw final/context/tool arguments/usage và prompt đã chạy.
- `/home/nhatnm/.codex/visualizations/2026/10/14/01a1399a-2e01-7062-b1c2-7a0076f41d80/sota-truoc-sau.html`:
  artifact hai cột, chọn ca/lần chạy; bản Markdown trong repo giữ toàn bộ câu trả lời.

## Quyết định

- Working tree ban đầu sạch; baseline commit `12771dc90496b191285e2d88f4097832a6028d3b`.
- Không dùng skill hoặc subagent. Không sửa v1, guard runtime, API/OpenAPI, DB, frontend hoặc model/secret.
- Đọc PRD README, architecture §2/3/6, requirements FR-AGT/AC, test-plan, implementation-plan §4;
  backend README, spec backend phần đối chiếu itinerary, architecture-repo, spec itinerary §4.7/5/6 và v2;
  agent README/working-context/nghiệp vụ/golden-run, mock itinerary README; history README, mười entry
  mới nhất theo tên và các entry chứa `orc_v2.py`/`TOO_FEW_ACTIVITIES`; các đề xuất mở liên quan.
- Lịch sử trực tiếp: `2026-10-14-lich-v2-ke-theo-ngay-va-cau-cut.md`,
  `2026-10-14-de-xuat-lua-chon-pho-bien-khi-khach-ne-cau-hoi.md`,
  `2026-10-14-sua-hoi-thoai-thu-luc-mot-gio.md`,
  `2026-10-14-orc-4-luot-tool-khong-tran-call-moi-luot.md`, `2026-10-14-bo-tran-request-nguon.md`.
- Chỉ áp mục 3–4 đã được người dùng chọn, phù hợp AC-AGT-01/07 hiện hành nên không sửa PRD. Giữ nguyên
  luật nhịp 2–3 hoạt động, tra vé, evidence xác nhận và các phần khác. Không áp đề xuất trần năm thẻ.
- Baseline được chạy trong process nạp source cũ trước khi sửa prompt; sau chạy bằng process mới.
  Bảy ca trước × một lần = 12 lượt; bảy ca sau × ba lần = 36 lượt. Mỗi lượt là model thật, không cassette.
- Model `gpt-6.1-sol`, OpenAI, reasoning low; Settings timeout request/tool/model 90/20/30 giây; không đổi
  giữa hai bản. HTTP source `http://127.0.0.1:8001`, backend báo inprocess/ready, productCount 4147.
- Ngữ cảnh trẻ em/lời mời được chuẩn bị sẵn và ghi nhãn; mọi response tiếp theo là model thật. Mỗi ca là
  hội thoại mới, không can thiệp history giữa các lượt. Không gửi LangSmith hoặc lưu suy luận nội bộ.

## Kiểm tra

- Lệnh kỹ thuật:
  `HF_HUB_OFFLINE=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false .venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_orc_loop.py src/backend/tests/unit/agents/test_orc_contracts.py src/backend/tests/unit/domain/test_orc_guardrails.py src/backend/tests/unit/application/test_assistant_v2_use_case.py src/backend/tests/unit/application/test_assistant_v2_store.py src/backend/tests/architecture`
  → **60 passed in 3.55s**.
- Model thật:
  `LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false .venv/bin/python -m src.evaluation.agent.sota_stop_review --variant before --repeat 1 --out src/evaluation/reports/eval-2026-10-14-sota-stop-before.json`
  và cùng lệnh `--variant after --repeat 3 --out src/evaluation/reports/eval-2026-10-14-sota-stop-after.json`.
  **48 lượt, không lượt lỗi.** Tiêu chí trạng thái/tool/lịch của bộ: baseline 6/7, sau 21/21.
- Baseline “Chán quá, không muốn đi nữa” → stop; sau 3/3 → rekindle, hủy consent. Từ chối tiếp và dừng rõ:
  không business tool/request nguồn/thẻ/nút/câu hỏi. `ko/k` hỏi trẻ em: 6/6 sau có lịch đúng ngày/người;
  `ko/không` từ chối lập lịch: 6/6 không dừng toàn bộ tư vấn; khám phá tiếp 3/3 trả một thẻ và không lập lịch.
- Các ca `ko/k` vốn đã đúng trong baseline; ghi là hồi quy, không coi là lỗi đã tái hiện trước sửa.
- JSON Schema `Draft202012Validator` + `FormatChecker`, bundle assistant-v2: **48/48** final khớp `AssistantV2Final`.
- Ruff `orc_v2.py` + `sota_stop_review.py`: PASS (đã sửa import, safe exception catch và subprocess trong async).
- `git diff --check`: PASS. Không đổi contract/mock nên không chạy validate_contract.py; đã kiểm schema trên
  toàn bộ response thực tế. Không chạy full suite, coverage toàn domain/application hoặc frontend.

## Còn lại / rủi ro

- Người dùng test lại trước khi tự commit. Backend đang chạy chưa được restart; cần nạp source mới khi test UI.
- Bộ đo gọi runtime/commit thật với tool qua HTTP; không phải kiểm route/SSE của assistant, browser, Redis hoặc
  archive Postgres. Các ca seed không được coi là hội thoại tự nhiên từ đầu.
- Khơi gợi là tùy chọn: ba lượt mất hứng sau sửa không tra sản phẩm mới; có lượt đáp ngắn, có lượt thêm ý tưởng
  nghỉ tại chỗ và một nút. Chưa kiểm thực tế nhánh giới thiệu một sản phẩm mới hoặc lịch cũ trước khi dừng.
- Không khẳng định chất lượng tổng thể/grounding ngôn ngữ/SLA từ bộ nhỏ này. Catalog không được đóng băng;
  model có thể đổi câu chữ. Ngày ca trẻ em cố định 17/10/2026, cần cập nhật ngày và dataset version khi chạy sau đó.
- Đề xuất nhịp lịch còn chờ chốt, ngoài phạm vi hai mục được chọn; không đổi PRD/source theo đề xuất đó.
