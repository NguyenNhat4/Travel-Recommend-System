# Phase 2 TEST, latency và report công thức OPH-L

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành (phần bench S1–S5); S6 trình gate, S7 Pha B chờ người dùng
- Phạm vi: evaluation, docs

## Mục tiêu

S4–S5 của `docs/plan/2026-10-09-recsys-cong-thuc-oph.md`: chạy TEST một lần cho chuỗi đã đóng băng (`e182b94`), đo latency xếp hạng, viết report và mục quyết định. FR-REC-01, FR-REC-02, FR-REC-04, NFR-PERF-01.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-09-recsys-cong-thuc-oph.md` — thêm: report (cấu hình, parity, quyết định TUNE, TEST + Holm, gate, latency, caveat, lệnh tái sinh)
- `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` — sửa: thêm §8 (giữ / bỏ, TEST, gate chờ chốt)
- `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` — sửa: thêm §0.1 trỏ tới kết quả
- `src/evaluation/recsys_bench/theme_study/results/2026-10-09-oph/` — thêm: `p2_test_a.json`, `p2_test_b.json`, `p2_test_ci.json`, `p2_test_ci.txt`, `p2_test_by_target_seen.json`, `latency_llbo.json`, `latency_nexttrip.json`; sửa `SHA256SUMS`

## Quyết định

- TEST (seed 101/202/303, 70 % khách, split đóng băng khớp sha): Holm bác H0 cho llbo h@20 và nexttrip h@20 ở B1p → F_O, B2 → F, B0 → OPH-prod; không bác cho llbo không target-in-cart h@4 (phần lợi riêng của O1 không vững).
- OPH-prod (`B0+orig:pen:0.15+sess`) đạt G7; F (`B2+orig:pen:0.15+sess`) đạt G1 trừ câu hỏi G2 nexttrip vốn của F14c.
- Report ghi rõ lợi ích tập trung ở khách mà món đích đã có trong lịch sử (coldstart đích đã xem +624 / 3.594; đích mới chỉ +4 … +7).
- Latency xếp hạng trong tiến trình p95 2,8–3,8 ms, chuỗi O thêm ≤ 0,12 ms; số cũ 38,63 ms gồm bước dựng lại popularity (cache 8).

## Kiểm tra

- `pytest src/evaluation/recsys_bench/tests`: 186 passed, 3 skipped, 4 xfailed (chạy lại sau các sửa của Phase 1).
- Lệnh tái sinh: report §7 và khoá `args` của các file JSON.

## Còn lại / rủi ro

- S6: người dùng chốt bản đưa lên production (OPH-prod hay gộp PR-A / PR-B) và có cần đề xuất PRD cho O1 / O4 không (đề xuất [D] đã chốt chỉ phủ O3).
- S7 Pha B: sửa engine, test ≥ 80 %, parity HTTP, latency đầu-cuối; áp [D] và [E] (PRD trước).
- Chưa làm: trần Z-pop, arm D-*; gương loại combo trong B1′.
