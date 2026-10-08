# Bàn giao: RecSys bám sở thích khách (profile P2, công thức điểm khi không có chuyến mở, ô khám phá)

- Ngày: 2026-10-08
- Người bàn giao: Pham Nguyen Dang Khoi (soạn cùng Claude Code)
- Người nhận: tqanh123 (Trịnh Quang Anh)
- Nhánh: **`feat/recSys_update`**, tạo từ `release-mvp-v2` @ `6f77e80` (= code production 08/10). Cùng nội dung nghiên cứu cũng có trên
  `bench_search_recomSys` (`0ccc948`), nhưng nhánh đó dùng engine cũ — làm tiếp trên `feat/recSys_update`.
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
| CI ghép cặp, nhiều seed, `noisy` cùng khách | **Xong** 08/10 (WP2) — `eval-2026-10-08-recsys-so-thich-ci.md` |
| Mốc mới trên engine production | **Xong** 08/10 (WP0) — bảng cũ đúng, trừ hai cột nexttrip |
| Tách test mất purchase | **Xong** 08/10 (WP1) — production pass phần nghiệp vụ, xfail chỉ còn ở phần vector |
| Bảng quyết định có CI | **Xong** 08/10 (WP3) — `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` |
| Chọn cấu hình | **Xong** 08/10 — người dùng chốt G3 = **P2 + F14c** (pop 0,35), G4 = **có** ô khám phá B, G1 = ngưỡng điểm ước lượng **0,04** |
| G2 (mức giảm nexttrip) | **Bị từ chối** 08/10 → đã điều tra, có bằng chứng mới và ứng viên `destCap2`; **chờ chốt lại** (`docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7.4) |
| WP4: ô B + latency trên tổ hợp đã chọn | **Xong** 08/10 — `eval-2026-10-08-recsys-g2-va-wp4.md` |
| Đề xuất PRD đúng nội dung mới, người dùng chốt | **Chưa** |
| Sửa engine backend, spec, unit test, deploy | **Chưa** |
| Commit / push | **Xong** 08/10 trên `origin/feat/recSys_update` (base `release-mvp-v2` @ `6f77e80`) |

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

Commit kèm: `src/evaluation/reports/eval-2026-10-07-recsys-grid-llbo-coldstart.md` (grid W_SHORT 07/10). Trọng số 0,7/0,15/0,15,
đề xuất 06/10 đã lưu trữ và history 07/10 **đã có sẵn** trên `release-mvp-v2` nên không commit lại.

### 2.2 Không thuộc bàn giao này

Các thay đổi chưa commit của việc khác (crawler Trip, nạp catalog theo mã băm, search bench, latency…) vẫn nằm local trên máy người bàn giao,
không có trên `feat/recSys_update`. Người nhận không cần quan tâm.

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
| G2 | Mức giảm nexttrip có chấp nhận được không | WP3 — **từ chối 08/10; chờ chốt lại** sau điều tra (§7 của tài liệu quyết định). Phát hiện quan trọng: `seed_histories.plan_trip` bốc điểm đến **không phụ thuộc khách**, nên temporal / nexttrip **không thể** đo được lợi ích bám sở thích → **G6 là điều kiện tiên quyết của G2**, không phải việc làm sau |
| G3 | Chọn công thức: F14 / F7 / khác | WP4 |
| G4 | Có làm ô khám phá B không (đổi hành vi FR-REC-02) | WP4 |
| G5 | Chốt đề xuất PRD viết lại | cài engine (WP5.3) |
| G6 | Đổi bộ sinh event để có sở thích chủ đề (`seed_histories.py`, `MOCK_DATA_SPEC.md`) | WP6 |

Không tự chọn thay người dùng; chưa chốt thì không sửa engine (AGENTS.md §8).

## 4. Đầu việc

Ước lượng thời gian chạy lấy từ log 08/10: một cấu hình đủ ba split + khách giả lập mất 20–45 phút; chỉ khách giả lập ~1 phút / cấu hình.
Chạy song song tối đa 2 tiến trình (4 tiến trình làm mỗi job chậm gần gấp đôi).

### WP0 — Dựng môi trường, đo lại mốc trên engine production

Mục tiêu: mọi số sau này đo trên engine giống production. Nhánh đã dựng từ `release-mvp-v2` nên **đã có** `9b703ba` (sửa cap lặp,
"hôm nay" theo giờ VN, parser `usingDate` chung), trọng số 0,7/0,15/0,15 và `LocalE5Embedder`. Số bước 1–2 trong báo cáo cuối chạy trên
engine cũ của `bench_search_recomSys` (§2.3 báo cáo) → phải đo lại mốc.

1. `git fetch && git switch feat/recSys_update`.
2. Nạp `vota_prodcopy` (`pg_restore`) và vector; tạo env local (`DATABASE_URL`, `CDP_DATABASE_URL`, `EVAL_DATABASE_URL` trỏ DB đó).
3. `profile_variants.py` viết lại theo `build_profile` cũ (không có dict `every`). Kiểm 08/10 trên engine của nhánh này:
   `parity_mismatch_llbo200 = 0` (lượt `eval_profile --profiles P0_prod --scorers F0_prod --n-syn 2 --max-users 50 --splits ""`).
   Parity chỉ so một số trường profile, nên vẫn đưa logic `every` vào bản viết lại cho đúng (tuổi / `ends_on` / món đã mua tính trên mọi
   event; cap chỉ giới hạn vector) và mở rộng parity so cả `bought_units`, `ends_on`, `active_trip`, `strategy`.
4. Đo lại P0+F0, P2+F7, P2+F14 trên engine này; so với bảng cũ; ghi report `src/evaluation/reports/eval-YYYY-MM-DD-recsys-so-thich-moc-moi.md`.
5. Chọn nhánh đích cho PR khi cài engine (WP5): `release-mvp-v2` hay `main`. Lưu ý `origin/main` còn khác `release-mvp-v2` ở phần
   recommendation (vẫn trọng số 0,6/0,25/0,15) — việc đưa 0,7 vào `main` đã chốt 07/10, chỉ thiếu PR.

Checklist:
- [x] Nhánh dựng từ engine production (`feat/recSys_update` @ `6f77e80` + 2 commit bàn giao)
- [x] `pytest src/evaluation/recsys_bench/tests` trên nhánh: 138 passed, 2 xfailed (08/10)
- [x] DB `vota_prodcopy` + vector + env trên máy người nhận (08/10: `pg_restore` gói bàn giao vào container `vota-prodcopy-pg` :55433; 18/18 checksum OK)
- [x] Dùng `.npy` của gói bàn giao, `meta.json` khớp revision `614241f…` (không cần sinh lại)
- [x] `profile_variants.py` thêm logic `every`, parity mở rộng từ 3 lên 8 phép so: 0/200, `parity_mismatch_by_field = {}`
- [x] Mốc mới đo xong (thêm P0+F7, P2+F0, P2+F13a), report `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-moc-moi.md`
- [ ] Chốt nhánh đích PR; W 0,7/0,15/0,15 có trên `main` — **còn lại, cần người dùng**
- [x] history entry (`history/2026-10-08-wp0-wp3-recsys-bam-so-thich.md`)

DoD: **đạt** — 58 / 60 ô khớp bảng cũ đến chữ số cuối; chênh duy nhất ở nexttrip nDCG@10 (+0,0008 … +0,0009) và nexttrip
hit@4 (+0,0012 … +0,0013 = 1 khách / 800), đúng dự đoán §2.3 của báo cáo cuối. Không cần đo lại nghiên cứu.

### WP1 — Sửa test mất purchase

Ca `production-known-bug` trong `test_profile_variants.py` gộp hai kiểm. Trên nhánh này `build_profile` đã đúng phần nghiệp vụ
nhưng vẫn không đưa purchase vào vector chuyến.

1. Tách thành `test_purchase_state_survives_repeat_cap` (bought_units, purchased_taxonomies, ends_on, ended, active_trip, strategy) —
   `build_profile` production phải **pass**, bỏ xfail.
2. Thêm `test_strong_events_weight_trip_vector` (purchase / cart nằm trong `trip.events`): production xfail strict cho tới khi WP5
   sửa; P1 / P4 pass.
3. Sửa docstring: "production" = `build_profile` của `src/backend`, ghi commit tham chiếu.

Checklist:
- [x] Hai ca tách riêng, tên đúng nghĩa; thêm P2 vào cả hai ca
- [x] `pytest src/evaluation/recsys_bench/tests/test_profile_variants.py`: 15 passed, 4 xfailed — production **pass** ca
      trạng thái chuyến (bỏ xfail), xfail chỉ còn ở ca vector (production + P2, mỗi ca 2 thứ tự đầu vào)
- [x] history entry

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
- [x] `--per-user-out` (JSONL mỗi khách) + `--scenarios` / `--syn-seeds` / `--f14-cal-profile` / `--f14-cal-seed`
- [x] `paired_ci.py` + 14 test unit (gồm `noise_effect` ghép qua `baseUid`)
- [x] `noisy` cùng khách: thêm kịch bản `noisy_paired` (`theme_exp.with_noise`). **Giữ nguyên tên `noisy`** cho cohort độc
      lập cũ thay vì đổi tên như plan ghi: đổi tên không đủ, phải giữ cả vị trí trong luồng rng, nên cách này mới tái sinh
      đúng số cũ — đã kiểm: mọi số theme của bản 08/10 ra y nguyên (`noisy` 0,447 / 0,666)
- [x] 3 seed khách giả lập (42, 7, 2026), có bảng trung bình ± độ lệch giữa seed
- [x] Dùng **toàn bộ** khách mỗi split (LLBO 4.072 / temporal 775 / nexttrip 1.835). Lý do: trên máy này một cấu hình đủ ba
      split mất ~4 phút chứ không phải 20–45 phút, nên chi phí 2–5× là chấp nhận được; và mẫu 800 khách đầu theo id lệch
      thật (LLBO h@20 0,836 ở 800 so với 0,808 ở toàn bộ; nexttrip h@20 0,025 so với 0,035)
- [x] Report `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-ci.md` có bảng CI
- [x] history entry

DoD: **đạt** — mọi so sánh trong khuyến nghị có CI ghép cặp (`results/2026-10-08-wp0-wp3/ci_full_*.json`).

### WP3 — Chọn công thức (cần G1, G2)

1. Ứng viên: F14, F7. Với F14 thử thêm pop 0,25 / 0,35 và độ bền calibration (q tính từ 3 seed calibration khác nhau — q lệch nhiều
   thì F14 không ổn định).
2. (Tuỳ chọn) F13 centering toàn phần: center cả vector truy vấn Weaviate, profile, MMR. Chỉ làm nếu F14 / F7 không đạt tiêu chí.
3. Bảng quyết định: mỗi ứng viên × mỗi tiêu chí G1 → đạt / không đạt, kèm CI.
4. Trình người dùng chọn (G3).

Checklist:
- [ ] Tiêu chí G1 đã chốt, chép vào báo cáo — **còn lại, cần người dùng** (bảng đối chiếu sẵn ở
      `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §4; ngưỡng temporal 0,03 không phân biệt được bằng dữ liệu hiện
      có, có hai cách xử lý đề nghị)
