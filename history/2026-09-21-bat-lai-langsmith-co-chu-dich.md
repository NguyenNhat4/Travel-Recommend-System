# Bật lại LangSmith tracing có chủ đích

- Ngày: 2026-09-21
- Tác giả: Nguyễn Minh Nhật / Claude Sonnet 5
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: backend

## Mục tiêu

Sau khi nối LLM vào composition root (`history/2026-09-21-noi-llm-vao-composition-root.md`),
LangSmith ngừng nhận trace. Nguyên nhân: LangSmith SDK tự đọc `LANGSMITH_*` thẳng từ `os.environ`;
trước đây các biến này lọt vào `os.environ` là nhờ `_load_local_env()` cũ trong `agents/llm.py` đẩy
**toàn bộ** `.env` vào `os.environ` lúc import — tác dụng phụ không ai chủ ý, đây chính là lỗi #1
từng nêu trong lần đánh giá code. Xoá `_load_local_env()` vô tình tắt luôn tracing.

Người dùng xác nhận muốn bật lại tracing, nhưng phải là hành động tường minh, không lặp lại tác
dụng phụ đọc-cả-`.env` như trước.

## File thay đổi

- `src/backend/app/core/config.py` — sửa: thêm 4 field `langsmith_tracing` (mặc định `False`),
  `langsmith_api_key`, `langsmith_endpoint`, `langsmith_project`.
- `src/backend/app/main.py` — sửa: thêm `_forward_langsmith_env(settings)`, gọi đầu `lifespan`;
  chỉ đẩy đúng 4 biến `LANGSMITH_*` vào `os.environ`, chỉ khi `langsmith_tracing=True` **và** có
  `langsmith_api_key`; log rõ khi bật hoặc khi thiếu key.
- `.env.example` — sửa: thêm block `LANGSMITH_*` với default tắt (`LANGSMITH_TRACING=false`) và
  ghi chú đây là tuỳ chọn dev, dữ liệu người dùng sẽ được gửi ra ngoài khi bật.
- `src/backend/tests/unit/test_backend_wiring.py` — sửa: thêm `LangSmithForwardingTests` (3 test:
  tắt → không đẩy; bật thiếu key → không đẩy; bật đủ key → đúng 4 biến được đẩy).

## Quyết định

- **Cấu hình qua `Settings`, forward thủ công chỉ 4 biến ở composition root** — không khôi phục lại
  kiểu `os.environ.setdefault()` cho toàn bộ `.env`. LangSmith SDK không có cách nhận config qua
  tham số nên bắt buộc phải đụng `os.environ`, nhưng phạm vi giới hạn đúng 4 key cần thiết và chỉ
  chạy khi được bật tường minh — giữ đúng tinh thần ARCHITECTURE.md §5 (chỉ composition root nối
  side effect ra ngoài) mà không lặp lại lỗi cũ.
- **Mặc định tắt** (`langsmith_tracing: bool = False`): `.env.example` nay đặt `false`; `.env` cá
  nhân của người dùng đã có `LANGSMITH_TRACING=true` từ trước nên bật ngay không cần đổi gì thêm.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` → PASS
  (không đổi contract).
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q src/backend/tests` → **140 passed, 2 skipped**
  (trước: 137 passed; thêm 3 test LangSmith).
- Chạy thật `uvicorn src.backend.app.main:app` với `.env` hiện có: log in ra
  `LangSmith tracing: on (project=Travel-agent)` lúc khởi động.

## Còn lại / rủi ro

- Chưa xác nhận lại bằng mắt trên dashboard LangSmith rằng trace mới thực sự tới nơi (chỉ xác minh
  4 biến env được set đúng lúc khởi động qua log và unit test); nếu dashboard vẫn trống, kiểm tra
  API key còn hiệu lực.
- Lỗi #3 từ lần đánh giá trước (store hội thoại phình không giới hạn) vẫn chưa sửa.
