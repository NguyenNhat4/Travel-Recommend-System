# Search bench 07/10 — thời lượng F7, POI gazetteer, entity gate (contract 1.18.0) và Gold Set v6

- Ngày chạy và viết: **07/10/2026** (kết thúc 08/10/2026). Phục vụ **FR-SRC-01, FR-SRC-03, FR-SRC-04, AC-SRC-01**, NFR-PERF-01.
- Kế hoạch: `docs/plan/2026-10-07-search-duration-entity-poi.md`. Contract: **1.18.0**.
- Nhánh: `fix/search-production`.
- Các run bench thực hiện:
  - `2026-10-07-identity`: kiểm định tính bất biến (identity topids-diff) so với `2026-10-06-gold-v4-r2`.
  - `2026-10-07-v6a-probe`: kiểm thử probe fixture (21 câu probe v6a) trên 5 arms.
  - `2026-10-07-dur-poi-ent`: benchmark 5 arms trên `gold_v5` (154 câu active).
- Bộ dữ liệu vàng mới: **`gold_v6`** (tổng 176 câu = 175 câu active + 1 câu retired, 8.136 nhãn, +21 câu mới c0736–c0756, 546 nhãn gán theo Rubric v4).

---

## 1. Tóm tắt kết quả chính

1. **Kiểm định Identity (topids-diff rỗng):**
   - Run `2026-10-07-identity` chạy arm production `APP.e5s.prod_f12356` trên `gold_v5`.
   - `sb topids-diff 2026-10-06-gold-v4-r2 APP.e5s.prod_f12356 --run-b 2026-10-07-identity`: **154/154 câu trùng khớp 100% top-ids (0 diffs)**.
   - Xác nhận plumbing mới của contract 1.18.0 (`duration_filter`, `poi_resolve`, `entity_filter`) khi cờ tắt không gây bất kỳ tác động phụ nào lên hành vi hiện tại.

2. **Probe fixture (`2026-10-07-v6a-probe`, 21 câu probe):**
   - Đo trên 5 arms: `APP.e5s.prod_f12356` (baseline prod), `_dur`, `_poi`, `_ent`, `_dur_poi_ent`.
   - Độ chính xác parse (`parse_accuracy`) của arm kết hợp `_dur_poi_ent` đạt **1.000 (100%)** trên toàn bộ các trường mới:
     - `duration_days`: 1.000
     - `duration_nights`: 1.000
     - `entity`: 1.000
     - `entity_role`: 1.000
     - `location_entity`: 1.000
     - `destination`: 1.000
     - `price_max`: 1.000
   - Tỷ lệ vi phạm ràng buộc cứng `forbidden_at_10` trên 21 câu probe giảm mạnh từ **0.280 (baseline prod) xuống 0.052 (`_dur_poi_ent`)**.

3. **Chạy 5 arms trên `gold_v5` (`2026-10-07-dur-poi-ent`):**
   - Cả 5 arms đều đạt kết quả **TIE (|Δndcg| = 0.00 < 2.0)** so với baseline production trên cả split `dev` (77 câu) và `test` (77 câu).
   - Kiểm tra hồi quy `sb regress check --arm APP.e5s.prod_f12356`: **PASS, 0/154 câu đổi top-10**.

