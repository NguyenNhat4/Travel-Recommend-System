# Golden dataset — Itinerary Agent

- Commit: `4a1a644`
- Chạy lúc: 2026-10-10T15:52:18.360042+00:00
- Model: `gpt-6-luna` · dataMode: `http` · mode: `dataset`
- productCount: 3183
- LangSmith project: `nhat-10-7`
- LLM giám khảo: `gpt-6-luna` (finding `[judge]`)

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 7 lượt tính được) |

Latency: p50=5176ms, p95=40316ms, max=46361ms (mục tiêu < 5000ms, không gate).

Tổng 28 lượt, PASS 25, FAIL 3.

## Lượt FAIL

### SC-A lượt 2 — 'không thích đi Nha Trang'
httpStatus=200 status=NEEDS_CLARIFICATION latency=14145ms
- [judge] không chấm được: OpenAIInvalidRequestError

### SC-MAIN lượt 2 — 'mình không biết đi đâu hết, mình ở nhà'
httpStatus=200 status=NEEDS_CLARIFICATION latency=6799ms
- [judge] không chấm được: OpenAIInvalidRequestError

### SC-MAIN lượt 8 — 'Ok, lên lịch Hà Nội luôn'
httpStatus=200 status=NEEDS_CLARIFICATION latency=7471ms
- [judge] không chấm được: OpenAIInvalidRequestError

## Đã loại

Điểm tham quan node `filter` bỏ vì trùng trước khi xếp lịch (AC-AGT-04).

| Case | Lượt | Bỏ | Trùng với | Do |
|---|---|---|---|---|
| SC-E | 1 | Vé Hạng Cổ Loa / Tặng Voucher Ẩm thực / Quà lưu niệm (`0d926cc0`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| SC-E | 1 | Vé Hạng Thăng Long / Tặng Voucher Ẩm thực / Quà lưu niệm (`aefa524b`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| SC-E | 1 | Vé Hạng Văn Lang / Tặng Voucher Ẩm thực / Quà lưu niệm (`e3a1d3bf`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| SC-E | 1 | Vé Hạng Cổ Loa / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`8d849029`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | llm |
| SC-E | 1 | Vé Hạng Thăng Long / Trải nghiệm Aquafield & Set Ẩm thực (`d65600c7`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| SC-E | 1 | Vé Hạng Thăng Long / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`5463024a`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | llm |
| SC-E | 1 | Vé Hạng Cổ Loa / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`c5cb2efb`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| SC-E | 1 | Vé Hạng Văn Lang / Trải nghiệm Aquafield & Set Ẩm thực (`cd1bbb38`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| SC-E | 1 | Vé Hạng Văn Lang / Trải nghiệm chèo thuyền Gondola & Voucher Ẩm thực (`83d01deb`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | llm |
| SC-E | 1 | Vé Hạng Thăng Long / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`37c3940f`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| SC-E | 1 | Vé Hạng Lạc Hồng / Tặng Voucher Ẩm thực / Quà lưu niệm (`d03bbb16`) | Vé Hạng Non Sông Gấm Vóc / Tặng Voucher Ẩm thực / Quà lưu niệm (`81f259e7`) | llm |
| SC-E | 1 | Vé Hạng Văn Lang / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`3443cb1f`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`6dc7bc9d`) | llm |
| SC-E | 1 | Vé Hạng Lạc Hồng / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`3409adbc`) | Vé Hạng Non Sông Gấm Vóc / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`973e1fad`) | llm |
| SC-H | 2 | Vé Hạng Thăng Long / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`5463024a`) | Vé Hạng Cổ Loa / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`8d849029`) | llm |
| SC-H | 2 | Vé Hạng Văn Lang / Trải nghiệm Aquafield & Set Ẩm thực (`cd1bbb38`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| SC-H | 2 | Vé Hạng Văn Lang / Trải nghiệm chèo thuyền Gondola & Voucher Ẩm thực (`83d01deb`) | Vé Hạng Cổ Loa / Trải nghiệm chèo thuyền Gondola & Ẩm thực tại Vinpalace (`8d849029`) | llm |
| SC-H | 2 | Vé Hạng Thăng Long / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`37c3940f`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
| SC-H | 2 | Vé Hạng Văn Lang / Trải nghiệm Gondola, Aquafield & Set Ẩm thực (`3443cb1f`) | Vé Hạng Cổ Loa / Trải nghiệm Aquafield & Set Ẩm thực (`1784b8a2`) | llm |
## Chạy lại SC-A, SC-MAIN có giám khảo

Lần chạy cả bộ ở trên bỏ biến `ITINERARY_LLM_REASONING_EFFORT` (đặt `none` trong môi trường container) khi chạy runner, nên LLM giám khảo lỗi `OpenAIInvalidRequestError` ở 3 lượt có `judge`; các kiểm tra tất định của 3 lượt đó đều đạt. Chạy lại hai case với môi trường gốc:

```
HF_HUB_OFFLINE=1 .venv/bin/python -m src.evaluation.agent.golden --dataset src/evaluation/datasets/agent_scenarios_v5.yaml \
    --api-base-url http://127.0.0.1:8020 --report-slug agent-scenarios-v5-judge --trace-project nhat-10-7 --only SC-A,SC-MAIN
```

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 3 lượt tính được) |

Latency: p50=4245ms, p95=8212ms, max=8154ms (mục tiêu < 5000ms, không gate).

Tổng 11 lượt, PASS 10, FAIL 1.

## Lượt FAIL

### SC-MAIN lượt 8 — 'Ok, lên lịch Hà Nội luôn'
httpStatus=200 status=NEEDS_CLARIFICATION latency=4245ms
- [judge] Trợ lý bắt đầu lập lịch Hà Nội và hỏi gộp các thông tin còn thiếu (số ngày, ngày đi, số người) trong một câu.: Trợ lý chỉ hỏi “Bạn muốn đi Hà Nội mấy ngày?”, chưa gộp ngày đi và số người.


## Bối cảnh và cách tái sinh số

- Backend local `inprocess` (Postgres + Weaviate + Redis bằng docker compose trong container), catalog snapshot 2026-09-30 seed `--as-of 2026-10-10 --seed 42` (11.718 sản phẩm, 3.183 search unit), embedding `intfloat/multilingual-e5-small` local; runner `dataMode: http` gọi backend `http://127.0.0.1:8020`.
- Lệnh cả bộ: `env -u ITINERARY_LLM_REASONING_EFFORT HF_HUB_OFFLINE=1 .venv/bin/python -m src.evaluation.agent.golden --dataset src/evaluation/datasets/agent_scenarios_v5.yaml --api-base-url http://127.0.0.1:8020 --report-slug agent-scenarios-v5 --trace-project nhat-10-7` (nên chạy không có `env -u`).
- Caveat: một lần chạy (không `--repeat`); bản `.json` không commit.
