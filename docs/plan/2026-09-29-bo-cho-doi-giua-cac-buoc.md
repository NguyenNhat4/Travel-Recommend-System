# Bỏ chờ đợi giữa các bước: chuẩn hoá theo nguồn, bật chạy liên tục, khai báo đồ thị bước, hạn giờ và cào lại một nguồn

- Ngày: 2026-09-29
- Người yêu cầu: Đăng Khôi
- Phục vụ: FR-CAT-01..04 (catalog đúng, đủ, tươi), FR-SRC-02 (tự động vector hoá). PRD không quy định cách job cào
  sắp xếp bước, nên plan này không lệch PRD.
- Phạm vi: `src/data_collection` (fresh_catalog.py, fresh_settings.py, monitor.py, monitor_ui, local_crawl.sh, một module
  mới `pipeline_graph.py`). Không đổi contract, DDL, 13 trường của `cdp.products`; `products.jsonl` phải giữ nguyên.
- Vẫn **không dùng Airflow** (quyết định 2026-09-28, `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`). Mỗi mục ghi
  khái niệm Airflow tương ứng để học kèm.
- Liên quan:
  - `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`: L1–L6 đã code; P2 là lượt kiểm thật mà L6 còn chờ.
  - `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`: CP5 (chuẩn hoá theo nguồn) và CP6 (chạy lại từ bước lỗi).
    P1 sửa CP5, P4 mở rộng CP6.
- Tiến độ (2026-09-29): người yêu cầu duyệt plan và chốt 5 mục "Cần chốt" theo đề xuất ("chốt theo đề xuất").
  P1 xong (`history/2026-09-29-p1-chuan-hoa-theo-buoc-cao.md`); đã chạy đúng trên lượt thật local.
  P2: xong lượt kiểm local (`history/2026-09-29-p2-kiem-that-chay-lien-tuc.md`). Người yêu cầu chốt theo đề xuất
  (2026-09-29): bật mặc định sau lượt VM (bật bằng Cấu hình trên monitor VM trước); nguồn đã chốt checkpoint không cần
  đủ `stream.minRecords` (`history/2026-09-29-p2-nguon-xong-khong-can-du-ban-ghi.md`). P3 xong
  (`history/2026-09-29-p3-khai-bao-do-thi-buoc.md`), chờ người yêu cầu kiểm tay. P4 xong
  (`history/2026-09-29-p4-han-gio-va-cao-lai-mot-nguon.md`), chờ người yêu cầu kiểm tay. Việc tiếp theo người yêu cầu
  nêu (2026-09-29): gọi Cohere song song khi index — plan riêng `docs/plan/2026-09-29-index-cohere-song-song.md` (P5).

## Mục tiêu

Không bước nào phải đợi một bước mà nó không thật sự cần:

1. **P1.** Nguồn nào cào xong thì chuẩn hoá ngay, không đợi các nguồn khác cùng nhóm site.
2. **P2.** Chạy một lượt thật với chế độ chạy liên tục (L1–L6, đã code) rồi bật mặc định. Mục tiêu: catalog của các nguồn
   nhanh vào DB, không đợi Vinpearl.
3. **P3.** Thứ tự và quan hệ giữa các bước chỉ khai báo ở một chỗ. Job, chạy lại và sơ đồ monitor cùng đọc từ đó.
4. **P4.** Mỗi nguồn có hạn giờ. Nguồn lỗi, bị chặn hoặc quá giờ thì cào lại được riêng nguồn đó, không cào lại cả lượt.

## Hiện trạng (đo trên lượt thật, đọc code 2026-09-29)

- Lượt `full-20260928T073959Z-221577` (sandbox `data/local_crawl`, 4 site cùng lúc, khách sạn Trip tắt):

  | Bước | Bắt đầu → xong |
  |---|---|
  | trip-flights | 07:39:59 → 07:40:25 |
  | trip-attractions | 07:40:25 → 07:42:14 |
  | chuẩn hoá `trip_flights` | 07:42:14 (đợi trip-attractions **1 phút 49 giây**) |
  | booking-hotels / agoda-hotels | xong 07:42:47 / 07:43:59 |
  | vinpearl | 07:39:59 → 07:59:56 (bị dừng tay sau ~20 phút) |

  Mọi nguồn khác xong lúc 07:44. Gộp chính thức, kiểm tra, nạp DB và index đợi Vinpearl thêm **~16 phút**.
