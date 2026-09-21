# Hợp đồng tích hợp Insider Clone

Phiên bản: 1.0  
Người tạo: mihhquan  
Ngày: 2026-09-17  
Múi giờ: UTC  
Mã hóa: UTF-8  
Prefix API: `insider/v1`

---

## 0. Tổng quan

Tài liệu này mô tả contract giữa **Backend** (và các job nội bộ) với **Insider clone** — một mock platform mô phỏng API của Insider trong production.

**Luồng chính:**

```text
Booking
  -> Backend
  -> CDP: purchase event
  -> Recommendation engine đọc CDP history
  -> Recommendation result
  -> Insider: push recommended_products attribute
```

Insider clone:

- Là service riêng biệt, độc lập với CDP clone.
- Nhận data qua API, validate rules giống production Insider.
- Lưu subset data phục vụ activation (profile, event, channel engagement).
- Export channel engagement events khi được yêu cầu.

**Phạm vi:**

- Backend gọi Insider qua `InsiderClient` interface.
- Seed job và recommendation job gọi Insider qua service token.
- Web/Frontend **không** gọi trực tiếp Insider clone.

---

## 1. Phạm vi trách nhiệm

### 1.1. Insider clone chịu trách nhiệm

- Lưu `insider_profiles`: attributes nhận qua Upsert, keyed trên identifier. Đây là copy của Insider — deliberately subset của CDP.
- Lưu `insider_events`: events nhận qua Upsert, expiring sau 90 days (730 days cho purchases).
- Lưu `channel_events`: email opens, clicks, bounces, unsubscribes; push và SMS. Seeded và exported qua `/raw/v1/export`.
- Lưu `identifiers`: maps `cdp_user_id`, email và phone tới một profile, để identity PATCH endpoint có data để operate.
- Validate rules production:
  - `X-PARTNER-NAME` header phải lowercase.
  - `X-REQUEST-TOKEN` phải present.
  - Custom events expire sau 90 days; purchases sau 730 days.
  - `gdpr_optin: false` nghĩa là customer không nhận gì cả, qua bất kỳ channel nào.
  - Sending `""` hoặc `null` **không** delete attribute — nó lưu empty value.
  - Array attributes append by default (trừ khi `not_append: true`).
  - Reject batch > 1,000 users hoặc body > 5 MB.

### 1.2. Backend chịu trách nhiệm

- Gọi Insider qua `InsiderClient` interface, không truy cập trực tiếp database Insider.
- Push recommendation results vào Insider như attributes (`recommended_products`).
- Push purchase events vào Insider (với TTL 730 days).
- Push browsing events vào Insider (với TTL 90 days).
- Handle identity changes qua `PATCH /user/v1/identity`.
- Export channel engagement events qua `POST /raw/v1/export`.

### 1.3. Team Data chịu trách nhiệm

- Seed channel engagement events (email opens, clicks, bounces, unsubscribes, push, SMS).
- Seed `insider_profiles` với các persona demo.
- Đảm bảo `cdpUserId` của 4 tài khoản demo khớp giữa Backend users và dữ liệu seed trong Insider.

### 1.4. Team Recommendation chịu trách nhiệm

- Đọc lịch sử từ CDP, không từ Insider.
- Sau khi tính recommendations, push vào Insider qua `InsiderClient` — batched tại 1,000 users, dưới 5 MB, `not_append: true` trên arrays, excluded suppressed customers.
- Đảm bảo chỉ push top 3–5 recommendations (để payload < 5 KB/customer).

### 1.5. Ngoại phạm vi

- Real payments, real booking confirmations.
- Training neural networks.
- Viết vào production CDP hoặc Insider.
- Web/Frontend gọi trực tiếp Insider clone.

---

## 2. Luồng dữ liệu

