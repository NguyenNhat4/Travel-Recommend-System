# Monitor: hiển thị mỗi lượt thành sơ đồ luồng

- Ngày: 2026-09-28
- Người yêu cầu: Đăng Khôi
- Phục vụ: FR-CAT-01..04 (catalog đúng, đủ, tươi), qua việc vận hành job cào. PRD chưa có mã NFR riêng cho
  công cụ vận hành pipeline dữ liệu.
- Phạm vi: `src/data_collection/monitor_ui/index.html`, `src/data_collection/monitor.py` (thêm API, không bỏ API cũ),
  test monitor trong `src/data_collection/tests/`. Không đổi PRD, contract, DDL. Không đổi job
  (`fresh_catalog.py`, `normalise.py`) và định dạng `run.json` / `steps.json`; monitor chỉ đọc.
- Liên quan: `docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md`. Làm plan này **trước** CP6–CP8 của plan đó, vì:
  - nút "Chạy lại từ bước này" (CP6) sẽ nằm trong panel chi tiết của ô;
  - cảnh báo (CP7) và SLA (CP8) sẽ nằm ở trang Tổng quan mới.
- Tiến độ (2026-09-28): UI1, UI2 xong (`history/2026-09-28-ui1-api-so-do-luong.md`, `history/2026-09-28-ui2-so-do-thay-tab.md`);
  UI2b xong (`history/2026-09-28-ui2b-buoc-con-chuan-hoa-gop.md`); UI3, UI4, UI5 xong (`history/2026-09-28-ui3-…`,
  `-ui4-…`, `-ui5-…`). Người yêu cầu (2026-09-28): làm hết rồi review một lần.

## Mục tiêu

Người yêu cầu thấy monitor hiện tại rối ở bốn chỗ; mỗi chỗ có một thay đổi tương ứng:

| Chỗ rối | Thay đổi |
|---|---|
| Quá nhiều tab mỗi lượt (9 tab ngang nhau) | sơ đồ các bước; bấm một ô thì chỉ hiện những gì thuộc bước đó (UI2) |
| Khó thấy lỗi ở đâu | dải lỗi ở đầu lượt, ô lỗi được chọn sẵn, đường tới ô lỗi tô đỏ (UI3) |
| Khó so các lượt | Lịch sử: mỗi lượt một dòng có dải ô trạng thái các bước (UI4) |
| Tổng quan dài và lộn xộn | Tổng quan chỉ còn trạng thái hiện tại, lượt kế tiếp, cảnh báo; phần kỹ thuật sang trang Hệ thống (UI5) |

Cách hiển thị học theo Graph view (một lượt) và Grid view (nhiều lượt) của Airflow; không dùng Airflow
(xem plan normalize).

## Hiện trạng (trước khi thay đổi)

- Một file `monitor_ui/index.html` (~320 dòng, JS thuần, không thư viện), server là `monitor.py`
  (`http.server`, API JSON dưới `/api/…`).
- Thanh trên: Tổng quan · Lịch sử lượt · Khách sạn Trip · Cấu hình.
- Tổng quan gồm chung một trang: 4 ô số, nút điều khiển lượt, "Nơi lượt kế tiếp ghi dữ liệu", bảng lượt gần nhất,
  log runner, biến kết nối.
- Mở một lượt: 9 tab — Luồng & nguồn, Theo thành phố, Log trực tiếp, Raw / interim, Chuẩn hoá, Catalog cuối,
  Nạp DB, Embedding, Báo cáo.
- Không có URL theo trạng thái (không dùng `location.hash`): tải lại trang là về Tổng quan.
- Dữ liệu bước có sẵn:
  - `run.json` → `steps[]`: `name`, `group`, `label`, `status`, `startedAt`, `finishedAt`, `seconds`, `detail`,
    và `error` / `errorKind` khi lỗi;
  - tên bước thực tế: `maintain`; bước cào theo site (`vinpearl`, `booking-hotels`, `agoda-hotels`, `trip-flights`,
    `trip-attractions`, `trip-hotels.discover`, `trip-hotels.prices`); `normalise.source:<nguồn>` (có `group`);
    `normalise.preview` (bản nháp, lặp nhiều lần); `normalise` (gộp chính thức); `validate`; `db`; `index`;
  - `normalise_stages/steps.json` (bước con của normalize) và `normalised/<nguồn>.errors.jsonl`;
  - `monitor.py` `SOURCES` đã ánh xạ bước cào → nguồn → thư mục raw/interim.
