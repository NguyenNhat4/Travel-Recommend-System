# Hướng dẫn gán nhãn gold (search bench)

Phục vụ: **FR-SRC-01..04**, **AC-SRC-01** (`docs/prd/requirements.md`) và test-plan §2.5 (`docs/prd/test-plan.md`). Áp dụng cho `pool_A.csv` / `pool_B.csv` do `sb gold split` xuất ra. Nhãn chỉ ghi qua app (`gold/labels/labels_<X>.csv`, hợp đồng trong `gold_schema.py`), không sửa file pool.

## Ba nhãn, gán ở cấp parent

| Nhãn | Nghĩa |
|---|---|
| **2** | Đúng thứ khách tìm: đúng loại, đúng nơi (nếu câu có nêu nơi) và thoả các điều kiện chấm được. |
| **1** | Liên quan một phần: đúng nơi nhưng sai loại, hoặc thiếu một điều kiện. |
| **0** | Không liên quan, hoặc sai nơi. |

"Loại" là loại sản phẩm khách hỏi: resort, khách sạn, homestay, vé tham quan, chuyến bay, combo…

## Quy tắc chung

- **Không chấm giá, ngày, số khách.** Điều kiện nào có ghi "(kiểm ở cấp room)" trong phần filter thì máy tự kiểm; người gán bỏ qua.
- **Chỉ dựa vào những gì hiện trên màn hình:** tên, loại, nơi, hạng sao, tiện ích, mô tả ngắn, hạng phòng. Không tra web.
- **Luật destination (chốt 25/09).**
  - Câu có nêu destination mà sản phẩm ở sai destination → **0**, kể cả khi đúng loại.
  - Đúng destination nhưng sai loại, hoặc thiếu điều kiện → **1**.

  *Lý do:* khách gõ nơi đến thì sản phẩm ở nơi khác không dùng được. Nếu cho 1, sản phẩm sai nơi sẽ được tính là "liên quan" trong nDCG, và arm kéo sai nơi lên sẽ trông tốt hơn thực tế. Luật này thay câu "đúng loại hoặc đúng nơi → 1" trong spec Part 5 bản cũ.
- **Câu khó hoặc không chắc:** gán theo ý mình, ghi lý do vào `note`. Không bỏ trống.

## Slice parent_child

- Nhãn **2** thì phải tick ít nhất một hạng phòng đúng loại; app không lưu nếu thiếu.
- Không có hạng phòng nào đúng loại → **0**.
- Có hạng phòng gần đúng (ví dụ villa nhưng không có hồ bơi riêng) → **1**, không tick.
- Khách sạn không có danh sách hạng phòng → tối đa **1**, vì không kiểm được.

## Tiện ích

- Sản phẩm **không ghi nhận** một tiện ích vẫn có thể được **2**. Dữ liệu tiện ích không đầy đủ, nên "không ghi" không có nghĩa là "không có".
- **Câu phủ định** ("không có hồ bơi"): sản phẩm *có ghi nhận* tiện ích bị loại trừ → tối đa **1**.
- App hiện tối đa 12 tiện ích. Tiện ích nêu trong filter hoặc trong câu hỏi luôn được xếp lên đầu, nên nếu nó không có trong danh sách thì tức là sản phẩm không ghi nhận tiện ích đó.

## Câu ngoài catalog (out_of_catalog)

Ứng viên thường là **0**. Nếu gặp sản phẩm thật sự đúng, gán theo luật chung, ghi `note` và báo lại: câu đó có thể không còn nằm ngoài catalog, và nó sẽ bị `sb gold check` báo đỏ.

## Năm ví dụ khó (lấy từ fixture `tests/fixtures/gold_small/`)

| Câu | Ứng viên | Nhãn | Lý do |
|---|---|---|---|
| resort ở Nha Trang | Khách sạn Trung Tâm Nha Trang | **1** | Đúng nơi, sai loại (khách sạn công tác, không phải resort). |
| resort ở Nha Trang | Resort Rừng Dừa Phú Quốc | **0** | Đúng loại nhưng sai nơi (luật destination). |
| villa hồ bơi riêng Phú Quốc | Resort Rừng Dừa Phú Quốc (có hạng "Villa Hồ Bơi Riêng") | **2**, tick `R0033` | Phòng hay khách sạn: nhãn gán cho khách sạn, hạng phòng đúng loại phải tick. |
| villa hồ bơi riêng Phú Quốc | Resort Ngọc Trai Phú Quốc (chỉ có "Villa Hướng Vườn", hồ bơi chung) | **1**, không tick | Gần đúng: có villa nhưng không có hồ bơi riêng. |
| khách sạn Đà Nẵng không có hồ bơi | Khách sạn Cầu Rồng Đà Nẵng (không ghi hồ bơi) | **2** | Tiện ích không ghi nhận vẫn được 2. |
| khách sạn Đà Nẵng không có hồ bơi | Khách sạn Mỹ Khê Đà Nẵng (có ghi hồ bơi) | **1** | Câu phủ định: có tiện ích bị loại trừ thì tối đa 1. |
| vé VinWonders Phú Quốc | Combo 2 ngày Vinpearl Safari + VinWonders Phú Quốc | **1** | Combo có kèm vé: có thứ khách tìm nhưng bán theo gói, khác đơn vị. Nếu câu hỏi "combo … có vé VinWonders" thì là **2**. |

## Gán độc lập (để κ đo đúng)

- Mỗi file có khoảng 25 câu chung với người kia, rải trong cả file. **Không tìm, không đoán** câu nào là câu chung: app không hiện điều này, và mọi câu gán cùng một mức cẩn thận.
- Thứ tự câu của A và B khác nhau có chủ đích (B bắt đầu từ slice khác, ứng viên cũng xếp khác), để hai người không gán cùng một câu cùng lúc. Cứ gán theo thứ tự app đưa ra.
- Cho tới khi `sb gold kappa` chạy xong: không trao đổi về từng câu hay ứng viên cụ thể, không mở file pool / nhãn của người kia, không mở `pool_meta.json` (`overlap_qids`) hay cột `is_overlap` trong file pool của mình. Hỏi chung về luật thì được, và luật chốt thêm phải ghi vào file này cho cả hai.
- `sb gold split` mặc định không in qid câu chung; chỉ người không gán nhãn mới dùng `--show-shared`.
- Sau khi có κ, không sửa nhãn của mình chỉ để khớp người kia; chỗ lệch đi qua `sb gold merge` như dưới.

## Hoà nhãn (`sb gold merge`)

- Cặp chung lệch 1 bậc thì merge tự lấy nhãn thấp hơn.
- Cặp lệch 2 bậc, hoặc cả hai gán 2 ở parent_child nhưng không tick chung hạng phòng nào, thì dòng đó có `needs_discussion = true` trong `gold/labels/merged.csv`. Hai người thảo luận rồi sửa ngay trên dòng đó:
  1. điền `label`;
  2. đổi `needs_discussion` thành `false`;
  3. ghi lý do vào `note`;
  4. nếu nhãn là 2 ở parent_child thì ghi `children_ok` (các id cách nhau bằng `;`).

Sau đó chạy `sb gold import` rồi `sb gold check`.
