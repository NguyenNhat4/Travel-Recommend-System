# Thêm LLM fallback có kiểm soát vào bước hiểu câu truy vấn của `/search`

- Ngày: 2026-10-06
- Người đề xuất: nhóm Search / Claude (agent soạn)
- Trạng thái: chờ chốt
- Chốt bởi / ngày:
- PRD bị ảnh hưởng: `docs/prd/architecture.md` §1 (sơ đồ: `HybridSearch` chỉ nối Weaviate/Embedding, không nối LLM), §4 (bảng công
  nghệ — LLM chỉ ghi cho Trợ lý), §5 mục 5 (luồng truy vấn search: embed → Weaviate); `docs/prd/requirements.md` NFR-PERF-01 (p95 ≤ 250 ms
  cho API tìm kiếm); `docs/prd/deployment-plan.md` §2 (biến môi trường của search)
- Mã FR/NFR: FR-SRC-01, FR-SRC-03 (hiểu câu → bộ lọc); NFR-PERF-01; mới — cần cấp mã nếu tách thành yêu cầu riêng

## Lý do

1. **Rule + gazetteer không phủ hết câu khó.** Từ 06/10 `/search` có query plan rule-based (điểm đến, câu không dấu, phủ định tiện ích,
   loại sản phẩm, chiều bay, giá/sao, số khách — sau cờ, mặc định tắt) và tự chấm **độ tin cậy** cùng lý do (`queryPlan.confidence`,
   `queryPlan.fallbackReasons`): phủ định không xác định được phạm vi, hai địa danh không rõ vai trò, nhiều loại sản phẩm cùng lúc, cụm
   tiện ích ngoài từ vựng. Với các câu đó engine hôm nay **giữ plan bảo thủ** (không lọc phần không chắc) — an toàn nhưng bỏ lỡ ràng buộc.
   Trên gold_v4 (+ nhãn hole chưa duyệt) 59 / 154 câu có độ tin cậy < 1 (10 câu ≤ 0,5; lý do chính: câu dài nhiều ràng buộc 48, cue
   loại yếu 11, nhiều loại 10); với cấu hình rule tốt nhất (F1–F6) nhóm này đạt nDCG@10 0,770 so 0,832 ở nhóm còn lại
   (`src/evaluation/reports/eval-2026-10-06-search-query-plan-gold-v4.md` §3).
2. **Kiến trúc tham chiếu đã chốt hướng này** (`docs/spec/bench/kien_truc_search_ota_so_do_va_giai_doan.md` §5, Phase C): LLM chỉ là
   fallback có cache và schema chặt, không thay hard filter, không trả `productId`, không xếp hạng.
3. **PRD hiện chỉ cho LLM ở Trợ lý.** Đường `/search` theo PRD là embed → Weaviate (+ BM25), không có lượt gọi LLM. Thêm LLM vào request
   path của `/search` là đổi kiến trúc và có rủi ro NFR-PERF-01 (một lượt gọi LLM thường 300–1.500 ms, vượt ngân sách 250 ms nếu chạy đồng
   bộ) — nên phải chốt trước khi code.

## Nội dung đề xuất

`docs/prd/architecture.md` §5 mục 5, sau đoạn **Truy vấn** — thêm:

> **Hiểu câu truy vấn (query plan).** Use case search phân tích câu bằng luật + gazetteer dựng từ catalog (điểm đến, loại sản phẩm, phủ
> định, chiều bay, giá/sao, số khách) rồi lọc trước khi truy xuất. Khi plan có độ tin cậy thấp, use case **có thể** gọi LLM qua port `llm`
> để lấy một giả thuyết JSON theo schema cố định (`intent`, `entities`, `hard_filters`, `must_not`, `soft_preferences`, `unknown_slots`).
> Server kiểm mọi giá trị với catalog (taxonomy, bảng điểm đến, từ vựng tiện ích, tuyến bay); giá trị không tồn tại bị bỏ, không tạo filter
> sai. LLM **không** trả `productId`, **không** xếp hạng, **không** nới hard filter của request. Kết quả cache theo câu đã chuẩn hoá.
> Ba chế độ theo cấu hình: `off` (mặc định), `shadow` (chạy nền, chỉ ghi so sánh rule ↔ LLM vào log, không đổi kết quả), `on` (chỉ
> khi `confidence < ngưỡng`, có hạn thời gian; quá hạn → plan rule). Bật `on` chỉ khi bench chứng minh không tụt ở các slice an toàn
> (`out_of_catalog`, `named_entity`, `cross_vertical`) và p95 vẫn đạt NFR-PERF-01 nhờ cache.

`docs/prd/architecture.md` §1 sơ đồ — thêm cạnh `HybridSearch -.->|fallback, cache| LLM`.

`docs/prd/deployment-plan.md` §2 — thêm biến `SEARCH_LLM_FALLBACK` (`off|shadow|on`, mặc định `off`), `SEARCH_LLM_FALLBACK_MIN_CONFIDENCE`,
`SEARCH_LLM_FALLBACK_TIMEOUT_MS`.

NFR-PERF-01 **không đổi**: p95 ≤ 250 ms vẫn áp cho `/search`; lượt có gọi LLM chỉ được phép khi nằm trong cache hoặc hạn thời gian cho phép.

## Thay đổi source sau khi chốt

- `src/backend/app/application/search/query_plan_llm.py` (mới): dựng prompt từ câu + plan rule, gọi port `llm`, validate theo catalog,
  merge vào `QueryPlan` (chỉ thêm ràng buộc mà rule bỏ trống; rule và param luôn thắng khi xung đột).
- `src/backend/app/application/search/use_cases.py`: nhánh fallback theo `confidence`, cache theo câu chuẩn hoá, ghi so sánh ở chế độ
  `shadow` (cùng writer `app.search_logs` sau cờ `SEARCH_LOG_QUERIES`).
- `src/backend/app/core/config.py`, `main.py`, `.env.example`: ba biến trên.
- Contract (additive): `queryPlan.llm {mode, used, cached, latencyMs, rejected[]}` trong `schemas/search.yaml`.
- Bench: arm `APP.e5s.*_llm` chạy chế độ `on` với cache cố định để số tái lập được; report tách parse accuracy rule vs LLM.
- Spec `docs/spec/hop-dong-tich-hop-search-recommendation.md` §2.2/§2.4/§10.