- Chuẩn hoá theo nguồn (CP5) được gọi khi **cả nhóm** xong (`crawl_sites` → `Previewer.group_done`, `fresh_catalog.py:332`).
- Nhóm Trip chạy tuần tự: tìm ID khách sạn → vé máy bay → điểm tham quan → giá phòng (`fresh_catalog.py:913`).
  - Chỉ bước giá phòng cần ID khách sạn.
  - Plan này **không** tách nhóm Trip: cùng site, chạy song song tăng nguy cơ bị chặn.
- Chạy liên tục (L1–L6) đã code, test pass, nhưng `stream.enabled` và `stream.db` mặc định tắt. Lượt local gần nhất
  (`full-20260928T100701Z-339934`) vẫn chạy với `stream.enabled=false`.
- Quan hệ giữa các bước khai báo rải rác ở nhiều nơi:
  - `fresh_catalog.py`: `SITE_GROUPS`, `GROUP_INTERIM`, `SOURCE_SWITCH`, `LIVE_KEYS`, thứ tự gọi trong `crawl_and_load`,
    `RESUME_STEPS`;
  - `monitor.py`: `SOURCES`, `STEP_OWNER`, `GRAPH_COLUMNS`, `GRAPH_SINGLE`, `GRAPH_MODES`, `RESUME_STEPS` (chép lại),
    `RESUME_FROM`, `STEP_LABELS`, `STREAM_STEPS`.

  Thêm hoặc đổi một bước phải sửa đồng bộ nhiều chỗ.
- **`fresh_catalog.py` không có hạn giờ nào**, cho cả lượt lẫn từng nguồn.
  - `MAX_HOURS` chỉ truyền cho `daily.py` (job cũ, `run_daily_docker.sh:77`), không tới `fresh-run`.
  - Bảng "Đối chiếu với Airflow" của plan 28/09 ghi `dagrun_timeout` là "có": sai với job mới.
  - Một nguồn treo giữ lượt chạy mãi; lượt hôm sau bị bỏ qua vì khoá còn giữ (CP8 chỉ báo sau khi đã trễ).
- Nguồn bị chặn (mã 75) không được thử lại. Muốn có lại dữ liệu nguồn đó phải bấm Cào lớn cho cả lượt.
- `resume --from` (CP6) chỉ chạy lại các bước sau cào: `normalise | merge | validate | db | index`.

## Đã chốt (2026-09-29, Đăng Khôi: "chốt theo đề xuất")

1. **P2: lượt kiểm chạy ở đâu.** Đề xuất: một lượt local (`DB_TARGET=local`, `stream.index` tắt), rồi một lượt trên VM
   ghi vào staging.
   - Lý do tắt index ở local: `.env` local trỏ Weaviate Cloud, index theo phần sẽ ghi vào collection dùng chung.
2. **P2: bật mặc định những gì.** Đề xuất: bật `stream.enabled` và `stream.db`; `stream.index` vẫn tắt mặc định.
   - Index đã chạy một lần cuối lượt.
   - Index theo phần tốn Cohere cho cả dòng về sau bị gộp.
3. **P4: hạn giờ mặc định.** Đề xuất theo số đo hiện có, người yêu cầu chỉnh ở Cấu hình:

   | Nguồn / mức | Hạn giờ |
   |---|---|
   | vinpearl | 90 phút |
   | trip-flights, trip-attractions, booking-hotels, agoda-hotels | 60 phút mỗi nguồn |
   | trip-hotels.discover | 60 phút |
   | trip-hotels.prices | 8 giờ |
   | cả phần cào (`crawl.maxHours`) | 16 giờ (bằng `MAX_HOURS` của job cũ) |

