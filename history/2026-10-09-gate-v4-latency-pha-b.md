# Gate baseline_v4 và latency đầu-cuối sau khi áp [D] + [E] (Pha B, phần đã chốt)

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành (phần [D] + [E]); O1 + O4 dang dở chờ chốt đề xuất [F]
- Phạm vi: evaluation, docs

## Mục tiêu

Pha B của `docs/plan/2026-10-09-recsys-cong-thuc-oph.md`: sau khi engine đổi (`configHash 3c6ca566 → dcbf67ca`), ghi baseline gate mới và đo latency đầu-cuối TRƯỚC / SAU theo tiêu chí G1. FR-REC-01, FR-REC-02, NFR-PERF-01.

## File thay đổi

- `src/evaluation/recsys_bench/frozen/baseline_v4-{llbo,temporal,nexttrip,coldstart}-prodcopy-asof20261008.json` — thêm: baseline gate cho engine `2026-10-09-booked-first` + `DORMANT_AFTER_DAYS = 365`
- `src/evaluation/reports/eval-2026-10-09-recsys-gate-v4-booked-first-dormant365.md` — thêm: report gate v3 → v4 và latency 4 lượt xen kẽ
- `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` — sửa: §0.2 trạng thái Pha B

## Quyết định

- `regress` so `baseline_v3` exit 2 (không so được theo thiết kế); đối chiếu tay: recall không đổi (llbo −0,0002), nhãn `dormant` nexttrip 447 → 0.
- Latency đo bằng backend local cổng 8010 trên DB `vota_prodcopy` + Weaviate local (cần `WEAVIATE_GRPC_PORT=55051`; thiếu biến này backend tắt RecSys — lượt đầu bị bỏ, không tính số); TRƯỚC = worktree tạm `2600ca5` (đã xoá).
- Lệch 1 khách giữa arm `content_profile` và `engine` ở nexttrip có sẵn từ v3 (ngày UTC trong `models/seeds.profile_for`), ghi caveat, không sửa trong thay đổi này.

## Kiểm tra

- Gate 4 kind: run exit 0; `regress` vs v4 exit 0 4/4.
- Latency: SAU p95 79,0–81,0 ms vs TRƯỚC 78,0–81,0 ms, Δ tối đa +3 ms ≤ 50 → đạt G1; parity SAU 60/60 cả hai lượt.

## Còn lại / rủi ro

- Đề xuất [F] (O1 điểm xuất phát + O4 gộp lượt xem) chờ người dùng chốt; sau đó cài vào engine, baseline_v5, latency lại.
- Môi trường dev / staging chạy lại seed để tài khoản P3 ra `dormant`.
