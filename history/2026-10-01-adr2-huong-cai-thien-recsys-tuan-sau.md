# ADR 2 — Hướng cải thiện recsys tuần sau (từ bảng thuật toán `algos_v1` Day 5)

- Ngày: 2026-10-01 (tối)
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `bench/day4-rec`
- Trạng thái: hoàn thành — **quyết định theo quy tắc, chưa đồng thuận** (plan Day 4–5 §2.4: họp chưa diễn ra; Lead xác nhận hoặc sửa)
- Phạm vi: evaluation, docs

## Mục tiêu

Plan `docs/plan/2026-10-01-plan-day4-5.md` §2.4 quyết định 2: từ bảng thuật toán hai chế độ và ceiling, ra **danh sách có thứ tự + owner**
cho tuần cải thiện (không ra số). `docs/decisions/` không có trong AGENTS.md §7 nên ADR ghi ở đây và tóm tắt ở
`docs/spec/bench/recsys-offline-eval.md` §4.17. Phục vụ FR-REC-01..04, test-plan §2.5. Bằng chứng:
`src/evaluation/reports/eval-2026-10-01-recsys-algos-v1.md`.

## File thay đổi

- `history/2026-10-01-adr2-huong-cai-thien-recsys-tuan-sau.md` — thêm: entry này (ADR). Thay đổi code / spec / report đi kèm ghi ở
  `history/2026-10-01-recsys-day5-full-run-baseline-because-bpr.md`.

## Quyết định

Áp quy tắc ghi trước (plan Day 5 A7) lên số thật của run `2026-10-01-{llbo,temporal}-algos-{funnel,raw}` (split `asof20260924`,
`configHash b0aee886`, `--vectors numpy`):

| Câu hỏi | Quy tắc | Số | Quyết định |
|---|---|---|---|
| Q1 Giữ `content_profile` (engine v5) làm lõi? | Giữ trừ khi một scorer thắng với CI loại 0 trên temporal và không thua LLBO | Temporal: mọi scorer ≤ content ở hit@20 (`star_blend` +0,0; CF −8 đến −10, CI loại 0); NDCG@10 `star_blend` −5,4 [−8,2; −2,7] | **Giữ** |
| Q2 Thêm co-occurrence / `star_blend` vào engine? | Vào grid nếu ΔNDCG@10 ≥ 0 hoặc CI chứa 0 **và** `Collab cov.` ≥ 0,10 | ΔNDCG@10 −1,2 (LLBO) / −5,4 (temporal), CI loại 0; `Collab cov.` 0,034 / 0,110; hit@20 LLBO +2,1 [+1,3; +3,0] | **Không** đưa vào engine; chỉ grid a ∈ {0,8; 0,9} ưu tiên thấp |
| Q3 Sửa filter? | Ceiling ≥ mpd → filter không phải nút thắt | Ceiling 0,988 / 0,918 ≥ mpd 0,602 / 0,102; funnel +44 điểm hit@20 ở LLBO | **Không** sửa filter; cap 2 / taxonomy (I-5) là nút thắt của list production (`engine_prod` 0,619 vs 0,848) → đề xuất PRD |
| Q4 Tham số nào vào grid (temporal)? | Chỉ tham số có bằng chứng ảnh hưởng | `H_*`: nodecay đổi < 0,2 điểm → bỏ; MMR −2,7 hit@20 LLBO; `W_SHORT/W_POP` grid lần 1 gợi ý; dormant 90/180 là lệch contract | Grid: `W_SHORT/W_POP`, rồi λ MMR (+ chuẩn hoá thang nếu thêm vế điểm); không grid `H_*`; dormant → đề xuất (I-8) |
| Q5 Harness trước tuning? | Có nếu số hiện tại bị thổi bởi đặc điểm dữ liệu | 441/1.016 khách LLBO đã `add_to_cart` (không gid) đúng target trước khi mua; `ials` 0,977 trên nhóm này, thua content −13,2 ở nhóm còn lại | **Có**: nhãn `targetInOwnHistory` + split biến thể trước grid |
| Q6 Chạy kiến trúc sâu? | Chỉ khi CF thuần vượt popularity | CF ≈ `pop_funnel` (CI chứa 0) cả hai split; U 1.486 × nnz 2.468 | **Không** |

Danh sách có thứ tự (owner; việc đổi hành vi production **chỉ là đề xuất** `docs/prd/update/`, không làm trước khi người dùng chốt —
AGENTS.md §8):

1. Giữ engine v5 (`content_profile`) làm lõi; không đưa CF / MF vào engine — Lead chốt.
2. Harness: thêm nhãn `targetInOwnHistory` vào `analyze`; split LLBO biến thể "bỏ target đã ở giỏ" hoặc "next trip" — R.
3. Đề xuất PRD cap theo `parentProductId` thay 2 / taxonomy (I-5) — C soạn, Lead chốt.
4. Grid temporal `W_SHORT / W_POP` ∈ {0,6/0,25; 0,7/0,15; 0,8/0,05} — R.
5. Grid temporal λ MMR ∈ {0,7; 0,85; 1,0}; chuẩn hoá thang điểm trước MMR chỉ khi #6 / #7 thêm vế mới vào điểm — R.
6. Nghiên cứu tín hiệu "đã cho vào giỏ, chưa mua" (nhắc lại item trong giỏ); có ích thì đề xuất PRD — R phân tích, Lead quyết.
7. `star_blend` a ∈ {0,8; 0,9} trên temporal — R, ưu tiên thấp.
8. Hỏi Data: seed gắn `eventGroupId` cho `add_to_cart` / view được không (co-occurrence theo chuyến hiện chỉ có purchase) — R → Data.
9. `DORMANT_AFTER_DAYS` 90 (contract) vs 180 (code), I-8 — C soạn đề xuất, Lead chốt.

Bỏ: grid `H_SHORT_DAYS / H_LONG_DAYS`; kiến trúc sâu (two-tower, Mult-VAE, SASRec, LightGCN). `bpr_dest` (phụ lục B của report): LLBO
hit@20 0,899 > content nhưng temporal thua −10,2 [−16,3; −5,1] → không vào grid tuần này; xem lại sau #2 (split không có tín hiệu giỏ).

Phần because (FR-REC-03): `content_profile` vi phạm luật contract ở khách `coldStart` / `dormant` (finding đã biết, phụ lục A của report) —
ghi cho Lead, không sửa engine tuần này.

## Kiểm tra

- Số trích từ run và `compare` thật (report mục 4–9); không chạy thêm gì cho entry này.

## Còn lại / rủi ro

- Chưa họp: Lead xác nhận hoặc sửa thứ tự; nếu sửa thì tạo entry mới `Thay thế: 2026-10-01-adr2-huong-cai-thien-recsys-tuan-sau.md`.
- Ba đề xuất PRD (#3, #6 nếu có ích, #9) chưa soạn — tạo trong `docs/prd/update/` khi Lead giao.
- Quyết định 1 (model + số chiều) và 3 (phạm vi tuần sau) của §2.4 thuộc track khác, không nằm trong ADR này.
