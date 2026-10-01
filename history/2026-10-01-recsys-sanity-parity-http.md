# RecSys harness — Track B Phase 2 + 3: `sanity` dữ liệu seed và parity offline = HTTP trên 60 khách

- Ngày: 2026-10-01
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation (recsys_bench), docs spec/plan

## Mục tiêu

Plan Day 3 Track B Phase 2 (B1 `sanity.py`) và Phase 3 (B9 offline = HTTP): trước khi tin số đo phải chắc dữ liệu seed đúng
luật (lifecycle, chuyến, cạnh lộn xộn, phổ biến) và engine offline của harness trả **đúng** list production. Lịch 10 ngày Day 2 B
("sanity + bảng baseline") và M5. Phục vụ FR-REC-01/02, test-plan §2.5.

## File thay đổi

- `src/evaluation/recsys_bench/sanity.py` — thêm: `Check`, `lifecycle_seed_rule` (ngày lịch VN như seed), `lifecycle_mix`,
  `lifecycle_recomputed`, `trips_multi_vertical`, `one_destination_per_trip`, `messy_edges` (cứng); `popularity` (top-10 %, Gini,
  Zipf), `golf_share`, `split_users` (chỉ báo); `run_all`, `summary`, `markdown`; hằng tỷ lệ đọc từ `data_collection/seed/config.py`.
- `src/evaluation/recsys_bench/parity.py` — thêm: `make_users` (4 persona + 56 phân tầng theo lifecycle seed rule, seed 42),
  `compare_user` (as_of = `generatedAt`, event mới nhất trước, `OfflineEngine(mode="prod")`), `parity_http` (X-Service-Token từ
  biến môi trường, không in), `verdict`, `write_parity`, `markdown`.
- `src/evaluation/recsys_bench/data_source.py` — thêm `load_profiles` (qua `PostgresCdpReader.all_profiles`, cache JSONL).
- `src/evaluation/recsys_bench/__main__.py` — thêm lệnh `sanity [--json] [--refresh]` (mã 1 khi kiểm tra cứng hỏng) và `parity
  [--make-users --seed] | --base-url … --k 5 --token-env AUTH_SERVICE_TOKEN` (mã 1 khi không 60/60).
- `src/evaluation/recsys_bench/frozen/users60.json` — thêm: 60 khách (persona VP0000001–4 + 14 new / 25 active / 11 dormant / 6 churned).
- `src/evaluation/recsys_bench/tests/test_sanity.py` (5 test), `tests/test_parity.py` (4 test) — thêm.
- `docs/spec/bench/recsys-offline-eval.md` — sửa: §1 lệnh; §2.1 bảng sanity; §4.12 parity offline = HTTP; §7.
- `docs/plan/2026-09-28-lich-10-ngay-3-engine.md` — sửa: tick dòng `sanity.py` Day 2 B với số; log Day 4.
- Backend `all_profiles()` ở history riêng `2026-10-01-cdp-reader-all-profiles.md`.

## Kết quả

- **Sanity (DB local seed 21/09, as_of 22/09, 7.131 event, 2.000 profile): 5/5 kiểm tra cứng PASS** — lifecycle 25,1 / 45,0 / 20,0 /
  10,0 %; tính lại từ event lệch 0/2.000 (stage và days_since_last_booking); chuyến ≥ 2 taxonomy 63,6 % (1.159/1.822); 0 chuyến
  nhiều điểm đến; orphan 2,0 %, thiếu gid 3,0 %. Chỉ báo: top-10 % sản phẩm = 41,1 % purchase, Gini sản phẩm 0,423 / search unit
  0,525, Zipf slope −0,63 (seed ZIPF_S 0,8 — phẳng hơn vì cắt theo điểm đến); hotel 55,6 % · flight 21,7 % · attraction 17,8 %.
- **Parity offline = HTTP: 60/60** khách trùng hoàn toàn (strategy, destination, excludedVerticals, eventsUsed, top-5 đúng thứ tự)
  với backend local (cùng checkout, Postgres 5432, Weaviate 8080, `INTERNAL_API_ENABLED=true`, token tạm trong shell). HTTP local
  `latencyMs` p50 250 / p95 321 ms, client 263 / 338 ms (máy đang chạy song song; 24/09 đo 127 / 143 ms).

## Quyết định

- Lifecycle tính lại theo **ngày lịch VN** và as_of = ngày sau event cuối (đúng `seed_histories.lifecycle`): lệch 0 nên không
  cần dung sai; `lifecycle_mix` dùng dung sai STAGE_TOLERANCE của seed.
- Parity dùng `/internal/recommendations` + `X-Service-Token` (đường demo/eval theo auth §14.4), không qua JWT; token sinh ngẫu
  nhiên cho phiên đo, xoá sau khi xong, không ghi file trong repo.
- `make_users` sinh bộ mới (danh sách 24/09 không được lưu); 4 persona luôn có mặt (VP0000004 không có event → `new`).

## Kiểm tra

- `pytest -q src/evaluation/recsys_bench/tests` → **59 passed** (recsys_bench; trước 50); backend đầy đủ trên nhánh bench **657 passed, 19 skipped**.
- `sanity --refresh` → PASS (bảng ở spec §2.1); `parity --make-users` → `frozen/users60.json`; `parity --base-url
  http://127.0.0.1:8000 --k 5 --run-id 2026-10-01-parity-http` → PASS 60/60.
- Review đối kháng (workflow 3 lens) → đang chạy lúc commit (3 lens); sửa nếu có ghi ở history của nhánh `bench/phan-con-lai`.

## Còn lại / rủi ro

- Parity đo offline = HTTP **local**; trên Cloud chỉ đo được guest path (§4.5) cho tới khi ops mở IAP (`http-latency --users`).
- Track B theo plan Day 3 đã đủ (Phase 0–3); việc tiếp theo thuộc M6/M7 (đề xuất đổi engine qua `docs/prd/update/`, tuning trên temporal).