- Lượt cũ trước CP5 không có `normalise.source:*`, chỉ có một bước `normalise`.

## Thiết kế

### Mô hình ô và đường nối

Tính ở server (`FreshMonitor.graph(run_id)`) để test được bằng Python và để UI không phải biết tên bước.

- Cột, từ trái sang phải: **Chuẩn bị** (`maintain`) → **Cào** (mỗi site một ô) → **Chuẩn hoá** (mỗi nguồn một ô)
  → **Gộp** (`normalise`) → **Kiểm tra** (`validate`) → **Nạp DB** (`db`) → **Index** (`index`).
- Mỗi site một hàng: ô cào nối tới các ô chuẩn hoá của nó (Vinpearl nối tới `vinpearl` và `vinpearl_bundles`;
  trip.com khách sạn là hai ô `discover` → `prices`). Mọi ô chuẩn hoá nối vào ô Gộp.
- `normalise.preview` không thành ô riêng; ô Gộp hiện "bản nháp: N lần".
- Bước không thuộc chế độ của lượt (vd. lượt `index` không cào) vẫn vẽ nhưng mờ, trạng thái "Không thuộc lượt",
  để sơ đồ các lượt luôn cùng hình.
- Lượt cũ không có `normalise.source:*`: vẽ một ô Chuẩn hoá chung.
- Mỗi ô có: tên, trạng thái (màu **và** chữ, không chỉ dựa vào màu), số giây, dòng vào → ra, số bản ghi lỗi,
  số lần thử lại. Ô đang chạy có số giây tăng dần.
- Toàn bộ quy tắc ghép tên bước → ô nằm ở một chỗ trong `monitor.py`, cạnh `SOURCES`, để khi job thêm bước
  (CP6–CP8) chỉ sửa một chỗ.

### Panel chi tiết của ô

Bấm một ô thì panel bên dưới sơ đồ hiện nội dung của bước đó. Các tab hiện tại được chia về từng loại ô; API cũ
giữ nguyên và được gọi lại với bộ lọc theo nguồn/bước.

| Ô | Nội dung panel (lấy từ tab cũ) |
|---|---|
| Mọi ô | thời gian, trạng thái, loại lỗi + thông báo + traceback, các lần thử lại; log lọc theo bước/nguồn (Log trực tiếp) |
| Cào | Raw / interim của nguồn đó; tốc độ và điều khiển trực tiếp (Luồng & nguồn) |
| Chuẩn hoá (nguồn) | dòng đã chuẩn hoá, bản ghi lỗi `errors.jsonl`, truy vết một sản phẩm (Chuẩn hoá) |
| Gộp | bảng bước con từ `steps.json`, gộp trùng, bị loại; Catalog cuối; Theo thành phố |
| Kiểm tra | kết quả kiểm tra và Báo cáo |
| Nạp DB | bảng trước → sau (Nạp DB) |
| Index | Embedding |
| Chuẩn bị | số dòng bảo trì (`detail`) |

- Đầu lượt vẫn có nút "Log toàn lượt", vì có dòng log không thuộc bước nào.
- Màn hình hẹp (< 700 px): sơ đồ chuyển thành danh sách dọc theo cột, panel mở ngay dưới ô được bấm.

### Chọn sẵn ô và đường dẫn

- Mở một lượt: lỗi thì chọn ô lỗi đầu tiên; đang chạy thì chọn ô đang chạy; xong thì chọn ô cuối cùng đã chạy.
- URL giữ trạng thái: `#run=<mã lượt>&node=<ô>&view=<phần của panel>`. Tải lại trang hoặc gửi link cho người khác
  mở đúng chỗ.

### Trang Lịch sử

- Mỗi lượt một dòng: bắt đầu (giờ VN), chế độ, trạng thái, **dải ô** theo 7 cột của sơ đồ, tổng thời gian,
  số sản phẩm, chênh lệch số sản phẩm so với lượt trước cùng chế độ.
- Ô Cào và Chuẩn hoá trong dải lấy trạng thái xấu nhất trong các nguồn; di chuột (hoặc chạm) để xem từng nguồn.
- Bấm một ô trong dải thì mở lượt đó với ô tương ứng được chọn sẵn.
- Lọc theo chế độ và trạng thái.

### Trang Tổng quan và Hệ thống

- Thanh trên mới: **Tổng quan · Lịch sử · Hệ thống · Cấu hình**. Nút chạy lượt (auto / full / daily / index)
  và nút Dừng chuyển lên thanh trên, luôn nhìn thấy.
