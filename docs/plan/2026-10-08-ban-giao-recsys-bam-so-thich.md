# Bàn giao: RecSys bám sở thích khách (profile P2, công thức điểm khi không có chuyến mở, ô khám phá)

- Ngày: 2026-10-08
- Người bàn giao: Pham Nguyen Dang Khoi (soạn cùng Claude Code)
- Người nhận: tqanh123 (Trịnh Quang Anh)
- Nhánh: `bench_search_recomSys`
- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04, AC-REC-02 (`docs/prd/requirements.md` §1.4, §3)
- Trạng thái: nghiên cứu xong bước 1–2; còn đo có thống kê, chọn cấu hình, chốt PRD, cài vào engine.

## 0. Đọc trước (theo thứ tự)

1. `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` — **báo cáo cuối**: phát hiện, bảng số đầy đủ, đính chính, khuyến nghị.
2. `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md` — số thô, lệnh tái sinh.
3. `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` — đề xuất PRD chờ chốt (**nội dung cũ**, WP5 viết lại).
4. `AGENTS.md` §1.2 (Search / Recommendation, Evaluation), §5 (history), §8 (lệch PRD phải chốt trước), và
   `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.3–4.7 trước khi chạm engine.

## 1. Trạng thái lúc bàn giao (08/10, sau khi push)

| Hạng mục | Trạng thái |
|---|---|
| Chẩn đoán: cos e5 dồn → pop lấn át; lượt xem lẻ lấn át `u_long` | Xong, có số |
| Công thức F0–F12 (profile production) | Xong |
| Profile P0–P4 × F0 / F7, kịch bản `noisy` | Xong |
| Bước 2 trên P2: F7, F12b, F13a, F13b, F14 | Xong (16:15) |
| Ô khám phá, không ẩn món đã xem | Xong (profile production) |
| Test giới hạn lặp / mất purchase | Có, nhưng ca "production" test nhầm engine (WP1) |
| CI ghép cặp, nhiều seed, `noisy` cùng khách | **Chưa** |
| Chọn cấu hình | **Chưa** — ứng viên P2 + F14 (dự phòng F7) |
| Đề xuất PRD đúng nội dung mới, người dùng chốt | **Chưa** |
| Sửa engine backend, spec, unit test, deploy | **Chưa** |
| Commit / push | **Xong** 08/10: 2 commit trên `origin/bench_search_recomSys`, rebase trên 6 commit search 06/10 |

## 2. File bàn giao

### 2.1 Đã commit trong bàn giao (thuộc nghiên cứu này)

```
src/evaluation/recsys_bench/theme_study/            # script đo (10 file .py) + results/2026-10-08/ (JSON + SHA256SUMS)
src/evaluation/recsys_bench/tests/test_profile_variants.py
src/evaluation/reports/eval-2026-10-08-recsys-so-thich-chu-de.md
docs/spec/bench/recsys-bam-so-thich-tong-hop.md
docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md
docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md
history/2026-10-08-bao-cao-recsys-so-thich-chu-de.md
history/2026-10-08-dua-script-do-recsys-so-thich.md
history/2026-10-08-do-f11-gian-pop.md
history/2026-10-08-do-f12-chi-ha-trong-so-pop.md
history/2026-10-08-do-phan-bo-thanh-phan-diem-recsys.md
history/2026-10-08-do-bien-the-dung-profile-recsys.md
history/2026-10-08-tam-dung-buoc-2-recsys.md
history/2026-10-08-tong-hop-recsys-bam-so-thich.md
history/2026-10-08-kiem-thu-purchase-va-doi-chieu-buoc-2.md
history/2026-10-08-bao-cao-cuoi-va-ban-giao-recsys-so-thich.md
```

Commit kèm (nghiên cứu phụ thuộc, việc 07/10 đã chốt): `src/backend/app/domain/recommendation/profile.py`
(W 0,7/0,15/0,15), `git mv` đề xuất `2026-10-06-recsys-trong-so-ngan-han-pho-bien.md` sang `update-archive/`,
`history/2026-10-07-recsys-trong-so-0-7-0-15.md`, `src/evaluation/reports/eval-2026-10-07-recsys-grid-llbo-coldstart.md`.

### 2.2 Không thuộc bàn giao này — vẫn local trên máy người bàn giao, chủ việc tự commit

Crawler Trip (`src/data_collection/collectors/trip_*.py`, `fresh_catalog.py`, test tương ứng, history 06/10 về Trip / Cohere),
nạp catalog theo mã băm (`postgres_store.py`, `test_postgres_catalog_reader.py`, history 07/10), search bench
(`sbench.yaml`, report search 05/10 và 07/10), latency (`latency-cloud-summary.md`, report latency), `docs/prd/deployment-plan.md`,
`docs/plan/2026-09-28-lich-10-ngay-3-engine.md`, `src/backend/README.md`, `.claude/`.
7 file trong số này trùng với 6 commit search 06/10; khi đồng bộ đã ghép lại trên máy người bàn giao (1 xung đột `src/backend/README.md`, đã gộp cả hai phía). Không ảnh hưởng người nhận: `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`,
`docs/prd/deployment-plan.md`, `docs/spec/hop-dong-tich-hop-search-recommendation.md`, `src/backend/README.md`,
`src/backend/app/infrastructure/vectors/postgres_store.py`, `src/data_collection/fresh_catalog.py`,
`src/evaluation/search_bench/config/sbench.yaml`.

### 2.3 Ngoài git (chuyển qua kênh riêng, không đưa lên git)

| File | Ở đâu | Cách chuyển |
|---|---|---|
| DB `vota_prodcopy` (bản sao production chỉ-đọc 08/10 01:49) | container `wt-seed-postgres-1` :55433 | `pg_dump -Fc` gửi riêng. Có event thật của tài khoản người bàn giao — không chia sẻ rộng. Bước nạp jsonl của `dump_prod.py` vào DB **chưa được ghi lại**, nên dùng `pg_dump` thay vì dựng lại |
| `vec_prodcopy_e5s.npy` + `.ids.json` + `.meta.json` (6 MB) | `~/code/recsys-theme-2026-10-08/` | gửi riêng, hoặc tự sinh bằng `embed_prodcopy.py` sau WP0.1 |
| `prodcopy.env` | như trên | **không gửi** (DSN, API key). Người nhận tự tạo env trỏ DB local của mình |
| Log gốc `*.log` | như trên | không cần: số đã có trong JSON (`*.log` bị `.gitignore`) |

## 3. Quyết định cần người dùng chốt (gate)

| Gate | Câu hỏi | Trước WP |
|---|---|---|
| G1 | Tiêu chí nghiệm thu (báo cáo cuối §6): ngưỡng LLBO, theme, temporal, latency | WP3 |
| G2 | Mức giảm nexttrip có chấp nhận được không (đo được −0,035 đến −0,046, là cận trên do dữ liệu giả lập) | WP3 |
| G3 | Chọn công thức: F14 / F7 / khác | WP4 |
| G4 | Có làm ô khám phá B không (đổi hành vi FR-REC-02) | WP4 |
| G5 | Chốt đề xuất PRD viết lại | cài engine (WP5.3) |
| G6 | Đổi bộ sinh event để có sở thích chủ đề (`seed_histories.py`, `MOCK_DATA_SPEC.md`) | WP6 |

Không tự chọn thay người dùng; chưa chốt thì không sửa engine (AGENTS.md §8).

## 4. Đầu việc

Ước lượng thời gian chạy lấy từ log 08/10: một cấu hình đủ ba split + khách giả lập mất 20–45 phút; chỉ khách giả lập ~1 phút / cấu hình.
Chạy song song tối đa 2 tiến trình (4 tiến trình làm mỗi job chậm gần gấp đôi).

### WP0 — Đồng bộ nhánh, dựng lại môi trường, đo lại mốc

Mục tiêu: mọi số sau này đo trên engine giống production.

1. ~~Kéo 6 commit search của `origin/bench_search_recomSys`~~ — đã xong khi push 08/10. Người nhận chỉ cần `git pull`.
2. Merge `origin/main` (nhánh chậm 71 commit). Quan trọng nhất: `9b703ba` (cap lặp, "hôm nay" theo giờ VN, parser `usingDate` chung).
3. Đảm bảo trọng số 0,7/0,15/0,15 có trên `main` (`origin/main` vẫn 0,6/0,25/0,15; production `release-mvp-v2` đã 0,7). Việc này đã chốt
   07/10, chỉ thiếu PR.
4. Viết lại `profile_variants.py` theo `build_profile` mới (dict `every`: tuổi / `ends_on` / món đã mua tính trên mọi event; cap chỉ
   giới hạn vector). Kiểm `parity_mismatch_llbo200 = 0`.
5. Nạp `vota_prodcopy` (`pg_restore`) và vector; tạo env local.
6. Đo lại P0+F0, P2+F7, P2+F14 trên engine mới; so với bảng cũ; ghi report `src/evaluation/reports/eval-YYYY-MM-DD-recsys-so-thich-moc-moi.md`.

Checklist:
- [x] Đồng bộ 6 commit search (xong khi push 08/10)
- [ ] merge `origin/main`, `pytest src/evaluation/recsys_bench/tests` pass
- [ ] W 0,7/0,15/0,15 có trên `main` (đã có trên nhánh này, commit `235e92e`; cần PR vào `main`)
- [ ] `profile_variants.py` theo engine mới, parity 0/200
- [ ] `embed_prodcopy.py` (import được từ 08/10) sinh lại vector, hoặc dùng `.npy` được gửi; `meta.json` khớp revision `614241f…`
- [ ] Mốc mới P0+F0 / P2+F7 / P2+F14 đo xong, có report
- [ ] history entry

DoD: số mốc mới có report; chênh với bảng cũ được giải thích.

### WP1 — Sửa test mất purchase

Ca `production-known-bug` trong `test_profile_variants.py` gộp hai kiểm. Sau WP0, `build_profile` của main đã đúng phần nghiệp vụ
nhưng vẫn không đưa purchase vào vector chuyến.

1. Tách thành `test_purchase_state_survives_repeat_cap` (bought_units, purchased_taxonomies, ends_on, ended, active_trip, strategy) —
   `build_profile` production phải **pass**, bỏ xfail.
2. Thêm `test_strong_events_weight_trip_vector` (purchase / cart nằm trong `trip.events`): production xfail strict cho tới khi WP5
   sửa; P1 / P4 pass.
3. Sửa docstring: "production" = `build_profile` của `src/backend`, ghi commit tham chiếu.

Checklist:
- [ ] Hai ca tách riêng, tên đúng nghĩa
- [ ] `pytest src/evaluation/recsys_bench/tests/test_profile_variants.py` pass (xfail chỉ ở ca vector)
- [ ] history entry

### WP2 — Đo lại có thống kê

1. `eval_profile.py`: thêm `--per-user-out <file.jsonl>` ghi từng khách (uid, split / kịch bản, chủ đề, hit@4/@20, nDCG@10, theme, list 4).
2. Script `paired_ci.py` (trong `theme_study/`): bootstrap ghép cặp 2.000 lần, CI 95 % cho chênh giữa hai cấu hình trên cùng khách.
   Test unit với dữ liệu giả.
3. Sửa kịch bản `noisy` thành **cùng khách**: sinh lịch sử `between`, sao chép rồi thêm 5–8 lượt xem nhiễu → đo trực tiếp "nhiễu làm
   theme giảm bao nhiêu". Giữ kịch bản cũ dưới tên khác để không đổi số cũ.
4. Khách giả lập: 3 seed (ví dụ 42, 7, 2026), báo trung bình ± độ lệch giữa seed.
5. Split thật: cân nhắc dùng đủ LLBO 4.072 / nexttrip 1.835 khách thay vì 800 (chạy lâu hơn khoảng 2–5 lần).
6. Cấu hình đo: P0+F0, P2+F0, P0+F7, P2+F7, P2+F14 (+ P2+F13a nếu còn muốn).

Checklist:
- [ ] `--per-user-out` + test
- [ ] `paired_ci.py` + test
- [ ] `noisy` cùng khách (kịch bản mới, kịch bản cũ giữ seed)
- [ ] 3 seed khách giả lập
- [ ] Quyết định 800 hay toàn bộ khách split thật; ghi lý do
- [ ] Report `src/evaluation/reports/eval-YYYY-MM-DD-recsys-so-thich-ci.md` có bảng CI
- [ ] history entry

DoD: mọi so sánh trong khuyến nghị có CI ghép cặp.

### WP3 — Chọn công thức (cần G1, G2)

1. Ứng viên: F14, F7. Với F14 thử thêm pop 0,25 / 0,35 và độ bền calibration (q tính từ 3 seed calibration khác nhau — q lệch nhiều
   thì F14 không ổn định).
2. (Tuỳ chọn) F13 centering toàn phần: center cả vector truy vấn Weaviate, profile, MMR. Chỉ làm nếu F14 / F7 không đạt tiêu chí.
3. Bảng quyết định: mỗi ứng viên × mỗi tiêu chí G1 → đạt / không đạt, kèm CI.
4. Trình người dùng chọn (G3).

Checklist:
- [ ] Tiêu chí G1 đã chốt, chép vào báo cáo
- [ ] F14 biến thể pop + độ bền calibration
- [ ] Bảng quyết định có CI
- [ ] Người dùng chọn công thức (G3), ghi ngày / người chốt

### WP4 — Đo đúng tổ hợp sẽ triển khai

Cấu hình: P2 + phần còn lại của P1 (purchase / cart luôn vào vector) + công thức đã chọn + ô khám phá B (nếu G4 đồng ý).

1. Cài ô B trong tiến trình đo (`eval_slots.py` đã có `fillExplore` cho profile production) để chạy chung với P2 + công thức.
2. Đo LLBO / temporal / nexttrip / coldstart (`recsys_bench`), khách giả lập `between` / `open` / `noisy`, AC-REC-01/02.
3. Latency: `recsys_bench` `http_latency` hoặc gọi API local, trước / sau, p50 / p95. Ô B không được thêm lượt gọi Weaviate; nếu cần
   `near_vector(u_long)` thì đo riêng.
4. Kiểm `because[]` vẫn hợp lệ theo contract (không thêm field).

Checklist:
- [ ] Ô B chạy cùng P2 + công thức
- [ ] Đủ split + coldstart + AC-REC-01/02
- [ ] Latency trước / sau
- [ ] Report + history

### WP5 — Đề xuất PRD → chốt → cài engine

1. Viết lại `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md`: P2, công thức đã chọn (G3), ô B (G4), tiêu chí G1, số WP4.
   Trạng thái `chờ chốt`. Dừng, chờ G5.
2. Sau khi chốt: cập nhật `docs/prd/requirements.md` §1.4 (FR-REC-02, FR-REC-04) **trước**, rồi mới sửa source.
3. Engine (`src/backend`), đúng phân lớp `docs/prd/architecture.md` §2:
   - `domain/recommendation/profile.py`: `build_profile` nhân độ tin cậy chuyến khi cộng `u_long`; cap lặp không bỏ purchase / add_to_cart
     khỏi vector; `score_candidates` có nhánh không chuyến mở theo công thức đã chọn (hằng mới, ví dụ `W_*_BETWEEN`; F14 thêm
     `Q_LOW` / `Q_HIGH` gắn với model + `TEXT_BUILDER_VERSION`); tăng `ENGINE_RULES_VERSION`.
   - `application/recommendation/use_cases.py`: ô B sau `mmr_select` nếu G4 đồng ý.
   - `explain()`: cân nhắc đồng bộ `because[]` với điểm thật (§3.D báo cáo cuối).
4. Spec `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.4 / §4.7: công thức 3 thành phần, nhánh không chuyến mở, luật lấp ô.
   Contract OpenAPI không đổi field (nếu đổi thì sửa `paths/` / `schemas/` trước, chạy `validate_contract.py`).
