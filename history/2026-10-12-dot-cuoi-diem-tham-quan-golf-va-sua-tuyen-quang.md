# Đợt cuối 12/10: điểm tham quan Đồng Tháp/Quảng Ngãi/Sóc Trăng, sân golf, ẩn 5 điểm rác, sửa điểm đến Tuyên Quang

- Ngày: 2026-10-12
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`); người dùng tự mở PR vào `release-mvp-v2`
- Trạng thái: dang dở (dữ liệu đã nạp + index trên production; bộ cào còn hàng đợi, xem "Còn lại"; plan bàn giao
  `docs/plan/2026-10-12-ban-giao-lam-giau-diem-tham-quan.md`)
- Phạm vi: data
- Trước: `history/2026-10-12-nap-diem-tham-quan-moi-thanh-pho-va-sua-du-lieu-production.md` (đợt 2, 3a–3g),
  `history/2026-10-12-job-cao-giu-du-lieu-sua-tren-production.md` (sửa job)

## Mục tiêu

Người dùng: "bổ sung điểm tham quan cho Đồng Tháp, Quảng Ngãi, Sóc Trăng", "tôi muốn bổ xung thêm golf, hiện tại nó ít quá",
"ok gộp luôn golf vào đợt cuối đi", "ok làm đợt cuối luôn đi"; sau soát dữ liệu: "ok sửa luôn cả 2 mục trong đợt cuối đi" (ẩn 5
điểm rác; sửa điểm đến Tuyên Quang). Issue #159. FR-CAT-01, FR-CAT-03, NFR-REL-01 (chỉ dữ liệu thật từ vn.trip.com qua bộ cào
của repo, tôn trọng robots).

## File thay đổi

- `src/data_collection/collectors/geo.py` — sửa: thêm tâm `DESTINATION_CENTERS["Tuyên Quang"]` (TP. Tuyên Quang). Tuyên Quang là
  điểm đến duy nhất có alias mà thiếu tâm: không kiểm được toạ độ, bộ cào BFS và bước gán điểm đến theo tâm bỏ qua nó.
- `src/data_collection/tests/test_plan.py` — sửa: test mọi điểm đến có alias phải có tâm (và ngược lại).
- `src/data_collection/collectors/excluded_products.csv` — sửa: thêm 5 điểm đã ẩn (khu vui chơi trong TTTM, công ty lữ hành),
  tổng 37 dòng.
- `src/data_collection/tests/test_quality.py` — sửa: test danh sách loại có thêm 2 mã mới (27 điểm ẩn ngày 12/10).
- `docs/plan/2026-10-12-ban-giao-lam-giau-diem-tham-quan.md` — thêm: plan bàn giao cho phiên sau (trạng thái, việc sau lượt
  cào 08:35, đưa sửa job lên VM, quy trình một đợt nạp, việc chờ quyết, lịch tắt VM). Người dùng yêu cầu 12/10 23:20.
- `history/2026-10-12-dot-cuoi-diem-tham-quan-golf-va-sua-tuyen-quang.md` — thêm: entry này.

## Đã ghi production (xem trước rồi mới ghi; người dùng đồng ý trong chat)

| Việc | Số dòng | Script (thư mục `src/data_collection/data/` bị ignore) |
|---|---|---|
| Ẩn tiNiWorld, Timezone Lotte Mart Cần Thơ, BigFun Vincom Rạch Giá, Netin Travel (Quảng Bình), Minh Tuấn travel (Cao Bằng) | 5 ẩn | `vm-repair-20261012/fix_final_junk_and_tuyen_quang.py` |
| Vinpearl Onsen Resort Tuyên Quang (khách sạn + 7 hạng phòng): điểm đến "Vinpearl Onsen Resort Tuyên Quang" → "Tuyên Quang" | 8 | cùng script |
| Đợt 3h: BFS (trip_bfs) + lượt 3 thành phố (trip_bfs_extra) + lượt golf (trip_bfs_golf) | 251 mới | `attractions-fill-20261012/trip_poi_load3h/` |

- Tuyên Quang: `normalise` hiện tại đã cho "Tuyên Quang" (alias trong `geo.py`); dòng DB cũ vì upsert không ghi đè `destination`,
  nên chỉ cần sửa DB. Bản Booking cùng resort (`booking:hotel:17149131`, 10 hạng phòng, không giá) vẫn ẩn, không đổi.
- Đợt 3h theo điểm đến: Quảng Ngãi 52, Đồng Tháp 50, Châu Đốc 23, còn lại 1–8 mỗi nơi. Sau nạp: Quảng Ngãi 56, Đồng Tháp 51,
  Sóc Trăng 5 điểm đang bán (Sóc Trăng: Trip chỉ có 39 trang lân cận, hầu hết đã có hoặc thuộc Cần Thơ).
- Golf: 14 sân golf thật mới (Hanoi Golf Club, Đại Lải, Amber Hills, Corn Hill, Hoàng Gia, Tràng An, FLC Hạ Long, KN Golf Links Cam
  Ranh, NovaWorld Phan Thiết, Vietnam Golf & Country Club, Bà Nà Hills, Legend Đà Nẵng, Sam Tuyền Lâm, Paradise Vũng Tàu).
  `taxonomy = golf` đang bán: 25 (20 sân Trip không giá + 5 voucher Vinpearl có giá). Trang loại hình golf của Trip
  (`type-golf-courses-71-…`) chỉ trả 16–18 link/thành phố, phần lớn là điểm nổi tiếng chung, nên thêm được ít sân.
- Duyệt tay (`tools/drop_reviewed.txt`, 212 tên): bỏ thêm hội trường, cổng chào, bùng binh, bể bơi, trung tâm văn hoá–thể thao,
  khu vui chơi thiếu nhi, cắm trại/nơi nghỉ, tên doanh nghiệp, tên mã toạ độ, điểm trùng (Tràm Chim, Gò Tháp, Gáo Giồng, Cồn Én,
  Mỹ Lai, Khe Hai…), 2 điểm miễn phí trùng vé có giá cùng chỗ (VinWonders Hà Nội Water Park, Vinpearl Golf Phú Quốc), 2 điểm Tây
  Yên Tử (phía Bắc Giang) bị gán Hải Phòng. Bộ lọc tên rác thêm sân tập/mini golf/golf 3D.
- Gán điểm đến theo tâm gần nhất: thêm `--keep-dest` cho `tools/build_wave.py`; giữ 5 điểm Yên Tử/Ba Vàng (địa chỉ Quảng Ninh) ở
  Hạ Long thay vì Hải Phòng, Vietnam Golf & Country Club (địa chỉ TP.HCM) ở TP.HCM thay vì Biên Hòa.
- Lần `--apply` đầu truyền sai `--code-root` (`…/src/data_collection` thay vì `…/src`): lỗi import trước khi ghi; đã kiểm 0/251 mã
  trên DB rồi chạy lại đúng.

Sau đợt (23:14): điểm tham quan đang bán 2.667 (Trip 1.843, Booking 586, Vinpearl 201, demo 37; 931 có giá); khách sạn tổng quan
đang bán 2.704; vé có logo hãng 11.005/11.005 (`set_flight_images.py` xem trước: 0 dòng cần sửa, bộ nạp dùng code test/newcrawl
không ghi đè ảnh).

## Kiểm tra

- `pytest data_collection/tests` (vsf2, từ `src/` của worktree): 656 passed, 27 skipped (chạy sau khi thêm tâm Tuyên Quang,
  5 dòng loại và hai test); `test_plan.py` + `test_quality.py` chạy lại sau sửa cuối: 42 passed.
- `python -m compileall -q data_collection/collectors/geo.py`: OK. Không đổi backend/contract.
- `build_wave.py 3h`: `validate_catalog OK · 251 dòng mới`; nạp thử: `{'new': 251}`, demo_data `changed=0 · fillChanged=0`;
  nạp thật: `new 251, dbRowsWritten 256, refConflicts 0, quarantined 0`.
- Đọc DB sau ghi: 0 dòng còn ở điểm đến "Vinpearl Onsen Resort Tuyên Quang"; 5 điểm rác `available = false`; 0/5 còn bán.
- Bảo trì + index (người dùng bấm, `index-20261012T162444Z-14541`, 23:24–23:26): `status ok`, `embedded 252` (251 điểm + resort
  Tuyên Quang), `searchUnits 5986`, `deletedOrphans 0`. Bảo trì (code cũ trên VM) ghi đè ảnh 7.392 vé/tuyến →
  `set_flight_images.py --apply`: `ĐÃ GHI 7392 dòng`.
- Search (`curl -G https://praxis.io.vn/api/v1/search`): `sân golf`@Hà Nội → Hanoi Golf Club; `chùa`@Quảng Ngãi → Chùa Bảo Quang,
  Chùa An sơn…; `Tràm Chim`@Đồng Tháp → Vườn quốc gia Tràm Chim; `Vinpearl Onsen`@Tuyên Quang → Vinpearl Onsen Resort Tuyên Quang;
  `Yên Tử`@Hạ Long → Chùa Đồng Yên Tử, Danh Thắng Yên Tử, Thiền viện Trúc Lâm Yên Tử.
