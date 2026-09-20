# Rubric đánh giá Itinerary Agent

> Mục đích: chấm nhanh agent bằng bằng chứng thực thi. OpenAPI là nguồn sự thật cho API.

## 1. Luồng phải đúng

```text
intake → classify
  ├─ chào hỏi/gợi ý chung/thiếu thông tin → answer (LLM) → finalize
  ├─ đủ destination + days → tool → evaluate → answer (LLM) → finalize
  └─ lỗi → retry hoặc dead_letter → finalize
```

- `classify` dùng LLM structured output.
- `answer` dùng LLM cho câu trả lời hội thoại và lịch trình bình thường.
- Thiếu `destination` hoặc `days`: hỏi tiếp, không gọi tool sản phẩm.
- Chào hỏi/gợi ý chung chỉ dẫn người dùng vào lập lịch; không biến agent thành trợ lý đa mục đích.
- LLM lỗi được dùng fallback có kiểm soát.

## 2. Thang điểm — 100

| Nhóm | Điểm | Điều kiện đạt |
|---|---:|---|
| Graph và state | 15 | Route đúng, state có kiểu, graph kết thúc hữu hạn, không lưu secret/client/model. |
| LLM | 20 | `classify`, tool planning và `answer` dùng structured output; output sai được chặn hoặc fallback. |
| Tool và API | 15 | Chỉ gọi Search/Recommendation qua port; arguments hợp lệ; FastAPI trả đúng OpenAPI. |
| Grounding | 25 | ID, tên, giá và điểm đến khớp dữ liệu tool; không bịa sản phẩm; backend tính tổng. |
| Hội thoại | 10 | Giữ intent theo conversation; thiếu dữ liệu thì hỏi; lời chào/gợi ý chung đi qua LLM `answer`. |
| Test và demo | 15 | Có unit/integration/eval thật, trace node, latency và hướng dẫn chạy không chứa secret. |
| **Tổng** | **100** | |

Mỗi tiêu chí chỉ nhận đủ điểm khi có test/trace chứng minh. Chưa chạy là `NOT_RUN`; thiếu dependency là `BLOCKED`.

## 3. Checklist bắt buộc

- [ ] `xin chào` chạy `intake → classify → answer → finalize`.
- [ ] `gợi ý cho tôi một chuyến đi` được LLM hỏi thêm thông tin.
- [ ] Thiếu điểm đến hoặc số ngày không gọi Search/Recommendation/Catalog.
- [ ] Đủ điểm đến và số ngày mới retrieval sản phẩm.
- [ ] Mọi sản phẩm trả về tồn tại trong kết quả tool của cùng run.
- [ ] Không sửa tên, giá, destination hoặc availability từ nguồn.
- [ ] Search rỗng trả `NO_RESULTS`, không bịa dữ liệu.
- [ ] LLM composition lỗi chỉ trả grounded fallback hoặc lỗi chuẩn.
- [ ] Retry tối đa một lần và không retry lỗi 400/401.
- [ ] Không log prompt, JWT, API key hoặc raw graph state.
- [ ] `context.language` được dùng; mặc định `vi`.
- [ ] Response và HTTP status hợp lệ theo OpenAPI.

## 4. Không đạt ngay nếu

- Bịa hoặc sửa sản phẩm, giá hay quyền lợi.
- Trả `COMPLETED` khi grounding/validation thất bại.
- Gọi tool trước khi có `destination` và `days`.
- Lời chào hoặc gợi ý chung bỏ qua LLM `answer`.
- Cam kết tồn kho, giá cuối hoặc ngân sách khi chỉ có snapshot.
- Thực hiện booking/cart hoặc tool ngoài allowlist.
- Làm lộ secret, dữ liệu người dùng hoặc bị prompt injection điều khiển.
- Retry vô hạn hoặc che lỗi thành thành công.

## 5. Bằng chứng cần lưu

- Kết quả từng scenario và node trace.
- Tool name, arguments và product IDs đã trả về.
- Response cuối và kết quả contract/grounding validation.
- Model/version, commit, dataset, thời gian chạy và latency.
- Phân biệt rõ: stub, model thật + fixture, hay model thật + service thật.

Mục tiêu chính: grounding **100%** và latency p95 toàn agent **dưới 5 giây**. Fixture chỉ chứng minh luồng local, không chứng minh availability hoặc hiệu năng production.
