# P2: lượt kiểm thật chế độ chạy liên tục (local)

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: docs (data)

## Mục tiêu

P2 của `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md`: chạy thật chế độ chạy liên tục (L1–L6) rồi mới bật mặc định.
Theo mục đã chốt:
- lượt local trước (`DB_TARGET=local`, `stream.index` tắt), rồi lượt VM ghi vào staging;
- bật mặc định `stream.enabled` và `stream.db`, không bật `stream.index`.

Phục vụ FR-CAT-01..04, FR-SRC-02.

## File thay đổi

- `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` — sửa: dòng tiến độ P1, P2.
- `history/2026-09-29-p2-kiem-that-chay-lien-tuc.md` — thêm: entry này.
- Không đổi code.
- Ngoài repo (sandbox, Git ignore): `src/data_collection/data/local_crawl/state/settings.json`.
  - Đặt `stream.index=false`.
  - Lượt 2 tạm đặt `sources.vinpearl=false`, `stream.minRecords=2`; đã trả về như trước lượt 2.

## Quyết định

- Chạy qua `./local_crawl.sh`: ghi vào database `vota_crawl` và Weaviate `ProductCrawl` trên Docker local, không đụng
  `vota`, `Product` hay staging.
- Thêm **lượt 2**. Ở lượt 1, `stream.minRecords` = 20 giữ lại mọi dòng của booking, agoda và Trip, vì phạm vi sandbox nhỏ
  nên mỗi nguồn có dưới 20 bản ghi. Lượt 2 tắt Vinpearl và đặt `stream.minRecords` = 2 để kiểm được các nguồn này.
- Lượt 2 được dừng tay (ghi `stop.request`, như nút Dừng) khi bước index bắt đầu thử lại vì Cohere 429. Lúc đó DB đã nạp
  xong; mục đích là không mất ~10 phút thử lại.
- **Chưa bật mặc định** `stream.enabled` / `stream.db` trong `fresh_settings.py`. Theo mục đã chốt, bật mặc định sau lượt
  VM. Lượt VM cần triển khai nhánh này lên VM, đó là việc của người yêu cầu.

## Kiểm tra

### Lượt 1 `full-20260929T024636Z-15154`

Cấu hình: 4 site cùng lúc, Nha Trang + Hà Nội, 3 khách sạn mỗi điểm đến, khách sạn Trip tắt; `stream.enabled`,
`stream.db` bật, `stream.index` tắt.

- **Thời gian cào:**
  - trip-flights xong sau 10 s, trip-attractions 33 s, booking 36 s, agoda 97 s;
  - vinpearl 989 s (02:46:36 → 03:03:05).
- **P1 trên lượt thật:** `normalise.source:trip_flights` chạy ngay khi vé máy bay cào xong, trước khi trip-attractions xong.
- **Nạp DB theo phần:**
  - 15 lô, 0 lỗi, 278 dòng, mỗi lô 0,07–0,14 s;
  - lô đầu lúc 02:48:36, 2 phút sau khi Vinpearl bắt đầu cào;
  - DB (dòng đang hiện) tăng dần trong lúc Vinpearl còn cào: 22 → 143 (02:49) → 211 (02:55) → 299 (03:02) → 434 sau
    lần nạp chính thức (03:03:51).
  - Dòng booking, agoda, Trip bị giữ tới lần nạp cuối, vì nguồn dưới 20 bản ghi. Combo bị giữ tới cuối theo thiết kế
    (87 dòng).
- **Nạp chính thức cuối lượt:**
  - `db` ok trong 0,4 s: new 135, refreshed 284, `dbRowsWritten` 419;
  - **không lỗi** `sourceRef/sameAs conflict` khi upsert lại dòng đã nạp giữa lượt.
- **So `sha256`:** chép `interim/` sang scratchpad, `normalise.py` cả khối, không checkpoint, cùng tham số và cùng ngày.
  `products.jsonl` **trùng**: `a27baa4a6ff8a9bb…`, 419 dòng.
- **DB sau lượt:**
  - 434 dòng đang hiện, 0 `mergedInto`;
  - **0 ref** (`sourceRef` hoặc `sameAs`) thuộc hơn một dòng đang hiện.
- **Nạp lại cùng `products.jsonl` bằng `load_into_db`:** `dbRowsWritten` = 419, không phải 0.
  - Lý do: mỗi lần nạp gắn `attributes.priceRefreshedAt = now` (`fresh_catalog_db.py:108`, `:224`), nên mọi dòng có giá
    đều "đổi". Đây là thiết kế có sẵn, không phải lỗi.
  - Tiêu chí "nạp lại cùng catalog thì 0 dòng ghi" của plan chỉ đúng ở mức `DbFeeder` (so `row_hash`, không gửi lại dòng
    chưa đổi). Ở lượt này 15 lô gửi 278 dòng, chỉ 1 dòng gửi lại vì đổi nội dung.
