# Pipeline dữ liệu ổn định theo từng bước (không dùng Airflow, áp dụng cách Airflow giải quyết)

- Ngày: 2026-09-28
- Người yêu cầu: Đăng Khôi (theo định hướng của mentor: pipeline dữ liệu "ổn định")
- Phục vụ: FR-CAT-01..04 (catalog đúng, đủ, tươi). PRD chưa có mã NFR riêng cho độ ổn định của pipeline dữ liệu.
- Phạm vi: `src/data_collection` (normalise.py, fresh_catalog.py, fresh_settings.py, monitor, module cảnh báo mới).
  Không đổi PRD, contract, DDL; `products.jsonl` phải giữ nguyên từng dòng so với hiện tại. Ngoại lệ duy nhất có thể
  chạm PRD: kênh gửi cảnh báo ra ngoài ở CP7 (xem CP7).
- Quyết định 2026-09-28 (người yêu cầu): **không dùng Airflow**. Job vẫn là cron → `run_daily_docker.sh` →
  `fresh_catalog.py`. Plan học cách Airflow giải quyết từng vấn đề (retry, skip/fail, clear task, callback, SLA…) rồi
  tự làm bằng Python có sẵn. Lý do: một job mỗi ngày, khoảng 7 nguồn, normalize khoảng 22 giây, VM 2 CPU / 4 GB;
  scheduler, webserver và database metadata của Airflow nặng hơn nhu cầu. Đối chiếu đầy đủ: mục "Đối chiếu với Airflow".
  Thay cho dòng cũ "Bước sau: DAG Airflow chạy thử trên laptop".
- Tiến độ (2026-09-28): CP1–CP5 xong, xem `history/2026-09-28-cp1-…` tới `history/2026-09-28-cp5-…`; CP6 xong
  (`history/2026-09-28-cp6-chay-lai-tu-buoc-loi.md`); CP7, CP8 xong (`history/2026-09-28-cp7-cp8-canh-bao-va-sla.md`).
  Kênh gửi cảnh báo ra ngoài: người yêu cầu để sau (2026-09-28), cảnh báo chỉ ghi file và hiện trên monitor.

## Mục tiêu

"Ổn định" theo người yêu cầu nghĩa là:
- pipeline xử lý liên tục;
- lỗi thì tự thử lại, hoặc xử lý theo chiến thuật riêng cho từng loại lỗi;
- biết log ở đâu, bước nào chậm, lỗi ở đâu thì sửa ở đâu, cần mở rộng chỗ nào;
- không phải cào lại từ đầu khi một bước sau lỗi;
- biết ngay khi lượt lỗi, bị chặn nạp DB hoặc không chạy, mà không cần tự mở monitor (thêm 2026-09-28, CP7–CP8).

## Hiện trạng (trước khi thay đổi)

- `normalise.py main()` là một khối khoảng 250 dòng, chạy tuần tự trong bộ nhớ. Bước sau đợi bước trước xong toàn bộ.
- Normalize chỉ có **một** bước trong `run.json`: không có thời gian hay số dòng riêng từng bước con.
- **Một bản ghi hỏng làm sập cả normalize.** Không có `try/except` quanh phần ánh xạ.
- Khi normalize lỗi, lượt chỉ ghi một dòng thông báo:
  - lỗi `RuntimeError/ValueError/OSError` chỉ in thông báo, không có traceback, không có tên bước;
  - lỗi khác in traceback sau khi `RunRecorder.finish()` đã trả stdout/stderr về luồng gốc, nên traceback **không nằm trong `job.log`**.
- Mọi lỗi đều như nhau: không thử lại, lượt dừng, muốn có dữ liệu phải cào lại cả lượt.
  - Ví dụ 28/09: `sqlite3 database is locked` ở trip → cả lượt không nạp DB.
  - Ví dụ 25/09: lỗi code `fetch_json` ở Vinpearl → 0 tour mà không ai biết, vì bị coi như cảnh báo.
- Bản nháp (`Previewer`) chạy lại **toàn bộ** normalize mỗi khi một site xong; bản chính thức lại ánh xạ lại tất cả.
- Số đo hiện có (interim thật 49 MB, 7 nguồn, profiler): toàn bộ ~22 giây, ~290 MB RAM.
  - Ánh xạ ~9 giây (booking 4,3 + agoda 4,4).
  - Ghi ảnh chụp cho monitor ~7 giây.
  - Gộp trùng khách sạn ~3 giây.
  - Các bước còn lại < 1 giây mỗi bước.

