# Kiến trúc Travel Recommendation Product

## 1. Mục tiêu

Repository này là monorepo cho sản phẩm gợi ý du lịch gồm:

- Web app Next.js + Tailwind CSS: tìm kiếm, cá nhân hóa, chi tiết sản phẩm, booking và chat lịch trình.
- Backend Python/FastAPI: API, xác thực, search, recommendation, booking và itinerary agent.
- PostgreSQL + pgvector: catalog, hồ sơ, event, booking và vector sản phẩm.
- CDP clone và Insider clone: mô phỏng ranh giới tích hợp production.
- Pipeline thu thập dữ liệu và bộ đánh giá chạy offline.

Kiến trúc ưu tiên hợp đồng API ổn định, ownership rõ theo feature và khả năng thay implementation hạ tầng mà không đổi business logic.

## 2. Các quyết định chính

| Vấn đề | Quyết định |
| --- | --- |
| Repository | Monorepo; toàn bộ source code nằm dưới `src/` |
| Frontend | Next.js (App Router) + TypeScript + Tailwind CSS, tổ chức theo feature |
| Backend | Python + FastAPI, kiến trúc phân lớp theo domain/application/infrastructure |
| Agent | LangGraph nằm trong backend và chỉ điều phối use case itinerary |
| Database | PostgreSQL + pgvector |
| Contract | `src/shared/contracts/openapi.yaml` là nguồn sự thật chung cho frontend/backend |
| Tích hợp ngoài | Đi qua client interface; không truy cập trực tiếp database của service khác |
| API | REST/JSON, prefix `/api/v1`, JWT tùy chọn ở các API cho khách ẩn danh |

Spec và repository thống nhất sử dụng Next.js + TypeScript + Tailwind CSS cho frontend và Python + FastAPI cho backend. Các boundary nghiệp vụ vẫn giữ nguyên khi thay đổi stack triển khai.

## 3. Sơ đồ hệ thống

```text
Next.js Web
   |
   | REST/JSON + JWT + X-Request-ID
   v
FastAPI
   |-- Auth / Catalog / Search / Recommendation / Booking / Events
   |-- Itinerary application service
   |      `-- LangGraph -> SearchClient / RecommendationClient / LLM
   |-- PostgreSQL + pgvector: products, users, bookings, product vectors
   |-- CdpClient  -- X-Service-Token, mạng nội bộ --> CDP clone API --> PostgreSQL riêng: events, profiles
   `-- InsiderClient --> Insider clone API
```

Web không gọi CDP clone. Backend ghi `product_view`, `search`, `add_to_cart` ở nền và `purchase` đồng bộ (`docs/spec/hop-dong-tich-hop-cdp.md`).

Luồng phản hồi cốt lõi:

```text
Booking hoàn tất -> CdpClient ghi purchase theo cdp_user_id -> cập nhật user vector
-> recommendation thay đổi -> frontend tải recommendation mới
```

## 4. Cấu trúc repository

```text
src/
├── frontend/                       # Next.js (App Router) + TypeScript + Tailwind CSS
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   └── src/
│       ├── app/                    # route segment, layout, route handler (Next.js App Router)
│       │   └── globals.css         # Tailwind directive và global style
│       ├── assets/
│       ├── components/             # UI dùng chung, không chứa business rule
│       ├── features/
│       │   ├── auth/
│       │   ├── booking/
│       │   ├── catalog/
│       │   ├── itinerary/
│       │   ├── recommendations/
│       │   └── search/
│       ├── hooks/
│       ├── services/               # HTTP client và generated API client
│       ├── test/                   # test setup, fixtures, render helpers
│       └── types/                  # kiểu dùng chung phía frontend
├── backend/
│   ├── app/
│   │   ├── api/v1/routes/          # FastAPI routers, chỉ xử lý HTTP
│   │   ├── core/                   # settings, logging, security, errors
│   │   ├── domain/                 # entity/value object và business rule thuần
│   │   ├── application/            # use case và port/interface
│   │   ├── infrastructure/         # DB, external clients, LLM implementation
│   │   ├── agents/                 # LangGraph state, graph, node và tool
│   │   └── main.py                 # composition root FastAPI
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── contract/
├── shared/
│   ├── contracts/                  # OpenAPI dùng chung
│   └── mocks/                      # fixture sinh từ contract
├── data_collection/                # collector, chuẩn hóa, dedupe, seed data
├── evaluation/                     # split, metrics, benchmark và report offline
├── insider_clone/                  # service giả lập đúng bề mặt Insider
└── cdp_clone/                      # service giả lập đúng bề mặt CDP
```

## 5. Quy tắc phụ thuộc backend

```text
api -> application -> domain
                  ^
infrastructure ---|
agents -> application ports
```

- `domain` không import FastAPI, database driver, LangGraph hoặc SDK bên ngoài.
- `application` điều phối use case và khai báo port như `CdpClient`, `SearchClient`, `InsiderClient`.
- `infrastructure` hiện thực các port; chỉ composition root được quyền nối implementation vào use case.
- `api` chuyển HTTP request/response sang application model, không chứa truy vấn DB hay prompt.
- `agents` không tự truy cập DB và không tạo sản phẩm; chỉ dùng các port do application cung cấp.

Mỗi domain (`auth`, `booking`, `catalog`, `itinerary`, `recommendation`, `search`) có namespace riêng để team có thể làm song song và tránh file tổng hợp quá lớn.

## 6. Quy tắc frontend

