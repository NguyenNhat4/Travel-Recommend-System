# Máy gán phần còn lại của gold, người duyệt trong app (nguồn nhãn, lọc, cột duyệt)

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành — nhãn máy đã ghi, app dùng chung đã khởi động lại với bản mới; chờ người dùng duyệt
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng đã gán một phần và yêu cầu:
1. Gán nốt phần còn lại.
2. Thêm bộ lọc theo máy gán / người gán / người duyệt.
3. Khi duyệt thì tick ở đầu dòng hoặc sửa nhãn.

Các lựa chọn người dùng chốt qua câu hỏi:
- máy gán phần còn lại của **cả A và B**;
- **câu chung để người gán**, máy không đụng vào (giữ κ giữa hai người);
- **Claude tự đánh giá, không gọi API**;
- khởi động lại app ngay khi code xong.

Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5. Không lệch PRD: PRD không quy định cách gán gold. Spec bench cập nhật trong `gold-guide.md` và `docs/spec/bench/README.md`.

## File thay đổi

- `src/evaluation/search_bench/labeling_core.py` — sửa:
  - `make_label_row` (tách phần dựng + kiểm khỏi `save_label`);
  - file phụ `provenance_<X>.csv`: `PROV_COLUMNS`, `load_provenance`, `update_provenance`;
  - `import_machine_labels`: chỉ cặp còn trống, từ chối câu chung, đọc – thêm – ghi một lần dưới khoá;
  - `record_review`, `plan_save`, `source_of`, `review_stats`.
- `src/evaluation/search_bench/__main__.py` — thêm `sb gold machine-import FILE… --model` (từ chối khi app dùng chung còn nghe ở cổng; `--dry-run`).
- `src/evaluation/search_bench/streamlit_app.py` — sửa chế độ gán nhãn:
  - ô "Tên người duyệt";
  - dòng số liệu nguồn nhãn;
  - "Lọc câu" (có nhãn máy chưa duyệt / có nhãn máy / chỉ nhãn người), đánh dấu 🤖 N chưa duyệt;
  - "Hiện dòng" (tất cả / máy gán / người gán / chưa duyệt / đã duyệt);
  - bảng thêm cột **duyệt** (tick), **nguồn**, **lý do máy**;
  - lưu tick = chấp nhận, sửa nhãn máy = đã sửa, bỏ tick = về chưa duyệt; cần tên người duyệt;
  - đổi bộ lọc thì lưu trước.

  Viết trên bản nháp `streamlit_app_next.py` rồi thay vào lúc app dừng, để không lặp lỗi nạp nửa chừng khi sửa code lúc app đang chạy.
- `src/evaluation/search_bench/tests/test_labeling_core.py` — thêm `test_machine_import_only_fills_free_private_pairs_and_tracks_review`, `test_plan_save_splits_label_changes_and_review_actions`.
- `src/evaluation/search_bench/tests/test_gold_cli.py` — thêm `test_machine_import_cli_refuses_while_app_listens_and_writes_when_stopped`.
- `src/evaluation/search_bench/tests/test_streamlit_app.py` — sửa + thêm:
  - `APP` đọc được từ `SBENCH_TEST_APP` (để test bản nháp trong lúc app phục vụ);
  - thêm `test_label_mode_shows_machine_labels_filters_and_reviewer`.
- `docs/spec/bench/gold-guide.md` — sửa: mục "Nhãn máy và duyệt (29/09)".
- `docs/spec/bench/README.md` — sửa: dòng `sb gold machine-import`.
- `src/evaluation/search_bench/gold/labels/labels_A.csv`, `labels_B.csv` — sửa: thêm nhãn máy (A 670, B 882).
- `src/evaluation/search_bench/gold/labels/provenance_A.csv`, `provenance_B.csv` — thêm.
- `history/2026-09-29-nhan-may-va-duyet.md` — thêm: entry này.

## Quyết định

