# RecSys có gợi ý theo sở thích (biển / núi / thành phố) không — thử công thức, 08/10/2026

- Phục vụ: FR-REC-01, FR-REC-02, FR-REC-04 (`docs/prd/requirements.md` §1.4); đề xuất kèm theo:
  `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` (chờ chốt).
- Commit engine: `release-mvp-v2 @ 85cea82` (W_SHORT / W_POP / W_LONG = 0,7 / 0,15 / 0,15), chạy từ worktree `test/newcrawl`.
  Biến thể = thay `score_candidates` lúc chạy trong tiến trình đo, không sửa code repo.
  **Riêng bước 1 và bước 2** (`profile_*`, `step2_*`) chạy trên working tree `bench_search_recomSys` (`c47fc35` + thay đổi chưa commit,
  W 0,7/0,15/0,15) — engine này **chưa có** commit `9b703ba` (sửa cap lặp, "hôm nay" theo giờ VN) đã có trên `origin/main` và
  `release-mvp-v2`. Hai engine cho cùng số trừ nexttrip nDCG@10 / hit@4 (F0: 0.0168 / 0.0163 so với P0+F0: 0.016 / 0.015).
- Kết quả gốc (JSON + SHA-256) đã chép vào repo: `src/evaluation/recsys_bench/theme_study/results/2026-10-08/`. Báo cáo cuối:
  `docs/spec/bench/recsys-bam-so-thich-tong-hop.md`.
- Run id: không có (script thử nghiệm ngoài `recsys_bench`); kết quả thô `formula_local.json`, `formula_prod.json`,
  `formula_prod_F78.log`, `formula_prod_F910.log`, `slots_prod_F0b.json`, `slots_prod_F4.json` (xem mục Tái sinh).
- Split: không dùng split đóng băng; LLBO / temporal / nexttrip dựng lại từ `cdp.events` của từng DB với as_of 2026-10-08T00:00:00Z
  (bản sao production: 800 khách đầu theo id mỗi split, temporal 775 = đủ; local: LLBO 1.056, temporal 100, nexttrip 269).
- Vector bản sao production: `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`,
  `catalog-text-v2`, 384 chiều, 3.991 search unit.
- Làm local, chỉ đọc production, không ghi production.


Làm **local**, không sửa repo, không ghi production. Phục vụ FR-REC-01, FR-REC-02, FR-REC-04; grounding không đổi (mọi món từ catalog).
Engine = production `release-mvp-v2 @ 85cea82` (trọng số 0,7 / 0,15 / 0,15). Biến thể = thay `score_candidates` lúc chạy trong tiến
trình đo, hoặc hậu xử lý list 4 món của trang chủ.

## Trả lời ngắn

1. **Có cần đổi công thức?** Có, nhưng **không phải đổi 3 trọng số**. Lỗi gốc: cosine của e5-small dồn sát nhau (mọi món 0,88–0,93,
   top 10 % hơn trung vị chỉ ~0,02) nên `0,15 · pop` (0–1) lấn át hẳn phần sở thích. Kết quả: khi khách **không có chuyến mở**,
   engine gợi ý gần như cùng một nhóm điểm đến bán chạy cho mọi người (Phan Thiết, Nha Trang, Hội An…); khách thích núi chỉ 17 %
   món đúng chủ đề, thích thành phố 23 % (ngẫu nhiên 33 %).
2. **Đề xuất A (sửa công thức):** chuẩn hoá cosine min-max trong từng request **chỉ khi không có chuyến mở**, rồi
   `0,55 · cos_short + 0,30 · pop + 0,15 · cos_long` (F7). Đúng chủ đề 0,44 → **0,78** (núi 0,17 → 0,75; thành phố 0,23 → 0,80);
   **độ chính xác trong chuyến (LLBO) giữ nguyên tuyệt đối** vì khách có chuyến mở vẫn chấm như cũ.
   Giá phải trả trên số offline: temporal hit@20 −3,0 điểm, nexttrip −3,5 — xem caveat 1 (dữ liệu giả lập chọn điểm đến theo độ
   phổ biến nên thưởng cho việc gợi ý món bán chạy). Bản thận trọng: F9 (`W_POP` 0,45): đúng chủ đề 0,56, temporal −2,1, nexttrip −2,8.
3. **Đề xuất B (ô khám phá):** khi khách **đang có chuyến mở** (tình huống test production 07/10: đang xem biển Vũng Tàu), engine khoá
   điểm đến nên 0 % món ở nơi khác. Thêm **ô khám phá lấp chỗ trống**: list có < 4 món (do giới hạn 2 món / loại — thực tế trung bình
   3,44 món) thì lấp bằng món ở **điểm đến khác** xếp theo sở thích dài hạn `cos(u_long, v)`, mỗi điểm đến 1 món. Đúng chủ đề 79 %
   (ngẫu nhiên 33 %), **hit@4 không đổi** (chỉ lấp ô trống). Thay hẳn ô thứ 4 thì tốn LLBO hit@4 −3,0 điểm — không khuyến nghị.
   Đây là thay đổi hành vi FR-REC-02 (khoá điểm đến) → cần đề xuất PRD.
