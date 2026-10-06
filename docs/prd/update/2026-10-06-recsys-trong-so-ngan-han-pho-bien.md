# Đổi trọng số điểm của engine gợi ý: tăng phần sở thích gần đây, giảm phần mức phổ biến

- Ngày: 2026-10-06
- Người đề xuất: Pham Nguyen Dang Khoi / Claude Code soạn
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: không đổi câu chữ. `docs/prd/requirements.md` §1.3 FR-REC-04 chỉ yêu cầu "trọng số kết hợp giữa độ liên quan ngữ nghĩa,
  mức độ ưa chuộng của cộng đồng và tính khả dụng", không ghi giá trị. Đề xuất này đổi **giá trị** trọng số, tức đổi thứ tự gợi ý người dùng
  thấy, nên đưa ra để nhóm chốt trước khi sửa engine.
- Mã FR/NFR: FR-REC-01, FR-REC-04 (kiểm lại AC-REC-01, AC-REC-02)

## Lý do

Điểm của mỗi ứng viên hiện là `0,6 × sở thích gần đây + 0,25 × mức phổ biến + 0,15 × sở thích dài hạn`. Đo offline trên bộ lịch sử đầy
đủ nhất hiện có (append-v1: 7.003 khách tổng hợp, 4 đề thi đóng băng, cùng vector e5-small), đổi thành **0,7 / 0,15 / 0,15**
(`W_LONG` giữ nguyên):

| Đề thi | Khách | Thứ hạng (NDCG@10) | Danh sách production 5 món (hit@20) | Danh sách 20 món (hit@20) |
|---|---:|---|---|---|
| Món tiếp theo trong chuyến (LLBO) | 4.021 | **+1,17** [+0,77; +1,58] | **+0,70** [+0,07; +1,32] | **−1,84** [−2,36; −1,32] |
| Mua gì sau mốc thời gian (temporal) | 774 | **+2,68** [+1,95; +3,45] | **+0,90** [+0,13; +1,81] | −0,65 [−1,68; +0,39] |
| Chuyến kế tiếp (nexttrip) | 1.835 | +0,12 [−0,10; +0,36] | −0,11 [−0,49; +0,27] | −0,16 [−0,93; +0,60] |
| Khách mua lần đầu (coldstart) | 5.231 | **+19,98** [+19,40; +20,57] | **+10,82** [+9,96; +11,70] | −0,32 [−0,73; +0,10] |

Điểm %, Δ = mới − hiện tại, CI95 paired bootstrap 10.000 lượt (**đậm** = có ý nghĩa). Nguồn: `src/evaluation/reports/eval-2026-10-06-recsys-search-tong-hop.md` phần A §4, §6.

- Danh sách khách thật sự thấy trên trang chủ là 5 món (`engine_prod`): tốt hơn ở 3/4 đề, hoà ở đề còn lại.
- Đánh đổi: danh sách 20 món (chế độ đánh giá) mất 1,84 điểm hit@20 ở LLBO — món đúng vẫn có trong danh sách nhưng ít hơn một chút ở vị
  trí 11–20, trong khi được đẩy lên cao hơn ở top-10.
- Các điểm khác trên temporal: 0,65 / 0,20 tăng ít hơn (+0,83 NDCG@10); 0,75 / 0,10 tăng NDCG nhiều hơn (+3,70) nhưng hit@20 −2,07;
  0,8 / 0,05 làm gãy đề chuyến kế tiếp (−3,54 hit@20). 0,5 / 0,35 và 0,4 / 0,45 kém hơn hiện tại. Kết hợp thêm λ MMR 0,85 không tốt hơn λ 0,7.

Giới hạn: dữ liệu lịch sử là dữ liệu sinh (phân bố do nhóm chốt); coldstart tăng mạnh vì khách mới thường đã xem đúng món ngay trước khi mua.

## Nội dung đề xuất

**`docs/prd/`:** không đổi câu chữ (FR-REC-04 không ghi số). Nếu nhóm muốn PRD ghi rõ, thêm vào cuối FR-REC-04:

- Thay "… mức độ ưa chuộng của cộng đồng và tính khả dụng của sản phẩm."
- bằng "… mức độ ưa chuộng của cộng đồng và tính khả dụng của sản phẩm. *(Trọng số hiện hành: sở thích gần đây 0,7 · mức phổ biến 0,15 ·
  sở thích dài hạn 0,15; chốt 2026-10-?? theo `update-archive/2026-10-06-recsys-trong-so-ngan-han-pho-bien.md`.)*"

## Thay đổi source sau khi chốt

- `src/backend/app/domain/recommendation/profile.py`: `W_SHORT, W_POP, W_LONG = 0.7, 0.15, 0.15`; tăng `ENGINE_RULES_VERSION` / `modelVersion`
  để `configHash` đổi.
- `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.7 (công thức điểm cuối — hiện ghi `cos + γ·log(1 + review_count)`, chưa khớp code
  ba thành phần) và §4.3–4.7 theo việc "chốt tham số recsys" của `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`.
- Kiểm lại: test `src/backend/tests/unit/domain/` của recommendation; lệnh `recsys_bench user --id VP0000001` (P1, AC-REC-02) và P3;
  `make recsys-gate-run` + ghi lại `baseline_v1` (`make recsys-baseline NOTE=…`) với entry `history/`.
- Đo lại p95 `/recommendations` không cần (chỉ đổi hằng số).
