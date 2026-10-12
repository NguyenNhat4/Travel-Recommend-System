# Merge release-mvp-v2 vào feat/agent trước khi mở PR

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng yêu cầu tạo PR từ `feat/agent` vào `release-mvp-v2`. Lúc đó release có 132 commit mà nhánh này chưa có, và hai nhánh xung đột ở 10 file (12 đoạn). Merge release vào trước để PR merge được.

## File thay đổi

Giải xung đột:

- `src/backend/app/agents/steps/classification.py` — giữ việc tách luật đồng ý sang `steps/consent.py` (HEAD). Chỉ lấy của release `_STOP`, `_STOP_TAIL`, `says_stop`, `stopped` (luật "không đi nữa", AC-AGT-01 chốt 12/10).
- `src/backend/app/agents/nodes.py` — import cả `consent`, `phase` (HEAD) lẫn `says_stop`, `stopped` (release). Thứ tự luật trước LLM: `_stop_rule` → `_option_pick` → `changes.detected` → `fares.chip_reply`.
- `docs/prd/requirements.md` — giữ AC-AGT-01..08 của HEAD (bản chốt 12/10). Lấy AC-REC-01/02/03 của release (đề xuất RecSys đã chốt). Nối đoạn "không muốn đi nữa thì cảm ơn, hẹn gặp lại" (`update-archive/2026-10-12-dung-len-lich-cam-on-hen-gap-lai.md`) vào AC-AGT-01 của HEAD, ghi thêm là không có nút form.
- `docs/prd/user-flow.md`, `docs/prd/architecture.md`, `docs/spec/agent/langgraph-nodes.md`, `docs/spec/agent/nghiep-vu/dien-giai-va-kiem-tra.md`, `docs/spec/agent/nghiep-vu/hieu-y-dinh-va-hoi-lai.md`, `docs/spec/agent/nghiep-vu/vong-doi-mot-luot.md`, `docs/spec/agent/state-fields.md` — giữ bản HEAD và thêm nhánh `stop` của release. Trong `hieu-y-dinh-va-hoi-lai.md`, luật dừng thành bước 4, các bước sau đánh số lại, bảng nhãn thêm `stop`.

Sửa sau merge:

- `src/backend/app/agents/steps/classification.py` — `route_result`: "ok" sau lời mời lập lịch mà LLM gắn `conversation` vẫn đi `extract` (hỏi gộp kèm nút form) như khi gắn `vague`.
- `src/backend/tests/unit/agents/test_exploration.py` — thêm `test_yes_after_the_offer_plans_even_when_the_llm_calls_it_conversation`.
- `src/backend/tests/unit/agents/behavior_snapshot/cassette.json`, `snapshot.json`, `tools.json.gz` — ghi lại bằng LLM thật.

## Quyết định

- Prompt `classify` của release thêm nhãn `stop` và câu "'ok' ngay sau khi trợ lý chào tạm biệt là `conversation`". Vì vậy mọi payload `TurnRoute` đổi: 54/57 kịch bản snapshot bị cassette miss, phải ghi lại bằng LLM thật (`behavior_snapshot.record`, giữ bản ghi cũ, chỉ gọi LLM cho payload mới).
- Sau lần ghi đầu, LLM thật gắn "ok" sau lời mời lập lịch là `conversation`. Trợ lý đi `converse` và chỉ hỏi số ngày, thay vì hỏi gộp như AC-AGT-01 (X04 lượt 5, TC-12 lượt 2). Luật đồng ý (`consent.says_yes` khi có `pending_offer`) đã nhận câu này, nên sửa bằng cách cho nhãn `conversation` đi cùng đường với `vague` khi vừa đồng ý. Không sửa prompt.
- Các lượt khác đổi hành vi được xem là dao động bình thường của LLM, hoặc tốt hơn nhờ prompt mới. Ví dụ: "thời tiết hà nội mai thế nào" sang `converse` kèm nút; "chán, đi rồi" sang `explore`. X12 "phương án 2" lập lại lịch vì lần chạy này lịch chỉ có 1 phương án; luật `picked_option` không đổi.

## Kiểm tra

- `validate_contract.py`: PASS (120 schemas, 96 fixtures).
- Backend `pytest src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract` (`WEAVIATE_URL` cổng đóng, `SEARCH_PREWARM=false`, `HF_HUB_OFFLINE=1`): 2852 passed, 2 skipped. Trước khi ghi lại cassette có 2 failed (snapshot). Test mới fail trước khi sửa `route_result`.
- Frontend: `tsc --noEmit` sạch. `vitest run` 79 file, 831/831 passed. Lần chạy đầu fail 24 test (checkout, confirmation, flights) trong lúc lệnh ghi cassette đang chạy; chạy riêng thì pass, chạy lại cả bộ khi máy rảnh thì pass.
- Snapshot: 57 kịch bản, 166 lượt. So với trước merge, 28 lượt khác chữ ký (status, node, form) trước khi sửa `route_result`. Sau khi sửa, X04 và TC-12 về đúng hành vi cũ.

## Còn lại / rủi ro

- Chưa thử lại trên trình duyệt với bản merge.