- [x] F14 biến thể pop (0,25 / 0,30 / 0,35 / 0,45, toàn bộ khách) + độ bền calibration (3 seed: `q` lệch ±0,3 %, kết quả
      lệch ≤ 0,006 → F14 **không** nhạy với tập calibration)
- [x] Bảng quyết định có CI: `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md`. Biên hiệu quả
      production → P2+F7 → P2+F14c → P2+F14 → P2+F13a; F14b và F14d bị trội, loại
- [ ] Người dùng chọn công thức (G3), ghi ngày / người chốt — **còn lại, cần người dùng**

Phát hiện phải ghi lại: ở cỡ mẫu đầy đủ, **F13a không còn thua F14** ở temporal / nexttrip (CI chứa 0) và hơn ở
`noisy_paired` (+0,028), nên lý do loại F13a ở báo cáo cuối §6 không còn đứng được. Và **P2+F14c (pop 0,35) hơn P2+F7 ở
theme (+0,035) mà không có chi phí nào phân biệt được.**

2b. (Tuỳ chọn, chưa làm) F13 centering **toàn phần**: center cả vector truy vấn Weaviate, profile và MMR. Giờ đáng làm hơn
    trước, vì F13a bản chấm-điểm-thôi đã ngang F14 ở split thật và tốt nhất ở độ bền với nhiễu.

