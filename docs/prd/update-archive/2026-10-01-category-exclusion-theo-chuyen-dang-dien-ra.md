# Category exclusion và khoá điểm đến chỉ trong chuyến đang diễn ra, không áp cho chuyến kế tiếp

- Ngày: 2026-10-01
- Người đề xuất: tqanh123 / Claude Code (từ số đo harness RecSys offline)
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.3 FR-REC-02 (và sau khi chốt: `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.3–4.5)
- Mã FR/NFR: FR-REC-02, FR-REC-01

## Lý do

FR-REC-02 nói: *"Khi người dùng vừa đặt phòng khách sạn tại điểm đến X, hệ thống phải ưu tiên gợi ý vé máy bay đến X và các
hoạt động trải nghiệm tại X."* Engine hiện thực bằng **category exclusion + khoá điểm đến** cho mọi "trip đang mở" — trip có
event gần nhất trong 60 ngày (`ACTIVE_TRIP_MAX_AGE_DAYS`), không xét chuyến đã diễn ra hay chưa (`usingDate`).

Số đo 01/10 trên harness (`docs/spec/bench/recsys-offline-eval.md` §4.7–4.11, split đóng băng, seed 21/09):

| | Trong chuyến (LLBO, giấu purchase cuối của chuyến) | Chuyến kế tiếp (temporal, target = purchase đầu sau mốc T) |
|---|---:|---:|
| Target tới được mask ứng viên (ceiling) | 0,990 | **0,784** — 22 % target bị chính engine chặn: `taxonomy_excluded` 15/102, `destination_mismatch` 18/102 |
| Recall@20 engine | 0,851 | 0,196 |
| Khách `cross_vertical` | 911 khách, hit@20 0,844 | 22 khách, hit@20 **0,000** |

Tức là giả định cross-vertical đúng **trong** một chuyến, nhưng khi khách đã đi xong (hoặc đang chuẩn bị chuyến khác) mà vẫn
trong 60 ngày, engine vẫn loại taxonomy đã mua và khoá điểm đến cũ: khách vừa đi Nha Trang về, chuẩn bị đi Đà Nẵng, không bao
giờ được gợi khách sạn (đã mua hotel) hay sản phẩm ngoài Nha Trang. 94/102 target temporal là hotel.

## Nội dung đề xuất

**`docs/prd/requirements.md` §1.3 FR-REC-02** — hiện tại:

> Khi người dùng vừa đặt phòng khách sạn tại điểm đến X, hệ thống phải ưu tiên gợi ý vé máy bay đến X và các hoạt động trải nghiệm tại X.

Đề xuất thay bằng:

> Khi người dùng vừa đặt phòng khách sạn tại điểm đến X **và chuyến đó chưa diễn ra xong** (ngày sử dụng `usingDate` của các
> sản phẩm trong chuyến chưa qua, hoặc chưa có ngày sử dụng và đặt trong vòng N ngày), hệ thống phải ưu tiên gợi ý vé máy bay
> đến X và các hoạt động trải nghiệm tại X (loại các loại sản phẩm đã mua trong chuyến). **Sau khi chuyến đã diễn ra xong**, hệ
> thống gợi ý cho chuyến kế tiếp: không loại loại sản phẩm đã mua, không khoá điểm đến X; dùng lịch sử dài hạn và mức phổ biến.

N và cách xác định "đã diễn ra xong" (theo `usingDate` lớn nhất của chuyến, có dự phòng khi thiếu) là tham số engine, chốt bằng
grid-search trên split temporal đóng băng (B10), không ghi trong PRD.

## Thay đổi source sau khi chốt

- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.3 (tripFactor), §4.4 (bảng strategy: `cross_vertical` chỉ khi
  chuyến chưa xong), §4.5 (category exclusion chỉ trong chuyến chưa xong), tiêu chí 17.
- `src/backend/app/domain/recommendation/profile.py`: `Trip` thêm trạng thái "đã diễn ra xong" từ `usingDate`
  (`ResolvedEvent` cần mang `usingDate`), `active_trip` chỉ chọn chuyến chưa xong; `application/recommendation/use_cases.py`
  mask ứng viên theo đó. Hằng N vào `core/config.py`.
- Harness: `src/evaluation/recsys_bench/ceiling.py` `engine_view` mô phỏng luật mới; chạy lại temporal đóng băng, kỳ vọng ceiling
  → ≈ 1,0 và `cross_vertical` temporal > 0; LLBO không giảm (trong chuyến vẫn giữ exclusion).
- Contract không đổi (`strategy`, `excludedVerticals`, `destination` giữ nguyên ý nghĩa); chỉ hành vi chọn trip mở đổi.
