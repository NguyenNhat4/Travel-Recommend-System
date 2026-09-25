# Việc cho máy 2: mở rộng app Streamlit để gán nhãn relevance 0/1/2

Phục vụ: **FR-SRC-01..04**, **AC-SRC-01** (`docs/prd/requirements.md`) và test-plan §2.5 (`docs/prd/test-plan.md`).

Nhánh: `feat/label-app`, tách từ main sau commit "gold: schema + fixtures (bước 0)". *25/09: chưa chia máy — khi làm thì tách từ `bench/embed-search` (main chưa có `src/evaluation/search_bench/`).*

## Mục tiêu

App hiện chỉ có chế độ soát câu hỏi (KEEP / REJECT / NEEDS_EDIT). Cần thêm chế độ **Gán nhãn relevance**. Người A và người B mỗi người gán khoảng 112 câu (≈ 87 câu riêng + 25 câu chung) × 26 ứng viên ≈ 2.900 cặp và xuất ra `gold/labels/labels_<X>.csv` đúng hợp đồng. Máy 1 làm CLI song song; hai bên chỉ nối với nhau qua file.

## Đọc trước

1. `src/evaluation/search_bench/gold_schema.py`. Chỉ dùng các hàm có sẵn:
   - đọc: `read_pool_csv`, `read_pool_meta`, `file_sha256`, `read_labels_csv`;
   - ghi: `upsert_label` (ghi an toàn, mỗi cặp một dòng);
   - kiểm tra: `validate_label_against_pool`, `missing_pairs`;
   - hiển thị: `DISPLAY_COLUMNS`, `children_visible`, `LabelRow`.

   Không tự viết parser CSV.
2. `src/evaluation/search_bench/tests/fixtures/gold_small/README.md`: `pool_A.csv` / `pool_B.csv` là input để thử; `labels_A.csv` / `labels_B.csv` là đáp án.
3. Code app Streamlit hiện tại.
4. `docs/spec/bench/gold-guide.md` khi máy 1 viết xong. Nhãn trên app phải khớp định nghĩa trong guide.

## Được sửa / không được sửa

- **Được sửa:** thư mục app Streamlit và test của app.
- **Không sửa:** `gold_schema.py`, fixture, `gold.py`, CLI `sb gold`.
- Cần đổi schema: dừng lại, ghi đề xuất vào mô tả PR.

## Cấu trúc code

- `labeling_core.py`: Python thuần, không import streamlit. Chứa:
  - nạp pool và meta, kiểm tra sha;
  - danh sách câu và tiến độ;
  - vị trí tiếp tục (câu đầu tiên còn cặp chưa gán);
  - lưu nhãn (dựng `LabelRow` → `validate_label_against_pool` → `upsert_label`).
- File UI Streamlit chỉ gọi các hàm trong `labeling_core.py`.

## Yêu cầu

1. **Chế độ riêng.** Thêm lựa chọn "Gán nhãn relevance" cạnh chế độ soát câu hiện có. Chế độ cũ phải chạy như trước.
2. **Người gán cố định trong phiên.**
   - Khi vào chế độ này, chọn A hoặc B. App chỉ mở `gold/pool_<X>.csv` và `gold/labels/labels_<X>.csv`; đường dẫn có thể đổi trong sidebar để chạy với fixture.
   - Không bao giờ đọc file nhãn của người kia: 25 câu chung phải được gán độc lập.
3. **Chặn pool lệch.** `file_sha256(pool)` khác `meta.files[X].sha256` → báo lỗi, không cho gán. Lỗi này nghĩa là pool đã bị sửa, hoặc đang mở nhầm file. Nếu lỗi xuất hiện ngay sau khi pull, kiểm tra `.gitattributes`: git trên Windows đổi ký tự xuống dòng làm đổi sha (xem README của bước 0).
4. **Mỗi trang một câu.**
   - Phần đầu trang: query, slice, `filter_text`. Nếu `expected_no_result` thì hiện dòng nhắc "câu ngoài catalog".
   - Bảng ứng viên giữ **đúng thứ tự trong file**, chỉ hiện các cột trong `DISPLAY_COLUMNS`.
   - Cột `children` chỉ hiện ở slice parent_child (`children_visible`).
   - Không hiện `from`, rank, `is_overlap`, `product_id`; không có giá.
