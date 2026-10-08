# Recommendation cho OTA du lịch: persona, profile và latency

> **Trạng thái: ghi chú nghiên cứu, không chuẩn tắc.** Phục vụ FR-REC-01, FR-REC-02, FR-REC-03, FR-REC-04, NFR-PERF-01.
> Đối chiếu với code và số đo ở `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §1.2: trọng số hiện tại là 0,7/0,15/0,15
> (không phải 0,6/0,25/0,15); đường request không đọc `cdp.profiles`; luật chuyến mở là if/else theo `usingDate`, không phải
> `ends_on >= today OR age <= 14`; event `search` không có `productId` nên không vào vector. Các mục kiến trúc §10–15
> (materialize profile, Redis, stale cache, precompute) lệch PRD và nằm ngoài plan đó (§8.3). Ngưỡng dormant đã chốt
> 365 ngày, persona = 4 trạng thái cold-start (đề xuất `docs/prd/update/2026-10-09-persona-trang-thai-cold-start-va-phong-cach-du-lich.md`).

## 1. Bối cảnh hiện tại

Hệ thống đang có bốn persona:

- **Frequent:** khách có lịch sử và mua hàng thường xuyên.
- **Dormant:** khách lâu năm quay lại nhưng vẫn còn lịch sử.
- **First time:** khách có view/search nhưng chưa mua.
- **No history:** khách mới hoàn toàn.

Hiện có seasonal popular và content-based recommendation. Engine hiện dùng:

- `cdp_user_id` làm business identity.
- `cdp.profiles`: `home_city`, `vinclub_tier`, `lifecycle_stage`, `last_destination`.
- `ResolvedEvent`: `event_name`, `days_ago`, `trip_id`, `using_date`.
- Event weight: purchase `1.0`, cart `0.5`, view `0.2`, search `0.1`.
- Event được gom thành `Trip`: vector, tuổi, taxonomy đã mua, destination, `ends_on`.
- Profile gồm `u_long`, `active_trip`, `n_events`, `bought_units`.
- Ranking hiện tại: `0.6 * short + 0.25 * popularity + 0.15 * long`.
- MMR `lambda = 0.7`, tối đa 2 sản phẩm mỗi taxonomy.
- `because[]` được phân rã theo event.

Persona hiện chủ yếu là nhãn để kích hoạt branch; chưa trực tiếp tham gia vào công thức điểm. Đây là điểm cần nghiên cứu thêm.

## 2. Nguyên tắc chính

Với OTA du lịch, khách chỉ đi một hoặc hai lần mỗi năm vẫn là hành vi bình thường. Không nên coi một khách là dormant chỉ vì vài tháng không booking.

Cần phân biệt ba loại tín hiệu:

```text
u_session: khách đang quan tâm gì trong phiên hiện tại
u_trip:    ý định của chuyến đi hiện tại hoặc sắp tới
u_long:    sở thích dài hạn của khách
```

Đề xuất thời gian ban đầu:

| Profile | Khoảng thời gian | Ý nghĩa |
|---|---:|---|
| `u_session` | 0–14 ngày | Search, view, cart trong phiên hoặc giai đoạn gần đây |
| `u_trip` | 0–120 ngày hoặc đến hết `using_date` | Một chuyến đi đang hình thành hoặc sắp diễn ra |
| `u_long` | 2–5 năm | Sở thích và lịch sử booking dài hạn |
| Dormant | Thường từ 12 tháng không có tín hiệu mới | Không có session intent, active trip hoặc booking sắp tới |

Các khoảng thời gian này là baseline cần benchmark, không phải giá trị cố định.

## 3. Ba lớp profile

### 3.1 Session intent: 0–14 ngày

Dùng để hiểu khách đang làm gì ngay lúc này:

- Search.
- Product view.
- Add-to-cart.
- Nhiều hành vi cùng destination.
- Nhiều hành vi cùng taxonomy.

Nên dùng decay nhanh:

```text
half-life: 3–7 ngày
```

Ví dụ: khách từng mua Phú Quốc năm ngoái nhưng hôm nay xem liên tục resort Nha Trang. `u_session` phải ưu tiên Nha Trang.

### 3.2 Trip intent: 0–120 ngày

Dùng cho một chuyến đi đang hình thành hoặc sắp diễn ra:

- Có `using_date`.
- Booking đã mua nhưng chưa sử dụng.
- Search/view/cart cùng destination.
- Sản phẩm cross-vertical liên quan đến booking hiện tại.

Nếu có `using_date`, cần dùng:

```text
days_to_use = using_date - today
```

`using_date` quan trọng hơn `days_ago`. Một booking được tạo 45 ngày trước nhưng có ngày sử dụng tháng sau vẫn là intent hiện tại.

Nếu không có `using_date`:

```text
booking hoặc event cùng destination <= 30 ngày: có thể là current intent
booking gần đây: giữ trip intent tối đa khoảng 60–120 ngày
```

Sau khi chuyến đi kết thúc:

```text
trip contribution -> giảm về 0
long preference   -> vẫn giữ lại
```

### 3.3 Long-term preference: 2–5 năm

Dùng để biểu diễn sở thích tương đối ổn định:

- Thích resort biển.
- Thường đi Nha Trang hoặc Phú Quốc.
- Ưu tiên thương hiệu.
- Thường chọn phòng cao cấp.
- Thường đi gia đình.
- Thích combo hoặc vé vui chơi.

Nên decay theo event type:

| Event | Long-term retention đề xuất |
|---|---:|
| Purchase | 3–5 năm, decay chậm |
| Add-to-cart | 12–18 tháng |
| View | 3–6 tháng |
| Search | 1–3 tháng |

Purchase có tín hiệu mạnh hơn view. Một khách từng đặt resort gia đình nhiều lần vẫn có thể có preference đó dù 10 tháng chưa quay lại.

## 4. Định nghĩa dormant phù hợp với travel

Không nên dùng riêng điều kiện:

```text
if days_since_last_purchase > 365:
    dormant
