# Search bench: benchmark 5 arms Weaviate va tao Gold Set v6

- Ngày: 2026-10-07 (hoàn thành 2026-10-08)
- Tác giả: người dùng / Antigravity
- Nhánh: fix/search-production
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Chạy benchmark Weaviate local cho tính năng search thời lượng F7, POI gazetteer và entity gate (contract 1.18.0) theo chu trình: identity topids-diff → probe fixture → 5 arm → report; sau đó tự gắn nhãn theo Rubric v4 (#8–#14) và chính sách drafts_raw để tạo lập và nghiệm thu Gold Set v6.

## File thay đổi

- `src/evaluation/search_bench/gold/gold.jsonl` — sửa: bổ sung 21 câu active (c0736–c0756) thuộc 2 slice `duration_false_positive` và `poi_resolution`, tổng 176 câu (175 active + 1 retired), 8.136 nhãn (tăng 546 nhãn).
- `src/evaluation/search_bench/gold/changelog.yaml` — sửa: ghi nhận mục `import_append` cho `gold_v6` với 21 câu mới.
- `src/evaluation/search_bench/config/query_annotations.yaml` — sửa: bổ sung chú giải 21 câu c0736–c0756 (`expected_parse`, `forbidden_filter`, `allowed_variants`).
- `src/evaluation/search_bench/gold/v6a/pool.csv` — thêm: pool 546 ứng viên từ collection Weaviate `Products__T3_R__e5_small`.
- `src/evaluation/search_bench/gold/v6a/pool.build.json` — thêm: metadata quá trình build pool v6a.
- `src/evaluation/search_bench/gold/v6a/pool_A.csv`, `pool_B.csv` — thêm: chia 2 bảng gán nhãn độc lập (273 cặp mỗi bảng).
- `src/evaluation/search_bench/gold/v6a/pool_meta.json` — thêm: checksum và thông số split của pool v6a.
- `src/evaluation/search_bench/gold/v6a/labels/labels_A.csv`, `labels_B.csv` — thêm: nhãn 0/1/2 gán theo Rubric v4.
- `src/evaluation/search_bench/gold/v6a/labels/provenance_A.csv`, `provenance_B.csv` — thêm: nguồn gốc nhãn máy được duyệt (QAnh, review accepted).
- `src/evaluation/search_bench/gold/v6a/labels/merged.csv` — thêm: kết quả hoà nhãn 546 cặp (0 needs_discussion).
- `src/evaluation/reports/eval-2026-10-07-search-duration-entity-poi.md` — thêm: báo cáo chi tiết benchmark 5 arms, probe fixture và tạo lập gold_v6.

## Quyết định

- Áp dụng triệt để Rubric v4:
  - Ràng buộc cứng (destination, variant cốt lõi, brand phủ định) vi phạm gán 0; tương đồng ngữ nghĩa không bù cho vi phạm cứng.
  - Chỗ nghỉ tại cùng thành phố nhưng xa POI yêu cầu (xa Hồ Gươm, xa Cầu Rồng, xa Chợ Đêm Đà Lạt) gán 1.
  - Khách sạn liền kề POI (như Vanda Hotel sát Cầu Rồng Đà Nẵng, Vinpearl Resort Nam Hội An sát VinWonders Nam Hội An) hoặc sát Hồ Gươm gán 2.
  - Phân tách vé lẻ và combo: hỏi combo ra vé lẻ = 1 (quy ước #10); hỏi vé ra combo kèm dịch vụ = 1.
  - Khách sạn có dịch vụ đưa đón sân bay tại Hà Nội gán 2 cho câu tìm khách sạn gần sân bay Nội Bài.
- Giữ vững nguyên tắc append-only của gold (`verify-append` với tag `gold_v5` PASS 100%).

## Kiểm tra

- `sb --run-id 2026-10-07-identity topids-diff 2026-10-06-gold-v4-r2 APP.e5s.prod_f12356 --run-b 2026-10-07-identity`: PASS, 0/154 diffs.
- `sb --run-id 2026-10-07-v6a-probe guards`: parse_accuracy 1.000 trên cả 7 trường mới, forbidden_at_10 giảm từ 0.280 xuống 0.052.
- `sb --run-id 2026-10-07-dur-poi-ent compare`: TIE (|Δndcg| = 0.00 < 2.0) trên cả dev (77 câu) và test (77 câu).
- `sb regress check --arm APP.e5s.prod_f12356`: PASS, 0/154 câu đổi top-10.
- `sb gold merge`: 546 cặp, 0 needs_discussion.
- `sb gold import --append --version gold_v6`: PASS, provenance `pool:machine@gold_v6`.
- `sb gold check`: PASS, 175 câu active, min_per_slice >= 3.
- `sb gold verify-append gold_v5`: PASS, không làm trôi dữ liệu cũ.

## Còn lại / rủi ro

- Cần commit và gắn git tag `gold_v6` để kích hoạt chia tách dev/test `sb gold devtest`.