- `app` chỉ chứa route segment (`layout.tsx`, `page.tsx`, `route.ts`) ghép layout và feature theo route; không chứa business rule.
- Mỗi folder trong `features` sở hữu component, hook, state và test của nghiệp vụ đó.
- `components` chỉ chứa thành phần dùng lại ở ít nhất hai feature; ưu tiên Server Component, chỉ đánh dấu `"use client"` khi cần tương tác/state phía client.
- Mọi HTTP call đi qua `services`; component không gọi `fetch` trực tiếp.
- Kiểu request/response được sinh từ OpenAPI. Không tự định nghĩa lại `SearchRequest`, `ProductSummary` hoặc `ItineraryResponse` trong từng feature.
- Server state và UI state được tách riêng; token không được log hoặc đưa vào URL.
- Styling dùng Tailwind CSS utility class; token màu/spacing khai báo tại `tailwind.config.ts`, không viết CSS tùy ý ngoài `globals.css`.

## 7. Hợp đồng và endpoint

Hợp đồng chung được quản lý tại `src/shared/contracts/openapi.yaml`. Ba schema phải khóa trước khi các team code độc lập:

1. `SearchRequest`
2. `ProductSummary`
3. `ItineraryResponse`

Nhóm endpoint v1:

- Auth: đăng ký, đăng nhập và JWT.
- Catalog: danh sách và chi tiết `/products/{productId}`.
- Search: semantic search, similar products.
- Recommendations: cá nhân hóa hoặc popular fallback cho khách ẩn danh.
- Booking: checkout giả lập, ghi event `purchase` về CDP clone trước khi commit.
- Events: `POST /api/v1/events` cho `product_view`; Backend chuyển sang CDP clone.
- Assistant: `POST /api/v1/assistant/itineraries`.
- Insider clone: bốn endpoint mô phỏng được mô tả trong spec.
- CDP clone: API nội bộ cho Backend, seed và job; contract riêng tại `src/shared/contracts/cdp-clone.openapi.yaml`.

Thay đổi tương thích ngược có thể bổ sung vào v1. Xóa/đổi tên field hoặc thay đổi semantics phải tạo v2.

## 8. Itinerary Agent và grounding

Pipeline bắt buộc:

```text
message -> extract intent -> clarify if required -> retrieve real products
-> optionally re-rank with recommendations -> compose itinerary
-> validate products, destination, availability, time and total -> response
```

- Mọi `productId`, tên, giá và `bookingUrl` phải đến từ Search/Recommendation API.
- LLM chỉ trích xuất intent và trình bày kết quả; backend tự tính tổng tiền.
- Không có kết quả phải trả `NO_RESULTS`, không lấp bằng sản phẩm do LLM tạo.
- Khi LLM lỗi, dùng rule-based fallback hoặc trả lỗi có kiểm soát.
- Conversation lưu intent đã chuẩn hóa, TTL mục tiêu 24 giờ; giá và availability luôn được tải lại.

## 9. Dữ liệu và tích hợp

- CDP clone (`src/cdp_clone`) là service tách biệt với PostgreSQL riêng, là system of record cho `events` và `profiles`, chỉ mở trong mạng nội bộ. Backend không truy cập database này; chỉ đọc/ghi qua `CdpClient` bằng service token.
- Luồng hành vi là Web → Backend → CDP. Event duyệt web ghi nền, bỏ khi CDP lỗi; `purchase` ghi đồng bộ, bù trừ bằng huỷ event khi commit booking lỗi; Recommendation rơi về `popular` khi không đọc được CDP. Chi tiết: `docs/spec/hop-dong-tich-hop-cdp.md`.
- `products`, `users`, `bookings` và `product_vectors` hiện ở PostgreSQL của Backend; việc chuyển chúng vào CDP clone đang chờ xác nhận.
- Insider clone là service tách biệt, cố ý chỉ giữ tập con dữ liệu và TTL theo spec.
- Collector phải cache raw response trước khi parse, hỗ trợ resume và ghi nguồn của từng field.
- Secret, API key và JWT không được commit hoặc ghi log.

## 10. Kiểm thử và quality gates

- Unit: domain rules, intent merge, ranking, budget và grounding validator.
- Integration: database adapter, client adapter, booking-to-event loop.
- Contract: backend response và frontend mock cùng kiểm tra với OpenAPI.
- End-to-end: search -> product -> checkout -> event -> recommendation đổi.
- Evaluation offline: Recall@20, NDCG@10, cross-category rate, availability precision, coverage.

Các tiêu chí bắt buộc từ spec: assistant grounding 100%, search/recommendation p95 dưới 300 ms và itinerary toàn luồng mục tiêu dưới 5 giây.

## 11. Ownership đề xuất

| Workstream | Phạm vi chính |
| --- | --- |
| Web | `src/frontend` |
| Backend | `src/backend/app/api`, `application`, `domain` |
| Search/Recommendation | domain/application tương ứng và pgvector adapter |
| Agent | `src/backend/app/agents`, itinerary use case |
| Data | `src/data_collection`, CDP adapters/migrations |
| Evaluation | `src/evaluation`, quality fixtures |
| Integration | `src/shared/contracts`, contract tests |

Một thay đổi contract cần reviewer của Web và Backend. Một thay đổi schema CDP/Insider cần reviewer của Data/Integration.

## 12. Quy ước thêm module mới

1. Xác định feature/domain sở hữu hành vi.
2. Cập nhật OpenAPI trước nếu thay đổi giao diện giữa các team.
3. Đặt business rule trong `domain`, orchestration trong `application`.
4. Đặt SDK/DB/HTTP implementation trong `infrastructure`.
5. Thêm unit test và contract/integration test tương ứng.
6. Không tạo folder `utils` chung; helper phải nằm gần domain sử dụng hoặc có tên theo trách nhiệm cụ thể.