```

Nên dùng:

```text
dormant =
    không có session intent gần đây
    AND không có active trip
    AND không có booking sắp tới
    AND không có meaningful event >= 365 ngày
```

Phân loại đề xuất:

| Trạng thái | Điều kiện gợi ý |
|---|---|
| Active planner | Search/view/cart trong 14 ngày |
| Recent traveler | Booking hoặc trip trong 0–120 ngày |
| Normal annual traveler | Không activity gần đây, lần mua gần nhất 4–12 tháng |
| Dormant | Không activity và booking từ 12–24 tháng |
| Deep dormant | Không activity trên 24 tháng |

Dormant nên dùng để điều chỉnh chiến lược recommendation và lifecycle marketing, không nên xoá long-term preference.

## 5. Xử lý persona

Persona không nhất thiết phải được đưa vào embedding. Nên dùng persona để điều chỉnh:

- Prior.
- Decay.
- Candidate strategy.
- Score weights.
- Threshold chuyển đổi giữa content và popular.

| Persona | Profile chính | Candidate chính | Tín hiệu bổ sung |
|---|---|---|---|
| Frequent | `u_session + u_trip + u_long` | ANN theo active destination, cross-vertical | Destination, taxonomy đã mua, `using_date` |
| Dormant | `u_long` decay nhẹ + popular | Popular theo destination/mùa + content | `last_destination`, `lifecycle_stage`, `vinclub_tier` |
| First time | `u_session` | Content top-K + popular | Search/view hiện tại, destination đang xem |
| No history | Không có vector | Contextual popular | `home_city`, `vinclub_tier`, mùa, destination |

## 6. Trọng số theo persona

Baseline cấu hình:

```python
PERSONA_CONFIG = {
    "frequent": {
        "session_weight": 0.20,
        "trip_weight": 0.50,
        "long_weight": 0.10,
        "pop_weight": 0.20,
        "candidate_mode": "active_trip",
    },
    "dormant": {
        "session_weight": 0.00,
        "trip_weight": 0.00,
        "long_weight": 0.30,
        "pop_weight": 0.70,
        "candidate_mode": "seasonal_last_destination",
    },
    "first_time": {
        "session_weight": 0.60,
        "trip_weight": 0.00,
        "long_weight": 0.00,
        "pop_weight": 0.40,
        "candidate_mode": "session_content",
    },
    "no_history": {
        "session_weight": 0.00,
        "trip_weight": 0.00,
        "long_weight": 0.00,
        "pop_weight": 1.00,
        "candidate_mode": "contextual_popular",
    },
}
```

Công thức tổng quát:

```text
score(i | u, context) =
    w_session(persona) * sim(u_session, i)
  + w_trip(persona)    * sim(u_trip, i)
  + w_long(persona)    * sim(u_long, i)
  + w_pop(persona)     * popularity(i, context)
  + w_dest             * destination_match(i, context)
  + w_tier             * tier_affinity(i, user)
  + w_fresh            * freshness(i)
  - w_repeat           * repeat_penalty(i)
