# Merge PR-A (feat/recSys_update) vào nhánh OPH-L và chỉnh harness theo engine mới

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Người dùng chốt gộp chuỗi O của `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` vào PR-A. PR-A (P2 + loại combo + ô khám phá B, commit `20ec374`) và lane B2 (`2f3b593`) đã có trên `feat/recSys_update`, nên merge vào trước khi làm Pha B. FR-REC-02, FR-REC-04.

## File thay đổi

- (merge) toàn bộ thay đổi của `feat/recSys_update` từ `a4f57e1` tới `2600ca5`
- `src/evaluation/recsys_bench/theme_study/profile_variants.py` — conflict: lấy bản `feat/recSys_update` (P2 là production, `cap_exempt` của nhánh này không còn cần)
- `src/evaluation/recsys_bench/theme_study/registry.py` — sửa: `P0`/`B0` = production mới (P2 + combo + ô B), `B1p` = `B0`, `B2` = `B0+F14c+destCap2`; token `P0legacy`, `noExplore`; bỏ gương ô B (`explore_fill` của harness) vì engine đã làm
- `src/evaluation/recsys_bench/theme_study/layered_profile.py` — sửa: dùng `Trip.confidence` của production; chuyến ảo có `confidence`
- `src/evaluation/recsys_bench/tests/test_oph.py` — sửa: kỳ vọng bí danh theo registry mới

## Quyết định

- Số TEST ngày 09/10 trong `eval-2026-10-09-recsys-cong-thuc-oph.md` đo trên engine trước PR-A + gương harness (B1′); không đo lại toàn bộ.

## Kiểm tra

- `pytest src/evaluation/recsys_bench/tests`: 190 passed, 3 skipped.
- Smoke `eval_oph` 150 khách / split + 3 kịch bản giả lập trên engine PR-A: parity `B0:V0p`, `B2:V2p` nDiscordant4 = nDiscordant20 = 0 mọi stratum.

## Còn lại / rủi ro

- Pha B: áp [D] (O3) vào engine; O1 + O4 chờ chốt đề xuất mới; áp [E].
