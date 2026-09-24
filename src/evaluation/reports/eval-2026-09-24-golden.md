# Golden dataset — Itinerary Agent

- Commit: `601f112`
- Chạy lúc: 2026-09-24T02:26:33.123996+00:00
- Model: `gpt-4o-mini` · dataMode: `http` · mode: `dataset+sweep`
- productCount: None
- LangSmith project: `không bật`

## Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 110 lượt tính được) |

Latency: p50=3810ms, p95=5296ms, max=8987ms (mục tiêu < 5000ms, không gate).

Tổng 124 lượt, PASS 113, FAIL 11.

## Lượt FAIL

### G-013 lượt 1 — 'tphcm 2 ngày'
httpStatus=200 status=NEEDS_CLARIFICATION latency=3624ms
- intent.destination='TPHCM', kỳ vọng 'TP. Hồ Chí Minh'

### G-047 lượt 1 — 'đặt phòng và thanh toán giúp tôi'
httpStatus=200 status=NEEDS_CLARIFICATION latency=5315ms
- httpStatus=200, kỳ vọng 400
- errorCode=None, kỳ vọng 'VALIDATION_ERROR'

### G-051 lượt 1 — 'Nha Trang 3 ngày cho gia đình có trẻ nhỏ'
httpStatus=200 status=COMPLETED latency=7584ms
- lịch có 1 hoạt động, kỳ vọng ít nhất 3

### G-052 lượt 1 — 'Nha Trang 3 ngày, 2 người lớn 1 bé 5 tuổi'
httpStatus=200 status=COMPLETED latency=3733ms
- lịch có 0 hoạt động, kỳ vọng ít nhất 3

### G-053 lượt 1 — 'nha trang 3n2d'
httpStatus=200 status=COMPLETED latency=3807ms
- intent.startDate='2026-09-24', kỳ vọng None

### G-055 lượt 1 — 'đi Hà Nội từ 1/10 đến 3/10'
httpStatus=200 status=COMPLETED latency=4488ms
- lịch có 0 hoạt động, kỳ vọng ít nhất 3

### G-056 lượt 1 — 'Hà Nội 2 ngày ngân sách 5tr'
httpStatus=200 status=NEEDS_CLARIFICATION latency=3701ms
- status='NEEDS_CLARIFICATION', kỳ vọng một trong ['COMPLETED', 'FALLBACK']

### G-058 lượt 2 — 'ngân sách tầm 3 triệu thôi'
httpStatus=200 status=COMPLETED latency=5057ms
- response có warning 'PRODUCT_DROPPED_EXCLUDED' không được phép

### G-059 lượt 2 — 'thêm 1 bé 6 tuổi đi cùng nhé, tổng 2 người lớn'
httpStatus=200 status=COMPLETED latency=6885ms
- lịch có 0 hoạt động, kỳ vọng ít nhất 3
- response có warning 'PRODUCT_DROPPED_EXCLUDED' không được phép

### G-062 lượt 1 — '3 days in Hoi An for a couple'
httpStatus=200 status=COMPLETED latency=4075ms
- response chứa chuỗi cấm 'Tham quan theo khung giờ'
- response chứa chuỗi cấm 'Giá và trạng thái là snapshot'

### G-072 lượt 1 — 'Mũi Né 2 ngày'
httpStatus=422 status=UNSUPPORTED_DESTINATION latency=3052ms
- httpStatus=422, kỳ vọng 200
- status=None, kỳ vọng một trong ['COMPLETED', 'FALLBACK']
- intent.destination không có (kỳ vọng 'Phan Thiết')
- intent.days không có (kỳ vọng 2)