## Cách làm việc

- Mỗi checkpoint (CP) là một thay đổi nhỏ, làm **tuần tự**. Ngoại lệ: CP7 không phụ thuộc CP6, có thể làm trước CP6. CP sau chỉ bắt đầu khi CP trước:
  1. có test tự động pass;
  2. với CP có đổi logic (CP2, CP4, CP5): `sha256` của `products.jsonl` trước/sau giống nhau (CP0);
  3. người yêu cầu đã kiểm tay theo mục "Bạn kiểm" và đồng ý.
- Mỗi CP có entry `history/` riêng. Không commit; người yêu cầu tự commit sau mỗi CP nếu muốn.
- Test chạy bằng:
  `cd src/data_collection && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -q -p no:cacheprovider tests`
  (env `vsf`).
- Kiểm tay trên bộ thử `data/local_crawl` (không dùng bộ demo).

## CP0 — So trước/sau (không viết test riêng)

Cập nhật 2026-09-28: người yêu cầu bỏ golden test dạng test tự động ở bước đầu.

- **Vì sao:** chỉ CP2, CP4, CP5 động vào logic normalize. CP1 và CP3 không đổi output, test hiện có là đủ.
- **Cách làm ở CP2, CP4, CP5:** so `sha256` của `products.jsonl` trước và sau khi sửa.
  - Chạy trên cùng bộ interim (bản sao interim 49 MB ở máy local, trong `data/` Git ignore).
  - Chạy **cùng ngày**, vì `normalise.py` dùng `date.today()` / `datetime.now()` (dòng ~2705, ~1413) nên output đổi theo ngày.
  - Khác thì `diff` hai file để xem dòng nào đổi.
- **Khi nào viết thành golden test thật:** khi CP4 kéo dài nhiều ngày, có người khác cùng sửa, hoặc cần chạy trong CI.
  Lúc đó thêm tuỳ chọn `--today` cho `normalise.py` để cố định ngày, rồi viết `tests/test_normalise_golden.py`
  (bỏ qua khi không đặt `NORMALISE_GOLDEN_DIR`).

## CP1 — Đo từng bước normalize (quan sát trước, sửa sau)

- **Vì sao:** "nghẽn ở một đoạn là không biết xử lý ở đâu". Phải thấy thời gian, số dòng và lỗi của từng bước **trước** khi quyết định sửa hay song song chỗ nào.
- **Trước:**
  - không biết bước nào chậm; số đo ở trên phải chạy profiler bằng tay;
  - lỗi không có tên bước; traceback có thể mất khỏi `job.log`.
- **Việc làm:**
  - Trong `normalise.py`, bọc từng bước của `main()` bằng `with stage("tên", rows_in=...)`. Mỗi bước ghi:
    - thời gian bắt đầu và kết thúc, số giây;
    - số dòng vào → ra;
    - RAM đỉnh (`resource.getrusage`);
    - khi lỗi: tên bước + traceback rút gọn.
  - Log thêm dòng `normalise.step.start name=… / normalise.step.done name=… seconds=… in=… out=…`.
  - Ghi `normalise_stages/steps.json`. Có ghi cả khi lỗi, để biết chết ở bước nào.
  - `fresh_catalog.py`: khi normalize lỗi, `run.json` và `job.log` có **tên bước + traceback** (ghi trước khi `RunRecorder` trả luồng về).
  - Monitor, tab Chuẩn hoá: bảng "bước · giây · vào → ra · RAM · lỗi". Tab Luồng & nguồn có dòng "normalize đang ở bước X, N giây".
  - Hạ mức nén gzip của ảnh chụp (9 → 1) nếu số đo xác nhận đây là chỗ tốn ~1/3 thời gian.
- **Test tự động:**
  - `steps.json` có đủ các bước, giây ≥ 0, số dòng khớp `stages.json`;
  - monkeypatch một bước ném lỗi → `steps.json` và `run.json` ghi đúng tên bước và traceback;
  - toàn bộ test hiện có vẫn pass.
- **Bạn kiểm:**
  - chạy một lượt test nhỏ, mở tab Chuẩn hoá xem bảng thời gian;
  - tìm dòng `normalise.step` trong Log trực tiếp.
- **Xong khi:** nhìn monitor trả lời được "bước nào chậm nhất, lỗi ở bước nào".