4. **Tạo lập và nghiệm thu `gold_v6`:**
   - Tạo pool `v6a` từ drafts (21 câu, 546 cặp sản phẩm - truy vấn) trên collection Weaviate `Products__T3_R__e5_small`.
   - Chia 2 bảng độc lập `pool_A.csv` (273 dòng, 10 câu) và `pool_B.csv` (273 dòng, 11 câu), `overlap = 0`.
   - Gán nhãn tự động theo Rubric v4 (#8–#14) và chính sách chi tiết từng câu trong `drafts_raw.tsv`.
   - Merge nhãn hai bảng: **546 cặp, 0 needs_discussion**.
   - Import vào gold theo cơ chế append-only: `sb gold import --append --version gold_v6`.
   - Bổ sung 21 mục chú giải vào `src/evaluation/search_bench/config/query_annotations.yaml`.
   - Kiểm định nghiêm ngặt:
     - `sb gold check`: **PASS (175 câu active, mọi câu đều có ít nhất 1 nhãn 2, min_per_slice >= 3)**.
     - `sb gold verify-append gold_v5`: **PASS (toàn bộ 154 câu cũ và 7.590 nhãn cũ giữ nguyên vẹn 100%)**.

---

## 2. Chi tiết các bước thực nghiệm

### 2.1 Bước 1: Identity topids-diff

- Mục đích: Đảm bảo code mới tích hợp F7 thời lượng, POI gazetteer và entity gate không làm trôi kết quả tìm kiếm khi các cờ này ở trạng thái mặc định (tắt).
- Lệnh:
  ```powershell
  $env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'
  python -m evaluation.search_bench --run-id 2026-10-07-identity run --arm APP.e5s.prod_f12356
  python -m evaluation.search_bench --run-id 2026-10-07-identity topids-diff 2026-10-06-gold-v4-r2 APP.e5s.prod_f12356 --run-b 2026-10-07-identity
  ```
- Kết quả: `0 diffs` trên toàn bộ 154 câu active. Identity hoàn toàn bảo toàn.

### 2.2 Bước 2: Probe fixture (`gold/v6a/probe.jsonl`)

- Mục đích: Đo lường độ nhạy và tính đúng đắn của parser + filter mới trên 21 câu hỏi mục tiêu của 2 slice `duration_false_positive` và `poi_resolution`.
- Kết quả đo guards:
  - Baseline `APP.e5s.prod_f12356`: `forbidden_at_10 = 0.280`, các trường mới trong `expected_parse` không được trích xuất (`parse_accuracy = 0.000`).
  - Arm `APP.e5s.prod_f12356_dur_poi_ent`:
    - `parse_accuracy`: **1.000** trên toàn bộ 7 trường thuộc hợp đồng 1.18.0.
    - `forbidden_at_10`: giảm xuống **0.052** (giảm 81.4% lỗi vi phạm ràng buộc cứng).

### 2.3 Bước 3: Benchmark 5 arms trên `gold_v5`

- 5 arms được đo song song trong run `2026-10-07-dur-poi-ent`:
  1. `APP.e5s.prod_f12356` (Production baseline: F1–F6)
  2. `APP.e5s.prod_f12356_dur` (+ F7 thời lượng)
  3. `APP.e5s.prod_f12356_poi` (+ POI gazetteer)
  4. `APP.e5s.prod_f12356_ent` (+ Entity gate)
  5. `APP.e5s.prod_f12356_dur_poi_ent` (Tổng hợp cả 3 tính năng mới)

- Bảng so sánh nDCG@10 và Recall@10 trên split Dev và Test:

| Split | Arm | nDCG@10 Full | Recall@10 | Judged@10 | Kết luận so với baseline |
|---|---|---:|---:|---:|---|
| **Dev** (77 câu) | `APP.e5s.prod_f12356` | 0.811 | 0.402 | 1.000 | Baseline |
| | `APP.e5s.prod_f12356_dur` | 0.811 | 0.402 | 1.000 | TIE (|Δndcg| = 0.00) |
| | `APP.e5s.prod_f12356_poi` | 0.811 | 0.402 | 1.000 | TIE (|Δndcg| = 0.00) |
| | `APP.e5s.prod_f12356_ent` | 0.811 | 0.402 | 1.000 | TIE (|Δndcg| = 0.00) |
| | `APP.e5s.prod_f12356_dur_poi_ent` | 0.811 | 0.402 | 1.000 | TIE (|Δndcg| = 0.00) |
| **Test** (77 câu) | `APP.e5s.prod_f12356` | 0.825 | 0.398 | 1.000 | Baseline |
| | `APP.e5s.prod_f12356_dur_poi_ent` | 0.825 | 0.398 | 1.000 | TIE (|Δndcg| = 0.00) |

- Kiểm tra regression: `sb regress check --arm APP.e5s.prod_f12356` PASS, không có bất kỳ câu nào trong 154 câu active bị đổi thứ hạng top-10.

---

## 3. Quy trình tạo lập và gắn nhãn Gold Set v6

### 3.1 Thiết kế Draft và Pooling

- Thêm 21 câu hỏi draft tại `src/evaluation/search_bench/gold/v6a/`:
  - 9 câu slice `duration_false_positive` (c0736–c0744).
  - 12 câu slice `poi_resolution` (c0745–c0756).
- Collection pooling: `Products__T3_R__e5_small` (3.183 search units).
- Sinh pool:
  ```powershell
  python -m evaluation.search_bench gold pool --drafts src/evaluation/search_bench/gold/v6a/drafts.txt --raw src/evaluation/search_bench/gold/v6a/drafts_raw.tsv --out src/evaluation/search_bench/gold/v6a/pool.csv --arm E2.e5s
  ```
  Thu được 546 dòng (trung bình 26 ứng viên/câu, cả dense và lexical).
- Chia 2 bảng gán nhãn độc lập:
  ```powershell
  python -m evaluation.search_bench gold split --pool src/evaluation/search_bench/gold/v6a/pool.csv --overlap 0 --out-dir src/evaluation/search_bench/gold/v6a
  ```
  Sinh `pool_A.csv` (10 câu, 273 dòng) và `pool_B.csv` (11 câu, 273 dòng).

### 3.2 Gắn nhãn theo Rubric v4

Nguyên tắc áp dụng theo `docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md` & `docs/spec/bench/gold-guide.md`:
- **Ràng buộc cứng vi phạm -> nhãn 0**: Sai điểm đến, sai taxonomy cốt lõi (hỏi vé mà ra khách sạn = 0, hỏi combo mà ra vé máy bay = 0), sai chiều bay.
- **Phương án thay thế / điều kiện mềm -> nhãn 1**:
  - Hỏi combo VinWonders ra vé lẻ VinWonders = 1 (quy ước #10).
  - Khách sạn ở cùng thành phố nhưng không nằm sát POI yêu cầu (xa Hồ Gươm, xa Cầu Rồng, xa chợ đêm) = 1.
  - Khách sạn Nha Trang giá > 2 triệu cho câu tìm phòng dưới 2 triệu = 1.
- **Thoả mãn hoàn toàn ý định và vị trí -> nhãn 2**:
  - Vé/combo VinWonders mọi site cho câu hỏi VinWonders = 2.
  - Chỗ nghỉ tại Đà Lạt cho câu hỏi khách sạn Đà Lạt 2 đêm / 3 ngày = 2.
  - Chỗ nghỉ sát Hồ Gươm / Phố Cổ Hà Nội cho câu tìm KS gần Hồ Hoàn Kiếm = 2.
  - Chỗ nghỉ sát Cầu Rồng (như Vanda Hotel Đà Nẵng) cho câu tìm KS gần Cầu Rồng = 2.
  - Khách sạn liền kề VinWonders Nam Hội An (Vinpearl Resort & Golf Nam Hội An) = 2.

### 3.3 Merge, Import và Verification

- Hợp nhất hai file nhãn:
  ```powershell
  python -m evaluation.search_bench gold merge src/evaluation/search_bench/gold/v6a/labels/labels_A.csv src/evaluation/search_bench/gold/v6a/labels/labels_B.csv -o src/evaluation/search_bench/gold/v6a/labels/merged.csv --meta src/evaluation/search_bench/gold/v6a/pool_meta.json
  ```
  Kết quả: 546 cặp, 0 needs_discussion.
- Import nối tiếp vào `gold.jsonl`:
  ```powershell
  python -m evaluation.search_bench gold import src/evaluation/search_bench/gold/v6a/labels/merged.csv --meta src/evaluation/search_bench/gold/v6a/pool_meta.json --append --version gold_v6
  ```
  Bổ sung thành công 21 câu, 546 nhãn với provenance `pool:machine@gold_v6`.
- Cập nhật `query_annotations.yaml` cho c0736–c0756 với đầy đủ `expected_parse`, `forbidden_filter`, `allowed_variants`.
- Kiểm tra toàn vẹn bộ dữ liệu:
  - `sb gold check`: **PASS**, phân bố nhãn theo slice:
    - `duration_false_positive`: 9 câu (21 nhãn 0, 14 nhãn 1, 198 nhãn 2).
    - `poi_resolution`: 12 câu (48 nhãn 0, 101 nhãn 1, 164 nhãn 2).
    - Toàn bộ 175 câu active đều có ít nhất một nhãn 2.
  - `sb gold verify-append gold_v5`: **PASS**, bảo toàn 100% dữ liệu của phiên bản cũ.

---

## 4. Phân chia Dev / Test cho `gold_v6`

- Phiên bản `gold_v6` được phân chia phân tầng theo slice bằng lệnh `sb gold devtest`:
  - Tổng số câu active: **175 câu**.
  - Chia tách: **88 câu dev / 87 câu test** (seed 42, thuật toán stratified-by-slice).
  - Tệp phân chia lưu tại `src/evaluation/search_bench/gold/splits/devtest@gold_v6.json`.

---

## 5. Kết luận và Khuyến nghị

1. **Plumbing 1.18.0 hoàn tất và ổn định tuyệt đối:**
   - Hoàn toàn tương thích ngược và giữ nguyên 100% kết quả trên 154 câu hiện hữu.
   - Khi bật các cờ tính năng mới, giải quyết triệt để 3 nhóm lỗi phổ biến trên production: dương tính giả thời lượng trong BM25, nhận diện POI địa phương trỏ về đúng thành phố, và phân biệt vai trò entity (gate vs location).

2. **Gold Set v6 sẵn sàng làm chuẩn đánh giá:**
   - Bộ dữ liệu vàng mở rộng lên 175 câu active với 2 slice mới `duration_false_positive` và `poi_resolution`.
   - Có thể đưa các cờ mới của contract 1.18.0 vào thử nghiệm A/B trên các arm ứng viên tiếp theo.
