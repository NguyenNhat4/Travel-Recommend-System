# Agent nhớ đã cho xem gì: "rẻ hơn" của vé, state `shown`, khối ngữ cảnh chung (B1–B3)

- Ngày: 2026-10-12
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs
- Bị thay thế bởi: `2026-10-12-sua-plan-orchestrator-theo-review.md` (một phần: lý do của đơn vị giá trong dòng `facts`)

## Mục tiêu

B1–B3 của plan `docs/plan/2026-10-12-nho-ket-qua-da-xem.md`. Đây là phần hiện thực đúng PRD hiện hành, làm không cần chốt:

- **B1** — vé: hỏi "rẻ hơn nữa không" sau khi đã báo vé rẻ nhất thì nói rõ đây đã là vé rẻ nhất (AC-AGT-08). Chat thử
  M11: đã có lịch, "chuyến bay về mấy giờ" → "có chuyến nào rẻ hơn ko" lặp y hệt câu của ngày về.
- **B2** — trí nhớ "đã cho xem": working memory giữ sản phẩm vừa hiển thị (`architecture.md` §3 "Hội thoại").
- **B3** — mọi lời gọi LLM nhận "sản phẩm đã cho xem" (`architecture.md` §3 "Ngữ cảnh cho LLM"), gọn.

Lỗi gốc: "hà nội" → "ngoài ra còn gì nữa" (hoặc "đi rồi") trả lại đúng 4 thẻ cũ.

## File thay đổi

- `src/backend/app/agents/steps/fares.py` — sửa: `answer_text` xét `cheaper` trước nhánh "có ngày". Khi có `cheaper`:
  nói đã là vé rẻ nhất, nêu vé rẻ nhất cả đợt, không lặp khối "ngày X chưa có chuyến…".
- `src/backend/app/agents/steps/shown.py` — thêm:
  - `record` ghi sản phẩm response vừa hiện, mỗi cái một mã `#n` giữ suốt hội thoại, kèm dòng `facts` theo loại; đơn
    vị giá theo `priceUnit`;
  - `context` dựng khối `already_shown` ≤ 2.000 ký tự, kèm `current_plan` tóm lịch gần nhất theo mã;
  - `plan_line`.
- `src/backend/app/agents/steps/phase.py` — sửa: `shown` vào `CARRIED`.
- `src/backend/app/agents/state.py` — sửa: khai báo `shown`.
- `src/backend/app/agents/nodes.py` — sửa: `finalize_node` ghi `shown` từ response đã kiểm; `finalize_node_async` lưu nó.
- `src/backend/app/agents/steps/history.py` — sửa: `llm_context` thêm `already_shown` ngay sau `known_constraints`; thứ tự
  các khoá cũ giữ nguyên.
- `src/backend/app/agents/steps/prompts.py` — sửa:
  - `classify` liệt kê `already_shown`;
  - `extract` dặn `already_shown` chỉ để tham khảo, giá đã gợi ý không phải ngân sách.
- `src/backend/app/agents/steps/turn_notes.py`, `messages.py` — sửa: bỏ `NOTE_CARDS`; ghi chú lượt khám phá chỉ ghi số nơi
  ("giới thiệu 4 nơi ở Hà Nội (xem already_shown)"), tên nằm ở khối.
- `src/backend/tests/unit/agents/test_shown.py` — thêm: 13 test (ghi, mã, giới hạn, lịch, đơn vị giá, bản lưu cũ,
  finalize, lưu store, khối ngữ cảnh, vị trí khối trong payload).
- `src/backend/tests/unit/agents/test_fares_followups.py`, `test_fares_messy.py` — thêm: test "rẻ hơn" sau câu trả lời có
  ngày và sau chặng về (fail trên code cũ). Sửa test ghi chú khám phá (ghi số nơi).
- `src/backend/tests/unit/agents/behavior_snapshot/cassette.json`, `snapshot.json`, `tools.json.gz` — ghi lại bằng LLM
  thật (`inprocess`), vì payload mọi lời gọi LLM có thêm khối.
- `docs/spec/agent/langgraph-nodes.md` — sửa: bảng "Ngữ cảnh cho LLM" thêm `already_shown`; ghi số đo về thứ tự payload.
- `docs/spec/agent/state-fields.md` — sửa: thêm hàng `shown`.
- `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` — sửa: §6 ngữ cảnh LLM có sản phẩm đã cho xem; mọi lượt lưu
  `shown`.
- `docs/spec/agent/nghiep-vu/tu-van-ve-may-bay.md` — sửa: tách dòng "rẻ hơn nữa không".
- `docs/plan/2026-10-12-nho-ket-qua-da-xem.md` — sửa: trạng thái, các điểm làm khác thiết kế ở 4.1, thứ tự payload bị bác
  bỏ bằng số đo.