4. **Không nên** loại món khách vừa xem: 29 % khách LLBO đã xem đúng món họ mua sau đó; loại món đã xem làm LLBO hit@4 0,574 → 0,463
   (−11 điểm), temporal 0,114 → 0,039. Việc "Private Vung Tau Beach" đứng đầu sau khi xem là **đúng**.

## Dữ liệu và cách đo

| Bộ | Catalog | Vector | Event (split thật) |
|---|---|---|---|
| local | snapshot 23/09 — 3.183 search unit, 34 điểm đến, không có Vũng Tàu | `vec_T3+R_e5-small` (bench) | seed 09-23, 7.145 event |
| **bản sao production** | `cdp.products` production đọc (GET) qua monitor 08/10 01:49 → DB local `vota_prodcopy` — 3.991 search unit (= `ProductE5Small` production), 58 điểm đến | embed lại: e5-small revision ghim + `catalog-text-v2` (đúng job index) | `cdp.events` production 40.158 event (có 8 view biển của tài khoản "Đăng Khôi" tạo tối 07/10) |

- **Split thật** (đo độ chính xác): LLBO (bỏ lần mua cuối, chủ yếu khách đang có chuyến mở), temporal (mốc thời gian chung), nexttrip
  (chuyến kế tiếp, chuyến trước đã xong). Bản sao production lấy 800 khách đầu mỗi split (thứ tự cố định, mọi biến thể cùng tập);
  temporal 775 (đủ). hit@20 / nDCG@10 = list 20 món (mode eval), hit@4 = list production 4 món như trang chủ.
- **Khách giả lập có chủ đề** (đo bám sở thích): 80 khách × 3 chủ đề × 2 kịch bản / biến thể. Mỗi khách 2–3 chuyến đã xong (xem → mua
  khách sạn, 50 % thêm tham quan), chuyến kế tiếp cùng chủ đề 80 %. "Giữa hai chuyến": không chuyến mở. "Đang có chuyến mở": xem 3 món
  ở một điểm đến trong 2 ngày. **Nhãn chủ đề điểm đến làm tay** (phụ lục), thuật toán không đọc nhãn — chỉ dùng để chấm.
  "Đúng chủ đề" = tỷ lệ món (điểm đến có nhãn) cùng chủ đề với khách.

## Kết quả — bản sao production

| Biến thể | LLBO hit@20 | nDCG@10 | hit@4 | temporal hit@20 | hit@4 | nexttrip hit@20 | Đúng chủ đề giữa 2 chuyến | biển | núi | thành phố |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F0 production | 0,836 | 0,525 | 0,574 | 0,159 | 0,114 | 0,074 | 0,438 | 0,91 | 0,17 | 0,23 |
| F1 min-max mọi lúc, 0,7/0,15/0,15 | 0,728 | 0,377 | 0,419 | 0,123 | 0,094 | 0,025 | 0,782 | 0,76 | 0,77 | 0,81 |
| F3 cosine thô, pop 0,05 | 0,766 | 0,424 | 0,461 | 0,134 | 0,107 | 0,031 | 0,739 | 0,79 | 0,71 | 0,72 |
| F4 min-max mọi lúc, pop 0,30 | 0,814 | 0,507 | 0,540 | 0,132 | 0,108 | 0,034 | 0,776 | 0,77 | 0,75 | 0,80 |
| F5 min-max mọi lúc, pop 0,25 | 0,794 | 0,485 | 0,521 | 0,128 | 0,103 | 0,030 | 0,783 | 0,76 | 0,78 | 0,82 |
| F6 min-max mọi lúc, pop 0,35 | 0,830 | 0,525 | 0,556 | 0,136 | 0,108 | 0,038 | 0,736 | 0,83 | 0,66 | 0,73 |
| **F7 min-max khi không chuyến mở, pop 0,30** | **0,836** | **0,525** | **0,574** | 0,129 | 0,106 | 0,039 | **0,776** | 0,77 | 0,75 | 0,80 |
| F8 như F7, pop 0,25 | 0,836 | 0,525 | 0,574 | 0,128 | 0,103 | 0,035 | 0,783 | 0,76 | 0,78 | 0,82 |
| F9 như F7, pop 0,45 | 0,836 | 0,525 | 0,574 | 0,138 | 0,114 | 0,046 | 0,556 | 0,89 | 0,28 | 0,50 |
| F10 như F7, pop 0,60 | 0,836 | 0,525 | 0,574 | 0,156 | 0,114 | 0,071 | 0,391 | 0,96 | 0,04 | 0,17 |

Đọc: chuẩn hoá mọi lúc (F1–F5) làm hỏng độ chính xác trong chuyến (LLBO hit@4 −3 đến −15 điểm); chỉ chuẩn hoá khi không có chuyến
mở (F7–F10) giữ LLBO nguyên vẹn. `W_POP` là núm vặn duy nhất giữa "bám sở thích" và "món bán chạy": 0,30 → bám sở thích 0,78;
0,60 → như production. Local (snapshot 23/09) cùng xu hướng: F0 0,417 → F4 0,776, LLBO giữ nguyên (F4 local hit@4 0,563 vs 0,560).

