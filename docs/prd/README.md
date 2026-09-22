# Cổng Tài Liệu Dự Án — V-OTA Platform

Chào mừng bạn đến với trung tâm tài liệu kỹ thuật và đặc tả sản phẩm của nền tảng **V-OTA (Virtual Online Travel Agency)**. Thư mục `docs/` chứa toàn bộ các tài liệu chuẩn hóa quy trình phát triển từ ý tưởng, kiến trúc, thiết kế dữ liệu cho đến kiểm thử và vận hành của toàn bộ hệ thống.

---

## 📑 Danh Mục Bộ Tài Liệu Chuẩn Quy Trình Sản Phẩm

Bộ tài liệu được xây dựng theo chuẩn 9 tài liệu kỹ thuật toàn diện:

| # | Tài liệu | Mục đích cốt lõi | Đối tượng độc giả chính |
|---|---|---|---|
| 1 | **[project-brief.md](project-brief.md)** | Xác định bối cảnh, vấn đề, tầm nhìn, mục tiêu dài hạn, phạm vi hệ thống và đối tượng người dùng. | Product Manager, Stakeholders, Toàn đội ngũ |
| 2 | **[requirements.md](requirements.md)** | Đặc tả yêu cầu chức năng (FR), yêu cầu phi chức năng (NFR) và ma trận tiêu chí nghiệm thu. | Product Owner, Developers, QA |
| 3 | **[user-flow.md](user-flow.md)** | Thống nhất trải nghiệm người dùng, bản đồ hành trình, route điều hướng và wireframe các màn hình chính. | UI/UX Designer, Frontend Engineers |
| 4 | **[data-model.md](data-model.md)** | Mô hình dữ liệu toàn hệ thống, sơ đồ ERD (cdp, catalog, app, insider), ranh giới bảo mật và migration. | Data Engineers, Backend Engineers, DBA |
| 5 | **[architecture.md](architecture.md)** | Kiến trúc tổng thể, Clean Architecture Backend, LangGraph AI Agent và các nguyên tắc phụ thuộc. | System Architects, Backend & AI Engineers |
| 6 | **[api-contract.md](api-contract.md)** | Hợp đồng giao tiếp giữa các thành phần, chuẩn RESTful, Error Envelope, Grounding và versioning. | Frontend, Backend, AI Engineers |
| 7 | **[test-plan.md](test-plan.md)** | Chiến lược kiểm thử 5 tầng: Contract testing, Unit/Integration, DB verify, RecSys & AI evaluation. | QA/QC, Automation Testers, Engineers |
| 8 | **[implementation-plan.md](implementation-plan.md)** | Lộ trình triển khai tổng thể qua 6 giai đoạn, phân công trách nhiệm và Definition of Done. | Project Manager, Tech Leads, Scrum Master |
| 9 | **[deployment-plan.md](deployment-plan.md)** | Quy trình đóng gói Docker, biến môi trường, quản trị migration, giám sát và kế hoạch rollback. | DevOps, SRE, Tech Leads |

---

## 🧭 Hướng Dẫn Tra Cứu Nhanh Theo Vai Trò

- **Nếu bạn là Product Manager / Designer:**
  - Bắt đầu với [project-brief.md](project-brief.md) để hiểu tầm nhìn và [requirements.md](requirements.md) để nắm các yêu cầu chức năng.
  - Xem [user-flow.md](user-flow.md) để nắm bắt sơ đồ luồng và wireframe giao diện.
- **Nếu bạn là Backend / AI Engineer:**
  - Đọc kỹ [architecture.md](architecture.md) để tuân thủ kiến trúc phân lớp sạch (Clean Architecture) và nguyên tắc Grounding của AI Agent.
  - Xem [data-model.md](data-model.md) và [api-contract.md](api-contract.md) trước khi viết mã nguồn hoặc endpoint mới.
- **Nếu bạn là Frontend Engineer:**
  - Xem [user-flow.md](user-flow.md) để đối chiếu tuyến đường (route) và bố cục màn hình.
  - Sử dụng [api-contract.md](api-contract.md) và `src/shared/contracts/openapi.yaml` làm chuẩn khi tích hợp dữ liệu.
- **Nếu bạn là Data / RecSys Engineer:**
  - Tham khảo [data-model.md](data-model.md) cho cấu trúc schema `cdp` và collection `Product` trên Weaviate.
  - Tham khảo [test-plan.md](test-plan.md) để nắm các chỉ số đánh giá chất lượng thuật toán (NDCG, Recall@K, Coverage).
- **Nếu bạn là DevOps / QA Engineer:**
  - Đọc [deployment-plan.md](deployment-plan.md) để nắm quy trình migration cơ sở dữ liệu và vận hành container.
  - Đọc [test-plan.md](test-plan.md) để tự động hóa các bộ test trong CI/CD.

---

## 📌 Nguyên Tắc Vận Hành & Quản Trị Tài Liệu

1. **Contract-First:** Mọi thay đổi giao tiếp API phải được cập nhật và kiểm thử tại `src/shared/contracts/` trước khi thay đổi mã nguồn.
2. **Database Schema as Truth:** Mọi thay đổi cấu trúc bảng phải đồng bộ đồng thời giữa DDL (`db/vota_schema.sql`), migration (`db/migrations/`) và [data-model.md](data-model.md).
3. **Bắt buộc ghi nhận lịch sử:** Bất kỳ chỉnh sửa nào trong thư mục `docs/` đều phải được ghi nhận vào một file mới trong thư mục `history/` theo đúng quy chuẩn `AGENTS.md`.
