# Golden dataset — Itinerary Agent

- Commit: `eddb909`
- Chạy lúc: 2026-10-05T06:39:22.859546+00:00
- Model: `gpt-6-luna` · dataMode: `http` · mode: `dataset`
- productCount: 3183
- LangSmith project: `nhat-10-1`
- LLM giám khảo: `gpt-6-luna` (finding `[judge]`)

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 12 lượt tính được) |

Latency: p50=9222ms, p95=14565ms, max=14263ms (mục tiêu < 5000ms, không gate).

Tổng 12 lượt, PASS 9, FAIL 3.

## Lượt FAIL

### TC-10 lượt 3 — 'không biết'
httpStatus=200 status=COMPLETED latency=14263ms
- status='COMPLETED', kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'startDate', có []
- missingFields thiếu 'party', có []
- missingFields thiếu 'budget', có []
- tool có chạy, mong ngược lại
- không có clarificationForm
- [judge] Trợ lý không hỏi lại ngày đi, số người, ngân sách bằng câu chữ y hệt lượt trước; nó mời người dùng chọn hoặc giữ giá trị gợi ý trên form.: Trợ lý không mời chọn hoặc giữ giá trị gợi ý trên form; câu trả lời chỉ nói “Ngày khởi hành, số người và ngân sách chưa được cung cấp”.

### TC-10 lượt 3 — 'không biết'
httpStatus=200 status=COMPLETED latency=10545ms
- status='COMPLETED', kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'startDate', có []
- missingFields thiếu 'party', có []
- missingFields thiếu 'budget', có []
- tool có chạy, mong ngược lại
- không có clarificationForm
- [judge] Trợ lý không hỏi lại ngày đi, số người, ngân sách bằng câu chữ y hệt lượt trước; nó mời người dùng chọn hoặc giữ giá trị gợi ý trên form.: Trợ lý không hỏi lại bằng câu chữ y hệt, nhưng cũng không mời chọn hoặc giữ giá trị gợi ý trên form.

### TC-10 lượt 3 — 'không biết'
httpStatus=200 status=COMPLETED latency=13401ms
- status='COMPLETED', kỳ vọng một trong ['NEEDS_CLARIFICATION']
- missingFields thiếu 'startDate', có []
- missingFields thiếu 'party', có []
- missingFields thiếu 'budget', có []
- tool có chạy, mong ngược lại
- không có clarificationForm
- [judge] Trợ lý không hỏi lại ngày đi, số người, ngân sách bằng câu chữ y hệt lượt trước; nó mời người dùng chọn hoặc giữ giá trị gợi ý trên form.: Trợ lý không mời chọn hoặc giữ giá trị gợi ý trên form; câu trả lời chỉ đưa ra “Lịch trình 3 ngày ở Đà Nẵng”.
