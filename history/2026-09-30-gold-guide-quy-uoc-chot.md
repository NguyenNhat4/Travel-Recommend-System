# Gold guide: 7 quy ước chốt ngày 30/09 trước khi merge / tag `gold_v1`

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Sau khi hai người gán xong (κ 0,692), kiểm 640 cặp chung và 6 câu không có nhãn 2 cho thấy bất đồng nằm ở chỗ guide chưa
nói rõ (địa danh con, đúng nơi sai loại với attraction, phủ định, tiện ích ngoài danh mục, cross_vertical, nghĩa của
"KS", tuyến bay). Người dùng chốt 7 quy ước; ghi vào guide để dùng khi sửa `merged.csv` và rà lại slice trước tag.
Phục vụ FR-SRC-01..04, AC-SRC-01.

## File thay đổi

- `docs/spec/bench/gold-guide.md` — sửa: thêm mục "Quy ước chốt 30/09" (bảng 7 quy ước, ví dụ, slice cần rà).

## Quyết định

- Quy ước #7 (điều kiện bắt buộc chỉ có 2 / 0) **thay** luật "phủ định → tối đa 1" cho slice `amenity_negation`; tuyến bay
  A → B: chỉ đúng tuyến được 2, tuyến khác 0.
- `amenity_offtaxonomy`: không ghi tiện ích → 1 (khác luật chung "không ghi vẫn có thể 2").
- Không sửa nhãn đã gán hàng loạt; chỉ rà các câu / slice ghi trong bảng, sửa trong `merged.csv` (câu chung) hoặc app.

## Kiểm tra

- Không có code. Đối chiếu với audit 30/09 (`docs/plan/2026-09-30-bench-search-recsys-3-ngay.md` §1 D6).

## Còn lại / rủi ro

- A1/A2 rà: c0136, c0178, c0217, c0259, c0268, c0457, c0463 (retire), c0503, c0564, c0565, các câu vé máy bay (c0541,
  c0547, c0202, c0373) và slice amenity_negation của A (đang cho 0/1 theo luật cũ → quy về 2/0).
- Sau `gold_v1` không sửa nhãn được nữa.