4. **P4: cào lại một nguồn là tay hay tự động.** Đề xuất: phase này chỉ làm bằng tay (lệnh + nút trên monitor). Tự động
   thử lại sau N giờ khi bị chặn để sau, khi đã thấy tần suất bị chặn thật.
5. **P4: khách sạn Trip.** Cào lại riêng bước giá phòng cần danh sách ID của bước tìm ID; hiện danh sách này chỉ nằm trong
   bộ nhớ. Đề xuất: P4 lưu thêm `trip_targets.run.json` vào thư mục lượt, cho phép cào lại `trip-hotels`.

## Cách làm việc

- Làm tuần tự P1 → P2 → P3 → P4. Mỗi P có test tự động pass và người yêu cầu kiểm tay rồi mới sang P sau.
- Ngoại lệ: P2 chủ yếu là lượt chạy thật do người yêu cầu bấm, nên được làm P3 trong lúc chờ kết quả P2.
- Mỗi P có entry `history/` riêng. Không commit.
- P có đổi logic (P1, P3, P4) phải giữ `sha256` của `products.jsonl` trên cùng bộ interim, chạy cùng ngày
  (`normalise.py --today`), như CP0 của plan 28/09.
- Test chạy bằng:
  `cd src/data_collection && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -q -p no:cacheprovider tests`
  (env `vsf`).
- Kiểm tay trên sandbox `data/local_crawl` qua `./local_crawl.sh`, không dùng bộ demo.

## P1: Chuẩn hoá ngay khi một nguồn cào xong (không đợi cả nhóm)

- **Airflow:** mỗi nguồn là một task riêng. Task chuẩn hoá chỉ phụ thuộc task cào của đúng nguồn đó, không phụ thuộc cả
  nhóm (task group).
- **Vì sao:** vé máy bay đợi điểm tham quan gần 2 phút ở lượt local. Trên VM còn có bước giá phòng Trip nhiều giờ trong
  cùng nhóm, nên vé máy bay và điểm tham quan có thể đợi hàng giờ nếu thứ tự nhóm đổi.
- **Việc làm:**
  - Thêm bảng `STEP_INTERIM`: bước cào → các file interim nó ghi.

    | Bước cào | File interim |
    |---|---|
    | `trip-flights` | `trip_flights` |
    | `trip-attractions` | `trip_attractions` |
    | `vinpearl` | `vinpearl`, `vinpearl_bundles` |
    | `booking-hotels` | `booking_hotels` |
    | `agoda-hotels` | `agoda_hotels` |
    | `price_rooms` | `trip_hotels` |
    | `find_hotels` | (không có) |

  - `run_group`: khi một bước kết thúc, gọi `previewer.source_done(nhóm, các file)`.
    - Chỉ gọi sau lần thử cuối, khi bước đã xong hẳn: ok, bị chặn, hoặc lỗi hết lượt thử.
    - Các trạng thái được chuẩn hoá giống hệt `group_done` hôm nay.
  - `Previewer.source_done`: submit `_normalise_source` cho từng file và ghi nhớ file đã submit.
    - Có chạy liên tục: chốt nguồn bằng `_finish_stream`.
  - `group_done` vẫn chạy khi nhóm xong. Nó chỉ submit các file của nhóm **chưa** được submit, để giữ đúng hành vi cũ khi:
    - bước lỗi làm nhóm dừng giữa chừng;
    - có file interim không nằm trong `STEP_INTERIM`.
  - Gộp nháp sau mỗi nguồn: dùng `_request_merge` như hiện nay (đang gộp thì dồn lại gộp một lần). Quy tắc
    "nguồn cuối cùng của lượt không gộp nháp" chuyển từ mức nhóm xuống mức nguồn.
  - Monitor: không đổi. Bước `normalise.source:<file>` vẫn cùng tên và cùng `group`.