### WP4 — Đo đúng tổ hợp sẽ triển khai · **đã làm 08/10** (`eval-2026-10-08-recsys-g2-va-wp4.md`)

Cấu hình: P2 + phần còn lại của P1 (purchase / cart luôn vào vector) + công thức đã chọn + ô khám phá B (nếu G4 đồng ý).

1. Cài ô B trong tiến trình đo (`eval_slots.py` đã có `fillExplore` cho profile production) để chạy chung với P2 + công thức.
   **08/10: `eval_slots.py` đã thêm `--profile` và dựng được scorer F13 / F14**, nên chạy được ngay sau khi có G3; chưa chạy
   vì còn chờ G3 / G4.
2. Đo LLBO / temporal / nexttrip / coldstart (`recsys_bench`), khách giả lập `between` / `open` / `noisy`, AC-REC-01/02.
3. Latency: `recsys_bench` `http_latency` hoặc gọi API local, trước / sau, p50 / p95. Ô B không được thêm lượt gọi Weaviate; nếu cần
   `near_vector(u_long)` thì đo riêng.
4. Kiểm `because[]` vẫn hợp lệ theo contract (không thêm field).

Checklist:
- [x] Ô B chạy cùng P2 + F14c: hit@4 **giống base đến bốn chữ số** ở LLBO (0,5324) và temporal (0,1045); thêm món ở điểm
      đến khác cho 29,2 % khách có chuyến mở. Thay hẳn ô 4 mất 0,033 LLBO h@4 → giữ luật chỉ lấp ô trống
