# P1: chuẩn hoá ngay khi một bước cào xong, không đợi cả nhóm site

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

P1 của `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md`. Phục vụ FR-CAT-01..04. Output không đổi.

Trước đây chuẩn hoá theo nguồn (CP5) chỉ chạy khi **cả nhóm site** xong. Ví dụ ở lượt `full-20260928T073959Z-221577`:
vé máy bay Trip cào xong lúc 07:40:25 nhưng tới 07:42:14 mới được chuẩn hoá, vì phải đợi điểm tham quan.

Người yêu cầu duyệt plan và chốt 5 mục "Cần chốt" theo đề xuất (2026-09-29), rồi yêu cầu làm P1 và "test đầy đủ".

## File thay đổi

- `src/data_collection/fresh_catalog.py` — sửa:
  - thêm `STEP_INTERIM`: bước cào → file interim nó ghi. Bước chạy trong tiến trình khai báo qua thuộc tính `interim`
    (`price_rooms.interim = ('trip_hotels',)`);
  - `crawl_sites`: thêm `step_finished`, gọi sau khi một bước xong hẳn (ok, bị chặn, hoặc thành công sau khi thử lại).
    Bước lỗi hoặc bước bị bỏ không gọi;
  - `Previewer.source_done` và `_submit` (dùng chung với `group_done`): mỗi file chỉ giao chuẩn hoá một lần
    (`self.submitted`); chỉ giao file có trên đĩa;
  - `group_done` chỉ giao phần file còn lại của nhóm: file của bước lỗi, hoặc file không khai báo trong `STEP_INTERIM`.
    Nhóm không có file nào vẫn gộp nháp như cũ;
  - "không gộp nháp ở bước cuối của lượt" chuyển từ mức nhóm xuống mức bước: bước cuối của nhóm, khi mọi nhóm khác đã
    xong và lượt không lỗi;
  - docstring và comment ("site xong" → "bước cào xong").
- `src/data_collection/fresh_settings.py` — sửa: nhãn và giải thích của `normalise.preview` và `stream.enabled`
  ("ngay khi nguồn cào xong"). Khoá và mặc định không đổi.
- `src/data_collection/monitor_ui/index.html` — sửa: hai câu mô tả chuẩn hoá theo nguồn ("ngay khi bước cào của nó xong").
- `src/data_collection/README.md` — sửa: mục "Chuẩn hoá theo nguồn và bản nháp".
- `src/data_collection/tests/test_live_monitor.py` — sửa:
  - `PreviewTriggerTests.Recorder` ghi thêm `source_done` và thứ tự sự kiện; `run_sites` nhận nhóm, mã thoát dạng hàm,
    bỏ chờ khi thử lại;
  - hai test cũ kiểm thêm các lần gọi `source_done`;
  - 6 test mới cho `crawl_sites`:
    - nguồn được chuẩn hoá trong lúc bước sau cùng nhóm còn cào;
    - chỉ bước cuối của nhóm xong sau cùng bỏ gộp nháp;
    - bước bị chặn được chuẩn hoá đúng một lần, ngay sau khi dừng;
    - bước thử lại chỉ chuẩn hoá sau lần thử cuối;
    - bước lỗi và các bước sau nó để `group_done` xử lý;
    - bước trong tiến trình khai báo `interim`; bước bị bỏ không được chuẩn hoá;
  - 5 test mới cho `Previewer` thật:
    - `source_done` tạo checkpoint thật ngay; giao lại hoặc file không có thì bỏ qua; `group_done` chỉ lấy phần còn lại
      và không gộp thêm;
    - nhóm không có file vẫn gộp nháp;
    - `group_done` không gộp lại khi các nguồn của nó đã gộp;
    - `source_done` sau khi đóng bị bỏ qua;
    - chạy liên tục chốt nguồn (`finish_source`) ngay khi bước xong.
- `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` — sửa: "Cần chốt" → "Đã chốt"; dòng tiến độ.
- `history/2026-09-29-p1-chuan-hoa-theo-buoc-cao.md` — thêm: entry này.

## Quyết định

- Giữ `group_done` làm lưới an toàn thay vì bỏ hẳn. Bước lỗi, nhóm bị dừng giữa chừng, và file interim chưa khai báo vẫn
  được chuẩn hoá đúng như cách cũ.
- Bước lỗi không gọi `source_done`. File của nó chuẩn hoá ở `group_done`, cùng thời điểm như trước, để lỗi hiện đúng chỗ.
- Tên bước `normalise.source:<file>` và `group` trong `run.json` không đổi, nên monitor không phải sửa.
- Không tách nhóm Trip thành các luồng song song (plan, mục Hiện trạng).

## Kiểm tra

- `pytest tests` (env `vsf`, từ `src/data_collection`, `PYTHONPATH=<repo>/src`): **479 passed, 5 skipped**.
  5 skip giống trước: 2 test Postgres cần `STREAM_TEST_ADMIN_URL`, 3 skip có từ trước.
- **Kiểm test bắt được lỗi:** tạm thay 2 lời gọi `step_finished` bằng `pass` (tức quay về chuẩn hoá theo nhóm) →
  8/8 test `crawl_sites` liên quan fail; đã khôi phục code.
- **So `sha256` của `products.jsonl`**, cùng ngày, theo ba cách:
  (a) chuẩn hoá cả khối, không checkpoint; (b) theo nhóm (`group_done`, cách cũ); (c) theo bước (`source_done`, P1)
  rồi `normalize` chính thức. Script ở scratchpad phiên này.
  - `local_crawl_demo/runs/full-20260925T091848Z-201309` (6 nguồn, ~2,8 MB): cả ba `50f3b50bd60d23a8…`, 631 dòng.
  - `local_crawl/runs/full-20260928T073959Z-221577` (4 nguồn): cả ba `cbc6d8fdc05bb357…`, 58 dòng.
  - Bước chính thức ở (c) dùng lại 6/6 checkpoint (`normalise.source.reuse`).
  - Bộ interim 49 MB của CP5/L1 không còn (nằm trong scratchpad phiên cũ), nên chưa so trên bộ lớn.
- **Lượt mô phỏng `run_job('full')`**: `Previewer` và `normalize` thật; cào giả chép interim thật kèm thời gian chờ;
  maintain, validate, DB, index giả lập. Trong `run.json`:
  - `normalise.source:trip_flights` chạy ở giây 0, trong lúc `trip-attractions` cào từ giây 0 tới 4;
  - nguồn cuối (vinpearl, giây 6) không tạo bản gộp nháp;
  - lượt `ok`.
- `git diff --check`: sạch.
- Chưa mở monitor trong trình duyệt; phần UI chỉ đổi câu chữ.

## Còn lại / rủi ro

- Người yêu cầu kiểm tay trên lượt thật (mục "Bạn kiểm" của P1).
- Gộp nháp chạy thường hơn (sau mỗi bước thay vì mỗi nhóm). Có gom yêu cầu dồn và công tắc `normalise.preview`.
- **Lỗi có sẵn, phát hiện khi mô phỏng, chưa sửa (ngoài P1):** `run_group` chỉ bắt `Exception`. Một bước trong tiến trình
  ném `SystemExit` thì luồng của nhóm chết lặng lẽ:
  - ví dụ: `trip-hotels.discover` ném "Không có màn hình để mở trình duyệt";
  - nhóm vẫn được ghi `ok`, các bước sau trong nhóm (vé máy bay, điểm tham quan) không chạy;
  - lượt kết thúc mã 0.
- Chưa commit.