- **Test tự động:**
  - nhóm giả 2 bước, bước 2 chạy lâu: `normalise.source:trip_flights` bắt đầu trước khi bước 2 xong;
  - bước bị chặn (mã 75): file của nó vẫn được chuẩn hoá đúng một lần;
  - bước lỗi làm nhóm dừng: file của bước đã xong không bị chuẩn hoá lại; file của bước lỗi được chuẩn hoá ở `group_done`
    như hôm nay;
  - bước được thử lại (lỗi tạm thời): chỉ chuẩn hoá sau lần thử cuối;
  - nguồn cuối cùng của lượt không kích hoạt gộp nháp;
  - `stream.enabled` bật: `_finish_stream` được gọi theo nguồn, không đợi nhóm;
  - `products.jsonl` trùng `sha256` với cách theo nhóm, trên cùng interim, cùng ngày.
- **Bạn kiểm:** chạy lượt full local.
  - Trong `run.json`, `normalise.source:trip_flights` bắt đầu ngay sau `trip-flights` xong, trong lúc `trip-attractions`
    còn chạy.
  - Trên sơ đồ, ô chuẩn hoá vé máy bay "Xong" khi ô cào điểm tham quan còn "Đang chạy".
- **Xong khi:** không file interim nào đợi bước cào khác trong nhóm mới được chuẩn hoá.

## P2: Lượt kiểm thật cho chế độ chạy liên tục, rồi bật mặc định

- **Airflow:** data-aware scheduling (Datasets): bước sau chạy khi dữ liệu đầu vào có thay đổi, không đợi cả DAG trước xong.
- **Vì sao:**
  - Đây là cách bỏ ~16 phút đợi Vinpearl. Catalog của booking, agoda và Trip vào DB và Search trong lúc Vinpearl còn cào.
  - Code L1–L6 đã có và test pass, chỉ còn thiếu lượt chạy thật (điều kiện bật mặc định ghi ở L6).
