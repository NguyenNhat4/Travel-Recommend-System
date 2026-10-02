# P5: gọi Cohere song song khi index, có giới hạn tốc độ

- Ngày: 2026-09-29
- Người yêu cầu: Đăng Khôi ("Phần gọi Cohere, tôi muốn song song luôn"; key hiện là Trial, "nếu hết thì đổi key được")
- Phục vụ: FR-SRC-02 (tự động vector hoá, `search_document` khi nạp), FR-CAT-01..04 (catalog tươi: sản phẩm mới tìm được
  sớm). PRD không quy định cách job index gọi Cohere (tuần tự hay song song), nên plan này không lệch PRD. Riêng việc có ghi
  biến môi trường mới vào `docs/prd/deployment-plan.md` §2 hay không: xem "Cần chốt" 2.
- Tiếp theo: `docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md` (P1–P4 xong). Vẫn không dùng Airflow.
- Phạm vi:
  - `src/backend/jobs/embed_products.py`;
  - `src/backend/app/infrastructure/embeddings/cohere_embedder.py`;
  - `src/backend/app/core/config.py`;
  - test backend tương ứng;
  - `.env.example`, `src/backend/README.md`, `src/data_collection/fresh-catalog.env.example`.
- **Ngoài phạm vi:**
  - Search lúc chạy API (`embed_query`, một câu mỗi request): không đổi, không bị giới hạn tốc độ mới;
  - port `EmbedderPort`, contract, DDL, Weaviate schema, model, `input_type`.
- Quy tắc đọc trước khi code (AGENTS.md §1.2, backend + Search): đã đọc
  - `src/backend/README.md`;
  - `docs/prd/architecture.md` §2 (quy tắc phụ thuộc 1–11);
  - `docs/spec/hop-dong-tich-hop-backend.md` (mục lục, mục Search / Catalog);
  - `docs/prd/requirements.md` FR-SRC-02, NFR-PERF-03.
  - Chưa đọc hết `docs/spec/hop-dong-tich-hop-search-recommendation.md`: **phải đọc trước khi code P5.2**.
- Tiến độ (2026-09-29): người yêu cầu duyệt plan và chốt 3 mục theo đề xuất ("chốt theo đề xuất, làm P5 đi"). P5.1–P5.3
  xong (`history/2026-09-29-p5-1-gioi-han-toc-do-cohere.md`, `-p5-2-nhung-song-song-khi-index.md`,
  `-p5-3-tai-lieu-va-do-that.md`), chờ người yêu cầu kiểm tay.

## Hiện trạng (đọc code và đo 2026-09-29)

- `embed_products.run()`:
  - so `textHash` / `modelVersion` để chỉ nhúng dòng mới hoặc đổi;
  - chia thành lô 96 text (`CohereEmbedder.batch_size`), rồi với **từng lô, tuần tự**: gọi Cohere → xoá object cũ → ghi
    object mới vào Weaviate;
  - lô nào xong thì đã ghi, nên dừng giữa chừng không mất phần đã xong; chạy lại chỉ nhúng phần còn thiếu.
- `CohereEmbedder._request`:
  - gặp 429 / 5xx thì tự chờ và thử lại tối đa 6 lần (theo `Retry-After`, không có thì 2, 4, 8… tối đa 60 s);
  - không có giới hạn tốc độ chủ động; mỗi lần gọi độc lập.
- Job được gọi từ hai chỗ trong `fresh_catalog.py`: bước index cuối lượt (`index_catalog`) và index theo phần khi chạy
  liên tục (L5, `stream.index`). Cả hai dùng chung `run()`, nên sửa một chỗ là đủ.
- Số đo:
  - lượt index local `index-20260929T033719Z-57914`: 274 dòng = 3 lô trong 6,1 s (~1,5–2 s mỗi lô, gồm ghi Weaviate);
  - catalog đầy đủ (DB `vota` local, snapshot 11.387 sản phẩm): **3.183 search unit = 34 lô**. Nhúng lại toàn bộ tuần tự
    ≈ 1 phút;
  - lượt hằng ngày thường chỉ nhúng dòng đổi: 1–3 lô.
- Key Cohere hiện là **Trial**: 100 lượt gọi / phút (header `x-trial-endpoint-call-limit: 100`), 1.000 lượt / tháng. Ngày
  29/09 key cũ hết quota tháng; người yêu cầu đã đổi key.

**Lợi ích thật (nói rõ để quyết):** gọi song song không giảm số lượt gọi, nên không tiết kiệm quota; nó chỉ rút thời gian.
- Với catalog hiện tại: nhúng lại toàn bộ từ ~1 phút xuống ~15–20 s. Lượt hằng ngày gần như không đổi.
- Có ích rõ khi:
  - catalog lớn lên (job cào mở rộng hằng ngày);
  - cần nhúng lại toàn bộ (đổi `TEXT_BUILDER_VERSION` hoặc model);
  - chạy liên tục bật `stream.index`, để sản phẩm mới tìm được sớm hơn.

