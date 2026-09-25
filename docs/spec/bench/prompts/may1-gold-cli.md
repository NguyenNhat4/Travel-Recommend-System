# Việc cho máy 1: gold-guide.md + 4 lệnh `sb gold` (kappa, merge, import, check)

Nhánh: `feat/gold-cli`, tách từ main sau commit "gold: schema + fixtures (bước 0)".

## Mục tiêu

Có đủ công cụ để biến hai file nhãn của người A và người B thành `gold/gold.jsonl` đã kiểm tra, rồi tag `gold_v1`. Máy 2 làm app gán nhãn song song; hai bên chỉ nối với nhau qua file, theo hợp đồng trong `gold_schema.py`.

## Đọc trước

1. `src/evaluation/search_bench/gold_schema.py`: toàn bộ định dạng file. Dùng các hàm đọc/ghi trong đó, không tự viết parser CSV.
2. `src/evaluation/search_bench/tests/fixtures/gold_small/README.md` và `expected.json`: đáp án để chấm code.
3. Spec bench Part 5 (Gold) và Part 11 (append-only), checklist ngày 2–4 trong `docs/spec/bench/`.
4. Code hiện có của `sb gold drafts`, `sb gold pool`, `sb gold split`.

## Được sửa / không được sửa

- **Được sửa:** `src/evaluation/search_bench/gold.py`, phần CLI của nhóm lệnh `gold`, test mới `tests/test_gold_cli.py`, `docs/spec/bench/gold-guide.md`, các dòng checklist của máy 1.
- **Không sửa:** `gold_schema.py`, thư mục `tests/fixtures/gold_small/`, thư mục app Streamlit.
- Cần đổi schema hoặc fixture: dừng lại, ghi đề xuất (đổi gì, vì sao) vào mô tả PR. Việc đổi sẽ làm trên main để máy 2 cùng nhận.

## Việc 0: `sb gold pool` và `split` xuất đúng hợp đồng

Máy 2 chỉ đọc CSV, không có Weaviate hay catalog, nên pool phải mang đủ thông tin để hiển thị.

- Ghi pool bằng `write_pool_csv`, đủ các cột trong `POOL_COLUMNS`:
  - `taxonomy`, `destination`, `star_rating`, `amenities` (tối đa 12 tên tiện ích), `snippet` (40 từ đầu `embed_text` của B0).
  - `children`: với `hotel_property`, lấy các hạng phòng con từ `products.jsonl` của snapshot (`parentProductId` = product_id), gồm `id` và tên hạng phòng. Các loại khác để `[]`.
  - `filter_text`: filter viết thành chữ tiếng Việt dễ đọc, theo mẫu ở câu c9003 của fixture.
- **Tách filter:** điều kiện trên các field thuộc `CHILD_FILTER_FIELDS` (giá, sức chứa, ngày bay) đưa sang `child_filter_json`; phần còn lại vào `filter_json`. Nếu drafts đang dùng tên field khác (ví dụ `price_max`, `pax`), map sang đúng tên trong `CHILD_FILTER_FIELDS`.
- Không ghi cột giá nào.
- Xáo thứ tự ứng viên trong từng câu với seed 42. Không sắp theo rank.
- `split --overlap 25`:
  - Chọn 25 câu chung phân tầng theo slice; ghi `is_overlap`.
  - Ghi `pool_A.csv`, `pool_B.csv` và `pool_meta.json` bằng `write_pool_meta`, gồm: snapshot, tên collection B0, depth, seed, sha của `drafts.txt`, sha và số dòng của từng file pool.
- **Xong khi:** chạy lại trên 10 câu mẫu, `read_pool_csv` đọc được cả hai file, và sha trong meta khớp với file.

## Việc 1: `docs/spec/bench/gold-guide.md` (làm trước các lệnh)

Một trang. Gồm:

- **Ba nhãn**, gán ở cấp parent:
  - 2 = đúng thứ khách tìm.
  - 1 = liên quan một phần.
  - 0 = không liên quan.
- **Quy tắc chung:**
  - Không chấm giá, ngày, số khách; máy tự kiểm các điều kiện này.
  - Chỉ dựa vào thông tin hiện trên màn hình, không tra web.
  - Câu khó thì ghi vào `note`.
- **Luật destination — cần chốt rõ trong guide.** Đề xuất: *query có nêu destination thì sai destination → 0, kể cả đúng loại; đúng destination nhưng sai loại hoặc thiếu điều kiện → 1.* Fixture đang gán theo luật này. Spec Part 5 cũ ghi "đúng loại hoặc đúng nơi → 1", mâu thuẫn với luật trên; guide là nơi chốt, và ghi lại lý do.
- **Slice parent_child:**
  - Nhãn 2 phải tick hạng phòng đúng loại.
  - Không có hạng phòng đúng loại → 0.
  - Có hạng phòng gần đúng (ví dụ villa nhưng không có hồ bơi riêng) → 1, không tick.
- **Tiện ích:**
  - Sản phẩm "không ghi nhận" một tiện ích vẫn có thể được gán 2.
  - Query phủ định: sản phẩm được ghi nhận có tiện ích bị loại trừ → tối đa 1.
