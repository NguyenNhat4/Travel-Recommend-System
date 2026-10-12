# Bàn giao: làm giàu điểm tham quan production và giữ dữ liệu đã sửa (sau ngày 12/10/2026)

- Ngày: 2026-10-12 (viết 23:25 giờ VN, để mở phiên mới)
- Người làm: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Phục vụ: FR-CAT-01 (catalog điểm tham quan mọi điểm đến), FR-CAT-02 (khách sạn ẩn/bật lại theo hạng phòng đặt được),
  FR-CAT-03 (chuẩn hoá, điểm đến đúng), NFR-REL-01 (chỉ dữ liệu thật, grounding 100%). Issue #159.
- Nhánh: `test/newcrawl` (worktree `~/code/Travel-Recommendation-Product-newcrawl`), người dùng tự mở PR vào `release-mvp-v2`.

## 0. Bắt đầu phiên mới

Đọc theo thứ tự: file này → `history/2026-10-12-dot-cuoi-diem-tham-quan-golf-va-sua-tuyen-quang.md` →
`history/2026-10-12-job-cao-giu-du-lieu-sua-tren-production.md` →
`history/2026-10-12-nap-diem-tham-quan-moi-thanh-pho-va-sua-du-lieu-production.md`. Quy tắc chung: `AGENTS.md`.

Quy tắc người dùng (giữ nguyên):
- Chỉ dữ liệu thật. Chỉ cào vn.trip.com qua bộ cào của repo, tôn trọng robots. Không dùng www.trip.com, curl hay trình duyệt
  trong app để lách chặn.
- Hỏi trước **mỗi** lần ghi production; luôn chạy xem trước (dry-run) và báo số dòng trước khi `--apply`.
- Người dùng tự commit/mở PR; chỉ commit/push khi được bảo. Không thêm `Co-Authored-By` hay "Generated with Claude Code" vào commit,
  issue, PR hay comment.
- Mọi thay đổi trong `src/`, `docs/`, `db/` phải có entry `history/` (AGENTS.md §5).

Môi trường:
- Python: `~/miniconda3/envs/vsf2/bin/python`. Test data: `cd <worktree>/src && python -m pytest -q data_collection/tests`.
- Production DB qua tunnel người dùng mở: `ssh -N -L 127.0.0.1:15432:10.148.0.34:5432 bastion@34.142.132.251`; biến
  `CLOUD_SEED_DATABASE_URL` trong `~/code/Travel-Recommendation-Product/src/data_collection/.env`
  (`set -a && . ./.env && set +a`).
- Monitor: https://monitor.praxis.io.vn. Người dùng bấm "Bảo trì và index"; agent đọc `curl -s https://monitor.praxis.io.vn/api/runs`.
- Kiểm Search: `curl -sG https://praxis.io.vn/api/v1/search --data-urlencode "q=..." --data-urlencode "destination=..."`
  (Python urllib bị Cloudflare trả 403). Backend làm mới catalog mỗi 900 s.
- Script nạp/sửa nằm trong thư mục bị git ignore `~/code/Travel-Recommendation-Product/src/data_collection/data/`
  (dưới đây viết tắt `$D`).
- Không dùng `pkill -f <mẫu>` (giết luôn shell của agent, exit 144): lấy PID từ `ps` rồi `kill <pid>`.

## 1. Trạng thái cuối ngày 12/10 (đọc DB 23:14)

- Điểm tham quan đang bán: **2.667** (Trip 1.843, Booking 586, Vinpearl 201, demo 37; 931 có giá). Đầu ngày 1.411.
- Đợt đã nạp: 2, 3a–3h (`$D/attractions-fill-20261012/trip_poi_load*/`). Đợt 3h (251 điểm: Quảng Ngãi 52, Đồng Tháp 50,
  Châu Đốc 23, 14 sân golf) đã index 23:26 (`embedded 252`, `searchUnits 5986`); ảnh vé đã sửa lại sau bảo trì (7.392 dòng).
- Golf `taxonomy = golf` đang bán: 25 = 20 sân Trip **không giá** (Trip không bán tee time) + 5 voucher Vinpearl 1.700.000 ₫.
- Sửa production trong ngày: 50+ điểm đến sai tỉnh (sau sáp nhập), 27 điểm rác ẩn, 87 khách sạn bật lại (có hạng phòng đặt được),
  logo hãng cho 11.005/11.005 vé, ảnh thành phố đến cho 140 tuyến, Vinpearl Onsen Resort Tuyên Quang (8 dòng) về "Tuyên Quang".
