# Thử sửa ORCHESTRATOR_PROMPT để giảm grounding và vòng lặp, không giữ thay đổi

- Ngày: 2026-10-13
- Tác giả: người dùng yêu cầu / agent (Claude Code)
- Nhánh: release-mvp-v2
- Trạng thái: dang dở
- Phạm vi: agent

## Mục tiêu

Entry `history/2026-10-13-ghi-lai-behavior-snapshot.md` ghi baseline mới có 3 lỗi 500 `ITINERARY_VALIDATION_FAILED`, 19
dừng `ROUND_LIMIT`, 72 fallback grounding. Mục tiêu của lần thử: sửa `ORCHESTRATOR_PROMPT` để giảm vi phạm grounding
(`raw_product_number`, `undeclared_question`) và vòng lặp `execute`, rồi ghi lại snapshot.

## File thay đổi

Không có thay đổi giữ lại. Repo quay về trạng thái của entry trước:

- `src/backend/app/agents/steps/prompts.py` — thử sửa rồi hoàn tác (`git checkout`), diff rỗng.
- `src/backend/tests/unit/agents/behavior_snapshot/{cassette.json,snapshot.json,tools.json.gz}` — ghi lần 2 rồi khôi phục
  về bản lần 1 (đã kiểm `cmp`).

Bản vá và artifact lần 2 chỉ lưu trong scratchpad của phiên làm việc, không nằm trong repo.

## Quyết định

- Lần 2 thêm 4 luật vào prompt: cấm dấu `?` trong `answer.message`; không khai lại việc đã có trong `results`; cấm số có đơn vị
  dù đã nằm trong facts (ngày viết bằng chữ); không nêu giờ/giá/sao/đánh giá từ trí nhớ. Các luật này đã có trong PRD
  (FR-AGT-04, NFR-REL-01), không lệch PRD.
- Kết quả lần 2 (ghi bằng `record` không `--fresh`, 414 khoá LLM mới) xấu hơn ở chỉ số chính, nên không giữ:

| Chỉ số | Lần 1 (prompt gốc) | Lần 2 (prompt thêm luật) |
|---|---|---|
| Vi phạm grounding (đếm trên replay) | 124 | 140 |
| `raw_product_number` | 65 | 74 |
| `undeclared_question` | 58 | 64 |
| `unknown_placeholder` | 0 | 2 |
| Sự kiện `ROUND_LIMIT` | 19 | 14 |
| Sự kiện `TOOL_LIMIT` | 6 | 11 |
| Lượt HTTP 500 | 3 | 2 |
| Sự kiện fallback | 95 | 105 |

- LLM bỏ qua luật placeholder ngay cả khi luật nằm trong prompt: vẫn viết `4.4 điểm (363 đánh giá)`, `1.850.000 ₫/đêm`,
  `mở cửa từ 06:00–18:00`, và nêu giờ mở cửa không có trong dữ liệu.
- Hai lỗi 500 còn lại (lần 2) có cùng nguyên nhân: `explore_grounding` trong `validation._explore_issues`. Thẻ fallback lấy từ
  trí nhớ lượt trước khớp sản phẩm nhưng khác `availableFrom`/`availableTo` so với bản tóm tắt của lượt này. Đây là vấn đề của
  code (so khớp dữ liệu giữa lượt cũ và lượt mới), không phải của prompt. Chưa sửa.
- Orchestrator đang chạy bằng `MODEL_NAME=gpt-4o-mini` (`.env` không đặt `ITINERARY_ORCHESTRATOR_MODEL`). PRD yêu cầu model
  riêng cho orchestrator. Baseline hiện tại có thể không đại diện cho model dùng thật.

## Kiểm tra

- Unit agent và domain (không gồm snapshot, khi prompt đã sửa): 2045 passed, 3 xfailed.
- `test_behavior_snapshot.py` với artifact lần 1 (đã khôi phục): 4 passed.
- Không chạy `validate_contract.py`: không đổi contract.

## Còn lại / rủi ro

- Quyết định cần người dùng: (a) chọn model cho orchestrator (đặt `ITINERARY_ORCHESTRATOR_MODEL` rồi ghi lại), hoặc (b) giữ
  baseline lần 1 và coi các lỗi trên là nợ kỹ thuật đã ghi rõ.
- Sửa `explore_grounding` cần quyết định: cửa sổ đặt chỗ nào là chuẩn cho thẻ fallback (cửa sổ lúc được hiện hay cửa sổ của
  lượt này). Thay đổi luật kiểm grounding phải đi qua người review, không tự sửa trong test.
- Vi phạm `raw_product_number` không giảm bằng prompt với model hiện tại. Nếu cần chặn cứng, phải thiết kế ở code (thay số
  bằng placeholder khi khớp chắc chắn), vì đây là quyết định về grounding.
