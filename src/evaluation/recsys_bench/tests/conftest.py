"""Fixture offline: catalog giả của backend (`src/backend/tests/conftest.py`) + bộ event dựng tay đủ các ca biên.

Chạy từ gốc repo: `PYTHONUTF8=1 python -m pytest -q src/evaluation/recsys_bench/tests` — không cần Postgres/Weaviate.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.tests.conftest import ROWS, FakeEmbedder  # noqa: E402


def ev(user, name, product_id, timestamp, group=None, using_date="+45"):
    """Event CDP. Purchase mặc định có `usingDate` = ngày mua + 45 (seed luôn gắn ngày sử dụng, p50 +25 ngày): từ 02/10 trip
    có `usingDate` mở tới hết ngày đó, trip chỉ view mở ≤ 14 ngày (FR-REC-02). `using_date=None` để bỏ."""
    using = None
    if name == "purchase" and using_date is not None:
        if isinstance(using_date, str) and using_date.startswith("+"):
            from datetime import datetime, timedelta
            using = (datetime.fromisoformat(timestamp.replace("Z", "+00:00")) + timedelta(days=int(using_date))).date().isoformat()
        else:
            using = using_date
    return {"cdpUserId": user, "eventName": name, "productId": product_id, "timestamp": timestamp,
            "eventGroupId": group, "usingDate": using}


def make_events() -> list[dict]:
    """17 event, 6 khách. Catalog: R1 → H1 (hotel), FL1 → F1 (flight), R3 → H3, A1 attraction, C1 combo, G1 golf."""
    return [
        ev("u1", "search", None, "2026-05-30T09:00:00Z"),
        ev("u1", "purchase", "R1", "2026-06-01T10:00:00Z", "T1"),
        ev("u1", "product_view", "A1", "2026-06-02T10:00:00Z"),
        ev("u1", "purchase", "FL1", "2026-06-03T10:00:00Z", "T1"),     # target LLBO của u1 → F1
        ev("u1", "product_view", "C1", "2026-06-05T10:00:00Z"),        # sau target: không được vào train
        ev("u2", "purchase", "R3", "2026-03-01T10:00:00Z", "T2"),
        ev("u2", "purchase", "A1", "2026-05-01T10:00:00Z", "T3"),
        ev("u3", "purchase", "C1", "2026-04-01T10:00:00Z", "T4"),      # 1 purchase: không vào test LLBO
        ev("u4", "purchase", "ghost", "2026-04-02T10:00:00Z", "T5"),   # orphan
        ev("u4", "purchase", "A1", "2026-04-03T10:00:00Z"),            # thiếu event_group_id
        ev("u4", "product_view", "ghost-2", "2026-04-04T10:00:00Z"),   # view ngoài catalog: giữ, chỉ đếm
        ev("u5", "purchase", "G1", "2026-04-01T10:00:00Z", "T6"),
        ev("u5", "purchase", "G1", "2026-05-10T10:00:00Z", "T7"),      # mua lại + cùng loại trip đang mở
        ev("VP0000001", "purchase", "R1", "2026-01-01T10:00:00Z", "P1a"),
        ev("VP0000001", "purchase", "A1", "2026-01-02T10:00:00Z", "P1a"),
        ev("VP0000001", "product_view", "R1", "2026-09-20T10:00:00Z"),
        ev("VP0000001", "purchase", "R1", "2026-09-21T10:00:00Z", "P1b"),
    ]


@pytest.fixture(scope="session")
def world(tmp_path_factory):
    from src.backend.tests.fakes.in_memory_vector_store import InMemoryVectorStore

    d = tmp_path_factory.mktemp("recsys_bench")
    (d / "products.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS), encoding="utf-8")
    index, vectors = InMemoryVectorStore(str(d / "products.jsonl"), FakeEmbedder(), str(d / ".embcache")).load()
    return {"index": index, "vectors": vectors}


@pytest.fixture
def events() -> list[dict]:
    return make_events()