- **Máy gán bằng 8 agent Claude trong phiên, không gọi API.**
  - Mỗi agent một lô khoảng 200 cặp, đọc đủ `gold-guide.md`, chỉ gán cặp TODO, và tự kiểm định dạng.
  - Đầu vào là ảnh chụp các cặp còn trống của câu riêng lúc 15:5x: 1.635 cặp ở 65 câu (A 746, B 889).
  - `validate_all.py` kiểm lại toàn bộ: 1.635 / 1.635, không thiếu, thừa, trùng, không có hạng phòng lạ, không có câu chung.
  - Phân bố: 0 = 569, 1 = 342, 2 = 724.
- **Import lúc app dừng, chỉ cặp còn trống.** Hai người vẫn gán trong lúc máy chạy, nên 76 cặp (A) và 7 cặp (B) đã có nhãn người và được giữ nguyên. Kết quả: A ghi 670, B ghi 882, không dòng nào bị từ chối. Import thử trên bản sao `gold/` trước khi làm thật; nhãn người giữ nguyên từng trường.
- **Nguồn nhãn ở file phụ, không đổi hợp đồng file nhãn.** Hợp đồng `gold_schema.py` đóng băng. `kappa` / `merge` / `import` không đọc file phụ, nên nhãn máy vào gold như nhãn thường. Chất lượng được kiểm bằng việc duyệt.
- **Nhãn máy ghi `note` trống.** Lý do của máy nằm ở `provenance.machine_note` (cột "lý do máy" trong app), để `merge` không nối lý do máy vào ghi chú.

## Kiểm tra

- `pytest evaluation/search_bench/tests`:
  - trên bản nháp trước khi thay: **280 passed, 10 skipped**;
  - trên file thật sau khi thay: **280 passed, 10 skipped**.
- `pyflakes` các file đổi: sạch.
- Chuyển thật:
  1. Dừng app, cổng 8502 đóng.
  2. `machine-import`: A ghi 670 / bỏ qua 76, B ghi 882 / bỏ qua 7, từ chối 0.
  3. Thay `streamlit_app.py` bằng bản mới.
  4. Chạy lại `sb gold share`: health 200, chỉ `127.0.0.1:8502`.
- **Sau chuyển:**
  - A: 1.662 / 1.999 cặp, 65/78 câu xong (người 992, máy 670 chưa duyệt).
  - B: 1.576 / 2.000 cặp, 62/79 câu xong (người 694, máy 882 chưa duyệt).
  - Còn trống chỉ là cặp câu chung.
  - AppTest qua launcher với mã B: dòng nguồn nhãn đúng, 35 câu có 🤖, có ô tên người duyệt.

## Còn lại / rủi ro

- **Người gán:** gán nốt các cặp câu chung (A 337, B 424).
- **Người duyệt:** duyệt 1.552 nhãn máy. Các agent báo chỗ mơ hồ, và **cách xử lý không đồng đều giữa các lô**, nên cần ưu tiên soát:
  1. **Câu hỏi đòi tiện ích mà sản phẩm không ghi nhận.** Phần lớn cho 2 theo hướng dẫn. Lô 06 cho 1 khi tiện ích là điều kiện chính (spa c0154, wifi c0166). Lô 02 dùng quy tắc riêng: tiện ích phổ biến cho 2, không chắc cho 1. Tìm qua cột lý do máy có chữ "không ghi nhận".
  2. **"khách sạn" có tính cả resort / nhà nghỉ / căn hộ / homestay không.** Lô 00 và 01 đọc chặt (căn hộ, homestay, resort → 1). Lô 04 tính resort, nhà nghỉ là khách sạn (→ 2).
  3. **Vé máy bay ngược chiều / khởi hành từ điểm đến.** Lô khác nhau cho 0 hoặc 1 (c0541, c0547, c0202, c0373).
  4. **parent_child cận biên:** ban công ghi ở cấp khách sạn, phòng không có chữ "Deluxe", phòng "Double Double" (c0276, c0277, c0290).
  5. **c0517:** câu hỏi nói "3 sao" nhưng filter là "≥ 3" → máy cho 2 cả khách sạn 4–5 sao.
- Nếu người dùng chốt cách hiểu cho các điểm trên, nên ghi thêm vào `gold-guide.md` trước khi gán / duyệt tiếp.
- Chưa commit.