## CP2 — Cô lập lỗi theo bản ghi + hàng lỗi

- **Vì sao:** một bản ghi hỏng không được làm mất cả catalog. Đây là cách rẻ nhất để tăng ổn định.
- **Trước:** một exception ở một bản ghi làm sập cả normalize.
- **Việc làm:**
  - Bọc từng lời gọi ánh xạ (`booking_hotel(r)`, `vinpearl_tour_product(r)`…) và các hàm xử lý từng dòng. Lỗi thì ghi `normalise_stages/errors.jsonl`: bước, nguồn, khoá bản ghi, loại lỗi, thông báo, traceback ngắn. Sau đó đi tiếp.
  - **Ngưỡng an toàn:** nếu tỉ lệ bản ghi lỗi của một nguồn vượt `normalise.maxErrorRate` (Cấu hình, mặc định 5%) thì dừng bước với lỗi rõ ràng. Lý do: lỗi code làm hỏng mọi bản ghi không được lặng lẽ bỏ hết dữ liệu. Đây chính là trường hợp `fetch_json` ngày 25/09.
  - Monitor: danh sách bản ghi lỗi (lọc theo nguồn, bước, loại lỗi), mở được bản ghi interim gốc.
- **Test tự động:**
  - một bản ghi sai kiểu → normalize xong, `errors.jsonl` có đúng một dòng, các dòng khác đủ;
  - 100% bản ghi của một nguồn lỗi → bước dừng với thông báo có tên nguồn và tỉ lệ;
  - so `sha256` trước/sau trên interim 49 MB: giống nhau, `errors.jsonl` rỗng.
- **Bạn kiểm:** chạy normalize trên thư mục thử có một dòng interim bị sửa hỏng; xem nó hiện ở danh sách lỗi.
- **Xong khi:** lỗi dữ liệu lẻ tẻ không làm hỏng lượt; lỗi hàng loạt vẫn dừng và báo rõ.

## CP3 — Phân loại lỗi và chiến thuật cho từng loại

- **Vì sao:** "lỗi thì tự retry, hoặc có chiến thuật khác theo log". Thử lại vô điều kiện sẽ làm hại khi bị chặn (dồn thêm request) và vô ích khi lỗi code.
- **Trước:** mọi lỗi như nhau; không thử lại ở mức bước/nguồn (chỉ có thử lại request bên trong collector).
- **Việc làm:** module `pipeline_errors.py` gồm các loại lỗi, cách nhận ra và chiến thuật:

  | Loại | Nhận ra từ | Chiến thuật |
  |---|---|---|
  | `TransientError` | timeout, HTTP 429/5xx, `database is locked`, lỗi mạng | thử lại bước/nguồn đó N lần, chờ tăng dần (backoff); N và thời gian chờ ở Cấu hình |
  | `BlockedError` | `crawl.py` mã 75, captcha, HTTP 403, "0 nơi lưu trú" ở trang lẽ ra có dữ liệu | không thử lại ngay; đánh dấu nguồn **bị chặn**, các nguồn khác đi tiếp, ghi rõ trên monitor |
  | `RecordError` | lỗi một bản ghi (CP2) | vào hàng lỗi, không thử lại |
  | `CodeError` | vượt ngưỡng CP2, exception lập trình ở bước | dừng ngay, không thử lại, báo tên bước + traceback |
  | `QualityGateError` | `validate_run` thiếu nhóm bắt buộc; số sản phẩm tụt > X% so với lượt trước | không nạp DB, giữ dữ liệu cũ, báo |
  | `InfraError` | Postgres, Weaviate, Cohere không kết nối được | thử lại với thời gian dài hơn; vẫn lỗi thì giữ checkpoint để chạy lại (CP6) |

  - `crawl_sites()` và các bước sau áp chiến thuật theo loại lỗi. Mỗi lần thử lại, bỏ qua hay dừng đều ghi vào `run.json` và log, và hiện trên monitor.
  - **Giữ quy tắc nạp DB hiện tại** ("được cả hoặc không có gì"). Nguồn bị chặn vẫn làm lượt không nạp DB như hôm nay, nhưng mọi bước khác chạy xong và lý do được ghi rõ. Nạp phần thành công là quyết định A/B, để sau.