### Ô khám phá khi đang có chuyến mở (list 4 món, công thức F0, bản sao production)

| Cách chọn món ở điểm đến khác | Đúng chủ đề |
|---|---:|
| ngẫu nhiên (theo cỡ điểm đến) | 0,333 |
| `cos(u_long, v)` — sở thích dài hạn | **0,792** |
| độ giống điểm đến (centroid) + `u_long` | 0,771 |
| `cos(u_short, v)` — giống món đang xem | 0,462 (vector e5 mang tên điểm đến → không chuyển sang nơi khác) |

| Hậu xử lý list 4 món | LLBO hit@4 | temporal hit@4 | Món ở điểm đến khác (khách có chuyến mở) |
|---|---:|---:|---:|
| production | 0,574 | 0,114 | 0 |
| loại món đã xem | 0,463 | 0,039 | 0 |
| thay ô 4 bằng món khám phá | 0,544 | 0,111 | 1,0 |
| **lấp ô trống bằng món khám phá** | **0,574** | **0,114** | 0,29 (chỉ khi list < 4) |

Khách đang có chuyến mở nhận lại đúng món vừa xem ở 92,5 % ca (giả lập) — đúng với dữ liệu: 29 % lần mua LLBO là món đã xem trước.

## Caveat (đọc trước khi chốt)

1. **Dữ liệu event là giả lập và không có sở thích chủ đề.** `seed_histories.py` (`World.destination`) bốc điểm đến từng chuyến theo độ
   phổ biến, độc lập với chuyến trước; bản production (làm giàu 05/10) cùng cách. Vì vậy split temporal / nexttrip **thưởng cho món bán
   chạy** và không thể cho thấy lợi ích bám sở thích; phần "−3 điểm" là chi phí trong một thế giới không ai có sở thích. Người dùng thật
   có sở thích → lợi ích thật nằm giữa hai cột. Muốn đo đúng cần thêm sở thích chủ đề vào bộ sinh event (đổi spec seed — cần chốt).
2. Nhãn chủ đề điểm đến làm tay (phụ lục); Hội An / Hạ Long / Ninh Bình có thể tranh cãi. 10 điểm đến "hỗn hợp" bị loại khỏi chấm.
3. Khách giả lập 80 / chủ đề / kịch bản — sai số chuẩn của tỷ lệ ~±0,03.
4. `u_long` của ô khám phá trong thí nghiệm tính xấp xỉ (trung bình có trọng số loại event × suy giảm 365 ngày); bản cài đặt thật nên
   dùng `profile.u_long` của engine.
5. Bản sao production lấy 800 khách đầu (theo id) mỗi split, không phải toàn bộ (LLBO 4.072, nexttrip 1.835).
6. Không đo latency — các biến thể không thêm lượt gọi Weaviate (A: chỉ đổi phép tính điểm; B: chấm trên vector đã có).


## Số thô bổ sung (nguyên văn từ file kết quả)

### Bản sao production — đủ chỉ số

| Biến thể | LLBO h20 | LLBO nDCG10 | LLBO h@4 | temp h20 | temp nDCG10 | temp h@4 | next h20 | next nDCG10 | next h@4 | between theme | số điểm đến khác nhau (between) | open theme |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F0_prod | 0.8363 | 0.525 | 0.5737 | 0.1587 | 0.0954 | 0.1135 | 0.0737 | 0.0168 | 0.0163 | 0.438 | 28 | 0.767 |
| F1_minmax | 0.7275 | 0.3765 | 0.4188 | 0.1226 | 0.0941 | 0.0942 | 0.025 | 0.0066 | 0.005 | 0.782 | 41 | 0.767 |
| F3_rawPop05 | 0.7662 | 0.4239 | 0.4612 | 0.1342 | 0.1012 | 0.1071 | 0.0312 | 0.0109 | 0.0063 | 0.739 | 40 | 0.767 |
| F4_minmaxPop30 | 0.8137 | 0.5065 | 0.54 | 0.1316 | 0.101 | 0.1084 | 0.0338 | 0.0091 | 0.0075 | 0.776 | 41 | 0.767 |
| F5_minmaxPop25 | 0.7937 | 0.4849 | 0.5212 | 0.1277 | 0.0976 | 0.1032 | 0.03 | 0.0076 | 0.0063 | 0.783 | 41 | 0.767 |
| F6_minmaxPop35 | 0.83 | 0.525 | 0.5563 | 0.1355 | 0.1025 | 0.1084 | 0.0375 | 0.0098 | 0.0112 | 0.736 | 39 | 0.767 |
| F7_betweenMinmaxPop30 | 0.8363 | 0.525 | 0.5737 | 0.129 | 0.0895 | 0.1058 | 0.0387 | 0.01 | 0.0075 | 0.776 | 41 | 0.767 |
| F8_betweenMinmaxPop25 | 0.8363 | 0.525 | 0.5737 | 0.1277 | 0.0867 | 0.1032 | 0.035 | 0.0085 | 0.0063 | 0.783 | 41 | 0.767 |
| F9_betweenMinmaxPop45 | 0.8363 | 0.525 | 0.5737 | 0.1381 | 0.0927 | 0.1135 | 0.0462 | 0.0142 | 0.015 | 0.556 | 39 | 0.767 |
| F10_betweenMinmaxPop60 | 0.8363 | 0.525 | 0.5737 | 0.1561 | 0.0911 | 0.1135 | 0.0712 | 0.0128 | 0.02 | 0.391 | 12 | 0.767 |

