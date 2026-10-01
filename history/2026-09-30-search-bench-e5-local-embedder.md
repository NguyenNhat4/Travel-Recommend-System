# Search bench: embedder local `multilingual-e5-base` (arm E2.e5) bằng transformers + torch

- Ngày: 2026-09-30
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Kế hoạch 3 ngày, mục P3 và yêu cầu của người dùng 30/09: tuần này phải so sánh **≥ 2 model embedding** trên gold. Lịch
10 ngày M2 ghi "≥ 1 arm E so Cohere vs `multilingual-e5-base`". Model đã có trong cache HF của máy; bench chưa có
provider local (`embed/__init__.py` báo "cài ở ngày 5"). Phục vụ FR-SRC-02 (đối chứng lựa chọn Cohere), AC-SRC-01.

## File thay đổi

- `src/evaluation/search_bench/embed/local_hf.py` — thêm: `LocalHFEmbedder` (transformers `AutoModel` + torch; pooling
  `mean` (e5) / `cls` (bge-m3, gte) rồi L2-normalise; prefix `query: ` / `passage: ` theo `input_type`; đếm token bằng
  tokenizer của model kể cả prefix, vượt `max_seq_length` → `TokenLimitError`, không cắt ngầm; nạp lười; test tiêm
  `encode_fn` / `tokenizer` giả).
- `src/evaluation/search_bench/embed/__init__.py` — sửa: `_kind` trả `local` cho model có `hf_model`; `embedder_name`
  = `hf_model`; `_local` kiểm `transformers` + `torch`; `make_embedder` nhánh local.
- `src/evaluation/search_bench/config.py` — sửa: `ModelConfig` thêm `query_prefix`, `passage_prefix`, `pooling`.
- `src/evaluation/search_bench/config/sbench.yaml` — sửa: model `e5-base` (768-d, 512, mean, prefix); `bge-m3`, `gte-mb`
  thêm `pooling: cls`.
- `src/evaluation/search_bench/__main__.py` — sửa: `sb tokens --model <local>` đếm bằng tokenizer HF (kể cả prefix
  `passage: `), hard max = `max_seq_length`.
- `src/evaluation/search_bench/doctor.py` — sửa: check "local models" (transformers + torch, model trong cache HF) thay
  check sentence-transformers.
- `src/evaluation/search_bench/requirements-extra.txt` — sửa: `torch`, `transformers` thay `sentence-transformers`.
- `src/evaluation/search_bench/arms/E2.e5.yaml` — thêm: arm giải sẵn (text T3+R của B0, model e5-base, dense).
- `src/evaluation/search_bench/tests/test_local_hf.py` — thêm: 7 test (config, prefix theo input_type, normalise, từ chối
  text quá dài, tắt preflight, thiếu torch, cache theo tên hf, pooling + batching).
- `src/evaluation/search_bench/tests/test_embed.py` — sửa: model local nay tạo được (lười), không còn lỗi "ngày 5".
- `docs/spec/bench/arms.md` — sửa: thêm dòng E2.e5 vào bảng §1 (44 arm), đoạn E2.e5 ở §2.
- `docs/spec/bench/search-eval-local-spec.md` — sửa: §1.6 requirements-extra và config model local.

## Quyết định

- **Không dùng sentence-transformers.** Gói cài được nhưng import thất bại: DLL `scipy.optimize._moduleTNC` bị
  Application Control của Windows chặn — ở **cả** `.venv-sbench` lẫn `.venv` (backend), tức là chính sách máy chứ không
  phải do pip vừa cài. `transformers` 5.17 + `torch` 2.14 import và chạy model bình thường (kiểm offline: e5 nạp, cos(doc,
  query) = 0,86). Pooling làm đúng model card / `1_Pooling/config.json` của e5 (mean pooling), nên vector tương đương
  sentence-transformers.
- **Prefix bắt buộc** cho e5 nằm trong config model, ghép lúc encode; khoá cache vẫn là text gốc + `input_type` + tên
  embedder. Đổi prefix phải đổi tên model (cache) — ghi trong docstring.
- **Không cắt ngầm** (spec §1.7 #2): kiểm token trước bằng tokenizer HF; T3+R trên 3.183 text: p50 144, p90 203, p99 236,
  max 301 < 512 → qua gate.
- `arms/E2.e5.yaml` viết dạng đã giải, `parent: B0`: chuỗi E1a → E1b → E4 bị bỏ qua tuần này (luật cắt lịch 10 ngày §7.2,
  người dùng chốt 30/09), nên `@E4` = B0.

## Kiểm tra

- `pytest evaluation/search_bench/tests -q -p no:cacheprovider`: **318 passed, 10 skipped** (gồm P4 cùng lượt).
- `sb tokens --variant T3+R --model e5-base`: n=3183 p50=144 p90=203 p99=236 max=301 — gate qua (26 s).
- `sb collection create --variant T3+R --model e5-base` → `sb embed` (3.183 vector × 768, 100 lô, 737 s CPU, 0 $) →
  `sb load`: `Products__T3_R__e5_base` 3.183 object, complete.
- `sb query "resort Nha Trang view biển" --arm E2.e5 --limit 5`: top-5 đều là khách sạn / resort Nha Trang (Marriott Hon
  Tre, Vinpearl Beachfront, Lucky Sun, Harry Premier, Vinpearl Resort & Spa Nha Trang Bay), distance 0,115–0,122.

## Còn lại / rủi ro

- Chưa chạy E2.e5 trên gold thật (chờ `gold_v1`); lệnh: `sb run --arm B0 --arm E2.e5` → holes → `gold_v2` → `rescore` →
  `sb compare B0 E2.e5`.
- Sanity `input_type_vectors_differ` cho e5: prefix khác nhau nên vector khác — sẽ đo chính thức khi có cổng SAN (P7).
- bge-m3 (`E2.bge`, cls pooling) có trong cache HF, chạy được với cùng đường; chưa embed (dự phòng nếu còn CPU).
- Máy khác không bị chặn scipy vẫn dùng được `transformers` + `torch`; không cần sentence-transformers.