- **Test tự động:** nguồn giả trả từng loại lỗi:
  - Transient: thử lại đúng N lần rồi thành công hoặc thất bại;
  - Blocked: không thử lại, nguồn khác vẫn chạy;
  - Code: dừng ngay;
  - QualityGate: không gọi nạp DB;
  - Infra: thử lại với thời gian dài.
  - Toàn bộ test hiện có vẫn pass.
- **Bạn kiểm:** chạy lại tình huống ngày 28/09 bằng test giả lập `database is locked` → thấy dòng "thử lại lần 1/…" rồi thành công.
- **Xong khi:** mỗi lỗi trên monitor có loại, và chiến thuật đã áp dụng hiện ngay bên cạnh.

## CP4 — Tách normalize thành các bước có checkpoint

- **Vì sao:**
  - để chạy lại **từng bước** mà không chạy lại cả khối;
  - để phần theo nguồn chạy được ngay khi nguồn đó cào xong (CP5);
  - mỗi bước là một hàm vào → ra theo file, giống task của Airflow: chạy lại riêng được, không giữ trạng thái trong bộ nhớ.
- **Trước:** một hàm `main()`; output trung gian chỉ là ảnh chụp để xem, không dùng để chạy tiếp.
- **Việc làm:**
  - `normalise_source(nguồn, interim, out)`: đọc interim của một nguồn → ánh xạ → ghi `normalised/<nguồn>.jsonl` (checkpoint).
  - `merge_catalog(normalised/, out)`: đọc các checkpoint → các bước còn lại → `products.jsonl`.
  - `main()` = gọi `normalise_source` cho từng nguồn rồi `merge_catalog`. CLI cũ giữ nguyên; thêm `--only-source <nguồn>` và `--merge-only`.
  - **Chia bước theo đúng thứ tự hiện tại.** Nhiều bước làm giàu đang chạy **sau** gộp trùng trên dòng đã gộp: mô tả tiếng Việt, chuẩn hoá thuộc tính, gộp biến thể giá, loại giá phòng bất thường. Chuyển chúng lên trước gộp có thể đổi output. Vì vậy:
    - phần theo nguồn ban đầu chỉ gồm **đọc interim + ánh xạ + sửa điểm đến/toạ độ theo nguồn** (phần nặng nhất, ~9 giây);
    - các bước khác chỉ chuyển sang phần theo nguồn khi so `sha256` chứng minh output không đổi.
- **Test tự động:**
  - trên interim 49 MB ở máy local: `products.jsonl` trùng `sha256` với bản chạy trước khi sửa (cùng ngày);
  - `--only-source booking` rồi `--merge-only` cho cùng kết quả với chạy một lần.
- **Bạn kiểm:** thư mục lượt có `normalised/<nguồn>.jsonl`; xoá `products.jsonl` rồi chạy `--merge-only` → file được dựng lại giống hệt.
- **Xong khi:** mỗi bước chạy độc lập được từ checkpoint của bước trước.

## CP5 — Normalize theo nguồn ngay khi nguồn cào xong (song song)

- **Vì sao:**
  - không phải đợi mọi nguồn cào xong mới normalize;
  - các nguồn normalize song song, không đợi nhau;
  - thay bản nháp đang chạy lại toàn bộ normalize.
- **Trước:** bản nháp chạy lại toàn bộ normalize mỗi lần một site xong; bản chính thức lại ánh xạ lại tất cả.
- **Việc làm:**
  - Khi một nhóm site xong, `crawl_sites()` chạy `normalise_source` cho các nguồn của nhóm trong tiến trình riêng (song song, có thử lại theo CP3). Sau đó chạy `merge_catalog` trên các checkpoint đang có, thay cho bản nháp.
  - Khi mọi nhóm xong, chỉ còn `merge_catalog` lần cuối.
  - Monitor, tab Chuẩn hoá: bảng **nguồn × bước**: trạng thái, giây, vào → ra, số lỗi.
- **Test tự động:**
  - `crawl_sites` giả với 4 nhóm xong lệch giờ → `normalise_source` của nhóm A chạy khi nhóm B còn đang chạy;
  - bước gộp cuối chỉ đọc checkpoint;
  - output cuối trùng `sha256` bản chạy trước khi sửa.
  - Một nguồn normalize lỗi → các nguồn khác vẫn xong, lỗi được phân loại theo CP3.
- **Bạn kiểm:** chạy lượt test 4 site; trên monitor thấy booking normalize xong trong lúc agoda còn cào.
- **Xong khi:** khi site cuối xong, catalog chính thức có sau vài giây (chỉ còn phần của site cuối + bước gộp).