## Đã chốt (2026-09-29, Đăng Khôi: "chốt theo đề xuất")

1. **Mặc định, theo key Trial.**
   - Tối đa **4** lô gọi cùng lúc (`COHERE_EMBED_CONCURRENCY`).
   - Tối đa **90** lượt gọi mỗi phút (`COHERE_CALLS_PER_MINUTE`, dưới trần 100 để chừa chỗ cho Search đang chạy cùng key).
   - Đổi sang Production key thì chỉ chỉnh env (ví dụ 8 lô, 1.500 lượt / phút), không sửa code.
   - Đặt 1 lô = chạy tuần tự như hôm nay; 0 lượt / phút = không giới hạn.
2. **Có ghi hai biến mới vào `docs/prd/deployment-plan.md` §2 không.**
   - Đề xuất: **không**. Đây là biến tinh chỉnh, không bí mật, giống `SEARCH_CUTOFF` và `CATALOG_REFRESH_SECONDS` vốn chỉ
     ghi ở README / `.env.example`.
   - Muốn ghi vào PRD thì phải có đề xuất trong `docs/prd/update/` chốt trước (AGENTS.md §8).
3. **Đo thật tốn quota.** Nhúng lại toàn bộ catalog = 34 lượt gọi (3,4% quota Trial mỗi tháng).
   - Đề xuất: đo tốc độ bằng Cohere giả (có độ trễ) trong test, và một lần thật trên sandbox `vota_crawl`
     (≈3 lượt gọi, `--force` nhúng lại).
   - Đo thật trên catalog đầy đủ chỉ khi người yêu cầu đồng ý tốn ~34 lượt gọi.

## Cách làm việc

- Làm tuần tự P5.1 → P5.3. Mỗi bước có test pass và người yêu cầu kiểm tay rồi mới sang bước sau. Mỗi bước có entry
  `history/` riêng. Không commit.
- Test backend chạy từ repo root:
  `PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider src/backend/tests/unit src/backend/tests/architecture`
  (môi trường có dependency backend; env `vsf2` thiếu fastapi, xem ghi chú môi trường test).
- Test data_collection như P1–P4 (bước index của `fresh_catalog` gọi `run()`).
- **Điều kiện bắt buộc:** cùng catalog, cùng Cohere giả, thì Weaviate sau khi index song song phải **giống hệt** tuần tự:
  cùng tập object, cùng `productId`, `textHash`, `modelVersion`, cùng vector. So bằng vector store giả trong test.

## P5.1 — Giới hạn tốc độ dùng chung cho các lần gọi Cohere

- **Airflow:** `pool` giới hạn số task dùng chung một tài nguyên; ở đây tài nguyên là quota Cohere.
- **Vì sao:** gọi song song mà không giới hạn sẽ vượt 100 lượt / phút của key Trial rồi bị 429 hàng loạt. Mỗi luồng tự chờ
  riêng thì các luồng khác vẫn gọi tiếp, làm 429 kéo dài.
- **Việc làm:**
  - `CallLimiter` trong `cohere_embedder.py` (hạ tầng, không vào `domain` / `application`):
    - trước mỗi lần gọi phải lấy một "vé"; tối đa `calls_per_minute` vé trong 60 s trượt;
    - khi một luồng nhận 429: đặt "tạm dừng tới T" (theo `Retry-After`, không có thì backoff hiện tại) **cho mọi luồng**.
  - `CohereEmbedder(..., limiter=None)`: không truyền limiter thì hành vi y như hôm nay. API Search không truyền, nên không
    đổi.
  - Đồng hồ và hàm chờ tiêm vào được, để test không phải chờ thật.
- **Test tự động** (`tests/unit/infrastructure/test_cohere_embedder.py`):
  - 10 lần gọi với giới hạn 3 / phút (đồng hồ giả): lần thứ 4 phải chờ tới khi lần 1 ra khỏi cửa sổ 60 s;
  - một luồng nhận 429 + `Retry-After: 5` → các luồng khác không gọi trong 5 s đó;
  - không có limiter: số lần gọi và thứ tự như trước (test cũ vẫn pass).
- **Bạn kiểm:** chỉ có test (chưa song song, chưa đổi hành vi job).
- **Xong khi:** một limiter dùng chung giữ được số lượt gọi mỗi phút dưới giới hạn, kể cả khi nhiều luồng cùng gọi.

## P5.2 — Nhúng song song trong job index

