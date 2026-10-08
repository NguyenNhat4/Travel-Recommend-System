# Harness bench OPH-L (S1 của plan công thức điểm mới)

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: dang dở
- Phạm vi: evaluation

## Mục tiêu

Bước S1 của `docs/plan/2026-10-09-recsys-cong-thuc-oph.md`: dựng harness để bench công thức OPH-L so với production, không sửa engine. FR-REC-01, FR-REC-02, FR-REC-04.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/registry.py` — thêm: tên cấu hình (token + bí danh B0/B1p/B2/V0p…/O1–O5/N1–N4) → cài monkeypatch; gương ô B (`explore_fill`); token trần `origTgt`, `cartTgt`
- `src/evaluation/recsys_bench/theme_study/layered_profile.py` — thêm: ưu tiên chuyến đã đặt (I-3), chuyến ảo T_S, dormant `H_L × m`, nhãn `segment` (365 ngày) / `ctx0` / `ctx`
- `src/evaluation/recsys_bench/theme_study/oph_scorer.py` — thêm: hàm điểm OPH-L (nhánh mở: phạt/mask origin, cart; nhánh không chuyến: F14c, mask origin, w_pop theo segment)
- `src/evaluation/recsys_bench/theme_study/origin.py` — thêm: suy điểm xuất phát từ event chuyến bay gần nhất, vector `mis`
- `src/evaluation/recsys_bench/theme_study/pop_smooth.py` — thêm: `pop_h` (decay + shrinkage theo điểm đến × taxonomy), cài thay `Popularity.unit_scores` theo `ctx`
- `src/evaluation/recsys_bench/theme_study/pool.py` — thêm: bọc `VectorSearchPort` đưa món trong giỏ vào pool
- `src/evaluation/recsys_bench/theme_study/eval_oph.py` — thêm: script đo (split đóng băng có kiểm sha256, TUNE/TEST, dòng per-user có segment/ctx/origin/tgtInCart/mrr@20/list20, `--parity`)
- `src/evaluation/recsys_bench/theme_study/profile_variants.py` — sửa: công tắc `cap_exempt` (CAP_EXEMPT_EVENTS của PR-A) + profile `P2x_prA`
- `src/evaluation/recsys_bench/theme_study/paired_ci.py` — sửa: thêm `p` bootstrap (p = 1 khi không khác), `lo90_1s`, `mrr@20`, `--split-by`, `--family` + Holm
- `src/evaluation/recsys_bench/tests/test_oph.py` — thêm: 32 test không cần DB

## Quyết định

- Script đo mới `eval_oph.py` thay vì sửa `eval_profile.py`: lane B đang sửa file đó ở bản checkout chính.
- B1′ = P2 (confidence + cap_exempt) + ô B; **chưa có gương loại combo** (đề xuất [C] đo ảnh hưởng offline ≈ 1 khách). Ghi vào report.
- Plan §5.1 mục 10 ghi "sửa p-value": `paired_ci.py` trước đây không tính p; nay thêm p đúng công thức plan, không sửa trường cũ.
- Lớp `layered_profile` luôn được cài (công tắc tắt → trả đúng đối tượng của bản nền) để mọi cấu hình kể cả B0 có nhãn `segment`/`ctx0`.
- `--split-source frozen`: dựng lại split trên event đã qua `filter_events` với tham số của file đóng băng rồi `Split.verify` (temporal dựng theo quantile 0,8 như lúc đóng băng).

## Kiểm tra

- `pytest src/evaluation/recsys_bench/tests src/evaluation/recsys_bench/theme_study`: 186 passed, 3 skipped, 4 xfailed.
- Smoke `eval_oph` (40 khách / split, 5 khách giả lập / chủ đề, `--split-source frozen`, sha khớp): parity B0:V0p, B1p:V1p, B2:V2p nDiscordant4 = nDiscordant20 = 0 trên mọi stratum; 73 giây cho 8 cấu hình.

## Còn lại / rủi ro

- Chưa làm: trần Z-pop, arm D-shuffleO / D-ôNoTgt / D-O2 / D-pool / D-score / D-union / D-typeLong, ba kịch bản giả lập mới (`session_multi`, `booked_browse`, `dormant`), stage của `rank_latency`, hash `popularity.py` trong `engine_config`, sửa `dest_diversity` đọc `MMR_LAMBDA` lúc gọi.
- S2 (Phase 0 trên TUNE) tiếp theo.