- Code: commit `11022a4d`, `5c3028df`, merge `ff3b32a4` và commit đợt cuối (`collectors/geo.py` tâm Tuyên Quang,
  `collectors/excluded_products.csv` +5 = 37, `tests/test_plan.py`, `tests/test_quality.py`, entry
  `history/2026-10-12-dot-cuoi-diem-tham-quan-golf-va-sua-tuyen-quang.md`, file plan này) đã push lên `origin/test/newcrawl`.
  Người dùng chọn **không merge** `release-mvp-v2` lần này. Test: 656 passed, 27 skipped.
- Sửa job (giữ dữ liệu đã sửa tay) **chưa deploy**: VM vẫn chạy code cũ của `release-mvp-v2`.

## 2. Việc tiếp theo, theo thứ tự

### 2.1. Index đợt 3h — đã xong 23:26 ngày 12/10; giữ làm mẫu cho đợt sau

1. Người dùng bấm "Bảo trì và index". Đọc `/api/runs`: lượt `index` mới `status: ok`, số `embedded` ≈ 251 + resort Tuyên Quang.
2. Bảo trì chạy code cũ nên ghi đè ảnh vé: chạy `set_flight_images.py` xem trước rồi `--apply` (mục 2.2, lệnh 4).
3. Kiểm Search: `q=sân golf&destination=Hà Nội` (ra Hanoi Golf Club), `q=chùa&destination=Quảng Ngãi`,
   `q=Tràm Chim&destination=Đồng Tháp`, `q=Vinpearl Onsen&destination=Tuyên Quang`.

### 2.2. Sau lượt cào 08:35 ngày 13/10 (VM còn code cũ)

Lượt cào hằng ngày (code cũ) có thể: tắt lại khách sạn đã bật, bật lại điểm rác, ghi đè ảnh vé. Chạy từng lệnh xem trước, báo số
dòng, hỏi người dùng rồi mới `--apply` (cả bốn script đều chạy lại được, không đổi gì nếu DB đã đúng):

```bash
cd ~/code/Travel-Recommendation-Product/src/data_collection && set -a && . ./.env && set +a
P=~/miniconda3/envs/vsf2/bin/python
$P data/vm-repair-20261012/reopen_hotels_with_rooms.py            # 1. khách sạn có hạng phòng đặt được
$P data/vm-repair-20261012/hide_junk_attractions.py               # 2. 20 điểm rác đợt đầu
$P data/vm-repair-20261012/fix_final_junk_and_tuyen_quang.py      # 3. 5 điểm rác đợt cuối + Tuyên Quang
$P data/flight-logos-20261012/set_flight_images.py                # 4. logo hãng cho vé, ảnh thành phố cho tuyến
```

Lặp lại sau **mỗi** lượt cào/bảo trì chạy code cũ, cho tới khi mục 2.3 deploy xong.

### 2.3. Đưa sửa job lên VM