- **Việc làm:**
  1. **Lượt local.** Bật ở Cấu hình của sandbox: `stream.enabled=true`, `stream.db=true`, `stream.index=false`,
     `DB_TARGET=local`. Chạy `./local_crawl.sh run full`.
  2. **Ghi số đo** vào entry `history/` của P2:
     - thời gian từ khi mỗi nguồn cào xong tới khi dòng của nó có trong `cdp.products`, lấy từ `db_batches.jsonl`;
     - RAM và CPU đỉnh của tiến trình job (`/proc`, hoặc `docker stats` trên VM);
     - số lô và số lô lỗi của từng việc chạy liên tục (`stream.*` trong `run.json`).
  3. **So kết quả với chế độ theo lô:**
     - chép `interim/` của lượt sang scratchpad;
     - chạy `normalise.py` không dùng checkpoint, cùng `--today`;
     - so `sha256` với `products.jsonl` của lượt.
  4. **Kiểm DB:**
     - không có hai dòng cùng `sourceRef` hoặc cùng ref trong `sameAs` (câu SQL ghi vào entry `history/`);
     - bộ nạp theo phần (`DbFeeder`) không gửi lại dòng chưa đổi nội dung (sửa 2026-09-29: bản đầu ghi "nạp lại cùng
       catalog thì 0 dòng ghi", không đúng vì `load_into_db` luôn gắn `priceRefreshedAt` mới cho mọi dòng);
     - dòng Vinpearl xuất hiện trong DB trước khi Vinpearl cào xong (L2).
  5. **Lượt VM** (nếu người yêu cầu chốt mục 1): như trên, `DB_TARGET=cloud`. Đây là lần đầu nạp theo phần vào staging.
  6. **Bật mặc định** (`fresh_settings.py`) theo mục 2 của "Cần chốt".
     - Cập nhật dòng tiến độ của `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`.
     - Cập nhật bảng đối chiếu Airflow ở plan này (mục cuối) nếu kết quả khác dự kiến.
- **Ngưỡng đạt** (đề xuất):
  - `sha256` trùng;
  - không dòng trùng trong DB;
  - không lô nào lỗi code;
  - RAM đỉnh của job dưới 3 GB trên VM 4 GB;
  - độ trễ cào xong → vào DB không quá `stream.mergeSeconds + stream.dbSeconds` + thời gian một lần nạp.
- **Test tự động:** không thêm, trừ khi lượt thật lộ lỗi. Lỗi nào lộ ra thì thêm test tái hiện rồi mới sửa.
- **Bạn kiểm:** chạy lượt local.
  - `SELECT count(*) FROM cdp.products` tăng dần trong lúc cào.
  - Khi Vinpearl còn cào, sản phẩm booking đã tìm được trên tab Embedding, sau lần index cuối hoặc nếu bật `stream.index`.
- **Xong khi:** `stream.enabled` và `stream.db` bật mặc định, có số đo thật ghi trong `history/`.

## P3: Khai báo đồ thị bước ở một chỗ

- **Airflow:** định nghĩa DAG (task + `>>` phụ thuộc) tách khỏi executor; web UI vẽ sơ đồ từ chính định nghĩa đó.
- **Không** làm executor chung. Job vẫn gọi bước theo thứ tự trong code; bảng này chỉ là dữ liệu.
- **Vì sao:**
  - Thêm bước (P4 thêm cào lại một nguồn) hoặc đổi thứ tự hôm nay phải sửa đồng bộ khoảng 15 hằng số ở hai file.
  - `RESUME_STEPS` đã phải chép tay từ `fresh_catalog.py` sang `monitor.py`.
  - Chạy lại từ một bước đang dùng thứ tự cứng, không suy từ phụ thuộc.
- **Việc làm:**
  - Module mới `pipeline_graph.py`: chỉ khai báo dữ liệu, không import `fresh_catalog` hay `monitor`. Gồm:
    - **nguồn:** khoá, nhãn, công tắc cấu hình, nhóm site, bước cào, file interim, khoá chỉnh live, chế độ chạy
      (gộp `SOURCES` của monitor với `SITE_GROUPS`, `SOURCE_SWITCH`, `LIVE_KEYS`, `GROUP_INTERIM` và `STEP_INTERIM` của P1);
    - **bước:** id, cột trên sơ đồ, nhãn, phụ thuộc (`deps`), chế độ chạy, chạy lại được hay không, việc chạy liên tục
      gắn vào ô nào (thay `GRAPH_SINGLE`, `GRAPH_MODES`, `RESUME_STEPS`, `RESUME_FROM`, `STREAM_STEPS`, `STEP_LABELS`);
    - **hàm suy ra:** `downstream(bước)` (chạy lại từ X thì những bước nào chạy tiếp), `resume_options(ô)`,
      `interim_of(bước cào)`.
  - `fresh_catalog.py` và `monitor.py` đọc từ module này; bỏ các hằng số trùng.
  - Giữ nguyên tên bước trong `run.json`, để lượt cũ vẫn hiện đúng trên monitor.
  - Chia hai lần sửa:
    - **P3a:** module + `fresh_catalog.py`;
    - **P3b:** `monitor.py`, file dài 2.167 dòng.
- **Test tự động:**
  - đồ thị không có vòng; mọi `deps` trỏ tới bước có thật; mỗi nguồn bật được có ít nhất một bước cào và một file interim;
  - `graph()` của 3 lượt thật trong sandbox (`full-20260928T073959Z-221577`, `full-20260928T080824Z-245196`,
    `daily-20260928T100632Z-339485`) cho JSON **giống hệt** trước khi sửa (lưu bản trước vào scratchpad);
  - `downstream` và `resume_options` cho đúng danh sách `RESUME_FROM` hiện nay;
  - **test thứ tự:** chạy `crawl_and_load` giả; mọi bước trong `run.json` bắt đầu sau khi các `deps` của nó kết thúc.
    Test này bắt được lỗi khi code gọi bước sai thứ tự so với bảng;
  - toàn bộ test hiện có vẫn pass.
- **Bạn kiểm:**
  - mở monitor, xem 3 lượt cũ: sơ đồ, nút chạy lại và nhãn không đổi;
  - chạy `resume … --from db` trên một lượt cũ: vẫn chạy đúng như trước.
- **Xong khi:** thêm một nguồn hoặc một bước chỉ cần sửa `pipeline_graph.py` và hàm chạy của bước đó.

## P4: Hạn giờ cho từng nguồn và cào lại một nguồn

- **Airflow:**
  - `execution_timeout` (hạn giờ của task), `dagrun_timeout` (hạn giờ của cả lượt);
  - "Clear" một task cào (CP6 mới làm cho các bước sau cào).
- **Vì sao:**
  - Job mới không có hạn giờ nào (xem Hiện trạng): một nguồn treo giữ lượt và khoá.
  - Nguồn bị chặn hoặc lỗi hôm nay chỉ lấy lại được bằng cách cào lại cả lượt, vài giờ trên VM.

### P4a: Hạn giờ

- **Việc làm:**
  - Cấu hình mới:
    - `timeout.<nguồn>` (phút; 0 = không giới hạn) cho `vinpearl`, `tripFlights`, `tripAttractions`, `booking`, `agoda`,
      `tripHotels.discover`, `tripHotels.prices`;
    - `crawl.maxHours` cho cả phần cào.
    - Mặc định theo mục 3 của "Cần chốt".
  - `run_source` chạy `crawl.py` trong process group riêng (`start_new_session=True`). Quá hạn thì:
    - SIGTERM cả nhóm tiến trình (crawl.py, Chromium), chờ 10 giây, rồi SIGKILL;
    - cách làm giống `terminate_children`, nhưng chỉ nhắm nguồn quá hạn.
  - Bước khách sạn Trip chạy trong tiến trình: thêm hạn giờ vào `run_cancellable` (huỷ task khi quá hạn).
  - Loại lỗi mới `timeout` trong `pipeline_errors.py`, xử lý như `blocked`:
    - không thử lại, vì thử lại sẽ tốn đúng chừng ấy thời gian;
    - nguồn khác đi tiếp;
    - dữ liệu đã ghi được giữ và được chuẩn hoá.
  - Quá hạn cả phần cào (`crawl.maxHours`): mọi nguồn còn chạy bị dừng theo cách trên, rồi lượt đi tiếp sang gộp, kiểm
    tra, nạp DB như hiện nay.
  - Vinpearl quá hạn khi chưa đổi tên `vinpearl.jsonl.tmp`: chuẩn hoá phải đọc được file tạm.
    - Chạy liên tục đã đọc được file tạm (L2).
    - Chế độ theo lô thì cần đổi tên file tạm sau khi dừng. Chỉ đổi khi dòng cuối đầy đủ (bỏ dòng ghi dở).
  - Monitor:
    - ô cào quá hạn hiện "Quá giờ sau N phút";
    - cảnh báo `warning` loại `timeout` qua `alerts.py`.
- **Test tự động:**
  - nguồn giả ngủ lâu hơn hạn: bị dừng đúng lúc, trạng thái `timeout`, nguồn khác xong bình thường, không còn tiến trình con;
  - quá `crawl.maxHours`: lượt vẫn gộp và nạp phần đã có;
  - Vinpearl bị dừng giữa chừng: file tạm với dòng cuối ghi dở được chuẩn hoá, bỏ dòng ghi dở;
  - hạn giờ 0: không giới hạn, như hiện nay.

### P4b: Cào lại một nguồn

- **Việc làm:**
  - Lệnh `fresh_catalog.py resume <mã lượt> --from crawl --source <nguồn>`, kèm `./local_crawl.sh run resume <mã lượt>
    crawl <nguồn>`. Lệnh này:
    1. cào lại **chỉ** nguồn đó vào thư mục của chính lượt; crawl.py tiếp tục từ tiến độ đã lưu nếu có;
    2. chuẩn hoá lại nguồn đó (checkpoint tự nhận ra interim đã đổi nhờ mtime và cỡ file);
    3. gộp từ checkpoint, kiểm tra, nạp DB, index như CP6.
  - Khách sạn Trip (mục 5 của "Cần chốt"):
    - bước tìm ID ghi `trip_targets.run.json` vào thư mục lượt;
    - `--source tripHotels` đọc file này và chỉ chạy bước giá phòng.
  - Ghi vào `resumes` của `run.json`: "cào lại nguồn X lúc …". Bước cào mới nối sau bước cũ; không xoá bước cũ.
  - Monitor: nút "Cào lại nguồn này" trên ô cào của lượt đã kết thúc khi ô đó `blocked`, `error` hoặc `timeout`.
    Dùng khoá hiện có: đang có lượt khác chạy thì bị từ chối.
  - Cảnh báo khi cào lại khác ngày (giờ Việt Nam) với lượt gốc. `normalise.py` dùng ngày hôm nay, nên cửa sổ đặt chỗ của
    **mọi** nguồn trong catalog sẽ theo ngày mới.
- **Test tự động:**
  - lượt giả có agoda bị chặn → cào lại agoda: chỉ `crawl.py agoda-hotels` được gọi;
  - checkpoint của các nguồn khác được dùng lại;
  - `products.jsonl` bằng kết quả khi agoda không bị chặn;
  - hai lệnh cào lại cùng lúc: lệnh thứ hai bị từ chối;
  - lượt đang chạy: không cho cào lại;
  - `--source tripHotels` thiếu `trip_targets.run.json`: báo lỗi rõ, không cào.
- **Bạn kiểm:**
  - đặt hạn giờ booking 1 phút, chạy lượt local: booking "Quá giờ", các nguồn khác vẫn nạp DB;
  - bấm "Cào lại nguồn này" trên ô booking: chỉ booking cào lại, rồi gộp, nạp DB, index.
- **Xong khi:** không lượt nào treo quá hạn đã đặt; mọi nguồn bị chặn, lỗi hoặc quá giờ đều cào lại riêng được.

## Đối chiếu với Airflow (cập nhật 2026-09-29)

Thay bảng ở `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md` cho các dòng dưới. Dòng không nêu ở đây giữ nguyên.

| Airflow | Trong pipeline | Trạng thái |
|---|---|---|
| Clear task | `resume --from normalise\|merge\|validate\|db\|index` (CP6); cào lại một nguồn `--from crawl --source` (P4b) | có |
| `on_failure_callback`, SLA miss | `alerts.py`, `check_sla` (CP7, CP8) | có |
| `dagrun_timeout` | `crawl.maxHours` (P4a); `MAX_HOURS` chỉ áp cho `daily.py` cũ | có |
| `execution_timeout` | `timeout.<nguồn>` (P4a) | có |
| Task group → task theo nguồn | chuẩn hoá theo nguồn khi nguồn xong (P1) | có |
| Datasets (chạy khi dữ liệu đổi) | chạy liên tục L1–L5 | có code, tắt mặc định (P2) |
| Định nghĩa DAG | `pipeline_graph.py` (P3) | có |
| `priority_weight` | thứ tự nhóm theo thời gian chạy trung vị khi `crawl.parallelSites` < số nhóm | chưa, ngoài plan này |

## Rủi ro

- **P1:** gộp nháp chạy thường hơn (sau mỗi nguồn thay vì mỗi nhóm), tốn thêm CPU trên VM 2 CPU. Gộp nháp đã gom yêu cầu dồn
  (mỗi lúc một lần), và có thể tắt bằng `normalise.preview`.
- **P2:**
  - Nạp theo phần để lại dòng trong DB kể cả khi cuối lượt bị chặn chất lượng (đã chốt ở L4).
  - Lượt VM đầu tiên là lần đầu staging thấy dòng xuất hiện dần: báo nhóm FE/agent trước.
- **P3:** sửa nhiều hằng số trong `monitor.py` dễ làm lệch sơ đồ lượt cũ. So `graph()` JSON trước/sau là điều kiện bắt buộc.
- **P4:**
  - SIGTERM giữa chừng có thể để lại interim dòng cuối ghi dở, hoặc state SQLite của collector đang ghi. Phải kiểm
    crawl.py tiếp tục đúng sau khi bị dừng như vậy; nếu không, thêm xử lý dừng êm trong crawl.py.
  - Cào lại khác ngày làm đổi cửa sổ ngày của cả catalog (xem P4b).