5. **Gán nhãn.**
   - Mỗi ứng viên chọn 2 / 1 / 0; mặc định là chưa gán, không tự điền 0.
   - Slice parent_child: khi chọn 2, hiện ô chọn hạng phòng đúng loại, bắt buộc chọn ít nhất một.
   - Có ô `note` cho mỗi cặp.
6. **Lưu ngay sau mỗi thay đổi.**
   - Mỗi lần chọn là một lần gọi `upsert_label`, với `labeled_at` = giờ hiện tại và `pool_sha` lấy từ meta.
   - Lỗi từ `validate_label_against_pool` hiện ngay tại dòng đó, không lưu.
7. **Tiếp tục đúng chỗ.**
   - Mở app thì nhảy tới câu đầu tiên còn cặp chưa gán.
   - Có nút "Câu chưa xong tiếp theo", nút lùi / tiến, và bộ lọc "chỉ câu chưa xong".
8. **Tiến độ.** Hiện số câu đã xong trên tổng số câu, số cặp đã gán trên tổng số cặp (`missing_pairs`), và phân bố nhãn 0/1/2 của người đang gán.
9. **Tự nạp lại khi file đổi.** Cache khoá theo thời điểm sửa file (mtime), kèm nút "Tải lại". Nếu lỗi "phải khởi động lại app mới thấy 72 câu bổ sung" của chế độ soát câu có cùng nguyên nhân cache, sửa luôn.
10. **Tốc độ.** Mỗi thao tác phải dưới 1 giây với trang khoảng 26 dòng.
    - Gợi ý: `st.data_editor` với cột nhãn kiểu `SelectboxColumn` sẽ nhanh hơn 26 nút radio. Chọn hạng phòng có thể tách thành `st.multiselect` riêng, chỉ cho các dòng parent_child.
    - Phím tắt 0/1/2 nếu làm được.
11. **Không dựa vào trạng thái trong bộ nhớ.** Tắt app giữa chừng rồi mở lại không được mất nhãn nào; file nhãn là nguồn sự thật duy nhất.

## Test bắt buộc (`test_labeling_core.py`, dùng fixture và `tmp_path`)

- Gán toàn bộ `pool_A.csv` qua các hàm của `labeling_core`, dùng đúng nhãn trong `labels_A.csv` → file xuất ra phải **giống `labels_A.csv` ở mọi cột trừ `labeled_at`**. Làm tương tự với B.
- Vị trí tiếp tục: gán 2 câu đầu → vị trí trả về là câu thứ 3.
- Pool bị sửa một ký tự → bị chặn vì lệch sha.
- Nhãn 2 ở slice parent_child mà không chọn hạng phòng → không lưu, trả về lỗi.
- Lõi gán nhãn không mở file nhãn của người kia: dùng patch hoặc kiểm tra đường dẫn được mở.
- `python -m pytest evaluation/search_bench/tests -q` và test của app đều phải xanh.

## Mốc tích hợp (sau khi máy 1 merge bốn lệnh)

1. Mở app với fixture, gán hết `pool_A.csv` bằng tay theo `labels_A.csv`, và `pool_B.csv` theo `labels_B.csv`.
2. Chạy `sb gold kappa` rồi `sb gold merge` trên hai file app vừa xuất:
   - κ phải bằng `expected.json`;
   - merge phải trùng với `merged_expected.csv`.
3. Qua được mốc này mới bắt đầu gán nhãn thật.

## Cách chạy khi gán thật

- **Mỗi người chạy trên máy mình**, với file pool của mình. Commit `labels_<X>.csv` thường xuyên, hoặc để file trên ổ chung.
- **Hoặc chạy một app trong mạng LAN:** `streamlit run <app>.py --server.address 0.0.0.0`, hai người mở bằng trình duyệt. Vì file nhãn tách riêng theo người gán nên không ghi đè nhau.

## Sau khi xong

Merge vào main và tick các dòng checklist của máy 2.
