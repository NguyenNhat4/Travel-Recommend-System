# L1: chuẩn hoá từng phần trong lúc đang cào

- Ngày: 2026-09-28
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

L1 của `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md`: bản ghi cào được thì chuẩn hoá ngay (theo lô vài giây một lần),
không đợi cả nguồn hay cả nhóm site cào xong. Người yêu cầu duyệt plan và chốt 4 mục "Cần chốt" theo đề xuất ngày 2026-09-28.

## File thay đổi

- `src/data_collection/normalise_stream.py` — thêm:
  - `SourceFollower`: đọc phần mới của một file interim, chỉ lấy dòng đã có `\n`; file bị ghi lại thì đọc lại từ đầu;
    bỏ trùng trên mọi bản ghi đã đọc; chỉ ánh xạ bản ghi chưa gặp (nhớ theo hash nội dung); ghi checkpoint `status: streaming`;
  - `StreamNormaliser`: luồng chạy mọi nguồn mỗi chu kỳ; `finish_source` chốt nguồn (`ok`/`failed`) rồi trả bộ nhớ.
- `src/data_collection/normalise.py` — sửa (refactor, không đổi hành vi):
  - tách `build_parser()` khỏi `main()`;
  - tách `dedupe_source(stem, records)` khỏi `read_source()`.
- `src/data_collection/fresh_catalog.py` — sửa, trong `Previewer`:
  - bật `stream.enabled` thì khởi động `StreamNormaliser` lúc bắt đầu cào;
  - khi site xong, `_finish_stream` chốt nguồn trong tiến trình (thay tiến trình con `--only-source`);
  - `finish()` dừng luồng.
- `src/data_collection/fresh_settings.py` — sửa: thêm `stream.enabled` (mặc định tắt) và `stream.normaliseSeconds` (mặc định 15).
- `src/data_collection/monitor.py` — sửa:
  - checkpoint `streaming` hiện "Đang chạy" trên sơ đồ, hoặc "Đã dừng" khi lượt không còn chạy;
  - `checkpoints()` trả thêm `batches`.
- `src/data_collection/monitor_ui/index.html` — sửa: bảng checkpoint hiện `streaming` là "Đang chạy" kèm số lô.
- `src/data_collection/tests/test_normalise_stream.py` — thêm: 9 test.
- `src/data_collection/tests/test_monitor_graph.py` — sửa: thêm 1 test cho checkpoint `streaming`.
- `docs/plan/2026-09-28-pipeline-chay-lien-tuc.md` — sửa: ghi mục đã chốt, thêm nút chỉnh sống vào L6, cập nhật tiến độ.

## Quyết định

- Kết quả giống bản theo lô nhờ ba điều:
  - dùng đúng `dedupe_source` và `map_source` của bản theo lô, trên toàn bộ bản ghi đã đọc, cùng thứ tự;
  - chỉ bỏ qua việc **ánh xạ lại** bản ghi đã gặp; mỗi bản ghi được ánh xạ trên bản sao, như khi chạy một lần;
  - fingerprint lấy từ `fstat` của đúng lần đọc: file dài thêm sau đó thì bước chính thức tự ánh xạ lại.
- Chạy trong tiến trình job (luồng `normalise-stream`), không phải tiến trình con. Lý do: phải giữ bản ghi và kết quả ánh xạ
  giữa các lô.
- Lỗi của một nguồn ở luồng này chỉ ghi log `normalise.stream.failed`, không chặn nguồn khác, không hỏng lượt:
  bước normalize chính thức ánh xạ lại nguồn nào không có checkpoint `ok` còn mới (như CP5).
- `stream.enabled` mặc định tắt cho tới L6, như plan. Cần bật cả "Chuẩn hoá từng nguồn ngay khi site cào xong".
- Nguồn chỉ ghi interim ở cuối (Vinpearl, Vinpearl combo, agoda API, giá phòng Trip) chưa được lợi; Vinpearl làm ở L2.

## Kiểm tra

- `pytest tests/test_normalise_stream.py` (env `vsf`): **9 passed**, gồm:
  - interim của cả 7 nguồn mẫu nối 3 khúc → checkpoint (mục, lỗi, meta) giống hệt `--only-source`;
  - bước chính thức dùng lại 7/7 checkpoint, `products.jsonl` = `expected_products.jsonl`;
  - dòng ghi dở; file ghi lại (inode mới) không ánh xạ lại; lỗi bản ghi cộng dồn qua các lô; một nguồn lỗi không chặn nguồn khác;
  - `Previewer` bật chạy liên tục → checkpoint `ok`, bước chính thức dùng lại hết, output = bản chạy thẳng.
- `pytest tests` (env `vsf`): **410 passed, 3 skipped**. `git diff --check`: sạch.
- **So `sha256` trên interim thật 49 MB** (bản sao từ scratchpad phiên CP5, 7 nguồn), `--today 2026-09-28`:
  - nối mỗi file theo 5 khúc, chuẩn hoá sau mỗi khúc, chốt, rồi chạy bản chính thức `--reuse-checkpoints`;
  - `products.jsonl` `993b6d68661de8ec…` **trùng** bản theo lô; dùng lại 7/7 checkpoint.
- Số đo:
  - mỗi chu kỳ trên cả 7 nguồn (mỗi khúc ~10 MB mới) 1,7–2,4 s; chu kỳ không có gì mới ~0 s; lần chốt 0,8 s;
  - bước chính thức 8,4 s, so với 15,4 s khi chạy theo lô;
  - RAM của phần chạy liên tục khi giữ cả 7 nguồn ~400 MB (449 MB đỉnh, 47 MB sau import); đã thêm trả bộ nhớ khi chốt nguồn.
- **Chưa** chạy trong một lượt cào thật.

## Còn lại / rủi ro

- Mỗi chu kỳ ghi lại cả checkpoint của nguồn có dữ liệu mới (agoda ~26 MB interim). Trên VM 2 CPU có thể cần chu kỳ dài hơn 15 s;
  tối ưu (chỉ ghi phần thêm) để sau nếu số đo trên VM cần.
- Chưa có ô "đang chạy liên tục" riêng trên sơ đồ: ô chuẩn hoá theo nguồn hiện "Đang chạy" nhờ meta `streaming` (đầy đủ ở L6).
- L2–L6 chưa làm. Chưa commit.
