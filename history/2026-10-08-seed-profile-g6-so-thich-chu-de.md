# Seed profile `g6-pref-v1`: sở thích chủ đề ẩn cho khách giả lập (gate G6, lane B1)

- Ngày: 2026-10-08
- Tác giả: tqanh123 / Claude Code
- Nhánh: `feat/recSys_update` (worktree `worktree-wf_30aec938-4cb-1`, gốc `1b5af92`)
- Trạng thái: hoàn thành (phần B1 của plan; B2 — tạo DB nghiên cứu, đo lại — chưa làm)
- Phạm vi: data, evaluation, docs
- Phục vụ: FR-REC-01/02/04, AC-REC-01/02; `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md` lane B1;
  `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7.1

## Mục tiêu

§7.1 của bảng quyết định chỉ ra: `seed_histories.plan_trip` → `World.destination(rng)` bốc điểm đến mỗi chuyến từ phân phối toàn cục
theo khối lượng bookable, không có tham số khách nào, nên split temporal / nexttrip không thể thưởng cho việc bám sở thích (bộ dự đoán
tối ưu = độ phổ biến toàn cục). Người dùng chốt 08/10: làm G6 trước — đổi bộ sinh event cho có sở thích chủ đề, đo lại, rồi mới chốt G2.
Entry này thêm profile **opt-in** `g6-pref-v1`: mỗi khách thường có một chủ đề ẩn (biển / núi / thành phố) và bốc điểm đến cùng chủ đề
với xác suất `THEME_PREF_RATE`. Demo (profile None), eval-v2 và append-v1 phải **không đổi một byte**.

## File thay đổi

- `src/data_collection/seed/config.py` — sửa: khối "§4.3 sở thích chủ đề" (`THEME_PREF_RATE` 0, `THEME_NO_PREF_SHARE` 0,30, `THEME_MIX`
  None, `DEST_THEMES` beach 15 / mountain 16 / city 10 chép từ `theme_exp.THEME`); `PROFILES["g6-pref-v1"]` = append-v1 + rate 0,8.
- `src/data_collection/seed/seed_histories.py` — sửa: `World` dựng bể điểm đến theo chủ đề (cùng trọng số bookable tuyến tính của lần
  bốc toàn cục) + `theme_mass` / `theme_mix()`; `World.destination(rng, theme=None)` (theme None / rate ≤ 0 / không bể → đường cũ, cùng
  số lần gọi rng); `plan_trip` / `plan_generic` nhận `theme` và chuyển vào mọi lần bốc điểm đến (chuyến chỉ xem của khách new, chuyến mua,
  lần bỏ giỏ); `_generate` gán chủ đề bằng stream RNG riêng `{seed}|theme|{user}` chỉ khi rate > 0, trả `themes` + `theme_params`;
  `profile_overrides(name, extra)`; `generate(..., theme_pref=)`; `theme_stats()`; report thêm một dòng (chỉ khi có nhãn); CLI
  `--theme-pref`, ghi `user_themes.jsonl` khi có nhãn.
- `src/data_collection/seed/append_histories.py` — sửa: `build(..., profile="append-v1", theme_pref=None)`; payload giữ `format=1`, thêm
  khóa `profile` chỉ khi khác append-v1; nhãn trả ở khóa `themes` ngoài payload (id có tiền tố `VPX:<batch>:`); `validate()` chấp nhận
  khóa `profile`; `prepare --profile --theme-pref`, ghi `themes.json` cạnh `batch.json` khi có nhãn.
- `src/evaluation/recsys_bench/theme_study/theme_exp.py` — sửa: `THEME` = `{**seed_config.DEST_THEMES, "mixed": [...]}` (một nguồn);
  `THEME_OF` giữ 51 điểm đến, thứ tự khóa beach / mountain / city / mixed không đổi.
- `src/data_collection/tests/test_seed_theme_profile.py` — thêm: 9 test (sha vàng demo / eval-v2 / append-v1 tính trước khi vá; g6 với
  rate 0 trùng append-v1; tất định; persona giống demo; khách có chủ đề ≥ 0,7 chuyến cùng chủ đề, khách None theo phân phối toàn cục
  ±0,1 và theo demo ±0,1; `themes` đúng tập khách thường; bể chủ đề đúng trọng số; catalog không có điểm đến có nhãn → dừng). Fixture
  mở rộng tại chỗ (`make_theme_catalog`: thêm Đà Nẵng, Sa Pa, Huế, Quảng Ngãi không nhãn), không đổi `make_catalog`.
- `src/data_collection/tests/test_append_histories.py` — sửa: thêm test `--profile g6-pref-v1` sinh `themes`, khóa `profile`, validate;
  append-v1 không đổi (không khóa profile, không themes, cùng sha hai lần build; g6 tắt sở thích trùng lịch sử append-v1).
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: §4 luật điểm đến thêm vế trỏ §4.3; §4.3 mới (mục đích, bảng tham số, luật nhãn ẩn, đường nạp,
  dòng verify.sql FAIL dự kiến, tên split `-g6pref-v1-`).
- `AGENTS.md` — sửa: §6.5 bước 5 thêm một câu về profile g6-pref-v1 (chỉ DB nghiên cứu, demo không đổi).
- `history/2026-10-08-seed-profile-g6-so-thich-chu-de.md` — thêm: entry này.

## Quyết định

- Tham số theo plan lane B1: p = 0,8; 30 % khách không sở thích; mix = khối lượng bookable; 7 điểm đến chưa nhãn của prodcopy không
  có chủ đề (chỉ qua lần bốc toàn cục). Người dùng chốt lại tham số khi review lane B (plan §4).
- Nhãn ẩn: stream RNG riêng nên không stream nào sẵn có bị dịch; chỉ sidecar (`user_themes.jsonl` / `themes.json`), không cột DB, không
  thuật toán nào đọc — như `theme_exp` (nhãn chỉ để chấm điểm).
- Rate 0 → không tạo stream, `themes = {}`, không ghi sidecar, report không có dòng mới: demo / eval-v2 / append-v1 trùng byte kể cả
  `seed_report.md`.
- Hướng import: `theme_exp` (chạy từ gốc repo, `src.…`) import `src.data_collection.seed.config` như `sanity.py` đã làm; package seed không
  import `src.evaluation`.
- g6-pref-v1 kế thừa append-v1 (5.004 khách, 40 event, bỏ giỏ, không cạnh giả) nên "g6 với rate 0" trùng **append-v1**, không trùng demo —
  test (a) của thiết kế được hiện thực là: demo == sha vàng == demo với `theme_pref=0`; g6 `theme_pref=0` == append-v1.
- Catalog không có điểm đến nào thuộc `DEST_THEMES` mà rate > 0 → `SystemExit` thay vì lặng lẽ sinh bộ "không sở thích".
- Đường nạp: plan ghi "TRUNCATE chỉ `cdp.events, cdp.profiles`" nhưng `app.users` / `app.bookings` FK tới `cdp.profiles` → spec §4.3 ghi
  `TRUNCATE cdp.events` + `DELETE` profile không còn ai trỏ tới, không `CASCADE`.
- Chỉ `append_histories prepare` stdout thêm hai khóa `profile`, `themed`; artifact không đổi.

## Kiểm tra

- `cd src && ../.venv/Scripts/python.exe -m pytest data_collection/tests/test_seed_histories.py data_collection/tests/test_seed_eval_profile.py
  data_collection/tests/test_append_histories.py data_collection/tests/test_seed_theme_profile.py -q -p no:cacheprovider`: **40 passed, 3 skipped** (3 skip = test DB
  `APPEND_TEST_DATABASE_URL`, không chạy DB theo yêu cầu). Trước khi vá: 30 passed, 3 skipped.
- `pytest test_seed_snapshot.py test_seed_load_products.py test_seed_parse_combos.py test_seed_insider.py`: 38 passed.
- `python -c "from src.evaluation.recsys_bench.theme_study import theme_exp; print(len(theme_exp.THEME_OF))"` → 51 (trước và sau);
  `eval_formula` import được.
- **Byte-identity trên catalog thật** (snapshot `src/data_collection/snapshots/2026-09-30/products.jsonl.gz` bung bằng gzip, 11.718 dòng;
  `seed_histories --as-of 2026-09-30 --seed 42`, chạy ở commit `1b5af92` TRƯỚC khi vá và sau khi vá):
  - demo `cdp_events.jsonl` `b41ad4b7835bfcb96a6daac3638111ecee61c049de2356a0f0bf90be4d393f7a` — trước = sau;
    `cdp_profiles.jsonl` `4c803eefe2b2dad499e378f45e2e7b330bf1a7164bbee77a5283221d510dead7` — trước = sau;
    `app_users` `9ef675cf…`, `app_bookings` `0ee50ebc…`, `app_booking_items` `da775ff2…`, `seed_report.md` `73227e84…` — đều trước = sau;
    không sinh `user_themes.jsonl`.
  - eval-v2 `cdp_events.jsonl` `66925a83abfabbc74c621893b006426e3b338c5df5ace6cae03606383b5c32e7`, `cdp_profiles.jsonl`
    `ea623d23361cd2551d437e6961d73d5f5fdf54e9e697efc190169b2f36cc9c81` — trước = sau.
  - append-v1 `build(batch="g6-evidence", as_of=2026-09-30, seed=42)` sha artifact
    `0437fa7fcd10625596817d959e06215b1d2c05ce43b434128a6c7c3fc72b71ca` (5.000 profile, 32.969 event; `build()` gọi trực tiếp trên
  dòng `products.jsonl` thô, `unitPrice` giữ kiểu gốc — qua `prepare` (ép `unitPrice` sang float) thì sha là `05a3e1eb…`, cũng trước = sau) — trước = sau.
  - Sha vàng fixture (`make_catalog`, seed 7, N 600, tính trước khi vá, ghi trong test): demo `8055fc45…`, eval-v2 `924e6475…`,
    append-v1 `857fab8b…` — test xác nhận sau khi vá.
- Chạy thử g6 trên catalog thật (`--profile g6-pref-v1`, as_of 30/09, seed 42): 5.004 profile, 32.773 event, stage 45/25/20/10 đúng;
  beach 1.735 · city 1.215 · mountain 546 · không sở thích 1.504; chuyến của khách có chủ đề tới điểm đến cùng chủ đề **87,5 % / 4.237**
  (mục tiêu ≈ p + (1 − p)·mass = 87,4 %); `cdp_events.jsonl` sha `1ac3dcc8…`; có `user_themes.jsonl`.
- Không chạy gì vào database (theo yêu cầu). `validate_contract.py` không áp (không đổi contract / mock).

## Còn lại / rủi ro

- B2 của lane B: tạo `vota_g6pref_v1` từ `vota_prodcopy`, nạp bằng `append_histories prepare --profile g6-pref-v1` + `apply`, đóng băng split
  `-g6pref-v1-`, đo lại C0–C3 với CI ghép cặp, rồi người dùng chốt lại G2 (luật D1–D5 trong plan).
- Tham số p / 30 % / mix chưa được người dùng chốt (plan §4 "G6 tham số"); đổi thì chỉ sửa `config.py` §4.3.
- Sha vàng trong `test_seed_theme_profile.py` gắn với fixture `make_catalog()`; đổi fixture thì phải tính lại ba sha và ghi history.
- Nhãn ẩn có thể suy ngược một phần từ lịch sử (87 % chuyến cùng chủ đề); đây là chủ ý — engine không được đọc sidecar.
- Worktree được tạo ở `dfa24af` (release-mvp-v2) thay vì `1b5af92`; đã `git reset --hard 1b5af92` trước khi làm để đúng gốc feat/recSys_update.
