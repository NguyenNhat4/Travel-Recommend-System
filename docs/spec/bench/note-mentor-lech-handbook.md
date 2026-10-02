# Ghi chú gửi mentor: ba điểm lệch so với handbook

- Ngày soạn: 2026-09-29 · Người soạn: nhóm Search/RecSys (bench) · Trạng thái: chờ mentor xác nhận bằng văn bản
- Phục vụ: **FR-SRC-02**, **NFR-PERF-01**, **NFR-PERF-03** (`docs/prd/requirements.md`); `docs/prd/architecture.md` §2, §4, §5.
- Điều kiện của checklist bench: `docs/spec/bench/search-eval-checklist.md` mục "Mentor xác nhận bằng văn bản việc lệch handbook ở 3 mục".

## Bối cảnh

Bản handbook gốc (`recsys-internship-handbook-v3`) chọn Java 21 + Spring Boot, PostgreSQL + pgvector, và embedding ONNX chạy trong JVM. Ngày 16/09 nhóm đã sửa bản handbook trong repo sang Python + FastAPI + sentence-transformers chạy cục bộ (commit `e33bdb6`). Bản trong repo vẫn ghi pgvector và embedding cục bộ. Vì vậy chúng em liệt kê cả ba điểm so với bản gốc, để mentor xác nhận dù đang dùng bản nào.

## Ba điểm lệch

| # | Handbook gốc | Nhóm đang dùng | Vì sao | Chốt ở đâu |
|---|---|---|---|---|
| 1 | Backend Java 21 + Spring Boot 3.x, Spring AI | Python 3.11+ + FastAPI; agent bằng LangGraph | Cả nhóm (backend, agent, data, đánh giá) dùng chung một ngôn ngữ; handbook gốc vốn đã dùng Python cho thu thập dữ liệu và đánh giá | PRD `architecture.md` §2, §4 |
| 2 | Vector trong PostgreSQL + pgvector | Weaviate (collection `Product`, cosine, `vectorizer: none`); Postgres chỉ giữ dữ liệu quan hệ | Mỗi lần dựng lại DB demo thì mất vector và phải embed lại cả catalog. Tách Weaviate cho vector một vòng đời riêng. Chốt 22/09 (`db/migrations/0002_drop_product_vectors.sql`) | PRD `architecture.md` §5, `data-model.md` §1 |
| 3 | Embedding ONNX multilingual chạy cục bộ | Cohere `embed-multilingual-v3.0`, 1024 chiều, gọi API (`search_document` khi nạp, `search_query` khi truy vấn) | Chất lượng tiếng Việt tốt, không cần GPU hay tải model lúc khởi động | PRD FR-SRC-02, NFR-PERF-03 |

## Rủi ro nhóm đã thấy và cách xử lý

- **Độ trễ:** một lượt `/search` hiện mất 0,4–0,6 giây, phần lớn do gọi Cohere. PRD NFR-PERF-01 yêu cầu p95 ≤ 250 ms, chặt hơn mốc 300 ms của handbook. Ngày 29/09 nhóm đã làm xong phần `/search` trả thời gian từng bước (`diagnostics.stageMs`, nhánh `feat/search-stage-timing`, đang chờ merge và deploy) để đo riêng phần Cohere. Hướng xử lý là cache vector của truy vấn lặp lại, đúng như NFR-PERF-03 cho phép (lịch Day 2–3).
- **So model bằng số:** trước 02/10 nhóm chạy arm E trên bộ gold đã gán nhãn, so Cohere với `intfloat/multilingual-e5-base` chạy cục bộ (đúng loại model handbook gợi ý). Quyết định giữ hay đổi đưa ra muộn nhất 02/10.
- **Phụ thuộc bên ngoài:** khoá Cohere bản trial giới hạn 1.000 lượt/tháng (đã chạm giới hạn một lần ngày 29/09). Cluster Weaviate Cloud có thể là bản Sandbox 14 ngày. Cả hai đang được theo dõi.

## Đề nghị mentor xác nhận

1. Chấp nhận ba điểm lệch trên cho bản demo và báo cáo cuối kỳ.
2. Nếu mentor muốn quay lại embedding cục bộ hoặc pgvector: đây là thay đổi PRD, nhóm sẽ làm đề xuất trong `docs/prd/update/` và cần mentor trả lời **trước 02/10** để kịp chạy lại chỉ mục và bộ đánh giá.

Trả lời bằng văn bản (email hoặc tin nhắn có lưu) là đủ. Nhóm sẽ ghi ngày xác nhận vào checklist.