```

Các trọng số cần được tune theo offline evaluation và A/B test.

## 7. Xử lý `using_date` và `active_trip`

Logic hiện tại:

```text
ends_on >= today OR age <= 14 days
```

có thể đánh dấu nhầm trip cũ là active. Nên tách:

```text
active_trip  = trạng thái nghiệp vụ của booking/trip
current_intent = tín hiệu hành vi gần đây
```

Logic đề xuất:

```python
if using_date exists:
    active_trip = using_date >= today - grace_period
    days_to_use = using_date - today
elif booking exists:
    active_trip = booking_age <= 120 days
elif recent_events_share_destination:
    current_intent = event_age <= 14 days
else:
    no_active_intent = True
```

`using_date` nên được dùng để:

- Xác định trip còn hiệu lực.
- Tính mức độ urgency.
- Lọc availability.
- Tăng điểm sản phẩm cùng destination.
- Chọn sản phẩm cross-vertical phù hợp.

Không nên đưa ngày, giá hoặc availability vào content embedding; các trường này nên dùng làm filter và ranking feature.

## 8. Event decay đề xuất

Không nên áp một half-life cho mọi event:

```text
purchase:
    trip: 60 ngày nếu trip chưa kết thúc
    long: 365–730 ngày

cart:
    session: 7 ngày
    long: 90–180 ngày

view:
    session: 3–7 ngày
    long: 30–90 ngày

search:
    session: 1–3 ngày
    long: 14–30 ngày
```

Công thức tổng quát:

```text
contribution(event) =
    event_weight
  * min(repeat_count, 3)
  * 2 ** (-age_days / half_life)
```

Cần chặn burst view để một sản phẩm được xem nhiều lần không lấn át toàn bộ profile.

## 9. Ranking và diversity

Sau khi tạo profile:

```text
1. Candidate generation: ANN, seasonal popular, destination popular, cross-vertical.
2. Filter: availability, sản phẩm đã mua, taxonomy/destination rules.
3. Score: similarity + popularity + context.
4. MMR lambda = 0.7.
5. Tối đa 2 sản phẩm mỗi taxonomy.
6. Trả top 3–5.
```

`because[]` hiện phân rã được phần similarity theo event. Tuy nhiên ranking còn popularity và context, nên nên phân biệt:

```text
because:
  - semantic_history
  - popularity
  - destination_context
  - loyalty_context
```

Nếu không có căn cứ, để `because[]` rỗng; không tạo lý do giả.

## 10. Vấn đề latency hiện tại

Luồng hiện tại có khả năng là:

```text
request
 → CdpClient lấy profile/events
 → ResolvedEvent
 → gom Trip
 → build u_long/active_trip
 → candidate ANN
 → score
 → MMR
 → ProductDetail
 → response
```

Không nên chạy toàn bộ luồng này đồng bộ trong request. Điểm nghẽn chính là đọc history và dựng `Trip/Profile`, không phải MMR.

## 11. Kiến trúc offline/nearline đề xuất

```text
CDP/event stream
  ├─ view
  ├─ search
  ├─ add_to_cart
  ├─ purchase
  └─ session/context event
        │
        ▼
Profile materializer
  ├─ ResolvedEvent
  ├─ Trip summaries
  ├─ u_session
  ├─ u_trip
  ├─ u_long
  ├─ active_trip/current_intent
  ├─ persona
  └─ context features
        │
        ▼
Candidate materializer
  ├─ ANN content candidates
  ├─ seasonal popular
  ├─ destination popular
  └─ cross-vertical candidates
        │
        ▼
Redis/KV recommendation cache
```

Request online:

```text
GET /recommendations
  → đọc profile đã materialize
  → đọc recommendation/candidate cache
  → filter availability
  → lightweight ranking
  → response
```

Cache miss chỉ được phép chạy profile đã precompute và candidate retrieval nhẹ; sau đó refresh cache asynchronous.

## 12. Dữ liệu nên materialize

Đề xuất bảng/cache `app.user_recommendation_profile`:

```text
cdp_user_id
persona
home_city
vinclub_tier
lifecycle_stage
last_destination

u_session
u_trip
u_long
active_trip_id
active_destination
current_intent
days_to_use

