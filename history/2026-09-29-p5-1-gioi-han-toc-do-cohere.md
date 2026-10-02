# P5.1: giới hạn tốc độ dùng chung cho các lần gọi Cohere

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

P5.1 của `docs/plan/2026-09-29-index-cohere-song-song.md`. Người yêu cầu chốt theo đề xuất ("chốt theo đề xuất, làm P5
đi", 2026-09-29): mặc định 4 lô cùng lúc, 90 lượt gọi mỗi phút (key Trial 100 lượt/phút); không ghi biến mới vào PRD; đo
bằng Cohere giả + một lần thật trên sandbox. Phục vụ FR-SRC-02.

## File thay đổi

- `src/backend/app/infrastructure/embeddings/cohere_embedder.py` — sửa:
  - thêm `CallLimiter`: tối đa N lượt gọi trong mọi cửa sổ 60 s trượt (0 = không giới hạn); `pause()` làm mọi luồng
    cùng chờ; đếm `calls`, `rate_limited`; đồng hồ / hàm chờ tiêm được;
  - `CohereEmbedder(..., limiter=None)`: có limiter thì mỗi lần gọi `acquire()`, và 429 / 5xx gọi `limiter.pause()`
    thay vì `time.sleep` riêng. Không có limiter thì y như trước.
- `src/backend/tests/unit/infrastructure/test_cohere_embedder.py` — sửa: 5 test mới:
  - cửa sổ trượt 3 lượt / phút;
  - 0 = không giới hạn;
  - 429 + `Retry-After` làm mọi người gọi cùng chờ;
  - không limiter thì backoff như cũ;
  - 4 luồng thật dùng chung limiter không vượt trần.
- `history/2026-09-29-p5-1-gioi-han-toc-do-cohere.md` — thêm: entry này.

## Quyết định

- Limiter là opt-in ở adapter hạ tầng, không vào `domain` / `application` hay port `EmbedderPort`. Search lúc chạy API
  không truyền limiter nên không đổi.

## Kiểm tra

- `pytest src/backend/tests/unit/infrastructure/test_cohere_embedder.py`: 7 passed.
- Kiểm test bắt được lỗi: bỏ `limiter.acquire()` trong `_request` → test 429 fail; đã khôi phục.
- Toàn bộ test backend: xem entry P5.2.
- Môi trường: env `vsf` là Python 3.10, không chạy được test backend (`StrEnum`). Đã tạo venv Python 3.11 từ `vsf2` +
  `pip install -r src/backend/requirements.txt` trong scratchpad của phiên (ngoài repo). Mốc trước khi sửa:
  **531 passed, 19 skipped**.

## Còn lại / rủi ro

- Người yêu cầu hỏi chuyển hết sang `vsf2`: chờ đồng ý cài dependency vào `vsf2`.
- Chưa commit.