## CP6 — Chạy lại từ bước lỗi

- **Vì sao:** cào mất nhiều giờ. Lỗi ở normalize, kiểm tra, nạp DB hay embed thì phải chạy lại **từ bước đó**, dùng lại raw, interim và checkpoint. Đây là tương đương nút "Clear" của Airflow.
- **Trước:** muốn có dữ liệu thì phải bấm Cào lớn lại, cào lại tất cả.
- **Việc làm:**
  - `fresh_catalog.py resume <mã lượt> --from normalise|merge|validate|db|index`, kèm lệnh `./local_crawl.sh run resume …`.
  - Ghi vào `run.json` của chính lượt đó, có dòng "chạy lại từ bước X lúc …".
  - Monitor: nút "Chạy lại từ bước này" ở bước lỗi; dùng khoá hiện có để không chạy trùng.
- **Test tự động:**
  - lượt giả lỗi ở normalize → sửa lỗi → resume từ normalize: không gọi cào, output đúng như chạy một lần;
  - resume từ db dùng đúng `products.jsonl` đã có;
  - hai lệnh resume cùng lúc → lệnh thứ hai bị từ chối.
- **Bạn kiểm:** tái hiện lượt lỗi (ví dụ cố ý đặt sai `COHERE_API_KEY` để index lỗi) → sửa → bấm chạy lại từ bước index → xong mà không cào lại.
- **Xong khi:** mọi bước sau cào đều chạy lại được riêng.

## CP7 — Cảnh báo khi lượt lỗi (tương đương `on_failure_callback` của Airflow)

- **Vì sao:** lỗi hiện chỉ thấy khi tự mở monitor hoặc `job.log`.
  - 25/09: lỗi code `fetch_json` làm Vinpearl ra 0 tour mà không ai biết.
  - 28/09: `database is locked` làm cả lượt không nạp DB; chỉ biết khi mở monitor.
- **Trước:** trạng thái lượt nằm trong `run.json`, `job.log` và monitor; không có gì tự báo tới người vận hành.
- **Việc làm:**
  - Module `alerts.py`. Một cảnh báo gồm: mức (`error` / `warning`), loại (theo `pipeline_errors.py`, thêm `sla` cho CP8),
    mã lượt, bước, nguồn, thông báo ngắn, đường dẫn tới lượt trên monitor.
  - Khi nào tạo cảnh báo:
    - `error`: lượt kết thúc lỗi (code, unknown, hoặc transient/infra đã hết số lần thử lại);
    - `error`: quality gate chặn nạp DB (`validate_run`, `quality.maxDropPercent`);
    - `warning`: có nguồn bị chặn (blocked), lượt vẫn chạy tiếp các nguồn khác;
    - `warning`: có bản ghi lỗi (`errors.jsonl` không rỗng) nhưng dưới ngưỡng `normalise.maxErrorPercent`.
  - Chống báo dồn: mỗi lượt gửi **một** tin tóm tắt lúc lượt kết thúc. Cùng loại + cùng bước + cùng nguồn đã báo
    trong `alert.cooldownHours` thì không gửi lại, chỉ ghi file.
  - Luôn ghi `alerts.jsonl` trong thư mục lượt. Monitor hiện dải cảnh báo ở đầu trang và danh sách cảnh báo lọc
    theo mức, loại, nguồn. Phần này không cần kênh ngoài và không chạm PRD.
  - **Kênh gửi ra ngoài — chờ người yêu cầu chốt:** Telegram bot, email hoặc một webhook chung.
    - Kênh nào cũng cần một secret (token hoặc URL). Thêm biến bí mật vào bảng `docs/prd/deployment-plan.md` §2 là đổi
      PRD, nên phải có đề xuất trong `docs/prd/update/` được chốt **trước** khi code phần gửi (AGENTS.md mục 8).
    - Chưa chốt thì CP7 chỉ làm phần ghi file và monitor.
  - Gửi là best effort: timeout ngắn; gửi lỗi thì ghi "gửi cảnh báo thất bại" vào `alerts.jsonl` và `job.log`, không
    đổi trạng thái lượt. Nội dung cảnh báo không chứa secret, DSN hay token.
  - Cấu hình: `alert.enabled`, `alert.minLevel`, `alert.cooldownHours`.
