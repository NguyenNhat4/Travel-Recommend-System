# Kế hoạch mở rộng gold search bench: gold_v3 → gold_v4 (đợt "v4a"), guard trước, nhãn sau

- **Phục vụ:**
  - **FR-SRC-01**: tìm kiếm từ khoá + ngữ nghĩa bằng tiếng Việt tự nhiên (`docs/prd/requirements.md:21`).
  - **FR-SRC-03**: lọc theo điểm đến, loại dịch vụ, hạng sao.
  - **FR-SRC-04**: không có kết quả.
  - **AC-SRC-01**.
  - **test-plan §2.5**: NDCG@10, Recall@5/10.
  - KPI "Search Relevance" (`docs/prd/project-brief.md`).
  - Phần độ bền với câu không dấu, viết tắt, sai chính tả dựa vào mục tiêu của project-brief "tìm được đúng sản phẩm bằng **bất kỳ cách diễn đạt tự nhiên nào**" (`project-brief.md:46`, `:52`). FR-SRC-01 tự nó không nhắc tới không dấu hay typo.
- **Phạm vi:** plan này chỉ là **công cụ đánh giá**. Không đổi hành vi backend, frontend, contract hay DDL.
- **Đầu vào:** đề xuất `docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md` (đổi tên từ `gold_v4_bo_sung_va_quy_trinh_gan_nhan.md` ngày 05/10, D8). Plan này thay cho phần "Phạm vi gold_v4a" của đề xuất. Rubric, ngưỡng và quy trình chốt nằm ở plan này và `gold-guide.md`, không lấy từ §4, §7, §9 của đề xuất. §2.4 liệt kê từng mục của đề xuất và cách plan xử lý.
- **Lịch:** hôm nay T2 05/10 là **Day 6** của `docs/plan/2026-09-28-lich-10-ngay-3-engine.md`.
  - **Code freeze T5 08/10 (Day 9).** T6 09/10 sinh lại mọi số từ tag.
  - Việc Track A Day 6–8 (S-sweep, `qu.py`, gate F1/P) chưa bắt đầu và tranh giờ với plan này. Lead phân xử.
- **Catalog bench:** snapshot **2026-09-23**, 11.387 bản ghi, 3.183 search unit (hotel_property 2.321 · attraction 610 · combo 133 · flight_route 113 · golf 6).
  - Mọi pool và report mới ghi rõ snapshot này.
  - Snapshot 2026-09-30 có cùng 113 route và cùng tập unit.
- **Người đọc:**
  - Lead: người dùng, chốt quyết định.
  - A1: QAnh (tqanh123).
  - A2: Khoi (chờ xác nhận).
  - Dev: phiên Claude. Viết code, chạy, viết report. Không gán nhãn câu chung.
- **Trạng thái:** **đã chốt cổng G0 (05/10)** — xem mục "Quyết định đã chốt" ngay dưới; đang làm Track L. Phần còn lại của plan là phân tích và phương án gốc; chỗ nào mâu thuẫn với mục "Quyết định đã chốt" thì mục đó thắng.

---

## Quyết định đã chốt (05/10) — thắng các mục bên dưới khi mâu thuẫn

