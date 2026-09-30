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

## Quy ước chốt 30/09 (người dùng chốt sau khi gán xong, trước khi merge / tag `gold_v1`)

Lý do: kiểm 640 cặp chung và 6 câu không có nhãn 2 ngày 30/09 cho thấy các bất đồng đều rơi vào chỗ guide chưa nói rõ. Áp dụng khi sửa `merged.csv` (12 cặp lệch 2 bậc, c0457, c0565) và khi rà lại các slice ghi bên dưới; **không** sửa âm thầm nhãn đã gán ngoài các câu được rà.

| # | Quy ước | Ví dụ | Slice cần rà |
|---|---|---|---|
| 1 | **Địa danh con thuộc tỉnh tính là đúng nơi.** | Cát Bà ⊂ Hải Phòng, Mũi Né ⊂ Phan Thiết, Phong Nha ⊂ Quảng Bình → câu hỏi Cát Bà, sản phẩm ghi destination Hải Phòng, tên "Cat Ba …" → xét như đúng nơi | c0217, no_diacritics |
| 2 | **Đúng nơi nhưng sai loại → 1, kể cả attraction.** | "nơi ở Pleiku" → "Chợ Đêm Pleiku" = **1** (không 0, không 2) | c0136, c0178, dest_type, audience_style |
| 3 | **Câu phủ định là điều kiện bắt buộc (xem #7):** sản phẩm *có ghi* tiện ích bị loại trừ → **0**; không ghi → **2** nếu phần còn lại đúng. | "khách sạn Đà Nẵng không có hồ bơi" → khách sạn có ghi hồ bơi = 0 | amenity_negation (thay luật "tối đa 1" ở mục Tiện ích phía trên cho slice này) |
| 4 | **Tiện ích ngoài danh mục (`amenity_offtaxonomy`): có ghi tiện ích → 2, không ghi → 1.** Luật "không ghi vẫn có thể được 2" ở mục Tiện ích không áp dụng cho slice này. | c0259 (máy cho 2 cả 19/19), c0268 (20/23) → rà lại: không ghi → 1 | amenity_offtaxonomy |
| 5 | **cross_vertical: sản phẩm thuộc một trong các vertical được hỏi và đúng nơi → 2.** | "khách sạn, vé máy bay, vé tham quan và combo ở Nghệ An": một khách sạn Nghệ An = 2 | c0564, c0565, cross_vertical |
| 6 | **"KS" (khách sạn) = mọi `hotel_property`**: khách sạn, nhà nghỉ, homestay, căn hộ, du thuyền. **Resort / KND / KDL** = các resort lớn (khu nghỉ dưỡng), không phải khách sạn thường. | "KS 3 sao Điện Biên" → nhà nghỉ 3 sao = đúng loại; "resort Phú Quốc" → khách sạn phố = sai loại (1) | multi_constraint, abbrev_typo, dest_type |
| 7 | **Điều kiện bắt buộc trong câu phải đúng — chỉ có 2 và 0, không có 1:** (a) câu yêu cầu *không có* một tiện ích → sản phẩm có ghi tiện ích đó = 0 (như #3); (b) **chuyến bay từ A đến B → chỉ tuyến A → B được 2**; tuyến khác (đến B từ nơi khác, hoặc chiều ngược) = **0**, không phải 1. Nhiều chuyến của cùng tuyến A → B đều là 2 (nhãn ở cấp route). | "ve may bay SG di DN": tuyến TP.HCM → Đà Nẵng = 2; Hà Nội → Đà Nẵng = 0; Đà Nẵng → TP.HCM = 0 | abbrev_typo, no_diacritics, cross_vertical (vé máy bay), c0541, c0547, c0202, c0373 |

Quy ước #3/#7 **thay** câu "câu phủ định … tối đa 1" ở mục Tiện ích cho slice `amenity_negation`; các mục khác của guide giữ nguyên.

## Gán độc lập (để κ đo đúng)

- Mỗi file có khoảng 25 câu chung với người kia, rải trong cả file. **Không tìm, không đoán** câu nào là câu chung: app không hiện điều này, và mọi câu gán cùng một mức cẩn thận.
- Thứ tự câu của A và B khác nhau có chủ đích (B bắt đầu từ slice khác, ứng viên cũng xếp khác), để hai người không gán cùng một câu cùng lúc. Cứ gán theo thứ tự app đưa ra.
- Cho tới khi `sb gold kappa` chạy xong: không trao đổi về từng câu hay ứng viên cụ thể, không mở file pool / nhãn của người kia, không mở `pool_meta.json` (`overlap_qids`) hay cột `is_overlap` trong file pool của mình. Hỏi chung về luật thì được, và luật chốt thêm phải ghi vào file này cho cả hai.
- `sb gold split` mặc định không in qid câu chung; chỉ người không gán nhãn mới dùng `--show-shared`.
- Sau khi có κ, không sửa nhãn của mình chỉ để khớp người kia; chỗ lệch đi qua `sb gold merge` như dưới.

## Nhãn máy và duyệt (29/09)

Theo quyết định của người dùng ngày 29/09: phần còn trống của các **câu riêng** được máy gán (Claude, theo đúng file này), người duyệt lại trong app.

- **Câu chung không bao giờ có nhãn máy.** Chúng dành cho người gán, để κ vẫn đo độ đồng thuận giữa hai người.
- Nguồn từng nhãn lưu ở `gold/labels/provenance_<X>.csv`, cạnh file nhãn: nhãn và lý do gốc của máy, model, người duyệt, thời điểm, và kiểu duyệt (`accepted` = tick đồng ý, `edited` = đã sửa). File nhãn giữ nguyên định dạng, nên `kappa` / `merge` / `import` không đổi.
- **Cách duyệt trong app:**
  1. Nhập **tên người duyệt** ở sidebar.
  2. **Lọc câu → "Có nhãn máy chưa duyệt"**; câu có nhãn máy chưa duyệt có dấu 🤖.
  3. Trong bảng: **Hiện dòng → "Máy gán"**, rồi xem cột *lý do máy*.
  4. Đồng ý thì **tick cột "duyệt"**; không đồng ý thì **sửa nhãn** (ghi nhận là đã sửa, không cần tick).
  5. Bấm **Lưu**, hoặc chuyển câu để tự lưu.
- **Duyệt tất cả nhãn máy của câu** (nút cạnh Lưu): chấp nhận mọi nhãn máy chưa duyệt của câu đang mở, sau khi lưu các sửa còn dở (nhãn vừa sửa vẫn ghi là đã sửa). Chỉ bấm sau khi đã xem hết các dòng máy gán của câu.
- Bỏ tick = về chưa duyệt. Cột *nguồn* cho biết: `máy · chưa duyệt`, `máy · duyệt: <tên>`, `máy → sửa: <tên>`, `người`.
- Khi duyệt nhãn máy trong file của người kia, chỉ mở các câu có 🤖 (câu riêng), không mở câu chung của họ trước khi có κ.

## Hoà nhãn (`sb gold merge`)

- Cặp chung lệch 1 bậc thì merge tự lấy nhãn thấp hơn.
- Cặp lệch 2 bậc, hoặc cả hai gán 2 ở parent_child nhưng không tick chung hạng phòng nào, thì dòng đó có `needs_discussion = true` trong `gold/labels/merged.csv`. Hai người thảo luận rồi sửa ngay trên dòng đó:
  1. điền `label`;
  2. đổi `needs_discussion` thành `false`;
  3. ghi lý do vào `note`;
  4. nếu nhãn là 2 ở parent_child thì ghi `children_ok` (các id cách nhau bằng `;`).

Sau đó chạy `sb gold import` rồi `sb gold check`.
