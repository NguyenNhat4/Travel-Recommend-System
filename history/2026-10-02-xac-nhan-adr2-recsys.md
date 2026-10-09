# Xác nhận ADR 2 — hướng cải thiện recsys tuần sau

- Ngày: 2026-10-02
- Tác giả: tqanh123 (haisonqn2003) / Claude (agent)
- Nhánh: `bench/day4-rec`
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

ADR 2 (`history/2026-10-01-adr2-huong-cai-thien-recsys-tuan-sau.md`) ra theo quy tắc của plan Day 4–5 §2.4 nhưng ghi "chưa đồng thuận"
vì họp chưa diễn ra. Người dùng xác nhận ADR 2 ngày 02/10; entry này ghi lại xác nhận và đổi trạng thái ở các tài liệu trỏ tới ADR 2.

## File thay đổi

- `docs/spec/bench/recsys-offline-eval.md` — sửa: §4.17 trạng thái ADR 2 "đã xác nhận 02/10, giữ nguyên thứ tự"; dòng cập nhật lần cuối.
- `src/evaluation/reports/eval-2026-10-01-recsys-algos-v1.md` — sửa: mục 12 ghi đã xác nhận.
- `docs/plan/2026-10-01-chia-task-day4-search-rec.md` — sửa: hàng R11 ghi đã xác nhận, bỏ việc "Lead xác nhận thứ tự".

## Quyết định

- ADR 2 được xác nhận **nguyên văn**, không đổi thứ tự hay owner: (1) giữ `content_profile` (engine v5) làm lõi, không đưa CF / MF vào
  engine; (2) harness nhãn `targetInOwnHistory` + split LLBO biến thể trước grid; (3) đề xuất PRD cap theo `parentProductId` (I-5);
  (4) grid temporal `W_SHORT / W_POP`; (5) grid λ MMR; (6) nghiên cứu tín hiệu giỏ hàng chưa mua; (7) `star_blend` a ∈ {0,8; 0,9} ưu
  tiên thấp; (8) hỏi Data về `eventGroupId` cho `add_to_cart`; (9) I-8 dormant 90/180. Bỏ grid `H_*`, không chạy kiến trúc sâu.
- Xác nhận ADR 2 không đổi hành vi production và không lệch PRD; các mục đổi hành vi (#3, #6, #9) vẫn chỉ đi qua đề xuất
  `docs/prd/update/` (AGENTS.md §8). Entry ADR 2 gốc không sửa (history/README.md) — xác nhận ghi ở entry này.

## Kiểm tra

- Chỉ sửa tài liệu; không chạy lại run. `pytest src/evaluation/recsys_bench/tests` trước commit Day 5 `d1aeb3c`: 119 passed.

## Còn lại / rủi ro

- Ba đề xuất PRD (#3 I-5, #6 nếu có ích, #9 I-8) chưa soạn trong `docs/prd/update/`.
- Quyết định 1 (model embedding + số chiều) và 3 (phạm vi tuần sau) của plan §2.4 thuộc track khác, không nằm trong xác nhận này.
