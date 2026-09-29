# Chạy bộ golden dataset của Itinerary Agent

Phục vụ `docs/prd/test-plan.md` §2.4 và FR-AGT-01..05, NFR-REL-01, NFR-SEC-01 trong `docs/prd/requirements.md`.

Hướng dẫn chạy bộ đánh giá tự động 14 case (mỗi category một case). Cấu trúc case và cách thêm case: [golden-dataset.md](golden-dataset.md).
Luật chấm: [evaluation-plan.md](evaluation-plan.md) §0.

Mọi lệnh chạy từ thư mục gốc repo.

## 1. Test nhanh (không cần LLM, DB hay backend)

Kiểm dataset và code chấm điểm, mất khoảng 1 giây:

```bash
.venv/bin/python -m pytest src/evaluation/tests/test_golden.py -q
```

Chạy lệnh này mỗi khi sửa dataset hoặc `golden.py`.

## 2. Chạy bộ golden với LLM thật

### Bước 1: bật Postgres

```bash
docker compose up -d --wait postgres
```

Postgres phải đã seed catalog (10.320 sản phẩm).

### Bước 2: bật backend

Chạy ở một terminal riêng:

```bash
.venv/bin/uvicorn src.backend.app.main:app --port 8000
```

`.env` cần có:

| Biến | Giá trị |
|---|---|
| `ITINERARY_DATA_MODE` | `inprocess` (nên dùng) hoặc `http`; không để `fixture` |
| `ITINERARY_SERVICE_BASE_URL` | `http://127.0.0.1:8000`, chỉ cần khi `ITINERARY_DATA_MODE=http` |
| `DATABASE_URL` | đọc được `cdp.products` (runner dùng để đối chiếu sản phẩm) |
| Key LLM | `OPENAI_API_KEY`, `GEMINI_API_KEY` hoặc `ANTHROPIC_API_KEY` |

Runner dựng graph trong tiến trình của nó và luôn gọi Search/Recommendation/destinations của backend qua HTTP
(`ItineraryHttpClients` tới `--api-base-url`), nên biên bản ghi `dataMode: http` bất kể mode của backend. Mode của
backend chỉ quyết định `productCount` trong biên bản, vì runner đọc số này từ `/assistant/status`: `inprocess` trả số
sản phẩm trong index, `http` trả `null`, còn `fixture` trả 50 của bộ mẫu nên không dùng. Staging/production chạy
`ITINERARY_DATA_MODE=inprocess` (agent gọi engine trong cùng tiến trình, không qua HTTP); golden không đo đường đó.
Output của hai đường được đối chiếu bằng test parity trong `src/backend/tests`, không phải bằng golden.

Đợi log in ra `startup.recsys.index.load.ready`, thường mất 1–2 phút. Chạy runner trước lúc đó thì mọi case
đều ra sai. Kiểm tra backend đã sẵn sàng:

```bash
curl -s localhost:8000/api/v1/assistant/status
```

Response phải có `"status":"ready"`, `"llmMode":"live"` và `"dataMode"` là `"inprocess"` hoặc `"http"`.

### Bước 3: chạy runner

```bash
.venv/bin/python -m src.evaluation.agent.golden
```

Lệnh trên chạy 75 case (89 lượt), mất khoảng 6 phút.

| Cờ | Tác dụng | Ví dụ |
|---|---|---|
| `--sweep` | Thêm hai lượt (`"<điểm đến> 2 ngày"` rồi `"chưa chốt ngày đi"`) cho mọi điểm đến trong catalog (35 điểm, tổng 93 lượt; chưa đo thời gian) | `--sweep` |
| `--only` | Chỉ chạy các case liệt kê, cách nhau bằng dấu phẩy | `--only G-047,G-072` |
| `--repeat N` | Chạy lại các case đã chọn N lần, để đo độ ổn định | `--repeat 5` |
| `--trace-project` | Gửi trace từng lượt lên LangSmith project này (key lấy từ `.env`) | `--trace-project claude-golden` |
| `--api-base-url` | Địa chỉ backend, mặc định `http://127.0.0.1:8000` | |
| `--dataset` | File dataset khác | `--dataset path/to.yaml` |
| `--timeout` | Giới hạn giây cho mỗi lượt, mặc định 90 | |

Các cách chạy thường dùng:

```bash
# Trước demo hoặc trước khi commit: toàn bộ, kèm trace
.venv/bin/python -m src.evaluation.agent.golden --sweep --trace-project claude-golden

# Thử case vừa thêm
.venv/bin/python -m src.evaluation.agent.golden --only G-051 --repeat 3 --trace-project claude-golden

# Đo tỷ lệ fail của các case hay dao động
.venv/bin/python -m src.evaluation.agent.golden --only G-047,G-072 --repeat 5
```

Runner không tự gửi trace. Không có `--trace-project` thì LangSmith không ghi lượt nào.

## 3. Đọc kết quả

Terminal in ba chỉ số PRD và số lượt PASS:

```text
Grounding Rate: 1.0
Structured Output Integrity: 1.0
Tool Calling Accuracy: 1.0 (86 lượt)
PASS 91/92
```

| Chỉ số | Ngưỡng |
|---|---|
| Grounding Rate | 100% |
| Structured Output Integrity | 100% |
| Tool Calling Accuracy | ≥ 95% |

Exit code `0` khi mọi lượt PASS và ba chỉ số đạt ngưỡng; `1` khi có lượt FAIL hoặc chỉ số dưới ngưỡng.

Biên bản ghi vào `src/evaluation/reports/`:

- `eval-<ngày>-golden.md`: commit, model, ba chỉ số, latency p50/p95/max, danh sách lượt FAIL kèm lý do.
  Commit file này cùng thay đổi.
- `eval-<ngày>-golden.json`: dữ liệu thô từng lượt, đã gitignore.

Chạy nhiều lần trong cùng ngày thì file bị ghi đè; biên bản còn lại là của lần chạy cuối.

Trên LangSmith, mỗi lượt là một trace tên `G-073#2 chưa chốt ngày đi`, gắn tag `golden`, id case và category.
Lọc theo id case để xem đúng lượt đó; mở node `classify` để xem nhãn phân luồng, node `extract` để xem LLM trích ra gì, node `tool` để xem tool plan.

Khi có lượt FAIL, xác định là kỳ vọng sai, lỗi agent hay nhiễu LLM theo
[golden-dataset.md](golden-dataset.md) mục 8.

## 4. Lỗi thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `httpx.ConnectError: All connection attempts failed` | Backend không chạy | Làm lại bước 2 |
| Hầu hết case ra `FALLBACK` hoặc sai điểm đến | Backend chạy khi Postgres tắt, nên recsys bị tắt | Bật Postgres rồi khởi động lại backend; kiểm log có `startup.recsys.index.load.ready` |
| `Không dựng được LLM` | `ITINERARY_USE_LLM=false` hoặc thiếu key | Sửa `.env` |
| `--trace-project cần LANGSMITH_API_KEY` | Thiếu key LangSmith | Thêm `LANGSMITH_API_KEY` vào `.env` |
| G-047 (và các case đã bị bỏ khỏi bộ rút gọn như G-013, G-032) lúc PASS lúc FAIL | Bước `classify` phân loại không ổn định | Đo bằng `--repeat 5`; xem [evaluation-plan.md](evaluation-plan.md) §0.1 |

Đừng đọc P50 hay tổng token của project LangSmith dev (`nhat-23-9`) như số đo agent. `pytest src/backend/tests`
gửi khoảng 140 trace giả (0 token, khoảng 30ms) lên project đó mỗi lần chạy.