Top điểm đến (between, số lần xuất hiện): F0 Nha Trang 251, Phan Thiết 245, Phú Quốc 227 · F7 Nha Trang 74, TP. Hồ Chí Minh 55,
Sa Pa 44, Phú Quốc 39, Đà Lạt 39 · F9 Nha Trang 236, Phú Quốc 194, Đà Nẵng 88 · F10 Phú Quốc 244, Nha Trang 239, Phan Thiết 199.

Ghi chú chạy: hai lượt F7/F8 và F9/F10 chạy riêng; script lỗi `KeyError: 'F0_prod'` ở bước dọn cuối (sau khi đã in số) nên số F7–F10
lấy nguyên văn từ log, không có trong `formula_prod.json`.

### Bước 2 — so cách phối hợp điểm trên profile P2 (hoàn tất 08/10 16:15)

Cả ba job đã xong: log kết thúc `done` (`profile_p2f7` 1.207 s, `step2_x` 2.238 s, `step2_y` 2.218 s), mọi JSON có
`parity_mismatch_llbo200 = 0`. Kiểm lúc 16:24 không còn tiến trình đo nào chạy. (Bản trước của mục này ghi "hai job còn chạy" theo
snapshot 16:03 — đã lỗi thời.) Mọi scorer chỉ đổi điểm khi **không** có chuyến mở; LLBO 100 % có chuyến mở nên LLBO giống nhau.

Mốc calibration F14 (tập calibration riêng seed 99, 120 request): q_low (p10) = 0.8529, q_high (p99) = 0.9387.

| P2 + scorer | LLBO h20 | nDCG10 | h@4 | temp h20 | temp nDCG10 | temp h@4 | next h20 | next nDCG10 | next h@4 | between (biển / núi / phố) | noisy (biển / núi / phố) | nguồn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| F0_prod | 0.8363 | 0.5221 | 0.5725 | 0.1548 | 0.0929 | 0.1123 | 0.0675 | 0.0151 | 0.0175 | 0.431 (0.912 / 0.163 / 0.219) | 0.404 (0.875 / 0.15 / 0.188) | `profile_b.json`, `profile_noisy.json` |
| F7_betweenMinmaxPop30 | 0.8363 | 0.5221 | 0.5725 | 0.1303 | 0.0884 | 0.1058 | 0.0275 | 0.0083 | 0.0063 | 0.763 (0.817 / 0.735 / 0.738) | 0.666 (0.815 / 0.528 / 0.654) | `profile_p2f7.json` |
| F12b_betweenRawPop05 | 0.8363 | 0.5221 | 0.5725 | 0.1329 | 0.0887 | 0.1058 | 0.03 | 0.0089 | 0.0063 | 0.717 (0.804 / 0.68 / 0.668) | 0.603 (0.782 / 0.476 / 0.551) | `step2_x.json` |
| F13a_betweenCenter (0,7/0,15/0,15) | 0.8363 | 0.5221 | 0.5725 | 0.1213 | 0.0835 | 0.0994 | 0.025 | 0.0071 | 0.0063 | 0.772 (0.791 / 0.772 / 0.753) | 0.744 (0.832 / 0.688 / 0.714) | `step2_x.json` |
| F13b_betweenCenterPop30 (0,55/0,30/0,15) | 0.8363 | 0.5221 | 0.5725 | 0.1277 | 0.0863 | 0.1045 | 0.0312 | 0.0089 | 0.0063 | 0.691 (0.866 / 0.571 / 0.637) | 0.661 (0.88 / 0.501 / 0.603) | `step2_y.json` |
| F14_betweenQuantilePop30 | 0.8363 | 0.5221 | 0.5725 | 0.1239 | 0.0874 | 0.1045 | 0.0262 | 0.0073 | 0.0063 | 0.782 (0.793 / 0.794 / 0.76) | 0.723 (0.79 / 0.684 / 0.695) | `step2_y.json` |

Top điểm đến (noisy): F7 Nha Trang 129, Hội An 39 · F12b Nha Trang 176 · F13a Phú Quốc 66, Phan Thiết 60, Sa Pa 57 ·
F13b Phú Quốc 188, Đà Nẵng 76 · F14 Nha Trang 56, Hội An 37, Phú Quốc 31.

Đọc:
- F14 bám chủ đề `between` cao nhất và phân bố điểm đến đều nhất; F13a `noisy` cao nhất nhưng temporal / nexttrip thấp nhất; F12b, F13b
  kém F7 → loại.
