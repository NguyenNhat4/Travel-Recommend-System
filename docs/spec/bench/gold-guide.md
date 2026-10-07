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
| 4 | **Tiện ích ngoài danh mục (`amenity_offtaxonomy`): có ghi rõ tiện ích → 2; không ghi, thiếu thông tin hoặc mô tả chưa rõ ràng (không kết luận được có/không) → 1.** Luật "không ghi vẫn có thể được 2" ở mục Tiện ích không áp dụng cho slice này. *(Làm rõ tối 30/09 khi rà: "chưa rõ ràng" xử như "không ghi" — đều 1, không suy đoán từ hạng sao/loại sản phẩm.)* | c0259 (máy cho 2 cả 19/19), c0268 (20/23) → rà lại: không ghi → 1 | amenity_offtaxonomy |
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

## Rubric v4 — áp dụng cho câu từ `gold_v4` (người dùng chốt 05/10)

**Phạm vi (sửa 06/10, người dùng chốt).** Áp dụng cho **mọi nhãn gán từ `gold_v4` trở đi**: câu mới (qid từ `c0673`, `gold/v4a/`) **và hole của câu cũ** (từ đợt D9a). Nhãn đã có trong `gold_v1`–`gold_v3` giữ nguyên theo các mục phía trên (gold chỉ được thêm, spec Part 11, không gán lại) — nên trong một câu cũ, nhãn 1 cũ cho "đúng nơi sai loại" (quy ước #2) và nhãn 0 mới cho cùng tình huống **cùng tồn tại** (06/10: 161 cặp nhãn 1 cũ / 34 câu). Hợp nhất (người dùng chốt 06/10, phương án b): **chiếu rubric v4 lúc chấm** — mỗi câu có `allowed_variants` trong `config/query_annotations.yaml`; evaluator (`metrics.project_rubric_v4`, bật bằng `metrics.rubric_v4_projection`) tính nhãn ≥ 1 của sản phẩm ngoài danh sách là 0, gold.jsonl không đổi. Report ghi `rubric_v4_projection {pairs, queries}` của results.json. Nguồn: đề xuất `docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md` §4 (D1) và kế hoạch `docs/plan/2026-10-05-gold-v4a-mo-rong.md`.

| Nhãn | Nghĩa (rubric v4) |
|---|---|
| **2** | Đúng thứ khách tìm: đúng **loại sản phẩm cốt lõi**, đúng nơi / đúng tuyến và chiều bay, thoả mọi ràng buộc cứng chấm được. |
| **1** | Gần đúng: đúng loại và đúng nơi nhưng thiếu một **điều kiện mềm**, hoặc là phương án thay thế mà **chính sách của câu** (bảng cuối mục này) cho phép. |
| **0** | Không liên quan, hoặc vi phạm **ràng buộc cứng**: sai nơi, sai chiều bay, **sai loại sản phẩm cốt lõi**, vi phạm loại trừ / thương hiệu khách nêu, có ghi tiện ích khách loại trừ. |

**Khác rubric v3:** "đúng nơi nhưng sai loại" là **0** (v3: 1, quy ước #2), trừ khi chính sách của câu cho phép 1.

**Ràng buộc cứng / mềm.**
- Cứng (vi phạm → 0): điểm đến hoặc tuyến bay và chiều; loại sản phẩm khách hỏi; tiện ích bị phủ định ("không có X") mà sản phẩm có ghi; loại trừ rõ ("vé lẻ", "không lấy combo", "không phải …"); thương hiệu khách nêu tên.
- Mềm (thiếu → 1): tiện ích yêu cầu dương ("có X") không được ghi nhận; vị trí cụ thể trong tỉnh ("ở Grand World") chưa thể hiện.
- **Loại cốt lõi = `variant` catalog** (`hotel_property` / `attraction` / `combo` / `flight_route` / `golf`), theo từ ngành dọc trong câu (khách sạn / chỗ nghỉ / resort / KS / KDL → hotel_property; vé tham quan / điểm vui chơi / VinWonders → attraction; combo → combo; vé máy bay → flight_route; golf → golf). Khác **subtype trong cùng variant** (resort / khách sạn / homestay / căn hộ; thương hiệu khác khi câu nêu thương hiệu dương) = 1. Phương án thay thế rubric cho **1** (không phải vi phạm cứng): combo / passport có kèm vé cho câu hỏi vé và vé lẻ thành phần cho câu hỏi combo (#10, hai chiều — trừ combo vé máy bay + khách sạn như c0706: vé bay lẻ / KS lẻ = 0), combo khứ hồi cho câu vé máy bay (#8d). Câu `cross_vertical`: mọi vertical được nêu đều đúng loại. Câu tên POI hoặc không có từ ngành dọc ("hoạt động trải nghiệm", "gói vui chơi"): đúng loại = loại của sản phẩm đúng.
- **Sao** (câu `multi_constraint` có "N sao"): dưới ngưỡng = **0** (ràng buộc cứng, đề xuất v4 §4.1; v3 cho 1); không khai sao = 1, `note` bắt đầu `unknown_metadata:`.
- Giá, ngày, số khách: **không chấm** — app không hiện giá; giá máy kiểm qua `child_filter`.

**Thứ tự quyết định** (đề xuất v4 §4.2): sai ràng buộc cứng → 0, dù rất giống câu hỏi; qua hết ràng buộc cứng → đúng ý định thì 2, là phương án thay thế được chính sách cho phép hoặc thiếu điều kiện mềm thì 1. **Không có trạng thái "review"**: luôn gán 0 / 1 / 2; không chắc thì gán theo luật và ghi `note` bắt đầu bằng `unknown_metadata:`.

### Quy ước chốt 05/10 (#8–#14, áp dụng cho câu từ gold_v4)

| # | Quy ước |
|---|---|
| 8 | **Vé máy bay.** (a) Có điểm đi và điểm đến: chỉ tuyến đúng chiều A → B = 2, kể cả nhiều sản phẩm cùng tuyến; chiều ngược và tuyến khác = 0. (b) Chỉ có điểm đến B: mọi tuyến **vào** B = 2, tuyến ra từ B = 0. (c) Chỉ có điểm đi A: mọi tuyến **ra** từ A = 2, tuyến vào A = 0. (d) Combo "vé máy bay khứ hồi X - Y + phòng" = 1 nếu {X, Y} chứa đúng cặp / đầu mút khách hỏi; combo khác = 0. (e) Khách sạn, vé tham quan cho câu hỏi vé máy bay = 0. |
| 9 | **Golf:** voucher golf = tee time = một loại; sản phẩm `golf` có giá ở đúng điểm đến = 2. Sân golf không có giá (POI) = 1 với câu muốn mua, = 2 với câu hỏi địa điểm. So theo `destination`, không theo tỉnh. |
| 10 | **Combo và vé lẻ:** hỏi vé → combo / passport có kèm đúng vé đó = 1; hỏi combo → vé lẻ thành phần = 1. **Loại trừ rõ** ("vé lẻ", "không lấy combo", "không phải Vinpearl") là ràng buộc cứng: vi phạm = 0. Vé đa khu chấm theo loại trong catalog (`attraction`). |
| 11 | **"Có X" và "gần X":** "có X" chỉ tính khi X **được ghi** trong danh sách tiện ích. Chuỗi "Không có …" và chuỗi khoảng cách tới nơi khác ("… 570 m", "… 1,6 km") không phải tiện ích (catalog bench đã bỏ hai loại chuỗi này từ 05/10). "Gần X": tên / mô tả nói rõ vị trí thì 2, không nói thì 1. |
| 12 | **Property và phòng:** nhãn ở cấp parent; hạng phòng chỉ xét ở slice `parent_child`; vé máy bay gán nhãn ở cấp tuyến. |
| 13 | **Ngoài catalog:** chỉ là out_of_catalog khi không sản phẩm nào có thể được 1 / 2, kể cả xét địa danh con và tên tỉnh cũ / mới (sau sáp nhập 2025). Mọi ứng viên = 0. |
| 14 | **Phủ định khi thiếu dữ liệu:** sản phẩm **không ghi** tiện ích bị phủ định vẫn đạt 2 nếu phần còn lại đúng; có ghi → 0. Không dùng phủ định cho `ocean_view` / `family_friendly` (dữ liệu không có giá trị false). "Phòng không hút thuốc" là yêu cầu dương. |

### Chính sách từng câu gold_v4a (bản đầy đủ trong `gold/v4a/drafts_raw.tsv`, cột `review_note`)

| qid | Câu | 2 | 1 | 0 |
|---|---|---|---|---|
| c0673 | khách sạn Sa Pa có spa nhưng không có hồ bơi | chỗ nghỉ Sa Pa có ghi spa, không ghi hồ bơi | không ghi spa, không ghi hồ bơi | có ghi hồ bơi; sai nơi; không phải chỗ nghỉ |
| c0676 | chỗ nghỉ ở TP. Hồ Chí Minh có xe đưa đón sân bay, không có hồ bơi | có ghi đưa đón sân bay, không ghi hồ bơi | không ghi cả hai | có ghi hồ bơi; sai nơi |
| c0679 | khách sạn Hội An có hồ bơi nhưng không có dịch vụ đưa đón sân bay | có ghi hồ bơi, không ghi đưa đón | không ghi cả hai | có ghi đưa đón sân bay; sai nơi |
| c0682 | chỗ nghỉ Đà Lạt có nhà hàng, không có hồ bơi | có ghi nhà hàng, không ghi hồ bơi | không ghi cả hai | có ghi hồ bơi; sai nơi |
| c0685 | khách sạn ở Phú Quốc có hồ bơi nhưng không có nhà hàng | có ghi hồ bơi, không ghi nhà hàng | không ghi cả hai | có ghi nhà hàng; sai nơi |
| c0688 | khách sạn Huế có hồ bơi, không có spa | có ghi hồ bơi, không ghi spa | không ghi cả hai | có ghi spa; sai nơi |
| c0691 | chỗ nghỉ Quy Nhơn có hồ bơi nhưng không có quầy bar | có ghi hồ bơi, không ghi bar | không ghi cả hai | có ghi bar; sai nơi |
| c0694 | khách sạn Đà Nẵng có hồ bơi, không có phòng gym | có ghi hồ bơi, không ghi phòng gym | không ghi cả hai | có ghi phòng gym; sai nơi |
| c0697 | khách sạn ở Grand World Phú Quốc | chỗ nghỉ ở Grand World Phú Quốc (tên / mô tả nói rõ) | chỗ nghỉ Phú Quốc khác | vé, combo vui chơi (Grand World, VinWonders, Safari); sai nơi |
| c0700 | vé vui chơi ở Grand World Phú Quốc | vé / trải nghiệm / show tại Grand World Phú Quốc | combo, passport có kèm Grand World Phú Quốc | khách sạn (kể cả tên có Grand World); vé Grand World Hà Nội; vé chỉ có VinWonders / Safari |
| c0703 | vé lẻ VinWonders Nam Hội An, không lấy combo | vé vào cửa VinWonders Nam Hội An bán lẻ (kể cả kèm buggy / voucher ẩm thực tặng) | dịch vụ thêm trong VinWonders (buggy, fastpass, tour) không có vé vào cửa | combo (loại trừ rõ); khách sạn; sai nơi |
| c0706 | combo vé máy bay và khách sạn Đà Lạt | combo vé máy bay + phòng ở Đà Lạt | — | tuyến bay lẻ vào Đà Lạt; khách sạn lẻ; combo không có vé bay |
| c0709 | khách sạn Vinpearl ở Nha Trang | chỗ nghỉ thương hiệu Vinpearl ở Nha Trang (gồm Meliá Vinpearl Cam Ranh) | chỗ nghỉ Nha Trang thương hiệu khác | vé VinWonders / Vinpearl Harbour, golf, combo; sai nơi |
| c0712 | vé máy bay Sài Gòn đi Đà Nẵng | tuyến TP. Hồ Chí Minh → Đà Nẵng | combo khứ hồi TP. Hồ Chí Minh - Đà Nẵng | chiều ngược; tuyến khác; không phải vé bay |
| c0715 | vé máy bay Cần Thơ đi Hà Nội | tuyến Cần Thơ → Hà Nội (cả 2 sản phẩm) | combo khứ hồi Cần Thơ - Hà Nội | chiều ngược; tuyến khác |
| c0718 | vé máy bay Côn Đảo về TP. Hồ Chí Minh | tuyến Côn Đảo → TP. Hồ Chí Minh | combo khứ hồi Côn Đảo - TP. Hồ Chí Minh | tuyến khác |
| c0721 | vé máy bay đi Côn Đảo | mọi tuyến vào Côn Đảo | combo khứ hồi có Côn Đảo | tuyến ra từ Côn Đảo; tuyến khác |
| c0724 | các chuyến bay xuất phát từ Cần Thơ | mọi tuyến ra từ Cần Thơ | combo khứ hồi có Cần Thơ | tuyến vào Cần Thơ; tuyến khác |
| c0727 | vé máy bay đến Phú Quốc | mọi tuyến vào Phú Quốc | combo khứ hồi có Phú Quốc | tuyến ra từ Phú Quốc; tuyến khác |
| c0730–c0733 | khách sạn ở Lạng Sơn · resort Bạc Liêu · tour hồ Ba Bể · homestay Tà Xùa | — | — | mọi ứng viên (#13) |

### Một người gán và nhãn máy (D5, D6 — 05/10)

- **Người gán duy nhất: QAnh**, gán cả `pool_A.csv` và `pool_B.csv` của `gold/v4a/` (chọn người gán A rồi B trong app). Không có câu chung (`split --overlap 0`), nên không đo κ. Thay vào đó report ghi tỉ lệ nhãn máy được duyệt giữ nguyên / bị sửa, theo slice.
- **Nhãn máy được phép** cho mọi cặp, cả nhãn 1 / 2: luật tất định (`rule:v4a`, từ dữ liệu catalog: tuyến bay, tiện ích đã làm sạch, out_of_catalog) và Claude (theo đúng file này). Nhãn máy hiện là `máy · chưa duyệt`; duyệt như mục "Nhãn máy và duyệt (29/09)". Note của nhãn máy có thể chứa `⚠` khi hai nguồn máy không khớp — xem kỹ các dòng đó.
- `sb gold import --append` **từ chối** nhãn máy chưa duyệt (trừ khi chạy với `--accept-unreviewed`); provenance trong gold ghi rõ nguồn: `pool@gold_v4` (người, hoặc máy bị người sửa), `pool:machine@gold_v4` (máy, người duyệt giữ nguyên).