```text
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│    Backend    │      │  CDP Clone    │      │ Insider Clone │
└───────┬───────┘      └───────┬───────┘      └───────┬───────┘
        │                      │                      │
        │ POST /events         │                      │
        │ (purchase)           │                      │
        ├─────────────────────>│                      │
        │                      │                      │
        │ GET /events          │                      │
        │ (history)            │                      │
        ├─────────────────────>│                      │
        │                      │                      │
        │ POST /upsert         │                      │
        │ (recommendations)    │                      │
        ├────────────────────────────────────────────>│
        │                      │                      │
        │ POST /export         │                      │
        │ (channel events)     │                      │
        ├────────────────────────────────────────────>│
        │                      │                      │
```

**Quy tắc:**

1. Recommendation đọc lịch sử từ CDP, không từ Insider.
2. Insider chỉ nhận subset data (attributes, top recommendations, recent events).
3. Event trong Insider có TTL: custom 90 ngày, purchase 730 ngày.
4. Channel events được seed và export qua `/raw/v1/export`.

---

## 3. Bộ mặt API Insider clone

### 3.1. Endpoints

| Method | Endpoint | Mục đích |
|---|---|---|
| `POST` | `/user/v1/upsert` | Insert/update customer attributes và events |
| `PATCH` | `/user/v1/identity` | Change identifier, preserve history |
| `POST` | `/user/v1/profile` | Get one customer's stored profile |
| `POST` | `/raw/v1/export` | Export channel engagement events |

### 3.2. `POST /user/v1/upsert`

**Request:**

```json
{
  "users": [
    {
      "identifiers": {
        "uuid": "user-001",
        "email": "demo@example.com",
        "phone_number": "+84901234567"
      },
      "attributes": {
        "gdpr_optin": true,
        "email_optin": true,
        "sms_optin": false,
        "lifecycle_stage": "active",
        "home_city": "Ho Chi Minh City",
        "last_destination": "Nha Trang",
        "purchased_verticals": ["hotel", "ticket"],
        "recommended_products": [
          {
            "product_id": "product-002",
            "name": "Vinpearl Resort Nha Trang",
            "url": "/products/product-002",
            "score": 0.91
          }
        ]
      },
      "events": [
        {
          "event_name": "recommendation_generated",
          "timestamp": "2026-09-17T06:00:00Z",
          "event_params": {
            "strategy": "personalized",
            "count": 3
          }
        }
      ]
    }
  ],
  "not_append": false
}
```

**Rules:**

- Tối đa **1,000 users** per request.
- Body tối đa **5 MB**.
- `X-PARTNER-NAME` header phải tồn tại và ở dạng **lowercase**.
- `X-REQUEST-TOKEN` header bắt buộc.
- Array attributes **append by default** (trừ khi `not_append: true`).
- `null` và chuỗi rỗng được lưu thành **empty value**, không phải delete.
- User có `gdpr_optin: false` không được activation/delivery.
- Custom events expire sau **90 days**; purchases sau **730 days**.

**Response:**

- `200 OK`: Thành công.
- `400 VALIDATION_ERROR`: Sai schema, thiếu required fields, hoặc vi phạm rules.
- `403 FORBIDDEN`: Thiếu hoặc sai `X-PARTNER-NAME` / `X-REQUEST-TOKEN`.
- `413 PAYLOAD_TOO_LARGE`: Body > 5 MB.
- `422 UNPROCESSABLE_ENTITY`: Batch > 1,000 users.

### 3.3. `PATCH /user/v1/identity`

**Request:**

```json
{
  "old_identifier": {
    "email": "old@example.com"
  },
  "new_identifier": {
    "email": "new@example.com"
  }
}
```

**Rules:**

- Chỉ **một user** per request (no batching).
- `old_identifier` và `new_identifier` phải **cùng type**.
- Update bảng `identifiers`, không tạo profile mới.
- Preserve toàn bộ history (events, attributes).

**Response:**

- `200 OK`: Thành công.
- `400 VALIDATION_ERROR`: `old_identifier` và `new_identifier` khác type.
- `404 NOT_FOUND`: `old_identifier` không tồn tại.
- `403 FORBIDDEN`: Thiếu hoặc sai headers.

### 3.4. `POST /user/v1/profile`

**Request:**

```json
{
  "identifier": {
    "uuid": "user-001"
  }
}
```

**Response:**

