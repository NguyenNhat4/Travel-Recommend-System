# Schema log chung (frontend, backend, crawler)

Một dòng JSON mỗi sự kiện, ghi ra stdout. Ops Agent đọc stdout của container, Cloud Logging lọc/đếm/cảnh báo theo các trường dưới đây. Kế hoạch triển khai: `docs/plan/2026-10-06-logging-he-thong.md`.

## 1. Trường chung

| Trường | Ý nghĩa |
|---|---|
| `ts` | ISO-8601 giờ Hà Nội, offset `+07:00`, mili-giây (`2026-10-06T10:49:50.955+07:00`). Dùng múi `Asia/Ho_Chi_Minh`, không dùng giờ local của máy/container |
| `ts_utc` | cùng thời điểm ở UTC (`2026-10-06T03:49:50.955Z`), để đối chiếu log GCP |
| `severity` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (tên của Cloud Logging) |
| `service` | `backend` \| `frontend` \| `crawler` |
| `event` | tên sự kiện `domain.action`, ví dụ `http.request`, `bff.proxy`, `step.end` |
| `message` | câu mô tả ngắn, tuỳ chọn |
| `request_id` | `X-Request-ID`; frontend sinh nếu thiếu và chuyển xuống backend để nối log. Crawler không có, dùng `run_id` |
| `error.type`, `error.message`, `error.stack` | khi có lỗi, đã làm sạch (mục 4) |

Mức log lấy từ biến môi trường `LOG_LEVEL` (mặc định `INFO`). Mỗi app có một logger chung duy nhất; không `print`/`console.log` trực tiếp.

## 2. Sự kiện theo service

### backend

`http.request` (một dòng khi response kết thúc): `request_id, method, route` (mẫu `/api/v1/bookings/{referenceCode}`), `status, duration_ms, user_kind` (`anon|user|guest|service`), `user_id_hash`, `request_bytes, response_bytes, query, request_body, response_body`. `/health/*` log ở `DEBUG`. Lỗi 4xx/5xx thêm `error.code` (Error Envelope); 5xx là `ERROR` kèm stack.

Sự kiện nghiệp vụ, nối với request qua `request_id`:

| Workflow | `event` |
|---|---|
| Xác thực | `auth.login` (`ok/bad_credentials/locked/mfa_required`), `auth.register`, `auth.session.revoke`, `auth.password.change`, `auth.mfa.verify` |
| Search | `search.run` (`mode, query_text, result_count, engine_ms, degraded`), `search.embed.failed` |
| Recommendation | `recsys.recommend` (`persona, branch, result_count, duration_ms, cache, stage_ms, events_read` — `stage_ms` là thời gian từng bước của engine, ms nguyên: `cdp, history, candidates, rank, explore, build, coldStart`, cộng thời gian riêng của từng lượt kho vector `annShort, annLong, popularVectors` (chạy song song nên có thể chồng lên nhau; `candidates` là thời gian thật của cả bước); `cache` là kết quả tra cache gợi ý khi bật), `recsys.fallback`, `recsys.vectors.preload` (`outcome, vectors, fetched, complete, duration_ms, error_kind` — nạp vector theo id vào RAM ở nền sau mỗi lần nạp catalog) |
| Giỏ / đơn nháp | `cart.item.add/remove`, `draft.create/update`, `guest.merge` |
| Đặt chỗ | `booking.create_hold`, `booking.checkout.start`, `booking.cdp.record_purchase`, `booking.commit`, `booking.cdp.cancel_purchase`, `booking.cancel`, `booking.reconcile.deferred/failed` (kèm `booking_ref, amount_vnd, item_count`) |
| Thanh toán | `payment.webhook.received` (`stripe_event_type, event_id`), `payment.signature.invalid`, `payment.settled`, `payment.failed` |
| Trợ lý | `assistant.run.start`, `assistant.node` (`node, duration_ms, outcome`), `assistant.tool.call`, `assistant.llm.call`, `assistant.grounding` (`checked, violations`), `assistant.run.end`, `assistant.stream.open/close` |
| Sự kiện hành vi | `events.ingest` (`count, cdp_ok`) |
| Hạ tầng | `app.startup`, `app.shutdown`, `db.unavailable`, `readiness.degraded` |

### frontend (chỉ Next.js, server-side)

`bff.proxy` (`request_id, method, route, status, upstream_ms, authenticated`), `bff.proxy.upstream_error`, `bff.csrf.rejected`, `bff.session.load/refresh/destroy`, `bff.auth.login/logout/register`, `bff.guest.issue/merge`, `bff.stream.open/close`, `render.error` (`route, digest, stack`), `app.startup`, `app.shutdown`. Server Express và log phía trình duyệt ngoài phạm vi.

