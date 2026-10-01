"""Job làm nóng cache qua HTTP (`jobs/prewarm_query_cache.py`): đếm hit/miss theo `diagnostics.embedCache`, lần hai miss 0."""
import json

import httpx

from src.backend.jobs import prewarm_query_cache as J


class _Backend:
    def __init__(self, with_cache=True):
        self.seen, self.with_cache, self.calls = set(), with_cache, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        q = request.url.params["q"]
        self.calls.append((q, request.url.params["limit"]))
        if q == "boom":
            return httpx.Response(503, json={"error": {"code": "SEARCH_UNAVAILABLE"}})
        status = "miss" if q not in self.seen else "hit"
        self.seen.add(q)
        diag = {"latencyMs": 1, **({"embedCache": status} if self.with_cache else {})}
        return httpx.Response(200, json={"results": [], "total": 0, "diagnostics": diag})


def test_warm_counts_hit_miss_and_errors_then_second_pass_is_all_hits():
    be = _Backend()
    client = httpx.Client(transport=httpx.MockTransport(be))
    r = J.warm("http://x/", ["a", "b", "boom"], client=client)
    assert (r["queries"], r["miss"], r["hit"], r["noCache"], r["errors"]) == (3, 2, 0, 0, 1)
    assert r["errorSamples"][0]["query"] == "boom" and be.calls[0] == ("a", "1")
    again = J.warm("http://x", ["a", "b"], client=client)
    assert (again["miss"], again["hit"]) == (0, 2)
    old = J.warm("http://x", ["z"], client=httpx.Client(transport=httpx.MockTransport(_Backend(with_cache=False))))
    assert old["noCache"] == 1


def test_main_dry_run_and_exit_code(tmp_path, capsys, monkeypatch):
    f = tmp_path / "q.txt"
    f.write_text("# h\ncâu a\ncâu a\ncâu b\n", encoding="utf-8")
    assert J.main(["--base-url", "http://x", "--file", str(f), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["queries"] == 2
    monkeypatch.setattr(J, "warm", lambda *a, **k: {"queries": 2, "hit": 0, "miss": 0, "noCache": 0, "errors": 2,
                                                     "errorSamples": [], "seconds": 0.0})
    assert J.main(["--base-url", "http://x", "--file", str(f)]) == 1
