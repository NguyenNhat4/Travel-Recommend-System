# Ẩn thêm 22 điểm thu phí thương hiệu không giá; job tự ẩn chưa làm (lệch PRD, tạm dừng)

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: dang dở — đợt 2 nhóm A xong phía job; job tự ẩn chưa làm (cần đề xuất PRD), người dùng tạm dừng; production chưa sửa
- Phạm vi: data

## Mục tiêu

Người dùng (13/10): "làm luôn mục 1 và 2 còn mở" sau `history/2026-10-13-an-golf-va-diem-thu-phi-khong-gia.md`:
(1) job tự ẩn golf/điểm thu phí không giá ở lượt cào sau; (2) xét điểm thương hiệu không giá ngoài bộ từ khoá (Red Dragon Junk, Mango
Cruises, MADALAND, CaraWorld, trại voi…). Sau đó người dùng: "Tạm thời dừng ở đây". FR-CAT-01, FR-CAT-03, NFR-REL-01.

## File thay đổi

- `src/data_collection/collectors/excluded_products.csv` — sửa: +22 (tổng 143), lý do "điểm thu phí không có giá…", ghi "đợt 2".
- `src/data_collection/tests/test_quality.py` — sửa: test A/B đếm 58 điểm thu phí (36 + 22), kiểm thêm 3 ref đợt 2.
- `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` — sửa: §4a đợt 2, trạng thái việc 1, số xem trước 191 dòng.
- `history/2026-10-13-an-diem-thu-phi-thuong-hieu-khong-gia.md` — thêm.

## Quyết định

- Việc 2 (không lệch PRD, cùng tiêu chí "chắc thu phí" người dùng đã chốt): rà 142 điểm không giá theo từ khoá mở rộng → ẩn 22: dù lượn
  (Sapa Paragliding, Khau Phạ, Tam Đảo, Dateh), xe trượt Alpine Coaster (Sa Pa, Bà Nà), The Wrath of Zeus, Vinpearl Submarine, Red Dragon
  Junk, Mango Cruises, Mr. Biker Bentre, Vanlong Elephants Farm, Green Elephant Camp, trại ngựa Măng Đen, Puppy Farm, trại rắn Đồng Tâm,
  trại cá sấu Long Xuyên, MADALAND, Ozo Park, Khu du lịch Cửa Biển (Seagate theme park), Sunset Sanato Beach Club, phim trường Kong Skull
  Island (tuyến thuyền Tràng An). Giữ (không chắc): ~45 "khu du lịch / sinh thái", ~17 farm, CaraWorld, K'Bin Camp, Everland, nhà hát,
  đảo, tượng voi — chờ người dùng.
- Việc 1 là **lệch PRD**: `docs/prd/architecture.md` §3 ghi "điểm tham quan hoặc golf … không có giá — tính 0 đ … tham quan tự do", tức
  PRD coi golf/điểm không giá là mục được hiển thị; job tự ẩn làm điều khoản đó hết hiệu lực → theo AGENTS.md §8 phải có đề xuất trong
  `docs/prd/update/` được chốt trước. Chưa viết đề xuất (người dùng tạm dừng). Hướng đã nêu ở plan §4a.

## Kiểm tra

- `test_quality.py`: 35 passed.
- Cả suite, bật mọi test DB thật trên DB nháp local (plan §6; DB nháp đã xoá):
  `python -m pytest -q -p no:cacheprovider data_collection/tests` → **710 passed** (0 failed, 0 skipped).
- Xem trước production (read-only): đổi tên 34, ẩn 115 (11 hạng phòng), đổi điểm đến 16 + 26 hạng phòng con → **191 dòng**; 0 thành phần
  combo, 0 dòng đơn hàng trỏ vào dòng sắp ẩn; cộng nạp 40 điểm Tuyên Quang (đợt `4tq`). Chưa ghi gì.

## Còn lại / rủi ro

- Việc 1: viết đề xuất PRD "không bán golf / điểm thu phí khi chưa có giá" → chờ chốt → sửa `normalise.py` + test + tài liệu.
- Hỏi người dùng về nhóm "khu du lịch / sinh thái", farm, CaraWorld, K'Bin Camp, Everland, nhà hát.
- Sửa production 191 dòng + nạp 40 điểm sau merge + deploy (hỏi trước khi ghi), rồi "Bảo trì và index".