5. Test unit `domain` / `application` (DoD ≥ 80 %): độ tin cậy chuyến, cap giữ event mạnh, hai nhánh công thức, lấp ô, mỗi điểm đến 1 món.
   Bỏ xfail ca vector ở WP1.
6. `make recsys-gate-run`, ghi baseline mới nếu gate yêu cầu.
7. `git mv` đề xuất sang `docs/prd/update-archive/` (trạng thái `đã áp dụng`, ngày, người chốt); history entry trỏ tới đề xuất.
8. Deploy theo `docs/prd/deployment-plan.md`; sau deploy test lại kịch bản production 07/10 (xem 8 sản phẩm biển) và một khách không chuyến mở.

Checklist:
- [ ] Đề xuất viết lại, `chờ chốt`
- [ ] G5: người dùng chốt
- [ ] PRD cập nhật
- [ ] `profile.py`, `use_cases.py`, `ENGINE_RULES_VERSION`
- [ ] Spec §4.4 / §4.7
- [ ] Unit test ≥ 80 % `domain` / `application`; `pytest src/backend/tests/unit` (1 lỗi có sẵn `test_agent_gateway_consumes_enriched_backend_endpoints` — không liên quan, ghi lại)
- [ ] `pytest src/evaluation/recsys_bench/tests`, `src/backend/tests/architecture`
- [ ] Gate RecSys
- [ ] Đề xuất → `update-archive/`, history
- [ ] Deploy + test lại trên production

