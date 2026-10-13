# Benchmark Search: Soạn gold_v7 phục vụ cổng bằng chứng và AC 7

- Ngày: 2026-10-13
- Tác giả: tqanh123 / Antigravity
- Nhánh: feat/search-evidence-gate
- Trạng thái: hoàn thành
- Phạm vi: evaluation, search_bench

## Mục tiêu

1. Soạn và phát hành phiên bản bộ dữ liệu benchmark `gold_v7` bổ sung 77 câu truy vấn mới (từ `c0757` đến `c0833`), nâng tổng số câu active từ 175 lên 252 câu (100% tuân thủ nguyên tắc append-only).
2. Phục vụ kế hoạch `/search` 1.28.0 (cổng bằng chứng `evidence_gate`, `duration_mask`, `embed_residual`, `unexplained_empty`, `restore` dấu, `emit_background`) và tiêu chí nghiệm thu AC 7 của Contract Search:
   - **`out_of_catalog`**: Bổ sung 3 câu âm (c0757: Cao Bằng, c0758: Hà Giang, c0759: Lai Châu), nâng tổng số câu của slice này lên đúng 10 câu theo AC 7 (`expected_no_result: true`).
   - **`no_answer` (40 câu, c0760–c0799)**: Kiểm thử khả năng trả rỗng khi câu hoàn toàn không giải thích được trong du lịch Việt Nam: tên người lạ (Nguyễn Văn A...), nhân vật hư cấu (Doraemon, Harry Potter...), POI sai/ngoài nước (tháp Eiffel Hà Nội, Kim tự tháp Giza Phú Quốc...), chuỗi ký tự vô nghĩa/gibberish (asdfghjkl...).
   - **`name_collision` (12 câu, c0800–c0811)**: Kiểm thử va chạm âm tiết rời rạc của tên người với tên sản phẩm catalog (Trần Thị Mai va chạm Thị trấn Hoàng Hôn, Phạm Văn Đồng va chạm Trung tâm Văn hoá / Sân Vận động), gắn `forbidden` các unit trùng âm tiết rác.
   - **`duration_only` (8 câu, c0812–c0819)**: Câu chỉ nêu thời lượng ("2 ngày 1 đêm", "combo 3N2Đ", "tour 1 ngày"...), rel 2 các tour/combo có thời lượng tương ứng, cấm vớt nhầm khách sạn (Chợ Đêm).
   - **`duration_stay` (6 câu, c0820–c0825)**: Câu lưu trú kèm thời lượng ("khách sạn Đà Lạt 2 ngày 1 đêm", "resort Phú Quốc 3 ngày 2 đêm"...), vai trò stay, rel 2 khách sạn/resort tại điểm đến, tuyệt đối không bị bộ lọc thời lượng diệt rỗng.
   - **`slang_residual` (8 câu, c0826–c0833)**: Câu chứa từ lóng/lifestyle ("rẻ bèo", "chanh sả", "sống ảo", "chill hết nấc", "quẩy banh nóc"...), kiểm thử cơ chế `embed_residual` giữ lại từ lóng đưa vào semantic search.

## File thay đổi

- `src/evaluation/search_bench/gold_schema.py`:
  - Thêm 5 slice mới vào tuple `SLICES`: `no_answer`, `name_collision`, `duration_only`, `duration_stay`, `slang_residual`.
  - Định nghĩa `NO_RESULT_SLICES = ("out_of_catalog", "no_answer")`.
- `src/evaluation/search_bench/gold.py`:
  - Cập nhật hàm kiểm tra `check_gold`: cho phép cả hai slice trong `NO_RESULT_SLICES` có `expected_no_result: true` và không chứa nhãn 2.
  - Cho phép `name_collision` linh hoạt theo `expected_no_result`.
- `src/evaluation/search_bench/config/sbench.yaml`:
  - Cập nhật `gold.target`: 306, `gold.minimum`: 66 (22 slice × min_per_slice = 3).
  - Khai báo hạn ngạch 5 slice mới trong khối `gold.slices`.
- `src/evaluation/search_bench/config/query_annotations.yaml`:
  - Thêm chú giải `expected_parse`, `forbidden`, `forbidden_filter`, `allowed_variants` cho 77 câu mới (loại bỏ `allowed_variants` rỗng cho các câu âm để pass validation).
- `src/evaluation/search_bench/gold/gold.jsonl`:
  - Nối 77 record mới (`c0757` đến `c0833`) với đầy đủ `judgments`, `provenance: "pool:machine@gold_v7"`.
- `src/evaluation/search_bench/gold/changelog.yaml`:
  - Ghi nhận phiên bản `gold_v7`: 252 câu active, 1 câu retired, 8.903 nhãn (767 nhãn mới).
- `src/evaluation/search_bench/gold/splits/devtest@gold_v7.json`:
  - Sinh file phân tầng ngẫu nhiên tất định (seed 42) theo slice: chia đều 126 dev / 126 test.
- `src/evaluation/search_bench/holes.py`:
  - Sửa `gold_version_of` truyền đường dẫn tương đối POSIX (`rel = repo_relpath(path)`) vào `git hash-object -- <path>` để tương thích Windows CRLF/LF filters.
- `src/evaluation/search_bench/tests/test_config.py`:
  - Cập nhật assertions của `test_gold_slice_quota_matches_target_and_min` cho 22 slice và target 306.
- `src/backend/data/search_prewarm_queries.txt`:
  - Cập nhật header với sha256 của blob `gold.jsonl` tại tag `gold_v7` và đồng bộ 252 câu active.

## Quyết định

- Đảm bảo tuân thủ nghiêm ngặt quy tắc append-only: giữ nguyên toàn bộ 175 câu cũ và thứ tự qid.
- Toàn bộ nhãn mới được kiểm tra chặt chẽ:
  - Các câu `expected_no_result: true` chỉ chứa nhãn 0, không có nhãn 2.
  - Các câu `expected_no_result: false` có ít nhất một nhãn 2 xác thực từ catalog `items.parquet`.
  - Phân chia vai trò thời lượng: `gate` cho `duration_only` và `stay` cho `duration_stay`.
- Gắn git tag `gold_v7` đồng bộ với blob hash trong repo.

## Kiểm tra

- `python -m evaluation.search_bench gold check`:
  - **PASS** 100% xanh (`gold check xanh (252 câu, min_per_slice = 3)`).
- `python -m evaluation.search_bench gold devtest`:
  - **PASS** sinh thành công `devtest@gold_v7.json` (126 dev / 126 test câu).
- Toàn bộ test suite liên quan (`test_annotations.py`, `test_config.py`, `test_prewarm_list.py`, `test_gold.py`, `test_gold_cli.py`, `test_devtest_regress.py`):
  - **PASS**: 114 passed, 1 skipped.
