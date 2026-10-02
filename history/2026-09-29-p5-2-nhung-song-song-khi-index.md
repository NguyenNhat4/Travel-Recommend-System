# P5.2: nhúng song song trong job index

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

P5.2 của `docs/plan/2026-09-29-index-cohere-song-song.md`: các lô Cohere của job index chạy song song dưới giới hạn tốc độ
(P5.1). Kết quả Weaviate phải giống hệt tuần tự. Phục vụ FR-SRC-02.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: thêm `cohere_embed_concurrency` (mặc định 4, 1–16) và `cohere_calls_per_minute`
  (mặc định 90, 0 = không giới hạn); env `COHERE_EMBED_CONCURRENCY`, `COHERE_CALLS_PER_MINUTE`. Chỉ job index đọc.
- `src/backend/jobs/embed_products.py` — sửa:
  - `embed_batches()`:
    - tối đa `concurrency` lô gọi Cohere cùng lúc (`ThreadPoolExecutor`);
    - `write()` luôn chạy ở luồng gọi (chỉ một luồng ghi Weaviate), lô nào xong ghi trước;
    - lô lỗi hẳn: không gửi lô mới, ghi các lô đang chạy, rồi ném lỗi đầu tiên;
    - `concurrency = 1` là tuần tự như cũ;
  - `run()`:
    - dùng chung một `CallLimiter`;
    - báo cáo thêm `concurrency`, `cohereCalls`, `rateLimited`, `seconds` (hiện trong chi tiết bước index của monitor, không
      sửa monitor);
    - `force=True` / `--force` nhúng lại mọi search unit (lý do `force`) để đo.
- `src/backend/tests/unit/infrastructure/test_embed_products_job.py` — sửa:
  - 2 test cũ thêm hai trường cấu hình;
  - 6 test mới:
    - song song = tuần tự: 500 dòng, cùng object và vector;
    - không vượt `concurrency` và chỉ luồng gọi ghi Weaviate;
    - lô lỗi giữ lô đã xong, lần chạy lại chỉ nhúng phần thiếu;
    - Cohere giả trễ 0,3 s × 8 lô: song song nhanh gấp ≥ 2 lần;
    - `--force`;
    - HTTP thật qua server local nhiều luồng: một `httpx.Client` dùng chung cho 4 lô song song, vector đúng.
- `history/2026-09-29-p5-2-nhung-song-song-khi-index.md` — thêm: entry này.

## Quyết định

- Ghi Weaviate giữ ở một luồng (plan P5.2): client Weaviate dùng chung chưa kiểm là an toàn khi dùng từ nhiều luồng.
- Không đổi `EmbedderPort` / `domain` / `application`; job vẫn gọi adapter như trước. Test kiến trúc vẫn pass.
- `fresh_catalog.index_settings` dựng `Settings` từ env, nên job VM và index theo phần (L5) nhận hai biến mới mà không sửa
  `data_collection`.

## Kiểm tra

- Kiểm test bắt được lỗi, mỗi lần tắt một hành vi rồi khôi phục (`cmp` sạch):
  - bỏ song song (`if True:`) → 3 test fail (giới hạn / chỉ luồng gọi ghi, nhanh hơn, HTTP thật);
  - ghi Weaviate từ luồng phụ → test "chỉ luồng gọi ghi" fail.
- Toàn bộ test backend:
  - trên venv Python 3.11 tạm (từ `vsf2`, trong scratchpad): **542 passed, 19 skipped** (mốc trước P5: 531 passed,
    19 skipped; thêm 11 test);
  - trên **conda `vsf2`** sau khi cài đủ dependency (người yêu cầu đồng ý): **542 passed, 19 skipped**.
- `data_collection` (`pytest tests`): **508 passed, 5 skipped** trên cả `vsf` và `vsf2`.
- `git diff --check`: sạch.

## Còn lại / rủi ro

- Số đo thật: xem entry P5.3.
- Chưa commit.
