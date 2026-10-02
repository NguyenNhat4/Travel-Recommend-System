# Golden dataset — Itinerary Agent

- Commit: `ea944b9`
- Chạy lúc: 2026-10-02T08:41:49.995829+00:00
- Model: `gpt-4o-mini` · dataMode: `http` · mode: `dataset`
- productCount: 3183
- LangSmith project: `nhat-agent-tc`
- LLM giám khảo: `gpt-4o-mini` (finding `[judge]`)

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 27 lượt tính được) |

Latency: p50=5894ms, p95=13707ms, max=14163ms (mục tiêu < 5000ms, không gate).

Tổng 27 lượt, PASS 27, FAIL 0.

## Lượt FAIL

Không có.