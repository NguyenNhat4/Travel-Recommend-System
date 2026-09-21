# V-OTA backend — search · similar · recommendations (MVP in-memory)

```bash
cd src/backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export PRODUCTS_PATH=../../data/products.jsonl          # file 2.216 sản phẩm
export EVENTS_PATH=../../data/events.jsonl              # tuỳ chọn: cdp.events mock (JSONL, camelCase)
export EMBED_MODEL=intfloat/multilingual-e5-base        # đổi sau benchmark: BAAI/bge-m3 ...
export SEARCH_CUTOFF=0.80                               # calibrate lại theo model
uvicorn app.main:app --reload
pytest tests -q                                         # 7 test, không cần tải model (FakeEmbedder)
```

Lần chạy đầu tải model (~1,1 GB) và embed ~1.125 search unit (1–3 phút CPU), cache ở `.embcache/units_<hash>.npy`;
đổi template hoặc model → hash đổi → embed lại.

Endpoint: `GET /api/v1/search?q=&taxonomy=&destination=&limit=&offset=` ·
`GET /api/v1/similar/{productId}?k=` · `GET /api/v1/recommendations?k=&cdp_user_id=` (tạm, sẽ lấy từ JWT) ·
`GET /api/v1/popular?k=`

## Chỗ nào làm gì (ARCHITECTURE.md §4–5)

| Lớp | File | Nội dung |
|---|---|---|
| domain/catalog | `models.py`, `text_builder.py` | Product + vai trò (variant, is_search_unit, is_bookable); text builder theo variant |
| domain/search | `scoring.py` | FILTER → SCORE → CUTOFF → TOTAL/FACETS thuần numpy |
| domain/recommendation | `profile.py`, `popularity.py` | user vector 2 thang thời gian, MMR, because[]; điểm đến tháng/mùa |
| application | `ports.py` | `EmbedderPort`, `UnitIndex`, `VectorStorePort`, `CdpClientPort` |
| application/search | `use_cases.py` | `SearchProducts`, `SimilarProducts` |
| application/recommendation | `use_cases.py` | `RecommendForUser`, `BuildPopularity` |
| infrastructure | `embeddings/`, `vectors/in_memory_store.py`, `cdp/local_cdp_client.py` | hiện thực port; thay bằng `pgvector_store.py` / `PostgresCdpClient` sau |
| api/v1/routes | `search.py`, `recommendations.py` | chỉ HTTP, đọc use case từ `app.state` |
| `main.py` | composition root | nối infrastructure vào use case |

Quy tắc: `domain` không import FastAPI/DB/model; `application` chỉ import `ports`; chỉ `main.py` biết infrastructure.
