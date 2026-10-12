# Chuẩn hoá mức liên quan với sở thích và giới hạn số món mỗi điểm đến khi khách không có chuyến đang mở

- Ngày: 2026-10-08
- Người đề xuất: tqanh123 / Claude Code soạn
- Trạng thái: đã áp dụng (2026-10-09: PRD FR-REC-04 / FR-REC-02, engine PR-B, spec §4.7, `baseline_v6`) — G2 chốt lại = (a) (`quyet-dinh.md` §7.7), G5b chốt 09/10
- Chốt bởi / ngày: tqanh123, 2026-10-09
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.3 FR-REC-04, FR-REC-02 (câu cuối)
- Mã FR/NFR: FR-REC-01, FR-REC-02, FR-REC-04

## Lý do

1. Khi khách **không có chuyến đang mở**, gợi ý production gần như không theo sở thích: khách thích núi chỉ 17 % món đúng chủ
   đề, thích phố 23 % (ngẫu nhiên 33 %). Nguyên nhân: cos của e5-small dồn sát nhau (0,82–0,94, p90 − trung vị 0,012) nên
   `0,15 · pop` lấn át phần sở thích dù trọng số danh nghĩa 0,7 / 0,15 / 0,15
   (`docs/spec/bench/recsys-bam-so-thich-tong-hop.md` §3.B).
2. Đưa cos về cùng thang với pop bằng calibration phân vị cố định (F14c) nâng tỷ lệ đúng chủ đề 0,439 → 0,769 (lịch sử
   sạch) và 0,376 → 0,703 (có lướt xem nhiễu), CI ghép cặp 95 % cận dưới > +0,29
   (`src/evaluation/reports/eval-2026-10-08-recsys-so-thich-ci.md`).
3. Công thức bám sở thích làm giảm **độ phủ điểm đến** (món gần `u_long` dồn vào ít điểm đến); giới hạn **2 món mỗi điểm đến**
   ở bước MMR đưa khoảng cách độ phủ so với production từ −0,296 về −0,049 mà chỉ trả 0,013 theme
   (`eval-2026-10-08-recsys-g2-va-wp4.md` §3).
4. **Chi phí đo được** (bản sao production, toàn bộ khách): temporal h@20 −0,0310 [−0,0465, −0,0168] (đạt G1 = 0,04);
   nexttrip h@20 −0,0316 [−0,0409, −0,0218]. Hai split này **không đo được lợi ích** vì bộ sinh event bốc điểm đến độc lập với
   khách (`seed_histories.py`), nên cần G6 trước khi chốt (`quyet-dinh.md` §7.1–7.2).

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.3 — FR-REC-04

Hiện tại:

> Sắp xếp thứ tự danh sách sản phẩm dựa trên trọng số kết hợp giữa độ liên quan ngữ nghĩa, mức độ ưa chuộng của cộng đồng và tính khả dụng của sản phẩm.

Thêm sau câu trên:

> Khi khách **không có chuyến đang mở**, độ liên quan ngữ nghĩa được **chuẩn hoá về cùng thang** với mức độ ưa chuộng trước
> khi kết hợp (ngưỡng chuẩn hoá cố định, gắn với model embedding và phiên bản text builder đang dùng; lệch model thì engine
> dùng lại công thức cũ và ghi cảnh báo), để sở thích dài hạn của khách quyết định thứ tự chứ không chỉ độ phổ biến. Danh
> sách gợi ý khi đó **không quá 2 món ở cùng một điểm đến** (không áp dụng khi yêu cầu đã khoá điểm đến).

### `docs/prd/requirements.md` §1.3 — FR-REC-02 (câu cuối)

Hiện tại:

> **Sau khi chuyến đã diễn ra xong**, hệ thống gợi ý cho chuyến kế tiếp: không loại loại sản phẩm đã mua, không khoá điểm đến X; dùng lịch sử dài hạn và mức phổ biến.

Thay bằng:

> **Sau khi chuyến đã diễn ra xong**, hệ thống gợi ý cho chuyến kế tiếp: không loại loại sản phẩm đã mua, không khoá điểm đến X; dùng lịch sử dài hạn và mức phổ biến theo cách kết hợp ở FR-REC-04 (sở thích đã chuẩn hoá, tối đa 2 món mỗi điểm đến).

### Tham số (ghi ở spec, không ở PRD)

`s = clip((cos(u_long, v) − 0,8529) / (0,9387 − 0,8529), 0, 1)`; `final = 0,50·s + 0,35·pop + 0,15·s`; `MAX_PER_DESTINATION = 2`;
ngưỡng calibrate trên 120 request khách giả lập (seed 99), bền qua seed (±0,3 %); gắn với
`intfloat/multilingual-e5-small` + `catalog-text-v2`. Có chuyến mở: giữ nguyên 0,7 / 0,15 / 0,15.