- **Test tự động:**
  - lượt giả lỗi code ở bước `db` → `alerts.jsonl` có đúng một dòng `error`, đúng loại và bước;
  - quality gate chặn nạp DB → một cảnh báo `error`; nguồn bị chặn → một cảnh báo `warning`, nguồn khác vẫn chạy;
  - hai lượt cùng lỗi trong thời gian cooldown → bộ gửi giả chỉ được gọi một lần, `alerts.jsonl` vẫn đủ hai dòng;
  - bộ gửi ném lỗi hoặc treo quá timeout → lượt kết thúc đúng trạng thái cũ, có dòng "gửi cảnh báo thất bại";
  - nội dung gửi không chứa giá trị của biến bí mật trong env;
  - lượt thành công, không bản ghi lỗi → không có cảnh báo.
- **Bạn kiểm:** cố ý đặt sai `COHERE_API_KEY` → bước index lỗi → thấy cảnh báo trên monitor (và ở kênh ngoài nếu đã chốt).
- **Xong khi:** mọi lượt lỗi hoặc bị chặn nạp DB đều tạo cảnh báo mà không cần ai mở monitor.

## CP8 — SLA: phát hiện lượt không chạy, chạy quá lâu, catalog cũ (tương đương SLA miss của Airflow)

- **Vì sao:** CP7 chỉ báo lỗi mà pipeline tự bắt được. Có loại lỗi "im lặng" không ném exception nào:
  - cron không gọi tick, hoặc `schedule.enabled` bị tắt nhầm;
  - lượt treo, hoặc một bước sau cào chạy lâu bất thường;
  - lượt bị bỏ qua vì khoá cũ còn giữ;
  - lượt "thành công" nhưng DB không được nạp mới nhiều ngày liền.
- **Trước:** `MAX_HOURS` chỉ giới hạn phần cào. Không có gì kiểm "hôm nay đã có catalog mới chưa".
- **Việc làm:** ba quy tắc SLA, ngưỡng nằm trong Cấu hình (giá trị mặc định dưới đây là đề xuất, người yêu cầu chỉnh):
  - **Hạn xong trong ngày** `sla.finishBy` (giờ Việt Nam, đề xuất 19:00 = `schedule.time` 02:00 + `MAX_HOURS` 16 + dự phòng):
    tới giờ này mà hôm nay có lịch chạy nhưng chưa có lượt kết thúc → cảnh báo `sla`.
  - **Bước chậm bất thường** `sla.slowFactor` (đề xuất 3): một bước sau cào (normalize, merge, validate, db, index)
    chạy lâu hơn N lần trung vị của chính bước đó trong các lượt đang giữ (`runs.keep`) → cảnh báo `warning`.
    Chưa đủ 3 lượt lịch sử thì bỏ qua quy tắc này.
  - **Catalog cũ** `sla.maxCatalogAgeHours` (đề xuất 48): lần nạp DB thành công gần nhất cũ hơn ngưỡng → cảnh báo `error`.
    Quy tắc này bám trực tiếp FR-CAT "tươi".
  - Kiểm ở đâu:
    - mỗi lần cron gọi `fresh-run tick`, kể cả tick rảnh. Kiểm SLA chỉ đọc `run.json` và file trạng thái, nên tick rảnh
      vẫn không cần thông tin kết nối DB như hiện nay;
    - lượt đang chạy tự kiểm bước chậm khi mỗi bước kết thúc;
    - monitor hiện dòng "SLA hôm nay: đạt / trễ / chưa tới hạn".
  - Vi phạm gửi qua CP7 với loại `sla`. Mỗi quy tắc báo tối đa một lần mỗi ngày.
  - Cấu hình: `sla.enabled`, `sla.finishBy`, `sla.slowFactor`, `sla.maxCatalogAgeHours`.
