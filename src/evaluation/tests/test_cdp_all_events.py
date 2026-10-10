import json

from src.backend.app.infrastructure.cdp.local_cdp_client import LocalCdpClient


def test_local_cdp_reader_returns_all_events_without_mutating_source(tmp_path):
    source = tmp_path / "events.jsonl"
    source.write_text(
        json.dumps({"cdpUserId": "u1", "eventName": "purchase", "productId": "p1", "timestamp": "2026-01-01T00:00:00Z"})
        + "\n"
        + json.dumps({"cdpUserId": "u2", "eventName": "product_view", "productId": "p2", "timestamp": "2026-01-02T00:00:00Z"})
        + "\n",
        encoding="utf-8",
    )
    client = LocalCdpClient(str(source))

    assert client.all_events() == [
        {"cdpUserId": "u1", "eventName": "purchase", "productId": "p1", "timestamp": "2026-01-01T00:00:00Z"},
        {"cdpUserId": "u2", "eventName": "product_view", "productId": "p2", "timestamp": "2026-01-02T00:00:00Z"},
    ]
    assert len(source.read_text(encoding="utf-8").splitlines()) == 2