## Quyết định

- **B1, bằng chứng.** Snapshot `messy-M11` lượt 3 có đầu ra thô của LLM là `cheaper=true, return_leg=true`. Code đặt
  `start` = ngày về nên đi nhánh "có ngày" và bỏ qua `cheaper`.
- **B1, sửa.** "Đã là vé rẻ nhất" nói không điều kiện khi `cheaper` cùng tuyến.
  - Bản đầu chỉ nói khi vé rẻ nhất nằm trong thẻ của lượt liền trước. Snapshot M05 cho thấy điều kiện đó quá hẹp: vé rẻ
    nhất báo ở lượt 1, lượt 2 là "ngày khác".
  - Mọi câu trả lời vé cùng tuyến đều đã nêu vé rẻ nhất cả đợt.
- **B2.** `shown` ghi **một chỗ**: `finalize`, từ response đã qua kiểm tra, thay vì ba chỗ như plan. Chỉ thứ người dùng
  thật sự thấy mới được ghi; response lỗi giữ nguyên `shown`.
- **B2.** Mỗi mục lưu luôn dòng thông tin lúc hiện, thay vì tra lại `get_product_detail` mỗi lượt (tới 40 lời gọi).
  - Giá trong dòng ghi rõ là giá lúc gợi ý, kèm đơn vị theo `priceUnit` ("/khách", "/gói", "/đêm"), để câu "giá tính theo
    người hay theo gói" trả lời được từ ngữ cảnh.
  - Response vẫn chỉ lấy sản phẩm, giá từ tool của chính lượt (spec Itinerary §6 giữ nguyên).
- **B3, bác bỏ việc đưa tin nhắn xuống cuối payload bằng số đo.** Plan đề xuất đưa câu cuối của trợ lý và tin nhắn hiện tại
  xuống cuối mọi payload, để tránh *lost in the middle*.
  - Lần ghi snapshot đầu cho thấy `classify` đổi nhãn ở các câu hỏi vé.
  - Đo lặp `classify` với 4 biến thể: thứ tự cũ / mới × có / không có khối. Kết quả:
    - "vé nha trang đi phú quốc bao nhiêu" hỏi lại loại vé (AC-AGT-08) 24/24 lần ở thứ tự cũ, còn 10/24 khi tin nhắn ở
      cuối;
    - "đi đâu cũng được, miễn đắt nhất" sau một câu báo giá hiểu đúng 8/10, còn 4/10 khi tin nhắn ở cuối (2/10 khi thêm
      cả khối);
    - riêng khối `already_shown` (thứ tự cũ) không đổi kết quả: 20/30 cả hai;
    - "rẻ hơn nữa ko" (M05) và "rẻ hơn" sau chặng về (M11) đúng 12/12 ở mọi biến thể.
  - Bản cuối (thứ tự cũ + khối) đo lại: X02 16/16 như cũ; v5-SC-F 15/16 so với 11/16 khi chưa có khối.
  - Vì vậy giữ thứ tự cũ, chỉ thêm khối. Bỏ hàm `latest` và hoàn nguyên 5 file chỗ gọi (`classification.py`,
    `conversation.py`, `exploration.py`, `narration.py`, `tool_planning.py`) cùng các test đã sửa theo nó.
- **B3.** Chưa đưa `rejected_destinations`, `open_question` vào ngữ cảnh chung như plan. Hai khoá này chưa được đo với
  `classify`; `explore`, `converse` vẫn nhận `rejected_destinations` như trước.
- **B3.** `previous_selection` (kèm id) vẫn ở ngữ cảnh, vì `extract` và Similar cần id. Bỏ id khỏi ngữ cảnh LLM để ở B6–B7.
- **B3.** Chưa có nhãn "rẻ nhất/nhiều đánh giá nhất" trong dòng, vì response không mang `reasons`; để ở B6.
- **Chưa đổi:** cách chọn thẻ của lượt khám phá (`exploration.pick`, hai câu tìm cố định). Đó là B5, lệch PRD, đang chờ
  chốt ở `docs/prd/update/2026-10-12-orchestrator-va-kham-pha-llm.md`.