purchased_taxonomies
bought_units
recent_event_ids
profile_version
computed_at
expires_at
```

Không cần lưu toàn bộ `ResolvedEvent` trong request path. Chỉ cần:

- Vector tổng hợp.
- Một số event/product ID gần nhất để tạo `because[]`.
- Trip summary.
- Exclusion list.
- Feature dùng cho ranking.

## 13. Cache và TTL

| Thành phần | TTL đề xuất |
|---|---:|
| Item embedding | Đến khi product thay đổi |
| User long profile | 6–24 giờ |
| User trip/session profile | 5–30 phút |
| Seasonal popularity | 1–6 giờ |
| Trending counter | 5–15 phút |
| Recommendation list | 5–30 phút |
| Anonymous recommendation | 15–60 phút |

Key gợi ý:

```text
profile:{cdp_user_id}:v{profile_version}
recs:{cdp_user_id}:{surface}:{destination}:{model_version}
recs:anonymous:{surface}:{destination}:{season_version}
```

## 14. Cập nhật profile theo event

Không cần tính lại từ đầu. Với item vector có sẵn:

```text
new_profile = normalize(
    decay(old_profile, elapsed_time)
    + event_weight * item_vector
)
```

### Event policy

| Event | Cập nhật profile | Xóa recommendation cache | Candidate |
|---|---|---|---|
| Purchase | Ngay lập tức | Có | Ngay lập tức hoặc async |
| Add-to-cart | Vài giây | Có ở surface liên quan | Async |
| Search | Micro-batch/session | Session cache | Async |
| Product view | Session state | Không nhất thiết | Micro-batch |
| Impression | Chỉ log | Không | Không |
| Availability change | Không | Theo item/destination | Có |

Purchase cần near-real-time. View không nên làm request chờ.

## 15. Fallback và latency budget

Đề xuất deadline API: 100–150 ms.

```text
0–20 ms:   đọc recommendation cache
20–50 ms:  đọc profile + candidate cache
50–90 ms:  lightweight rank/filter
90–120 ms: fallback nếu dependency chậm
> deadline: trả stale cache hoặc popular
```

Thứ tự fallback:

1. Recommendation cache còn hạn.
2. Cache cũ nhưng còn trong stale window.
3. Popular theo persona/destination/mùa.
4. Global seasonal popular.
5. Danh sách có availability mặc định.

Không để lỗi CDP, embedding hoặc ANN làm API trả empty page.

## 16. Research cần bổ sung

### 16.1 Ablation theo profile

So sánh:

```text
V0: score hiện tại
V1: u_short + u_long
V2: u_session + u_trip + u_long
V3: V2 + home_city
V4: V3 + vinclub_tier
V5: V4 + lifecycle_stage/last_destination
V6: V5 + using_date/days_to_use
V7: persona-specific weights
```

### 16.2 Ablation theo popularity

- Global popular.
- Seasonal popular.
- Destination popular.
- Destination + taxonomy popular.
- Destination + taxonomy + persona bucket.
- Destination + taxonomy + persona + season.

### 16.3 Metric offline

- Recall@10/20.
- NDCG@5/10.
- MRR.
- Coverage.
- Diversity.
- Freshness.
- Explanation coverage.

### 16.4 Metric online

- Impression-to-click rate.
- Detail-view rate.
- Add-to-cart rate.
- Purchase conversion.
- Revenue hoặc booking value.
- Reactivation rate của dormant.
- P95 latency.
- Cache hit rate.
- Tỷ lệ fallback.
- Empty-response rate.

Không nên chỉ tối ưu CTR nếu mục tiêu chính là booking.

## 17. Lộ trình ưu tiên

### P0 — giảm latency

1. Materialize profile vào bảng hoặc Redis.
2. Không gọi full history trong `/recommendations`.
3. Không embed lại user/item trong request.
4. Precompute candidate top-200.
5. Cache recommendation theo user/surface/context.
6. Thêm timeout và stale-cache fallback.
7. Log latency từng stage.

### P1 — cải thiện chất lượng

1. Đưa CDP attributes vào ranking feature.
2. Tách `active_trip` khỏi `current_intent`.
3. Tạo `u_session` riêng cho first-time.
4. Dùng `using_date` để điều chỉnh urgency.
5. Tune weight theo persona.

### P2 — nghiên cứu mở rộng

1. Contextual popularity.
2. EASE khi đủ interaction.
3. LightGBM ranker.
4. Bandit/A-B test theo slot.
5. Fine-tune embedding nếu retrieval mới là bottleneck.

## 18. Kết luận

Đối với khách du lịch/khách sạn:

```text
session: 0–14 ngày
trip:    0–120 ngày hoặc đến hết using_date
long:    2–5 năm, decay theo event type
dormant: thường từ 12 tháng không có tín hiệu mới
```

Thay đổi có giá trị nhất là:

```text
ResolvedEvent → Trip → Profile
```

được chuyển sang event-driven materialization. Request chỉ nên thực hiện:

```text
materialized Profile
→ cached candidates
→ lightweight ranking
→ response
```

Persona nên được dùng để điều chỉnh profile, decay, candidate và ranking; không chỉ là nhãn để chọn branch.