- **Giới hạn:** VM hoặc cron chết thì tick không chạy và không ai báo, giống Airflow khi scheduler chết. Muốn bắt được
  cần một heartbeat kiểm từ bên ngoài VM (dead man's switch); không thuộc plan này.
- **Test tự động:**
  - quá `sla.finishBy`, hôm nay có lịch nhưng chưa có lượt xong → một cảnh báo `sla`; tick lần hai cùng ngày không báo lại;
  - lượt xong trước hạn → không báo; hôm nay không có lịch (daily tắt) → không báo;
  - lần nạp DB gần nhất cũ hơn ngưỡng → cảnh báo `error`;
  - bước chậm gấp N lần trung vị → cảnh báo; dưới 3 lượt lịch sử → không báo;
  - tick rảnh vẫn chạy được khi không có biến kết nối DB.
- **Bạn kiểm:** đặt `sla.finishBy` về một giờ đã qua khi hôm nay chưa có lượt → chờ tick kế tiếp → thấy cảnh báo SLA.
- **Xong khi:** "hôm nay không có catalog mới" luôn sinh cảnh báo, dù không có exception nào.

## Kiến thức nên học kèm

| CP | Khái niệm |
|---|---|
| CP0 | regression check / golden test: khoá output để refactor an toàn |
| CP1 | observability: metrics theo bước, structured log, traceback |
| CP2 | dead-letter queue, error budget / ngưỡng lỗi |
| CP3 | phân loại lỗi, retry với exponential backoff, fail-fast, quality gate, circuit breaker (tạm dừng nguồn bị chặn) |
| CP4 | checkpoint, idempotency (chạy lại cho cùng kết quả), tách hàm thuần vào → ra |
| CP5 | fan-out / fan-in, song song theo dữ liệu, tiến trình và GIL |
| CP6 | resume / "clear task" của orchestrator, idempotency khi chạy lại |
| CP7 | alerting, callback khi lỗi, chống báo dồn (dedup, cooldown), best-effort side effect |
| CP8 | SLA / SLO, freshness check, dead man's switch |

## Đối chiếu với Airflow

Không dùng Airflow; bảng dưới là khái niệm của Airflow và chỗ tương ứng trong pipeline.

| Airflow | Trong pipeline | Trạng thái |
|---|---|---|
| `schedule` | cron gọi `fresh-run due/tick`, `schedule.*` trong Cấu hình | có |
| `max_active_runs=1` | khoá `fresh_catalog.lock` (`fcntl`) | có |
| `dagrun_timeout` | `MAX_HOURS`: hết giờ dừng êm, publish phần đã cào | có |
| Task, thứ tự task | cào → normalize theo nguồn → merge → validate → db → maintain → index | có |
| Dynamic task mapping | normalize từng nguồn khi nguồn đó cào xong (CP5) | có |
| Pools / parallelism | số site cào song song, số worker normalize | có |
| XCom (truyền dữ liệu giữa task) | file checkpoint `normalised/<nguồn>.jsonl` (CP4) | có |
| `retries`, `retry_exponential_backoff` | `with_retry`, `retry.*` (CP3) | có |
| `AirflowSkipException` / `AirflowFailException` | loại lỗi trong `pipeline_errors.py` (CP3) | có |
| Trigger rules | nguồn bị chặn, nguồn khác vẫn chạy; nạp DB vẫn "được cả hoặc không có gì" | một phần |
| Không có sẵn | cô lập lỗi theo bản ghi, `errors.jsonl`, ngưỡng lỗi (CP2) | có |
| Data quality check | `validate_run`, `quality.maxDropPercent` | có |
| Grid view, task log | `run.json`, `steps.json`, `job.log`, monitor | có |
| Variables | Cấu hình: monitor → env → mặc định (`fresh_settings.py`) | có |
| Log retention | `prune_runs`, `runs.keep` | có |
| Clear task | `resume --from` (CP6) | chưa |
| `on_failure_callback`, `email_on_failure` | cảnh báo (CP7) | chưa |
| SLA miss | SLA (CP8) | chưa |
| Backfill / catchup | không áp dụng: giá là dữ liệu sống, không cào lại được ngày đã qua | bỏ |
| Executor phân tán, sensors, nhiều DAG, phân quyền | không cần: một VM, một job, không có upstream phải chờ | bỏ |

## Rủi ro

- Tách bước (CP4) có thể đổi output ở ca biên → so `sha256` trên 49 MB là điều kiện bắt buộc; viết golden test nếu CP4 kéo dài.
- Chạy normalize song song với cào (CP5) thêm CPU/RAM: phải theo dõi trên VM 2 CPU / 4 GB. Có công tắc tắt như bản nháp hiện nay.
- Monitor cần khởi động lại sau mỗi CP có đổi API.
- Cảnh báo quá nhiều (CP7, CP8) làm người vận hành bỏ qua: mặc định chỉ gửi mức `error`, `warning` chỉ hiện trên monitor.
- SLA dựa trên cron tick: VM hoặc cron chết thì không có cảnh báo (xem giới hạn ở CP8).
