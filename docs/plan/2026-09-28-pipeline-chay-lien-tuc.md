# Pipeline chạy liên tục: chuẩn hoá, gộp, nạp DB, index theo phần trong lúc đang cào

- Ngày: 2026-09-28
- Người yêu cầu: Đăng Khôi
- Phục vụ: FR-CAT-01..04 (catalog đúng, đủ, tươi), FR-SRC-02 (tự động vector hoá). PRD không quy định thời điểm
  hay cách nạp catalog của job cào, nên plan này không lệch PRD.
- Phạm vi: `src/data_collection` (fresh_catalog.py, normalise.py, fresh_catalog_db.py, collectors/vinpearl.py,
  fresh_settings.py, monitor). Không đổi contract, DDL, 13 trường của `cdp.products`.
- Thay một quyết định cũ của nhóm: quy tắc nạp DB "được cả hoặc không có gì" (ghi ở
  `history/2026-09-28-cp3-phan-loai-loi-va-thu-lai.md` và CP3 của `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`)
  đổi thành "dòng nào đủ thì nạp dòng đó" (L4). Người yêu cầu chọn ngày 2026-09-28.
- Liên quan: `docs/plan/2026-09-28-monitor-so-do-luong.md` (UI1–UI2 xong; sơ đồ phải hiện được bước chạy liên tục, L6).
- Tiến độ (2026-09-28): người yêu cầu duyệt plan, chốt 4 mục "Cần chốt" theo đề xuất và thêm nút chỉnh sống vào L6.
  L1 xong (`history/2026-09-28-l1-chuan-hoa-tung-phan-khi-cao.md`); L2 phần 1 xong
  (`history/2026-09-28-l2-vinpearl-doc-file-tam.md`). Người yêu cầu yêu cầu làm hết rồi review một lần (2026-09-28):
  L2 phần 2 không áp dụng; L3–L6 xong (`history/2026-09-28-l3-…`, `-l4-…`, `-l5-…`, `-l6-…`). `stream.enabled` vẫn mặc định
  tắt, chờ người yêu cầu kiểm một lượt thật.

## Mục tiêu

Người yêu cầu muốn pipeline tự động tới hết, không bước nào đợi cả nguồn cào xong:

- cào được bản ghi nào thì chuẩn hoá bản ghi đó (theo lô nhỏ vài giây một lần);
- catalog gộp được cập nhật liên tục;
- sản phẩm nào đủ điều kiện thì nạp DB, rồi index, ngay trong lượt.

## Hiện trạng (trước khi thay đổi)

- Chuẩn hoá theo nguồn (CP5) chạy khi **cả nhóm site** cào xong (`crawl_sites` → `Previewer.group_done`). Nhóm Trip
  gồm 4 bước tuần tự (tìm ID KS → vé máy bay → điểm tham quan → giá phòng), nên vé máy bay đợi cả nhóm.
- Mỗi lần chuẩn hoá một nguồn đọc lại **cả** file interim (`normalise.py --only-source`).
- Gộp chính thức, kiểm tra, nạp DB, index chạy **một lần** sau khi mọi nhóm xong.
- Collector ghi interim theo hai kiểu:
  - booking, Trip (vé máy bay, điểm tham quan, combo, khách sạn), booking flights: nối từng bản ghi trong lúc cào
    (`JsonlWriter(..., "a")`, flush ngay), cuối nguồn ghi lại cả file qua file tạm rồi đổi tên;
  - Vinpearl: ghi từng khách sạn/tour vào `vinpearl.jsonl.tmp` (flush ngay), cuối nguồn mới đổi tên thành `vinpearl.jsonl`
    (`collectors/vinpearl.py:745`). (Sửa 2026-09-28: bản đầu của plan ghi nhầm là Vinpearl chỉ ghi ở cuối.)
  - Vinpearl combo (giữ hết trong bộ nhớ), agoda API (xuất từ SQLite), giá phòng Trip (`trip_live`): chỉ ghi cả file một lần ở cuối.
- Nạp DB (`fresh_catalog_db.load_into_db`): upsert trong một transaction, có advisory lock, **không xoá dòng**.
  Dòng cũ được nhận ra qua `sourceRef` / `sameAs` **của dòng trong DB**; dòng mới chỉ được tra bằng `sourceRef` của chính nó.
- Index: đã tăng dần theo `textHash` (chỉ nhúng dòng mới hoặc đổi text) và xoá vector mồ côi.
- Số đo: chuẩn hoá một nguồn 0,3–2,7 s; gộp 1,6–6 s; cào Vinpearl ~1.200 s, booking 38–143 s.

## Đã chốt (2026-09-28, Đăng Khôi: "chốt theo đề xuất")