- **Sự cố khi ghi snapshot.** Lần ghi đầu, Postgres và Weaviate nhận lệnh tắt lúc 18:16:06. Không phải do phiên này; trên
  máy còn một phiên Claude khác cùng repo. Từ đó mọi `search_products` quá giờ 10 giây, và harness ghi cả lỗi
  `TOOL_TIMEOUT` vào cassette.
  - Xử lý: khôi phục `tools.json.gz` về HEAD rồi `docker compose up -d --wait postgres weaviate`.
  - Ghi lại cả 57 kịch bản, rồi bỏ khỏi cassette các bản ghi vừa không có ở HEAD vừa không được snapshot mới dùng.

## Kiểm tra

- **Test fail trước khi sửa:** 3 test "rẻ hơn" mới (`test_fares_followups`, `test_fares_messy`) fail trên code cũ. Lượt
  M11 tái hiện đúng: câu trả lời lặp y hệt.
- **Unit test nhanh:** `.venv/bin/python -m pytest -q src/backend/tests/unit/agents src/backend/tests/unit/domain` →
  2.039 passed trước khi ghi lại snapshot (chỉ 2 test snapshot fail).
- **Snapshot hành vi:**
  - Lệnh: `HF_HUB_OFFLINE=1 .venv/bin/python -m src.backend.tests.unit.agents.behavior_snapshot.record` (`inprocess`,
    Postgres + Weaviate local, LLM thật), chạy cả 57 kịch bản, 166 lượt, 0 lời gọi tool quá giờ.
  - Sau đó bỏ bản ghi rác: LLM 359, tool 35.
  - `test_behavior_snapshot.py`: 4 passed.
- **So snapshot mới với HEAD theo từng lượt:** 105 lượt giống hệt, 16 lượt chỉ đổi chữ, 45 lượt có thay đổi, trong đó 28 lượt
  đổi ở mức node, thẻ hoặc lịch.
  - **Đúng mục tiêu:**
    - M11 lượt 3 và M05 lượt 3: "Đây đã là vé rẻ nhất…";
    - X13 lượt 2 "chán, đi rồi": không còn 4 thẻ Nha Trang cũ, trợ lý gợi nơi khác.
  - **Lịch khác:** 15 lượt lập lịch có sản phẩm khác, vì planner nhận payload mới nên tìm khác đi. Vẫn qua `finalize`,
    grounding giữ.
  - **Ba lượt `classify` đổi nhãn theo hướng xấu.** Đo lặp 12 lần cho thấy đây là dao động lấy mẫu, không phải hồi quy:
    | Lượt | HEAD | Bản cuối |
    |---|---|---|
    | X10 "Đà Lạt có gì" → explore | 11/12 | 10/12 |
    | X01 lượt 6 "vé rẻ nhất là chuyến nào" → báo giá vé | 12/12 | 11/12 |
    | X02 lượt 2 "ngày 20/10 thì sao" → `vague` (sai) | 0/12 | 1/12 |

    Snapshot giữ đúng mẫu đã ghi, không lấy mẫu lại.
- **Đo lặp `classify`** (script tạm, không thêm vào repo; số liệu ở "Quyết định"): 4 ca × 4 biến thể × 10–16 lần, thêm 30
  lần cho v5-SC-F, 12 lần cho 3 lượt đổi nhãn.
- **Tái hiện bằng LLM thật** (`inprocess`, script ở mục 0 của plan), code cuối:
  - "hà nội" → "ngoài ra còn gì nữa": vẫn 4/4 thẻ cũ.
  - "cứ chọn đại" → "chán, đi rồi": không lặp; trợ lý bỏ Nha Trang, gợi Đà Lạt.
  - "hà nội" → "đi rồi": vẫn 4/4 thẻ cũ.
  - M11 ba lượt: lượt 3 "Đây đã là vé rẻ nhất…" (trước: lặp y hệt câu ngày về).
- **Cả bộ backend:** `WEAVIATE_URL=http://127.0.0.1:1 SEARCH_PREWARM=false HF_HUB_OFFLINE=1 .venv/bin/python -m pytest -q
  src/backend/tests/unit src/backend/tests/architecture src/backend/tests/contract` → 2.867 passed, 2 skipped.
- Không đổi contract hay mock nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- **Lỗi lặp 4 thẻ của lượt khám phá chưa hết.** "hà nội" → "ngoài ra còn gì nữa" và "hà nội" → "đi rồi" vẫn ra đúng 4 thẻ
  cũ, vì `pick()` chưa đổi. Cần B5 sau khi đề xuất được chốt.
- Một lần chạy "đi rồi", LLM viết link lồng "[Nếu muốn …, [Luxury Backpackers](product:…)". Đã thấy, chưa sửa, ngoài
  phạm vi B1–B3.
- Snapshot ghi lại bằng LLM thật nên một số lượt đổi nhãn hoặc đổi lịch do LLM dao động (danh sách ở "Kiểm tra").
