# Ô khám phá: lấp ô trống bằng món ở điểm đến khác khi khách đang có chuyến mở

- Ngày: 2026-10-08 (viết lại từ `2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md`; phần công thức tách sang
  `2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md`)
- Người đề xuất: Pham Nguyen Dang Khoi, tqanh123 / Claude Code soạn
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: tqanh123, 2026-10-09 (G5a — "chốt cả [A] và [C] như đề nghị"); PRD cập nhật 2026-10-09
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.3 FR-REC-02 (phần chuyến đang mở)
- Mã FR/NFR: FR-REC-02, FR-REC-01

## Lý do

1. Khi khách đang có chuyến mở tại X, engine khoá điểm đến X và giới hạn 2 món mỗi loại (FR-REC-02, spec §4.7), nên danh
   sách trang chủ trung bình chỉ **3,44 / 4 món** và **0 %** món ở điểm đến khác. Khách đang xem biển Vũng Tàu không bao giờ
   thấy biển Đà Nẵng / Phú Quốc, kể cả khi còn ô trống.
2. Đo trên bản sao production 08/10 với đúng tổ hợp sẽ triển khai (profile P2 + F14c), xếp hạng món khám phá theo
   `cos(u_long, v)` như engine sẽ làm (`src/evaluation/reports/eval-2026-10-08-recsys-g2-va-wp4.md` §4; lượt đo lại
   `eval_slots --how ulong` 08/10):

   | Biến thể | LLBO h@4 (4.072) | temporal h@4 (775) | thêm điểm đến khác / list (chuyến mở) | theme `open` |
   |---|---:|---:|---:|---:|
   | không có ô B | 0.5324 | 0.1045 | 0.000 | 0.833 |
   | **chỉ lấp ô trống (đề xuất)** | **0.5324** | **0.1045** | **0.292** | 0.823 |
   | thay hẳn ô 4 | 0.4998 | 0.1019 | 1.000 | 0.817 |

   Chỉ lấp ô trống **không đổi** độ chính xác (giống đến bốn chữ số) và thêm một điểm đến khác cho 29,2 % khách có chuyến
   mở; thay hẳn ô 4 mất 0,033 LLBO h@4 → luật là *lấp*, không *thay*.
3. **P2 (dựng profile):** `u_long` nhân độ tin cậy chuyến `min(1, Σ W_TYPE)` và không bỏ purchase / add_to_cart khỏi vector
   chuyến khi cap lặp. Không có chi phí nào phân biệt được trên split thật (mọi CI chứa 0, trừ LLBO nDCG@10 −0,0031) và giữ
   theme khi khách có lịch sử lướt xem (+0,175). PRD chỉ nói "dùng lịch sử dài hạn", không quy định cách gộp chuyến → P2 là
   chi tiết triển khai, **không phải lệch PRD**; ghi ở đây cho minh bạch vì ô B dùng `u_long` của P2.

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.3 — FR-REC-02

Hiện tại (phần chuyến đang mở):

> …hệ thống phải ưu tiên gợi ý vé máy bay đến X và các hoạt động trải nghiệm tại X (loại các loại sản phẩm đã mua trong chuyến).

Thêm ngay sau câu trên:

> Nếu danh sách tại X chưa đủ số món yêu cầu, **các ô còn trống** được lấp bằng sản phẩm ở điểm đến khác hợp với sở thích
> dài hạn của khách (khách sạn, hoạt động trải nghiệm hoặc combo; mỗi điểm đến tối đa một món; không gồm sản phẩm đã mua),
> xếp **sau** các món tại X; các món tại X không bị thay thế. Chiến lược gợi ý (`strategy`) và loại sản phẩm kế tiếp
> (`nextVertical`) vẫn tính trên các món tại X.

### Luật chi tiết (ghi ở spec §4.7)

- Chỉ khi có chuyến mở và `len(list) < k`; ứng viên: điểm đến ≠ X, `is_recommendable`, taxonomy ∈ {hotel, attraction, combo}
  (bản đã đo), loại mọi sản phẩm đã mua kể cả combo liên quan (đề xuất `2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md`);
  **không** loại taxonomy đã mua trong chuyến (khách sạn ở điểm đến khác là gợi ý cho chuyến sau — đúng bản đã đo).
- Xếp theo `cos(u_long, v)`; tối đa 1 món / điểm đến; nối sau món X; `because[]` phân rã từ `u_long`.
- Cần **một** lượt truy vấn vector bổ sung (`near_vector(u_long)` không khoá điểm đến) chỉ cho khách có chuyến mở mà list
  ngắn (≈ 29 % khách có chuyến mở). Điều kiện triển khai: latency đầu-cuối p95 `/recommendations` tăng ≤ 50 ms (G1), đo theo
  từng `strategy`; có công tắc cấu hình để tắt mà không cần deploy lại. Caveat: đo local không chứng minh được chi phí trên
  Weaviate Cloud khác region — nếu vỡ ngưỡng trên production thì tắt bằng công tắc.
- Giữ việc hiện lại món đã xem (ẩn món đã xem làm LLBO h@4 0,5324 → 0,3986).

### Tiêu chí nghiệm thu bổ sung (§3, thêm vào hàng AC-REC-02 hoặc ghi chú dưới bảng)

> Khi khối gợi ý tại điểm đến của chuyến đang mở có ít hơn số món yêu cầu, các ô còn lại hiển thị sản phẩm ở điểm đến khác
> phù hợp sở thích, xếp sau các món tại điểm đến đó.

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md` §1.3 FR-REC-02 (trước), rồi:
- `src/backend/app/domain/recommendation/profile.py`: P2 (`CAP_EXEMPT_EVENTS`, `Trip.confidence`, `u_long` nhân confidence,
  `explain()` theo), hằng `EXPLORE_TAXONOMIES`, `EXPLORE_MAX_PER_DESTINATION = 1`, `explain(..., long_term=True)`; tăng
  `ENGINE_RULES_VERSION`.
- `src/backend/app/application/recommendation/use_cases.py`: sau `mmr_select`, nếu có chuyến mở và `len(chosen) < k` →
  `_explore_fill()` (mask điểm đến ≠ X, whitelist taxonomy, loại closure đã mua, một `near_vector(u_long)`, 1 món / điểm đến,
  nối sau, `because[]`); `strategy` / `nextVertical` tính trên món X. `core/config.py` + `main.py`: `recommend_explore_fill`.
- Spec `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.3 (P2), §4.4 (ghi chú strategy không đổi), §4.7 (luật ô B).
  Contract OpenAPI **không đổi** (`RecommendationDiagnostics` giữ nguyên).
- Test unit domain (P2) + application (lấp ô, 1 món / điểm đến, không gọi vector khi đủ k, tắt công tắc = output cũ, không
  chuyến mở → không lấp); bỏ xfail `test_strong_events_weight_trip_vector` ở `src/evaluation/recsys_bench/tests`.
- Gate: baseline mới; **latency đầu-cuối trước / sau** (plan lane A1 và PR-A); deploy theo `docs/prd/deployment-plan.md`.