1. **"Đủ" để nạp DB nghĩa là gì.** Đề xuất của agent, một dòng catalog được nạp khi:
   - qua kiểm tra từng dòng hiện có (`validate_catalog`: 13 trường, kiểu dữ liệu, cha của phòng/chuyến);
   - nguồn của nó đã có ít nhất `stream.minRecords` bản ghi (đề xuất 20) và tỉ lệ bản ghi lỗi ≤ `normalise.maxErrorPercent`
     (sửa 2026-09-29, người yêu cầu chốt: nguồn đã cào xong — mọi checkpoint của site đã chốt `ok` — không cần đủ
     `stream.minRecords`; xem `history/2026-09-29-p2-nguon-xong-khong-can-du-ban-ghi.md`)
     (tránh lỗi code đổ dữ liệu hỏng vào DB);
   - phòng khách sạn: khách sạn cha đã nạp hoặc nạp cùng lô;
   - khách sạn Trip: đã có đủ giá ở mọi mốc ngày (quy tắc coverage hiện có);
   - combo: mọi thành phần parse được đã có trong DB hoặc cùng lô.
2. **Chấp nhận hệ quả của việc bỏ "được cả hoặc không có gì":**
   - dòng đã nạp giữa lượt vẫn ở lại DB nếu cuối lượt lỗi hoặc bị chặn chất lượng;
   - kiểm tra cả catalog cuối lượt (đủ nhóm bắt buộc, số sản phẩm không tụt quá 50%) chỉ còn **báo cáo và cảnh báo**,
     không chặn được dòng đã nạp;
   - FE/agent đọc DB staging sẽ thấy dòng mới xuất hiện dần trong lượt.
3. **Chu kỳ mặc định** (đề xuất, chỉnh ở Cấu hình): chuẩn hoá 15 s, gộp nháp 30 s, nạp DB 60 s, index 300 s.
4. **Thứ tự so với việc khác:** đề xuất làm L1–L3 trước UI3, vì chúng đổi thời điểm các ô chuyển trạng thái trên sơ đồ;
   L4–L5 sau khi L1–L3 đã chạy ổn trên lượt thật.

## Cách làm việc

Như plan normalize: làm tuần tự; mỗi checkpoint có test pass và người yêu cầu kiểm tay rồi mới sang checkpoint sau.
Mỗi checkpoint có entry `history/` riêng; không commit. Có công tắc `stream.enabled` (mặc định tắt cho tới L6); tắt thì
job chạy đúng như hiện nay.

**Điều kiện bắt buộc cho L1–L3:** trên cùng bộ interim 49 MB, chạy cùng ngày, `products.jsonl` cuối lượt của chế độ
liên tục trùng `sha256` với chế độ theo lô hiện tại (cách so của CP0 plan normalize).

## L1 — Chuẩn hoá từng phần trong lúc cào

- **Vì sao:** yêu cầu chính: bản ghi cào xong thì chuẩn hoá ngay, không đợi nguồn hay nhóm.
- **Việc làm:**
  - Một vòng lặp chuẩn hoá trong `fresh_catalog.py` chạy suốt phần cào. Mỗi `stream.normaliseSeconds`, với mỗi file interim:
    - đọc phần mới từ byte đã đọc lần trước, chỉ lấy dòng đã có `\n` (bỏ dòng đang ghi dở);
    - file bị ghi lại (inode đổi hoặc nhỏ hơn vị trí đã đọc, vd. collector ghi lại cả file cuối nguồn): đọc lại từ đầu;
    - ánh xạ phần mới bằng đúng hàm ánh xạ theo nguồn hiện có, nối vào `normalised/<nguồn>.jsonl`; lỗi bản ghi
      nối vào `<nguồn>.errors.jsonl`; `meta.json` ghi thêm vị trí đã đọc và số lô.
  - Bản ghi trùng khoá trong cùng nguồn (collector thử lại): giữ bản sau cùng, như khi đọc cả file.
  - Tách phần theo nguồn của `normalise.py` thành hàm nhận một danh sách bản ghi, gọi được trong tiến trình. Phần nào của
    bước theo nguồn cần xem cả nguồn (vd. sửa điểm đến/toạ độ theo nguồn) thì chạy lại trên cả checkpoint mỗi lô; **phải
    kiểm từng bước khi làm**.
  - Khi nguồn cào xong: chạy một lượt đọc cuối, rồi đánh dấu checkpoint "xong"; bước gộp chính thức dùng checkpoint này.