- Tổng quan chỉ còn:
  - sơ đồ thu nhỏ của lượt đang chạy (hoặc lượt gần nhất), bấm vào để mở lượt;
  - lượt kế tiếp theo lịch;
  - chỗ dành cho cảnh báo (CP7) và dòng SLA hôm nay (CP8); chưa có thì ẩn.
- Hệ thống: nơi lượt kế tiếp ghi dữ liệu, biến kết nối, log runner, dung lượng dữ liệu giữ lại, và nội dung trang
  Khách sạn Trip hiện tại (đề xuất gộp vào đây; người yêu cầu có thể giữ nó là mục riêng).

## Checkpoint

Làm tuần tự như plan normalize: CP sau chỉ bắt đầu khi CP trước có test pass và người yêu cầu đã kiểm tay.
Mỗi CP có entry `history/` riêng; không commit. Test chạy bằng
`cd src/data_collection && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<repo>/src python -m pytest -q -p no:cacheprovider tests`
(env `vsf`). Kiểm tay trên bộ `data/local_crawl`, bằng trình duyệt ở cả màn hình rộng và 375 px.

### UI1 — API sơ đồ và dải bước

- **Việc làm:**
  - `FreshMonitor.graph(run_id)` → `/api/graph?run=`: danh sách ô (id, cột, hàng, nhãn, trạng thái, giây,
    vào/ra, số lỗi, số lần thử lại, loại lỗi) và đường nối.
  - `/api/runs` thêm trường `strip`: trạng thái 7 cột cho mỗi lượt, cộng số sản phẩm và chênh lệch với lượt trước.
  - Không đổi UI trong CP này.
- **Test tự động:** dựng `run.json` giả cho các trường hợp:
  - lượt full đầy đủ có `normalise.source:*` → đủ ô, đường nối Vinpearl tới hai nguồn;
  - lượt cũ chỉ có `normalise` → một ô Chuẩn hoá chung;
  - lượt `index` → các ô cào mờ "Không thuộc lượt";
  - bước lỗi → ô mang `errorKind`, dải có cột đó ở trạng thái lỗi;
  - trạng thái xấu nhất của cột Cào khi một site bị chặn, các site khác xong;
  - `normalise.preview` lặp nhiều lần → không sinh ô, ô Gộp có đếm bản nháp.
- **Bạn kiểm:** mở `/api/graph?run=<một lượt trong local_crawl>` trên trình duyệt, đối chiếu với tab Luồng & nguồn cũ.
- **Xong khi:** mọi lượt trong `data/local_crawl/runs` trả sơ đồ không lỗi.

### UI2 — Sơ đồ và panel thay cho 9 tab

- **Việc làm:** vẽ sơ đồ (CSS grid cho ô, SVG cho đường nối); panel chi tiết theo bảng ở trên, dùng lại các hàm
  vẽ tab cũ với bộ lọc theo nguồn/bước; bỏ thanh 9 tab; cập nhật trực tiếp khi lượt đang chạy (giữ chu kỳ 3–5 giây như hiện nay).
- **Test tự động:** test hiện có của monitor vẫn pass; test API mà panel gọi với bộ lọc nguồn trả đúng dữ liệu nguồn đó.
- **Bạn kiểm:** mở một lượt full: thấy sơ đồ; bấm từng loại ô, mỗi panel có đúng nội dung của tab cũ tương ứng;
  xem ở 375 px.
- **Xong khi:** mọi thứ xem được ở 9 tab cũ đều tới được từ một ô của sơ đồ.

### UI2b — Bước con bên trong Chuẩn hoá và Gộp (thêm 2026-09-28)

- **Vì sao:** người yêu cầu thấy ô Gộp "Chờ tới lượt · nháp 4" trong khi gộp nháp đã chạy 4 lần (lần cuối 0,4 s, 59 dòng)
  nên tưởng Gộp đang nghẽn; và muốn thấy bên trong Chuẩn hoá, Gộp làm những gì. Số liệu bước con đã có từ CP1
  (`steps.json` của `normalise.StepClock`) nhưng chưa lên sơ đồ.