1. Đã commit + push đợt cuối lên `test/newcrawl` (12/10 23:30).
2. Chỉ khi người dùng bảo: merge `origin/release-mvp-v2` vào `test/newcrawl` (12/10 người dùng nói "không merge"). Kiểm 23:20 ngày 12/10: 18 commit mới (PR #169
   agent orchestrator + bộ nhớ hội thoại, #181 bỏ khoá concurrency CD, #184 sửa bước roll), **không chạm `src/data_collection`**,
   `git merge-tree` báo merge sạch. Chạy lại test data + backend + `validate_contract.py` sau merge.
3. Người dùng mở PR vào `release-mvp-v2`; Crawler CD deploy. Cổng khung giờ CD (23:45–08:40) còn trên `release-mvp-v2` cho tới khi
   PR #180 của Khoa merge.
4. Sau deploy: một lượt bảo trì, rồi chạy bốn lệnh mục 2.2 ở chế độ xem trước — kỳ vọng 0 dòng cần sửa. Nếu đúng, bỏ bước 2.2.

### 2.4. Cào tiếp và nạp đợt mới (không trần số điểm mỗi thành phố)

Hàng đợi đã lưu (`bfs_frontier.json`), chạy lại cùng thư mục là đi tiếp:
- `$D/attractions-fill-20261012/trip_bfs`: 986 link mới (dừng 22:41 ngày 12/10).
- `$D/attractions-fill-20261012/trip_bfs_extra`: Quảng Ngãi 41, Đồng Tháp 64 (dừng 23:10). Sóc Trăng đã hết link.

```bash
T=~/code/Travel-Recommendation-Product/src/data_collection/data/attractions-fill-20261012
cd ~/code/Travel-Recommendation-Product-newcrawl/src/data_collection
# cào chính (log mới, không ghi đè log cũ)
SEEDS_FILE=$T/trip_bfs/seeds.json SKIP_LISTS=1 xvfb-run -a ~/miniconda3/envs/vsf2/bin/python $T/tools/crawl_bfs_pois.py \
  "$PWD" --data-dir $T/trip_bfs trip-attractions > $T/trip_bfs/bfs-run4.log 2>&1
# 3 thành phố
SEEDS_FILE=$T/trip_bfs/seeds.json ONLY_DESTS='["Đồng Tháp","Quảng Ngãi","Sóc Trăng"]' SKIP_LISTS=1 xvfb-run -a \
  ~/miniconda3/envs/vsf2/bin/python $T/tools/crawl_bfs_pois.py "$PWD" --data-dir $T/trip_bfs_extra trip-attractions \
  > $T/trip_bfs_extra/bfs-part3.log 2>&1
```

Dòng "hàng đợi N" trong log chỉ đếm hạt giống, không phải link mới: xem số link còn lại trong `bfs_frontier.json`.

Quy trình một đợt (vd. `3i`):
1. Ghép interim: các dòng JSON hợp lệ của `trip_bfs`, `trip_bfs_extra`, `trip_bfs_golf` (khử trùng theo `key`) →
   `$T/trip_poi_wave3i/interim/trip_attractions.jsonl` (tạo trước, `build_wave.py` chỉ tự chụp `trip_bfs` khi file này chưa có).
2. Dựng: `cd <worktree>/src/data_collection && set -a && . ~/code/Travel-Recommendation-Product/src/data_collection/.env && set +a && \
   ~/miniconda3/envs/vsf2/bin/python $T/tools/build_wave.py 3i --drop-file $T/tools/drop_reviewed.txt [--keep-dest "tên" ...]`.
3. Duyệt tay **mọi** tên mới (in theo điểm đến), các dòng `GẦN`, `ĐỔI ĐIỂM ĐẾN`. Bỏ tên rác/trùng bằng cách thêm vào
   `drop_reviewed.txt` (212 tên); luật gán theo tâm gần nhất sai khi khác tỉnh (Yên Tử → Hải Phòng, Thủ Đức → Biên Hòa): dùng
   `--keep-dest`. Điểm miễn phí trùng chỗ sản phẩm có giá (VinWonders, Vinpearl Golf) thì bỏ.
4. Xem trước: `cd $T/trip_poi_load3i && ~/miniconda3/envs/vsf2/bin/python load_attractions.py --code-root <worktree>/src`
   (**`/src`**, không phải `/src/data_collection`). Kỳ vọng `{'new': N}`, demo_data `changed=0`.
5. Hỏi người dùng → `--apply` → `set_flight_images.py` (xem trước, `--apply` nếu có dòng) → người dùng bấm bảo trì → đọc
   `/api/runs` → chạy lại `set_flight_images.py` → kiểm Search → ghi bảng đợt vào entry `history/` mới.

## 3. Chờ người dùng quyết

1. "Vinpearl Golf Hải Phòng" (Trip, không giá, đợt trước) trùng chỗ voucher Vinpearl có giá: ẩn hay giữ?
2. Golf không giá: (a) bổ sung vào issue #185 cho team agent — giá trống ở golf là "chưa có giá", không phải miễn phí;
   (b) thêm nguồn có bán tee time = mở rộng phạm vi (kiểm robots/điều khoản trước), chưa làm.
3. Sửa job cho lần sau (người dùng để sau): bỏ trần `tripAttractions.perDestination` 25, cào trang Trip Moments trong job, đưa
   override điểm đến của các đợt (`trip_poi_wave*/overrides_wave*.csv`, `nearest_destination_wave*.csv`, danh sách `--keep-dest`)
   vào `collectors/destination_overrides.csv` để dựng lại catalog từ đầu vẫn đúng.

## 4. Issue agent đã mở (team agent xử lý)

- #177 hỏi theo loại hình ("đi chùa") bị coi là tên một nơi.
- #183 bỏ qua "miễn phí, rẻ nhất": thêm tour có phí, đổi khách sạn đắt hơn.
- #185 nhánh khám phá không bao giờ tìm `taxonomy: golf`.
PR #169 (orchestrator mới, merge 22:59 ngày 12/10) có thể đã đổi các luồng này: chat thử lại trên production trước khi báo thêm.

## 5. Hạ tầng (của Khoa, chỉ đọc)

- Lịch tắt VM 23:59 / bật 08:30: Khoa15 gỡ bằng gcloud 12/10, PR #180 (gỡ trong Terraform + bỏ cổng khung giờ CD) **chưa merge**.
  Đọc 23:21 ngày 12/10 (`gcloud compute instances list --project vinpearl-508801`): crawler, pg-a, pg-b, pg-w, bastion **lại gắn
  lịch** sau CD của #184/#169 (mỗi lượt CD trên `release-mvp-v2` gắn lại cho tới khi #180 merge). Đã báo người dùng để báo Khoa.
- Hệ quả cho việc data: nếu VM tắt, không có DB 23:59–08:30; lượt cào 08:35 chạy sau khi VM bật.
