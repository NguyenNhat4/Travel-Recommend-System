import asyncio, json, os, sys, pathlib
import numpy as np, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

# psycopg async không chạy được trên ProactorEventLoop — event loop mặc định của Windows.
# Test gọi asyncio.run() trực tiếp nên phải đặt policy ở đây, trước khi loop đầu tiên được tạo,
# nếu không LocalCdpClient trả InterfaceError trên mọi máy Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Test dựng app (TestClient) đọc `.env` của dev; `.env` bật LANGSMITH_TRACING thì `main._enable_langsmith` đẩy cờ
# vào os.environ và mọi lượt graph với LLM giả sau đó bị gửi lên project LangSmith thật (trace < 1 s, tên
# "lên lịch giúp mình", "conv-khong-co"...). Biến môi trường thật thắng `.env`, nên tắt ở đây trước khi app nào được dựng.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# Test không bao giờ đọc `.env`: file đó của dev thường trỏ DB staging qua tunnel, Weaviate Cloud và khóa Cohere/OpenAI
# thật (APP_ENV=production). Kết nối cho test integration đặt tường minh bằng biến môi trường trong shell, ví dụ
# DATABASE_URL=... RUN_POSTGRES_INTEGRATION=1. Phải chạy trước khi `main` tạo Settings (conftest nạp trước test).
from src.backend.app.core.config import Settings  # noqa: E402
from src.backend.tests.guard import OVERRIDE, remote_dependency_violations  # noqa: E402

Settings.model_config["env_file"] = None


def pytest_configure(config):
    bad = remote_dependency_violations()
    if bad:
        raise pytest.UsageError(
            "Từ chối chạy test: biến môi trường trỏ dịch vụ không phải máy này (" + "; ".join(bad) + "). "
            "Trỏ về Docker cục bộ, hoặc đặt " + OVERRIDE + "=1 nếu thật sự muốn."
        )


class FakeEmbedder:
    """Vector giả, xác định theo hash text — đủ để test luồng, không test chất lượng."""
    name = "fake"
    def _v(self, t):
        r = np.random.default_rng(abs(hash(t)) % (2**32)); v = r.normal(size=64).astype(np.float32); return v / np.linalg.norm(v)
    def embed_docs(self, texts): return np.stack([self._v(t) for t in texts])
    def embed_query(self, q): return self._v(q)


def P(pid, name, tax, dest, attrs=None, price=100000, avail=True, desc="Mô tả nghỉ dưỡng biển cho gia đình."):
    return {"productId": pid, "name": name, "taxonomy": tax, "destination": dest, "description": desc, "attributes": attrs or {},
            "unitPrice": price, "currency": "VND", "available": avail, "availableFrom": None, "availableTo": None, "imageUrl": None, "sourceRef": pid}

ROWS = [
 P("H1","Vinpearl Resort Nha Trang","hotel","Nha Trang",{"level":"property","starRating":5,"propertyType":"khu nghỉ dưỡng","amenities":["bãi biển riêng","hồ bơi"],"oceanView":True,"familyFriendly":True,"province":"Khánh Hòa"},price=None),
 P("R1","Vinpearl Resort Nha Trang - Deluxe Ocean View","hotel","Nha Trang",{"level":"room","parentProductId":"H1","roomName":"Deluxe Ocean View"},price=3400000),
 P("H2","Khách sạn B Nha Trang","hotel","Nha Trang",{"level":"property","starRating":4},price=None),
 P("H3","Resort Phú Quốc","hotel","Phú Quốc",{"level":"property","starRating":5},price=None),
 P("R3","Resort Phú Quốc - Villa","hotel","Phú Quốc",{"level":"room","parentProductId":"H3"},price=5000000),
 P("F1","Vé máy bay Hà Nội - Cam Ranh","flight","Nha Trang",{"level":"route","originCity":"Hà Nội","destinationCity":"Nha Trang"},price=None),
 P("FL1","Vé máy bay Hà Nội - Cam Ranh VJ123","flight","Nha Trang",{"level":"flight","parentProductId":"F1","airline":"VietJet Air"},price=1890000),
 P("A1","VinWonders Nha Trang","attraction","Nha Trang",{"audience":["gia đình"],"venue":"Hòn Tre"},price=880000),
 P("A2","Bãi biển Trần Phú","attraction","Nha Trang",{"ticketed":False},price=None),
 P("C1","Combo 3N2Đ Vinpearl Nha Trang","combo","Nha Trang",{"nights":2},price=9800000),
 P("G1","Vinpearl Golf Nha Trang","golf","Nha Trang",{},price=2000000),
]
EVENTS = [
 {"cdpUserId":"P1","eventName":"product_view","productId":"A1","timestamp":"2026-09-15T10:00:00Z","eventGroupId":"T1"},
 {"cdpUserId":"P1","eventName":"purchase","productId":"R1","timestamp":"2026-09-18T10:00:00Z","usingDate":"2026-10-05","eventGroupId":"T1"},
 {"cdpUserId":"P3","eventName":"purchase","productId":"R3","timestamp":"2025-08-01T10:00:00Z","usingDate":"2025-08-20","eventGroupId":"T0"},   # > 365 ngày: dormant (09/10)
 {"cdpUserId":"X","eventName":"purchase","productId":"R3","timestamp":"2025-09-15T10:00:00Z","usingDate":"2025-10-01","eventGroupId":"c"},
 {"cdpUserId":"Y","eventName":"purchase","productId":"FL1","timestamp":"2025-08-20T10:00:00Z","usingDate":"2025-09-05","eventGroupId":"e"},
]

@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS), encoding="utf-8")
    (d / "events.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in EVENTS), encoding="utf-8")
    return d

@pytest.fixture(scope="session")
def services(data_dir):
    from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore
    from src.backend.tests.fakes.jsonl_cdp_reader import JsonlCdpReader
    from src.backend.app.application.search import SearchProducts, SimilarProducts
    from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
    from datetime import datetime, timezone
    emb = FakeEmbedder()
    index, vectors = InMemoryVectorStore(str(data_dir / "products.jsonl"), emb, str(data_dir / ".embcache")).load()
    cdp = JsonlCdpReader(str(data_dir / "events.jsonl"))
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    pop = BuildPopularity(index, cdp)(now=now)
    return {"index": index, "vectors": vectors, "search": SearchProducts(index, vectors, emb, cutoff=-1.0),
            "similar": SimilarProducts(index, vectors), "recommend": RecommendForUser(index, vectors, cdp, pop), "now": now}