- **Airflow:** dynamic task mapping (mỗi lô một task) + `max_active_tis_per_dag` (giới hạn số task chạy cùng lúc).
- **Việc làm:**
  - Trong `embed_products.run()`: các lô gọi Cohere qua `ThreadPoolExecutor(max_workers=cohere_embed_concurrency)`, dùng
    chung một `CohereEmbedder` + `CallLimiter`.
    - Giữ tối đa `concurrency` lô đang chờ, để không đưa cả catalog vào bộ nhớ một lúc.
  - **Chỉ luồng chính ghi Weaviate**, theo thứ tự lô nào xong trước ghi trước: xoá object cũ rồi ghi object mới, như hôm
    nay. Tránh ghi Weaviate từ nhiều luồng (client dùng chung chưa kiểm là an toàn khi dùng từ nhiều luồng).
  - Một lô lỗi hẳn (hết lần thử lại):
    - không gửi thêm lô mới, chờ các lô đang chạy xong và ghi chúng;
    - rồi ném lỗi như hôm nay: lượt index lỗi, phần đã ghi được giữ, chạy lại chỉ nhúng phần thiếu.
  - Cấu hình (`core/config.py`, không bí mật): `cohere_embed_concurrency` (mặc định 4, 1–16),
    `cohere_calls_per_minute` (mặc định 90, 0 = không giới hạn).
    - Env `COHERE_EMBED_CONCURRENCY`, `COHERE_CALLS_PER_MINUTE`, đọc qua `Settings` như các biến khác.
    - `fresh_catalog.index_settings` dựng `Settings` từ env nên job VM nhận luôn, không sửa `data_collection`.
  - `concurrency = 1`: chạy tuần tự như hôm nay (không tạo pool).
  - Báo cáo của `run()` thêm `seconds`, `cohereCalls`, `concurrency`, `rateLimited` (số lần gặp 429). Hiện ở chi tiết bước
    index trên monitor: `detail` của bước lấy nguyên báo cáo, không sửa monitor.
  - Thêm cờ `--force` cho `embed_products` (nhúng lại mọi search unit dù `textHash` không đổi), chỉ để đo.
- **Test tự động** (`tests/unit/infrastructure/test_embed_products_job.py`, vector store và embedder giả):
  - **song song = tuần tự:** cùng catalog 500 dòng, concurrency 1 và 4 cho cùng tập object trong Weaviate giả;
  - số lô chạy cùng lúc không vượt `concurrency` (đếm trong embedder giả có độ trễ);
  - chỉ luồng chính gọi `insert` / `delete` (ghi lại tên luồng trong store giả);
  - lô thứ 3 lỗi: các lô đã xong vẫn được ghi, job ném lỗi, lần chạy lại chỉ nhúng phần thiếu;
  - Cohere giả trễ 0,5 s / lô, 8 lô: concurrency 4 nhanh hơn tuần tự ít nhất 2 lần;
  - báo cáo có `cohereCalls`, `concurrency`, `rateLimited`;
  - test kiến trúc (`tests/architecture/`) vẫn pass: không import mới từ `domain` / `application` ra ngoài.
- **Bạn kiểm:**
  - `./local_crawl.sh run index` trên sandbox sau khi đổi text của vài sản phẩm (hoặc `--force`) → thời gian và số lượt
    gọi trong chi tiết bước index;
  - Search trên sandbox trả kết quả như trước.
- **Xong khi:** index nhúng song song trong giới hạn tốc độ; kết quả Weaviate giống hệt tuần tự.

## P5.3 — Tài liệu, cấu hình VM, đo thật

- **Việc làm:**
  - `.env.example` (khối backend / job embed), `src/data_collection/fresh-catalog.env.example`, `src/backend/README.md`
    (mục Search / Recommendation): thêm hai biến, giá trị cho Trial / Production key.
  - Đo thật trên sandbox (`--force`, ~3 lượt gọi): thời gian tuần tự và song song; ghi vào `history/`.
  - Đo trên catalog đầy đủ chỉ nếu người yêu cầu chốt mục 3.
- **Xong khi:** người vận hành biết chỉnh hai biến khi đổi key; có số đo thật.

## Rủi ro

- **Quota tháng của Trial không đổi:** song song chỉ tiêu nhanh hơn, không tiêu ít hơn. Hết quota thì mọi lượt index
  (và Search, nếu dùng chung key) lỗi 429 như 29/09. Không nằm trong phạm vi plan này; cách xử lý vẫn là đổi key.
- Dùng chung key với Search đang chạy: limiter chỉ đếm lượt gọi của job, không biết Search gọi bao nhiêu. Để 90 / phút là
  để chừa chỗ. Key Production thì gần như không gặp.
- `httpx.Client` dùng từ nhiều luồng: tài liệu httpx nói an toàn, nhưng phải có test gọi đồng thời thật (P5.2) trước khi
  dựa vào.
- Ghi Weaviate vẫn tuần tự. Nếu sau này ghi thành điểm nghẽn thì mới tính song song ghi, bằng batch API của Weaviate.