- Trước commit: `pytest data_collection/tests` 656 passed, 27 skipped; `compileall -q data_collection` OK.

Ngoài repo (thư mục `data/` bị ignore): `vm-repair-20261012/hide_junk_attractions.py` đổi sang kiểm trạng thái cuối để chạy lại
được (trước đây ROLLBACK khi có dòng đã ẩn); xem trước 23:27: 20/20 điểm có đúng 1 dòng, 0 dòng cần ẩn.

## Còn lại / rủi ro

1. Index: xong 23:26 (xem Kiểm tra). Mỗi lượt bảo trì/cào chạy code cũ trên VM vẫn ghi đè ảnh vé: chạy lại
   `data/flight-logos-20261012/set_flight_images.py --apply` cho tới khi sửa job được deploy.
2. Bộ cào còn hàng đợi (đã lưu frontier, chạy lại cùng lệnh là đi tiếp): `trip_bfs` 986 link (dừng 22:41), `trip_bfs_extra`
   Quảng Ngãi 41 + Đồng Tháp 64 (dừng 23:10 để kịp nạp trước khi VM tắt 23:59).
3. Sân golf Trip không có giá: agent không được coi `unit_price` trống là "miễn phí" cho golf (liên quan #183, #185). "Vinpearl Golf
   Hải Phòng" (Trip, không giá, đợt trước) trùng chỗ với voucher Vinpearl có giá: chưa ẩn, chờ người dùng quyết.
4. Override điểm đến của đợt 3h (`trip_poi_wave3h/overrides_wave3h.csv`, `nearest_destination_wave3h.csv`, danh sách
   `--keep-dest`) chưa đưa vào `collectors/destination_overrides.csv`: không cần cho dòng đã có, cần khi dựng lại catalog từ đầu.
5. Việc sau lượt cào 08:35 ngày 13/10 nếu job fix chưa deploy: như mục 1 của
   `history/2026-10-12-job-cao-giu-du-lieu-sua-tren-production.md`; thêm `vm-repair-20261012/fix_final_junk_and_tuyen_quang.py --apply`
   (5 điểm rác có thể bị bật lại; script chạy lại được: kiểm trạng thái cuối — 0/5 còn bán, 8/8 dòng ở "Tuyên Quang" — lệch thì ROLLBACK;
   chạy lại lúc 23:15 ở chế độ xem trước: 0 dòng cần đổi).
