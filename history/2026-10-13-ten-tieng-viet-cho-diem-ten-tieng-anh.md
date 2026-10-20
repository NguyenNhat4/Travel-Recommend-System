# Tên tiếng Việt cho điểm tham quan trip.com chỉ có tên tiếng Anh, loại 9 bản trùng (mục 2 rà soát production)

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở — job xong; production chưa sửa (gộp với mục 1, sau khi merge vào `release-mvp-v2` + CD crawler deploy)
- Phạm vi: data

## Mục tiêu

Người dùng (13/10): "ok làm mục 2 trước" — mục 2 của `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md`: điểm tham quan
trip.com đang bán chỉ có tên tiếng Anh làm trợ lý gợi ý/lên lịch hiển thị tên khó hiểu. FR-CAT-02, NFR-REL-01. Không lệch PRD (thêm
dữ liệu soát tay theo cơ chế `name_overrides.csv` / `excluded_products.csv` đã có).

## File thay đổi

- `src/data_collection/collectors/name_overrides.csv` — sửa: +33 tên tiếng Việt (tổng 35), evidence ghi tên nguồn, nameEn, URL, địa chỉ.
- `src/data_collection/collectors/excluded_products.csv` — sửa: +9 bản trùng (tổng 54), lý do trỏ tới `source_ref` bản tiếng Việt giữ lại.
- `src/data_collection/tests/test_quality.py` — sửa: test mục 2 (vài tên mẫu, đủ 33 dòng duyệt, 9 bản bị loại trỏ tới bản giữ và bản giữ không
  bị loại, không ref nào vừa đổi tên vừa bị loại, Đảo chè Thanh Chương chưa đổi).
- `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` — sửa: §3 kết quả mục 2, bản xem trước production gộp 61 dòng.
- `history/2026-10-13-ten-tieng-viet-cho-diem-ten-tieng-anh.md` — thêm.

## Quyết định

- Rà production (read-only): 127 search unit `trip:attraction:*` đang bán, tên không có chữ tiếng Việt (121 điểm tham quan + 6 sân golf).
  Với mỗi dòng, tìm điểm tham quan/golf đang bán có tên tiếng Việt trong 400 m để phát hiện bản trùng trước khi đề xuất đổi tên.
- Người dùng duyệt "ok hết, loại cả 5 bản có thể trùng":
  - 33 tên tiếng Việt chỉ cho địa danh có tên tiếng Việt rõ (Động Tiên Sơn, Bãi Kỳ Co, Vườn quốc gia Hoàng Liên…); thương hiệu, du
    thuyền, sân golf giữ nguyên (70); 14 dòng không chắc để trống (liệt kê ở plan §3).
  - Loại 9: 4 bản có bản tiếng Việt cách 2–298 m (Mũi Nai, Ấp Bắc, Bảo Ninh, Hang Tối) + 5 bản "có thể trùng" (Tiên Trang/Quảng Lợi,
    Quảng trường/Tháp Tam Thắng, Chùa Bà Đen/Điện Bà Linh Sơn Thánh Mẫu, Halong Park/Sun World Hạ Long, Hacoconut/Hạnh Coconut).
- `trip:attraction:133828272` "Dao Che Thanh Chuong" chưa đổi tên: tên đúng nhưng toạ độ ở TP Vinh, lệch ~40 km → chuyển mục 4, hỏi người
  dùng ẩn hay sửa toạ độ.
- Câu evidence ghi "không có bản tiếng Việt của cùng điểm trong 400 m" (không phải "không có điểm tên tiếng Việt"): vài điểm đổi tên có
  điểm khác tên tiếng Việt ở gần (vd. Chợ Đông Hà cách Công Viên Lê Duẩn 168 m).

## Kiểm tra

- Hai CSV: 35 / 54 dòng, không trùng `sourceRef`, không dòng thiếu cột; 9 bản giữ không nằm trong danh sách loại.
- `test_quality.py` + `test_normalise_steps.py`: 47 passed. Phá thử: thêm bản giữ `trip:attraction:140139148` (Hang Tối) vào danh sách
  loại → test mục 2 lỗi; trả file lại → qua.
- Bản xem trước production (read-only, dùng `normalise.load_name_overrides` / `apply_name_overrides` / `excluded_reason` trên dữ liệu
  production): đổi tên 35 dòng (34 đổi đầu mô tả; Hang Luồn có mô tả nguồn đã viết "Hang Luồn"), ẩn 26 dòng đang bán (16 ref + 10 hạng
  phòng con) → 61 dòng; cả 35 ref đổi tên có trên DB. Chưa ghi gì.
- Cả suite, bật mọi test DB thật trên DB nháp trong container local (plan §6; DB nháp đã xoá):
  `python -m pytest -q -p no:cacheprovider data_collection/tests` → **707 passed** (0 failed, 0 skipped).

## Còn lại / rủi ro

- Sửa production (61 dòng) sau khi người dùng merge `test/newcrawl` vào `release-mvp-v2` và CD crawler deploy: script xem trước →
  người dùng đồng ý trong chat → ghi → "Bảo trì và index" (35 tên đổi text → embed lại) → rà lại.
- Mục 4: Đảo chè Thanh Chương (toạ độ), Hang Luồn (điểm đến Hải Phòng nhưng mô tả nói đảo Bồ Hòn, vịnh Hạ Long), toạ độ tour Booking /
  khách sạn Trip, Tuyên Quang.
