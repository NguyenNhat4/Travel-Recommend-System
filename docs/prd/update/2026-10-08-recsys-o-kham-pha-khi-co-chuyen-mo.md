# RecSys bám sở thích giữa hai chuyến và ô khám phá khi đang có chuyến

- Ngày: 2026-10-08
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.4 FR-REC-02, FR-REC-04
- Mã FR/NFR: FR-REC-01, FR-REC-02, FR-REC-04

## Lý do

Test production tối 07/10 (tài khoản thật, xem 8 sản phẩm biển Nha Trang + Vũng Tàu) và đo offline 08/10 trên bản sao catalog +
event production (`src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md`) cho thấy hai vấn đề:

1. **Khi không có chuyến mở, gợi ý gần như không theo sở thích.** Cosine của e5-small dồn sát nhau (mọi món 0,88–0,93), nên thành
   phần phổ biến `0,15 · pop` (thang 0–1) lấn át phần sở thích dù trọng số danh nghĩa là 0,7 / 0,15 / 0,15. Khách thích núi chỉ 17 %
   món đúng chủ đề, thích thành phố 23 % (ngẫu nhiên 33 %); ai cũng nhận Phan Thiết / Nha Trang / Hội An.
2. **Khi đang có chuyến mở, 0 % món ở điểm đến khác.** Khách đang xem biển Vũng Tàu không bao giờ thấy biển Đà Nẵng / Phú Quốc,
   kể cả khi list chưa đủ 4 món (trung bình 3,44 món vì giới hạn 2 món mỗi loại).

Số đo (bản sao production, chi tiết ở report):

| | Đúng chủ đề giữa 2 chuyến | LLBO hit@4 | temporal hit@20 | nexttrip hit@20 |
|---|---:|---:|---:|---:|
| hiện tại | 0,438 | 0,574 | 0,159 | 0,074 |
| A (pop 0,30) | **0,776** | 0,574 | 0,129 | 0,039 |
| A thận trọng (pop 0,45) | 0,556 | 0,574 | 0,138 | 0,046 |

Ô khám phá B: món ở điểm đến khác đúng chủ đề 79 % (ngẫu nhiên 33 %), LLBO / temporal hit@4 **không đổi** (chỉ lấp ô trống).
Lưu ý: event là dữ liệu giả lập chọn điểm đến theo độ phổ biến (không có sở thích), nên temporal / nexttrip thưởng món bán chạy và
không thể hiện được lợi ích bám sở thích — mức giảm ở hai cột này là cận trên của chi phí.

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.4 — FR-REC-02

Hiện tại (câu cuối):

> **Sau khi chuyến đã diễn ra xong**, hệ thống gợi ý cho chuyến kế tiếp: không loại loại sản phẩm đã mua, không khoá điểm đến X; dùng lịch sử dài hạn và mức phổ biến.

Thay bằng:

> **Sau khi chuyến đã diễn ra xong**, hệ thống gợi ý cho chuyến kế tiếp: không loại loại sản phẩm đã mua, không khoá điểm đến X; dùng lịch sử dài hạn và mức phổ biến, trong đó **mức liên quan với sở thích được chuẩn hoá trong từng lần gợi ý** để sở thích dài hạn (ví dụ khách hay đi biển, hay đi núi) quyết định thứ tự chứ không chỉ độ phổ biến. **Khi chuyến đang mở mà danh sách gợi ý tại X chưa đủ số món yêu cầu**, phần còn trống được lấp bằng sản phẩm ở điểm đến khác hợp với sở thích dài hạn của khách (mỗi điểm đến tối đa 1 món), xếp sau các món tại X.

### `docs/prd/requirements.md` §1.4 — FR-REC-04

Hiện tại:

> Sắp xếp thứ tự danh sách sản phẩm dựa trên trọng số kết hợp giữa độ liên quan ngữ nghĩa, mức độ ưa chuộng của cộng đồng và tính khả dụng của sản phẩm.

Thêm sau câu trên:

> Độ liên quan ngữ nghĩa được đưa về cùng thang với mức độ ưa chuộng trước khi kết hợp khi khách không có chuyến đang mở, để trọng số phản ánh đúng tỷ lệ đóng góp. Món khách đã xem vẫn được gợi ý lại (là tín hiệu mua mạnh).

## Thay đổi source sau khi chốt

- `src/backend/app/domain/recommendation/profile.py` — `score_candidates`: khi `profile.active_trip is None`, chuẩn hoá min-max
  `E @ u_short`, `E @ u_long` trên không gian ứng viên của request; hằng mới `W_SHORT_BETWEEN, W_POP_BETWEEN, W_LONG_BETWEEN =
  0.55, 0.30, 0.15` (hoặc 0.40 / 0.45 / 0.15 nếu chọn bản thận trọng); giữ nguyên nhánh có chuyến mở. Tăng `ENGINE_RULES_VERSION`.
- `src/backend/app/application/recommendation/use_cases.py` — sau `mmr_select`, nếu có chuyến mở và `len(chosen) < k`: lấp bằng món
  ngoài điểm đến X, ngoài loại đã mua trong chuyến, xếp theo `cos(profile.u_long, v)`, mỗi điểm đến 1 món; `because` theo `explain`.
  Không thêm lượt gọi Weaviate (chấm trên ứng viên / vector đã có, hoặc thêm 1 `near_vector(u_long)` không mask điểm đến — cần đo latency).
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4 / §4.7 — công thức + luật lấp ô; contract không đổi field.
- Test: unit `profile` (chuẩn hoá, nhánh có / không chuyến mở), `use_cases` (lấp ô, mỗi điểm đến 1 món, không trùng loại đã mua);
  bench `recsys_bench` thêm arm; đo lại LLBO / temporal / nexttrip / coldstart và AC-REC-01/02 trên bản sao production.
- (Khuyến nghị, tách riêng) thêm sở thích chủ đề vào bộ sinh event (`seed_histories.py`, `docs/spec/MOCK_DATA_SPEC.md`) để đo được
  lợi ích bám sở thích offline — cần chốt riêng.
