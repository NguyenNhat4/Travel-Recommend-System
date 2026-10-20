# Đưa script đo RecSys bám sở thích vào src/evaluation

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Để người khác tái lập được số trong `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` (FR-REC-01, FR-REC-02,
FR-REC-04), đưa script thử nghiệm vào repo. Tiếp theo `history/2026-10-08-bao-cao-recsys-so-thich-chu-de.md`.

## File thay đổi

- `src/evaluation/recsys_bench/theme_study/__init__.py` — thêm
- `src/evaluation/recsys_bench/theme_study/theme_exp.py` — thêm: khách giả lập theo chủ đề, nhãn chủ đề, ô khám phá
- `src/evaluation/recsys_bench/theme_study/eval_formula.py` — thêm: 11 biến thể `score_candidates` (monkeypatch trong tiến trình đo)
- `src/evaluation/recsys_bench/theme_study/eval_slots.py` — thêm: hậu xử lý list 4 món
- `src/evaluation/recsys_bench/theme_study/dump_prod.py` — thêm: tải chỉ-đọc qua API GET của monitor
- `src/evaluation/recsys_bench/theme_study/embed_prodcopy.py` — thêm: embed e5-small cho DB bản sao
- `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — sửa: mục Tái sinh trỏ vào module mới

## Quyết định

- So với bản chạy đêm: import theo package; bỏ đường dẫn máy cá nhân (`--vec` bắt buộc); URL monitor thành `--base-url`;
  sửa lỗi `KeyError: 'F0_prod'` ở bước dọn cuối của `eval_formula`. Logic đo không đổi.
- Không đưa vector `.npy`, file env (DSN) vào repo. Không sửa engine.

## Kiểm tra

- `python -m src.evaluation.recsys_bench.theme_study.eval_formula --splits llbo --n-syn 80 --max-users 800 --variants F0_prod,F7_betweenMinmaxPop30`
  trên `vota_prodcopy`: LLBO 0.8363 / 0.525 / 0.5737, theme between F0 0.438, F7 0.776 — khớp report. Chạy xong không lỗi (406 s).
- `eval_slots --n-syn 5 --max-users 50`: chạy hết, không lỗi. `dump_prod --help`: ok.
- Chưa có unit test cho module này (script thí nghiệm).

## Còn lại / rủi ro

- Cần DB bản sao production local + vector `.npy` tự tạo bằng `dump_prod` / `embed_prodcopy`.
