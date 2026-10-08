# Đưa báo cáo đo RecSys bám sở thích (08/10) và đề xuất chờ chốt vào repo

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Lưu kết quả đo đêm 07–08/10 (RecSys có gợi ý theo sở thích biển / núi / thành phố không; 11 biến thể công thức; ô khám phá) vào repo
để sau này tổng hợp số liệu báo cáo. Phục vụ FR-REC-01, FR-REC-02, FR-REC-04.

## File thay đổi

- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — thêm: report đo trên bản sao production + local, số thô
  nguyên văn, caveat, lệnh tái sinh, đo kèm production (test persona biển, latency).
- `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` — thêm: đề xuất sửa FR-REC-02 / FR-REC-04, trạng thái `chờ chốt`.

## Quyết định

- Report đặt ở `src/evaluation/reports/` theo AGENTS.md §7; đề xuất lệch PRD đặt ở `docs/prd/update/` theo §8, chưa có hiệu lực.
- Không đưa script thử nghiệm, vector `.npy` (6 MB) và `prodcopy.env` vào repo; chúng ở `~/code/recsys-theme-2026-10-08/` trên máy chạy.
- Không sửa code, PRD, spec hay production.

## Kiểm tra

- Số trong report đối chiếu với `formula_prod.json`, `formula_local.json`, `formula_prod_F78.log`, `formula_prod_F910.log`,
  `slots_prod_F0b.json`, `slots_prod_F4.json`. Không có thay đổi contract/schema nên không chạy validate_contract / verify.sql.

## Còn lại / rủi ro

- Chờ người dùng chốt đề xuất (F7 hay F9; có làm ô khám phá B không; có thêm sở thích chủ đề vào `seed_histories.py` không).
- Script tái sinh nằm ngoài repo; nếu cần tái lập bởi người khác thì phải đưa script vào `src/evaluation/` (chưa làm).