- **Việc làm:**
  - `/api/substeps?run=&node=&variant=`: bước con của ô, mỗi bước có nhãn, **một câu mô tả việc nó làm**, trạng thái,
    giây, dòng vào → ra, RAM, lỗi. Nguồn số liệu:
    - chuẩn hoá theo nguồn, tiến trình con: `normalised/steps/<nguồn>/steps.json`;
    - chuẩn hoá theo nguồn, chạy liên tục: meta checkpoint ghi thêm thời gian bước con của lô cuối và lịch sử các lô;
    - Gộp: bản chính thức `normalise_stages/steps.json`; bản nháp mới nhất `preview/normalise_stages/steps.json`
      (bản nháp cũ hơn chỉ còn dòng tóm tắt trong `run.json`, vì thư mục nháp được thay mỗi lần).
  - Ô Gộp khi chưa có bản chính thức nhưng đã có bản nháp: trạng thái "Đang gộp nháp", kèm lần, số dòng, nhóm site đã gồm.
  - Ô đang chạy hiện bước con hiện tại ("đang: gộp trùng khách sạn").
  - Panel: tab "Các bước bên trong" đứng đầu cho ô chuẩn hoá và ô Gộp; Gộp có nút chọn bản nháp / bản chính thức và bảng
    mọi lần gộp nháp; chạy liên tục có bảng các lô.
  - Mô tả bước con do agent viết từ code `normalise.py`; người yêu cầu đọc lại.
- **Test tự động:** `/api/substeps` cho tiến trình con, chạy liên tục, nháp, chính thức; ô Gộp "Đang gộp nháp" khi lượt
  chạy và chưa có bản chính thức; bước con đang chạy hiện trên ô.
- **Bạn kiểm:** mở lượt có gộp nháp, bấm ô Gộp → thấy 9 bước con có mô tả; chuyển bản nháp / chính thức.

### UI3 — Dải lỗi, chọn sẵn ô, đường dẫn

- **Việc làm:** dải lỗi ở đầu lượt (bước, nguồn, loại lỗi, thông báo; bấm để nhảy tới ô); tự chọn ô theo quy tắc
  ở trên; tô đỏ đường tới ô lỗi; `location.hash` giữ lượt, ô và phần panel.
- **Test tự động:** hàm chọn ô mặc định (đặt ở server trong `graph()`, trường `focus`) cho lượt lỗi, đang chạy, xong.
- **Bạn kiểm:** mở lượt `full-20260928T024657Z-14811` (lỗi ở `trip-flights`): ô đó được chọn sẵn; tải lại trang
  vẫn ở đúng ô; chép link sang tab khác mở đúng chỗ.
- **Xong khi:** mở một lượt lỗi thì thấy ngay lỗi ở đâu mà không phải bấm gì.

### UI4 — Lịch sử có dải bước

- **Việc làm:** trang Lịch sử theo thiết kế ở trên, dùng `strip` của UI1; lọc theo chế độ và trạng thái.
- **Test tự động:** `strip` của nhiều lượt liên tiếp tính đúng chênh lệch số sản phẩm theo cùng chế độ.
- **Bạn kiểm:** nhìn trang Lịch sử và chỉ ra được lượt bất thường mà không mở lượt nào.
- **Xong khi:** so được các lượt trên một màn hình.

### UI5 — Tổng quan gọn, trang Hệ thống

- **Việc làm:** thanh trên mới, nút điều khiển lên thanh trên, Tổng quan 3 phần, trang Hệ thống.
  Chỉ chuyển chỗ, không bỏ thông tin nào đang có.
- **Test tự động:** test API tổng quan và điều khiển lượt hiện có vẫn pass (không đổi API).
- **Bạn kiểm:** mọi thông tin của Tổng quan cũ còn tìm thấy được ở Tổng quan mới hoặc Hệ thống; bấm chạy/dừng lượt
  từ thanh trên.
- **Xong khi:** Tổng quan vừa một màn hình.

## Rủi ro

- Job đổi hoặc thêm tên bước (CP6–CP8) làm sơ đồ thiếu ô: quy tắc ghép nằm một chỗ; bước không nhận ra thì hiện
  ở ô "Bước khác" thay vì bị ẩn.
- Panel dùng lại hàm vẽ tab cũ có thể mang theo phần rối của tab cũ; chấp nhận ở UI2, dọn dần khi kiểm tay.
- File `index.html` đang ~320 dòng và sẽ dài thêm. Nếu vượt khoảng 600 dòng thì tách JS ra file riêng
  trong `monitor_ui/`; khi đó `monitor.py` phải phục vụ thêm file tĩnh (hiện chỉ trả `/` và `/index.html`).
- Monitor cần khởi động lại sau mỗi CP có đổi API.