### WP6 — Bước 3: dữ liệu và tracking (mỗi mục cần chốt riêng)

- Tín hiệu chủ đề tường minh trong `attributes` / text (cùng team Search + Data); mô tả cho 21 % điểm tham quan chỉ có tiêu đề;
  `_clip` cắt giữa câu; tách combo sai (`parse_combos`). Đổi builder → `TEXT_BUILDER_VERSION` mới, embed lại, đo lại Search **và**
  calibrate lại F14 nếu đã chọn.
- Tracking impression gợi ý + `source` / `position` cho `product_view` (đổi contract `TrackEventRequest`, FR-CDP) — điều kiện để học
  trọng số / bandit sau này.
- Bộ sinh event có sở thích chủ đề (G6) để temporal / nexttrip đo được lợi ích bám sở thích.
- Bench / gate RecSys thêm: theme theo nhóm, tách có / không chuyến mở, đa dạng điểm đến, `component_stats` khi đổi model.

### WP7 — Vệ sinh

- [ ] **Bảo mật:** `askpass.cmd` chứa mật khẩu trên `origin/fix/search-production` (commit `b80acb6`) — tqanh123 đổi mật khẩu và gỡ file khỏi lịch sử nhánh.
- [ ] Dọn `~/code/recsys-theme-2026-10-08/` sau khi người nhận đã có DB + vector.
- [ ] (Tuỳ chọn) cập nhật deck mentor bằng số bước 1–2.

