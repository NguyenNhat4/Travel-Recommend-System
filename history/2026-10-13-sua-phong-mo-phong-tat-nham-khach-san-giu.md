# Sửa phòng mô phỏng tắt nhầm khách sạn giữ lại sau khi gộp

- Ngày: 2026-10-13
- Tác giả: Phạm Nguyễn Đăng Khôi / Claude (agent)
- Nhánh: test/newcrawl (worktree `~/code/Travel-Recommendation-Product-newcrawl`)
- Trạng thái: hoàn thành
- Phạm vi: data

## Mục tiêu

Người dùng (13/10): "sửa luôn test cũ" — `test_stream_feed_db.py::StreamLoadRealDbTests::test_rows_loaded_separately_then_merged_leave_one_visible`
lỗi cả trên `origin/release-mvp-v2` (xem `history/2026-10-13-kiem-lai-ra-soat-va-loai-tms-lee-xinh.md`). FR-CAT-02 (khách sạn
còn phòng đặt được thì hiển thị), `docs/prd/data-model.md` §3.1 (hạng phòng mô phỏng cho khách sạn chưa có phòng, chốt 09/10/2026).
Không lệch PRD: sửa code cho đúng điều PRD đã ghi.

## File thay đổi

- `src/data_collection/seed/simulated_rooms.py` — sửa: `plan` không tắt khách sạn cha của một phòng mô phỏng bị tắt nếu khách sạn đó vẫn
  có phòng mô phỏng của chính nó trong lượt (`keeps_room`).
- `src/data_collection/tests/test_simulated_rooms.py` — sửa: test gộp A vào B, phòng mô phỏng của A chuyển sang B rồi bị tắt, B vẫn bật.
- `src/data_collection/tests/test_stream_feed_db.py` — sửa: test gốc giữ nguyên assertion "dòng giữ vẫn hiển thị"; kiểm thêm phòng mô phỏng
  (của B bật, của A tắt); phần đếm dòng cuối chỉ đếm dòng thật (test viết 29/09, trước khi có `demo:room:*`).
- `history/2026-10-13-sua-phong-mo-phong-tat-nham-khach-san-giu.md` — thêm.

## Quyết định

- Ban đầu định sửa test bằng cách thêm hạng phòng thật cho khách sạn giữ — bỏ, vì sẽ che bug. Tái hiện bằng DB tạm cho thấy nguyên
  nhân: gộp `agoda:hotel:1` vào `booking:hotel:9` chuyển `demo:room:agoda:hotel:1` sang làm con của `booking:hotel:9`;
  `simulated_rooms.plan` tắt phòng đó (khách sạn gốc đã gộp) rồi tắt luôn "khách sạn cha" mà không xét `demo:room:booking:hotel:9`
  vẫn đang bán → khách sạn giữ bị `available = false`, `noBookableRoom` tới lượt nạp kế tiếp (lượt sau tự bật lại).
- Production 13/10 (đọc, read-only): 0 khách sạn đang tắt mà có phòng mô phỏng đang bán, 0 phòng mô phỏng treo dưới khách sạn khác →
  không cần sửa dữ liệu.

## Kiểm tra

- Trước khi sửa code: test mới trong `test_simulated_rooms.py` lỗi (khách sạn giữ nằm trong danh sách tắt).
- Sau khi sửa: `test_simulated_rooms.py`, `test_stream_feed_db.py`, `test_demo_data.py`: 10 passed (`STREAM_TEST_ADMIN_URL` = superuser local).
- Phá thử: bỏ điều kiện `keeps_room` → 2 test lỗi (test mới + test gốc); trả lại → qua.
- Cả suite, bật mọi test DB thật trên DB nháp trong container local (cách dựng ở
  `docs/plan/2026-10-13-ban-giao-ra-soat-du-lieu-production.md` §6; DB nháp đã xoá):
  `python -m pytest -q -p no:cacheprovider data_collection/tests` → **706 passed** (0 failed, 0 skipped).

## Còn lại / rủi ro

- Không có. Bản sửa chỉ lên production khi `test/newcrawl` được merge và CD crawler deploy.
