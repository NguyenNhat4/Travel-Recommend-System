# Gợi ý: gọi song song các lượt Weaviate độc lập (output y hệt)

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành (đo latency trên cloud chưa làm, xem "Còn lại")
- Phạm vi: backend, docs
- Liên quan: `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` (giai đoạn 2, bước 2)

## Mục tiêu

Mỗi request gợi ý cá nhân hoá gọi Weaviate Cloud (eu-central-1) 3–5 lượt nối tiếp từ VM ở asia-southeast1:

- `vectors()` cho lịch sử;
- `near_vector` ngắn hạn, rồi dài hạn khi có chuyến mở;
- `vectors()` cho món phổ biến;
- `near_vector` của ô khám phá.

Hai lượt ANN và lượt lấy vector món phổ biến không phụ thuộc nhau. Chạy chúng song song thì thời gian của bước "ứng viên" còn bằng lượt chậm nhất thay vì tổng ba lượt. Phục vụ NFR-PERF-01; người dùng đã loại phương án đưa Weaviate về cùng vùng.

## File thay đổi

- `src/backend/app/application/recommendation/use_cases.py` — sửa:
  - helper `_timed` và `_Pending`: có executor thì `submit(copy_context().run, …)`, không có thì hoãn tới `result()` để chạy tuần tự đúng thứ tự cũ;
  - field `RecommendForUser.executor` (mặc định `None`);
  - trong `_rank`: tính món phổ biến trước ANN; gửi đồng thời ANN ngắn hạn, ANN dài hạn và vector món phổ biến; ghép kết quả đúng thứ tự cũ; ghi `annShort`, `annLong`, `popularVectors` vào `stageMs`.
- `src/backend/app/application/search/use_cases.py` — sửa: `StageTimer.record(name, seconds)` (không dời mốc `lap`).
- `src/backend/app/core/config.py` — sửa: `recommend_io_workers` (mặc định 16, 0–64; 0 = tuần tự).
- `src/backend/app/main.py` — sửa:
  - `build_recsys(..., recommend_executor=None)` truyền vào engine;
  - lifespan dựng pool `recsys-io` một lần cho mỗi tiến trình và đưa vào `RecsysRefresher` qua `functools.partial`, nên pool được dùng lại qua các lần nạp lại.
- `.env.example` — sửa: dòng chú thích `RECOMMEND_IO_WORKERS`.
- `docs/spec/logging-schema.md` — sửa: tên các bước đo riêng của từng lượt kho vector.
- `src/backend/tests/unit/application/test_recommendation_parallel.py` — thêm:
  - 7 ca (chuyến mở có ô khám phá, khoá điểm đến, chuyến đã xong, khách đọc từ CDP, dormant, cold-start, khách vãng lai): có pool cho output y hệt chạy tuần tự, cùng số lượt gọi;
  - có thời gian từng lượt;
  - lỗi ở lượt ANN thứ hai được ném ra ở cả hai chế độ.
- `src/backend/tests/unit/api/test_recommend_settings_wiring.py` — thêm: mặc định 16 và 0 hợp lệ; pool được nối tới engine.
- `history/2026-10-12-recsys-goi-song-song-weaviate.md` — thêm: entry này.

## Quyết định

- **Ghép đúng thứ tự cũ.** Song song chỉ đổi lúc các lời gọi chạy, không đổi thứ tự áp kết quả vào `_LocalSpace` và danh sách ứng viên, nên cách phá hoà giữ nguyên.
- **Lấy vector món phổ biến sớm.** Khi chạy song song, lượt này lấy cho mọi món phổ biến chưa có trong lịch sử (tập lớn hơn lượt tuần tự). Vòng ghép kiểm `g in space.local` trước, nên món ANN đã thêm vẫn dùng vector của ANN.
- **Ô khám phá vẫn tuần tự sau MMR,** vì số ô còn trống chỉ biết sau MMR. Số lượt gọi trong `test_recommendation_explore_fill.py` không đổi.
- **Harness bench không bị ảnh hưởng:** không có executor thì chạy tuần tự, và các hàm domain vẫn được gọi qua tên toàn cục của module.
- **Pool riêng mỗi tiến trình,** không dùng chung pool 40 thread của trợ lý.
- **Bản sao context mỗi lời gọi:** một `Context` không vào được hai thread cùng lúc; bản sao giữ request ID trong log của adapter. Thời gian từng lượt gom ở thread của request.

## Kiểm tra

- `pytest -q -p no:cacheprovider src/backend/tests src/evaluation/recsys_bench/tests`: 3060 passed, 42 skipped.
- In nhánh từng ca của test song song (script trong scratchpad, không commit): cold-start, dormant, long_term, guest, cross_vertical có hoặc không có ô khám phá, và khoá điểm đến đều được phủ.

## Còn lại / rủi ro

- Parity HTTP 60/60 và `http-latency` trước/sau chưa chạy được (không có môi trường prodcopy trên máy). Số thật đọc từ `stage_ms` trên staging sau khi deploy.
- Mỗi lần trượt cache, Weaviate Cloud nhận 2–3 lời gọi đồng thời thay vì nối tiếp. Rollback không cần redeploy bằng `RECOMMEND_IO_WORKERS=0`.