```json
{
  "identifier": {
    "uuid": "user-001",
    "email": "demo@example.com"
  },
  "attributes": {
    "gdpr_optin": true,
    "lifecycle_stage": "active",
    "recommended_products": []
  },
  "updated_at": "2026-09-17T06:00:00Z"
}
```

**Rules:**

- Trả về profile và attributes.
- Không trả về events (dùng `/raw/v1/export` cho events).

**Response:**

- `200 OK`: Thành công.
- `404 NOT_FOUND`: Profile không tồn tại.
- `403 FORBIDDEN`: Thiếu hoặc sai headers.

### 3.5. `POST /raw/v1/export`

**Request:**

```json
{
  "start_date": "2026-09-01T00:00:00Z",
  "end_date": "2026-09-17T23:59:59Z",
  "channels": ["email", "push", "sms"],
  "identifier": {
    "uuid": "user-001"
  }
}
```

**Response:**

```json
{
  "events": [
    {
      "event_id": "channel-001",
      "identifier": "user-001",
      "channel": "email",
      "event_name": "open",
      "timestamp": "2026-09-10T08:30:00Z",
      "metadata": {
        "campaign_id": "campaign-001"
      }
    }
  ]
}
```

**Rules:**

- Export channel engagement events trong khoảng thời gian.
- Channels: `email`, `push`, `sms`.
- Event types: `open`, `click`, `bounce`, `unsubscribe`, `sent`, `delivered`.

**Response:**

- `200 OK`: Thành công.
- `400 VALIDATION_ERROR`: Sai date range hoặc channels.
- `403 FORBIDDEN`: Thiếu hoặc sai headers.

---

## 4. Database schema

### `insider_profiles`