| # | Người dùng chốt | Ảnh hưởng tới plan |
|---|---|---|
| D1 | Dùng rubric v4 làm rubric gán nhãn | **Thay §2.3 điểm 1 và §5 "một rubric gold-guide".** Câu từ `gold_v4` gán theo rubric v4 (`gold-guide.md` mục "Rubric v4", kèm #8–#14 và chính sách từng câu). Câu `gold_v1`–`gold_v3` giữ nhãn cũ (gold chỉ thêm). Report tách khối câu v3 / câu v4. |
| D2 | Track L | Đợt này làm **Track L** (23 câu, tag `gold_v4`). Track G (spec guard, probe, `guard_facts`, guard metric) để sau. |
| D3 | Thêm 2 slice | Đã nối `taxonomy_collision`, `flight_direction` vào cuối `SLICES`; quota 5 / 6; `target` 211, `minimum` 45. |
| D4 | Duyệt #8–#14 | Đã ghi vào `gold-guide.md` (áp cho câu từ gold_v4). |
| D5 | Chỉ QAnh gán; vẫn làm Track L trước freeze | `split --overlap 0`, không có câu chung, không đo κ. Report ghi tỉ lệ nhãn máy được duyệt giữ nguyên / bị sửa thay cho κ. |
| D6 | Cho phép nhãn máy, người duyệt | **Thay §9 bước 4–6 và §9.3.** Nhãn máy cho mọi cặp, cả 1 / 2: luật tất định `rule:v4a` (negation, flight, out_of_catalog) + Claude (2 người gán độc lập + trọng tài) cho `taxonomy_collision` + Claude soát lại nhãn luật phủ định (bất đồng ghi `⚠` vào note). QAnh duyệt trong app; `import --append` từ chối nhãn máy chưa duyệt. |
| D7 | Chấp nhận | Guard chỉ báo cáo, WIN tính trên câu `gold_v3` — cài cùng Track G. |
| D8 | Chấp nhận | Đã đổi tên spec v4, thêm dòng FR và trạng thái, viết §1 thành giả thuyết bench, thêm §14 (đề xuất SLICES). |
| D9 | Chấp nhận | Giữ 10 qid trôi nhãn; report có / không có. |
| D10 | `/search` vẫn có vé máy bay | `flight_direction` là slice bình thường, không chỉ chẩn đoán. FR-SRC-03 ghi "Vé máy bay không nằm trong kết quả `/search`" → lệch PRD đã biết, cập nhật PRD sau (D12). |
| D11 | Sửa lỗi dữ liệu | Đã sửa matcher tiện ích của bench (bỏ chuỗi "Không có …" và chuỗi khoảng cách; `elevator` 681 → 607 khách sạn, `golf` 2 → 1) và build lại catalog bench. Tỉnh sai của sản phẩm golf và Vinpearl Hà Tĩnh trùng nằm ở snapshot nguồn (`src/data_collection`) → việc riêng, chưa làm. |
| D12 | Bench trước, cập nhật PRD sau | Không sửa PRD đợt này. Filter-first chỉ là arm bench; đổi `/search` production phải qua `docs/prd/update/`. |

**Đã thực hiện (05/10):** 23 câu `gold/v4a/` — qid `c0673`–`c0727` (bước 3, khối 3 case như `drafts_raw.tsv` cũ) và `c0730`–`c0733` (out_of_catalog); câu bay dùng filter `variant = flight_route` (không lọc destination, để pool có tuyến ngược làm bẫy). Pool B0 (dense ∪ BM25 depth 15): 559 cặp, đủ mọi tuyến đúng của 6 câu bay (kể cả 10 / 10 ở hai câu chỉ có điểm đi / điểm đến). Split: `pool_A.csv` 12 câu / 279 cặp, `pool_B.csv` 11 câu / 280 cặp.

---

## 0. Tóm tắt một đoạn

Đề xuất v4 nhắm đúng vấn đề: các lỗi production (sai chiều bay, lẫn loại sản phẩm, phủ định, không dấu, không có kết quả) bị nDCG trung bình che mất.

Làm nguyên văn thì không vừa 3 ngày trước freeze:
- 80 query, khoảng 1.500–2.300 quyết định người;
- một rubric mới, 9 trường GoldRecord mới, trường catalog mới, khoảng 9 nguồn pool.

Nó còn phá khả năng so sánh: ít nhất 162 trong 1.184 nhãn 1 của v3 sẽ thành 0 dưới rubric v4, trong khi gold là append-only.

Plan chọn hướng **guard trước**, gồm hai track:

**Track G** (không cần nhãn cặp, chắc chắn xong trước freeze):
- Spec guard dạng sidecar cho cả 131 query v3.
- Khoảng 85 **probe** không cần nhãn: chiều bay, va chạm loại, phủ định, bản có dấu hoặc khai triển của query v3.
- Guard tính từ catalog trên `top_ids` đã lưu, nên `sb rescore` cho run cũ có guard miễn phí.

**Track L** (append nhỏ có nhãn, có cổng go/no-go):
- **23 query mới**, chấm theo **một rubric duy nhất**: gold-guide + quy ước 30/09 + quy ước 05/10.
- Khoảng 600–700 quyết định người, cỡ D5a. Tag **`gold_v4`**.
- Trễ hạn thì chuyển sang sau freeze.

**WIN** vẫn tính trên tập qid gold_v3. Query và guard mới chỉ báo cáo, cho tới khi người dùng chốt ngưỡng.

---

## 1. Mục tiêu và mã FR/NFR

| # | Mục tiêu | Đo bằng | Mã |
|---|---|---|---|
| M1 | Không coi arm nào là tốt hơn khi nó kéo lên top kết quả sai chiều bay, sai loại sản phẩm, vi phạm phủ định đã ghi nhận, hoặc sai điểm đến | Guard (§7), báo cáo tách khỏi nDCG | FR-SRC-01, FR-SRC-03 |
| M2 | Đo độ bền với câu không dấu / viết tắt mà không phá luật "một cách nói cho mỗi ý định" | Probe twin + RobustnessGap theo dest_share/required_hit | FR-SRC-01 (project-brief:46/52) |
| M3 | Thêm query có nhãn ở các vùng gold_v3 còn mỏng: phủ định kiểm được bằng máy, va chạm loại, chiều bay, ngoài catalog | 23 qid mới, tag `gold_v4` | FR-SRC-01/03/04, AC-SRC-01 |
| M4 | Không làm hỏng số đã báo cáo | Append-only, `verify-append gold_v3` PASS, WIN scope = gold_v3 | test-plan §2.5 |

**Không làm trước freeze:**
- đổi `/search` production;
- relabel cặp v3;
- tách variant thành qid riêng;
- dùng LLM làm ground truth;
- thêm arm mới;
- đổi `items.parquet`, filter DSL hoặc collection Weaviate;
- sửa bug catalog.

---

## 2. Phân tích đề xuất v4

### 2.1 Điểm mạnh (giữ lại)

Đề xuất nhắm đúng vấn đề. Số liệu đo lại ngày 05/10 xác nhận:

| Lỗi | Bằng chứng |
|---|---|
| Chiều bay | c0373 "Vé máy bay Buôn Ma Thuột - Hà Nội": tuyến ngược đứng **hạng 1 ở cả 5 arm** (B0, E2.e5, APP.dense/hybrid/hybrid_norm), nhưng nDCG vẫn 0,631. c0078: 4/10 kết quả top-10 là tuyến ngược. |
| Phủ định | c0241, c0253: top-1 chứa đúng tiện ích bị loại, ở mọi arm. |
| Ngoài catalog | 0/3 câu trả về rỗng. |
| Không dấu | Bỏ dấu 104 câu có dấu: nDCG e5-base tụt 0,785 → 0,168 (full) / 0,534 (condensed). Tỉ lệ đúng điểm đến trong top-10 tụt 0,85 → 0,22. |

Các ý thiết kế nên giữ:
- Tách "query understanding" khỏi "retrieval/ranking". Guard tính được trên `top_ids`.
- Auto-final **chỉ nhãn 0**, và chỉ khi có bằng chứng catalog. LLM chỉ làm pre-annotator.
- Bootstrap theo nhóm (family), không coi các biến thể là độc lập.
- Không chấm toàn catalog. Dùng pooling + bẫy (adversarial) + chiều ngược.

### 2.2 Vấn đề (có dẫn chứng)

| # | Vấn đề | Dẫn chứng | Hệ quả |
|---|---|---|---|
| V1 | Rubric 0/1/2 của v4 xung đột gold-guide | v3 cho "đúng nơi sai loại → 1" (#2), v4 cho sai core taxonomy → 0. v4 hard-fail cả giá và sao, v3 không chấm giá. v4 có trạng thái "review" trong khi `Label` chỉ có 0/1/2 | ≥ 162/1.184 nhãn 1 đang active là item khác variant (dest_type 103/128). Trộn hai rubric trong một nDCG làm phép so sánh mất nghĩa. Gold append-only (`verify-append`) nên không relabel được |
| V2 | Câu §1 "constraint phải được parse và filter trước retrieval" là hành vi sản phẩm | Contract §2.2: "Không tách điểm đến/số khách thành filter (bước 2)" | Chỉ được coi là **giả thuyết bench** (arm S3/S4 trong `arms.md`, chưa dựng). Muốn đưa vào production phải có đề xuất `docs/prd/update/` |
| V3 | Sao là ràng buộc cứng; vé bay trong /search; trang rỗng | Contract §2.5 (`starRatingMin` mềm). FR-SRC-03: "Vé máy bay không nằm trong kết quả `/search`". FR-SRC-04: gợi ý khi kết quả yếu | Không lấy sao làm guard. `no_result_ok` chỉ là metric của engine. Slice bay chỉ dùng để chẩn đoán |
| V4 | Trường schema trong ví dụ không tồn tại | `GoldRecord` có `extra="forbid"`. DSL không có `vertical`, `product_kind`, `has_golf`, `origin_city`. `metrics` gọi `F.validate` trên filter gold, nên một record sai làm hỏng chấm điểm **mọi arm** | Metadata v4 phải nằm ở sidecar. Filter gold chỉ dùng trường DSL có sẵn |
| V5 | Ví dụ golf không đứng được trên catalog | Golf chỉ có 6 sản phẩm: 5 voucher Vinpearl cùng giá 1,7 triệu (một cái tên "Voucher Tee time") + Sea Links là POI không giá. 3/6 sai `province`. "voucher golf Hội An" trùng c0088. "resort Nha Trang không có sân golf": không resort NT nào có golf, nên không có đáp án sai để loại | Bỏ phân biệt voucher/tee-time. Golf chỉ giữ làm probe một đáp án |
| V6 | Tên slice trùng v3 | no_diacritic ≈ no_diacritics; typo + alias ≈ abbrev_typo; negation_hard ≈ amenity_negation; mixed ≈ multi_constraint | Chia nhỏ `by_slice` và làm rối luật slice. Chỉ thêm `taxonomy_collision`, `flight_direction` |
| V7 | Tách variant thành qid riêng phá luật "một cách nói cho mỗi ý định" | `search-eval-checklist.md:199`; gold-draft-prompt rule 10; chưa có code gộp theo `equivalence_group` | Variant để sau freeze. Trước freeze dùng probe twin không cần nhãn |
| V8 | Khối lượng vượt sức người | v4 §9.2: 900–1.400 adjudication + 600–900 review. Cap D5a là 700 cặp (≈ 20 s/cặp) | Cắt còn 23 query + probe |
| V9 | Bug dữ liệu làm sai rule/guard | Matcher tiện ích bắt cả chuỗi phủ định lẫn chuỗi khoảng cách. Kiểm lại 05/10: elevator chỉ đến từ "Không có Thang máy" ở 74 KS; wifi 3; golf 1 ("Sân Golf Đà Lạt 570 m"); pool 2 ("Story Beach & Pool 190 m", "Hồ bơi chung cư 930 m"); bar 8; spa ≥ 6; kids_club 1. restaurant, airport_shuttle, parking, breakfast: 0 ca | Guard và rule phải dùng tiện ích **đã làm sạch**. Không dùng elevator/wifi/golf/pets/smoking làm điều kiện phủ định |
| V10 | Ngưỡng guard và luật WIN mới là cấu hình bench | Spec §1.5, §1.7 #1: agent không được tự chọn. `max_slice_loss = 3` hiện chặn ≈ 97,5 % khi hai arm như nhau (mô phỏng); chưa cặp nào từng WIN | Mọi guard mới chỉ báo cáo. Người dùng chốt ngưỡng |
| V11 | Không rõ ai double-label, κ đo trên tập nào | κ gold_v1 = 0,661 trên 640 cặp, gồm cả các cặp sai nơi dễ. Riêng 468 cặp cùng điểm đến: κ_lin 0,388; κ(0 vs ≥1) −0,046 (p_o 0,83) | Không gate κ trên mẫu "chỉ cặp khó". Gate trên mọi cặp chung như v1, báo thêm κ phần dư |
| V12 | Quản trị tài liệu | Tên file dùng gạch dưới (AGENTS.md §7); không có dòng FR/NFR; chưa có entry `history/` | Đổi tên, thêm FR, thêm header trạng thái (§3) |

### 2.3 Điều chỉnh so với đề xuất

1. **Một rubric.** Độ chặt về loại của v4 chuyển thành guard (forbidden / type / direction), không thành nhãn 0.
2. **Metadata v4 nằm ở sidecar** (`gold/guards/*.jsonl`, `gold/annotations.jsonl`). `GoldRecord` giữ nguyên; 132 dòng v3 giữ byte-identical.
3. **Sự thật catalog cho guard** nằm ở bảng dẫn xuất `guard_facts.parquet`:
   - `origin_city`/`destination_city` lấy từ thuộc tính thô của snapshot;
   - tiện ích đã làm sạch;
   - không đổi `items_sha256`, nên không phải nạp lại mọi collection 3 ngày trước freeze.
4. **Chỉ 2 slice mới:** `taxonomy_collision`, `flight_direction`, nối vào **cuối** `SLICES`.
5. **WIN scope = qid gold_v3.** Khối mới báo riêng. Guard chỉ báo cáo.
6. **Tag `gold_v4`**, vì regex `^gold_v(\d+)$` từ chối "gold_v4a". "v4a" chỉ là tên đợt.
7. **Nguồn pool:** không thêm arm (spec §1.7 #5). Dùng:
   - `sb gold pool` (dense ∪ BM25);
   - holes từ các arm có sẵn;
   - **inject** theo luật (đáp án đầy đủ, tuyến ngược, bẫy) qua đường holes. Inject không phải arm và không sinh `per_query`.

### 2.4 Cách xử lý từng mục của đề xuất v4 (không bỏ sót mục nào)

| Mục v4 | Nội dung | Xử lý trong plan | Lý do |
|---|---|---|---|
| §1 | Parse + filter trước retrieval | Viết lại thành giả thuyết bench (T-doc-4) | Contract §2.2 |
| §3 | 10 slice mới | Giữ 2 slice mới; 5 slice gộp vào slice v3; `negation_soft`, `mixed_constraints`, `flight_partial_route` để sau (§14) | V6; chưa arm nào áp filter |
| §4 | Rubric 0/1/2 chặt + "review" | Không áp dụng; một rubric + quy ước 05/10 (§5) | V1 |
| §5/§12 | Trường schema (checklist) | Ánh xạ theo §6.3 | V4 |
| §7 | Guard + 5 luật WIN bổ sung | §7.1 (guard), §7.3 (cả 5 luật) | V10 |
| §8.3 | Nguồn pool + cỡ pool theo slice | §9 bước 2 + bảng §9.1 | Cap 700 |
| §8.4 | Rule status + confidence | §9.2 | Rule tất định |
| §8.5–8.6, §9.1 | LLM pre-label, auto-final | Không dùng LLM cho 1/2; auto-final chỉ rule-0 (§9.3) | Luật 30/09 |
| §10 | Double-label 100 % batch đầu ở slice an toàn | **Lệch có chủ đích** (§9.3), D5/D6 | Cap + `labeling_core.py:357` |
| §11 | Cột debug `per_query` | §6.4 | Chưa có parser / fusion internals |
| §13 #4 | Người chốt top-k/hole và slice an toàn | **Lệch có chủ đích** (§9.3) | Như trên |
| §9.3 | Đích dài hạn | §14 | — |

---

## 3. Quản trị (làm trước tiên)

| Việc | Chi tiết | Cần người dùng? |
|---|---|---|
| T-doc-1 | Đổi tên `gold_v4_bo_sung_va_quy_trinh_gan_nhan.md` → `docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md` (file chưa track: `mv` rồi `git add`) | Có (file của người dùng) |
| T-doc-2 | Thêm dòng "Phục vụ: FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01, test-plan §2.5" | Có |
| T-doc-3 | Thêm header trạng thái: "Đề xuất tham khảo. Rubric §4, ngưỡng §7/§9 **không áp dụng**. Phạm vi và rubric hiện hành: `docs/plan/2026-10-05-gold-v4a-mo-rong.md` + `gold-guide.md` (Quy ước chốt 05/10)". Mục đích: không để hai rubric mâu thuẫn cùng tồn tại trong `docs/spec/bench/` | Có |
| T-doc-4 | Viết lại câu §1 "phải được parse và filter trước retrieval" thành "giả thuyết bench, kiểm bằng arm S3/S4" | Có |
| T-doc-5 | Ghi đề xuất đổi `gold_schema.SLICES` (header file yêu cầu "ghi đề xuất") thành một mục ngắn trong spec đã đổi tên. `search_bench` **không có trên main** (`git ls-tree main` không ra file nào), nên sau khi được duyệt sẽ commit trên nhánh trunk của bench là `bench_search_recomSys`, rồi merge vào `feat/gold-v4` | Có |
| T-doc-6 | Spec mới `docs/spec/bench/search-guards.md` (có dòng FR): định nghĩa guard, probe, quy tắc version | Không (spec bench) |
| T-doc-7 | Cập nhật index `docs/spec/bench/README.md`. Thêm vào `arms.md` câu "probe và inject không phải arm" | Không |
| T-doc-8 | `src/evaluation/README.md` là README của lab RecSys, không phải README search bench (AGENTS.md §1.2 ghi là "chưa tồn tại"). Báo người dùng, không tự sửa | Báo |
| T-hist | Mỗi task một entry `history/2026-10-0X-<slug>.md`, liệt kê đủ file theo `git status`, nằm trong cùng commit. Commit message một dòng ngắn | — |

**Xác nhận trước khi code** (AGENTS.md §1.3), đăng trước commit code đầu tiên:
- danh sách file đã đọc;
- FR/AC phục vụ;
- ràng buộc: append-only; một cách nói cho mỗi ý định; Judged@10 ≥ 0,80, mỗi slice ≥ 0,70; κ ≥ 0,6; min_per_slice 3; spec §1.7;
- không có entry "dang dở" nào đang mở cho phạm vi gold;
- không lệch PRD (§15).

---

## 4. Phạm vi

### 4.1 Track G: guard và probe (0 nhãn cặp)

**(a) Spec guard cho 131 query v3** (`gold/guards/specs_gold.jsonl`, khoá theo qid).

119 câu có nêu điểm đến được trích bằng gazetteer + bảng địa danh con (§6.2), rồi người duyệt. Các spec riêng:

| qid | Loại guard |
|---|---|
| c0373 | direction_explicit |
| c0070, c0078 | direction_partial |
| c0241, c0250, c0253 | negation, key sạch: pool, restaurant, airport_shuttle |
| c0244, c0247 | negation qua raw slug, gắn cờ `facts_quality=raw` |
| c0085, c0088 | taxonomy: allowed = golf; forbidden = golf ở điểm đến khác + attraction/combo có tên "Voucher" |
| c0446, c0472 | taxonomy: allowed = attraction |
| c0574, c0585, c0663 | no_result |

**(b) Probe** (`gold/guards/probes.jsonl`, id `p0001…`).
- Mỗi probe một cách nói và không vào nDCG.
- Cặp tuyến đã kiểm trên snapshot 2026-09-23 (route cấp cha, 113 route / 112 cặp).

| Nhóm | n | Nội dung |
|---|---:|---|
| direction_explicit | 24 | 12 cặp × 2 chiều: HAN↔DAD, SGN↔PQC, HAN↔SGN, **SGN↔Thanh Hóa**, DLI↔HAN, HUI↔SGN, CXR↔HAN, PQC↔HAN, HPH↔SGN, VII↔SGN, UIH↔HAN, SGN↔DLI. Thiết kế đối xứng: arm mù chiều đạt khoảng 50 %. Cách nói luân phiên: "từ A đến/vào/ra B", "A - B", "A đi B"; khoảng 5 không dấu, khoảng 3 IATA/alias. **Bỏ BMV↔HAN**, vì BMV→HAN chính là ý định c0373. Thay bằng SGN↔Thanh Hóa: cả hai chiều có trong catalog (mỗi chiều 1 route), không cặp nào khác trong plan dùng. HAN↔Thanh Hóa **không có** route nào, và HAN↔Cần Thơ đã dùng ở Track L. Không dùng ý định c0463 (đã vào Track L) |
| direction_partial | 6 | Thành phố có cả tuyến vào lẫn tuyến ra, khác c0070/c0078 và Track L, ví dụ: từ Đà Lạt, từ Phú Quốc, đến Nha Trang, đến Buôn Ma Thuột. Bỏ Điện Biên Phủ (0 tuyến vào nên guard rỗng) |
| route_absent | 6 | HN→Côn Đảo, SGN→Cần Thơ (chỉ có Cần Thơ→SGN), Nha Trang→Đà Lạt, Đà Nẵng→Nghệ An, "bay đến Pleiku", "bay đến Tuy Hòa". Guard: tuyến ngược không nằm trong top-3 |
| negation | 10 | Sinh bằng script: (điểm đến × có X × không Y) trên key sạch; ≥ 5 đáp án, ≥ 5 bẫy; không trùng Track L |
| exclusion | 3 | "resort Nha Trang không phải Vinpearl" (token tên `vinpearl`, vì `brand` null trừ 26 KS); "vé VinWonders Phú Quốc, không mua combo"; "khách sạn Hội An không phải homestay" (token tên, đúng nhưng không đủ) |
| taxonomy | 8 | Golf một đáp án: tee time golf Phú Quốc; sân golf Vũ Yên Hải Phòng (bẫy là 8 combo VinWonders Vũ Yên); golf TP.HCM (LéMan); sân golf Phan Thiết (Sea Links, cách nói "địa điểm"). Thêm cáp treo Hòn Thơm (POI vs vé) và 3 va chạm do generator đề xuất, có kiểm trùng ý định |
| robustness_twin | 28 | 24 twin với `equivalence_group` = qid: bản có dấu của 12 câu `no_diacritics` + bản khai triển của 12 câu `abbrev_typo`. Twin là **nhóm tương đương khai báo trước**, nên được miễn luật loại trùng. Thêm 4 probe va chạm khi bỏ dấu: "resort con dao", "can ho can tho", "khach san phong nha", **"homestay cat ba"** (18 homestay ở Cát Bà; Cát Bà ⊂ Hải Phòng). **Bỏ "vinpearl ha tinh"**: cùng ý định với c0324 "thông tin Vinpearl Ha Tinh, Affiliated by Meliá" (active, named_entity). Bỏ "khach san vinh" (đọc được hai nghĩa: Vinh / vịnh) |

**Tổng 85 probe.**

**Luật loại trùng:** probe nào trùng ý định một qid gold, kiểm bằng `intent_key`/fold, thì bị loại. `sb guards check` chạy kiểm này và in danh sách. Các trường hợp đã loại khi soạn:
- "vé Safari PQ" trùng c0472;
- "vé VW Nha Trang" trùng c0446;
- "resort golf Nam Hội An" trùng c0332;
- BMV→HAN trùng c0373;
- "vinpearl ha tinh" trùng c0324.

Các probe "homestay cat ba", "resort con dao", "can ho can tho" đã đối chiếu với gold. Cát Bà có c0153 (resort + spa), c0217 (chỗ nghỉ + wifi), c0277 (phòng ban công). Côn Đảo có c0097, c0187, c0220, c0241. Cần Thơ có c0223, c0284, c0546. Đều khác ý định.

### 4.2 Track L: 23 query mới có nhãn → `gold_v4`

**Cổng trước khi viết spec (bước 1, §9):** mọi số đếm trong bảng dưới được đếm lại bằng `guard_facts` với **tiện ích đã làm sạch**. Đặc biệt ở `amenity_negation`, số trong bảng đến từ matcher thô còn bug đảo nghĩa: pool, bar, spa nằm trong nhóm bị ảnh hưởng (V9). Câu nào sau khi đếm lại còn < 5 đáp án hoặc < 5 bẫy thì thay bằng câu do script chọn.

| Slice | Mới | Canonical (đếm thô, đếm lại ở bước 1) | `filter` gold | Nguồn nhãn 2 | Nguồn bẫy / hard-negative | Guard |
|---|---:|---|---|---|---|---|
| `amenity_negation` (có sẵn) | 8 | Sa Pa có spa, không hồ bơi (24/18); TP.HCM có đưa đón sân bay, không hồ bơi (37/16); Hội An có hồ bơi, không đưa đón (39/63); Đà Lạt có nhà hàng, không hồ bơi (37/12); Phú Quốc có hồ bơi, không nhà hàng (22/55); Huế có hồ bơi, không spa (16/27); Quy Nhơn có hồ bơi, không bar (14/41); +1 do script chọn. Không có điều kiện sao | `destination` + `variant`. Không đặt `not`, để pool vẫn lấy được bẫy; phủ định nằm ở sidecar | Pool dense ∪ BM25, depth 15 | KS cùng điểm đến **có ghi** tiện ích bị loại (facts sạch) → rule R-NEG = 0; holes từ arm | forbidden@k_eff, forbidden@3 thô, forbidden@10, required_hit@10 |
| `taxonomy_collision` (MỚI) | 5 | "khách sạn ở Grand World Phú Quốc" (8 KS / 19 vé / combo); "vé vui chơi Grand World Phú Quốc"; "vé lẻ VinWonders Nam Hội An, không lấy combo" (16 vé / 7 combo); "combo vé máy bay và khách sạn Đà Lạt" (6 combo / 9 tuyến vào Đà Lạt); "khách sạn Vinpearl ở Nha Trang" (7 KS theo brand / item VinWonders NT) | null, để pool lấy được item va chạm | Pool + inject đáp án đầy đủ | Item va chạm cùng điểm đến (inject). Với "vé lẻ… không combo" thì combo = 0 theo #10 | type_top1, type_purity@3, forbidden@k_eff |
| `flight_direction` (MỚI) | 6 | Explicit 3: "vé máy bay Sài Gòn đi Đà Nẵng" (ý định c0463, qid mới); "vé máy bay Cần Thơ đi Hà Nội" (2 sản phẩm trùng); "vé máy bay Côn Đảo về TP. Hồ Chí Minh" (không có chiều ngược). Partial 3: "vé máy bay đi Côn Đảo" (4 vào / 5 ra); "các chuyến bay xuất phát từ Cần Thơ" (10 ra / 7 vào); "vé máy bay đến Phú Quốc" (10 vào / 9 ra) | `variant = flight_route`; câu chỉ có điểm đến thì thêm `destination` | Pool + inject **toàn bộ** tuyến đúng từ `guard_facts` (sửa lỗi pool_miss của c0463) | Tuyến ngược, cùng gốc/đích, combo khứ hồi cùng cặp (inject); KS/vé từ holes | dir_top1, dir_order, forbidden@3 |
| `out_of_catalog` (có sẵn) | 4 | "khách sạn ở Lạng Sơn", "resort Bạc Liêu", "tour hồ Ba Bể", "homestay Tà Xùa" | null, `expected_no_result=true` | — | Mọi ứng viên = 0 (rule R-OOC; holes thì `auto_ooc`) | no_result_ok (chỉ arm có cutoff) |

**Tổng 23 qid.** `taxonomy_collision` có 5 câu và `flight_direction` có 6 câu, đều ≥ min_per_slice 3.

**Đã loại khỏi out_of_catalog** (kiểm 05/10). Theo quy ước #1, địa danh con thuộc tỉnh được tính là đúng nơi, nên các câu này có thể có nhãn 1/2:
- Măng Đen thuộc Kon Tum: destination có 16 item; ngoài ra "mang đến" khớp 712 mô tả.
- Hà Tiên thuộc Kiên Giang: 207 item.
- Lý Sơn thuộc Quảng Ngãi: 16 item theo tỉnh mới.
- Mù Cang Chải thuộc Lào Cai mới: 112 item.
- Hồ Tràm thuộc Bà Rịa–Vũng Tàu: 60 item.
- Bảo Lộc thuộc Lâm Đồng: 135 item.

Các câu "có trong catalog nhưng 0 khớp" (combo Sa Pa, golf Đà Lạt) cũng loại: theo #2, KS Sa Pa là "đúng nơi sai loại" = 1, không phải OOC. Bốn nơi được giữ có 0 khớp ở tên, địa chỉ, mô tả, và cả tỉnh cũ lẫn tỉnh mới.

**Không thêm câu `no_diacritics`/`abbrev_typo` có nhãn trước freeze.** Twin (§4.1) đã đo phần này. Holes theo dạng canonical để sau freeze (§14).

### 4.3 Ước lượng nhãn

| Hạng mục | Cặp | Quyết định người |
|---|---:|---:|
| Pool 23 câu (≈ 25/câu) | ≈ 575 | ≈ 310 (rule-0 ≈ 265: toàn bộ OOC, tuyến sai, R-NEG) |
| Câu chung để đo κ (5 câu, ≈ 25 cặp/câu, người gán cả hai phía) | +≈ 125 | +≈ 125 |
| Audit rule-0 (10 %, tối thiểu 5/slice) | — | ≈ 30 |
| Holes + inject sau import (B0, E2.e5, APP.hybrid_norm, cap 200) | ≈ 200 | ≈ 130 |
| **Tổng** | **≈ 900** | **≈ 600–650** (≤ cap 700 của D5a) |

---

## 5. Rubric và policy cục bộ: "Quy ước chốt 05/10" thêm vào `gold-guide.md`

**Nguyên tắc:**
- **Một rubric**: gold-guide + #1–#7 ngày 30/09.
- Quy ước mới chỉ áp cho qid tạo từ 05/10. Không sửa nhãn cũ.
- **[CHỜ CHỐT]** = khuyến nghị cần người dùng duyệt.
- **"luật mới"** = thay đổi so với #2, không phải làm rõ.

| # | Điểm (v4 §12) | Quy ước đề xuất | Căn cứ |
|---|---|---|---|
| 8 | Chuyến bay **[CHỜ CHỐT, luật mới ghi đè #2 cho câu bay]** | (a) Explicit A→B: chỉ tuyến A→B = 2, kể cả sản phẩm trùng tuyến (#7b). (b) Chỉ có điểm đến: mọi tuyến **vào** B = 2, tuyến ra = 0 (tiền lệ c0070: 16 vào = 2, 9 ra = 0). (c) Chỉ có điểm đi: đối xứng với (b). (d) Combo "Vé máy bay khứ hồi X - Y + Phòng …": = 1 nếu {X, Y} = {A, B} của câu (vé khứ hồi có chặng được hỏi); combo khác = 0. (e) KS / vé tham quan cho câu hỏi vé bay = 0 | Thực tế v3: combo theo chiều hỏi 9/9; item không phải chuyến bay = 0 ở 9/11 cặp (2 ngoại lệ là nhãn máy D4a). Cả 39 combo bay đều là khứ hồi nên cần (d) |
| 9 | Voucher vs tee-time **[CHỜ CHỐT]** | Coi là một loại golf. Sản phẩm `variant=golf` **có giá** ở đúng điểm đến = 2 cho "voucher / tee time / đặt sân / green fee". Sea Links (POI không giá) = 1 với cách nói giao dịch, = 2 với cách nói địa điểm ("sân golf Phan Thiết"). So theo `destination`, **không bao giờ theo `province`** | Catalog không có subtype; 3/6 sai tỉnh |
| 10 | Combo vs vé lẻ **[CHỜ CHỐT]** | Giữ ví dụ gold-guide: hỏi vé → combo chứa vé = 1; hỏi combo → vé lẻ thành phần = 1 (#2). **Loại trừ rõ** ("vé lẻ", "không lấy combo", "không phải Vinpearl", "không kèm X") là điều kiện bắt buộc: vi phạm = 0 (mở rộng #7a). Vé đa công viên kiểu "[02 ngày] VinWonders + Safari" chấm theo `variant` trong catalog (attraction) | gold-guide "vé VinWonders Phú Quốc → combo = 1" |
| 11 | Gần vs có (nearby vs included) **[CHỜ CHỐT, luật mới]** | "có X": X phải được **ghi nhận** trong danh sách tiện ích. Chuỗi bắt đầu bằng "Không có …" hoặc kết thúc bằng khoảng cách ("… 570 m", "… 1,8 km") **không** tính là ghi nhận. "gần X": nói rõ khoảng cách / vị trí trong tên, mô tả hoặc chuỗi khoảng cách = 2, không nói = 1. "Gần" không bao giờ là guard | Bug matcher (V9). #4 ngày 30/09 nói về amenity_offtaxonomy, không nói về "gần" |
| 12 | Property vs room | Không đổi: nhãn ở parent; hạng phòng chỉ qua `expected_children` (parent_child); chuyến bay gán nhãn ở cấp route | gold-guide "Slice parent_child", #7 |
| 13 | Ngoài catalog | Chỉ là OOC khi **không** sản phẩm nào có thể được 1/2 theo rubric, kể cả theo #1 với tên tỉnh cũ **và** mới (sau sáp nhập 2025). Ứng viên = 0 | Danh sách đã loại ở §4.2 |
| 14 | Phủ định khi thiếu metadata | "không ghi nhận" X vẫn = 2 nếu phần còn lại đúng (#3), xét trên tiện ích đã làm sạch. Không dùng phủ định trên `ocean_view`/`family_friendly` (dữ liệu không bao giờ có giá trị False), `property_type` (rỗng 64 %), elevator/wifi/golf/pets/smoking. "Phòng không hút thuốc", "không tiếp xúc" là **yêu cầu dương** | V9; dữ liệu 05/10 |
| — | Không có trạng thái "review" | Giữ luật "Không bỏ trống". Không chắc thì gán theo luật và ghi `unknown_metadata` vào `note` | `gold_schema.Label` = 0/1/2 |
| — | Sao, giá | Người không chấm giá. Sao là điều kiện mềm (contract §2.5): thiếu điều kiện sao = 1 | gold-guide, contract |

**Câu mơ hồ không đưa vào v4a:**
- QN (Quy Nhơn hay Quảng Ninh);
- Vũng Tàu / Côn Đảo;
- "sân golf Hạ Long";
- Phú Quý / Phú Quốc;
- "khách sạn Vinh".

---

## 6. Thay đổi schema và dữ liệu gold

### 6.1 Tương thích v3 và version

**Giữ nguyên:**
- `GoldRecord` **không đổi** (`extra="forbid"`); 132 dòng v3 giữ byte-identical. Mọi metadata v4 nằm ở sidecar.
- `gold_schema.SLICES`: chỉ nối `"taxonomy_collision", "flight_direction"` **vào cuối**. `split` lấy luồng RNG theo `SLICES.index`, nên golden test không đổi. Thực hiện theo T-doc-5.

**`config/sbench.yaml`:**
- `gold.slices` += `taxonomy_collision`, `flight_direction` (quota tham khảo, người dùng chọn).
- `tests/test_config.py:25` assert `sum(slices) == target (200)`, nên phải chỉnh `target` theo (người dùng chốt quota).
- Khối mới `hard_guards: {facts, specs, probes, manifest, sub_places, clean_amenities, cutoff_arms: [APP.dense, APP.hybrid, APP.hybrid_norm], win_block: {enforce: false}}`.
- `metrics.win_scope: gold_v3`.
- Khối `metrics.guards` cũ giữ nguyên. Nó vẫn chỉ được khai báo, không được thực thi (§7.3).

**Phương án dự phòng nếu không duyệt SLICES:** câu bay vào `named_entity` (như c0373), câu va chạm vào `dest_type` (như c0085/c0088), nhóm báo cáo lấy từ sidecar.

**Version:**
- Gold dùng tag `gold_v4` (người dùng tự chạy `git tag`).
- Spec và probe có `gold/guards/manifest.json {guards_version, sha256 từng file, snapshot, items_sha256}`.
  - Sửa spec sau khi tag thì tăng `guards_version` và rescore.
  - Không so sánh số giữa các version khác nhau.
- `results.json` ghi `guards_version` và `guards_sha256` cho **mọi** run và mọi lần rescore.
- Probe và spec được commit (đăng ký trước) **trước** khi chạy arm trên chúng.

### 6.2 Sidecar

**1. `gold/guards/specs_gold.jsonl` và `probes.jsonl`**, model `GuardSpec` (`extra="forbid"`). Các trường:
- `id`, `kind` (gold | probe), `text` (chỉ probe), `group`
- `allowed`, `allowed_variants`, `required`, `forbidden` (predicate), `route {origin, destination}`
- `expected_no_result_kind`, `equivalence_group`, `canonical_text`, `expected_parse` (để dành, N/A)
- `exceptions`: danh sách product_id có nhãn 2 cũ xung đột với guard, kèm lý do
- `label_policy`: danh sách id quy ước, ví dụ `["#8","#10"]`; không cho văn xuôi tự do
- `facts_quality`, `source`, `reviewed_by`, `note`

Ngôn ngữ predicate:
- Dùng AST của `store/filters.py`, mở rộng **chỉ cho guard**: thêm trường `origin_city`, `destination_city`, `city` và op `name_has` (token đã fold).
- Kiểm bằng `guards.validate`, không dùng `F.validate`, nên chấm gold không thể bị hỏng.

**2. `gold/annotations.jsonl`**: một dòng cho mỗi (qid, product_id) từ gold_v4 trở đi.
- Trường: `source` (human | rule | auto_ooc | llm), `rule_id`, `reason_codes`, `evidence`, `annotators`, `reviewed_by`, `guide_rev` (sha của `gold-guide.md`), `batch`.
- Ghi lúc `import --append` / `holes import`, lấy từ `provenance_X.csv`.
- Mục đích: giữ nguồn gốc máy hay người. `gold.jsonl` và changelog hiện làm mất thông tin này (D4a đếm 597 nhãn máy thành "human").

**3. `config/sub_places.yaml`** (người duyệt):
- Cát Bà ⊂ Hải Phòng; Mũi Né ⊂ Phan Thiết; Phong Nha ⊂ Quảng Bình; Vân Đồn ⊂ Hạ Long; Cửa Lò/Vinh ⊂ Nghệ An.
- Tên thành phố tuyến bay ↔ điểm đến KS: Điện Biên Phủ ↔ Điện Biên; Nghệ An (VII); Quảng Bình (VDH).

**4. `bench_out/search/data/guard_facts.parquet`** (dẫn xuất, không commit):
- Cột: `product_id, variant, destination, city, origin_city, destination_city, name_fold, amenity_ids_clean, unit_price_present, parent_product_id`.
- Meta: sha của snapshot + `items_sha256`. Lệch với `items.parquet` là lỗi cứng.
- `amenity_ids_clean`: chạy lại matcher trên `amenities_raw` sau khi bỏ chuỗi "Không có …" và chuỗi kết thúc bằng khoảng cách.

### 6.3 Ánh xạ trường schema v4 (§5/§12 checklist) vào thiết kế

| Trường v4 | Xử lý | Ghi chú |
|---|---|---|
| `canonical_text`, `equivalence_group` | `GuardSpec` | Twin dùng `equivalence_group` = qid |
| `expected_intent` | **Ánh xạ** thành `allowed_variants` (vertical/loại) + `allowed` (điểm đến/route) | Không giữ trường riêng: intent ở v4a chỉ gồm loại và nơi, đúng hai trường trên |
| `expected_parse` | Có chỗ trong `GuardSpec` nhưng N/A | Chờ `qu.py` (§14 #9) |
| `forbidden` | `GuardSpec.forbidden` (predicate + `product_ids`) | Không đặt trong filter gold |
| `label_policy` | `GuardSpec.label_policy` = danh sách id quy ước | Cấm văn xuôi |
| `annotation` | `gold/annotations.jsonl` | — |
| `query_variants` | **Để sau** (§14 #2). Trước freeze thay bằng probe twin | Luật một cách nói |
| `soft_preferences` | **Để sau** cùng `negation_soft` (§14 #5) | Chưa arm nào áp filter, nên "không loại oan" không đo được |
| Guard "Variant constraint pass ≥ 90–95 %" | **Không tính ở v4a.** Trên twin chỉ báo proxy không nhãn: `required_hit10` và `dest_share10` theo từng dạng. `VariantConstraintPass` thật cần constraint đã parse cho từng biến thể và cần variant chia nhãn, nên để sau cùng variant/family (§14 #2) | Twin không có filter gold |

### 6.4 Cột debug `per_query` (v4 §11)

| Cột v4 | Xử lý |
|---|---|
| Guard: `forbidden_ids_hit` (thay `forbidden_attribute_hit`), `dest_top1_ok`, `dest_share10`, `taxonomy_top1(_ok)`, `taxonomy_top3_purity`, `dir_top1_ok`, `dir_order_ok`, `no_result_ok`, `required_hit10` | **Làm** (C3), cả trong `per_query.parquet` và `probes.parquet` |
| `query_text`, `equivalence_group`, `form` | **Làm** cho `probes.parquet` |
| `query_rewritten` (một phần) | **Có sẵn** qua cột `extra` của APP: `normalizedQuery`, `corrections`, `appliedAliases`, `lexicalCount`, `lexicalCandidates`. C3 sửa để `rescore` **giữ** `extra` (hiện đang bỏ) |
| `filter_pass_rate` | **Có sẵn** dưới dạng `constraint_ok/constraint_n` |
| `retriever_sources`, `dense_rank`, `lexical_rank`, `fusion_score` | **Để sau** (§14 #11). Runner bench không giữ nội bộ fusion; adapter APP chỉ trả danh sách cuối |
| `intent`, `intent_confidence`, `parsed_filter`, `actual_parse` | **Để sau** cùng `qu.py` (§14 #9). Chưa arm nào phát parse |
| `cache_hit` | **Để sau** (§14 #11). `embedCache` chưa được chép vào `extra` |

---

## 7. Metric, guard và quy tắc WIN

### 7.1 Guard

Guard không phụ thuộc nhãn và rescore được từ `top_ids`.

| Guard | Định nghĩa | Phạm vi |
|---|---|---|
| `dest_top1_ok`, `dest_share10` | Top-1, hoặc tỉ lệ top-10, thuộc destination `allowed` (gồm địa danh con). `UNKNOWN`/null không tính vào mẫu | Spec có điểm đến. Câu bay dùng route thay vì guard này |
| `type_top1_ok`, `type_purity3` | `variant` thuộc `allowed_variants` | taxonomy; gold có spec loại |
| `forbidden_at_keff`, `forbidden_at3_raw`, `forbidden_at10` | Có item `forbidden` trong top-k. **k_eff = min(3, \|required\| trong catalog)**, đếm từ facts chứ không từ nhãn. Lý do: câu chỉ có 1–2 đáp án thì Forbidden@3 nguyên văn trượt chắc chắn, vì vị trí 2–3 buộc phải là item khác. Vẫn báo **Forbidden@3 thô** bên cạnh để đọc trực tiếp ngưỡng v4 | negation, exclusion, taxonomy, partial, route_absent |
| `dir_top1_ok`, `dir_order_ok` | Tuyến bay đầu tiên trong top-10 đúng A→B; tuyến đúng có mặt và không có tuyến ngược xếp trên nó | direction_explicit, c0373, Track L explicit |
| `required_hit10` | Có ít nhất 1 item thoả `required`. Chống lách bằng cách trả rỗng | Mọi spec trong catalog |
| `no_result_ok` | Danh sách rỗng | **Chỉ arm có cutoff**; B0/E2/_nocut ghi N/A |
| `robustness_gap` | dest_share10 / required_hit10 / type_top1 của twin so với qid gốc. Báo **theo từng dạng** (canonical vs biến thể), không trung bình gộp | robustness_twin |
| `qu_slot_match` | So với `expected_parse` | N/A cho tới khi có arm phát parse (`qu.py` chưa dựng) |

### 7.2 Báo cáo: bốn khối tách rời

1. **core-v3**: 131 qid, nhãn gold_v4.
   - Holes và inject đều bị giới hạn `--qids` vào 23 qid mới, nên gold_v4 **không** thêm nhãn nào cho qid v3.
   - Vì vậy số trên gold_v3 và gold_v4 ở khối này phải **giống hệt**. Đây là phép kiểm (chênh lệch phải bằng 0), không phải một cột so sánh.
   - Báo full + condensed + coverage. Dùng WIN rule hiện hành.
2. **v4a**: 23 qid mới.
   - Mô tả kèm n, CI và Judged@10.
   - Không dùng làm bằng chứng WIN: slice 4–8 câu có MDE 14–22 điểm.
3. **guards**:
   - Số query pass/fail kèm khoảng Wilson / Clopper–Pearson.
   - So sánh arm bằng **bảng sửa/hỏng (fix/break)** + McNemar exact trên các query đổi trạng thái.
4. **drift**: core-v3 có và không có 10 qid trong sổ trôi nhãn (c0059, c0078, c0088, c0253, c0372, c0433, c0446, c0456, c0460, c0472). Ghi rõ nếu verdict đổi.

### 7.3 WIN (người dùng chốt; mặc định chỉ báo cáo)

**Giữ nguyên `win_verdict`** (Δrecall ≥ 2, p < 0,05, max_slice_loss 3, tie 2), tính trên **`win_scope: gold_v3`**.

**Năm luật WIN bổ sung của v4 §7**, từng luật một:

| Luật v4 | Xử lý | Lý do |
|---|---|---|
| Forbidden@10 tăng | **Thay bằng** bảng fix/break trên danh sách must-pass (khuyến nghị bên dưới); trước T6 chỉ báo cáo | "Tăng" thô không có kiểm định; arm APP có nhiễu HNSW |
| Direction < 100 % | **Cổng phát hành tuyệt đối** RED/GREEN, không chặn WIN; trong WIN chỉ xét `dir_order` hỏng ròng trên must-pass | Mọi arm hiện tại đều trượt c0373 |
| nDCG slice an toàn giảm > 3 | **Đã có sẵn** qua `max_slice_loss = 3` trên slice của `win_scope: gold_v3`. Slice mới chỉ báo cáo | Slice mới quá nhỏ (MDE 14–22) |
| Filter pass rate giảm > 1 điểm | **Để sau / không áp dụng ở v4a.** Chỉ báo Δ`constraint_precision` | Không arm nào áp filter: `applied_filter` null, filter pass 0,44–0,57 ở mọi arm, nên luật đo nhiễu thay vì hành vi lọc. Xem lại khi có arm S3/S4 |
| Query trong catalog trả rỗng vượt ngưỡng hiện hành | **Chỉ báo cáo.** `zero_result_in_catalog_max: 0.02` có trong `sbench.yaml` nhưng khối `metrics.guards` **chưa bao giờ được thực thi** (không có `select()` hay `report.py`). In cột này trong bảng guard; bật chặn là quyết định D7 | Spec §1.7 #1. APP.dense 16,4 %, hybrid 15,6 %, hybrid_norm 7,0 % đều vượt 2 %, nên bật ngay sẽ chặn mọi arm APP |

**Khuyến nghị để người dùng chọn**, ghi vào `hard_guards.win_block`:
- BLOCKED khi **break − fix > 0** trên một danh sách **must-pass** đã chốt (các probe/qid mà arm cha đang pass), áp cho `dir_order`, `forbidden_at_keff`, `type_top1`.
- BLOCKED khi `dest_top1` hỏng ròng có McNemar p < 0,05.
- `no_result_ok` chỉ áp cho arm có cutoff.
- Arm APP dùng HNSW (`app_adapter.py:11`) nên có nhiễu ANN: một lần lật đơn lẻ chỉ được tính khi lặp lại ở lần chạy thứ hai.

**Cổng phát hành tuyệt đối:** direction 100 %, Forbidden@3 0 %, Top-1 type ≥ 98 %, no-result 100 % cho arm có cutoff. Chỉ báo RED/GREEN, không chặn. Dự kiến mọi arm hiện tại đều RED, và đó là một phát hiện.

**Báo cho người dùng:** `max_slice_loss = 3` chặn khoảng 97,5 % khi hai arm như nhau. Thay bằng non-inferiority theo nhóm quyết định, bootstrap theo family, là quyết định sau v4a.

---

## 8. Thay đổi code (`src/evaluation/search_bench/`) theo thứ tự phụ thuộc

| # | File | Thay đổi | Cỡ | Test |
|---|---|---|---|---|
| C0 | `gold_schema.py`, `config/sbench.yaml`, `config.py`, `tests/test_config.py`, `tests/test_gold.py` | Nối SLICES (sau T-doc-5); slices/target; `hard_guards`; `win_scope` | S | Golden `gold_small` không đổi; split không đổi |
| C1 | `guard_facts.py` (mới) + `sb guards facts` | Dựng facts từ snapshot thô (originCity/destinationCity) + tiện ích sạch | S | `tests/test_guard_facts.py`: chuỗi "Không có Thang máy" và "Spa … 90 m" không sinh tiện ích; 113 route đủ hai đầu |
| C2 | `guards.py` (mới) | `GuardSpec`; validate/mask (whitelist mở rộng + `name_has`); metric từng query; gộp theo nhóm; `compare_guards` (fix/break + McNemar); `check_specs` (gồm kiểm trùng `intent_key` giữa probe và gold) | M | `tests/test_guards.py` (danh sách bên dưới) |
| C3 | `runner.py`, `metrics.py`, `__main__.py` | Chạy probe → `probes.parquet`; cột guard trong `per_query` (§6.4); `rescore` tính lại guard và **giữ cột `extra`**; `sb compare` in 3 bảng (ranking / guard / QU) + lọc `win_scope`; BLOCKED chỉ khi `enforce: true` | M | Rescore run `20261001-0623-ec5fbd2` cho đúng metric ranking cũ, có thêm khối guard |
| C4 | `gold.py`, `__main__.py` | `sb gold import --append --meta gold/v4a/pool_meta.json` (chi tiết bên dưới) | M | `tests/test_gold_append.py` |
| C5 | `rule_prelabel.py` (mới) + `sb gold rule-prelabel` | Sinh JSON cho `machine-import`, **chỉ nhãn 0** (chi tiết bên dưới) | S | `tests/test_rule_prelabel.py`: không bao giờ ra 1/2; câu chỉ có điểm đi; địa danh con; combo khứ hồi được miễn |
| C6 | `holes.py`, `__main__.py` | `sb gold inject --pairs <csv> --tag T` → thư mục định dạng holes (dùng lại `hole_rows`/`write_holes`, `meta.csv arms=inject:<rule>`); `sb gold holes --qids/--slice` để cap không bị loãng; ghi `guide_rev` | S | `tests/test_inject.py` |
| C7 | `gold.py` (`kappa`) | Thêm κ theo ranh giới (0 vs ≥1, trong {1,2}), theo slice, phần dư cùng điểm đến, p_o, Gwet AC1 | S | test với fixture |
| C8 | `tools/gen_guard_specs.py` (mới) | Nháp spec v3 (gazetteer) + nháp probe từ mẫu catalog. Đầu ra là **nháp**, chờ người duyệt | M | — |

**Test của C2** (`tests/test_guards.py`):
- tuyến ngược ở #1 → fail; tuyến ngược xếp dưới tuyến đúng → pass;
- danh sách rỗng → top-1 fail, required fail;
- địa danh con được tính đúng;
- loại `UNKNOWN` khỏi mẫu;
- từ chối forbidden rỗng; từ chối key không sạch;
- `exceptions` hoạt động;
- phát hiện probe trùng ý định.

**Chi tiết C4** (`import --append`):
- chỉ dựng record cho qid mới; từ chối qid trùng;
- **từ chối dòng máy chưa duyệt** trong `provenance_X.csv`;
- chạy `verify_append` với tag cuối;
- changelog `action: import_append` có `new_labels_by_source {human, rule, auto_ooc}`;
- ghi `annotations.jsonl`.

**Chi tiết C5** (`rule-prelabel`):
- Đầu ra cho `machine-import`: **chỉ nhãn 0**, `model="rule:v4a@<sha>"`, note = mã lý do + bằng chứng.
- Mỗi rule **lấy từ spec đã duyệt của chính query** (`allowed`/`required`/`forbidden`), không dùng một luật điểm đến chung. Lý do: luật chung sẽ đảo ngược câu "từ Cần Thơ", vì đáp án đúng có destination ≠ Cần Thơ.
- Mã rule: R-DEST, R-ROUTE, R-FLIGHT-OTHER, R-NEG, R-EXCL, R-OOC.
- Câu chung bị `machine-import` từ chối sẵn.

**Không đụng:**
- `catalog.py`, `store/filters.py`, `store/weaviate_store.py`, YAML arm, backend.
- `streamlit_app.py`: giữ gán nhãn mù. Sửa file này khi app gán nhãn đang chạy sẽ làm app crash.

**Thứ tự:**
- Track G: C0 → C1 → C2 → C3.
- Track L (song song): C4 → C5 → C6.
- Cuối cùng: C7.
- **C4, C5 làm từ tối T2**, để mốc T3 12:00 có cả điều kiện "C4/C5 xanh".

**Kiểm:** `pytest src/evaluation/search_bench/tests` xanh; độ phủ `guards.py` ≥ 80 %.

---

## 9. Quy trình gán nhãn (Track L)

**Môi trường:** lệnh chạy từ `src/`, `sb` = `../.venv-sbench/Scripts/python -m evaluation.search_bench`, đặt `PYTHONUTF8=1`.

**Bước 1. Spec trước pool.**
- **Cổng đếm lại:**
  - `sb guards facts` phải chạy xong trước.
  - Mọi số đáp án/bẫy của 23 câu được đếm lại trên `amenity_ids_clean` và route facts.
  - Câu `amenity_negation` nào dưới ngưỡng (≥ 5 / ≥ 5) thì thay trước khi viết nháp.
- Dev nháp `gold/v4a/drafts.txt` + `gold/v4a/drafts_raw.tsv` và dòng spec sidecar:
  - case_id bắt đầu từ **c0673**, theo `draft_authoring.next_block_start`;
  - `source_refs` = id bằng chứng.
- **Không** dùng app để soát nháp: app ghi đè `gold/drafts.txt` của v1. Nếu buộc phải dùng, trỏ `SBENCH_GOLD_DIR` sang bản sao.
- Lead duyệt spec. Tốt nhất là người không gán nhãn câu đó.
- Commit spec + `manifest.json` (đăng ký trước).

**Bước 2. Pool.**
- Lệnh: `sb gold pool --drafts gold/v4a/drafts.txt --raw gold/v4a/drafts_raw.tsv --out gold/v4a/pool.csv --arm B0` (depth 15).
- Không có key Cohere thì dùng `--arm E2.e5`. Khi đó collection pool đổi từ `products__T3+R__cohere_v3` (collection của gold_v1) sang e5-base. Phải ghi việc này vào `pool_meta` và vào caveat của report như một **nguồn thiên lệch pool**.
- Script kiểm trước khi split: mỗi câu trong catalog có ≥ 1 item `required` trong pool. Thiếu thì tăng `--depth` cho đợt đó hoặc sửa nháp.

**Bước 3. Split.**
- Lệnh: `sb gold split --pool gold/v4a/pool.csv --overlap 5 --out-dir gold/v4a`.
- Khoảng 1 câu chung mỗi slice; κ tính trên mọi cặp chung.
- Câu chung **không có nhãn máy** (gold-guide 29/09): hai người gán toàn bộ.

**Bước 4. Rule prelabel.**
- Dừng app gán nhãn dùng chung (port 8502).
- `sb gold rule-prelabel --meta gold/v4a/pool_meta.json` → `sb gold machine-import … --model rule:v4a@<sha>`.

**Bước 5. Gán nhãn người.**
- A1 và A2 gán trong app, ở chế độ mù (không thấy rank của arm).
- Nhãn rule-0 xem theo từng câu: lọc "Có nhãn máy chưa duyệt", đọc lý do.
- **Audit độc lập:** người kia tick ngẫu nhiên 10 % dòng rule-0 của mỗi slice (tối thiểu 5). Gặp sai có tính hệ thống thì dừng, sửa rule, chạy lại.

**Bước 6. Chính sách nhãn máy** (chi tiết và phần lệch v4: §9.3).
- Không dùng LLM pre-label cho 1/2.
- Chỉ rule-0 có bằng chứng catalog mới được auto-final.
- **Không** auto-final rule-0 cho item nằm top-3 của bất kỳ arm nào trong holes: người xác nhận, khoảng 5 s/cặp.

**Bước 7. κ, merge, import.**
- `sb gold kappa --meta gold/v4a/pool_meta.json`.
- Gate: κ_lin ≥ 0,6 trên mọi cặp chung; lệch 2 bậc ≤ 3 %.
- Báo thêm, không gate: κ phần dư, AC1, p_o theo slice. Mốc v1 phần dư: κ_lin 0,388, p_o 0,797, n = 468.
- Không đạt gate thì dừng, sửa guide, gán lại phần của người.
- Chuỗi lệnh: `sb gold merge` → xử lý `needs_discussion` → `sb gold import --append --meta gold/v4a/pool_meta.json --provenance pool@gold_v4` → `sb gold check` → `sb gold verify-append gold_v3` → `sb guards check`.
- Commit, chưa tag.

**Bước 8. Holes + inject** (bắt buộc trước khi tag).
- Chạy run lấy holes: `sb --run-id 20261007-v4a-holes run --arm B0 --arm E2.e5 --arm APP.hybrid_norm --allow-untagged`. Kết quả run này không được trích dẫn.
- Gold lúc này chưa tag, nên `gold_version_of` trả `None`:
  - thư mục mặc định là `gold/holes/untagged__D8a/`;
  - `holes import` mặc định lấy version "tag mới nhất + 1" = `gold_v4`;
  - plan vẫn **ghi rõ** `--out-dir gold/holes/gold_v4__D8a` và `--version gold_v4` để tên thư mục và provenance không phụ thuộc mặc định.
- `sb gold holes --arms B0,E2.e5,APP.hybrid_norm --qids <23 qid mới> --tag D8a --cap 200 --split --out-dir gold/holes/gold_v4__D8a`. OOC tự thành `auto_ooc`.
- `sb gold inject --pairs gold/v4a/inject.csv --tag D8i --out-dir gold/holes/gold_v4__D8i`. Nội dung inject: toàn bộ tuyến đúng, tuyến ngược, combo khứ hồi cùng cặp, đáp án Grand World / VinWonders còn thiếu.
- Rule prelabel → machine-import → người gán → `sb gold holes import gold/holes/gold_v4__D8a --version gold_v4`, tương tự cho D8i.

**Bước 9. Tag.**
- Điều kiện: `gold check`, `verify-append gold_v3`, `guards check` đều PASS, và Judged@10 khối v4a ≥ 0,70 cho 3 arm đã pool.
- **Người dùng chạy `git tag gold_v4`.**

### 9.1 Nguồn pool và cỡ pool của v4 §8.3: xử lý từng mục

| Mục v4 §8.3 | Xử lý | Lý do |
|---|---|---|
| Dense, BM25 | Dùng (`sb gold pool`) | Có sẵn |
| Arm hiện có (holes) | Dùng (B0, E2.e5, APP.hybrid_norm) | Có sẵn |
| Lexical có dấu, trigram/fuzzy, alias-expanded lexical, filter-first QU, LLM rewrite | **Không làm** (spec §1.7 #5: không arm mới) | Để sau (§14 #4, #9) |
| Ứng viên bẫy / chiều ngược | Dùng qua **inject** | Không phải arm |
| **Random sample có điều kiện cùng destination/taxonomy** | **Để sau** (§14 #12) | Đi qua inject được, nhưng thêm quyết định người có kỳ vọng liên quan thấp và vượt cap 700. Giá trị chính của nó là ước lượng độ đầy đủ của pool (sampled recall), nên làm sau freeze khi có ngân sách |
| **Cỡ pool mục tiêu 20–40 (bay/OOC) đến 45–70 (typo/taxonomy)** | **Không dùng làm mục tiêu.** Pool khoảng 25/câu ở depth 15, cộng holes và inject | Tiêu chí đủ là Judged@10 ≥ 0,70 theo slice và required ∈ pool, không phải cỡ pool. Inject đã gom toàn bộ đáp án và bẫy đã biết cho câu bay/taxonomy. Cỡ 45–70 nhân 23 câu vượt cap 700 |

### 9.2 Trạng thái rule của v4 §8.4 ánh xạ vào thiết kế

| Trạng thái v4 | Xử lý |
|---|---|
| `hard_fail` | Rule phát **nhãn 0** (chỉ trạng thái này có đầu ra) |
| `hard_pass` | Không phát nhãn; người gán |
| `partial_match` | Không phát nhãn; người gán |
| `unknown_metadata` | Không có trạng thái riêng. Người gán theo luật, ghi `unknown_metadata` vào `note`. Guard loại null/UNKNOWN khỏi mẫu |
| `not_in_scope` | Không phát nhãn |
| `confidence` | **Không lưu**: rule là tất định. Bằng chứng nằm ở `evidence` và `reason_codes` |

### 9.3 Lệch có chủ đích so với v4 §8.6 #4–#6, §10, §13 #4 (người dùng chốt ở D5/D6)

**v4 yêu cầu:**
- double-label **100 %** ở batch đầu cho negation hard, taxonomy collision, flight direction;
- người chốt top-k/hole và slice an toàn.

**Plan làm khác:**
- auto-final rule-0 trong pool, holes, inject và cả slice an toàn (`amenity_negation`, `taxonomy_collision`, `flight_direction`), trừ item nằm top-3 của arm;
- chỉ 5 câu chung (khoảng 1 câu mỗi slice) được double-label toàn bộ.

**Lý do:**
1. **Sức người.** Double-label 100 % ba slice an toàn (19 câu × khoảng 25 cặp × 2 người ≈ 950) đã vượt cap 700, chưa tính holes.
2. **Công cụ.** `machine-import` từ chối câu chung (`labeling_core.py:357`). Câu đặt 100 % chung thì không ghi được rule-0, nên người phải gán tay mọi cặp, kể cả các cặp OOC / tuyến sai hiển nhiên.
3. **Thống kê.** Đưa các cặp rule-0 hiển nhiên vào κ làm κ phồng lên. Plan đo κ trên câu chung do người gán hoàn toàn và báo thêm κ phần dư.
4. **Rủi ro.** Đã được giảm bằng 3 lớp:
   - rule lấy từ spec đã duyệt của từng câu;
   - audit 10 % (tối thiểu 5/slice), có luật dừng;
   - item top-3 của bất kỳ arm nào luôn được người xác nhận.

**Phương án người dùng có thể chọn thay:**
- (a) double-label 100 % **phần quyết định của người** (không gồm rule-0) cho batch đầu của 3 slice an toàn, khoảng +150 quyết định;
- (b) chuyển cả 3 slice an toàn thành câu chung, rồi chuyển Track L sang sau freeze.

### QA

**`sb guards check`:**
- spec hợp lệ;
- forbidden ≥ 1 item; required ≥ 1 (trừ no_result); required ∩ forbidden = ∅;
- điểm đến / thành phố có trong facts; không dùng key không sạch;
- probe không trùng ý định với qid gold (kiểm `intent_key`; twin `equivalence_group` được miễn);
- **forbidden ∩ nhãn-2 cũ → cảnh báo**, kèm `exceptions` có lý do. Không đặt thành lỗi, vì gold cũ đã có:
  - c0244: 5 nhãn 2 có ghi bếp;
  - c0247;
  - 7 câu có nhãn 2 ở điểm đến khác: c0147, c0178, c0394, c0409, c0439, c0469, c0481;
- required ∩ nhãn-0 → cảnh báo.

**Kiểm khác:**
- Nhất quán: trong một qid mới, cùng (variant, quan hệ điểm đến) phải cùng nhãn; liệt kê ngoại lệ.
- Chạy guard hai lần phải cho kết quả giống hệt.

---

## 10. Lịch thực hiện

**Vai trò:**
- **Lead** = người dùng
- **A1** = QAnh
- **A2** = Khoi (chờ xác nhận)
- **Dev** = phiên Claude (A1 duyệt PR)

| Ngày | Lead | A1 | A2 | Dev |
|---|---|---|---|---|
| **T2 05/10 (Day 6), chiều – tối** | Cổng G0 (45 phút): chốt §12 | — | — | T-doc-1..8 (nếu được duyệt), plan + history; C1, C2 + test; nháp `specs_gold.jsonl`; **tối: C4, C5 + test** |
| **T3 06/10 (Day 7)** | 12:00 **mốc quyết định** Track L. Điều kiện: D2, D3, D5, D6 đã chốt **và** C4/C5 xanh. Duyệt spec Track L (1 h) | Duyệt spec v3 (1,5 h) + nửa số probe (1,5 h) | Duyệt nửa còn lại của probe (1,5 h) | C3 (nối Track G vào runner/compare); C0 trên trunk → merge; Track L bước 1–4; chạy probe cho B0, E2.e5, APP.* (cần key Cohere cho query mới); rescore run có trên máy; report `eval-2026-10-06-search-guards-v1.md` |
| **T4 07/10 (Day 8)** | 12:00 go/no-go Track L; 18:00 tag `gold_v4` nếu đủ điều kiện | Sáng gán pool (≈ 2 h); chiều gán holes (≈ 1 h) | Như A1 | C6, C7; κ / merge / import; holes + inject; chạy trên gold_v4; `eval-2026-10-07-search-gold-v4.md`; cập nhật `search-gold-summary.md` và spec Part 5/8/11 |
| **T5 08/10 (Day 9), freeze** | Ký duyệt | — | — | Không đổi gold/guard sau khi tag; regression baseline có khối guard |
| **T6 09/10 (Day 10)** | Đọc report cuối | — | — | Sinh lại mọi số từ tag (gold_v4, hoặc gold_v3 + guards_v1) → `eval-2026-10-09-search-final-gold-v4.md` |

**Mốc cắt:**
- Trước **T3 12:00** mà chưa chốt D2/D3/D5/D6, chưa xanh C4/C5, hoặc **không có A2**: Track L chuyển sang sau freeze. Track G vẫn giao, đóng băng bằng `manifest.json` trong tag phát hành.
- Track L chưa tag trước **T4 18:00**: số T6 dùng gold_v3. v4a tiếp tục sau freeze, ghi là "post-freeze".

**Chống rò rỉ khi tune:**
- Probe và 23 qid mới **không** được dùng để tune S-sweep / `qu.py` trước freeze.
- S-sweep chạy trên gold_v3; việc chia dev/test vẫn còn mở.
- Report ghi rõ: query v4a được chọn **vì arm đang thua**, nên có thiên lệch chọn mẫu và hồi quy về trung bình.

**Giới hạn máy:**
- Chỉ có vector tài liệu cohere-v3 và e5-base. E2.e5s / bge / gte / e5L cần embed lại + `sb load`, làm khi còn CPU hoặc sau freeze.
- Thư mục run Day-4/5 không có trên máy này. Chỉ rescore được `20261001-0623-ec5fbd2` (B0, E2.e5) và `preview-0930` (APP code cũ; không trích dẫn).

---

## 11. Definition of Done / tiêu chí nghiệm thu

**Track G (bắt buộc trước freeze)**
1. `sb guards facts` + `sb guards check` xanh. Cảnh báo xung đột được liệt kê và có `exceptions`; 0 probe trùng ý định gold ngoài twin. `manifest.json` đã commit.
2. `pytest src/evaluation/search_bench/tests` xanh (test mới cho guard_facts, guards + test cũ). Golden `gold_small` không đổi. Độ phủ `guards.py` ≥ 80 %.
3. Khối guard có trong `results.json` của run mới **và** của run rescore. `sb compare` in 3 bảng tách rời. WIN không đổi (BLOCKED chỉ khi `enforce: true`).
4. Report `src/evaluation/reports/eval-2026-10-06-search-guards-v1.md` gồm:
   - commit, run id, `gold_version`, `guards_version`, cấu hình arm;
   - bảng chép nguyên văn từ output;
   - caveat: HNSW, probe chọn theo lỗi, arm thiếu, collection pool;
   - lệnh tái sinh.

**Track L (nếu không bị cắt)**

5. Tag `gold_v4` tồn tại, với:
   - `sb gold check` PASS: 154 qid active, 15 slice, mỗi slice ≥ 3, mỗi câu trong catalog ≥ 1 nhãn 2, câu OOC toàn 0;
   - `verify-append gold_v3` PASS: +23 qid, 0 nhãn cũ đổi;
   - `annotations.jsonl` có nguồn cho mọi nhãn mới;
   - changelog đếm theo nguồn.
6. κ_lin ≥ 0,6 trên cặp chung. Có bảng κ theo ranh giới / slice / phần dư. Audit rule-0 có số lỗi và cận trên 95 %.
7. Judged@10 khối v4a ≥ 0,70 theo slice cho B0, E2.e5, APP.hybrid_norm. Arm khác báo NEEDS_LABELS + condensed + tỉ lệ giữ lại.
8. Run trên gold_v4 là run mới (rescore không chấm được qid mới). Report `eval-2026-10-07-search-gold-v4.md` gồm 4 khối của §7.2; khối core-v3 kiểm chênh lệch gold_v3 / gold_v4 = 0. `search-gold-summary.md` cập nhật hồ sơ gold_v4.

**Chung**

9. Tài liệu:
   - plan này;
   - spec v4 đã đổi tên (dòng FR, header trạng thái, §1 viết lại, mục đề xuất SLICES);
   - `search-guards.md`;
   - `gold-guide.md`: "Quy ước chốt 05/10";
   - `search-eval-local-spec.md`: Part 5 (`import --append`, `inject`, `rule-prelabel`), §1.7 #4 (thêm writer `import --append`), Part 8 (guard, `win_scope`, 4 khối, xử lý 5 luật WIN v4), Part 11 (inject, version sidecar);
   - `arms.md`, README bench.
10. Mỗi task có entry `history/` (đối chiếu `git status`) trong cùng commit.
11. Không đổi `src/backend`, `src/frontend`, `src/shared/contracts`, `db/`, nên không cần `validate_contract.py`.

---

## 12. Việc cần người dùng chốt (cổng G0)

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| D1 | Rubric: một rubric (gold-guide + 30/09 + 05/10), độ chặt về loại chuyển thành guard? Hay rubric v4 chặt cho qid mới, báo riêng? | Một rubric |
| D2 | Phạm vi và hạn: Track G trước freeze + Track L 23 câu, tag gold_v4 trước T4 18:00 (mốc cắt T3 12:00)? | Có |
| D3 | Nối SLICES `taxonomy_collision`, `flight_direction` (đề xuất ghi trong spec, commit trên `bench_search_recomSys`), kèm quota và `target` mới? | Có. Dự phòng: dùng slice cũ + nhóm sidecar |
| D4 | Quy ước #8–#14, nhất là #8 (ghi đè #2 cho câu bay), #8d (combo khứ hồi), #11 ("gần") | Duyệt như §5 |
| D5 | Người gán: A1 QAnh, A2 Khoi; 5 câu chung. **Chấp nhận lệch v4 §10** (không double-label 100 % batch đầu của slice an toàn, §9.3) hay chọn (a) double-label 100 % phần quyết định người (+≈150) hay (b) toàn slice an toàn thành câu chung (Track L sau freeze)? Không có A2 thì sao? | 5 câu chung + chấp nhận lệch; không có A2 thì Track L sau freeze |
| D6 | Nhãn máy: auto-final rule-0 có audit 10 % và **cả ở holes / inject / slice an toàn**, trừ item top-3 (lệch v4 §8.6 #4–#6 và §13 #4, §9.3). Không dùng LLM cho 1/2 trong v4a? | Có |
| D7 | Guard và luật WIN: chỉ báo cáo tới T6; `win_scope: gold_v3`. Xác nhận cách xử lý 5 luật WIN của v4 (§7.3): Forbidden@10 → fix/break; direction → cổng phát hành; nDCG slice an toàn → `max_slice_loss`; **filter pass −1 điểm → để sau** (không arm nào lọc, pass 0,44–0,57); **zero_result_in_catalog_max 0.02 → chỉ báo cáo** (khối guards chưa thực thi; APP 7–16 %). Luật chặn fix/break + must-pass chốt sau | Có |
| D8 | Đổi tên và sửa đầu file spec v4 (T-doc-1..4) | Cho phép |
| D9 | Sổ trôi nhãn (10 qid): giữ và báo có/không; hay retire + làm query lại sau freeze? | Giữ, báo độ nhạy |
| D10 | Câu bay: giữ mức chẩn đoán (6 câu có nhãn + 36 probe), vì FR-SRC-03 không đưa vé bay vào `/search`? Itinerary agent có dùng search cho vé bay không? | Giữ chẩn đoán; người dùng xác nhận ai dùng tín hiệu này |
| D11 | Bug dữ liệu (đảo nghĩa tiện ích, tỉnh golf, Vinpearl Hà Tĩnh trùng) sửa sau freeze? Việc sửa cần `catalog build --allow-id-drift` và nạp lại | Sau freeze |
| D12 | Xác nhận không đổi `/search` production (filter-first, vé bay trong /search, trang rỗng, sao cứng) | Xác nhận; muốn đổi thì đi qua `docs/prd/update/` |

---

## 13. Rủi ro và giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Trễ, đè lên việc Track A Day 6–8 | Hai track; Track G độc lập; C4/C5 làm từ tối T2; mốc cắt T3 12:00 phụ thuộc C4/C5 xanh; go/no-go T4; dự phòng gold_v3 |
| Một người làm nhiều vai (A1 vừa duyệt vừa gán) | Dev là phiên Claude; spec Track L do Lead duyệt; app không hiện spec cho người gán |
| Trôi nhãn giữa các đợt (bài học 29/09, D4a/D5a) | Viết quy ước trước; `guide_rev`; dừng khi κ < 0,6; không LLM cho 1/2; kiểm nhất quán |
| Rule-0 sai (địa danh con, câu chỉ có điểm đi, bug tiện ích) | Rule theo spec từng câu; `sub_places.yaml`; facts sạch; audit; item top-3 do người xác nhận |
| Lệch v4 §10 (ít double-label) che sai sót ở slice an toàn | 3 lớp ở §9.3; phương án (a) nếu người dùng muốn chặt hơn |
| Guard mã hoá sai policy hoặc xung đột gold cũ | Người duyệt 100 %; `exceptions`; version + rescore |
| Probe trùng ý định gold | Kiểm `intent_key` trong `guards check`; đã loại BMV→HAN, "vinpearl ha tinh" |
| Lách guard bằng cách trả rỗng | `required_hit10`; danh sách rỗng thì top-1 fail |
| Nhiễu HNSW ở arm APP | Lật đơn phải lặp lại mới tính; báo kèm caveat |
| Thiếu key Cohere / Weaviate bench / vector model khác | Pool `--arm E2.e5` (ghi đổi collection là thiên lệch pool); đánh dấu arm thiếu; không chặn |
| Pool thiếu đáp án bay (như c0463) | Lọc `variant=flight_route`; kiểm required có trong pool; inject toàn bộ tuyến đúng |
| Slice nhỏ nên delta nhiễu | WIN chỉ tính trên gold_v3; khối v4a chỉ mô tả; guard theo số đếm + McNemar |
| Hạ tầng dùng chung (worktree TRP-release, Streamlit hot-reload) | Không sửa `streamlit_app.py`; dừng app trước machine-import; không dùng `make demo-db*` |
| Rò rỉ khi tune | Probe và qid mới không dùng để tune trước freeze; đăng ký trước bằng commit |

---

## 14. Lộ trình dài hạn (gold_v5+, sau freeze)

1. **gold_v5: holes theo dạng canonical** cho 12 `no_diacritics` + 12 `abbrev_typo`.
   - Hiện chỉ 0,39 kết quả có dấu đã được chấm, nên một normalizer đúng cũng chỉ đạt khoảng 0,33 nDCG full.
   - Batch tag riêng. Báo core-v3 trước/sau. Bỏ các qid trong sổ trôi khỏi đợt này.
2. **Variant/family:**
   - `query_variants` trong sidecar; runner mở rộng dòng `qid~vN` dùng chung nhãn; holes riêng cho biến thể;
   - gộp theo `equivalence_group`; bootstrap theo family (n_eff ≈ 1,4–1,8/family với ρ ≈ 0,4); báo theo từng dạng;
   - **`VariantConstraintPass`** tính ở đây.
3. **Mở rộng taxonomy_collision** (VinWonders/Safari vé ↔ combo, POI ↔ vé, "Voucher ẩm thực") tới khoảng 18–22 ý định mà catalog đỡ được. Báo theo họ va chạm.
4. **Sửa dữ liệu và mở rộng nguồn pool:**
   - sửa đảo nghĩa tiện ích, tỉnh golf, Vinpearl Hà Tĩnh trùng;
   - thêm `origin_city`/`property_type` vào items / DSL / Weaviate cho arm filter-first S3/S4 (phải nạp lại mọi collection);
   - nguồn pool trigram / alias lexical / lexical có dấu khi được đăng ký thành arm.
5. **`negation_soft` + `soft_preferences`, `mixed_constraints`, luật "filter pass −1 điểm"**: chờ có arm áp filter. Hiện `applied_filter` null, filter pass 0,44–0,57 ở mọi arm.
6. **LLM pre-label:**
   - thêm `confidence`/`reason_codes` vào `PROV_COLUMNS`, cổng duyệt trong merge, tập mù + test–retest;
   - chỉ cho bulk-accept theo slice khi κ(LLM, người) ≥ κ(A, B) − 0,05;
   - cần người dùng cho phép lại (luật 30/09 "Claude không gán máy cho hole").
7. **Chia dev/test theo family**, phân tầng theo slice. Tập gate không dùng để tune.
8. **Luật WIN non-inferiority** theo nhóm quyết định (robustness / constraint / vertical-route / no-result, mỗi nhóm ≥ 25 family) thay cho `max_slice_loss = 3`. Cân nhắc bật chặn `zero_result_in_catalog_max` khi đã có `select()`.
9. **Metric QU** khi `qu.py` phát parse: `intent`, `intent_confidence`, `parsed_filter`, `actual_parse`, `qu_slot_match`.
10. **Double-label 100 % theo v4 §10** cho slice an toàn khi có thêm người / ngân sách.
11. **Cột debug còn lại:** `retriever_sources`, `dense_rank`, `lexical_rank`, `fusion_score` (cần adapter APP trả nội bộ fusion), `cache_hit` (chép `embedCache` vào `extra`).
12. **Random sample có điều kiện** (cùng destination/taxonomy) qua inject, để ước lượng độ đầy đủ của pool.
13. **Đích dài hạn** theo v4 §9.3: 240–300 ý định canonical, 10–15k nhãn, 2,5–4,5k nhãn người.

---

## 15. Đánh giá lệch PRD

**Không lệch PRD; không cần đề xuất `docs/prd/update/`.**
- Gold, sidecar, guard, probe, rule-prelabel và version là công cụ đánh giá cho FR-SRC-01/03/04, AC-SRC-01, test-plan §2.5.
- PRD không đặt ngưỡng số cho chất lượng search. Ngưỡng guard/WIN là cấu hình bench do người dùng chọn (spec §1.5, §1.7 #1).

**Cổng nội bộ bench** (không phải PRD), cần người dùng duyệt:
- đề xuất ghi tay cho `gold_schema.SLICES`;
- quota và `target`;
- writer mới `import --append` / `inject` phải được ghi vào spec §1.7 #4 và Part 5/11 trước;
- ngưỡng guard;
- quy ước rubric 05/10;
- các điểm lệch có chủ đích so với đề xuất v4 (§9.3) — đề xuất v4 là spec, không phải PRD.

**Bị chặn, cần đề xuất PRD + sửa contract trước** (ngoài phạm vi plan):
- (a) filter-first trong `/search` production (contract §2.2 "bước 2");
- (b) vé bay hoặc hỏi lại tuyến trong `/search` (FR-SRC-03, user-flow);
- (c) trang `/search` rỗng không có gợi ý (FR-SRC-04);
- (d) sao là filter cứng (contract §2.5).

Hai đề xuất đang chờ trong `docs/prd/update/` thuộc itinerary agent, không liên quan.