- [x] Đủ ba split (toàn bộ khách) + khách giả lập 3 seed; thêm bộ đo mới `tgtHit` / `nextDestHit` trên dữ liệu **có** sở
      thích (`--syn-target`) — bộ đo duy nhất phản ánh được lợi ích
- [ ] Coldstart + AC-REC-01/02 — **còn lại**
- [x] Latency **ranking-only**: p95 38,63 → 38,54 (F14c) → 39,26 ms (destCap2), Δp95 +0,63 ms. Tiêu chí latency đầu-cuối
      của G1 vẫn trống, cần `http_latency` hoặc API local
- [x] Report + history
- [x] (ngoài plan) Ứng viên mới **destCap2** — giới hạn 2 món / điểm đến khi không có chuyến mở: nextDestHit@20 +0,2472 so
      với F14c, trả 0,013 theme; đưa khoảng cách độ phủ điểm đến so với production từ −0,296 về −0,049

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

- [x] Commit + push §2.1 lên `feat/recSys_update` (08/10)
- [x] Gửi riêng: dump `vota_prodcopy`, bộ vector (gói `recsys-theme-2026-10-08-ban-giao.zip`, 18/18 checksum OK, đã nạp)
- [x] WP0 môi trường + mốc mới trên engine production
- [x] WP1 tách test purchase
- [x] WP2 CI ghép cặp, 3 seed, `noisy` cùng khách
- [x] G1 chốt 08/10: ngưỡng điểm ước lượng 0,04
- [ ] **G2 chờ chốt lại** — từ chối 08/10; đã điều tra, ba lựa chọn ở §7.4 tài liệu quyết định
- [x] WP3 bảng quyết định → trình G3
- [x] G3 chốt 08/10: P2 + F14c (pop 0,35)
- [x] G4 chốt 08/10: có làm ô khám phá B — đã đo lại trên đúng tổ hợp, miễn phí về độ chính xác
- [x] WP4 đo tổ hợp + latency (ranking-only); coldstart + AC-REC-01/02 còn lại
- [ ] WP5.1 đề xuất viết lại → G5
- [ ] WP5.2–5.8 PRD, engine, spec, test, gate, archive, deploy
- [ ] WP7.1 xử lý `askpass.cmd` (của chủ nhánh `fix/search-production`, không tự làm)
- [ ] WP6 lên kế hoạch riêng

Tài liệu sinh ra ở lượt WP0–WP3 (08/10): `src/evaluation/reports/eval-2026-10-08-recsys-so-thich-moc-moi.md`,
`eval-2026-10-08-recsys-so-thich-ci.md`, `docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md`,
`src/evaluation/recsys_bench/theme_study/results/2026-10-08-wp0-wp3/`,
`history/2026-10-08-wp0-wp3-recsys-bam-so-thich.md`.

Lượt điều tra G2 + WP4 (08/10, sau khi chốt gate): `src/evaluation/reports/eval-2026-10-08-recsys-g2-va-wp4.md`,
`docs/spec/bench/recsys-bam-so-thich-quyet-dinh.md` §7,
`src/evaluation/recsys_bench/theme_study/results/2026-10-08-g2-wp4/`,
`history/2026-10-08-g2-wp4-recsys-bam-so-thich.md`. Script mới: `loss_analysis.py`, `dest_diversity.py`,
`rank_latency.py`.