- **Test tự động:**
  - interim được nối thêm 3 lần → checkpoint bằng checkpoint chuẩn hoá cả file một lần;
  - dòng cuối chưa có `\n` không được đọc; lần sau đọc đủ;
  - file bị ghi lại (ngắn hơn, inode khác) → đọc lại từ đầu, không trùng dòng;
  - bản ghi lỗi giữa các lô vẫn vào `errors.jsonl` và tính đúng tỉ lệ;
  - **so `sha256`**: mô phỏng cào bằng cách nối interim 49 MB theo từng khúc → `products.jsonl` trùng bản theo lô.
- **Bạn kiểm:** chạy lượt nhỏ; trên monitor, số dòng của ô chuẩn hoá booking tăng dần trong lúc ô cào booking còn chạy.
- **Xong khi:** mọi nguồn ghi interim nối tiếp được chuẩn hoá trong lúc đang cào.

## L2 — Vinpearl được chuẩn hoá dần

- **Vì sao:** Vinpearl là nguồn chậm nhất (~20 phút); L1 chỉ đọc `<nguồn>.jsonl`, trong khi Vinpearl ghi dần vào file tạm.
- **Phần 1 (xong):** bộ theo dõi đọc `<nguồn>.jsonl.tmp` khi chưa có `<nguồn>.jsonl`. Không sửa collector.
  - Đổi tên giữ inode và nội dung nên không đọc lại.
  - Nguồn dừng trước khi đổi tên: xoá checkpoint lúc chốt/dừng luồng, để khớp bản theo lô (bản theo lô không có nguồn đó).
- **Phần 2 (không áp dụng, 2026-09-28):** job cào mới không chạy Vinpearl combo (`source_command` chỉ gọi `crawl.py vinpearl`;
  `vinpearl-bundles` là lệnh riêng), nên không sửa collector. agoda API giữ nguyên (xuất từ SQLite ở cuối, theo thiết kế).
- **Test tự động:** file tạm lớn dần được đọc dần; đổi tên không đọc lại, checkpoint cuối giống bản theo lô; nguồn chỉ có
  file tạm khi dừng thì không còn checkpoint.
- **Bạn kiểm:** bật chạy liên tục; trong lúc Vinpearl đang cào, ô chuẩn hoá Vinpearl "Đang chạy" và số dòng tăng dần.

## L3 — Gộp nháp liên tục

- **Vì sao:** thấy catalog gộp gần như trực tiếp; thay bản nháp chỉ chạy khi một nhóm xong.
- **Việc làm:** mỗi `stream.mergeSeconds`, nếu có checkpoint đổi từ lần trước thì chạy `merge_catalog` trên checkpoint
  hiện có, ghi vào `preview/` như bản nháp hiện nay. Không chạy chồng: lần trước chưa xong thì bỏ qua lượt này. Hết cào
  thì gộp chính thức một lần như hiện nay.
- **Test tự động:** checkpoint không đổi → không gộp lại; gộp chậm hơn chu kỳ → không chạy chồng; gộp nháp lỗi không làm
  hỏng lượt (như CP5).
- **Bạn kiểm:** trong lúc cào, catalog nháp trên monitor tăng dần.
- **Xong khi:** catalog nháp trễ so với dữ liệu cào không quá một chu kỳ gộp.

## L4 — Nạp DB theo phần

- **Vì sao:** "đủ catalog nào thì nạp cái đó".
- **Trước khi nạp theo phần, phải sửa `prepare_rows`:** tra dòng cũ bằng **mọi** ref của dòng mới (`sourceRef` và `sameAs`),
  không chỉ `sourceRef`. Lý do: dòng được giữ khi gộp trùng có thể đổi theo thứ tự nguồn về. Ví dụ: agoda về trước và được
  nạp; booking về sau và thành dòng giữ, với `sameAs` chứa ref agoda. Nếu không sửa, DB có hai dòng cho một khách sạn và lượt
  sau lỗi "sourceRef/sameAs conflict". Sau khi sửa, dòng booking được nạp vào đúng `product_id` đã có.
- **Việc làm:**
  - Mỗi `stream.dbSeconds`: lấy catalog nháp mới nhất, chọn các dòng "đủ" (mục Cần chốt 1) **mới hoặc đổi** so với lần nạp
    trước (so hash nội dung), rồi nạp bằng `load_into_db` hiện có (cùng transaction, advisory lock, chỉ upsert).
  - Cuối lượt: nạp lần cuối từ catalog chính thức, rồi chạy `validate_run` và quality gate như hiện nay. Không đạt thì
    ghi lỗi `quality` vào `run.json` và báo (CP7 plan normalize khi có), **không** hoàn tác dòng đã nạp.
  - Mỗi lần nạp ghi một dòng vào `db_batches.jsonl` của lượt: lúc, số dòng, số dòng ghi, lỗi. `db_load.jsonl` (báo cáo
    trước → sau) gộp mọi lần nạp.
  - Nạp lỗi tạm thời / hạ tầng: thử lại theo CP3 ở lần sau; không dừng phần cào.
