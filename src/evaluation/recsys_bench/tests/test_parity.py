"""B9 `parity.py`: offline (`OfflineEngine(mode="prod")`) phải trùng đường production (`RecommendForUser` với cap 2) khi mọi khác
biệt được trung hoà; `make_users` phân tầng tất định; so sánh phát hiện lệch; HTTP qua MockTransport."""
from datetime import datetime, timezone

import httpx
import pytest

from src.backend.app.application.recommendation import BuildPopularity, RecommendForUser
from src.backend.app.domain.recommendation.profile import MAX_PER_VERTICAL
from src.evaluation.recsys_bench import parity as P
from src.evaluation.recsys_bench.engine import OfflineEngine
from src.evaluation.recsys_bench.tests.conftest import make_events

AS_OF = datetime(2026, 9, 24, 8, 30, tzinfo=timezone.utc)


class _Reader:
    """`CdpHistoryReader` production giả: lịch sử theo khách mới nhất trước, purchase toàn hệ thống (như Postgres)."""

    def __init__(self, events):
        self.events = events

    def events_for_user(self, cdp_user_id):
        return P.events_desc([e for e in self.events if e["cdpUserId"] == cdp_user_id])

    def purchase_events(self, since_days=730):
        return [e for e in self.events if e["eventName"] == "purchase"]


def _production_response(world, events, user, now, k=5):
    index, vectors = world["index"], world["vectors"]
    reader = _Reader(events)
    pop = BuildPopularity(index, reader)(now=now)
    out = RecommendForUser(index, vectors, reader, pop, candidate_k=200, max_per_vertical=MAX_PER_VERTICAL)(user, k=k, now=now)
    return out


def test_offline_prod_engine_matches_production_path_for_every_fixture_user(world):
    """Chứng minh harness **trung hoà đúng** (as_of = generatedAt, event mới nhất trước, popularity theo as_of, cap 2) khi đường
    production là `RecommendForUser` thật với reader giả. Bằng chứng offline = HTTP thật là lượt đo 60/60 với backend local
    (spec §4.12); test này không thay được lượt đo đó."""
    events = make_events()
    users = sorted({e["cdpUserId"] for e in events})
    purchases = [e for e in events if e["eventName"] == "purchase"]
    engine = OfflineEngine(world["index"], world["vectors"], purchases, candidate_k=200, mode="prod")
    rows = []
    for u in users:
        http_like = _production_response(world, events, u, AS_OF)
        assert http_like["generatedAt"] == AS_OF.isoformat()
        rows.append(P.compare_user(u, http_like, engine, [e for e in events if e["cdpUserId"] == u], k=5))
    res = P.verdict(rows)
    assert res["pass"] is True and res["equal"] == len(users) and res["idsMismatch"] == [] and res["fieldsMismatch"] == []
    assert any(r.http_ids for r in rows) and all(len(r.http_ids) <= 5 for r in rows)


def test_popularity_now_anchors_offline_popularity_table(world):
    """Production neo bảng phổ biến ở lúc khởi động; harness nhận mốc đó qua `popularity_now` thay vì generatedAt."""
    from datetime import timedelta
    events = make_events()
    engine = OfflineEngine(world["index"], world["vectors"], [e for e in events if e["eventName"] == "purchase"], mode="prod")
    http_like = _production_response(world, events, "u1", AS_OF)
    started = AS_OF - timedelta(minutes=14)
    row = P.compare_user("u1", http_like, engine, [e for e in events if e["cdpUserId"] == "u1"], k=5, popularity_now=started)
    assert started in engine._popularity and AS_OF not in engine._popularity and row.error is None
    assert P.compare_user("u1", http_like, engine, [e for e in events if e["cdpUserId"] == "u1"], k=5).equal is True


def test_compare_detects_mismatch_and_markdown(world):
    events = make_events()
    engine = OfflineEngine(world["index"], world["vectors"], [e for e in events if e["eventName"] == "purchase"], mode="prod")
    http_like = _production_response(world, events, "u1", AS_OF)
    http_like["recommendations"] = list(reversed(http_like["recommendations"]))
    http_like["diagnostics"]["excludedVerticals"] = ["golf"]
    row = P.compare_user("u1", http_like, engine, [e for e in events if e["cdpUserId"] == "u1"], k=5)
    assert row.equal is False and row.ids_equal is (len(http_like["recommendations"]) < 2) and row.fields_equal is False
    res = P.verdict([row, P.ParityRow("x", None, [], [], error="boom")])
    assert res["pass"] is False and res["errors"][0]["user"] == "x" and res["n"] == 2
    md = P.markdown([row], res, k=5)
    assert "u1" in md and "✗" in md and "khách trùng hoàn toàn" in md


