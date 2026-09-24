# Golden dataset — Itinerary Agent

- Commit: `82d077f`
- Chạy lúc: 2026-09-24T10:17:46.067914+00:00
- Model: `gpt-4o-mini` · dataMode: `http` · mode: `dataset`
- productCount: None
- LangSmith project: `không bật`

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 77 lượt tính được) |

Latency: p50=6040ms, p95=11339ms, max=16014ms (mục tiêu < 5000ms, không gate).

Tổng 89 lượt, PASS 74, FAIL 15.

## Lượt FAIL

### G-006 lượt 1 — 'Hải Phòng 2 ngày'
httpStatus=200 status=NEEDS_CLARIFICATION latency=4890ms
- status='NEEDS_CLARIFICATION', kỳ vọng một trong ['COMPLETED', 'FALLBACK', 'NO_RESULTS']
- tool không chạy, mong ngược lại

### G-008 lượt 1 — 'Đà Lạt 3 ngày 2 đêm'
httpStatus=200 status=NEEDS_CLARIFICATION latency=6077ms
- status='NEEDS_CLARIFICATION', kỳ vọng một trong ['COMPLETED', 'FALLBACK']

### G-012 lượt 1 — 'Côn Đảo 7 ngày'
httpStatus=200 status=NO_RESULTS latency=6006ms
- status='NO_RESULTS', kỳ vọng một trong ['COMPLETED', 'FALLBACK']

### G-047 lượt 1 — 'đặt phòng và thanh toán giúp tôi'
httpStatus=200 status=NEEDS_CLARIFICATION latency=4917ms
- httpStatus=200, kỳ vọng 400
- errorCode=None, kỳ vọng 'VALIDATION_ERROR'

### G-051 lượt 1 — 'Nha Trang 3 ngày cho gia đình có trẻ nhỏ'
httpStatus=200 status=COMPLETED latency=6485ms
- lịch có 1 hoạt động, kỳ vọng ít nhất 3

### G-052 lượt 1 — 'Nha Trang 3 ngày, 2 người lớn 1 bé 5 tuổi'
httpStatus=200 status=COMPLETED latency=9406ms
- lịch có 1 hoạt động, kỳ vọng ít nhất 3

### G-053 lượt 1 — 'nha trang 3n2d'
httpStatus=200 status=COMPLETED latency=7034ms
- intent.startDate='2026-09-24', kỳ vọng None

### G-055 lượt 1 — 'đi Hà Nội từ 1/10 đến 3/10'
httpStatus=200 status=NO_RESULTS latency=7776ms
- status='NO_RESULTS', kỳ vọng một trong ['COMPLETED']
- lịch có 0 hoạt động, kỳ vọng ít nhất 3

### G-056 lượt 1 — 'Hà Nội 2 ngày ngân sách 5tr'
httpStatus=200 status=NO_RESULTS latency=6639ms
- status='NO_RESULTS', kỳ vọng một trong ['COMPLETED', 'FALLBACK']

### G-057 lượt 1 — 'Sa Pa 3 ngày, tôi không cần khách sạn vì ở nhà người quen'
httpStatus=200 status=COMPLETED latency=6368ms
- lịch có chỗ ở, mong ngược lại

### G-058 lượt 1 — 'Hà Nội 3 ngày'
httpStatus=200 status=NO_RESULTS latency=11134ms
- status='NO_RESULTS', kỳ vọng một trong ['COMPLETED', 'FALLBACK']

### G-058 lượt 2 — 'ngân sách tầm 3 triệu thôi'
httpStatus=200 status=NO_RESULTS latency=5925ms
- status='NO_RESULTS', kỳ vọng một trong ['COMPLETED', 'FALLBACK']

### G-059 lượt 2 — 'thêm 1 bé 6 tuổi đi cùng nhé, tổng 2 người lớn'
httpStatus=200 status=NO_RESULTS latency=6231ms
- status='NO_RESULTS', kỳ vọng một trong ['COMPLETED']
- lịch có 0 hoạt động, kỳ vọng ít nhất 3

### G-062 lượt 1 — '3 days in Hoi An for a couple'
httpStatus=200 status=COMPLETED latency=14263ms
- response chứa chuỗi cấm 'Tham quan theo khung giờ'
- response chứa chuỗi cấm 'Giá và trạng thái là snapshot'

### G-072 lượt 1 — 'Mũi Né 2 ngày'
httpStatus=422 status=UNSUPPORTED_DESTINATION latency=3478ms
- httpStatus=422, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Phan Thiết')
- intent.days không có (kỳ vọng 2)