- F7 / F13a / F14 không phân biệt được về temporal / nexttrip (z ≤ 0,5, ước lượng độc lập bảo thủ); chênh theme 0,02–0,08 chưa có CI.
- So với P0+F0: P2+F7 temporal h@20 −0.0284 (z 1,6), nexttrip h@20 −0.0462 (z 4,2 — giảm thật). Phần lớn do công thức: riêng
  F0 → F7 trên P0 đã −0.0297 / −0.0350. Lịch sử split sinh thiên về popularity (caveat 1) nhưng không tự động vô hiệu hoá mức giảm.
- F13 chỉ center ở scorer trên ứng viên lấy bằng không gian cũ, không dựng lại profile từ vector đã center và không đổi MMR; không suy
  rộng thành kết luận cho mọi cách centering.
- Chưa có CI ghép cặp: JSON chỉ lưu chỉ số tổng hợp. Cần lưu kết quả từng khách (plan `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` WP2).

Lệnh tái sinh (repo root, env trỏ DB bản sao local như mục Tái sinh). Lệnh gốc của `step2_x` / `step2_y` không được lưu; hai dòng sau
dựng lại từ tên cấu hình trong JSON và tham số mặc định của `eval_profile.py` (`--splits` mặc định = cả ba split):

```bash
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 --profiles P2_confidence --scorers F7_betweenMinmaxPop30 --n-syn 80 --max-users 800 --splits llbo,temporal,nexttrip --out profile_p2f7.json
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 --profiles P2_confidence --scorers F12b_betweenRawPop05,F13a_betweenCenter --n-syn 80 --max-users 800 --out step2_x.json
python -m src.evaluation.recsys_bench.theme_study.eval_profile --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 --profiles P2_confidence --scorers F13b_betweenCenterPop30,F14_betweenQuantilePop30 --n-syn 80 --max-users 800 --out step2_y.json
```

### Bước 1 — biến thể dựng profile (đo thêm 08/10 chiều)

`profile_variants.py` viết lại `build_profile` với ba công tắc (khớp production 200/200 khách khi tắt hết): P1 `cap_fix` (giữ event mới
nhất, không bỏ purchase / add_to_cart), P2 `confidence` (u_long nhân độ tin cậy chuyến `min(1, Σ W_TYPE)`), P3 `session` (gom event
không eventGroupId thành phiên theo điểm đến, cách ≤ 14 ngày), P4 = cả ba. `eval_profile.py`, cùng split / seed với `eval_formula`.
Kịch bản mới `noisy` (khách giả lập): mua 2–3 chuyến đúng chủ đề + lướt xem 5–8 sản phẩm ở điểm đến khác chủ đề 20–300 ngày trước.

Cấu trúc profile (LLBO, 300 khách): P0/P1/P2 trung vị 4 chuyến, 63,5 % chuyến không có lần mua; P3/P4 2 chuyến, 49,7 %.

| Profile + công thức | LLBO h@4 | h20 | nDCG10 | temp h@4 | temp h20 | next h20 | between | noisy (biển / núi / phố) | open |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 + F0 (production) | 0.574 | 0.836 | 0.525 | 0.114 | 0.159 | 0.074 | 0.438 | 0.373 (0.85 / 0.11 / 0.16) | 0.767 |
| P1 + F0 | 0.574 | 0.836 | 0.525 | 0.114 | 0.159 | 0.074 | 0.438 | 0.373 | 0.767 |
| P2 + F0 | 0.573 | 0.836 | 0.522 | 0.112 | 0.155 | 0.068 | 0.431 | 0.404 | 0.767 |
| P3 + F0 | 0.570 | 0.838 | 0.525 | 0.115 | 0.165 | 0.069 | 0.430 | 0.357 | 0.767 |
| P4 + F0 | 0.570 | 0.839 | 0.521 | 0.116 | 0.165 | 0.069 | 0.432 | 0.403 | 0.767 |
| P0 + F7 | 0.574 | 0.836 | 0.525 | 0.106 | 0.129 | 0.039 | 0.776 | 0.447 (0.60 / 0.36 / 0.38) | 0.767 |
| P2 + F7 | 0.573 | 0.836 | 0.522 | 0.106 | 0.130 | 0.028 | 0.763 | 0.666 (0.82 / 0.53 / 0.65) | 0.767 |
| P3 + F7 | — | — | — | — | — | — | 0.778 | 0.287 (0.44 / 0.23 / 0.20) | 0.767 |
| P4 + F7 | 0.570 | 0.839 | 0.521 | 0.110 | 0.141 | 0.030 | 0.763 | 0.674 (0.82 / 0.55 / 0.66) | 0.767 |

(— = chưa đo trên split thật; P0+F7 split thật lấy từ bảng F7 ở trên.) Đọc: lượt xem lẻ lấn át u_long là có thật — với F7, khách lướt
xem nhiễu chỉ 0.447 đúng gu (so với 0.776 khi không nhiễu); trọng số độ tin cậy (P2) đưa lên 0.666. P1 không đổi số nào (giới hạn lặp chỉ
chạm 10 event trên bản sao production). P3 một mình làm tệ hơn (0.287): gom các lượt xem đúng gu trước khi mua thành một phiên làm
giảm số "chuyến" đúng gu trong khi lượt xem nhiễu ở nhiều điểm đến vẫn tách riêng. Với công thức production F0, đổi profile gần như
không tác động vì pop lấn át. Lệnh: `eval_profile --profiles … --scorers F0_prod,F7_betweenMinmaxPop30 [--splits ""]`.