### Tiêu chí nghiệm thu (G1 đã chốt 08/10) và điều kiện trình chốt

| Chỉ số | Ngưỡng | Hiện có (bản sao production) |
|---|---|---|
| LLBO h@4 | CI chứa 0 | −0,0005 [−0,0020, +0,0010] ✅ |
| theme `between` / `noisy_paired` | ≥ +0,15, cận dưới CI > 0,10 | +0,317 / +0,322 ✅ |
| temporal h@20 | ≥ −0,04 (điểm ước lượng) | −0,0310 ✅ |
| `open` | không đổi | lệch đúng 0 ✅ |
| latency p95 `/recommendations` | Δ ≤ 50 ms đầu-cuối | ranking-only +0,63 ms; đầu-cuối đo ở lane A1 |
| nexttrip **hit@4** (G2 chốt lại 09/10, lựa chọn (a): list khách thật nhìn thấy) | CI chứa 0 | **G6: −0,0039** [−0,0097, +0,0019] ✅ |
| nexttrip h@20 (list 20, chỉ để theo dõi) | không còn là tiêu chí | −0,0316 (prodcopy); G6 −0,0322 [−0,0425, −0,0219] |
| nexttrip destHit@20 (G6, dữ liệu có sở thích) | cận dưới CI > 0 | **+0,0425** [+0,0213, +0,0631]; khách có chủ đề +0,0494 |

Luật đóng G2 đề nghị trên DB G6: D1 nexttrip h@20 cận dưới CI ≥ −0,01 · D2 nexttrip `destHit@20` cận dưới CI > 0 · D3 LLBO h@4
và coldstart CI chứa 0 · D4 temporal ≥ −0,04 · D5 `tgtHit@20` / `nextDestHit@20` khách giả lập cận dưới > 0.

**Kết quả G6 (09/10, `src/evaluation/reports/eval-2026-10-09-recsys-g6-so-thich-do-lai.md`):** D2, D4 đạt; D3 đạt trong dung
sai 0,01; D5 nửa đạt; D1 trên hit@20 không đạt ở mọi cấu hình vì bộ sinh chọn món trong điểm đến theo độ phổ biến.
**Người dùng chốt lại G2 ngày 09/10 theo lựa chọn (a)** (`quyet-dinh.md` §7.7): D1 định nghĩa lại trên nexttrip **hit@4**
(−0,0039, CI chứa 0 → đạt); chi phí hit@20 món được theo dõi sau deploy. Với định nghĩa này mọi dòng trong bảng đạt → trình
chốt G5b.

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md` FR-REC-04, FR-REC-02 (trước), rồi (P2, `Trip.confidence`, đã ship PR-A 09/10 — không còn trong danh sách này):
- `src/backend/app/domain/recommendation/profile.py`: hằng `SEMANTIC_Q_LOW`, `SEMANTIC_Q_HIGH`, `SEMANTIC_CALIBRATION_MODEL_VERSION`,
  `W_NEXT_SHORT / W_NEXT_POP / W_NEXT_LONG = 0,50 / 0,35 / 0,15`, `MAX_PER_DESTINATION = 2`; `calibrated_similarity()`,
  `calibration_applies()`; `score_candidates(..., next_trip_scoring)`; `mmr_select(..., destination, max_per_destination)`;
  tăng `ENGINE_RULES_VERSION`.
- `src/backend/app/application/recommendation/use_cases.py`: nhánh không chuyến mở dùng công thức mới khi `index.model_version`
  khớp tag, ngược lại công thức cũ + WARNING; truyền `space.destination` tại thời điểm MMR; không áp cap khi request khoá
  `destination`. `core/config.py` + `main.py`: `recommend_next_trip_scoring`, `recommend_max_per_destination` (rollback bằng env).
- `src/evaluation/recsys_bench/engine.py`: `OfflineEngine` nhận hai tham số, `engine_config` ghi chúng; CLI
  `theme_study/calibrate.py` để calibrate lại khi đổi model.
- Spec `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4, §4.7. Contract OpenAPI không đổi.
- Test unit hai nhánh công thức, cap điểm đến, guard model; test `SEMANTIC_CALIBRATION_MODEL_VERSION == f"{embed_model}:{TEXT_BUILDER_VERSION}"`;
  engine thật phải tái sinh số nghiên cứu trên split prodcopy (LLBO h@4 0,5324, nexttrip h@20 0,0469, nextDestHit@20 0,4181).
- Gate: baseline mới; latency đầu-cuối SAU; deploy theo `docs/prd/deployment-plan.md`.
