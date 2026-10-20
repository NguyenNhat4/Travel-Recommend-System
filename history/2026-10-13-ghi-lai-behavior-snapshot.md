# Ghi lại behavior snapshot của orchestrator sau khi đổi ORCHESTRATOR_PROMPT

- Ngày: 2026-10-13
- Tác giả: yêu cầu bởi người dùng / agent (Claude Code)
- Nhánh: release-mvp-v2
- Trạng thái: dang dở
- Phạm vi: agent
- Bị thay thế bởi: 2026-10-13-bo-kiem-tra-snapshot-hanh-vi.md

## Mục tiêu

CI `Backend CI` (run 38369764081, job 115203563662) fail ở `Run backend tests`: hai test trong
`src/backend/tests/unit/agents/test_behavior_snapshot.py` báo `CassetteMiss`. Cassette khoá theo hash system prompt và payload.
Commit `cab5e728` đã đổi `ORCHESTRATOR_PROMPT` (`src/backend/app/agents/steps/prompts.py`: thêm luật `requested_count`,
`scope_mode`, `excluded_destinations`), nhưng cassette và snapshot không được ghi lại. Với prompt của `a50c5e62`, 59/170 lượt
orchestrator khớp cassette; với prompt hiện tại, 0/170 khớp. Mục tiêu: ghi lại cassette và snapshot theo đúng quy trình trong
`behavior_snapshot/record.py`.

## File thay đổi

- `src/backend/tests/unit/agents/behavior_snapshot/cassette.json` — sửa: thêm khoá LLM cho payload mới (347 → 762 khoá).
- `src/backend/tests/unit/agents/behavior_snapshot/tools.json.gz` — sửa: thêm kết quả tool cho lời gọi mới (213 khoá).
- `src/backend/tests/unit/agents/behavior_snapshot/snapshot.json` — sửa: hành vi của 63 kịch bản, 191 lượt, ghi lại từ LLM thật.
- `history/2026-10-13-ghi-lai-behavior-snapshot.md` — thêm: entry này.

## Quyết định

- Ghi bằng `record` không có `--fresh`: giữ mọi khoá cũ, chỉ gọi LLM và tool cho khoá còn thiếu.
- Chạy trong image `Dockerfile.backend` (torch `2.14.1` và e5-small đúng pin, như CI). Máy host là macOS Intel, không cài được
  `torch==2.14.1` từ PyPI.
- Dùng Postgres local đã seed sẵn (`vota`, 10.320 sản phẩm), không seed lại. Không dùng `DATABASE_URL`, `CDP_DATABASE_URL`,
  `WEAVIATE_URL`, Redis trong `.env` vì trỏ tới đường hầm staging và Weaviate Cloud. Ghi đè các biến này trỏ về local.
- Weaviate local dùng volume mới `vota_record_weaviate` (port 8090). Không xoá volume `travel-recommendation-product_weaviate_data`
  cũ (đang lỗi join cluster) để tránh mất dữ liệu local.
- Tắt LangSmith tracing khi chạy (`LANGSMITH_TRACING=false`) để prompt và dữ liệu hội thoại không gửi ra ngoài.
- Index lại vector e5-small: `embed_products` 2.897/2.897 search unit vào collection `ProductE5Small`.

## Kiểm tra

- `embed_products`: exit 0, 2.897 vector, đếm Weaviate khớp.
- `behavior_snapshot.record`: exit 0, `recorded 63 scenarios, 191 turns, llm cassette 762 entries, tool cassette 213 entries`,
  không kịch bản nào bị từ chối.
- `pytest src/backend/tests/unit/agents/test_behavior_snapshot.py`: 4 passed.
- `pytest src/backend/tests`: 2973 passed, 40 skipped, 3 xfailed.
- Không chạy `validate_contract.py`: không đổi contract.

## Còn lại / rủi ro

Snapshot mới ghi lại hành vi xấu đi so với snapshot cũ. Chưa được chấp nhận, không nên coi là baseline tốt:

- 3 lượt trả HTTP 500 `ITINERARY_VALIDATION_FAILED` (cũ: 0): `X01-plan-doi` lượt 4, `X11-dai-ngay` lượt 3, `messy-M05` lượt 4.
  Nguyên nhân: orchestrator chạy `execute` lặp đủ 3 vòng (`ROUND_LIMIT`) rồi fallback.
- 19 sự kiện dừng do `ROUND_LIMIT` (cũ: 0); sự kiện `TOOL_LIMIT` không đổi (6), trong đó 4 sự kiện kèm fallback.
- 72 lượt fallback do grounding (cũ: 1). Đếm lỗi vi phạm ở gatekeep trên replay: `raw_product_number` 65,
  `undeclared_question` 58, `references_not_retrieved` 1. Prompt mới làm LLM ghi số thô thay vì placeholder `[[price:#n]]`
  và hỏi câu không khai báo. Chưa xác định luật prompt nào gây ra từng loại.
- Snapshot dùng model trong `.env` (`MODEL_NAME=gpt-4o-mini`). Nếu tác giả ghi bằng model khác thì các khoá cũ vẫn khớp, nhưng
  đây là điểm cần xác nhận.
- Lỗi `get_product_detail` `PRODUCT_NOT_FOUND` 404 là kết quả tool thật được ghi vào cassette, không phải lỗi môi trường.
- Log nền có `booking.reconcile.loop_failed`: DB local thiếu bảng `app.payments`. Schema local có thể đã cũ so với
  migration; không ảnh hưởng replay.
- Trước khi commit, cần người review `snapshot.json` (diff khoảng 100 nghìn dòng) và quyết định: chấp nhận baseline này hay sửa
  prompt rồi ghi lại.