## 5. Thứ tự và phụ thuộc

```
WP0 ──► WP1
  └───► WP2 ──► [G1, G2] ──► WP3 ──► [G3, G4] ──► WP4 ──► WP5.1 ──► [G5] ──► WP5.2–5.8
WP6, WP7: độc lập, làm song song
```

Đi nhanh nhất: WP0 + WP1 (khoảng 1 ngày), WP2 (1–2 ngày, phần lớn là thời gian chạy), WP3–WP4 (1 ngày + chờ chốt), WP5 (1–2 ngày sau khi chốt).
Đây là ước lượng, chưa tính thời gian chờ chốt.

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Merge main đổi engine → số cũ không so được | WP0.6 đo lại mốc; chỉ so cấu hình đo cùng engine |
| F14 phụ thuộc model / text builder | Gắn `Q_LOW` / `Q_HIGH` với `TEXT_BUILDER_VERSION` + model; job index hoặc gate calibrate lại khi đổi |
| Dữ liệu giả lập thưởng pop → chọn sai hướng | Tiêu chí G1–G2 chốt trước khi xem số mới; WP6 đổi bộ sinh event |
| Bản sao production cũ dần | Ghi rõ ngày bản sao trong mọi report; tải lại nếu cần (cần quyền monitor) |
| Lộ dữ liệu bản sao / DSN | Chỉ chuyển qua kênh riêng; không commit `.env`, `.npy`, dump |

## 7. Checklist tổng

- [x] Commit + push §2.1 (08/10)
- [ ] Gửi riêng: dump `vota_prodcopy`, bộ vector
- [ ] WP0 đồng bộ nhánh + mốc mới
- [ ] WP1 tách test purchase
- [ ] WP2 CI ghép cặp, 3 seed, `noisy` cùng khách
- [ ] G1, G2 chốt
- [ ] WP3 bảng quyết định → G3
- [ ] G4 ô khám phá
- [ ] WP4 đo tổ hợp + latency
- [ ] WP5.1 đề xuất viết lại → G5
- [ ] WP5.2–5.8 PRD, engine, spec, test, gate, archive, deploy
- [ ] WP7.1 xử lý `askpass.cmd`
- [ ] WP6 lên kế hoạch riêng
