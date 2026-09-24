# Chạy lại Day 1 của Người B trên clone mới sau khi gộp app gán nhãn

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu hoàn tất phần Day 1 của Người B trong `docs/spec/bench/search-eval-checklist.md`, trừ việc Người A chọn 200 draft bằng app Streamlit. Các ô đó đã tick trên nhánh `bench/embed-search` bằng bằng chứng 23/09, nhưng máy này là clone sạch: không có `.venv-sbench`, không có `bench_out/`, volume Weaviate của bench chưa tồn tại. Vì vậy phần việc thật là **tái lập toàn bộ chuỗi Day 1 sau khi merge app gán nhãn**, để chắc rằng nhánh gộp vẫn chạy được, rồi ghi số đo 24/09 bên cạnh số 23/09.

Phục vụ FR-SRC-01..04, NFR-PERF-01, NFR-PERF-03, AC-SRC-01.

## File thay đổi

- `docs/spec/bench/search-eval-checklist.md` — sửa: thêm block-quote *24/09 kiểm lại trên clone mới* sau khối `### B` của Ngày 1 (không viết lại ghi chú 23/09 của ai); thêm ghi chú property thật trong Weaviate là `parent_product_id` vào ô `collection create`.
- `history/2026-09-24-sbench-ngay-1-kiem-lai-tren-clone-moi.md` — thêm: entry này.

Không sinh file nào trong `src/evaluation/search_bench/gold/` (thư mục của Người A). Artefact chạy nằm trong `bench_out/` (đã gitignore).

## Quyết định

- Dùng `.venv-sbench` riêng theo header của `requirements.txt`, không dùng `.venv` gốc (chỉ có pip) và không dùng miniconda base.
- Chạy toàn bộ trên `--dataset sample` (26 search unit): đủ để nghiệm thu chuỗi Day 1, tốn ~$0,0004. Không embed lại toàn catalog vì nhánh đã có bằng chứng 24/09 của Người B (2.897 vector, $0,045) và collection thật chỉ khác dataset.
- Không viết lại ghi chú 23/09 trong checklist. `history/README.md` cấm sửa lịch sử, và số của hai lần chạy là hai sự thật riêng (ví dụ Docker 29.7.2 ở 23/09 vs 29.4.2 trên máy này).
- Không tự chốt `stopwords_preset: none`, `max_tokens_per_min: 90000`, ngữ nghĩa `retry.max_attempts` — vẫn là *đề xuất* chờ Người A/mentor xác nhận.
- Giữ nguyên cách ghi `parentProductId` trong câu checklist (đó là tên field của `products.jsonl`) nhưng ghi thêm tên property thật `parent_product_id` để tick không lệch với `store/weaviate_store.py::KEYWORD_PROPS`.
- Giữ collection `Products__T3_R__cohere_v3__sample` lại vì ô demo cuối ngày trỏ vào nó.

## Kiểm tra

Mọi lệnh chạy từ `src/` với `PYTHONUTF8=1`, interpreter `.venv-sbench`.