### crawler

Mọi dòng có `run_id`, `flow` (`full|daily|index|resume`) và, khi ở trong bước, `step` (đúng tên trong `src/data_collection/pipeline_graph.py`). `catalog.due`, `catalog.schedule.skip`, `catalog.lock.busy`, `step.start`, `step.end` (`step, source, duration_ms, status, records`), `resume.plan`, `catalog.index.start/complete`, `run.end` (`status, duration_ms, exit_code, records` theo nguồn). Chuỗi cũ mà metric đang khớp (`fresh-catalog.exit=3`, `catalog.index.start/complete`) giữ nguyên trong `message` trong giai đoạn chuyển tiếp.

## 3. Nội dung request/response

Chỉ khi `LOG_BODIES=true` (mặc định bật ở staging; tắt khi chạy tải). JSON/text, mỗi phía tối đa 2.048 byte (`truncated: true` khi cắt). Không log body nhị phân, upload, SSE (chỉ tóm tắt). Quy trình: parse → che theo khoá → che theo mẫu giá trị → cắt.

| Nhóm endpoint | Request | Response |
|---|---|---|
| `/auth/*` | không log | che `token*`; giữ `user.id` băm, vai trò |
| `/payments/stripe/webhook` | không log (chỉ `stripe_event_type`, `event_id`) | không log |
| `/bookings*`, `/booking-drafts*`, `/cart*`, `/guest-bookings/merge` | che toàn bộ hành khách/liên hệ; giữ `productId, quantity, usingDate`, tổng tiền | che tương tự; giữ `referenceCode, status, totalAmount` |
| `/search*`, `/recommendations`, `/products*`, `/destinations` | nguyên văn | chỉ `result_count` và `productId` top 10 |
| `/assistant/*` | tin nhắn người dùng đã làm sạch (cắt 500 ký tự) | câu trả lời cuối đã làm sạch (cắt 1000 ký tự); không dump lịch trình |
| `/events` | `type, productId` | không log |
| còn lại | log | log |

## 4. Không bao giờ log

- **PII**: email, số điện thoại, tên hành khách, địa chỉ, ngày sinh, hộ chiếu/CCCD. Dùng `user_id_hash` hoặc `booking_ref`.
- **Bí mật**: mật khẩu, mã MFA, JWT/access/refresh token, cookie phiên và `vota_guest`, `Authorization`, `X-Service-Token`, `X-CSRF-Token`, `X-Guest-Id`, API key (Cohere, LLM, Stripe), DSN DB/Redis, nội dung `backend.env`.
- **Thanh toán**: số thẻ, CVV, payload và chữ ký webhook, client secret.
- **Prompt đầy đủ / response thô của LLM** (debug dùng LangSmith).
- **URL ngoài kèm key/token**: hạ `httpx`/`httpcore`/`urllib3` xuống WARNING; crawler log `source` + đường dẫn, bỏ query.
- **Stack/exception** kèm DSN, URL có token: làm sạch `error.message`/`error.stack`.

Khoá bị che (không phân biệt hoa thường, khớp "chứa"): `password, passwd, token, secret, authorization, cookie, api_key, apikey, dsn, connection, email, phone, mobile, passport, idnumber, cccd, dob, birth, address, card, cvv, cvc, iban`, và `name` dưới nhánh hành khách/liên hệ. Mẫu giá trị bị che: email, số điện thoại VN (`0…`/`+84…`), chuỗi 13–19 chữ số, JWT (`eyJ…`), `Bearer …`, `sk_/pk_/whsec_…`, DSN `scheme://user:pass@`. Giá trị thay thế: `***`.

Thực thi: mỗi app có một hàm `redact()` trong logger chung, logger chỉ nhận trường khai báo cho từng `event` (allowlist), và test mỗi nhánh bơm giá trị giả (`password=hunter2`, JWT, DSN, email, thẻ) rồi khẳng định stdout không chứa chuỗi đó. Bảng này là quy tắc review PR.

## 5. Ops Agent / metric

Container log là `{"log": "<dòng JSON>", "stream": ...}` của docker json-file; Ops Agent parse hai tầng rồi đặt `severity` và `time` từ `severity`/`ts`. Metric requests/5xx lọc `jsonPayload.event="http.request"`, loại `/health/*`; metric lỗi loại `logName:"ops-agent"`. Chi tiết ở nhánh monitoring.
