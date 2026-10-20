# Monitor: ô "Gộp catalog" hiện log "Catalog đang gộp"

- Ngày: 2026-10-09
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: test/newcrawl (chưa commit)
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Trên monitor VM mới (lượt `full-20261009T051518Z-23`), bấm ô "Gộp catalog" rồi mở tab Log thì gần như không có gì: bước Gộp
chính thức chưa chạy (`notRun`, chỉ có bản nháp 6.944 dòng), bộ lọc `name=normalise` chỉ bắt dòng start/done của bước khác
(`normalise.source:…`, `normalise.preview`). Yêu cầu: ô Gộp hiện log "Catalog đang gộp".

## File thay đổi

- `src/data_collection/monitor_ui/index.html` — sửa: `stepLine` cho ô Gộp (không chọn ô con) lấy mọi dòng nhóm `[preview]`
  và `catalog.preview.*`; lọc `name=<bước>` khớp đúng tên bước (ranh giới khoảng trắng / `:` / hết dòng) để không lẫn
  `normalise.source:…`; start/done của `normalise.preview` thuộc ô Gộp; thêm `reEsc`. Lần 2 (cùng ngày): `trackMerge` lấy
  mọi dòng không tiền tố giữa `catalog.step.start name=normalise` và mốc `catalog.step.*` / `run.end` kế tiếp — log của
  bước Gộp chính thức (chạy trong tiến trình job, không có tiền tố) trước đó chỉ hiện các dòng `normalise.step.*`.
- `src/data_collection/README.md` — sửa: đoạn "Bước con chưa chạy và log theo bước" ghi thêm hành vi trên.

## Quyết định

- Chỉ đổi bộ lọc phía giao diện; không đổi cách job ghi log. Dòng chuẩn hoá theo nguồn (`[normalise:<nguồn>]`) vẫn thuộc ô
  của nguồn đó. Ô con của Gộp vẫn chỉ lọc dòng của đúng bước con.
- Theo monitor sẵn có, không lệch PRD (FR-CDP/vận hành job cào, không đổi hành vi sản phẩm).

## Kiểm tra

- Bộ lọc chạy trên log thật của lượt `full-20261009T051518Z-23` (814 dòng): ô Gộp 118 dòng (113 dòng `[preview]`), 0 dòng
  `name=normalise.source|preview` lọt vào; ô con "đọc checkpoint" 10 dòng; `maintain` 8 dòng.
- Monitor local (worktree này, bản sao `run.json` + `job.log` của lượt trên): ô Gộp → tab Log hiện "118 / 814 dòng", chip
  "Đang lọc theo bước: Gộp catalog", có các dòng `[preview] … Đã ghi 6944 sản phẩm`, WARNING, `catalog.preview.done`;
  console không lỗi.
- Lần 2: lượt local `full-20261008T082044Z-380938` (có bước Gộp chính thức): khối Gộp 44/44 dòng hiện trong ô Gộp
  ("Đọc agoda_api.jsonl", "Khách sạn: 6 → 6", "Đã ghi 22 sản phẩm", WARNING, substep), dòng `validate` kế tiếp không lọt
  vào; ô Gộp 70/197 dòng. Lượt VM 12:15: 128/814 dòng (thêm start/done `normalise.preview`). 0 dòng tiền tố site lọt vào.
- `node --check` script của `index.html`: OK.
- `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q data_collection/tests` (env vsf2, từ `src/`): 646 passed, 27 skipped.

## Còn lại / rủi ro

- Cùng worktree còn thay đổi monitor chưa commit của phiên trước (bước con chưa chạy, `pipeline_graph.SUBSTEPS`, lọc log theo
  bước, tab DB tự làm mới — các file `monitor.py`, `pipeline_graph.py`, `stage_log.py`, tests) chưa có entry `history/` riêng.
- Chưa commit / deploy; VM chỉ có hành vi mới sau khi merge và Crawler CI/CD deploy.