- `python -m venv .venv-sbench` + `pip install -r src/evaluation/search_bench/requirements.txt` + `pip check`: **INSTALL_OK**, không xung đột.
- `docker compose -f evaluation/search_bench/docker/compose.yml up -d --wait weaviate`: `sbench-weaviate-1 Healthy`; `GET /v1/meta` → version **1.37.3**, `/v1/.well-known/ready` → 200.
- `sb doctor`: **exit 0** — docker server 29.4.2 · weaviate 1.37.3 ready · gRPC 127.0.0.1:55051 mở · ascii_fold `text_analyzer(ascii_fold=True)` trên `name`, `embed_text` · `COHERE_API_KEY` hợp lệ (tokenize "xin chào" = 2 token) · products.jsonl 10.320 dòng · sample 50 dòng · disk 764,8 GB · `bge-m3` WARN (chỉ cần E2/P5) · `gold tags` INFO (chưa tới ngày 4).
- `sb --dataset sample catalog build`: 26 search unit / 50 bản ghi; variant `{hotel_property 8, attraction 5, combo 5, flight_route 4, golf 4}`; 0 con mồ côi; 9 điểm đến; amenity phủ 30,8% (seed 23 · raw 36 · trigram 3).
- `sb --dataset sample collection create --variant T3+R --model cohere-v3`: `Products__T3_R__cohere_v3__sample (logic products__T3+R__cohere_v3) · ascii_fold analyzer · index flat · stopwords none`.
- `sb --dataset sample embed --variant T3+R --model cohere-v3 --limit 50`: 26 vector × 1024 · mới 26 · **1 lượt gọi · 3.654 token · $0,000365** · 1,29 s — trùng khít số 23/09.
- Chạy lại y hệt lệnh trên: **mới 0 · từ cache 26 · 0 lượt gọi · $0,0** → bằng chứng cache `sha1(model|input_type|text)`.
- `sb --dataset sample load --variant T3+R --model cohere-v3`: 26 object, 2,6 s. `sb --dataset sample collection list`: `complete=True`, `embedder=embed-multilingual-v3.0`, `fold=analyzer`, `items=39e24f766b`.
- `sb --dataset sample tokens --variant T3+R --model cohere-v3`: n=26 p50 134 p90 188 p99 214 max 217 → **token gate: qua** (p99 < 450, max < 512).
- `sb --dataset sample query "resort Nha Trang" --arm B0`: top-1 **Vinpearl Resort & Spa Nha Trang Bay (0,3225)**, top-2 Vinpearl Beachfront Nha Trang (0,3608), top-3 VinWonders Nha Trang (0,3788); footer `input_type=query`.
- `sb cost`: 4 lượt gọi / 28 text / 3.659 token / **$0,000365** (embed document 1, embed query 1, models.get 1, tokenize 1) — dưới trần $0,01 và 10 lượt gọi đặt cho PR này.
- `pytest evaluation/search_bench/tests`: **129 passed, 9 skipped** (125 của nhánh + 3 của `test_labeling.py` + 1 test quota mới). 9 skip là integration, đúng thiết kế.
- `pytest -m integration evaluation/search_bench/tests`: **9 passed**, gồm `test_50_random_filters_match_pandas`.
- App gán nhãn (Streamlit `AppTest`, chạy từ gốc repo để đọc `.streamlit/secrets.toml`): chưa nhập mật khẩu → chặn; nhập sai → vẫn chặn, 0 metric; nhập đúng → 0 exception, "Tổng case 600", selectbox Slice 13 slice.
- Không chạy `validate_contract.py`: không đổi OpenAPI hay mock. Không chạy `db/verify.sql`: không đổi schema hay seed.

## Còn lại / rủi ro

- Ô còn `[ ]` của Day 1 và lý do: **mentor xác nhận bằng văn bản** 3 mục lệch handbook (ngoài tầm phiên làm việc); **Người A chọn 200 draft → `gold/drafts.txt`** (người dùng loại khỏi phạm vi lần này); **A đưa B `gold/drafts.txt`** (phụ thuộc ô trên); **bổ sung 30 ứng viên `c0601`–`c0630`** (thêm ở entry `2026-09-24-quota-gold-min-per-slice-10.md`).
- Chưa chạy lại `sb embed`/`load` toàn catalog trên máy này, nên collection `Products__T3_R__cohere_v3` (2.897 object) chỉ tồn tại ở máy của Người B. Ai cần B0 thật phải chạy lại (≈30 lượt gọi, ~$0,045, có 429 nên bật `max_tokens_per_min`).
- `sb tokens` trên `--dataset sample` chỉ phản ánh 26 text; số của toàn catalog vẫn là bằng chứng 23/09 (p99 276, max 379).
- Cohere trial: đã dùng 4 lượt gọi trong lượt này; lượt embed toàn catalog trước đó của Người B tốn 30 + 22 lần 429.
- App gán nhãn chưa deploy Community Cloud nên chưa smoke test URL thật; secret Cloud chưa được dán.
- Collection `Products__T3_R__fake` của Người B không có trên máy này (volume mới) — không cần xoá.
