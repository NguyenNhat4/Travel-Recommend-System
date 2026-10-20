# Ẩn sân golf và điểm thu phí không giá, ẩn bản đắt của tour Booking trùng tên (mục còn treo rà soát production)

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở — job xong; production chưa sửa (169 dòng + nạp 40 điểm, sau khi merge vào `release-mvp-v2` + CD crawler deploy)
- Phạm vi: data

## Mục tiêu

Người dùng (13/10): "mục còn treo, giải quyết giúp tôi, hỏi tôi nếu cần" — hai mục treo của
`docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md`: 2 cặp tour Booking cùng tên; nhóm A/B (điểm thu phí và sân golf không giá bị
trợ lý tính 0 đ). FR-CAT-01, FR-CAT-03, FR-AGT-04, NFR-REL-01. Không lệch PRD: chỉ ẩn dữ liệu theo cơ chế `excluded_products.csv`; quy tắc
"không giá = tham quan tự do" của `docs/prd/architecture.md` §3 giữ nguyên.

## File thay đổi

- `src/data_collection/collectors/excluded_products.csv` — sửa: +55 (tổng 121): 17 sân golf không giá, 36 điểm thu phí không giá, 2 tour
  Booking bản đắt hơn.
- `src/data_collection/collectors/name_overrides.csv` — sửa: bỏ `trip:attraction:142507515` ("Lantern Making Class" → "Lớp học làm đèn lồng
  Hội An", duyệt sáng 13/10) vì nay bị ẩn (tổng 34 dòng).
- `src/data_collection/tests/test_quality.py` — sửa: số tên duyệt 13/10 còn 32; test mới A/B (17 golf, 36 điểm, bản giữ: golf/cáp treo có
  giá, Grand World, bảo tàng; tour rẻ hơn giữ; không ref nào vừa đổi tên vừa bị ẩn).
- `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` — sửa: §4a quyết định, số cuối của đợt sửa production; §3, §4, §5 cập nhật.
- `history/2026-10-13-an-golf-va-diem-thu-phi-khong-gia.md` — thêm.
- Ngoài repo: `attractions-fill-20261012/trip_poi_wave4tq/drop_4tq.txt` +1 (khoáng nóng Mỹ Lâm Hà Phú), đợt `4tq` dựng lại còn 40 điểm.

## Quyết định

- Đọc code: `src/backend/app/domain/itinerary/planning.py` `free_to_visit` coi điểm tham quan/golf không giá là "tham quan tự do" (chốt
  01/10, PRD architecture §3); agent thêm cảnh báo chung "một số nơi có thể thu phí tại chỗ". Đề xuất đang chờ chốt
  `docs/prd/update/2026-10-08-ung-vien-da-dang-va-diem-mien-phi.md` giữ nguyên quy tắc này.
- Nguồn không phân biệt miễn phí / có vé: 1.753 điểm không giá đều từ trip.com, không dòng nào có `ticketed`; HTML gốc có `isFree` —
  `true` hiếm nhưng đúng (Hồ Hoàn Kiếm, Phố cổ Hà Nội), `false` gắn cả nơi miễn phí ("Sông Nho Quế") → không tự suy được.
- Đã nêu hai hướng (ẩn / đề xuất PRD "chưa có giá"); người dùng chọn ẩn cho cả golf và nhóm A, giữ bảo tàng.
- Nhóm A: 85 dòng theo từ khoá → duyệt tay → 36 ẩn; giữ 40 bảo tàng + 9 nơi có thể miễn phí (liệt kê ở plan §4a).
- Tour cùng tên: hai sản phẩm khác mã, giá, mô tả; người dùng chọn ẩn bản đắt hơn (`przjecq6mcez` 1.904.000 ₫, `pr5d00274odq` 2.577.000 ₫).
- Danh sách ẩn là tĩnh theo `sourceRef`; golf/điểm thu phí không giá mới của lượt cào sau chưa được xử lý tự động (không đổi job khi chưa hỏi).

## Kiểm tra

- `test_quality.py`: 35 passed.
- Cả suite, bật mọi test DB thật trên DB nháp local (plan §6; DB nháp đã xoá):
  `python -m pytest -q -p no:cacheprovider data_collection/tests` → **710 passed** (0 failed, 0 skipped).
- Xem trước production (read-only, `normalise` của worktree): đổi tên 34, ẩn 93 (11 hạng phòng), đổi điểm đến 16 + 26 hạng phòng con →
  169 dòng; 0 thành phần combo, 0 dòng đơn hàng trỏ vào dòng sắp ẩn. `load_attractions.py` đợt `4tq`: `{'new': 40}`, demo_data `changed=0`.
  Chưa ghi gì.

## Còn lại / rủi ro

- Sửa production sau merge + deploy (hỏi trước khi ghi), rồi "Bảo trì và index".
- Hỏi người dùng nếu muốn: điểm thương hiệu không giá ngoài bộ từ khoá (Red Dragon Junk, Mango Cruises, MADALAND, CaraWorld, trại voi…);
  job tự ẩn golf không giá ở lượt cào sau.