def test_make_users_is_deterministic_and_stratified():
    events = [{"cdpUserId": f"VP{i:07d}", "eventName": "purchase", "productId": "R1", "timestamp": ts, "eventGroupId": "g"}
              for i, ts in [(n, "2026-09-10T00:00:00Z") for n in range(5, 45)]
              + [(n, "2026-03-01T00:00:00Z") for n in range(45, 65)] + [(n, "2025-05-01T00:00:00Z") for n in range(65, 80)]]
    events += [{"cdpUserId": f"VP{i:07d}", "eventName": "product_view", "productId": "R1", "timestamp": "2026-09-01T00:00:00Z", "eventGroupId": None}
               for i in range(80, 100)]
    events += [{"cdpUserId": "VP0000001", "eventName": "purchase", "productId": "R1", "timestamp": "2026-09-19T00:00:00Z", "eventGroupId": "p"}]
    as_of = datetime(2026, 9, 22, tzinfo=timezone.utc)
    a = P.make_users(events, as_of, seed=42)
    b = P.make_users(events, as_of, seed=42)
    assert a == b and len(a["users"]) == 60 and [u["cdpUserId"] for u in a["users"][:4]] == sorted(P.PERSONA_IDS)
    from collections import Counter
    assert Counter(u["stage"] for u in a["users"][4:]) == P.STAGE_QUOTA and a["users"][0]["stage"] == "active"
    assert P.make_users(events, as_of, seed=7)["users"][4:] != a["users"][4:]
    with pytest.raises(P.ParityError, match="churned"):
        P.make_users(events, as_of, seed=1, quota={"churned": 99})
    # có cdp.profiles → tầng theo lifecycleStage seed ghi, gồm khách không có event (đường popular)
    profiles = [{"cdpUserId": f"VP{i:07d}", "lifecycleStage": "new"} for i in range(100, 130)] \
        + [{"cdpUserId": u["cdpUserId"], "lifecycleStage": u["stage"]} for u in a["users"][4:]]
    c = P.make_users(events, as_of, seed=42, profiles=profiles, quota={"new": 10, "active": 2})
    assert c["stageSource"] == "profiles" and c["zeroEventUsers"] >= 1 and len(c["users"]) == 16
    assert a["stageSource"] == "events" and a["zeroEventUsers"] == 0


def test_parity_http_uses_service_token_and_tolerates_errors(world, tmp_path):
    events = make_events()
    engine = OfflineEngine(world["index"], world["vectors"], [e for e in events if e["eventName"] == "purchase"], mode="prod")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, dict(request.url.params), request.headers.get("X-Service-Token")))
        user = request.url.params["cdp_user_id"]
        if user == "bad":
            return httpx.Response(500, json={"error": {"code": "INTERNAL"}})
        return httpx.Response(200, json=_production_response(world, events, user, AS_OF))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(P.ParityError, match="32"):
        P.parity_http("http://x", ["u1"], engine, events, k=5, token="short", client=client)
    rows = P.parity_http("http://x", ["u1", "u2", "bad"], engine, events, k=5, token="t" * 40, client=client)
    assert seen[0] == (P.INTERNAL_PATH, {"cdp_user_id": "u1", "k": "5"}, "t" * 40)
    res = P.verdict(rows)
    assert res["equal"] == 2 and res["errors"] == [{"user": "bad", "error": "HTTP 500"}] and res["pass"] is False
    p = P.write_parity(tmp_path / "r", base_url="http://x", rows=rows, result=res)
    assert p.exists() and "rows" in p.read_text(encoding="utf-8")
    (tmp_path / "u.json").write_text('{"users": [{"cdpUserId": "u1"}, "u2"]}', encoding="utf-8")
    assert P.load_users(tmp_path / "u.json") == ["u1", "u2"]