### F11 — giãn cả `pop` (đo thêm 08/10 chiều, cùng bộ khách và seed)

| Biến thể | LLBO h20 | nDCG10 | h@4 | temp h20 | temp nDCG10 | temp h@4 | next h20 | next nDCG10 | next h@4 | between theme | biển | núi | phố | số điểm đến | open theme |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F11_betweenMinmax3Pop30 (0,55/0,30/0,15) | 0.8363 | 0.525 | 0.5737 | 0.129 | 0.0895 | 0.1058 | 0.0387 | 0.0091 | 0.0063 | 0.776 | 0.773 | 0.752 | 0.803 | 41 | 0.767 |
| F11b_betweenMinmax3Pop10 (0,75/0,10/0,15) | 0.8363 | 0.525 | 0.5737 | 0.1187 | 0.0829 | 0.0981 | 0.0312 | 0.007 | 0.005 | 0.781 | 0.764 | 0.771 | 0.807 | 41 | 0.767 |

Đọc: F11 gần như trùng F7 (cùng theme, cùng top điểm đến). Lý do: `Popularity.unit_scores` đã chia cho max (món bán chạy nhất = 1)
và tập ứng viên luôn gồm các món phổ biến nhất, nên min-max của `pop` trong request ≈ chính `pop`. F11b thực chất là F7 với pop 0,10:
theme nhích 0.776 → 0.781 (trong sai số), temporal / nexttrip giảm thêm. Kết luận: giãn `pop` không cần; giữ F7.
Lệnh: `eval_formula --n-syn 80 --max-users 800 --variants F11_betweenMinmax3Pop30,F11b_betweenMinmax3Pop10` (1.135 s).

### F12 — không giãn, chỉ hạ trọng số pop khi không có chuyến mở (đo thêm 08/10 chiều)

| Biến thể | LLBO h20 | nDCG10 | h@4 | temp h20 | temp nDCG10 | temp h@4 | next h20 | next nDCG10 | next h@4 | between theme | biển | núi | phố | số điểm đến | open theme |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F12_betweenRawPop03 (0,82/0,03/0,15) | 0.8363 | 0.525 | 0.5737 | 0.1303 | 0.0861 | 0.0981 | 0.03 | 0.0087 | 0.005 | 0.767 | 0.752 | 0.752 | 0.798 | 43 | 0.767 |
| F12b_betweenRawPop05 (0,80/0,05/0,15) | 0.8363 | 0.525 | 0.5737 | 0.1355 | 0.0894 | 0.1071 | 0.0375 | 0.0109 | 0.0063 | 0.739 | 0.785 | 0.708 | 0.722 | 40 | 0.767 |

Đọc (so với F7: temp h@4 0.1058, next h20 0.0387, theme 0.776): F12 pop 0,03 bám chủ đề ngang F7 (trong sai số) nhưng temporal
h@4 và nexttrip thấp hơn; F12b pop 0,05 ngang F7 về độ chính xác nhưng bám chủ đề kém hơn 0.037 (núi 0.708, Nha Trang 110 lần vs 74).
Chênh lệch nhỏ, sát sai số ±0,03; F7 không thua ở chỉ số nào. Lệnh: `eval_formula --variants F12_betweenRawPop03,F12b_betweenRawPop05` (1.128 s).

### Phân bố ba thành phần trước khi nhân trọng số (đo thêm 08/10 chiều)

`component_stats.py` bọc `score_candidates` production, ghi `E @ u_short`, `E @ u_long`, `pop` trên đúng ma trận `E` của từng request
(ứng viên Weaviate + món phổ biến + món trong lịch sử khách). Bản sao production, as_of 2026-10-08. Trung vị theo request:

| Nhóm | Số request (giá trị) | Thành phần | min | p50 | p90 | max | p90 − p50 | Tỷ lệ = 0 (mọi giá trị) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Khách giả lập, không chuyến mở | 150 (37.977) | cos(u_short) = cos(u_long) | 0.8226 | 0.9111 | 0.9235 | 0.9443 | 0.0119 | 0 |
| | | pop | 0 | 0 | 0.2821 | 1.0 | 0.2821 | 0.599 |
| Khách giả lập, có chuyến mở | 150 (17.418) | cos(u_short) | 0.7792 | 0.8591 | 0.9049 | 1.0 | 0.0302 | 0 |
| | | cos(u_long) | 0.8653 | 0.9128 | 0.9262 | 0.9389 | 0.0124 | 0 |
| | | pop | 0 | 0 | 0.0732 | 1.0 | 0.0732 | 0.664 |
| LLBO thật (100 % có chuyến mở) | 300 (19.764) | cos(u_short) | 0.7914 | 0.8322 | 0.8531 | 1.0 | 0.0192 | 0 |
| | | cos(u_long) | 0.828 | 0.8607 | 0.8818 | 0.9884 | 0.0176 | 0 |
| | | pop | 0 | 0 | 0.1818 | 1.0 | 0.1487 | 0.639 |

