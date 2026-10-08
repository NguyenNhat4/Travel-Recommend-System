# Golden dataset — Itinerary Agent

- Commit: `95dfc8c`
- Chạy lúc: 2026-10-02T09:04:39.129052+00:00
- Model: `gpt-4o-mini` · dataMode: `http` · mode: `dataset`
- productCount: 3183
- LangSmith project: `nhat-agent-tc`
- LLM giám khảo: `gpt-4o-mini` (finding `[judge]`)

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 9 lượt tính được) |

Latency: p50=1390ms, p95=14737ms, max=15242ms (mục tiêu < 5000ms, không gate).

Tổng 27 lượt, PASS 8, FAIL 19.

## Lượt FAIL

### TC-03 lượt 3 — 'ngày 15/10, 2 người lớn'
httpStatus=200 status=COMPLETED latency=13979ms
- [judge] không chấm được: TimeoutError

### TC-01 lượt 1 — 'Lên lịch trình 1 ngày tại Hà Nội, bắt đầu từ ngày 2026-10-02, cho 2 người lớn, ngân sách khoảng 1 triệu.'
httpStatus=503 status=LLM_UNAVAILABLE latency=1517ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Hà Nội')
- intent.days không có (kỳ vọng 1)
- intent.startDate không có (kỳ vọng '2026-10-02')
- intent.party.adults không có (kỳ vọng 2)

### TC-01 lượt 2 — 'Đổi ngày'
httpStatus=503 status=LLM_UNAVAILABLE latency=1420ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- intent.startDate không có (kỳ vọng '2026-10-02')
- [judge] không chấm được: OpenAIConnectionError

### TC-01 lượt 3 — 'Ngày 14 tháng 10'
httpStatus=503 status=LLM_UNAVAILABLE latency=1338ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Hà Nội')
- intent.days không có (kỳ vọng 1)
- intent.startDate không có (kỳ vọng '2026-10-14')
- intent.party.adults không có (kỳ vọng 2)
- [judge] không chấm được: OpenAIConnectionError

### TC-01 lượt 4 — 'À nhầm ngày 15 tháng 10'
httpStatus=503 status=LLM_UNAVAILABLE latency=1255ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Hà Nội')
- intent.days không có (kỳ vọng 1)
- intent.startDate không có (kỳ vọng '2026-10-15')
- intent.party.adults không có (kỳ vọng 2)
- [judge] không chấm được: OpenAIConnectionError

### TC-02 lượt 1 — 'Mình muốn một chuyến nghỉ dưỡng, ưu tiên thư giãn và nghỉ ngơi.'
httpStatus=503 status=LLM_UNAVAILABLE latency=1390ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'destination', có []
- missingFields thiếu 'days', có []

### TC-02 lượt 2 — 'ko biết đi đâu'
httpStatus=503 status=LLM_UNAVAILABLE latency=1285ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'destination', có []
- không có clarificationForm
- [judge] không chấm được: OpenAIConnectionError

### TC-03 lượt 1 — 'Mình muốn một chuyến nghỉ dưỡng, ưu tiên thư giãn và nghỉ ngơi. 1 ngày 2 đêm'
httpStatus=503 status=LLM_UNAVAILABLE latency=1265ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'destination', có []

### TC-03 lượt 2 — 'Đà nẵng'
httpStatus=503 status=LLM_UNAVAILABLE latency=1282ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- intent.destination không có (kỳ vọng 'Đà Nẵng')

### TC-03 lượt 3 — 'ngày 15/10, 2 người lớn'
httpStatus=503 status=LLM_UNAVAILABLE latency=1351ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK', 'NO_RESULTS']
- intent.destination không có (kỳ vọng 'Đà Nẵng')
- intent.startDate không có (kỳ vọng '2026-10-15')
- intent.party.adults không có (kỳ vọng 2)
- [judge] không chấm được: OpenAIConnectionError

### TC-01 lượt 1 — 'Lên lịch trình 1 ngày tại Hà Nội, bắt đầu từ ngày 2026-10-02, cho 2 người lớn, ngân sách khoảng 1 triệu.'
httpStatus=503 status=LLM_UNAVAILABLE latency=1436ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Hà Nội')
- intent.days không có (kỳ vọng 1)
- intent.startDate không có (kỳ vọng '2026-10-02')
- intent.party.adults không có (kỳ vọng 2)

### TC-01 lượt 2 — 'Đổi ngày'
httpStatus=503 status=LLM_UNAVAILABLE latency=1368ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- intent.startDate không có (kỳ vọng '2026-10-02')
- [judge] không chấm được: OpenAIConnectionError

### TC-01 lượt 3 — 'Ngày 14 tháng 10'
httpStatus=503 status=LLM_UNAVAILABLE latency=1257ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Hà Nội')
- intent.days không có (kỳ vọng 1)
- intent.startDate không có (kỳ vọng '2026-10-14')
- intent.party.adults không có (kỳ vọng 2)
- [judge] không chấm được: OpenAIConnectionError

### TC-01 lượt 4 — 'À nhầm ngày 15 tháng 10'
httpStatus=503 status=LLM_UNAVAILABLE latency=1365ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Hà Nội')
- intent.days không có (kỳ vọng 1)
- intent.startDate không có (kỳ vọng '2026-10-15')
- intent.party.adults không có (kỳ vọng 2)
- [judge] không chấm được: OpenAIConnectionError

### TC-02 lượt 1 — 'Mình muốn một chuyến nghỉ dưỡng, ưu tiên thư giãn và nghỉ ngơi.'
httpStatus=503 status=LLM_UNAVAILABLE latency=1496ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'destination', có []
- missingFields thiếu 'days', có []

### TC-02 lượt 2 — 'ko biết đi đâu'
httpStatus=503 status=LLM_UNAVAILABLE latency=1211ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'destination', có []
- không có clarificationForm
- [judge] không chấm được: OpenAIConnectionError

### TC-03 lượt 1 — 'Mình muốn một chuyến nghỉ dưỡng, ưu tiên thư giãn và nghỉ ngơi. 1 ngày 2 đêm'
httpStatus=503 status=LLM_UNAVAILABLE latency=1335ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'destination', có []

### TC-03 lượt 2 — 'Đà nẵng'
httpStatus=503 status=LLM_UNAVAILABLE latency=1309ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['NEEDS_CLARIFICATION']
- intent.destination không có (kỳ vọng 'Đà Nẵng')

### TC-03 lượt 3 — 'ngày 15/10, 2 người lớn'
httpStatus=503 status=LLM_UNAVAILABLE latency=1238ms
- httpStatus=503, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK', 'NO_RESULTS']
- intent.destination không có (kỳ vọng 'Đà Nẵng')
- intent.startDate không có (kỳ vọng '2026-10-15')
- intent.party.adults không có (kỳ vọng 2)
- [judge] không chấm được: OpenAIConnectionError
