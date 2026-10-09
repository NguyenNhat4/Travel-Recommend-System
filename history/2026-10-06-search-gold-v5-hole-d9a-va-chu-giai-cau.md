# Search bench: gán nhãn hole D9a–D9e (1.799 cặp nhãn máy chưa duyệt + 125 auto_ooc) → gold chưa tag; chú giải theo câu cho 154 câu; split dev/test gold_v4

- Ngày: 2026-10-06
- Tác giả: người dùng (yêu cầu "tự label thêm nếu cần và chạy đủ bench mới với gold_v4") / Claude (Opus 5.5, orchestrator + agent gán nhãn)
- Nhánh: fix/search-gold-v4
- Trạng thái: hoàn thành (nhãn máy chờ người duyệt trước khi tag `gold_v5`)
- Phạm vi: evaluation

## Mục tiêu

Run vòng 1 trên gold_v4 có Judged@10 chỉ 0,77–0,86: số nDCG của các arm query plan không so được vì kết quả mới vào top-10 chưa có nhãn.
Việc 1 của yêu cầu 06/10: gán hole cho mọi arm (ưu tiên `amenity_negation`); việc 2: chú giải forbidden / chiều bay / expected parse để
Forbidden@10, direction accuracy, parse accuracy chạy được trên câu v4.

## File thay đổi

- `src/evaluation/search_bench/gold/holes/gold_v4__D9a/` — thêm: hole từ run `2026-10-06-gold-v4-r1` (21 arm): 829 cặp / 121 câu + 56
  auto_ooc; `labels/labels_A.csv`, `labels/provenance_A.csv` (`sb gold machine-import`, model `claude-opus-5-5`).
- `src/evaluation/search_bench/gold/holes/untagged__D9b/` — thêm: hole từ run `2026-10-06-gold-v4-r2` (42 arm): 871 cặp / 140 câu + 60 auto_ooc.
- `src/evaluation/search_bench/gold/holes/untagged__D9c/` — thêm: 69 cặp / 36 câu + 9 auto_ooc (13 arm chạy lại sau sửa kênh fuzzy).
- `src/evaluation/search_bench/gold/holes/untagged__D9d/` — thêm: 14 cặp / 5 câu (chạy lại sau sửa parser; Claude gán trực tiếp).
- `src/evaluation/search_bench/gold/holes/untagged__D9e/` — thêm: 16 cặp / 14 câu (3 arm F1–F6).
- `src/evaluation/search_bench/gold/gold.jsonl` — sửa (chỉ thêm): +1.799 nhãn máy CHƯA duyệt + 125 auto_ooc = +1.924 nhãn so `gold_v4`
  (5.666 → 7.590), provenance `holes:<đợt>:machine_unreviewed@gold_v5`; 0 câu mới, 0 retired. SHA-256 `7107a91a…e9e5`.
- `src/evaluation/search_bench/gold/changelog.yaml` — sửa: năm dòng import (do `sb gold holes import` ghi).
- `src/evaluation/search_bench/gold/splits/devtest@gold_v4.json` — thêm: `sb gold devtest` seed 42, dev 77 / test 77 phân tầng slice.
- `src/evaluation/search_bench/config/query_annotations.yaml` — sửa (file do agent bench tạo cùng ngày với 8 mục chuyển từ
  `forbidden_v3.yaml`): đủ 154 câu active — `expected_parse` (11 trường) mọi câu, 28 `forbidden_filter` (13 tiện ích bị phủ định, 9 tuyến
  sai chiều/chặng, 6 loại sản phẩm sai lõi v4), `origin` / `destination_city` cho 9 câu vé máy bay, không `family`. 8 mục cũ giữ nguyên
  nghĩa (so AST 8/8).

## Quyết định

- **Nhãn máy theo gói slice** (mỗi gói một agent đọc `docs/spec/bench/gold-guide.md` + nhãn sẵn có của chính câu làm mốc — giữ độ chặt
  của người gán từng câu). Gói vòng 2 có đủ danh sách tiện ích catalog (tới 80 chuỗi) + dòng "Tiện ích:" của text index, không chỉ 12
  tiện ích đầu như vòng 1. Phân bố 0 / 1 / 2: D9a 323 / 247 / 259, D9b 279 / 307 / 285, D9c 19 / 22 / 28, D9d 0 / 10 / 4, D9e 0 / 10 / 6.
- **Đối chiếu luật** cho câu phủ định v4 + vé máy bay (`amenity_keys` backend + tên tuyến "Vé máy bay A - B"): luật khớp gold người 313/322;
  khớp nhãn máy D9a 99/101, D9b 74/75 — lệch đều vì "dòng Tiện ích" ghi tiện ích bị loại trừ → nhãn máy 0 đúng theo #3/#14 (Pullman Phú
  Quốc c0685 sửa tay 2 → 0). "Ghi" = danh sách tiện ích / dòng tiện ích / tên; chỉ nhắc trong mô tả dài thì không tính (#11).
- **Sao trong `multi_constraint` là điều kiện**: prompt vòng 1 ghi nhầm "sao do máy kiểm"; nhãn người cùng câu cho 1 khi dưới ngưỡng
  (54/57) hoặc không khai (20/20) → hạ 14 cặp 2 → 1; prompt vòng 2 đã sửa.
- **Không sửa nhãn cũ** dù agent chỉ ra nghi vấn (gold chỉ thêm): c0394 Moscow Hotel Ha Long nhãn 2 cho câu Hà Nội; c0426 Bao Phuc (Cát Bà)
  nhãn 0 trái #1; c0439 / c0247 / c0253 có nhãn trước #3 / #6 mâu thuẫn nhãn mới; 34 cặp nhãn ≥ 1 rơi vào 8 forbidden_filter cũ.
- **Không tag `gold_v5`**; mọi số chạy `--allow-untagged`. Thư mục hole D9b–D9e mang tiền tố `untagged__` vì gold lúc sinh chưa có tag.

## Kiểm tra

- Mỗi đợt: kiểm gộp (mỗi cặp đúng một nhãn, nhãn ∈ {0,1,2}, `children_ok` ⊆ phòng con), `sb gold machine-import --dry-run` rồi chạy thật
  (từ chối 0 ở cả năm đợt), `sb gold holes import --accept-unreviewed`, `sb gold check` xanh (154 câu, min_per_slice 3),
  `sb gold verify-append gold_v4` xanh (+0 câu, +1.924 nhãn, +0 retired).
- `pytest test_annotations.py test_blocks_guards.py test_metrics_phase_a.py` (.venv-sbench): 76 passed.
- Sau đợt cuối, `sb gold holes` trên 45 arm của run r2: 0 cặp còn trống; `rescore`: Judged@10 = 1,000 mọi arm.
- Report: `src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md`.

## Còn lại / rủi ro

- Người duyệt nhãn máy (app gán nhãn, `source=machine`) rồi `git tag gold_v5`; tới lúc đó mọi số là "trên nhãn máy chưa duyệt".
- Chú giải là nhãn máy: c0340 (tên POI trần), c0355 (Cát Bà là điểm đến?), c0361 / c0366 (quận của Cần Thơ), c0372 (combo hay attraction)
  là ca biên; chưa gắn `family` nào.