Khi không có chuyến mở `u_short = u_long` nên hai cột cos trùng nhau. Sau trọng số 0,7/0,15/0,15: khoảng p50→p90 của phần cos đóng
góp 0,85 × 0,012 ≈ 0,010 điểm; của `pop` 0,15 × 0,28 ≈ 0,042; món bán chạy nhất được cộng 0,15. Lệnh:
`python -m src.evaluation.recsys_bench.theme_study.component_stats --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 --max-users 300 --n-syn 50 --out stats.json`.
Đính chính các con số dùng trước đó: "85 % pop = 0" là trên toàn catalog; trong tập engine chấm mỗi request là 60–66 %.

### Local (snapshot 23/09) — đủ chỉ số

| Biến thể | LLBO h20 | nDCG10 | h@4 | temp h20 | temp h@4 | next h20 | between theme | biển | núi | phố | open theme |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| F0_prod | 0.8504 | 0.5114 | 0.5597 | 0.18 | 0.14 | 0.052 | 0.417 | 0.703 | 0.263 | 0.285 | 0.773 |
| F1_minmax | 0.8049 | 0.4257 | 0.4801 | 0.19 | 0.16 | 0.0409 | 0.801 | 0.875 | 0.811 | 0.718 | 0.773 |
| F2_rank | 0.7121 | 0.3134 | 0.34 | 0.2 | 0.16 | 0.0409 | 0.709 | 0.899 | 0.595 | 0.632 | 0.773 |
| F3_rawPop05 | 0.804 | 0.4533 | 0.4858 | 0.2 | 0.16 | 0.052 | 0.724 | 0.818 | 0.744 | 0.61 | 0.773 |
| F4_minmaxPop30 | 0.8551 | 0.5161 | 0.5625 | 0.2 | 0.15 | 0.0409 | 0.776 | 0.882 | 0.759 | 0.688 | 0.773 |
| F5_minmaxPop25 | 0.8438 | 0.4926 | 0.5436 | 0.2 | 0.16 | 0.0409 | 0.802 | 0.868 | 0.812 | 0.727 | 0.773 |
| F6_minmaxPop35 | 0.8598 | 0.5277 | 0.5786 | 0.2 | 0.15 | 0.0446 | 0.688 | 0.848 | 0.63 | 0.586 | 0.773 |

Local temporal chỉ 100 khách → sai số lớn, không dùng để kết luận.

### Hậu xử lý list 4 món (bản sao production)

| Scorer | Split | Mục tiêu đã xem trước | base | noSeen | explore1 | noSeen+explore1 | fillExplore |
|---|---|---:|---:|---:|---:|---:|---:|
| F0_prod | LLBO (800) | 0.292 | 0.5737 | 0.4625 | 0.5437 | 0.4138 | 0.5737 |
| F0_prod | temporal (775) | 0.105 | 0.1135 | 0.0387 | 0.111 | 0.031 | 0.1135 |
| F4_minmaxPop30 | LLBO (800) | 0.292 | 0.54 | 0.4375 | 0.505 | 0.3787 | 0.54 |
| F4_minmaxPop30 | temporal (775) | 0.105 | 0.1084 | 0.0335 | 0.1058 | 0.0271 | 0.1084 |

Kịch bản đang có chuyến mở (F0): số món trung bình base 3.438 → fillExplore 3.729; món ở điểm đến khác base 0 → fillExplore 0.292
→ explore1 1.0; tỷ lệ món đã xem trong list base 0.343, fillExplore 0.312; theme base 0.833, fillExplore 0.816.

## Đo kèm trên production (07/10 tối, tài khoản của người yêu cầu)

- 8 view biển (4 Nha Trang, 4 Vũng Tàu) → `/recommendations` trả strategy `recent_activity`, cả 4 món ở Vũng Tàu: Private Vung Tau
  Beach, Vung Tau Beach Full Day Trip, Ho Tram Beach Boutique Resort, Ocean Sunrise Vung Tau. Hỏi k=8 nhận 4.
- Latency: guest `latencyMs` 29, đầu-cuối ~0,4 s; đã đăng nhập trung vị server 1,06 s, lần gọi đầu 3–4 s; trang chủ `/recommendations`
  3,05 s đầu-cuối. Các biến thể ở trên chưa đo latency.

## Tái sinh

Script: `src/evaluation/recsys_bench/theme_study/` (`dump_prod.py` tải chỉ-đọc qua API GET của monitor, `embed_prodcopy.py`,
`theme_exp.py` khách giả lập + ô khám phá, `eval_formula.py` biến thể công thức, `eval_slots.py` hậu xử lý list 4 món).
Vector `.npy` (6 MB) và file env chứa DSN không nằm trong repo. Chạy từ gốc repo, env trỏ `DATABASE_URL` / `CDP_DATABASE_URL` /
`EVAL_DATABASE_URL` vào DB local `vota_prodcopy`:

