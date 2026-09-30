# P3: khai báo đồ thị bước ở một chỗ (`pipeline_graph.py`)

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

P3 của `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` (người yêu cầu: "làm P3 đi", 2026-09-29).

Trước đây quan hệ giữa các bước khai báo rải rác, thêm hoặc đổi một bước phải sửa đồng bộ nhiều chỗ:
- 7 hằng số trong `fresh_catalog.py`;
- 12 hằng số trong `monitor.py`, trong đó `RESUME_STEPS` chép tay từ `fresh_catalog.py`.

Tương đương "định nghĩa DAG tách khỏi executor" của Airflow, nhưng không dựng executor: job vẫn gọi bước theo thứ tự
trong code. Phục vụ FR-CAT-01..04. Không đổi hành vi.

## File thay đổi

- `src/data_collection/pipeline_graph.py` — thêm. Chỉ có dữ liệu và hàm suy ra, không import job hay monitor:
  - `SOURCES` (6 nguồn): làn, nhãn, công tắc, site, bước, nhãn bước, file interim, khoá chỉnh sống, chế độ, bước trong
    tiến trình hay `crawl.py`;
  - `SITE_ORDER`, `SITE_EXTRA_INTERIM`;
  - `STEPS` (maintain, normalise, validate, db, index): cột, nhãn ngắn/dài, `deps`, chế độ, tên dùng khi chạy lại;
  - `STREAMS` (4 việc chạy liên tục), `COLUMNS`, `NORMALISE_SOURCE`, `NORMALISE_ALL`;
  - bảng suy ra: `SITE_GROUPS`, `SITE_INTERIM`, `STEP_INTERIM`, `SOURCE_SWITCH`, `LIVE_KEYS`, `STEP_TITLES`,
    `STEP_LABELS`, `RESUME_STEPS`;
  - hàm: `deps_of`, `downstream`, `resume_plan`, `resume_options`.
- `src/data_collection/fresh_catalog.py` — sửa:
  - `SITE_GROUPS`, `SOURCE_SWITCH`, `LIVE_KEYS`, `GROUP_INTERIM`, `STEP_INTERIM`, `RESUME_STEPS`,
    `Previewer.STREAM_LABELS` lấy từ `pipeline_graph`;
  - nhãn của bước maintain, normalise, validate, db, index và khách sạn Trip lấy từ đồ thị;
  - `resume_run` dùng `resume_plan()` (bước chạy tiếp suy từ `deps`) thay vì so vị trí trong một tuple cứng;
  - bước trong tiến trình khai báo tên bước (`price_rooms.step = 'trip-hotels.prices'`) thay cho thuộc tính `interim`
    của P1; file interim tra từ `STEP_INTERIM`.
- `src/data_collection/monitor.py` — sửa:
  - `SOURCES`, `STEP_OWNER`, `GRAPH_COLUMNS`, `GRAPH_SINGLE`, `GRAPH_MODES`, `NORMALISE_SOURCE`, `STREAM_STEPS`,
    `STREAM_LIVE`, `NORMALISE_ALL`, `RESUME_STEPS`, `STEP_LABELS` suy từ `pipeline_graph` (giữ tên cũ trong monitor);
  - bỏ `RESUME_FROM`, dùng `graph.resume_options()`;
  - đường nối validate → db → index trên sơ đồ suy từ `deps`.
- `src/data_collection/tests/test_pipeline_graph.py` — thêm, 9 test:
  - đồ thị tự nhất quán: mọi dep có thật, không có vòng, bước khai báo sau dep;
  - nguồn đủ trường; khoá chỉnh sống khớp `live_control`;
  - chạy lại theo `deps`; `resume_options` bằng `RESUME_FROM` cũ;
  - bảng suy ra bằng giá trị cũ của job;
  - **thứ tự thật**: chạy `run_job('full')` và `run_job('daily')` giả, mọi bước trong `run.json` bắt đầu sau khi các
    dep của nó xong;
  - `resume_run` từ mỗi bước gọi đúng `resume_plan()`.
- `src/data_collection/tests/test_live_monitor.py` — sửa: test P1 dùng `prices.step` thay cho `prices.interim`.
- `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` — sửa: dòng tiến độ.
- `history/2026-09-29-p3-khai-bao-do-thi-buoc.md` — thêm: entry này.

## Quyết định

- Không làm executor chung (plan P3). `deps` là dữ liệu. Test thứ tự bắt khi code gọi bước lệch `deps`.
- Giữ tên hằng số cũ trong `fresh_catalog.py` và `monitor.py` (gán từ `pipeline_graph`), để code còn lại và test cũ
  không phải đổi.
- **Không gộp** vào đồ thị `FAMILIES`, `SOURCE_LABELS`, `STEP_SOURCE` của monitor. Đó là bảng hiển thị file interim,
  không phải quan hệ bước.
  - `FAMILIES['trip']` có `trip_experiences`, còn bảng file của job thì không. Gộp lại sẽ làm job chuẩn hoá thêm một file
    (đổi hành vi).
- `CRAWL` là dep giả nghĩa là "mọi bước cào của lượt". Bước chuẩn hoá theo nguồn không đợi bước nào khác (P1).
- Tên bước trong `run.json` giữ nguyên, để lượt cũ vẫn hiện đúng.

## Kiểm tra

- **Giá trị suy ra = hằng số cũ:** so từng bảng khi job và monitor chưa đọc từ module: không bảng nào khác.
- **So kết quả monitor trước/sau** trên 12 lượt thật:
  - bộ dữ liệu: 5 lượt `data/local_crawl` (full, daily, index; có và không có chạy liên tục; lượt bị dừng; lượt index lỗi)
    và 7 lượt `data/local_crawl_demo`;
  - chụp `runs`, `overview`, `live`, và theo từng lượt `graph`, `run`, `health`, `checkpoints`, `progress`, `substeps`
    (script ở scratchpad phiên này; chụp hai lần trước khi sửa để loại trường đổi theo giờ);
  - kết quả: **giống hệt**, trừ `hours` của SLA (tuổi catalog, tăng theo giờ thật) và `STEP_INTERIM` có thêm
    `trip-hotels.prices` (thay thuộc tính `interim` của P1, cùng hành vi).
- `pytest tests` (env `vsf`): **489 passed, 5 skipped** (thêm 9 test; 5 skip như trước).
- **Kiểm test bắt được lỗi:** tạm đảo `deps` (validate sau db) → 5 test fail (3 thứ tự thật, 1 khai báo, 1 chạy lại);
  đã khôi phục.
- `git diff --check`: sạch; file mới không có khoảng trắng cuối dòng.
- Chưa mở monitor trong trình duyệt. Kết quả API mà UI đọc đã so giống hệt ở trên.

## Còn lại / rủi ro

- Người yêu cầu kiểm tay (plan P3):
  - mở monitor, xem 3 lượt cũ: sơ đồ, nút chạy lại, nhãn không đổi;
  - `./local_crawl.sh run resume <lượt> db` chạy như trước.
- P4 (hạn giờ, cào lại một nguồn) sẽ thêm bước vào `pipeline_graph.py`.
- Chưa commit.