- **Câu ngoài catalog:** ứng viên thường là 0. Nếu gặp sản phẩm thật sự đúng, ghi `note` và báo lại, vì câu đó có thể không còn nằm ngoài catalog.
- **Ít nhất 5 ví dụ khó**, mỗi ví dụ có nhãn và lý do:
  - đúng nơi sai loại;
  - hạng phòng hay khách sạn;
  - combo có kèm vé;
  - tiện ích không ghi nhận;
  - query phủ định.

Xong thì gửi người B đọc. Hai người thống nhất các ví dụ khó trước khi gán thật (mốc 1).

## Việc 2–5: bốn lệnh

Exit code thống nhất cho cả bốn lệnh: **0** là đạt; **1** là dữ liệu vi phạm luật; **2** là lỗi đầu vào (file thiếu, sai định dạng, sai sha).

### `sb gold kappa LABELS_A LABELS_B [--meta gold/pool_meta.json] [--min 0.6]`

- Chỉ tính trên các cặp thuộc `meta.overlap_qids`.
- Câu chung còn thiếu nhãn ở một trong hai file → exit 1, liệt kê cặp thiếu.
- In ra: số cặp, ma trận nhầm (A theo hàng, B theo cột), **κ có trọng số linear** (dùng để quyết định), κ không trọng số để tham khảo, và các cặp lệch 2 bậc.
- κ < `--min` → exit 1.
- Trên fixture: κ linear phải bằng `expected.json → kappa.linear` (0,731343).

### `sb gold merge LABELS_A LABELS_B -o gold/labels/merged.csv [--meta ...]`

- Mọi cặp trong pool phải có nhãn; thiếu → exit 1, liệt kê.
- Cặp chỉ một người gán: lấy nhãn người đó (`source` = A hoặc B).
- Cặp chung:
  - Hai nhãn bằng nhau thì giữ nguyên.
  - Lệch 1 bậc: lấy nhãn thấp hơn, `note` = "lệch 1 bậc: lấy nhãn thấp hơn".
  - Lệch 2 bậc: `label` để trống, `needs_discussion` = true.
- `children_ok` (chỉ khi nhãn cuối là 2): lấy phần giao của hai người. Cả hai gán 2 nhưng phần giao rỗng → `needs_discussion`.
- Ghi file bằng `write_merged_csv`. Trên fixture, kết quả phải trùng từng dòng với `merged_expected.csv`.
- In số cặp `needs_discussion`. Người gán sửa trực tiếp trong `merged.csv`: điền `label`, đổi `needs_discussion` thành false, ghi lý do vào `note`.

### `sb gold import MERGED [--meta ...] [--catalog <products.jsonl snapshot>] [-o gold/gold.jsonl] [--provenance pool@gold_v1]`

Từ chối (exit 1 hoặc 2) nếu:
- còn dòng `needs_discussion`;
- thiếu cặp so với pool;
- có cặp không có trong pool;
- sha của file pool khác với meta;
- product_id hoặc id hạng phòng không có trong catalog snapshot;
- `validate_label_against_pool` báo lỗi.

Ghi `GoldRecord` bằng `write_gold_jsonl`:
- `filter` và `child_filter` lấy từ pool; `expected_children` gồm các cặp có nhãn 2 và có `children_ok`.
- Trên fixture: `import merged_expected.csv` phải từ chối; `import merged_resolved.csv --catalog tests/fixtures/gold_small/catalog_small.jsonl` phải ra file **giống từng byte** với `gold_expected.jsonl`.

### `sb gold check [gold/gold.jsonl] [--min-per-slice N]` (mặc định N lấy từ config, là 10)

Chỉ xét các câu `active`. Báo đỏ nếu:
- câu không thuộc out_of_catalog mà không có nhãn 2;
- câu out_of_catalog có nhãn 2, hoặc thiếu `expected_no_result`;
- slice có ít hơn N câu;
- nhãn 2 ở slice parent_child không có `expected_children`.

In bảng theo slice (số câu, số nhãn 0/1/2). Kết quả xanh thì in lệnh `git tag gold_v1`. Trên fixture: `--min-per-slice 1` → exit 0; mặc định 10 → exit 1.

## Test bắt buộc (`tests/test_gold_cli.py`, dùng fixture và `tmp_path`)

- Bốn đáp án ở trên: κ; merge; import từ chối rồi chấp nhận; check.
- Các ca âm, tự tạo trong `tmp_path`:
  - κ < 0,6: đổi vài nhãn của B.
  - Một cặp thiếu nhãn.
  - Pool bị sửa một ký tự làm sha lệch.
  - `children_ok` chứa id lạ.
  - Nhãn cho cặp không có trong pool.
  - Câu thường không có nhãn 2.
  - Câu out_of_catalog có nhãn 2.
- `python -m pytest evaluation/search_bench/tests -q` phải xanh, kể cả `test_gold_fixtures.py` có sẵn.

## Sau khi xong

1. Merge vào main. Máy 2 sẽ chạy thử bốn lệnh trên file do app xuất ra (mốc 2).
2. Khi `drafts.txt` đã đóng băng (đã soát 42 câu `--fill`, sửa 3 góp ý, thêm câu dự phòng cho 5 slice mỏng): nếu máy này có Weaviate và `COHERE_API_KEY`, chạy `sb gold pool --drafts gold/drafts.txt --depth 15` rồi `sb gold split --overlap 25`, commit `pool_A.csv`, `pool_B.csv`, `pool_meta.json`.
3. Tick các dòng checklist của máy 1.