- **Tài nguyên** (bộ đo psutil mỗi 2 s trên cả cây tiến trình job, kể cả crawl.py, Chromium, normalise; máy 8 lõi, 15 GB):
  - PSS đỉnh **2.863 MB**, lúc 4 site và Chromium chạy cùng lúc; trung vị 800 MB khi chỉ còn Vinpearl;
  - RSS cộng dồn đỉnh 5.104 MB (đếm trùng bộ nhớ chia sẻ của Chromium);
  - CPU đỉnh 523% (≈5 lõi), trung bình 24% trong lúc cào;
  - chưa tách được phần chạy liên tục tốn thêm bao nhiêu; gộp nháp mỗi lần 0,3–0,8 s.
- `run.json` có 54 bước, trong đó 36 bước `normalise.preview` (rủi ro đã ghi ở L3).
- **Index cuối lượt lỗi, không liên quan chạy liên tục** (`stream.index` tắt):
  - 10:03 (giờ máy) mạng mất phân giải tên (`Temporary failure in name resolution`; Vinpearl cũng gặp
    `ERR_NAME_NOT_RESOLVED` ở trang tour cùng lúc);
  - 3 lần thử lại sau đó đều bị Cohere trả 429 Too Many Requests;
  - lượt kết thúc mã 3 ("Index thất bại; DB đã giữ dữ liệu mới"), cảnh báo `alerts.jsonl` được tạo đúng.

### Lượt 2 `full-20260929T031533Z-42720`

Cấu hình như lượt 1, nhưng Vinpearl tắt và `stream.minRecords` = 2.

- **Nạp DB theo phần:** 3 lô, **0 dòng bị giữ**, 0 lỗi.
  - Lô 1 lúc 03:16:33: 22 dòng Trip, 10 s sau khi trip-attractions xong (03:16:23).
  - Lô 2 lúc 03:17:33: 13 dòng, **trước** khi booking cào xong (03:17:47).
  - Lô 3 lúc 03:18:33: 24 dòng, **trước** khi agoda cào xong (03:18:56).
- `sha256` trùng bản cả khối: `c052b677926a8e29…`, 63 dòng.
- DB: 436 dòng đang hiện, 0 ref trùng, 0 `mergedInto`.
- Nạp chính thức 0,1 s, ok. Index bị dừng tay khi bắt đầu thử lại vì Cohere 429; lượt `stopped`, mã 5.

### Đối chiếu ngưỡng đạt của plan

| Tiêu chí | Kết quả |
|---|---|
| `sha256` trùng | đạt, cả 2 lượt |
| Không dòng trùng trong DB | đạt |
| Không lô lỗi code | đạt: 18 lô, 0 lỗi |
| RAM đỉnh < 3 GB | đạt ở local (2,86 GB, 4 site cùng lúc). **Chưa đo trên VM** (2 CPU / 4 GB, 2 site cùng lúc, có Chromium hỏi giá Trip) |
| Độ trễ cào → DB ≤ `mergeSeconds` + `dbSeconds` + một lần nạp (~90 s) | đạt: 10 s (Trip) tới dưới 60 s |

## Còn lại / rủi ro

- **Chưa bật mặc định.** Theo mục đã chốt, cần một lượt VM (staging) trước, nên phải triển khai nhánh này lên VM.
  Người yêu cầu chọn:
  - bật mặc định ngay trong bản triển khai, để lượt VM đầu là lượt kiểm; hoặc
  - bật bằng Cấu hình trên monitor của VM trước rồi mới đổi mặc định.
- **Ca biên của ngưỡng `stream.minRecords`:** nguồn đã cào **xong** mà tổng dưới 20 bản ghi thì cả lượt không được nạp
  theo phần, chỉ vào DB ở bước nạp cuối.
  - Trên VM phạm vi thật, mỗi nguồn có hàng trăm bản ghi nên hầu như không gặp.
  - Hướng sửa có thể: bỏ ngưỡng số bản ghi cho nguồn đã chốt checkpoint (vẫn giữ ngưỡng tỉ lệ lỗi).
  - Đây là đổi quy tắc "đủ" đã chốt ở L4, nên chờ người yêu cầu quyết.
- Sửa câu "nạp lại cùng catalog thì 0 dòng ghi" trong plan P2 thành mức `DbFeeder` (xem Kiểm tra); chưa sửa.
- Nguyên nhân Cohere 429 (kiểm bằng một request thử): key trong `.env` local là **Trial key, giới hạn 1.000 lượt gọi
  API mỗi tháng**, và đã hết quota tháng. Thử lại (loại `infra`, 60/120/240 s) không giúp được.
  - Người yêu cầu đã đổi key trong `.env`.
  - `./local_crawl.sh run index` (lượt `index-20260929T033719Z-57914`): ok trong 6,1 s, nhúng 274 dòng, 14 không đổi;
    `ProductCrawl` có 288 vector (bằng `searchUnits`).
  - Cần kiểm key của `/etc/vota/fresh-catalog.env` (job VM) và `/etc/vota/backend.env` (Search staging) nếu dùng chung
    key cũ.
- Vinpearl gặp lỗi mạng ở trang danh sách tour (`toursError`), nhưng bước vẫn `ok` và có 280 tour. Chưa xem có thiếu tour
  hay không.
- Chưa commit.