- **Test tự động** (Postgres test như `test_fresh_catalog_job.py`):
  - agoda nạp trước, booking gộp sau → một `product_id`, không lỗi conflict ở lần nạp sau;
  - phòng về trước khách sạn cha → phòng chờ, nạp khi cha đủ;
  - combo chờ đủ thành phần;
  - nguồn mới có 5 bản ghi hoặc tỉ lệ lỗi vượt ngưỡng → chưa nạp;
  - nạp lại cùng catalog → 0 dòng ghi;
  - quality gate cuối lượt không đạt → lượt báo lỗi `quality`, dòng đã nạp còn nguyên.
- **Bạn kiểm:** chạy lượt nhỏ vào DB local (`DB_TARGET=local`); `SELECT count(*) FROM cdp.products` tăng dần trong lúc cào.
- **Xong khi:** sản phẩm vào DB local trong lúc cào; không có dòng trùng sau nhiều lần nạp.

## L5 — Index theo phần

- **Vì sao:** sản phẩm đã nạp thì tìm được qua Search ngay (FR-SRC-02).
- **Việc làm:** mỗi `stream.indexSeconds`, nếu DB có dòng ghi mới từ lần index trước thì gọi `index_catalog` (đã tăng dần
  theo `textHash`). Không chạy chồng. Cuối lượt index lần cuối như hiện nay (xoá vector mồ côi chỉ ở lần cuối).
- **Test tự động:** không có dòng ghi mới → không gọi Cohere; hai chu kỳ liền nhau → dòng đã nhúng không nhúng lại.
- **Bạn kiểm:** trong lúc cào, trên tab Embedding thử truy vấn một khách sạn vừa cào được thì thấy nó.
- **Xong khi:** độ trễ từ lúc cào tới lúc tìm được không quá một chu kỳ nạp + một chu kỳ index.

## L6 — Monitor cho bước chạy liên tục, bật mặc định

- **Việc làm:**
  - `run.json`: mỗi bước liên tục (chuẩn hoá theo nguồn, gộp nháp, nạp DB, index) là một bước `running` suốt phần cào,
    `detail` có số lô, số dòng, lô gần nhất;
  - sơ đồ (UI1): các ô này hiện "Đang chạy · lô N · M dòng", đường nối giữa ô cào và ô chuẩn hoá thể hiện chạy song song;
  - nút chỉnh sống khi lượt đang chạy (cùng cơ chế `live_control` của tốc độ cào: vòng lặp đọc lại mỗi giây, áp từ lô
    kế tiếp, lô đang chạy dở không bị đổi; tạm dừng thì dữ liệu dồn sang lô sau, không mất):
    - chu kỳ gộp, nạp DB, index (toàn lượt);
    - tạm dừng / chạy tiếp nạp DB và index (phần cào, chuẩn hoá vẫn chạy);
    - "Chuẩn hoá ngay" cho từng nguồn;
    - đặt ở phần đầu lượt và panel của ô Gộp, Nạp DB, Index;
  - đổi tên "bản nháp" trên UI thành "Catalog đang gộp" (từ L4 nó là nguồn để nạp DB, không chỉ để xem);
  - bật `stream.enabled` mặc định sau khi người yêu cầu kiểm một lượt thật đầy đủ.
- **Test tự động:** `graph()` với các bước liên tục đang chạy; tắt `stream.enabled` → job chạy như trước; đổi chu kỳ /
  tạm dừng qua `live_control` → vòng lặp áp ở lô kế tiếp, không mất dữ liệu khi chạy tiếp.
- **Xong khi:** trên sơ đồ nhìn thấy dữ liệu chảy qua các bước trong lúc cào.

## Rủi ro

- VM 2 CPU / 4 GB chạy cùng Chromium: gộp nháp mỗi 30 s dùng CPU và ~290 MB RAM. Có chu kỳ trong Cấu hình và công tắc tắt.
- Cohere: index theo phần gọi Cohere nhiều lần hơn và nhúng cả dòng về sau bị gộp hoặc loại. Chu kỳ index dài (300 s)
  để giới hạn.
- DB staging có catalog trộn cũ và mới trong lượt. Lượt lỗi giữa chừng vẫn để lại phần đã nạp (quyết định ở Cần chốt 2).
- Output cuối có thể lệch bản theo lô ở ca biên: `sha256` là điều kiện bắt buộc ở L1–L3.
- `normalise.py` dùng `date.today()`; lượt chạy qua nửa đêm có thể cho lô đầu và lô sau khác ngày. Cần cố định ngày của
  lượt khi làm L1.
