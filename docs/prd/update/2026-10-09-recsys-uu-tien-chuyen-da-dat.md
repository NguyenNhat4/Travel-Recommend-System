# Chuyến đã đặt chưa diễn ra được ưu tiên hơn lượt xem lẻ đến sau

- Ngày: 2026-10-09
- Người đề xuất: tqanh123 / Claude Code soạn
- Trạng thái: đã chốt (chưa áp dụng — áp dụng ở Pha B của plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md`)
- Chốt bởi / ngày: tqanh123, 2026-10-09
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.3 FR-REC-02
- Mã FR/NFR: FR-REC-02

## Lý do

1. FR-REC-02 yêu cầu: khi khách vừa đặt khách sạn tại X và chuyến chưa diễn ra xong, hệ thống **ưu tiên** vé máy bay đến X và
   hoạt động tại X. Engine hiện không làm đúng khi khách xem thêm sản phẩm sau khi đặt.
2. Nguyên nhân (lỗi I-3, `docs/spec/bench/recsys-offline-eval.md` mục Issue): view và cart không có `event_group_id` nên engine gom
   mỗi sản phẩm thành một chuyến `_solo_`. `active_trip` là chuyến mở **trẻ nhất** (`src/backend/app/domain/recommendation/profile.py:138-139`),
   nên một lượt xem sau khi đặt sẽ thay chỗ chuyến đã đặt. Khách mất `cross_vertical` và mất luật loại loại sản phẩm đã mua.
   Hành vi này đang được ghim bằng test `test_later_view_without_group_takes_over_the_open_trip`
   (`src/evaluation/recsys_bench/tests/test_engine_no_leak.py:43-53`).
3. Ví dụ: khách đặt khách sạn Đà Nẵng cho tuần sau, rồi mở xem một khách sạn ở Vũng Tàu. Trang chủ chuyển hẳn sang Vũng Tàu
   (`cold_start_content`), không còn gợi vé bay và vé tham quan Đà Nẵng.

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.3 — FR-REC-02

Hiện tại (câu đầu):

> Khi người dùng vừa đặt phòng khách sạn tại điểm đến X **và chuyến đó chưa diễn ra xong** (…), hệ thống phải ưu tiên gợi ý vé máy bay đến X và các hoạt động trải nghiệm tại X (loại các loại sản phẩm đã mua trong chuyến).

Thêm ngay sau câu trên:

> Chuyến **đã đặt** chưa diễn ra xong luôn được ưu tiên hơn các lượt xem hoặc thêm giỏ hàng **không thuộc chuyến nào** diễn ra
> sau đó: các hành vi này không thay thế chuyến đã đặt khi chọn điểm đến X. Nếu khách có nhiều chuyến đã đặt chưa diễn ra
> xong, chọn chuyến đặt gần nhất.

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md` FR-REC-02 (trước), rồi:
- `src/backend/app/domain/recommendation/profile.py`: `active_trip` = chuyến mở có purchase trẻ nhất; không có thì chuyến mở trẻ
  nhất như hiện tại. Tăng `ENGINE_RULES_VERSION`.
- Test: sửa `src/evaluation/recsys_bench/tests/test_engine_no_leak.py:43-53` (lượt xem sau không còn chiếm chuyến đã đặt),
  `src/backend/tests/unit/domain/test_recommendation_trip_open.py`; thêm test unit cho trường hợp nhiều chuyến đã đặt.
- Spec `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4–4.5 ghi luật chọn chuyến. Contract OpenAPI không đổi.
- Bench: bậc O3 của plan (kiểm non-inferiority LLBO h@4 cận dưới ≥ −0,01, temporal h@20 cận dưới ≥ −0,02; kịch bản
  `booked_browse` phải ra `cross_vertical`). Baseline gate mới vì `configHash` đổi.
