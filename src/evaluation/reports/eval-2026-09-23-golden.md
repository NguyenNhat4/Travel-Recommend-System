# Golden dataset — Itinerary Agent

- Commit: `d996beb`
- Chạy lúc: 2026-09-23T14:34:03.943285+00:00
- Model: `gpt-4o-mini` · dataMode: `http` · mode: `dataset+sweep`
- productCount: None
- LangSmith project: `claude-golden`

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 86 lượt tính được) |

Latency: p50=4392ms, p95=5564ms, max=7328ms (mục tiêu < 5000ms, không gate).

Tổng 92 lượt, PASS 91, FAIL 1.

## Lượt FAIL

### G-013 lượt 1 — 'tphcm 2 ngày'
httpStatus=200 status=NEEDS_CLARIFICATION latency=3290ms
- intent.destination='TPHCM', kỳ vọng 'TP. Hồ Chí Minh'