```sql
CREATE TABLE insider_profiles (
  profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  primary_identifier VARCHAR(255) NOT NULL,
  attributes JSONB NOT NULL,
  gdpr_optin BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `insider_events`

```sql
CREATE TABLE insider_events (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES insider_profiles(profile_id),
  event_name VARCHAR(128) NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  event_params JSONB,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index để cleanup events hết hạn
CREATE INDEX idx_insider_events_expires_at ON insider_events(expires_at);
```

### `channel_events`

```sql
CREATE TABLE channel_events (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES insider_profiles(profile_id),
  channel VARCHAR(32) NOT NULL,
  event_name VARCHAR(64) NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_channel_events_profile ON channel_events(profile_id);
CREATE INDEX idx_channel_events_occurred_at ON channel_events(occurred_at);
```

### `identifiers`

```sql
CREATE TABLE identifiers (
  identifier_type VARCHAR(32) NOT NULL,
  identifier_value VARCHAR(255) NOT NULL,
  profile_id UUID NOT NULL REFERENCES insider_profiles(profile_id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (identifier_type, identifier_value)
);

CREATE INDEX idx_identifiers_profile ON identifiers(profile_id);
```

---

## 5. Interface `InsiderClient`

Backend không nên gọi HTTP trực tiếp ở business logic. Nên có interface:

```java
public interface InsiderClient {
    /**
     * Insert/update customer attributes và events.
     * @param users Danh sách users (max 1000).
     * @param notAppend Nếu true, array attributes sẽ replace thay vì append.
     */
    void upsertUsers(List<InsiderUser> users, boolean notAppend);

    /**
     * Change identifier, preserve history.
     */
    void changeIdentity(IdentityChangeRequest request);

    /**
     * Get one customer's stored profile.
     */
    InsiderProfile getProfile(Identifier identifier);

    /**
     * Export channel engagement events.
     */
    List<ChannelEvent> exportChannelEvents(ExportRequest request);
}
```

### DTOs

```java
public class InsiderUser {
    private Identifiers identifiers;
    private Map<String, Object> attributes;
    private List<InsiderEvent> events;
    // getters, setters
}

public class Identifiers {
    private String uuid;
    private String email;
    private String phoneNumber;
    // getters, setters
}

public class InsiderEvent {
    private String eventName;
    private Instant timestamp;
    private Map<String, Object> eventParams;
    // getters, setters
}

public class IdentityChangeRequest {
    private Identifier oldIdentifier;
    private Identifier newIdentifier;
    // getters, setters
}

public class Identifier {
    private String type; // "uuid", "email", "phone"
    private String value;
    // getters, setters
}

public class InsiderProfile {
    private Identifier identifier;
    private Map<String, Object> attributes;
    private Instant updatedAt;
    // getters, setters
}

public class ExportRequest {
    private Instant startDate;
    private Instant endDate;
    private List<String> channels;
    private Identifier identifier;
    // getters, setters
}

public class ChannelEvent {
    private String eventId;
    private String identifier;
    private String channel;
    private String eventName;
    private Instant timestamp;
    private Map<String, Object> metadata;
    // getters, setters
}
```

---

## 6. Mock data requirements

### Bắt buộc

- Seed channel engagement events: email opens, clicks, bounces, unsubscribes; push và SMS.
- Seed `insider_profiles` với các persona demo (4 tài khoản).
- Đảm bảo `cdpUserId` khớp giữa Backend users và dữ liệu seed trong Insider.
- Có customer với `gdpr_optin: false`.
- Có customer ở các life stages: `new`, `active`, `dormant`, `churned`.
- Có purchase events (TTL 730 ngày) và custom events (TTL 90 ngày).
- Có recommended_products attributes.

### Acceptance test

| Test | Kết quả mong đợi |
|---|---|
| Upsert hợp lệ (1 user) | `200 OK`, profile/event được lưu |
| Upsert hợp lệ (1,000 users) | `200 OK` |
| Upsert 1,001 users | `422 UNPROCESSABLE_ENTITY`, không lưu partial batch |
| Body > 5 MB | `413 PAYLOAD_TOO_LARGE` |
| Thiếu `X-REQUEST-TOKEN` | `403 FORBIDDEN` |
| `X-PARTNER-NAME` không lowercase | `403 FORBIDDEN` |
| Array không có `not_append` | Append |
| Array có `not_append: true` | Replace |
| `gdpr_optin=false` | Không activation/delivery |
| Custom event quá 90 ngày | Không còn trả về |
| Purchase quá 730 ngày | Không còn trả về |
| Identity change cùng type | `200 OK`, preserve history |
| Identity change khác type | `400 VALIDATION_ERROR` |
| Get profile không tồn tại | `404 NOT_FOUND` |
| Export events hợp lệ | `200 OK`, trả về events |

---

## 7. Bảo mật

1. **Mạng nội bộ:** Insider clone chỉ nằm trong mạng nội bộ. Không mở cổng service ra ngoài (trừ khi dev).
2. **Không CORS:** Không có CORS. Web/Frontend không được gọi trực tiếp Insider clone.
3. **Service token:** `X-REQUEST-TOKEN` tối thiểu 32 ký tự, chỉ dành cho Backend, seed job và recommendation job. Không đưa vào code frontend, URL hay log.
4. **Token rotation:** Nếu nghi ngờ token bị lộ, phải đổi đồng thời cả hai bên và khởi động lại.
5. **Log:** Log không chứa `cdpUserId`, `email`, `phone`, token hay payload event. Chỉ ghi `requestId`, `eventName`, số lượng, lý do bị bỏ, `profileId`.

---

## 8. Vận hành và truy vết

### 8.1. Cấu hình

| Biến môi trường | Ghi chú |
|---|---|
| `INSIDER_DATABASE_URL` | PostgreSQL riêng cho Insider clone |
| `INSIDER_SERVICE_TOKEN` | Token cho service-to-service (Backend ↔ Insider) |
| `INSIDER_BASE_URL` | Base URL của Insider clone (mặc định: `http://localhost:8200`) |
| `INSIDER_EVENT_QUEUE_SIZE` | Queue size cho async events (mặc định: 1000) |
| `INSIDER_TIMEOUT_SECONDS` | Timeout cho calls (mặc định: 2 giây) |

### 8.2. Thứ tự khởi động

1. Khởi tạo PostgreSQL: `alembic -c src/insider_clone/alembic.ini upgrade head`.
2. Khởi động Insider clone service.
3. Seed `insider_profiles`, `insider_events`, `channel_events`, `identifiers`.
4. Khởi động Backend.

### 8.3. Truy vết

- Backend chuyển tiếp `X-Request-ID` của request gốc sang mọi lời gọi Insider, kể cả từ worker.
- Insider clone lặp lại ID trong header response và `error.requestId`.
- Log phải ghi `requestId`, `profileId`, `eventName`, `channel`, `action` (upsert/export/identity).

### 8.4. Thay đổi phiên bản

- Đổi API: cập nhật `insider-clone.openapi.yaml` và fixture trước, rồi adapter Backend, rồi Insider clone.
- Deploy Insider clone trước Backend khi chỉ thêm trường; ngược lại khi bỏ trường.
- Đổi bảng: sửa `tables.py` và thêm revision Alembic cùng lúc.

---

## 9. Rủi ro còn lại

| Rủi ro | Mức | Xử lý hiện tại |
|---|---|---|
| Event purchase mất khi backup thất bại | Trung bình | Log ERROR, hủy tay |
| Event browsing mất khi Insider lỗi, queue đầy, Backend restart | Thấp | Log chấp nhận |
| Checkout phụ thuộc Insider | Trung bình | Checkout không gọi Insider; chỉ recommendation |
| Một token cho mọi caller, chưa có xoay vòng | Trung bình | Chỉ mạng nội bộ |
| Người dùng tự gọi POST /user/v1/upsert hàng loạt | Thấp | productId phải có thật, chưa rate limit |
| Seed lệch giữa CDP và Insider | Trung bình | Bước kiểm tra 4 persona |
| Khách ẩn danh không được ghi | Thấp | Ngoại phạm vi |

---

## 10. Chỉ xác nhận

1. Web không có URL hay token của Insider clone trong code và biến môi trường.
2. Gọi Insider clone không có hoặc sai `X-REQUEST-TOKEN` trả `403` mọi endpoint.
3. Upsert hợp lệ sinh `200 OK`.
4. Upsert 1,001 users trả `422`, không lưu partial batch.
5. Body > 5 MB trả `413`.
6. `X-PARTNER-NAME` không lowercase trả `403`.
7. Array không có `not_append` append; có `not_append: true` replace.
8. `gdpr_optin=false` không được activation/delivery.
9. Custom event quá 90 ngày không còn trả về.
10. Purchase quá 730 ngày không còn trả về.
11. Identity change cùng type preserve history; khác type reject.
12. Export events hợp lệ trả về channel events.
13. Một `X-Request-ID` xuất hiện log Backend và log Insider clone cho cùng một thao tác.

---

## 11. Tiêu chí nghiệm thu

| Ngày | Quyết định | Lý do |
|---|---|---|
| 2026-09-17 | Insider clone là service riêng, PostgreSQL riêng | Mô phỏng ranh giới production Insider |
| 2026-09-17 | Event có TTL: custom 90 ngày, purchase 730 ngày | Giống production Insider |
| 2026-09-17 | Web không gọi trực tiếp Insider | Tránh dependency frontend, bảo mật |
| 2026-09-17 | Backend gọi qua `InsiderClient` interface | Swappable cho production adapter |
| 2026-09-17 | Recommendation đọc từ CDP, không từ Insider | CDP là system of record |

---

## 12. Lịch sử quyết định

| Ngày | Quyết định | Lý do |
|---|---|---|
| 2026-09-17 | Insider clone độc lập với CDP clone | Mô phỏng kiến trúc production |
| 2026-09-17 | Event TTL 90/730 ngày | Giống production Insider |
| 2026-09-17 | Batch limit 1,000 users, 5 MB | Giống production Insider |
| 2026-09-17 | `X-PARTNER-NAME` lowercase, `X-REQUEST-TOKEN` required | Giống production Insider |
| 2026-09-17 | Array append default, `not_append: true` để replace | Giống production Insider |
| 2026-09-17 | `gdpr_optin=false` không activation | GDPR compliance |
| 2026-09-17 | Recommendation đọc từ CDP, push vào Insider | CDP là system of record |