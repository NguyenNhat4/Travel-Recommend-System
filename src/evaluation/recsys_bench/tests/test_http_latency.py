"""`http-latency` (Day 2 C): guest path và users path qua httpx.MockTransport — không mạng, không DB."""
from __future__ import annotations

import json

import httpx
import pytest

from src.evaluation.recsys_bench import http_latency as H


def _server(calls: list):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, dict(request.url.params), request.headers.get("X-Service-Token")))
        if request.url.path == H.INTERNAL_PATH and request.headers.get("X-Service-Token") != "t" * 32:
            return httpx.Response(401, json={"error": {"code": "UNAUTHORIZED"}})
        user = request.url.params.get("cdp_user_id")
        if user == "bad":
            return httpx.Response(500, json={"error": {"code": "INTERNAL"}})
        k = int(request.url.params["k"])
        return httpx.Response(200, json={"strategy": "popular" if not user else "cross_vertical",
                                         "recommendations": [{"productId": f"p{i}"} for i in range(k)],
                                         "diagnostics": {"latencyMs": 120 if not user else 300}})
    return handler


def test_guest_path_repeats_k_gets_and_summarizes():
    calls: list = []
    client = httpx.Client(transport=httpx.MockTransport(_server(calls)))
    samples = H.measure("http://x/", runs=3, k=5, timeout_s=5, client=client)
    assert len(samples) == 15 and all(c[0] == H.GUEST_PATH and c[2] is None for c in calls)
    s = H.summarize(samples, drop_first=True)
    assert s["path"] == "guest" and s["latency_ms"]["n"] == 10 and s["latency_ms"]["p95"] == 120
    assert s["strategies"] == {"popular": 15} and s["n_items_min"] == 5 and s["n_error"] == 0
    assert H.summarize(samples, drop_first=False)["latency_ms"]["n"] == 15


def test_users_path_requires_token_and_records_errors(tmp_path, monkeypatch):
    calls: list = []
    users = tmp_path / "users.json"
    users.write_text(json.dumps({"users": [{"cdpUserId": "u1"}, {"cdpUserId": "bad"}]}), encoding="utf-8")
    ids = H.load_users(users)
    assert ids == ["u1", "bad"]
    monkeypatch.delenv("AUTH_SERVICE_TOKEN", raising=False)
    with pytest.raises(H.HttpLatencyError, match="AUTH_SERVICE_TOKEN"):
        H.measure("http://x", runs=1, k=5, timeout_s=5, users=ids, client=httpx.Client(transport=httpx.MockTransport(_server(calls))))
    monkeypatch.setenv("AUTH_SERVICE_TOKEN", "t" * 32)
    samples = H.measure("http://x", runs=2, k=5, timeout_s=5, users=ids, client=httpx.Client(transport=httpx.MockTransport(_server(calls))))
    assert len(samples) == 4 and calls[0][0] == H.INTERNAL_PATH and calls[0][1]["cdp_user_id"] == "u1"
    s = H.summarize(samples, drop_first=True)
    assert s["n_ok"] == 2 and s["n_error"] == 2 and s["errors"][0]["user"] == "bad" and "500" in s["errors"][0]["error"]
    assert s["latency_ms"]["p50"] == 300 and s["strategies"] == {"cross_vertical": 2}
    p = H.write(tmp_path / "run", base_url="http://x", samples=samples, summary=s, meta={"runId": "r"})
    assert json.loads(p.read_text(encoding="utf-8"))["summary"]["n_ok"] == 2


def test_load_users_rejects_empty(tmp_path):
    p = tmp_path / "u.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(H.HttpLatencyError):
        H.load_users(p)


def test_cli_guest(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from src.evaluation.recsys_bench.__main__ import app
    calls: list = []
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: real(transport=httpx.MockTransport(_server(calls))))
    monkeypatch.setenv("RECSYS_HOME", str(tmp_path))
    r = CliRunner().invoke(app, ["http-latency", "--base-url", "http://fake", "--runs", "2", "--k", "3", "--run-id", "t"])
    assert r.exit_code == 0, r.output
    assert "guest" in r.output and (tmp_path / "runs" / "t" / "http_latency.json").exists()
