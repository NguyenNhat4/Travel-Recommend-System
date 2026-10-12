# Gói nhiều ngày hiện hai lần vì tên chỉ đảo thứ tự: lọc trùng bằng luật

- Ngày: 2026-10-09
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Câu "ddi ddau ma no hoang da 1 xiu" (trace LangSmith `01a11f41-9b75-76a3-b2f9-e8ba675d9d0c`, project `nhat-10-7`): mục "Gói
nhiều ngày để bạn cân nhắc riêng" hiện hai gói như nhau:
"[02 ngày không giới hạn] - VinWonders + Vinpearl Safari Phú Quốc + Bảo Tàng Gấu Teddy" (`07594eb2…`) và
"[02 ngày không giới hạn] - Vinpearl Safari + VinWonders Phú Quốc + Bảo Tàng Gấu Teddy" (`baa6f8cf…`). Hai mã khác nhau, cùng
giá 2.040.000 đ, cùng cửa sổ bán, ảnh cùng tên file.

Nguyên nhân:
1. Vinpearl bán một gói dưới hai mã, chỉ đảo thứ tự "VinWonders" và "Vinpearl Safari".
2. Gói nhiều ngày không đi qua bước lọc trùng của node `filter`; bước này chỉ lọc điểm tham quan xếp được vào buổi. Gói vào
   thẳng danh sách gợi ý riêng.
3. Luật cùng tên cũng không bắt được ca này vì thứ tự từ khác.

Phục vụ FR-AGT-03, FR-AGT-04, AC-AGT-04. Không lệch PRD: PRD không mô tả danh sách gói nhiều ngày; chỉ spec
`nghiep-vu/xep-lich.md` ghi gói nhiều ngày không qua bước lọc, nay sửa theo.

## File thay đổi

- `src/backend/app/domain/itinerary/dedupe.py` — sửa:
  - thêm `multi_day` (gói nhiều ngày);
  - `same_name_pairs` nhận `any_order` (so các từ, không kể thứ tự);
  - `apply_pairs` nhận `pool` (mặc định `filterable`, nên cặp của LLM vẫn chỉ áp lên điểm tham quan).
- `src/backend/app/agents/steps/filtering.py` — sửa: `ruled` lọc thêm gói nhiều ngày với nhau bằng luật cùng các từ.
- `src/backend/tests/unit/domain/test_itinerary_dedupe.py` — thêm `MultiDayPassTests` (2 test).
- `src/backend/tests/unit/agents/test_filter_node.py` — thêm test gói bán hai lần bị luật bỏ, không gửi cho LLM.
- `docs/spec/agent/nghiep-vu/xep-lich.md` — sửa: mục "Không lặp một nơi" ghi luật cho gói nhiều ngày.

## Quyết định

- Dùng luật, không dùng LLM: so cùng bộ từ là kiểm tra tất định, đủ cho dữ liệu đang có, và không tốn thêm thời gian gọi LLM.
- Chỉ so gói với gói. Gói không bị bỏ vì trùng một vé lẻ, vì gói được gợi ý riêng, không chiếm buổi nào trong lịch.
- Không đòi cùng giá. Catalog có cặp "[Combo 02 ngày] …" cùng bộ từ nhưng giá 1.300.000 / 1.700.000 đ. Cặp này là taxonomy
  `combo` nên hiện không hiện ở mục gói. Nếu sau này gặp ca như vậy, thứ tự giữ hiện có vẫn giữ gói rẻ hơn.
- Giữ mã nào theo `keep_rank` như các cặp trùng khác. Mã bị bỏ có cảnh báo `PRODUCT_DROPPED_DUPLICATE` và vào mục "Đã loại"
  của eval với `by = rule`.
- Luật cùng tên cho điểm tham quan xếp vào buổi giữ nguyên (so cả thứ tự từ), đúng câu chữ AC-AGT-04. Vé lẻ đảo thứ tự tên
  vẫn do bước LLM bắt.

## Kiểm tra

- Test mới fail trên code cũ: `test_itinerary_dedupe.py` lỗi import `multi_day`; ở `test_filter_node.py`, test gói bán hai
  lần FAIL.
- `.venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests/unit/domain/test_itinerary_dedupe.py src/backend/tests/unit/agents/test_filter_node.py`: 20 passed.
- `.venv/bin/python -m pytest -q -p no:cacheprovider src/backend/tests`: 2594 passed, 36 skipped.
- Chạy lại bước luật trên đúng state của node `filter` lấy từ trace:
  - mục gói nhiều ngày từ 2 gói còn 1 (giữ `07594eb2…`, mã nhỏ hơn khi cùng nguồn và cùng giá);
  - vé Water Taxi trùng vẫn bị bỏ như trước.
- Quét catalog local (`cdp.products`, 17.118 dòng): có 84 gói nhiều ngày thuộc `attraction`/`golf`, trong đó 5 cặp cùng bộ
  từ. Cả 5 đều ở Phú Quốc, đều là kiểu đảo "VinWonders + Vinpearl Safari", không có cặp nào ghép nhầm.
- Tầng bằng chứng: unit/fixture tất định, cộng thêm bước luật chạy trên state thật của trace. **Chưa chạy** lại hội thoại với
  LLM thật và chưa xem trên trình duyệt.

## Còn lại / rủi ro

- Phía dữ liệu: 5 cặp gói (cùng các cặp `combo` đảo tên) nên được gộp ở bước nạp catalog. Phần đó là việc của nhóm Data,
  chưa làm.
