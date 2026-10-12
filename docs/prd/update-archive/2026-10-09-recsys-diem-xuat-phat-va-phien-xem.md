# Gợi ý chuyến bay theo điểm xuất phát của khách và gộp các lượt xem gần đây thành một ý định

- Ngày: 2026-10-09
- Người đề xuất: tqanh123 / Claude Code soạn
- Trạng thái: đã áp dụng (2026-10-09: PRD FR-REC-02 / FR-REC-04, engine `profile.py` + `use_cases.py`, spec §4.4 / §4.7, test, `baseline_v5`)
- Chốt bởi / ngày: tqanh123, 2026-10-09
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.3 FR-REC-02, FR-REC-04
- Mã FR/NFR: FR-REC-02, FR-REC-04

## Lý do

Người dùng chốt 09/10 gộp hai thay đổi này vào PR-A (plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §0). Số đo:
`src/evaluation/reports/eval-2026-10-09-recsys-cong-thuc-oph.md` (tham số chọn trên 30 % khách, kiểm một lần trên 70 % còn lại).

1. **Điểm xuất phát chuyến bay (O1).** Engine gợi mọi tuyến bay tới điểm đến X, kể cả tuyến bay từ thành phố khách không ở.
   Khách đã xem hoặc mua chuyến bay Hà Nội → Đà Nẵng vẫn thấy TP.HCM → Đà Nẵng ngang hàng. Trên bản sao production, 534/534 khách
   có từ 2 vé chỉ bay từ một điểm xuất phát. Hạ điểm tuyến bay có điểm xuất phát khác với điểm khách vừa bay (0,15 trên thang điểm
   hiện tại) nâng LLBO hit@20 +0,0261 [+0,0190, +0,0337]; lợi chủ yếu ở khách đã xem chính tuyến đó.
2. **Gộp các lượt xem gần đây (O4).** Mỗi sản phẩm khách xem mà không đặt là một "chuyến" riêng, và engine chỉ dùng chuyến **mới
   nhất**. Khách xem 4 resort Nha Trang rồi 1 resort Vũng Tàu sẽ chỉ thấy Vũng Tàu. Gộp các lượt xem đang mở (≤ 14 ngày, chưa đặt)
   thành một ý định với điểm đến là nơi khách xem nhiều nhất: nexttrip hit@20 +0,0080 [+0,0032, +0,0136] (có ý nghĩa sau Holm);
   kịch bản giả lập "xem hai điểm đến" chọn đúng điểm đến đa số 0,52 → 0,92.
3. Không đổi: luật chuyến mở / đã kết thúc, N = 14, nghĩa `usingDate`, chuyến **đã đặt** vẫn được ưu tiên (đề xuất
   `2026-10-09-recsys-uu-tien-chuyen-da-dat.md`, đã chốt). Contract OpenAPI không đổi; latency xếp hạng thêm ≤ 0,12 ms.

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.3 — FR-REC-02

Thêm vào cuối mục (sau câu về combo):

> Khi khách **chưa đặt** chuyến nào còn hiệu lực nhưng có nhiều lượt xem / thêm giỏ gần đây (trong N ngày) ở nhiều điểm đến, các
> lượt này được coi là **một ý định** và điểm đến được ưu tiên là nơi khách quan tâm nhiều nhất (theo số lượt và độ gần đây), không
> chỉ nơi xem sau cùng.

### `docs/prd/requirements.md` §1.3 — FR-REC-04

Hiện tại:

> Sắp xếp thứ tự danh sách sản phẩm dựa trên trọng số kết hợp giữa độ liên quan ngữ nghĩa, mức độ ưa chuộng của cộng đồng và tính khả dụng của sản phẩm.

Thêm sau câu trên:

> Với chuyến bay, tuyến có **điểm xuất phát khác** điểm xuất phát của chuyến bay khách vừa xem / đặt gần nhất bị xếp thấp hơn
> (khi khách đang có chuyến mở) hoặc không được gợi ý (khi không có chuyến mở). Khách chưa có lịch sử chuyến bay thì không áp dụng.

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md` FR-REC-02, FR-REC-04 (trước), rồi:
- `src/backend/app/domain/recommendation/profile.py`: `infer_origin(...)`; `W_ORIGIN = 0.15`; `H_SESSION_DAYS = 7`; chuyến ảo khi
  không có chuyến đã đặt mở và ≥ 2 chuyến chỉ-xem/giỏ mở; `score_candidates(..., context)` trừ `W_ORIGIN` / mask route sai điểm
  xuất phát; `explain()` phân rã theo chuyến ảo; tăng `ENGINE_RULES_VERSION`.
- `src/backend/app/application/recommendation/use_cases.py`: truyền `origin_city` của ứng viên (`UnitIndex.attrs.origin_city`) vào
  hàm điểm; `diagnostics.trips` vẫn đếm chuyến thật.
- Spec `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4, §4.7.
- Test unit domain / application; parity bench `B0+orig:pen:0.15+sess` của harness = engine mới (nDiscordant = 0); baseline gate mới;
  latency đầu-cuối SAU theo lane A1.