```
python -m src.evaluation.recsys_bench.theme_study.dump_prod --base-url <monitor>/api/dbx/rows <out_dir> products events combo_items
python -m src.evaluation.recsys_bench.theme_study.embed_prodcopy <dsn vota_prodcopy> <prefix>
python -m src.evaluation.recsys_bench.theme_study.eval_formula --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 \
  --n-syn 80 --max-users 800 --variants F0_prod,F7_betweenMinmaxPop30,F9_betweenMinmaxPop45 --out formula_prod.json
python -m src.evaluation.recsys_bench.theme_study.eval_slots --vec npy:<prefix> --as-of 2026-10-08T00:00:00+00:00 \
  --scorer F0_prod --n-syn 80 --max-users 800 --out slots.json
python -m src.evaluation.recsys_bench.theme_study.theme_exp --vec npy:<prefix> --n 80 --out theme_rows.json
```

Kiểm tra sau khi chuyển vào repo (08/10): `eval_formula --splits llbo --variants F0_prod,F7_betweenMinmaxPop30` ra lại đúng
LLBO 0.8363 / 0.525 / 0.5737, theme between F0 0.438 và F7 0.776 như bảng trên.

## Phụ lục — nhãn chủ đề

- biển: Phú Quốc, Nha Trang, Đà Nẵng, Quy Nhơn, Phan Thiết, Côn Đảo, Cát Bà, Tuy Hòa, Hạ Long, Sầm Sơn, Vũng Tàu, Phan Rang, Lý Sơn, Hà Tiên, Vân Đồn
- núi / mát: Đà Lạt, Sa Pa, Điện Biên, Mai Châu, Pleiku, Buôn Ma Thuột, Phong Nha, Kon Tum, Tam Đảo, Mù Cang Chải, Sơn La, Mộc Châu, Hà Giang, Bảo Lộc, Cao Bằng, Lạng Sơn
- thành phố / văn hoá: Hà Nội, TP. Hồ Chí Minh, Huế, Hội An, Hải Phòng, Cần Thơ, Ninh Bình, Mỹ Tho, Vĩnh Long, Đồng Tháp
- hỗn hợp (không chấm): Nghệ An, Hà Tĩnh, Rạch Giá, Quảng Bình, Thanh Hóa, Châu Đốc, Bến Tre, Bắc Ninh, Biên Hòa, Tây Ninh (+ điểm đến chưa gán)

## Kèm theo: lượt cào production 08/10 02:00 (code mới, chỉ đọc qua monitor)

`full-20261007T190008Z-23`: **ok** (xanh toàn bộ), 02:00 → 03:52. maintain, trip-flights, trip-attractions, trip-hotels.discover,
trip-hotels.prices (32/32, 0 ngày thiếu giá), vinpearl, booking-hotels, agoda-hotels, normalise, validate, db (1.880 dòng, 0 xung đột),
index (125 s) đều `ok`. Bảo trì parse lại combo: 112 combo đổi; combo có dòng "Vé vào cửa …" 19 → 28 (+9 = đúng 9 combo vector cũ).

## Kiểm thử trực tiếp giới hạn lặp (08/10, bổ sung sau review)

Phục vụ FR-REC-02 / AC-REC-02. `src/evaluation/recsys_bench/tests/test_profile_variants.py` dùng vector giả,
không DB/model/network: cùng sản phẩm và chuyến có ba lượt xem rồi purchase; thử đầu vào cũ-trước và mới-trước.
Kiểm cả event purchase, bought_units, purchased_taxonomies, ends_on, active_trip và strategy cross_vertical.
Các event đều cũ hơn 14 ngày nhưng usingDate còn ở tương lai, để phát hiện mất ngày sử dụng làm đóng nhầm chuyến.
Thêm ca cart/purchase trước hoặc sau nhiều lượt xem (chỉ giữ ba lượt xem mới nhất) và cart không được coi là đã mua.

Lệnh: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/evaluation/recsys_bench/tests/test_profile_variants.py`.
Kết quả: **7 passed, 2 xfailed**. Hai xfail strict là kỳ vọng nghiệp vụ trên production hiện còn lỗi; P1/P4 pass.
Khi production sửa xong, strict xfail sẽ XPASS và làm bộ test fail để buộc bỏ marker. Đây không phải bằng chứng lỗi production đã được sửa.

**Đính chính (08/10 16:40):** ca xfail `production-known-bug` gọi `build_profile` của **nhánh `bench_search_recomSys`**, không phải
production. `origin/main` và `release-mvp-v2` đã có commit `9b703ba` (tuổi chuyến, `ends_on`, món đã mua tính trên mọi event; cap lặp
chỉ giới hạn trọng số vector). Chạy cùng kịch bản với `build_profile` của `origin/main`: `bought_units`, `purchased_taxonomies`,
`ends_on`, `active_trip`, `strategy = cross_vertical` đều đúng; chỉ còn purchase không nằm trong `trip.events` (không góp vào vector chuyến).
Ca test gộp hai kiểm này nên sau khi merge main vẫn xfail vì lý do khác — cần tách thành ca nghiệp vụ (main phải pass) và ca vector
(plan `docs/plan/2026-10-08-ban-giao-recsys-bam-so-thich.md` WP1). Chạy lại 16:30, env `vsf2`: `test_profile_variants.py`,
`test_parity.py`, `test_engine_no_leak.py` → **20 passed, 2 xfailed**.
